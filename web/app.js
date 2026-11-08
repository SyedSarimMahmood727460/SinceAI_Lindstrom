/* Value Review dashboard: state, API calls and page rendering. Numbers come only from the API. */
(() => {
'use strict';

const {Components, PRI, esc, fmtM, rangeText, badges, weight, obsHtml, isSimple} = window.VR;

const SUGGESTED_PROMPTS = [  // pack sheet Suggested_Prompts
  'Show the value created for NorthStar Foods Group in 2025.',
  'Focus on water and emissions for the food-industry sites.',
  'Which sites have the greatest textile-allocation optimization potential?',
  'How can we improve our performance next year?',
  'Compare our circular service with local laundry.',
  'Prepare five discussion points for the annual steering committee.',
];
const PAGES = {
  meeting: null,  // the meeting flow renders its own step titles
  overview: null,  // title built from the review
  sites: ['Sites', ""],
  footprint: ['Environmental impact', "Compared with the selected baseline. Ranges show low–high sensitivity."],
  circularity: ['Circularity', ""],
  steering: ['Steering pack', ""],
  methodology: ['Method & assumptions', "Boundaries, baseline, sources and limitations."],
  readiness: ['Data readiness', ""],
  vs_diy: ['Compare alternatives', "Do-it-yourself figures are illustrative until you enter the customer's own numbers."],
  growth: ['Opportunities', "Per year, for the whole account."],
  intel: ['Customer background', "Public sources only. Separate from the review figures."],
  fit: ['How it fits Lindström', ""],
};
// Components that show the account's figures; on an empty filter they say "No data for this filter".
// Growth is account-wide (not filtered); intelligence and the fit page do not use the review figures.
const STATIC_COMPONENTS = new Set(['meeting_flow', 'methodology', 'assumption_table', 'data_quality', 'readiness_table', 'discussion_points',
  'growth_inputs', 'growth_levers', 'intel_page', 'fit_page']);
const SOURCE_LABEL = {prompt: 'from your prompt', chips: 'your selection', customer: "customer's stated priorities + industry default",
  industry: 'industry default'};

const MODE_KEY = 'vr.mode';
function storedMode() { try { return localStorage.getItem(MODE_KEY) === 'expert' ? 'expert' : 'simple'; } catch (e) { return 'simple'; } }
const S = {account: null, period: '2025', product: '', serviceLine: '', baseline: 'B_LOCAL', sens: 'base', priorities: null,
  prioritySource: null, audience: 'kam', view: 'meeting', step: 1, site: null, sort: null, intentText: '', mode: storedMode()};
// A reload keeps the meeting step: #meeting/N (design §3).
const hashStep = () => { const m = /^#meeting\/([1-5])$/.exec(location.hash); return m ? +m[1] : null; };
if (hashStep()) S.step = hashStep();
let R = null, siteReview = null, MODULES = [], ACCOUNTS = [], INTERNAL = [], ASSUMPTIONS = {};
// State for the DIY, growth, intelligence and fit pages (passed to the components as ctx.ext).
const GROWTH_SENT = {};  // account -> growth inputs last saved in this session (kept when review.growth is null)
const EXT = {
  spec: {}, catalogue: null, fit: undefined, storedGrowth: {},
  intel: {company: 'Fazer Group', website: '', report: null, error: '', loading: false, snapshots: [], auto: false},
  growthStored: () => growthStored(),
};
const productNames = {};
const charts = {};
let reqSeq = 0, siteSeq = 0;
const $ = id => document.getElementById(id);

// ---------- API ----------
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (e) { /* not JSON */ }
    const err = new Error(`${r.status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
    err.status = r.status; err.detail = detail; throw err;
  }
  return r;
}
const getJSON = async path => (await api(path)).json();

function reviewQuery(extra) {
  const p = new URLSearchParams({period: S.period, baseline: S.baseline, sens: S.sens, audience: S.audience});
  if (S.product) p.set('product', S.product);
  if (S.serviceLine) p.set('service_line', S.serviceLine);
  if (S.priorities && S.priorities.length) {
    p.set('priorities', S.priorities.join(','));
    if (S.prioritySource === 'prompt') p.set('hint', 'prompt');
  }
  Object.entries(extra || {}).forEach(([k, v]) => p.set(k, v));
  return `/accounts/${encodeURIComponent(S.account)}/review?${p}`;
}

/** Fetch and render the review; resolves true when this load rendered, false when it failed or a
 * newer load superseded it. */
async function load() {
  const seq = ++reqSeq;
  busy(true);
  try {
    const r = await getJSON(reviewQuery());
    if (seq !== reqSeq) return false;
    R = r;
    (R.meta.products || []).forEach(p => { productNames[p.id] = p.name; });
    if (S.site && !R.sites.some(s => s.node_id === S.site)) S.site = null;
    render();
    if (S.site) loadSite();
    if (!EXT.storedGrowth[S.account]) {  // growth form prefill, also a lone stored expansion price
      fetchStoredGrowth().then(g => { if (g && seq === reqSeq && (S.view === 'growth' || S.view === 'meeting')) renderPageKeepFocus(); });
    }
    return true;
  } catch (e) {
    if (seq === reqSeq) toast(`Could not load the review (${e.message})`, true);
    return false;
  } finally {
    if (seq === reqSeq) busy(false);
  }
}

async function loadSite() {
  const id = S.site, seq = ++siteSeq;
  siteReview = null;
  try {
    const r = await getJSON(reviewQuery({site: id}));
    if (seq !== siteSeq || S.site !== id) return;
    siteReview = r;
    if (S.view === 'sites') renderPage();
  } catch (e) { toast(`Could not load site trends (${e.message})`, true); }
}

// ---------- rendering ----------
const activePri = () => (R ? R.context.active_priorities : []);
const kpiOf = id => R.kpis.find(k => k.metric_id === id) || null;

function render() {
  if (!R) return;
  $('cust').value = S.account; $('period').value = S.period; $('base').value = S.baseline; $('sens').value = S.sens;
  document.querySelectorAll('#aud button').forEach(b => { const on = b.dataset.aud === S.audience; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
  document.body.classList.toggle('aud-customer', S.audience === 'customer');
  renderProducts();
  renderServiceLines();
  renderSettingsDot();
  renderChips();
  renderInterp();
  renderPage();
}

function renderProducts() {
  const ids = (R.meta.products || []).map(p => p.id);
  let h = '<option value="">All products</option>' + R.meta.products.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  if (S.product && !ids.includes(S.product))
    h += `<option value="${esc(S.product)}">${esc(productNames[S.product] || S.product)} (not rented by this customer)</option>`;
  $('product').innerHTML = h;
  $('product').value = S.product;
}

function renderServiceLines() {
  const lines = R.meta.service_lines || [];
  let h = '<option value="">All service lines</option>' + lines.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join('');
  if (S.serviceLine && !lines.includes(S.serviceLine)) h += `<option value="${esc(S.serviceLine)}">${esc(S.serviceLine)} (not used by this customer)</option>`;
  const el = $('sline');
  el.innerHTML = h; el.value = S.serviceLine;
  el.disabled = lines.length < 2 && !S.serviceLine;
  el.title = el.disabled ? `This customer uses one service line${lines.length ? ` (${lines[0]})` : ''}` : '';
}

function renderMode() {
  document.querySelectorAll('#mode button').forEach(b => { const on = b.dataset.mode === S.mode; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
  document.body.classList.toggle('simple', S.mode === 'simple');
  document.body.classList.toggle('expert', S.mode === 'expert');
  renderSettingsDot();
}

/** The Settings button shows a dot when any setting in the popover differs from its default;
 * the Ask button shows one while a stated priority tailors the view. */
const SETTING_DEFAULTS = {product: '', serviceLine: '', sens: 'base', audience: 'kam', mode: 'simple'};
function renderSettingsDot() {
  const changed = Object.entries(SETTING_DEFAULTS).some(([k, v]) => S[k] !== v);
  $('settingsDot').hidden = !changed;
  $('settingsDotSr').textContent = changed ? ' (changed from the defaults)' : '';
  $('askDot').hidden = !(S.priorities && S.priorities.length);
}

function renderChips() {
  const ap = activePri(), had = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.chip : null;
  $('pchips').innerHTML = Object.entries(PRI).map(([k, l]) => {
    const i = ap.indexOf(k);
    return `<button type="button" class="chip ${i >= 0 ? 'on' : ''}" data-chip="${k}" aria-pressed="${i >= 0}">${i >= 0 ? `<sup>${i + 1}</sup> ` : ''}${l}</button>`;
  }).join('');
  $('psugg').innerHTML = SUGGESTED_PROMPTS.slice(0, 4).map(p => `<button type="button" data-prompt="${esc(p)}">${esc(p)}</button>`).join('');
  if (had) { const b = $('pchips').querySelector(`[data-chip="${had}"]`); if (b) b.focus(); }  // keyboard toggling keeps its place
}

function renderInterp() {
  const ap = activePri(), src = R.context.priority_source;
  const srcLabel = src === 'industry' || src === 'customer' ? `${SOURCE_LABEL[src]} for ${R.meta.node.industry}` : SOURCE_LABEL[src];
  $('interp').innerHTML = `<div class="interp-h">Showing now</div>` +
    (S.intentText ? `<div>“${esc(S.intentText)}”</div>` : '') +
    `<div>Focus: <b>${esc(ap.map(p => PRI[p] || p).join(' → ') || 'balanced')}</b> <span class="muted">(${esc(srcLabel)})</span></div>` +
    `<div>Compared with: <b>${esc(R.meta.baseline.name)}</b> · ${esc(R.meta.sensitivity)} case</div>` +
    (S.audience === 'customer' ? '<div><b>Customer view</b> (internal figures hidden)</div>' : '') +
    (R.context.industry_note ? `<div class="why">Why this view: ${esc(R.context.industry_note)}</div>` : '');
}

function moduleStatus(mod) {
  const ind = R.meta.node.industry;
  if (!(mod.industries.includes('*') || mod.industries.includes(ind))) return {show: false, reason: `not used for ${ind}`};
  const missing = mod.required_metrics.filter(id => { const k = kpiOf(id); return !k || k.value == null; });
  if (!missing.length) return {show: true};
  // Customer view: a module missing only internal (non-customer-facing) metrics is not a data gap.
  if (S.audience === 'customer' && missing.every(id => INTERNAL.includes(id))) return {show: false, internal: true};
  const absent = missing.filter(id => !kpiOf(id));
  const why = S.audience === 'customer' && absent.length ? 'not customer-facing / missing data' : 'missing data';
  return {show: false, reason: `${why} (${missing.join(', ')})`};
}

// KPI rows lead their page (as in the mockup); other modules follow by priority score (spec §8.3).
const pin = m => (m.component === 'kpi_row' && m.pack !== 'financial' ? 1 : 0);
const emptyFilter = () => R.kpis.length > 0 && R.kpis.every(k => k.value == null);

function hiddenModules() {
  if (emptyFilter()) return [];
  const own = MODULES.map(m => ({m, st: moduleStatus(m)})).filter(x => !x.st.show && !x.st.internal)
    .map(x => ({id: x.m.id, page: x.m.page, reason: x.st.reason}));
  const fromApi = (R.data_quality.hidden_modules || []).map(h => (typeof h === 'string' ? {id: h, page: '', reason: 'hidden by the API'} : h));
  return [...own, ...fromApi.filter(h => !own.some(o => o.id === h.id))];
}

function filterText() {
  return `${S.product ? ` · product: ${esc(productNames[S.product] || S.product)}` : ''}` +
    `${S.serviceLine ? ` · service line: ${esc(S.serviceLine)}` : ''}`;
}

function pageHead() {
  const n = R.meta.node, pl = $('period').selectedOptions[0];
  if (S.view === 'meeting') return '';  // the meeting flow carries its own step titles
  if (S.view === 'overview') {
    const sites = kpiOf('sites');
    return `<h1>${esc(n.name)} — Annual value review ${esc(pl ? pl.textContent : R.meta.period)}</h1>
      <p class="lead">${esc(n.industry)} · ${esc(n.segment)} · ${esc(sites ? fmtM(sites) : '–')} delivery sites · ${esc(n.countries.join(', '))}` +
      `${filterText()}</p>`;
  }
  const [t, l] = PAGES[S.view];
  return `<h1>${esc(t)}</h1>${l ? `<p class="lead">${VR.gloss(l)}</p>` : ''}`;
}

function renderPage() {
  if (!R) return;
  document.querySelectorAll('nav a').forEach(a => {
    const on = a.dataset.v === S.view;
    a.classList.toggle('on', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('pageHead').innerHTML = pageHead();
  Object.keys(charts).forEach(id => { charts[id].destroy(); delete charts[id]; });
  VR.resetLocal();
  syncHash();
  ensurePageData(S.view);
  const pri = activePri(), empty = emptyFilter();
  const ctx = {R, S, pri, kpi: kpiOf, siteReview, hidden: hiddenModules(), ext: EXT};
  const mods = MODULES.filter(m => m.page === S.view)
    .map((m, i) => ({m, i, w: weight(m.priority_tags, pri)}))
    .sort((a, b) => pin(b.m) - pin(a.m) || b.w - a.w || a.i - b.i).map(x => x.m);
  const entries = [];
  for (const mod of mods) {
    if (empty && !STATIC_COMPONENTS.has(mod.component)) {
      entries.push({id: mod.id, cls: '', html: '<div class="card empty">No data for this filter</div>', charts: []});
      continue;
    }
    if (!moduleStatus(mod).show) continue;
    let res;
    try { res = Components[mod.component]({...ctx, mod}); } catch (e) {
      console.warn('module failed', mod.id, e);
      res = {html: `<div class="card empty">Could not render ${esc(mod.id)}</div>`};
    }
    if (!res) continue;
    entries.push({id: mod.id, cls: res.cls || '', html: res.html, charts: res.charts || []});
  }
  const LY = window.VRLayout && window.VRLayout.supports(S.view) ? window.VRLayout : null;
  const arranged = LY ? LY.arrange(S.view, S.account, entries) : null;
  const shown = arranged ? arranged.shown : entries;
  const pending = shown.flatMap(e => e.charts);
  const out = shown.map(e => `<div class="mod ${e.cls}" data-mod="${esc(e.id)}"${LY ? LY.attrs(e.id) : ''}>${LY ? LY.chrome(e.id) : ''}${e.html}</div>`);
  if (LY) $('pageHead').insertAdjacentHTML('beforeend', LY.toolbar());
  $('page').classList.toggle('editing', !!(LY && LY.isEditing()));
  $('page').innerHTML = out.join('') || '<div class="mod"><div class="card empty">No modules for this page.</div></div>';
  if (window.Chart) pending.forEach(c => mkChart(c));
  else if (pending.length) toast('Charts unavailable (Chart.js did not load)', true);
}

/** Re-render after background data arrives (catalogue, stored growth inputs) without dropping the
 * keyboard: focus that was inside the page goes back to the current step button (if it was in the
 * step bar) or the step title. */
function renderPageKeepFocus() {
  const a = document.activeElement, inPage = !!(a && a !== document.body && $('page').contains(a));
  const inBar = inPage && !!a.closest('.msteps');
  renderPage();
  if (inPage && !$('page').contains(document.activeElement)) {
    if (S.view === 'meeting') focusStep(S.step, inBar);
    else { const h = document.querySelector('#pageHead h1'); if (h) { h.tabIndex = -1; h.focus({preventScroll: true}); } }
  }
}

// ---------- meeting flow steps ----------
/** Keep S.step on a visible step (the customer view drops an empty step 4) and mirror it in the URL hash. */
function syncHash() {
  let want = '';
  if (S.view === 'meeting') {
    const vis = VR.meetingSteps(R, S.audience);
    if (!vis.includes(S.step)) S.step = [...vis].reverse().find(n => n < S.step) || vis[0];
    want = `#meeting/${S.step}`;
  }
  if (location.hash !== want) history.replaceState(null, '', want || location.pathname + location.search);
}
function setStep(n, focusBar) {
  if (!R || S.view !== 'meeting') return;
  const vis = VR.meetingSteps(R, S.audience);
  if (!vis.includes(n)) return;
  S.step = n; closeDrawer(); renderPage(); window.scrollTo(0, 0);
  focusStep(n, focusBar);
}
/** After a step change keep the keyboard in the step bar when it started there; otherwise move
 * focus to the new step's title so screen readers announce it. */
function focusStep(n, focusBar) {
  const el = focusBar ? document.querySelector(`.msteps [data-step="${n}"]`) : document.querySelector('.mtitle');
  if (el) el.focus({preventScroll: true});
}
/** ←/→ step through the meeting when focus is not in a form field. */
function stepKey(e) {
  if (S.view !== 'meeting' || !R || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return false;
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return false;
  const el = e.target;
  if (el && el.closest && el.closest('input,select,textarea,[contenteditable],details[open] form')) return false;
  if ($('drawer').classList.contains('open')) return false;
  const vis = VR.meetingSteps(R, S.audience), i = vis.indexOf(S.step);
  const n = vis[i + (e.key === 'ArrowRight' ? 1 : -1)];
  if (n == null) return false;
  setStep(n, !!(el && el.closest && el.closest('.msteps')));
  return true;
}

/** The demo's reference: the account's do-it-yourself total for the full year (2025-Q2 -> 2025), the
 * whole account (no product or service-line filter), base sensitivity, local-laundry baseline (B_LOCAL):
 * dto.diy_total.range.base. The current review is used only when it already is exactly that view;
 * otherwise that view is fetched, so the demo contract is the same whatever quarter or filter is on screen. */
const DEMO_BASELINE = 'B_LOCAL';
async function demoDiyBase(acct) {
  const year = String(S.period).slice(0, 4);
  let r = R;
  const same = R && S.period === year && !S.product && !S.serviceLine && S.sens === 'base' && S.baseline === DEMO_BASELINE;
  if (!same) {
    const p = new URLSearchParams({period: year, baseline: DEMO_BASELINE, sens: 'base', audience: S.audience});
    r = await getJSON(`/accounts/${encodeURIComponent(acct)}/review?${p}`);
  }
  const t = r && r.dto && r.dto.diy_total;
  const base = t && t.range && t.range.base != null ? t.range.base : null;
  return base != null && isFinite(base) ? base : null;
}
/** Demo scenario (design §6, controller ruling): contract price = 60% of the account's full-year, unfiltered,
 * base-case, local-laundry do-it-yourself total (demoDiyBase), to the nearest €10,000 (skipped when there
 * is none), so it is the same on 2025 and on 2025-Q2; 4 more sites; mats, or
 * washroom if the account already uses mats. Merged into the stored inputs (stored entries win; the
 * demo service line is added), then the full set is PUT. The toast follows the reloaded review. */
async function loadDemo(btn) {
  if (!R || S.audience === 'customer') return;
  const acct = S.account;
  if (btn) { btn.disabled = true; btn.textContent = 'Loading demo…'; }
  try {
    const [st, cat, base] = await Promise.all([getJSON(`/accounts/${encodeURIComponent(acct)}/inputs?include=growth`),
      catalogue(), demoDiyBase(acct)]);
    if (acct !== S.account) return;
    const used = new Set(R.meta.service_lines || []);
    const mats = (cat || []).find(c => c.id === 'mats');
    const line = used.has(mats ? mats.service_line : 'Mats') ? 'washroom' : 'mats';
    const price = base ? Math.round(0.6 * base / 1e4) * 1e4 : 0;
    const demo = {extra_sites: 4, ...(price > 0 ? {[VR.INPUT_CONTRACT]: price} : {})};
    const g = growthBody(st.growth);
    const body = {...demo, ...diyStored(st.inputs), ...g};
    body.extra_service_lines = [...new Set([...(g.extra_service_lines || []), line])];
    await saveInputs(body, null, "Demo scenario loaded — example numbers; reset with 'Reset to defaults' in Your numbers and 'Clear' in step 4.");
  } catch (e) {
    toast(`Could not load the demo scenario (${e.message})`, true);
  } finally { if (btn && btn.isConnected) { btn.disabled = false; btn.textContent = 'Load demo scenario'; } }
}
/** The service catalogue, loaded once (shared by the meeting, growth and intelligence pages). */
let catLoad = null;
function catalogue() {
  if (EXT.catalogue) return Promise.resolve(EXT.catalogue);
  if (!catLoad) {
    catLoad = getJSON('/config/service-catalogue').then(c => { EXT.catalogue = c; return c; })
      .catch(e => { console.warn('catalogue unavailable', e); EXT.catalogue = []; return []; })
      .finally(() => { catLoad = null; });
  }
  return catLoad;
}

// ---------- DIY, growth, intelligence and fit pages ----------
/** Load what a page needs once (fit content, service catalogue, intel snapshots), then re-render. */
function ensurePageData(view) {
  const rerender = () => { if (S.view === view) renderPageKeepFocus(); };
  if (view === 'fit' && EXT.fit === undefined && !EXT.fitLoading) {
    EXT.fitLoading = true;
    getJSON('/config/fit').then(f => { EXT.fit = f; }).catch(e => { EXT.fit = null; toast(`Could not load the page (${e.message})`, true); })
      .finally(() => { EXT.fitLoading = false; rerender(); });
  }
  if ((view === 'growth' || view === 'intel' || view === 'meeting') && EXT.catalogue === null && !catLoad) catalogue().then(rerender);
  if (view === 'intel' && !EXT.intel.auto && S.audience === 'kam') {
    // first visit: list the snapshots and open the example company (Fazer Group) straight away
    EXT.intel.auto = true;
    getJSON('/ai/status').then(s => { EXT.intel.liveResearch = !!(s && s.live_research); rerender(); }).catch(() => { /* banner stays hidden */ });
    getJSON('/intel/snapshots').then(list => {
      EXT.intel.snapshots = list || [];
      const pre = EXT.intel.snapshots.find(s => s.company === 'Fazer Group') || EXT.intel.snapshots[0];
      if (pre && !EXT.intel.report && !EXT.intel.loading) runIntel(pre.company, '', true); else rerender();
    }).catch(e => { console.warn('snapshots unavailable', e); rerender(); });
  }
}

let intelSeq = 0;
/** `preferSnapshot`: snapshot chips and the auto-open use the committed snapshot (no live call);
 * only the Research button may start live research. */
async function runIntel(company, website, preferSnapshot = false) {
  company = (company || '').trim(); website = (website || '').trim();
  const I = EXT.intel;
  I.company = company; I.website = website;
  if (!company) { I.error = 'Enter a company name.'; I.report = null; renderPage(); return; }
  const seq = ++intelSeq;
  I.loading = true; I.error = ''; renderPage();
  try {
    const rep = await (await api('/intel', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({company, website: website || null, prefer_snapshot: !!preferSnapshot})})).json();
    if (seq !== intelSeq) return;
    I.report = rep;
  } catch (e) {
    if (seq !== intelSeq) return;
    I.report = null;
    const d = e.detail;
    I.error = typeof d === 'string' ? d : (Array.isArray(d) && d[0] && d[0].msg ? d[0].msg.replace(/^Value error, /, '') : e.message);
  } finally {
    if (seq === intelSeq) { I.loading = false; if (S.view === 'intel') renderPage(); }
  }
}

const AMBIGUOUS = 'Use digits only, e.g. 120000 or 2.5';
/** UI-side number parsing: decimal comma → dot, spaces dropped, blank → undefined (= use the default).
 * Thousands-separator forms ("120,000", "1.234,5") are ambiguous: {bad: message}, shown inline.
 * Anything else that is not a plain number is sent as text so the API answers with its 422 message. */
function normNum(raw) {
  const t = String(raw == null ? '' : raw).replace(/[\s  ]/g, '');
  if (t === '') return undefined;
  const commas = (t.match(/,/g) || []).length, dots = (t.match(/\./g) || []).length;
  if ((commas && dots) || commas > 1 || dots > 1 || /^[-+]?[1-9]\d{0,2},\d{3}$/.test(t)) return {bad: AMBIGUOUS};
  const s = t.replace(',', '.');
  return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s) ? Number(s) : s;
}
/** normNum for a form field; an ambiguous number stops the save with an inline message. */
function fieldNum(el, field) {
  const v = el ? normNum(el.value) : undefined;
  if (v && typeof v === 'object') throw {field, msg: v.bad};
  return v;
}

/** The do-it-yourself inputs as stored (KAM-entered keys only), rebuilt from review.dto.inputs
 * (or from the rows of GET /inputs). */
function diyStored(rows = R && R.dto && R.dto.inputs) {
  const out = {};
  (rows || []).filter(r => r.source === 'kam').forEach(r => {
    if (r.value != null) out[r.key] = r.value;
    if (r.key === VR.INPUT_CONTRACT) return;
    if (r.low != null && r.low !== r.value) out[r.key + '_low'] = r.low;
    if (r.high != null && r.high !== r.value) out[r.key + '_high'] = r.high;
  });
  return out;
}

/** The growth inputs as stored (GET /inputs?include=growth, also a lone expansion price),
 * else review.growth, else what this session last saved. */
function growthStored() {
  const st = EXT.storedGrowth[S.account];
  if (st) {
    const dates = Object.values(st.entered_at || {}).sort();
    return {...st, entered_at: dates.length ? dates[dates.length - 1] : null};
  }
  const g = R && R.growth && R.growth.inputs;
  if (g) return g;
  return GROWTH_SENT[S.account] || null;
}
/** Fetch the account's stored growth inputs (cached per account until the next save). */
async function fetchStoredGrowth(account = S.account) {
  if (EXT.storedGrowth[account]) return EXT.storedGrowth[account];
  try {
    const r = await getJSON(`/accounts/${encodeURIComponent(account)}/inputs?include=growth`);
    EXT.storedGrowth[account] = r.growth;
    return r.growth;
  } catch (e) { console.warn('stored growth inputs unavailable', e); return null; }
}
function growthBody(g) {
  const out = {};
  if (!g) return out;
  ['extra_sites', 'extra_wearers', 'expansion_price_eur_per_site_year'].forEach(k => { if (g[k] != null && g[k] !== 0) out[k] = g[k]; });
  if ((g.extra_service_lines || []).length) out.extra_service_lines = [...g.extra_service_lines];
  return out;
}

function diyFromForm(form) {
  const spec = EXT.spec, body = {};
  ((R.dto && R.dto.inputs) || []).forEach(r => {
    const get = part => fieldNum(form.querySelector(`[data-in="${CSS.escape(r.key)}"][data-part="${part}"]`), part === 'value' ? r.key : `${r.key}_${part}`);
    const v = get('value');
    if (v !== undefined) {
      const def = spec[r.key] ? spec[r.key].default : undefined;
      if (r.source === 'kam' || v !== def) body[r.key] = v;  // an untouched default is not "entered"
    }
    const lo = get('low'), hi = get('high');
    if (lo !== undefined) body[r.key + '_low'] = lo;
    if (hi !== undefined) body[r.key + '_high'] = hi;
  });
  return body;
}

function growthFromForm(form) {
  const g = {};
  ['extra_sites', 'extra_wearers', 'expansion_price_eur_per_site_year'].forEach(k => {
    const v = fieldNum(form.querySelector(`[data-g="${k}"]`), k);
    if (v !== undefined && v !== 0) g[k] = v;
  });
  const lines = [...form.querySelectorAll('[data-gline]:checked')].map(el => el.dataset.gline);
  if (lines.length) g.extra_service_lines = lines;
  return g;
}

/** Show a 422 message next to the field it names (form values stay as typed). */
function showFormError(form, detail) {
  form.querySelectorAll('.err-row,.gerr').forEach(el => el.remove());
  const general = form.querySelector('.form-err');
  general.textContent = '';
  const msg = typeof detail === 'string' ? detail : (Array.isArray(detail) && detail[0] && detail[0].msg) || 'The inputs could not be saved.';
  const m = /^([a-z0-9_]+?)(_low|_high)?:\s*(.*)$/i.exec(msg);
  const key = m && m[1], part = m && m[2] ? ` (${m[2].slice(1)})` : '';
  const row = key && form.querySelector(`tr[data-key="${CSS.escape(key)}"]`);
  const gf = key && form.querySelector(`.gfield[data-key="${CSS.escape(key)}"]`);
  if (row) {
    const label = row.querySelector('label') ? row.querySelector('label').textContent : key;
    const tr = document.createElement('tr'); tr.className = 'err-row';
    tr.innerHTML = `<td colspan="6" class="l"><span class="err">${esc(label + part)}: ${esc(m[3])}</span></td>`;
    row.after(tr);
    const inp = row.querySelector(`[data-part="${m[2] ? m[2].slice(1) : 'value'}"]`); if (inp) inp.focus();
  } else if (gf) {
    const label = gf.querySelector('label,.glabel'); const div = document.createElement('div'); div.className = 'err gerr';
    div.textContent = `${label ? label.textContent : key}: ${m[3]}`; gf.appendChild(div);
    const inp = gf.querySelector('input'); if (inp) inp.focus();
  } else general.innerHTML = `<span class="err">${esc(msg)}</span>`;
}

/** PUT replaces the whole stored set, so every save sends the DIY and the growth inputs together.
 * `done` is toasted only once the review has reloaded successfully; otherwise an error toast. */
async function saveInputs(body, form, done) {
  const btns = form ? [...form.querySelectorAll('button')] : [];
  btns.forEach(b => { b.disabled = true; });
  try {
    await api(`/accounts/${encodeURIComponent(S.account)}/inputs`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  } catch (e) {
    btns.forEach(b => { b.disabled = false; });
    if (e.status === 422 && form) showFormError(form, e.detail); else toast(`Could not save (${e.message})`, true);
    return;
  }
  const g = {};
  ['extra_sites', 'extra_wearers', 'extra_service_lines', 'expansion_price_eur_per_site_year'].forEach(k => { if (k in body) g[k] = body[k]; });
  GROWTH_SENT[S.account] = Object.keys(g).length ? g : null;
  delete EXT.storedGrowth[S.account];
  if (await load()) toast(done);
  else toast('Saved, but the review could not be refreshed — reload the page to see the new figures', true);
}

async function onSubmit(e) {
  const form = e.target.closest('form[data-form]'); if (!form) return;
  e.preventDefault();
  const kind = form.dataset.form;
  if (kind === 'intel') { runIntel($('intelCompany').value, $('intelWebsite').value); return; }
  let part;
  try { part = kind === 'diy' ? diyFromForm(form) : growthFromForm(form); } catch (err) {
    if (err && err.field) { showFormError(form, `${err.field}: ${err.msg}`); return; }
    throw err;
  }
  if (kind === 'diy') {
    await fetchStoredGrowth();
    saveInputs({...part, ...growthBody(growthStored())}, form, 'Saved: the comparison uses your numbers');
  } else if (kind === 'growth') saveInputs({...diyStored(), ...part}, form, 'Saved: growth opportunity sized');
}

async function resetDiy(form) {
  if (!window.confirm('Reset all do-it-yourself inputs to the defaults? Values the account manager entered (including the contract price) are removed; the growth inputs are kept.')) return;
  await fetchStoredGrowth();
  saveInputs(growthBody(growthStored()), form, 'Reset: the comparison uses the defaults');
}

/** Placeholders of low/high follow the value field: the default range, or "same as value" once changed. */
function onInput(e) {
  const el = e.target;
  if (!el.matches || !el.matches('[data-in][data-part="value"]')) return;
  const key = el.dataset.in, s = EXT.spec[key]; if (!s) return;
  const v = normNum(el.value), atDefault = v === undefined || v === s.default;
  const tr = el.closest('tr');
  ['low', 'high'].forEach(p => { const x = tr.querySelector(`[data-part="${p}"]`); if (x) x.placeholder = atDefault ? String(s[p]) : '= value'; });
}

/** Drawer for results without an /explain endpoint (do-it-yourself and growth figures). */
function explainLocal(id) {
  const m = VR.LOCAL[id]; if (!m) return;
  const reg = (ASSUMPTIONS.register || []).filter(a => (m.assumptions || []).includes(a.id));
  const assum = reg.length ? `<table><tr><th class="l">ID</th><th class="l">Assumption</th><th class="l">Value / rule</th><th class="l">Confidence</th></tr>${reg.map(a =>
    `<tr><td class="l">${esc(a.id)}</td><td class="l">${esc(a.assumption)}</td><td class="l">${esc(a.value_or_rule)}</td><td class="l">${esc(a.confidence)}</td></tr>`).join('')}</table>`
    : `<p class="small">${esc((m.assumptions || []).join(', ') || 'No assumptions.')}</p>`;
  const rng = m.range ? `<h3>Sensitivity (low / base / high)</h3><table><tr><th class="l">Case</th><th>Value</th></tr>${['low', 'base', 'high'].map(c =>
    `<tr class="${c === S.sens ? 'sel' : ''}"><td class="l">${c}${c === S.sens ? ' (selected)' : ''}</td><td>${esc(VR.fmtV(m.unit, m.range[c]))}</td></tr>`).join('')}</table>` : '';
  const kamIn = R.dto && (R.dto.inputs || []).some(i => i.source === 'kam') && /^dto_/.test(m.metric_id)
    ? '<p class="small">Uses figures entered by the account manager where given (see Your numbers).</p>' : '';
  const lin = m.lineage || {};
  const how = isSimple() ? '<p class="small">Switch to <button type="button" class="link" data-mode-set="expert">Expert detail</button> for the formula and data lineage.</p>'
    : `<h3>How it's calculated</h3><div class="formula">${esc(m.formula_text)}</div>
      <h3>Lineage</h3><p class="small">Facts: ${esc((lin.facts || []).join(', '))} · ${esc(VR.num(lin.rows))} rows</p>`;
  openDrawer(`<h2>${esc(m.label)}</h2><p class="small">${esc(R.meta.node.name)} · ${esc(S.period)}${/^growth_/.test(m.metric_id) ? ' · per year, whole account' : ''}</p>
    <p>${badges(m, true)}</p><p style="font-size:24px;font-weight:700;color:var(--navy);margin:6px 0">${esc(fmtM(m))}</p><p class="range">${esc(rangeText(m))}</p>
    ${kamIn}${how}${rng}<h3>Assumptions</h3>${assum}`);
}

function mkChart({id, type, data, options}) {
  const el = $(id); if (!el) return;
  const cs = getComputedStyle(document.documentElement);
  Chart.defaults.color = cs.getPropertyValue('--secondary').trim() || '#5e6b7e';
  Chart.defaults.borderColor = cs.getPropertyValue('--chart-grid').trim() || '#edf0f5';
  charts[id] = new Chart(el, {type, data, options: Object.assign({responsive: true, maintainAspectRatio: false,
    plugins: {legend: {position: 'bottom', labels: {boxWidth: 10, font: {size: 11}}}}, elements: {line: {tension: .3}}}, options || {})});
}

// ---------- drawer ----------
function openDrawer(h) { $('drawerBody').innerHTML = h; $('drawer').classList.add('open'); }
function closeDrawer() { $('drawer').classList.remove('open'); }

function metricAt(id, node) {
  if (node === R.meta.node.id) return kpiOf(id);
  const s = R.sites.find(x => x.node_id === node);
  return s ? s.metrics[id] || null : null;
}
const nodeName = node => (node === R.meta.node.id ? R.meta.node.name : ((R.sites.find(s => s.node_id === node) || {}).name || node));

async function explain(id, node) {
  const m = metricAt(id, node);
  openDrawer(`<h2>${esc(m ? m.label : id)}</h2><p class="small">Loading…</p>`);
  let ex;
  try {
    ex = await getJSON(`/metrics/${encodeURIComponent(id)}/explain?` + new URLSearchParams({node_id: node, period: S.period, baseline: S.baseline}));
  } catch (e) { openDrawer(`<h2>${esc(id)}</h2><p>Could not load the explanation (${esc(e.message)}).</p>`); return; }
  const d = ex.definition, res = ex.result, cur = m || res;
  const rng = cur.range ? `<h3>Sensitivity (low / base / high)</h3><table><tr><th class="l">Case</th><th>Value</th></tr>${['low', 'base', 'high'].map(c =>
    `<tr class="${c === S.sens ? 'sel' : ''}"><td class="l">${c}${c === S.sens ? ' (selected)' : ''}</td><td>${esc(VR.fmtV(cur.unit, cur.range[c]))}</td></tr>`).join('')}</table>` : '';
  const expertHint = '<p class="small">Switch to <button type="button" class="link" data-mode-set="expert">Expert detail</button> for the formula and data lineage.</p>';
  const assum = (ex.assumptions || []).length ? `<table><tr><th class="l">ID</th><th class="l">Assumption</th><th class="l">Value / rule</th><th class="l">Confidence</th></tr>${ex.assumptions.map(a =>
    `<tr><td class="l">${esc(a.id)}</td><td class="l">${esc(a.assumption)}</td><td class="l">${esc(a.value_or_rule)}</td><td class="l">${esc(a.confidence)}</td></tr>`).join('')}</table>
    <p class="small"><button type="button" class="link" data-go="methodology">Open the full assumption register</button></p>` : '<p class="small">No assumptions: a direct formula over source rows.</p>';
  const lin = res.lineage || {};
  const how = isSimple() ? '' : `<h3>How it's calculated</h3><div class="formula">${esc(d.formula_text || cur.formula_text)}</div>
    <p class="small">Aggregation: ${esc(d.aggregation)} · unit: ${esc(d.unit)} · inputs: ${esc((d.inputs || []).join(', '))}</p>`;
  const lineage = isSimple() ? expertHint : `<h3>Lineage</h3><p class="small">Facts: ${esc((lin.facts || []).join(', '))} · ${esc(VR.num(lin.rows))} rows · load ${esc((lin.load_ids || []).join(', '))}${(S.product || S.serviceLine) ? '<br>Lineage is shown for all products and service lines.' : ''}</p>`;
  openDrawer(`<h2>${esc(cur.label)}</h2><p class="small">${esc(nodeName(node))} · ${esc(S.period)}${S.product ? ' · product ' + esc(S.product) : ''}${S.serviceLine ? ' · service line ' + esc(S.serviceLine) : ''}</p>
    <p>${badges(cur, true)}</p>
    <p style="font-size:26px;font-weight:700;color:var(--navy);margin:6px 0">${esc(fmtM(cur))}</p><p class="range">${esc(rangeText(cur))}</p>
    ${cur.dq_warning ? `<div class="alert small">⚠ An input to this figure carries a ${VR.gloss('data-consistency warning')}. <button type="button" class="link" data-go="readiness">See Data readiness</button>.</div>` : ''}
    ${how}${rng}<h3>Assumptions</h3>${assum}
    ${lineage}`);
}

function evidence(idx) {
  const o = R.observations[idx]; if (!o) return;
  const acc = R.meta.node.id;
  const rows = o.evidence.map(([mid, node]) => {
    const here = metricAt(mid, node), whole = kpiOf(mid);
    return `<tr><td class="l">${esc((here || whole || {}).label || mid)} ${badges(here || whole)}</td>
      <td>${node === acc ? '–' : esc(fmtM(here))}</td><td>${esc(fmtM(whole))}</td></tr>`;
  }).join('');
  const siteNode = o.evidence.map(e => e[1]).find(n => n !== acc) || (o.node_id !== acc ? o.node_id : null);
  const formulas = [...new Set(o.evidence.map(e => e[0]))].map(mid => { const m = metricAt(mid, acc) || kpiOf(mid);
    return m ? `${m.label}: ${m.formula_text}` : mid; }).join('\n');
  openDrawer(`<h2>${o.rule_id === 'R8' ? '⚠ ' : ''}${esc(o.title)}</h2><p>${badges(o, true)}</p><p>${VR.gloss(VR.plainFinding(o.finding))}</p>
    <p><b>Next step:</b> ${esc(o.action)}</p>
    <h3>Evidence</h3><table><tr><th class="l">Metric</th><th>${esc(siteNode ? nodeName(siteNode) : 'Site')}</th><th>Account</th></tr>${rows}</table>
    ${siteNode ? `<p class="small"><button type="button" class="link" data-site="${esc(siteNode)}">Open ${esc(nodeName(siteNode))} drill-down</button></p>` : ''}
    ${isSimple() ? '<p class="small">Switch to <button type="button" class="link" data-mode-set="expert">Expert detail</button> for the rule, z-score and formulas.</p>' : `<h3>Rule ${esc(o.rule_id)}</h3><div class="formula">${o.z != null ? `Peer group: the account's sites. z = ${VR.num(o.z, 2)} (outlier when |z| ≥ 1.5).\n` : ''}Priority match (${esc(o.tags.join(', '))}) sets the display order (score ${VR.num(o.score, 0)}).
${esc(formulas)}</div>`}`);
}

// ---------- interaction ----------
function go(view) {
  if (!PAGES.hasOwnProperty(view)) return;
  if (view === 'intel' && S.audience === 'customer') view = 'meeting';  // preparation tool: KAM only
  S.view = view; closeDrawer(); renderPage(); window.scrollTo(0, 0); }

/** Story "Show the detail": detail_view names a module or a page (vs_diy, growth); an unknown
 * target falls back to the overview. */
function goDetail(target) {
  const mod = MODULES.find(m => m.id === target);
  const view = mod ? mod.page : (PAGES.hasOwnProperty(target) ? target : 'overview');
  go(view);
  if (mod) {
    const el = document.querySelector(`[data-mod="${CSS.escape(mod.id)}"]`);
    if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
}

async function copyText(text, done = 'Talking point copied') {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {  // clipboard API unavailable (permissions, insecure context): hidden-textarea fallback
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e2) { ok = false; }
    ta.remove();
    if (!ok) { toast('Could not copy: select the text and copy it by hand', true); return; }
  }
  toast(done);
}

function setMode(mode) {
  S.mode = mode === 'expert' ? 'expert' : 'simple';
  try { localStorage.setItem(MODE_KEY, S.mode); } catch (e) { /* storage blocked: keep for this session */ }
  VR.setMode(S.mode); renderMode(); hideTip(); closeDrawer(); renderPage();
}

// ---------- glossary tooltip ----------
// The term carries aria-describedby="gtip" while the tip is open. The tip stays open while the
// pointer is over it, and keyboard focus scrolling the term into view repositions it instead of hiding it.
let tipFor = null, tipHideTimer = null, tipFocusAt = 0;
function placeTip(el) {
  const tip = $('gtip');
  const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  const left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2));
  const top = r.bottom + 8 + h > window.innerHeight ? r.top - h - 8 : r.bottom + 8;
  tip.style.left = left + 'px'; tip.style.top = Math.max(8, top) + 'px';
}
function showTip(el) {
  const t = VR.glossTerm(el.dataset.term); if (!t) return;
  clearTimeout(tipHideTimer);
  if (tipFor && tipFor !== el) tipFor.removeAttribute('aria-describedby');
  const tip = $('gtip');
  tip.innerHTML = `<b>${esc(t.term)}</b>${esc(t.definition)}`; tip.hidden = false;
  el.setAttribute('aria-describedby', 'gtip'); tipFor = el;
  placeTip(el);
}
function hideTip() {
  clearTimeout(tipHideTimer);
  $('gtip').hidden = true;
  if (tipFor) { tipFor.removeAttribute('aria-describedby'); tipFor = null; }
}
/** Hide shortly after the pointer leaves, unless it moves onto the tip itself. */
function hideTipSoon() { clearTimeout(tipHideTimer); tipHideTimer = setTimeout(hideTip, 150); }
function onScrollTip() {
  if ($('gtip').hidden || !tipFor) return;
  if (Date.now() - tipFocusAt < 300 || document.activeElement === tipFor) placeTip(tipFor);  // focus-driven scroll
  else hideTip();
}

function drill(id) {
  S.site = id; S.view = 'sites'; closeDrawer(); siteReview = null;
  renderPage(); loadSite();
  const el = $('siteDetail'); if (el) el.scrollIntoView({behavior: 'smooth'});
}

function togglePri(k) {
  const ap = [...activePri()];
  S.priorities = ap.includes(k) ? ap.filter(x => x !== k) : [k, ...ap];
  if (!S.priorities.length) S.priorities = null;
  S.prioritySource = S.priorities ? 'chips' : null; S.intentText = '';
  load();
}

/** Everything tied to one account is reset when the account changes (by the selector or a prompt). */
function switchAccount(id, opts) {
  S.account = id; S.site = null; S.sort = null; S.serviceLine = ''; siteReview = null;
  if (!(opts && opts.keepIntent)) { S.priorities = null; S.prioritySource = null; S.intentText = ''; }
  closeDrawer();
}

async function runPrompt(text) {
  text = (text || '').trim(); if (!text) return;
  $('q').value = text;
  let vs;
  try {
    vs = await (await api('/intent', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, account_id: S.account})})).json();
  } catch (e) { toast(`Could not interpret the prompt (${e.message})`, true); return; }
  const it = vs.interpretation_text || '';
  if (!it || it.startsWith('Not recognised')) {
    S.intentText = `“${text}” → ${it || 'Not recognised'}. View unchanged.`;
    renderInterp(); return;
  }
  if (vs.node_id) {
    if (ACCOUNTS.some(a => a.node_id === vs.node_id)) { if (vs.node_id !== S.account) switchAccount(vs.node_id, {keepIntent: true}); }
    else if (R && R.sites.some(s => s.node_id === vs.node_id)) { S.site = vs.node_id; }
  }
  if (vs.priorities && vs.priorities.length) { S.priorities = vs.priorities; S.prioritySource = 'prompt'; }
  if (vs.baseline_id) S.baseline = vs.baseline_id;
  if (vs.sensitivity) S.sens = vs.sensitivity;
  if (vs.view && PAGES.hasOwnProperty(vs.view)) S.view = vs.view;
  S.intentText = it;
  await load();
  if (R) { askPanel(false); $('askBtn').focus(); }  // the prompt is applied: the panel steps aside
}

// ---------- Settings popover and Ask panel ----------
/** Open, close (`on` false) or toggle (`on` undefined) a header panel; opening one closes the other. */
function headerPanel(btnId, panelId, on, focusSel) {
  const p = $(panelId), open = on == null ? p.hidden : on;
  if (open === !p.hidden) return;
  p.hidden = !open; $(btnId).setAttribute('aria-expanded', String(open));
  if (open) {
    const f = p.querySelector(focusSel); if (f) f.focus();
  }
}
const settingsPanel = on => { if (on !== false && $('settingsPanel').hidden) askPanel(false); headerPanel('settingsBtn', 'settingsPanel', on, 'select:not(:disabled),button'); };
const askPanel = on => { if (on !== false && $('askPanel').hidden) settingsPanel(false); headerPanel('askBtn', 'askPanel', on, '#q'); };

const EXPORT_EXT = {pptx: 'pptx', pdf: 'pdf', xlsx: 'xlsx'};
function exportMenu(open) {
  const m = $('exportMenu'), on = open == null ? m.hidden : open;
  m.hidden = !on; $('exportBtn').setAttribute('aria-expanded', String(on));
}

async function exportReview(format) {
  exportMenu(false);
  if (!R) return;
  const body = {account_id: S.account, period: S.period, product: S.product || null, service_line: S.serviceLine || null, baseline_id: S.baseline,
    sensitivity: S.sens, priorities: S.priorities, priority_source_hint: S.priorities ? (S.prioritySource === 'prompt' ? 'prompt' : 'chips') : null,
    audience: S.audience, format};
  const btn = $('exportBtn'); btn.disabled = true;
  try {
    const r = await fetch('/reviews/export', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    if (!r.ok) {
      let detail = '';
      try { const j = await r.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail || ''); } catch (e) { /* not JSON */ }
      // only a format the server says it does not support yet is "coming soon"; anything else shows the server's reason
      if (r.status === 501 || (r.status === 400 && /unsupported format/i.test(detail))) toast('Export available soon');
      else toast(`Export failed (${r.status}${detail ? `: ${detail}` : ''})`, true);
      return;
    }
    const blob = await r.blob();
    const m = /filename="?([^";]+)"?/.exec(r.headers.get('Content-Disposition') || '');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = m ? m[1] : `value-review-${S.account}.${EXPORT_EXT[format] || format}`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    toast('Export downloaded');
  } catch (e) { toast(`Export failed (${e.message})`, true); } finally { btn.disabled = false; }
}

let toastTimer = null;
function toast(msg, err) {
  const t = $('toast'); t.textContent = msg; t.className = 'toast on' + (err ? ' err' : '');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.className = 'toast'; }, 3500);
}
function busy(on) { $('loading').classList.toggle('on', on); $('main').classList.toggle('busy', on); }

document.addEventListener('click', e => {
  if (!e.target.closest('#drawer') && e.target.isConnected && $('drawer').classList.contains('open')) closeDrawer();
  if (!e.target.closest('.export')) exportMenu(false);
  if (!e.target.closest('.pop-wrap') && e.target.isConnected) settingsPanel(false);
  if (!e.target.closest('#askPanel,#askBtn') && e.target.isConnected) askPanel(false);
  const t = e.target.closest('[data-step],[data-cmetric],[data-copy-say],[data-copy],[data-copy-growth],[data-detail],[data-mode-set],[data-fmt],[data-local],[data-explain],[data-evidence],[data-site],[data-go],[data-sort],[data-chip],[data-prompt],[data-close-site],[data-action],[data-intel-snap]');
  if (!t) return;
  const d = t.dataset;
  if (d.step) setStep(+d.step, !!t.closest('.msteps'));
  else if (d.copySay) { const x = t.closest('.say') && t.closest('.say').querySelector('.say-t'); if (x) copyText(x.textContent.trim()); }
  else if (d.action === 'demo') loadDemo(t);
  else if (d.copy != null) { const c = R && R.story[+d.copy]; if (c) copyText(c.what_to_say); }
  else if (d.copyGrowth != null) { if (R && R.growth && R.growth.narrative_line) copyText(R.growth.narrative_line, 'Line copied'); }
  else if (d.local) explainLocal(d.local);
  else if (d.action === 'diy-reset') resetDiy(t.closest('form'));
  else if (d.action === 'growth-clear') saveInputs(diyStored(), t.closest('form'), 'Growth inputs cleared');
  else if (d.intelSnap) runIntel(d.intelSnap, '', true);
  else if (d.detail != null) goDetail(d.detail);
  else if (d.modeSet) setMode(d.modeSet);
  else if (d.cmetric) { S.cmetric = d.cmetric; renderPage(); }
  else if (d.fmt) exportReview(d.fmt);
  else if (d.evidence != null) evidence(+d.evidence);
  else if (d.explain) explain(d.explain, d.node);
  else if (d.site) drill(d.site);
  else if (d.go) go(d.go);
  else if (d.sort) { S.sort = S.sort && S.sort[0] === d.sort ? [d.sort, -S.sort[1]] : [d.sort, 1]; renderPage(); }
  else if (d.chip) togglePri(d.chip);
  else if (d.prompt) runPrompt(d.prompt);
  else if (d.closeSite) { S.site = null; siteReview = null; renderPage(); }
});
document.querySelectorAll('nav a[data-v]').forEach(a => { a.onclick = e => { e.preventDefault(); go(a.dataset.v); }; });
// ---------- theme (light / dark) and sidebar collapse ----------
const ICON_SUN = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/></svg>';
const ICON_MOON = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"/></svg>';
function applyTheme(t, persist) {
  document.documentElement.dataset.theme = t;
  const b = $('themeBtn'); if (b) { b.setAttribute('aria-checked', String(t === 'dark')); $('themeIcon').innerHTML = t === 'dark' ? ICON_MOON : ICON_SUN; }
  if (persist) { try { localStorage.setItem('lindstrom-theme', t); } catch (e) { /* session only */ } }
  if (window.VR && VR.refreshColors) VR.refreshColors();
  if (R) renderPage();
}
$('themeBtn').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark', true);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ev => {
  let saved = null; try { saved = localStorage.getItem('lindstrom-theme'); } catch (e) { /* none */ }
  if (!saved) applyTheme(ev.matches ? 'dark' : 'light', false);
});
// below 840px the navigation is a modal drawer opened from the header (Material breakpoints)
const navDrawer = open => {
  document.body.classList.toggle('nav-open', open);
  $('menuBtn').setAttribute('aria-expanded', String(open)); $('scrim').hidden = !open;
};
$('menuBtn').onclick = () => navDrawer(!document.body.classList.contains('nav-open'));
$('scrim').onclick = () => navDrawer(false);
document.querySelectorAll('nav a[data-v]').forEach(l => l.addEventListener('click', () => navDrawer(false)));
// ---------- resizable sidebar: drag the edge, arrows nudge, double-click resets ----------
{
  const MIN = 220, MAX = 360, DEF = 230, h = $('navResize');
  const clamp = w => Math.min(MAX, Math.max(MIN, w));
  const apply = (w, save) => {
    width = w; document.documentElement.style.setProperty('--nav-w', w + 'px'); h.setAttribute('aria-valuenow', String(w));
    if (save) { try { localStorage.setItem('vr-nav-width', String(w)); } catch (e) { /* session only */ } }
  };
  let width = DEF, drag = null;
  try { const w = +localStorage.getItem('vr-nav-width'); if (w >= MIN && w <= MAX) width = w; } catch (e) { /* default */ }
  const cur = () => width;
  h.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    e.preventDefault(); drag = {x: e.clientX, w: cur()}; h.setPointerCapture(e.pointerId);
    document.body.classList.add('nav-resizing');
  });
  h.addEventListener('pointermove', e => { if (drag) apply(clamp(drag.w + e.clientX - drag.x), false); });
  const end = e => {
    if (!drag) return;
    drag = null; document.body.classList.remove('nav-resizing');
    if (h.hasPointerCapture(e.pointerId)) h.releasePointerCapture(e.pointerId);
    apply(clamp(cur()), true);
  };
  h.addEventListener('pointerup', end); h.addEventListener('pointercancel', end);
  h.addEventListener('dblclick', () => { apply(DEF, false); try { localStorage.removeItem('vr-nav-width'); } catch (e) { /* none */ } });
  h.addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    apply(e.key === 'Home' ? MIN : e.key === 'End' ? MAX : clamp(cur() + (e.key === 'ArrowRight' ? 10 : -10)), true);
  });
  h.setAttribute('aria-valuenow', String(width));
}
// ---------- customer picker: sidebar when it is wide, filter row when it is a rail / collapsed ----------
function placeCustomer() {
  const rail = innerWidth >= 840 && (innerWidth < 1200 || document.body.classList.contains('nav-collapsed'));
  const slot = $(rail ? 'filterRow' : 'custSlot'), c = $('custCtl');
  if (c.parentNode !== slot) { if (rail) slot.prepend(c); else slot.appendChild(c); }
  // the "synthetic data" tag sits above Dark mode when the sidebar is fully open; otherwise (rail, collapsed,
  // phone drawer) it stays in the action bar so it is always visible
  const full = innerWidth >= 1200 && !document.body.classList.contains('nav-collapsed');
  const tag = $('disclaimerStrip'), dest = full ? document.querySelector('.nav-foot') : document.querySelector('.ab-left');
  if (tag.parentNode !== dest) dest.prepend(tag);
}
addEventListener('resize', placeCustomer);
$('navCollapse').onclick = () => {
  const c = document.body.classList.toggle('nav-collapsed');
  $('navCollapse').setAttribute('aria-label', c ? 'Expand sidebar' : 'Collapse sidebar'); $('navCollapse').title = c ? 'Expand sidebar' : 'Collapse sidebar';
  try { localStorage.setItem('vr-nav', c ? 'collapsed' : 'open'); } catch (e) { /* session only */ }
  placeCustomer();
};
if (document.body.classList.contains('nav-collapsed')) { $('navCollapse').setAttribute('aria-label', 'Expand sidebar'); $('navCollapse').title = 'Expand sidebar'; }
placeCustomer();
applyTheme(document.documentElement.dataset.theme || 'light', false);
if (window.VRLayout) window.VRLayout.init({rerender: () => renderPage(), tagsOf: id => ((MODULES.find(m => m.id === id) || {}).priority_tags || [])});
$('drawerX').onclick = closeDrawer;
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    const menuOpen = !$('exportMenu').hidden, setOpen = !$('settingsPanel').hidden, askOpen = !$('askPanel').hidden;
    closeDrawer(); exportMenu(false); hideTip(); settingsPanel(false); askPanel(false);
    if (menuOpen) $('exportBtn').focus();
    else if (setOpen) $('settingsBtn').focus();
    else if (askOpen) $('askBtn').focus();
    return;
  }
  // clickable figures and meeting tiles (role="button") open with Enter / Space like a button
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('.fig[role="button"],.mtile[role="button"]')) { e.preventDefault(); e.target.click(); return; }
  if (stepKey(e)) e.preventDefault();
});
document.addEventListener('submit', onSubmit);
window.addEventListener('hashchange', () => {  // a typed #meeting/N; renderPage clamps a hidden step
  const n = hashStep();
  if (n && R && (n !== S.step || S.view !== 'meeting')) { S.view = 'meeting'; S.step = n; closeDrawer(); renderPage(); focusStep(S.step); }
});
document.addEventListener('input', onInput);
const glAt = e => (e.target && e.target.closest ? e.target.closest('.gl[data-term]') : null);
document.addEventListener('mouseover', e => { const g = glAt(e); if (g) showTip(g); });
document.addEventListener('focusin', e => { const g = glAt(e); if (g) { tipFocusAt = Date.now(); showTip(g); } });
document.addEventListener('mouseout', e => { if (glAt(e)) hideTipSoon(); });
document.addEventListener('focusout', e => { if (glAt(e)) hideTip(); });
$('gtip').addEventListener('mouseenter', () => clearTimeout(tipHideTimer));
$('gtip').addEventListener('mouseleave', hideTipSoon);
window.addEventListener('scroll', onScrollTip, {passive: true});
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') runPrompt($('q').value); });
$('qBtn').onclick = () => runPrompt($('q').value);
$('exportBtn').onclick = () => { settingsPanel(false); askPanel(false); exportMenu(); };
$('settingsBtn').onclick = () => { exportMenu(false); settingsPanel(); };
$('askBtn').onclick = () => { exportMenu(false); askPanel(); };
document.querySelectorAll('#mode button').forEach(b => { b.onclick = () => { if (S.mode !== b.dataset.mode) setMode(b.dataset.mode); }; });
$('cust').onchange = e => { switchAccount(e.target.value); load(); };
$('period').onchange = e => { S.period = e.target.value; load(); };
$('product').onchange = e => { S.product = e.target.value; load(); };
$('sline').onchange = e => { S.serviceLine = e.target.value; load(); };
$('base').onchange = e => { S.baseline = e.target.value; load(); };
$('sens').onchange = e => { S.sens = e.target.value; load(); };
document.querySelectorAll('#aud button').forEach(b => { b.onclick = () => {
  if (S.audience === b.dataset.aud) return;
  S.audience = b.dataset.aud; closeDrawer();
  if (S.audience === 'customer' && S.view === 'intel') S.view = 'meeting';  // no Customer background in the customer view
  load();
}; });

async function init() {
  VR.setMode(S.mode); renderMode();
  busy(true);
  try {
    const glossary = getJSON('/config/glossary').catch(e => { console.warn('glossary unavailable', e); return []; });
    const [accounts, assumptions, modules, internal, terms] = await Promise.all([getJSON('/accounts'), getJSON('/config/assumptions'),
      getJSON('/config/modules'), getJSON('/config/internal-metrics'), glossary]);
    ACCOUNTS = accounts; MODULES = modules; INTERNAL = internal; ASSUMPTIONS = assumptions; EXT.spec = assumptions.dto_inputs || {};
    VR.setGlossary(terms);
    $('cust').innerHTML = accounts.map(a => `<option value="${esc(a.node_id)}">${esc(a.name)} (${a.site_count} sites)</option>`).join('');
    const bl = Object.entries(assumptions.baselines || {});
    $('base').innerHTML = bl.map(([id, b]) => `<option value="${esc(id)}">${esc(b.name)}${b.default ? ' (default)' : ''}</option>`).join('');
    const def = bl.find(([, b]) => b.default); if (def) S.baseline = def[0];
    S.account = accounts.length ? accounts[0].node_id : null;
  } catch (e) { toast(`Could not reach the API (${e.message})`, true); busy(false); return; }
  if (S.account) await load(); else busy(false);
}
init();
})();
