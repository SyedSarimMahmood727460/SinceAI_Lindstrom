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
  story: null,  // title built from the review
  overview: null,  // title built from the review
  sites: ['Sites & drill-down', 'Customer-level consolidation of the delivery sites. Sort any column, or click a row to drill down.'],
  footprint: ['Footprint & handprint', "Lindström's allocated service footprint compared with the selected baseline for the same washed kilograms. Ranges show low–high sensitivity."],
  circularity: ['Circularity & repairs', 'Repairs extend garment life. Textile waste is routed to recycling, reuse or energy recovery.'],
  steering: ['Steering-committee pack', 'Discussion points generated from the observations. A KAM edits them before the meeting.'],
  methodology: ['Methodology & assumptions', 'Boundaries, baseline, provenance and limitations. Always one click away and included in the export.'],
  readiness: ['Data readiness', 'Data-consistency warnings, quarantined rows, and how each prototype field maps to a future approved source.'],
};
// Components that show the account's figures; on an empty filter they say "No data for this filter".
const STATIC_COMPONENTS = new Set(['methodology', 'assumption_table', 'data_quality', 'readiness_table', 'discussion_points']);
const SOURCE_LABEL = {prompt: 'from your prompt', chips: 'your selection', customer: "customer's stated priorities + industry default",
  industry: 'industry default'};

const MODE_KEY = 'vr.mode';
function storedMode() { try { return localStorage.getItem(MODE_KEY) === 'expert' ? 'expert' : 'simple'; } catch (e) { return 'simple'; } }
const S = {account: null, period: '2025', product: '', serviceLine: '', baseline: 'B_LOCAL', sens: 'base', priorities: null,
  prioritySource: null, audience: 'kam', view: 'story', site: null, sort: null, intentText: '', mode: storedMode()};
let R = null, siteReview = null, MODULES = [], ACCOUNTS = [], INTERNAL = [];
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
    const err = new Error(`${r.status}: ${detail}`); err.status = r.status; throw err;
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

async function load() {
  const seq = ++reqSeq;
  busy(true);
  try {
    const r = await getJSON(reviewQuery());
    if (seq !== reqSeq) return;
    R = r;
    (R.meta.products || []).forEach(p => { productNames[p.id] = p.name; });
    if (S.site && !R.sites.some(s => s.node_id === S.site)) S.site = null;
    render();
    if (S.site) loadSite();
  } catch (e) {
    if (seq === reqSeq) toast(`Could not load the review (${e.message})`, true);
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
  $('disclaimer').textContent = R.meta.disclaimer;
  $('cust').value = S.account; $('period').value = S.period; $('base').value = S.baseline; $('sens').value = S.sens;
  document.querySelectorAll('#aud button').forEach(b => b.classList.toggle('on', b.dataset.aud === S.audience));
  renderProducts();
  renderServiceLines();
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
  document.querySelectorAll('#mode button').forEach(b => b.classList.toggle('on', b.dataset.mode === S.mode));
  document.body.classList.toggle('simple', S.mode === 'simple');
  document.body.classList.toggle('expert', S.mode === 'expert');
}

function renderChips() {
  const ap = activePri();
  $('pchips').innerHTML = Object.entries(PRI).map(([k, l]) => {
    const i = ap.indexOf(k);
    return `<span class="chip ${i >= 0 ? 'on' : ''}" data-chip="${k}">${i >= 0 ? `<sup>${i + 1}</sup> ` : ''}${l}</span>`;
  }).join('') + SUGGESTED_PROMPTS.map(p => `<span class="chip sugg" data-prompt="${esc(p)}">${esc(p)}</span>`).join('');
}

function renderInterp() {
  const ap = activePri(), src = R.context.priority_source;
  const srcLabel = src === 'industry' || src === 'customer' ? `${SOURCE_LABEL[src]} for ${R.meta.node.industry}` : SOURCE_LABEL[src];
  $('interp').innerHTML = (S.intentText ? `${esc(S.intentText)} · ` : '') +
    `Emphasis: <b>${esc(ap.map(p => PRI[p] || p).join(' → ') || 'balanced')}</b> (${esc(srcLabel)}) · ` +
    `Baseline: <b>${esc(R.meta.baseline.name)}</b> · Sensitivity: <b>${esc(R.meta.sensitivity)}</b>` +
    (S.audience === 'customer' ? ' · <b>Customer view</b> (internal figures hidden)' : '') +
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
  if (S.view === 'story') {
    return `<h1>${esc(n.name)} — Customer story ${esc(pl ? pl.textContent : R.meta.period)}</h1>
      <p class="lead">Plain-language headlines to walk the customer through, each with a talking point and a link to the detail${filterText()}.</p>`;
  }
  if (S.view === 'overview') {
    const sites = kpiOf('sites');
    return `<h1>${esc(n.name)} — Annual value review ${esc(pl ? pl.textContent : R.meta.period)}</h1>
      <p class="lead">${esc(n.industry)} · ${esc(n.segment)} · ${esc(sites ? fmtM(sites) : '–')} delivery sites · ${esc(n.countries.join(', '))}` +
      `${filterText()}</p>`;
  }
  const [t, l] = PAGES[S.view];
  return `<h1>${esc(t)}</h1><p class="lead">${VR.gloss(l)}</p>`;
}

function renderPage() {
  if (!R) return;
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('on', a.dataset.v === S.view));
  $('pageHead').innerHTML = pageHead();
  Object.keys(charts).forEach(id => { charts[id].destroy(); delete charts[id]; });
  const pri = activePri(), empty = emptyFilter();
  const ctx = {R, S, pri, kpi: kpiOf, siteReview, hidden: hiddenModules()};
  const mods = MODULES.filter(m => m.page === S.view)
    .map((m, i) => ({m, i, w: weight(m.priority_tags, pri)}))
    .sort((a, b) => pin(b.m) - pin(a.m) || b.w - a.w || a.i - b.i).map(x => x.m);
  const out = [], pending = [];
  for (const mod of mods) {
    if (empty && !STATIC_COMPONENTS.has(mod.component)) {
      out.push(`<div class="mod" data-mod="${esc(mod.id)}"><div class="card empty">No data for this filter</div></div>`);
      continue;
    }
    if (!moduleStatus(mod).show) continue;
    let res;
    try { res = Components[mod.component]({...ctx, mod}); } catch (e) {
      console.warn('module failed', mod.id, e);
      res = {html: `<div class="card empty">Could not render ${esc(mod.id)}</div>`};
    }
    if (!res) continue;
    out.push(`<div class="mod ${res.cls || ''}" data-mod="${esc(mod.id)}">${res.html}</div>`);
    (res.charts || []).forEach(c => pending.push(c));
  }
  $('page').innerHTML = out.join('') || '<div class="mod"><div class="card empty">No modules for this page.</div></div>';
  if (window.Chart) pending.forEach(c => mkChart(c));
  else if (pending.length) toast('Charts unavailable (Chart.js did not load)', true);
}

function mkChart({id, type, data, options}) {
  const el = $(id); if (!el) return;
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
  const expertHint = '<p class="small">Switch to <span class="link" data-mode-set="expert">Expert detail</span> for the formula and data lineage.</p>';
  const assum = (ex.assumptions || []).length ? `<table><tr><th class="l">ID</th><th class="l">Assumption</th><th class="l">Value / rule</th><th class="l">Confidence</th></tr>${ex.assumptions.map(a =>
    `<tr><td class="l">${esc(a.id)}</td><td class="l">${esc(a.assumption)}</td><td class="l">${esc(a.value_or_rule)}</td><td class="l">${esc(a.confidence)}</td></tr>`).join('')}</table>
    <p class="small"><span class="link" data-go="methodology">Open the full assumption register</span></p>` : '<p class="small">No assumptions: a direct formula over source rows.</p>';
  const lin = res.lineage || {};
  const how = isSimple() ? '' : `<h3>How it's calculated</h3><div class="formula">${esc(d.formula_text || cur.formula_text)}</div>
    <p class="small">Aggregation: ${esc(d.aggregation)} · unit: ${esc(d.unit)} · inputs: ${esc((d.inputs || []).join(', '))}</p>`;
  const lineage = isSimple() ? expertHint : `<h3>Lineage</h3><p class="small">Facts: ${esc((lin.facts || []).join(', '))} · ${esc(VR.num(lin.rows))} rows · load ${esc((lin.load_ids || []).join(', '))}${S.product ? '<br>Lineage is shown for all products.' : ''}</p>`;
  openDrawer(`<h2>${esc(cur.label)}</h2><p class="small">${esc(nodeName(node))} · ${esc(S.period)}${S.product ? ' · product ' + esc(S.product) : ''}${S.serviceLine ? ' · service line ' + esc(S.serviceLine) : ''}</p>
    <p>${badges(cur, true)}</p>
    <p style="font-size:26px;font-weight:700;color:var(--navy);margin:6px 0">${esc(fmtM(cur))}</p><p class="range">${esc(rangeText(cur))}</p>
    ${cur.dq_warning ? `<div class="alert small">⚠ An input to this figure carries a ${VR.gloss('data-consistency warning')}. <span class="link" data-go="readiness">See Data readiness</span>.</div>` : ''}
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
    ${siteNode ? `<p class="small"><span class="link" data-site="${esc(siteNode)}">Open ${esc(nodeName(siteNode))} drill-down</span></p>` : ''}
    ${isSimple() ? '<p class="small">Switch to <span class="link" data-mode-set="expert">Expert detail</span> for the rule, z-score and formulas.</p>' : `<h3>Rule ${esc(o.rule_id)}</h3><div class="formula">${o.z != null ? `Peer group: the account's sites. z = ${VR.num(o.z, 2)} (outlier when |z| ≥ 1.5).\n` : ''}Priority match (${esc(o.tags.join(', '))}) sets the display order (score ${VR.num(o.score, 0)}).
${esc(formulas)}</div>`}`);
}

// ---------- interaction ----------
function go(view) { if (!PAGES.hasOwnProperty(view)) return; S.view = view; closeDrawer(); renderPage(); window.scrollTo(0, 0); }

/** Story "Show the detail": detail_view names a module (or a page). A target with no page yet
 * (vs_diy and growth get their own pages in a later task) falls back to the overview. */
function goDetail(target) {
  const mod = MODULES.find(m => m.id === target);
  const view = mod ? mod.page : (PAGES.hasOwnProperty(target) ? target : 'overview');
  go(view);
  if (mod) {
    const el = document.querySelector(`[data-mod="${CSS.escape(mod.id)}"]`);
    if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
}

async function copyText(text) {
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
  toast('Talking point copied');
}

function setMode(mode) {
  S.mode = mode === 'expert' ? 'expert' : 'simple';
  try { localStorage.setItem(MODE_KEY, S.mode); } catch (e) { /* storage blocked: keep for this session */ }
  VR.setMode(S.mode); renderMode(); hideTip(); closeDrawer(); renderPage();
}

// ---------- glossary tooltip ----------
function showTip(el) {
  const t = VR.glossTerm(el.dataset.term); if (!t) return;
  const tip = $('gtip');
  tip.innerHTML = `<b>${esc(t.term)}</b>${esc(t.definition)}`; tip.hidden = false;
  const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  const left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2));
  const top = r.bottom + 8 + h > window.innerHeight ? r.top - h - 8 : r.bottom + 8;
  tip.style.left = left + 'px'; tip.style.top = Math.max(8, top) + 'px';
}
function hideTip() { $('gtip').hidden = true; }

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
    if (ACCOUNTS.some(a => a.node_id === vs.node_id)) { if (vs.node_id !== S.account) { S.account = vs.node_id; S.site = null; } }
    else if (R && R.sites.some(s => s.node_id === vs.node_id)) { S.site = vs.node_id; }
  }
  if (vs.priorities && vs.priorities.length) { S.priorities = vs.priorities; S.prioritySource = 'prompt'; }
  if (vs.baseline_id) S.baseline = vs.baseline_id;
  if (vs.sensitivity) S.sens = vs.sensitivity;
  if (vs.view && PAGES.hasOwnProperty(vs.view)) S.view = vs.view;
  S.intentText = it;
  await load();
}

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
    if (r.status === 400 || r.status === 501) { toast('Export available soon'); return; }  // format not built yet
    if (!r.ok) { toast(`Export failed (${r.status})`, true); return; }
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
  if (!e.target.closest('.export')) exportMenu(false);
  const t = e.target.closest('[data-copy],[data-detail],[data-mode-set],[data-fmt],[data-explain],[data-evidence],[data-site],[data-go],[data-sort],[data-chip],[data-prompt],[data-close-site]');
  if (!t) return;
  const d = t.dataset;
  if (d.copy != null) { const c = R && R.story[+d.copy]; if (c) copyText(c.what_to_say); }
  else if (d.detail != null) goDetail(d.detail);
  else if (d.modeSet) setMode(d.modeSet);
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
document.querySelectorAll('nav a').forEach(a => { a.onclick = () => go(a.dataset.v); });
$('drawerX').onclick = closeDrawer;
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeDrawer(); exportMenu(false); hideTip(); } });
const glAt = e => (e.target && e.target.closest ? e.target.closest('.gl[data-term]') : null);
['mouseover', 'focusin'].forEach(ev => document.addEventListener(ev, e => { const g = glAt(e); if (g) showTip(g); }));
['mouseout', 'focusout'].forEach(ev => document.addEventListener(ev, e => { if (glAt(e)) hideTip(); }));
window.addEventListener('scroll', hideTip, {passive: true});
$('q').addEventListener('keydown', e => { if (e.key === 'Enter') runPrompt($('q').value); });
$('qBtn').onclick = () => runPrompt($('q').value);
$('exportBtn').onclick = () => exportMenu();
document.querySelectorAll('#mode button').forEach(b => { b.onclick = () => { if (S.mode !== b.dataset.mode) setMode(b.dataset.mode); }; });
$('cust').onchange = e => { S.account = e.target.value; S.priorities = null; S.prioritySource = null; S.intentText = ''; S.site = null; S.sort = null; S.serviceLine = ''; closeDrawer(); load(); };
$('period').onchange = e => { S.period = e.target.value; load(); };
$('product').onchange = e => { S.product = e.target.value; load(); };
$('sline').onchange = e => { S.serviceLine = e.target.value; load(); };
$('base').onchange = e => { S.baseline = e.target.value; load(); };
$('sens').onchange = e => { S.sens = e.target.value; load(); };
document.querySelectorAll('#aud button').forEach(b => { b.onclick = () => { if (S.audience !== b.dataset.aud) { S.audience = b.dataset.aud; closeDrawer(); load(); } }; });

async function init() {
  VR.setMode(S.mode); renderMode();
  busy(true);
  try {
    const glossary = getJSON('/config/glossary').catch(e => { console.warn('glossary unavailable', e); return []; });
    const [accounts, assumptions, modules, internal, terms] = await Promise.all([getJSON('/accounts'), getJSON('/config/assumptions'),
      getJSON('/config/modules'), getJSON('/config/internal-metrics'), glossary]);
    ACCOUNTS = accounts; MODULES = modules; INTERNAL = internal;
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
