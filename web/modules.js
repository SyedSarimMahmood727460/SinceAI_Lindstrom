/* Component renderers for the module registry (config/modules.json).
 * Every number shown here comes from the ReviewModel returned by the API. The only arithmetic is
 * display formatting (unit scaling, percent) and the client-side z used for outlier dots. */
(() => {
'use strict';

const PRI = {water: 'Water', emissions: 'Emissions', cost: 'Cost', circularity: 'Circularity', service: 'Service'};
const COLORS = {navy: '#1b2a4a', red: '#d71920', blue: '#1565c0', grey: '#8e9bb5', light: '#c9cfdb',
  orange: '#e67e22', green: '#2e7d32', teal: '#00897b', slate: '#7f8c8d'};

// ---------- formatting helpers (display only) ----------
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const num = (v, d = 0) => (v == null || !isFinite(v)) ? '–'
  : Number(v).toLocaleString('en-GB', {maximumFractionDigits: d, minimumFractionDigits: d});

/** [number text, unit text] for a metric value in its registry unit. */
function scale(unit, v) {
  if (v == null || !isFinite(v)) return ['–', ''];
  switch (unit) {
    case 'l': return [num(v / 1000, 0), 'm³'];
    case 'kg': { const t = v / 1000; return [num(t, Math.abs(t) < 100 ? 1 : 0), 't']; }
    case 'kgCO2e': { const t = v / 1000; return [num(t, Math.abs(t) < 100 ? 1 : 0), 't CO₂e']; }
    case 'kWh': return [num(v / 1000, 0), 'MWh'];
    case 'ratio': return [num(v * 100, 1), '%'];
    case '%': return [num(v, 1), '%'];
    case 'EUR': return ['€' + num(v, 0), ''];
    case 'h': return [num(v, 1), 'h'];
    case 'kg/wearer': return [num(v, 1), 'kg / wearer'];
    case 'per 100 wearers': return [num(v, 1), 'per 100 wearers'];
    case 'count': return [num(v, 0), ''];
    default: return [num(v, 0), unit || ''];
  }
}
const joinU = ([n, u]) => (u === '%' ? n + '%' : (u ? `${n} ${u}` : n));
const fmtV = (unit, v) => joinU(scale(unit, v));
const fmtM = m => (m ? fmtV(m.unit, m.value) : '–');
/** Table cell: number only (the column header carries the unit), percent sign kept. */
const cellFmt = m => { const [n, u] = scale(m.unit, m.value); return u === '%' ? n + '%' : n; };
function fmtRange(m) {
  if (!m || !m.range || m.range.low == null || m.range.high == null) return '';
  const lo = Math.min(m.range.low, m.range.high), hi = Math.max(m.range.low, m.range.high);
  const [a] = scale(m.unit, lo), [b, u] = scale(m.unit, hi);
  return `range ${a}–${u === '%' ? b + '%' : b + (u ? ' ' + u : '')}`;
}
/** Simple mode: 'about X (between A and B)'; 'about X' when there is no spread. */
function fmtAbout(m) {
  if (!m || m.value == null) return '–';
  const x = fmtM(m);
  if (!m.range || m.range.low == null || m.range.high == null) return `about ${x}`;
  const lo = Math.min(m.range.low, m.range.high), hi = Math.max(m.range.low, m.range.high);
  const [a] = scale(m.unit, lo), [b, u] = scale(m.unit, hi);
  if (a === b) return `about ${x}`;
  return `about ${x} (between ${a} and ${u === '%' ? b + '%' : b + (u ? ' ' + u : '')})`;
}
const tagLabels = tags => (tags || []).map(t => PRI[t] || t).join(', ');

// ---------- Simple / Expert mode (display only) ----------
// Simple (default) hides z-scores, method-status / provenance badges (one "estimate" pill instead),
// lineage and formula text. Ranges read "about X (between A and B)" in both modes (design §8b G9);
// Expert adds badges, formulas and lineage.
let MODE = 'simple';
const setMode = m => { MODE = m === 'expert' ? 'expert' : 'simple'; };
const isSimple = () => MODE === 'simple';
/** Range line for a metric ('' when the metric has no range): 'about X (between A and B)'. */
const rangeText = m => (!m || !m.range ? '' : fmtAbout(m));

// ---------- glossary (config/glossary.yaml via /config/glossary) ----------
// Each term matches its own name plus the word forms used in the dashboard text.
const GLOSS_FORMS = {baseline: 'baselines?', allocation: 'allocat(?:ion|ed)', scope3: 'Scope 3', utilisation: 'utilisation',
  range_sensitivity: 'sensitivity', estimate: 'estimates?', repair_handprint: 'handprint',
  data_consistency_warning: 'data-consistency warnings?'};
const reEsc = s => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
let GLOSS = {}, GLOSS_IDS = [], GLOSS_RE = null;
function setGlossary(terms) {
  GLOSS = {}; GLOSS_IDS = [];
  (terms || []).forEach(t => { if (t && t.id && t.definition) { GLOSS[t.id] = t; GLOSS_IDS.push(t.id); } });
  const alt = GLOSS_IDS.map(id => `(${GLOSS_FORMS[id] || reEsc(GLOSS[id].term)})`);
  GLOSS_RE = alt.length ? new RegExp(`\\b(?:${alt.join('|')})\\b`, 'gi') : null;
}
const glossTerm = id => GLOSS[id] || null;
/** Escaped text with the first occurrence of each glossary term marked (dotted underline + tooltip). */
function gloss(text) {
  const h = esc(text);
  if (!GLOSS_RE) return h;
  const used = new Set();
  return h.replace(GLOSS_RE, (w, ...groups) => {
    const id = GLOSS_IDS[groups.slice(0, GLOSS_IDS.length).findIndex(g => g !== undefined)];
    if (!id || used.has(id)) return w;
    used.add(id);
    return `<span class="gl" data-term="${esc(id)}" tabindex="0">${w}</span>`;
  });
}

/** Method-status badge, SYN marker, and a warning sign for dq_warning.
 * Simple mode: a single "estimate" pill for ESTIMATED values (plus the warning sign). */
function badges(m, withConf) {
  if (!m) return '';
  if (isSimple()) {
    let s = m.method_status === 'ESTIMATED' ? '<span class="pill gl" data-term="estimate" tabindex="0">estimate</span>' : '';
    if (m.dq_warning) s += '<span class="warn" title="An input carries a data-consistency warning (see Data readiness)">⚠</span>';
    return s;
  }
  let h = `<span class="badge b-${esc(m.method_status)}">${esc(m.method_status)}</span>`;
  if (m.provenance === 'SYNTHETIC') h += '<span class="badge b-SYN" title="Synthetic source data">SYN</span>';
  if (m.dq_warning) h += '<span class="warn" title="An input carries a data-consistency warning (see Data readiness)">⚠</span>';
  if (withConf && m.confidence) h += `<span class="conf">${esc(m.confidence)} conf.</span>`;
  return h;
}

/** Display-order weight: 10 - rank of each tag in the active list (spec §8.3). Used only for layout order. */
function weight(tags, pri) {
  return (tags || []).reduce((a, t) => a + (pri.includes(t) ? 10 - (pri.indexOf(t) + 1) : 0), 0);
}

function kpiTile(m, node, pri) {
  const focus = pri && (m.priority_tags || []).some(t => pri.includes(t));
  const sub = m.method_status === 'ESTIMATED' && m.range ? rangeText(m)
    : (m.confidence && !isSimple() ? `${m.confidence} confidence` : '');
  const tip = isSimple() ? 'Click to see what this figure means' : (m.formula_text || '');
  return `<div class="card kpi ${focus ? 'focus' : ''}" data-explain="${esc(m.metric_id)}" data-node="${esc(node)}" title="${esc(tip)}">
    <div class="badges">${badges(m)}</div><div class="l">${gloss(m.label)}</div>
    <div class="v">${esc(fmtM(m))}</div><div class="s">${esc(sub)}</div></div>`;
}

const chart = (id, cls = '') => `<div class="chart ${cls}"><canvas id="${id}"></canvas></div>`;

// ---------- z for outlier dots (display only) ----------
function zScores(sites, key) {
  const vals = sites.map(s => s.metrics[key] && s.metrics[key].value).filter(v => v != null && isFinite(v));
  if (vals.length < 3) return () => null;
  const mu = vals.reduce((a, b) => a + b, 0) / vals.length;
  const sd = Math.sqrt(vals.reduce((a, b) => a + (b - mu) ** 2, 0) / vals.length);
  return s => { const v = s.metrics[key] && s.metrics[key].value; return (v == null || !sd) ? null : (v - mu) / sd; };
}

// ---------- components ----------
// Each renderer takes (ctx) and returns {html, charts?: [{id,type,data,options}], cls?} or null (render nothing).
// ctx: {R, S, mod, pri, kpi(id), site(id), siteReview, accountName}
const RANK_BY = {
  water: {k: 'washed_kg_per_wearer', l: 'washed kg per wearer (highest first)', dir: -1},
  emissions: {k: 'co2_saving_kg', l: 'CO₂e avoided vs baseline (highest first)', dir: -1},
  cost: {k: 'utilisation', l: 'garment utilisation (lowest first)', dir: 1},
  circularity: {k: 'repairs_per_100w', l: 'repairs per 100 wearers (highest first)', dir: -1},
  service: {k: 'service_requests_per_100w', l: 'service requests per 100 wearers (highest first)', dir: -1},
};
const HEADLINE_ROWS = new Set(['overview_kpis']);
const MOD_TITLES = {idle_stock: 'Idle stock · internal (KAM view only)'};

/** A story value reference: an account KPI, or one of the do-it-yourself (DTO) results. */
function storyRef(R, id) {
  const k = R.kpis.find(x => x.metric_id === id);
  if (k) return k;
  const d = R.dto;
  if (!d) return null;
  const map = {dto_diy_total: d.diy_total, dto_contract_price: d.contract_price, dto_net: d.net,
    dto_staff_hours_freed: d.convenience && d.convenience.staff_hours_freed};
  return map[id] || null;
}

// ---------- helpers for the DIY, growth, intelligence and fit pages ----------
const INPUT_CONTRACT = 'contract_price_eur_per_year';
/** Results without an /explain endpoint (do-it-yourself, growth): kept here for the local drawer. */
const LOCAL = {};
const resetLocal = () => { Object.keys(LOCAL).forEach(k => { delete LOCAL[k]; }); };
/** Only http(s) URLs become links; anything else is shown as text. */
function safeUrl(u) {
  try { const x = new URL(String(u)); return x.protocol === 'http:' || x.protocol === 'https:' ? x.href : null; } catch (e) { return null; }
}
const hostOf = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (e) { return ''; } };
function extLink(url, text) {
  const u = safeUrl(url);
  const t = text || (u ? hostOf(u) : url);
  return u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t);
}
const unitText = u => String(u || '').replace(/EUR/g, '€').replace(/\bm3\b/g, 'm³');
/** One figure: label + badges, then 'about X (between A and B)'. Click opens its explanation. */
function fig(label, m, node, cls = '') {
  if (!m) return `<div class="fig ${cls}"><div class="fig-l">${gloss(label)}</div><div class="fig-v">–</div></div>`;
  let attr;
  if (m.metric_id && /^(dto|growth)_/.test(m.metric_id)) { LOCAL[m.metric_id] = m; attr = `data-local="${esc(m.metric_id)}"`; }
  else attr = `data-explain="${esc(m.metric_id)}" data-node="${esc(node)}"`;
  const spread = m.range && m.range.low != null && m.range.high != null && m.range.low !== m.range.high;
  const v = m.value == null ? 'No data' : (spread ? fmtAbout(m) : fmtM(m));
  return `<div class="fig ${cls}" role="button" tabindex="0" ${attr} title="${esc(isSimple() ? 'Click to see what this figure means' : (m.formula_text || ''))}">
    <div class="fig-l">${gloss(label)} ${badges(m)}</div><div class="fig-v">${esc(v)}</div></div>`;
}
const srcBadge = r => (r.source === 'kam'
  ? `<span class="src kam">entered by account manager${r.entered_at ? `, ${esc(r.entered_at)}` : ''}</span>`
  : `<span class="src">default${r.assumption_id ? ` (${esc(r.assumption_id)})` : ''}</span>`);
const rawNum = v => (v == null ? '' : String(v));
const FIT_KIND = {PUBLIC_REFERENCE: ['PUBLIC', 'b-PUBLIC'], DATA_PACK: ['DATA PACK', 'b-DATAPACK'], BRIEF: ['BRIEF', 'b-BRIEF']};

const Components = {
  // Customer story (G9): plain-language headline cards from review.story; the statements are
  // filled by the engine (insights/story.py), the UI adds no numbers.
  story_cards(ctx) {
    const cards = ctx.R.story || [];
    if (!cards.length) return {html: '<div class="card empty">No story cards for this view.</div>'};
    const html = cards.map((c, i) => {
      const refs = (c.value_refs || []).map(id => storyRef(ctx.R, id)).filter(Boolean);
      let based = '';
      if (isSimple()) {
        if (refs.some(m => m.method_status === 'ESTIMATED')) based = badges({method_status: 'ESTIMATED'});
      } else if (refs.length) {
        based = 'Based on: ' + refs.map(m => `<span class="ref">${esc(m.label || m.metric_id)} ${badges(m)}</span>`).join(' ');
      }
      return `<div class="card story-card" data-card="${esc(c.id)}">
        <div class="story-n">${i + 1}</div><h2>${esc(c.title)}</h2>
        <div class="story-statement">${gloss(c.statement)}</div>
        ${c.relatable ? `<div class="story-rel" title="A rough equivalent to help the figure land, not a measured result">${esc(c.relatable)}</div>` : ''}
        <div class="say"><div class="say-h">What to say <button class="btn ghost sm" data-copy="${i}" title="Copy the talking point">Copy</button></div>
          <div class="say-t">${gloss(c.what_to_say)}</div></div>
        <div class="story-foot"><span class="story-based">${based}</span>
          <button type="button" class="link" data-detail="${esc(c.detail_view || '')}">Show the detail →</button></div></div>`;
    }).join('');
    return {html: `<div class="story">${html}</div>`};
  },

  kpi_row(ctx) {
    let list;
    if (HEADLINE_ROWS.has(ctx.mod.id)) {
      // The API orders kpis by priority and flags the headline set (display.headline); take the first 8 headline KPIs.
      // Before that flag exists, fall back to the first 8 KPIs in API order.
      const flagged = ctx.R.kpis.some(k => k.display && 'headline' in k.display);
      list = (flagged ? ctx.R.kpis.filter(k => k.display.headline === true) : ctx.R.kpis).slice(0, 8);
    } else {
      const ids = new Set(ctx.mod.required_metrics);
      list = ctx.R.kpis.filter(k => ids.has(k.metric_id)).sort((a, b) => a.display.rank - b.display.rank).slice(0, 8);
    }
    const title = MOD_TITLES[ctx.mod.id] ? `<div class="mod-title">${esc(MOD_TITLES[ctx.mod.id])}</div>` : '';
    const cols = list.length === 5 ? 5 : Math.min(4, list.length || 1);
    return {html: title + `<div class="kpis" style="grid-template-columns:repeat(${cols},minmax(0,1fr))">${list.map(k => kpiTile(k, ctx.R.meta.node.id, ctx.pri)).join('')}</div>`};
  },

  observations(ctx) {
    const all = ctx.R.observations;
    const main = all.filter(o => o.rule_id !== 'R8').slice(0, 4), warn = all.filter(o => o.rule_id === 'R8');
    const list = [...main, ...warn];
    const body = list.length ? list.map((o, i) => obsHtml(o, i, all.indexOf(o))).join('')
      : '<div class="empty">No observations fired for this view.</div>';
    return {cls: 'w7', html: `<div class="card"><h2>What matters for this customer <span class="small">· rules-generated observations, ranked by priority</span></h2>${body}</div>`};
  },

  site_rank(ctx) {
    const p = ctx.pri[0], r = RANK_BY[p] || RANK_BY.cost;
    const rows = ctx.R.sites.filter(s => s.metrics[r.k] && s.metrics[r.k].value != null)
      .sort((a, b) => r.dir * (a.metrics[r.k].value - b.metrics[r.k].value));
    const mx = Math.max(...rows.map(s => Math.abs(s.metrics[r.k].value)), 0) || 1;
    const prefix = ctx.R.meta.node.name.split(' ')[0] + ' ';
    const tr = rows.slice(0, 10).map(s => { const m = s.metrics[r.k];
      return `<tr class="click" data-site="${esc(s.node_id)}"><td>${esc(s.name.replace(prefix, ''))}<div class="small">${esc(s.country)} · ${esc(s.site_type)}</div></td>
        <td style="width:40%"><div class="bar"><i style="width:${Math.abs(m.value) / mx * 100}%"></i></div></td><td>${esc(fmtM(m))}</td></tr>`; }).join('');
    return {cls: 'w5', html: `<div class="card"><h2>Sites ranked by ${esc(r.l)}</h2><table>${tr}</table>
      <div class="small" style="margin-top:6px">Showing ${Math.min(10, rows.length)} of ${rows.length}. Open <button type="button" class="link" data-go="sites">Sites</button> for all.</div></div>`};
  },

  site_table(ctx) {
    const {R, S} = ctx;
    const cols = [['Site', 'name'], ['Country', 'country'], ['Type', 'site_type'], ['Wearers', 'active_wearers'],
      ['Utilisation', 'utilisation'], ['On-time', 'on_time_rate'], ['Req./100 w', 'service_requests_per_100w'],
      ['Repairs/100 w', 'repairs_per_100w'], ['kg/wearer', 'washed_kg_per_wearer'], ['Water saved m³', 'water_saving_l'],
      ['CO₂e avoided t', 'co2_saving_kg']];
    const textCols = new Set(['name', 'country', 'site_type']);
    const zf = {}; ['utilisation', 'on_time_rate', 'service_requests_per_100w', 'repairs_per_100w', 'washed_kg_per_wearer']
      .forEach(k => { zf[k] = zScores(R.sites, k); });
    const val = (s, k) => textCols.has(k) ? s[k] : (s.metrics[k] ? s.metrics[k].value : null);
    let rows = [...R.sites];
    if (S.sort) { const [k, d] = S.sort;
      rows.sort((a, b) => { const va = val(a, k), vb = val(b, k);
        if (va == null) return 1; if (vb == null) return -1; return (va > vb ? 1 : va < vb ? -1 : 0) * d; }); }
    const head = `<tr>${cols.map(([l, k]) => `<th class="sort ${textCols.has(k) ? 'l' : ''}" data-sort="${k}">${l}${S.sort && S.sort[0] === k ? (S.sort[1] > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr>`;
    const body = rows.map(s => `<tr class="click ${S.site === s.node_id ? 'sel' : ''}" data-site="${esc(s.node_id)}">${cols.map(([, k]) => {
      if (textCols.has(k)) return `<td class="l">${esc(s[k])}</td>`;
      const m = s.metrics[k]; const z = zf[k] ? zf[k](s) : null;
      const dot = z != null && Math.abs(z) >= 1.5 ? ` <span class="flag" title="${isSimple() ? 'Unusual compared with the other sites' : `z = ${num(z, 1)} vs peer sites`}">●</span>` : '';
      const w = m && m.dq_warning ? '<span class="warn" title="Data-consistency warning">⚠</span>' : '';
      return `<td>${esc(m ? cellFmt(m) : '–')}${w}${dot}</td>`; }).join('')}</tr>`).join('');
    return {html: `<div class="card"><table>${head}${body}</table>
      <div class="small" style="margin-top:6px">Click a column to sort, or a row to drill down. <span class="flag">●</span> = ${isSimple() ? 'unusual compared with the other sites' : 'outlier vs peer sites (|z| ≥ 1.5)'}.</div></div>`};
  },

  site_detail(ctx) {
    const {R, S} = ctx;
    const s = S.site && R.sites.find(x => x.node_id === S.site);
    if (!s) return {html: '<div class="card small">Select a site above to see its KPI cards and monthly trends.</div>'};
    const ids = ['utilisation', 'on_time_rate', 'avg_cycle_hours', 'service_requests', 'service_requests_per_100w',
      'repairs', 'repairs_per_100w', 'washed_kg_per_wearer'];
    const tiles = ids.map(k => s.metrics[k]).filter(Boolean).map(m => kpiTile(m, s.node_id, ctx.pri)).join('');
    const obs = R.observations.filter(o => o.node_id === s.node_id);
    const obsH = obs.length ? `<div style="margin-top:12px">${obs.map(o => obsHtml(o, null, R.observations.indexOf(o))).join('')}</div>` : '';
    const tr = ctx.siteReview && ctx.siteReview.trends;
    const charts = [];
    let trendsH = '<div class="small" style="margin-top:12px">Loading monthly trends…</div>';
    if (tr) {
      const months = (tr.active_wearers || tr.repairs || []).map(p => p.month);
      const ser = k => (tr[k] || []).map(p => p.value);
      trendsH = `<div class="grid c2" style="margin-top:12px"><div>${chart('chSite', 'xs')}</div><div>${chart('chSite2', 'xs')}</div></div>`;
      charts.push({id: 'chSite', type: 'line', data: {labels: months, datasets: [
        {label: 'Allocated pieces', data: ser('garments_allocated'), borderColor: COLORS.navy},
        {label: 'Scanned in use', data: ser('active_assets_scanned'), borderColor: COLORS.red},
        {label: 'Wearers (de-duplicated)', data: ser('active_wearers'), borderColor: COLORS.grey, borderDash: [4, 4]}]}});
      charts.push({id: 'chSite2', type: 'bar', data: {labels: months, datasets: [
        {label: 'Repairs', data: ser('repairs'), backgroundColor: COLORS.blue},
        {label: 'Service requests', data: ser('service_requests'), backgroundColor: COLORS.orange},
        {label: 'Late cycles', data: ser('late_cycles'), backgroundColor: COLORS.red}]}});
    }
    return {charts, html: `<div class="card" id="siteDetail"><h2>${esc(s.name)} <span class="small">· ${esc(s.site_type)} · ${esc(s.city)}, ${esc(s.country)} · laundry ${esc(s.laundry_id)}</span>
      <button type="button" class="link small" style="float:right" data-close-site="1">close</button></h2>
      <div class="kpis">${tiles}</div>${obsH}${trendsH}</div>`};
  },

  footprint_cards(ctx) {
    const b = ctx.R.meta.baseline.name, k = ctx.kpi;
    const rows = [['Water', 'water_saving_l', 'allocated_water_l', 'baseline_water_l'],
      ['CO₂e (washing + logistics)', 'co2_saving_kg', 'allocated_co2_kg', 'baseline_co2_kg'],
      ['Energy', 'energy_saving_kwh', 'allocated_energy_kwh', 'baseline_energy_kwh']];
    return {html: `<div class="grid c3">${rows.map(([l, s, a, bl]) => { const sv = k(s);
      return `<div class="card kpi" data-explain="${s}" data-node="${esc(ctx.R.meta.node.id)}"><div class="small">${l}</div>
        <div style="font-size:22px;font-weight:700;color:var(--navy)">${esc(fmtM(sv))} saved</div>
        <div class="small">Lindström ${esc(fmtM(k(a)))} ${badges(k(a))} vs ${esc(b)} ${esc(fmtM(k(bl)))}</div>
        <div class="range">${esc(rangeText(sv))} · ${badges(sv, true)}</div></div>`; }).join('')}</div>`};
  },

  footprint_pct_chart(ctx) {
    const ids = ['footprint_pct_of_baseline_water', 'footprint_pct_of_baseline_co2', 'footprint_pct_of_baseline_energy'];
    const ms = ids.map(ctx.kpi), b = ctx.R.meta.baseline.name;
    const max = Math.max(110, ...ms.map(m => (m && m.range ? m.range.high : m && m.value) || 0));
    return {cls: 'w6', html: `<div class="card"><h2>Lindström footprint as % of baseline</h2>${chart('chBase')}
      <div class="legend">${ms.map(m => `<span>${esc(m.label)}: ${esc(rangeText(m) || fmtM(m))} ${badges(m)}</span>`).join('')}</div>
      <div class="legend"><span>${gloss(`Footprint = allocated from laundry level by washed-kg share${isSimple() ? '' : ' (A003)'}. Baseline = washed kg × baseline factor.`)}</span></div></div>`,
    charts: [{id: 'chBase', type: 'bar', data: {labels: ['Water', 'CO₂e (washing + logistics)', 'Energy'], datasets: [
      {label: `${b} = 100`, data: [100, 100, 100], backgroundColor: COLORS.light},
      {label: 'Lindström (allocated), % of baseline', data: ms.map(m => m.value), backgroundColor: COLORS.navy}]},
    options: {scales: {y: {min: 0, max: Math.ceil(max / 10) * 10, ticks: {callback: v => v + '%'}}}}}]};
  },

  baseline_compare_chart(ctx) {
    const bl = (ctx.R.comparisons && ctx.R.comparisons.baselines) || [], sel = ctx.R.meta.baseline.id;
    return {cls: 'w6', html: `<div class="card"><h2>Compare all baselines (CO₂e saving, base case)</h2>${chart('chAllBase')}
      <div class="legend">${bl.map(b => `<span>${esc(b.name)}: ${esc(fmtV('kgCO2e', b.co2_saving_kg))} · ${esc(fmtV('l', b.water_saving_l))} water</span>`).join('')}</div></div>`,
    charts: [{id: 'chAllBase', type: 'bar', data: {labels: bl.map(b => b.name), datasets: [{label: 't CO₂e avoided (base)',
      data: bl.map(b => b.co2_saving_kg == null ? null : b.co2_saving_kg / 1000),
      backgroundColor: bl.map(b => b.baseline_id === sel ? COLORS.red : COLORS.grey)}]},
    options: {indexAxis: 'y', plugins: {legend: {display: false}}}}]};
  },

  repairs_month_chart(ctx) {
    const rm = ctx.R.circularity.repairs_by_month || [];
    return {cls: 'w4', html: `<div class="card"><h2>Repairs by month</h2>${chart('chRep', 'sm')}</div>`,
      charts: [{id: 'chRep', type: 'bar', data: {labels: rm.map(r => r.month), datasets: [{label: 'Repairs', data: rm.map(r => r.repairs), backgroundColor: COLORS.blue}]},
        options: {plugins: {legend: {display: false}}}}]};
  },

  repairs_type_chart(ctx) {
    const t = ctx.R.circularity.repairs_by_type || {};
    return {cls: 'w4', html: `<div class="card"><h2>Repairs by type</h2>${chart('chRepT', 'sm')}</div>`,
      charts: [{id: 'chRepT', type: 'doughnut', data: {labels: Object.keys(t), datasets: [{data: Object.values(t),
        backgroundColor: [COLORS.navy, COLORS.red, COLORS.blue, COLORS.grey, COLORS.orange, COLORS.teal]}]}}]};
  },

  waste_routes_chart(ctx) {
    const w = ctx.R.circularity.waste_routes || {};
    return {cls: 'w4', html: `<div class="card"><h2>Attributed textile-waste routes</h2>${chart('chWaste', 'sm')}<div class="legend">kg, allocated by washed-kg share ${badges(ctx.kpi('textile_waste_kg'))}</div></div>`,
      charts: [{id: 'chWaste', type: 'doughnut', data: {labels: Object.keys(w).map(k => k.replace(/_/g, ' ')), datasets: [{data: Object.values(w),
        backgroundColor: [COLORS.green, COLORS.teal, COLORS.orange, COLORS.slate]}]}}]};
  },

  exec_summary(ctx) {
    const n = ctx.R.narrative;
    if (!n || !n.exec_summary) return null;  // narrative not generated yet: hide the block
    const paras = n.exec_summary.split(/\n\s*\n/).map(p => `<p>${esc(p)}</p>`).join('');
    return {cls: 'w6', html: `<div class="card"><h2>Executive value summary</h2>${paras}
      <p class="small">Drafted by: ${esc(n.generated_by)}. Built from the calculated metrics only; it adds no numbers.</p></div>`};
  },

  discussion_points(ctx) {
    const pts = (ctx.R.narrative && ctx.R.narrative.discussion_points) || [];
    const li = pts.map(p => { const i = p.indexOf(':');
      return i > 0 && i < 40 ? `<li><b>${esc(p.slice(0, i))}</b>${esc(p.slice(i))}</li>` : `<li>${esc(p)}</li>`; }).join('');
    const wide = ctx.R.narrative && ctx.R.narrative.exec_summary ? 'w6' : '';
    return {cls: wide, html: `<div class="card"><h2>${pts.length === 5 ? 'Five discussion points' : 'Discussion points'}</h2><ol class="qs">${li}</ol></div>`};
  },

  action_table(ctx) {
    const unitOf = id => { const m = ctx.kpi(id); return m ? m.unit : null; };
    const labelOf = id => { const m = ctx.kpi(id); return m ? m.label : id; };
    const rows = ctx.R.actions.map(a => `<tr><td class="l">${esc(a.text)}</td><td class="l">${esc(a.owner)}</td>
      <td class="l">${esc(labelOf(a.kpi_metric_id))}</td><td>${esc(fmtV(unitOf(a.kpi_metric_id), a.value_2025))}</td>
      <td><input type="text" placeholder="set" value="${esc(a.target_2026 == null ? '' : a.target_2026)}"></td></tr>`).join('');
    return {html: `<div class="card"><h2>Agreed actions → tracked next year</h2><table>
      <tr><th class="l">Action</th><th class="l">Owner</th><th class="l">KPI</th><th>${esc(ctx.R.meta.period)}</th><th>2026 target</th></tr>${rows ||
      '<tr><td class="l" colspan="5"><span class="small">No actions for this view.</span></td></tr>'}</table>
      <div class="small" style="margin-top:6px">Targets are editable for the meeting and are not saved in this prototype.</div></div>`};
  },

  methodology(ctx) {
    const m = ctx.R.methodology;
    const legend = (m.status_legend || []).map(s => `<p><span class="badge b-${esc(s.status)}">${esc(s.status)}</span> ${esc(s.meaning)}</p>`).join('') +
      '<p><span class="badge b-SYN">SYN</span> Synthetic source value from the data pack (provenance).</p>' +
      '<p><span class="warn">⚠</span> An input carries a data-consistency warning (see Data readiness).</p>';
    return {html: `<div class="grid c2"><div class="card"><h2>Calculation boundary</h2><ul class="tight">${(m.boundary || []).map(b => `<li>${esc(b)}</li>`).join('')}</ul>
      <p class="small">Baseline in use: <b>${esc(ctx.R.meta.baseline.name)}</b> · sensitivity <b>${esc(ctx.R.meta.sensitivity)}</b> · assumption set ${esc(ctx.R.meta.assumption_set_version)}</p></div>
      <div class="card"><h2>Status legend</h2>${legend}</div></div>
      <div class="card" style="margin-top:12px"><h2>Limitations</h2><ul class="tight">${(m.limitations || []).map(b => `<li>${esc(b)}</li>`).join('')}</ul></div>`};
  },

  assumption_table(ctx) {
    const rows = (ctx.R.methodology.assumptions_used || []).map(a => `<tr><td class="l">${esc(a.id)}</td><td class="l">${esc(a.assumption)}</td>
      <td class="l">${esc(a.value_or_rule)}</td><td class="l">${esc(a.confidence)}</td><td class="l">${esc(a.treatment)}</td></tr>`).join('');
    return {html: `<div class="card"><h2>Assumption register</h2><table><tr><th class="l">ID</th><th class="l">Assumption</th>
      <th class="l">Value / rule</th><th class="l">Confidence</th><th class="l">Treatment</th></tr>${rows}</table></div>`};
  },

  data_quality(ctx) {
    const dq = ctx.R.data_quality, groups = {};
    (dq.warnings || []).forEach(w => { const key = w.check_id + '|' + w.entity_id; (groups[key] = groups[key] || []).push(w); });
    const TITLES = {C1: 'Laundry volume inconsistency'};
    const alerts = Object.values(groups).sort((a, b) => (a[0].check_id === 'C1' ? -1 : 0) - (b[0].check_id === 'C1' ? -1 : 0)).map(ws => {
      const w0 = ws[0], t = TITLES[w0.check_id] || `Check ${w0.check_id}`;
      return `<div class="alert"><div class="t">⚠ ${esc(t)}: ${esc(w0.entity_name ? `${w0.entity_name} (${w0.entity_id})` : w0.entity_id)} <span class="small">(${esc(w0.check_id)} · ${ws.length} monthly warning${ws.length > 1 ? 's' : ''})</span></div>
        <div class="small" style="margin:4px 0 6px">${w0.check_id === 'C1' ? 'Customer washed kg routed to this laundry is far above the laundry’s own reported washed kg, so per-kg allocation of water, energy, CO₂e and waste is uncertain. Affected figures carry ⚠.' : ''}</div>
        <table><tr><th class="l">Month</th><th class="l">Detail</th></tr>${ws.map(w => `<tr><td class="l">${esc(w.month)}</td><td class="l">${esc(w.message || w.detail)}</td></tr>`).join('')}</table></div>`; }).join('');
    return {html: `${alerts || '<div class="card small">No data-consistency warnings touch this account.</div>'}
      <div class="card" style="margin-top:12px"><h2>Quarantined source rows</h2><p><b>${esc(num(dq.quarantine_count))}</b> rows failed validation on load and are excluded from every figure.</p></div>`};
  },

  readiness_table(ctx) {
    const gaps = ctx.R.data_quality.gaps || [];
    const hidden = ctx.hidden || [];
    const hiddenH = hidden.length ? `<ul class="tight">${hidden.map(h => `<li><b>${esc(h.id)}</b> (${esc(h.page)}): ${esc(h.reason)}</li>`).join('')}</ul>`
      : '<p class="small">All modules have the data they need for this view.</p>';
    return {html: `<div class="card"><h2>How prototype fields map to future approved sources</h2><table>
      <tr><th class="l">Field</th><th class="l">Future approved source</th><th class="l">Status</th><th class="l">Note</th></tr>
      ${gaps.map(g => `<tr><td class="l">${esc(g.field)}</td><td class="l">${esc(g.future_source)}</td><td class="l">${esc(g.status)}</td><td class="l">${esc(g.note)}</td></tr>`).join('')}</table></div>
      <div class="card" style="margin-top:12px"><h2>Hidden: missing data</h2>${hiddenH}</div>`};
  },

  // ---- Service vs do-it-yourself (design §8a): review.dto; the engine computes every figure ----
  diy_compare(ctx) {
    const d = ctx.R.dto, k = ctx.kpi, node = ctx.R.meta.node.id;
    if (!d) return {html: '<div class="card empty">No do-it-yourself comparison for this view.</div>'};
    const bname = ctx.R.meta.baseline.name, customer = ctx.S.audience === 'customer';
    const kam = (d.inputs || []).some(i => i.source === 'kam');
    const chip = kam ? '<span class="kchip" title="At least one figure uses a value entered by the account manager (see Your numbers)">✎ uses figures entered by the account manager</span>' : '';
    const partial = (d.missing_lines || []).length ? `<div class="alert small">The do-it-yourself total is partial: ${esc(d.missing_lines.map(id => (d.lines.find(l => l.id === id) || {}).label || id).join(', '))} could not be sized for this view, so the total is lower than it would be.</div>` : '';
    const lines = d.lines.map(l => fig(l.in_total ? l.label : `${l.label} (explanatory, not in total)`, l.diy, node, l.in_total ? 'sub' : 'sub muted')).join('');
    let net;
    if (d.net) net = fig('Do-it-yourself total minus Lindström contract price', d.net, node, 'hl') + `<div class="small">${d.net.value >= 0 ? 'Positive: doing it yourself would cost more than the service.' : 'Negative: on cost alone, doing it yourself would cost less than the service.'}</div>`;
    else net = customer ? '' : '<div class="small hint">Enter the contract price in Your numbers to see the net comparison.</div>';
    const cost = fig(`Do-it-yourself cost (${bname})`, d.diy_total, node, 'hl') + `<div class="figs">${lines}</div>` +
      (d.contract_price ? fig('Lindström contract price', d.contract_price, node) : '') + net;
    const c = d.convenience || {};
    const env = fig('Water saved', k('water_saving_l'), node) + fig('CO₂e avoided', k('co2_saving_kg'), node) + fig('Energy saved', k('energy_saving_kwh'), node) +
      `<div class="small">Lindström's allocated footprint vs ${esc(bname)} for the same washed kilograms. <button type="button" class="link" data-go="footprint">Footprint detail</button></div>`;
    const time = fig('Staff hours freed', c.staff_hours_freed, node, 'hl') + fig('On-time delivery', c.on_time_rate, node) +
      fig('Garment utilisation', c.utilisation, node) + fig('Service requests per 100 wearers', c.service_requests_per_100w, node);
    const hyg = d.hygiene_note ? `<p>${esc(d.hygiene_note)}</p>` : `<p class="small">No industry-specific hygiene note for ${esc(ctx.R.meta.node.industry)}.</p>`;
    const col = (t, body) => `<div class="card dcol"><h2>${t}</h2>${body}</div>`;
    return {html: `<div class="diy-head"><span>Lindström service vs <b>${esc(bname)}</b> · ${esc(ctx.R.meta.period)} · change the comparison in the toolbar</span>${chip}</div>${partial}
      <div class="dgrid">${col('Environment', env)}${col('Cost', cost)}${col('Time', time)}${col('Hygiene', hyg)}</div>
      <p class="small">€, hours and CO₂e are shown side by side and never added into one score. Click any figure to see how it is calculated.</p>`};
  },

  diy_cost_chart(ctx) {
    const d = ctx.R.dto;
    if (!d || !d.diy_total || d.diy_total.value == null) return null;
    const cols = [COLORS.navy, COLORS.blue, COLORS.grey, COLORS.teal, COLORS.orange];
    const inTot = d.lines.filter(l => l.in_total && l.diy && l.diy.value != null);
    const cp = d.contract_price && d.contract_price.value != null ? d.contract_price : null;
    const labels = ['Do it yourself', ...(cp ? ['Lindström contract'] : [])];
    const ds = inTot.map((l, i) => ({label: l.label, data: [l.diy.value, ...(cp ? [null] : [])], backgroundColor: cols[i % cols.length], stack: 's'}));
    if (cp) ds.push({label: 'Lindström contract price', data: [null, cp.value], backgroundColor: COLORS.red, stack: 's'});
    const ex = d.lines.filter(l => !l.in_total);
    return {cls: 'w5', html: `<div class="card"><h2>Cost breakdown (${esc(ctx.R.meta.period)}, ${esc(ctx.R.meta.sensitivity)} case)</h2>${chart('chDiy', 'sm')}
      <div class="legend">${ex.map(l => `<span>${esc(l.label)} (${esc(fmtM(l.diy))}) is already reflected in garment purchases: explanatory, not in the total.</span>`).join('')}
      ${cp ? '' : '<span>No contract price entered, so there is no Lindström bar.</span>'}</div></div>`,
    charts: [{id: 'chDiy', type: 'bar', data: {labels, datasets: ds}, options: {indexAxis: 'y',
      scales: {x: {stacked: true, ticks: {callback: v => '€' + num(v / 1000, 0) + 'k'}}, y: {stacked: true}},
      plugins: {tooltip: {callbacks: {label: c => `${c.dataset.label}: €${num(c.raw, 0)}`}}}}}]};
  },

  diy_inputs(ctx) {
    const d = ctx.R.dto;
    if (!d) return null;
    const rows = d.inputs || [], spec = ctx.ext.spec || {};
    if (ctx.S.audience === 'customer') {
      const tr = rows.filter(r => r.key !== INPUT_CONTRACT || r.value != null).map(r => `<tr><td class="l">${esc(r.label)}</td>
        <td>${esc(rawNum(r.value))}</td><td>${r.key === INPUT_CONTRACT || r.low === r.high ? '' : `${esc(rawNum(r.low))}–${esc(rawNum(r.high))}`}</td>
        <td class="l">${esc(unitText(r.unit))}</td><td class="l">${srcBadge(r)}</td></tr>`).join('');
      return {cls: 'w7', html: `<div class="card"><h2>Figures used in this comparison</h2><table><tr><th class="l">Input</th><th>Value</th><th>Low–high</th><th class="l">Unit</th><th class="l">Source</th></tr>${tr}</table>
        <p class="small">Defaults are illustrative Nordic values (low confidence) unless your account manager entered your own figures.</p></div>`};
    }
    const tr = rows.map(r => {
      const isC = r.key === INPUT_CONTRACT, s = spec[r.key] || {};
      const ranged = r.source === 'kam' && !isC && !(r.low === r.value && r.high === r.value);
      const atDefault = r.value === s.default;
      const ph = part => (atDefault ? rawNum(s[part]) : '= value');
      const inp = (part, val, extra) => `<input type="text" inputmode="decimal" autocomplete="off" data-in="${esc(r.key)}" data-part="${part}" value="${esc(val)}" ${extra}>`;
      return `<tr data-key="${esc(r.key)}"><td class="l"><label for="in_${esc(r.key)}">${esc(r.label)}</label>${r.help ? `<div class="small">${esc(r.help)}</div>` : ''}</td>
        <td>${inp('value', rawNum(r.value), `id="in_${esc(r.key)}" placeholder="${isC ? 'not entered' : ''}"`)}</td>
        <td>${isC ? '' : inp('low', ranged ? rawNum(r.low) : '', `placeholder="${esc(ph('low'))}" aria-label="${esc(r.label)}, low"`)}</td>
        <td>${isC ? '' : inp('high', ranged ? rawNum(r.high) : '', `placeholder="${esc(ph('high'))}" aria-label="${esc(r.label)}, high"`)}</td>
        <td class="l">${esc(unitText(r.unit))}</td><td class="l">${srcBadge(r)}</td></tr>`;
    }).join('');
    return {cls: 'w7', html: `<div class="card"><h2>Your numbers <span class="small">· account manager only</span></h2>
      <form data-form="diy" novalidate><table class="inputs"><tr><th class="l">Input</th><th>Value</th><th>Low</th><th>High</th><th class="l">Unit</th><th class="l">Source</th></tr>${tr}</table>
      <div class="form-err" role="alert"></div>
      <div class="form-row"><button type="submit" class="btn">Save</button><button type="button" class="btn ghost" data-action="diy-reset">Reset to defaults</button></div>
      <p class="small">Decimal comma or dot both work (2,5 = 2.5). Leave a field blank to use the default. Low/high are optional: an entered value applies to low, base and high unless you also give a range. Saving keeps the growth inputs.</p></form></div>`};
  },

  // ---- Growth opportunities (design §8b G7): review.growth; per year, account-wide ----
  growth_inputs(ctx) {
    const g = ctx.ext.growthStored() || {}, cat = ctx.ext.catalogue || [];
    const used = new Set(ctx.R.meta.service_lines || []);
    const chosen = new Set(g.extra_service_lines || []);
    if (ctx.S.audience === 'customer') {
      const parts = [];
      if (g.extra_sites) parts.push(`${num(g.extra_sites)} more site${g.extra_sites === 1 ? '' : 's'}`);
      if (g.extra_wearers) parts.push(`${num(g.extra_wearers)} more employee${g.extra_wearers === 1 ? '' : 's'} on the service`);
      cat.filter(c => chosen.has(c.id)).forEach(c => parts.push(`add ${c.name}`));
      return {cls: 'w4', html: `<div class="card"><h2>Scenario discussed</h2>${parts.length ? `<ul class="tight">${parts.map(p => `<li>${esc(p)}</li>`).join('')}</ul>` : '<p class="small">No scenario entered yet.</p>'}
        ${parts.length ? `<p class="small">Entered by your account manager${g.entered_at ? `, ${esc(g.entered_at)}` : ''}.</p>` : ''}</div>`};
    }
    const boxes = cat.map(c => `<label class="cb" title="${esc(c.description)}"><input type="checkbox" data-gline="${esc(c.id)}" ${chosen.has(c.id) ? 'checked' : ''}>
      ${esc(c.name)}${used.has(c.service_line) ? ' <span class="small">(already used, will be skipped)</span>' : ''}</label>`).join('');
    const field = (key, label, val, hint) => `<div class="gfield" data-key="${key}"><label for="g_${key}">${label}</label>
      <input type="text" inputmode="decimal" autocomplete="off" id="g_${key}" data-g="${key}" value="${esc(val ? rawNum(val) : '')}" placeholder="${esc(hint)}"></div>`;
    return {cls: 'w4', html: `<div class="card"><h2>What could we add?</h2><form data-form="growth" novalidate>
      ${field('extra_sites', 'Sites not yet served', g.extra_sites, 'e.g. 4')}
      ${field('extra_wearers', 'Employees not yet on the service', g.extra_wearers, 'e.g. 200')}
      <div class="gfield" data-key="extra_service_lines"><div class="glabel">Service lines not yet used</div>${boxes || '<span class="small">Service catalogue unavailable.</span>'}</div>
      ${field('expansion_price_eur_per_site_year', 'Optional: Lindström price per extra site and year (€)', g.expansion_price_eur_per_site_year, 'blank = no net figure')}
      <div class="form-err" role="alert"></div>
      <div class="form-row"><button type="submit" class="btn">Size the opportunity</button><button type="button" class="btn ghost" data-action="growth-clear">Clear</button></div>
      <p class="small">Saved with Your numbers (the do-it-yourself inputs are kept). Typical volumes and prices per service line are illustrative defaults (T12+).</p></form></div>`};
  },

  growth_levers(ctx) {
    const g = ctx.R.growth, node = ctx.R.meta.node.id, customer = ctx.S.audience === 'customer';
    const intro = "<p class=\"small\">Per year, for the whole account, scaled from this customer's own current figures. The product and service-line filters do not apply. Estimates, not a quote.</p>";
    if (!g) return {cls: 'w8', html: `<div class="card empty">${customer ? 'No growth scenario has been entered for this customer yet.' : 'Enter sites, employees or service lines and press <b>Size the opportunity</b> to see the extra savings.'}</div>`};
    const cat = {}; (ctx.ext.catalogue || []).forEach(c => { cat[c.id] = c; });
    const notes = [
      ...(g.skipped_lines || []).map(s => `${(cat[s.id] || {}).name || s.id}: ${s.reason}`),
      ...(g.partial ? ['The do-it-yourself total behind these figures is partial, so the € figures are lower than they would be.'] : []),
      ...(g.notes || [])];
    const notesH = notes.length ? `<div class="alert small"><ul class="tight">${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul></div>` : '';
    if (!g.totals) return {cls: 'w8', html: `${notesH}<div class="card empty">Nothing to size: every chosen service line is already used by this customer.</div>`};
    const figs = x => fig('Do-it-yourself cost avoided', x.diy_cost_avoided, node, 'hl') +
      (x.net ? fig('Cost avoided minus Lindström price', x.net, node) : '') +
      fig('Staff hours freed', x.staff_hours_freed, node) + fig('CO₂e avoided', x.co2_saving_kg, node) + fig('Water saved', x.water_saving_l, node);
    const cards = g.levers.map(lv => `<div class="card lever"><h2>${esc(lv.label)}</h2>${figs(lv)}
      ${lv.lindstrom_offer_url ? `<div class="small">${extLink(lv.lindstrom_offer_url, `About the ${(cat[(lv.id || '').replace('line:', '')] || {}).name || 'Lindström'} service`)}</div>` : ''}</div>`).join('');
    const say = g.narrative_line ? `<div class="say"><div class="say-h">What to say <button type="button" class="btn ghost sm" data-copy-growth="1" title="Copy the line">Copy</button></div>
      <div class="say-t">${gloss(g.narrative_line)}</div>${g.what_to_say ? `<div class="small" style="margin-top:4px">${esc(g.what_to_say)}</div>` : ''}</div>` : '';
    return {cls: 'w8', html: `${say}${notesH}${intro}<div class="levers">${cards}</div>
      ${g.levers.length > 1 ? `<div class="card lever total"><h2>All levers together, per year</h2>${figs(g.totals)}</div>` : ''}`};
  },

  // ---- Account intelligence (design §8b G8): POST /intel; no engine numbers are mixed in ----
  intel_page(ctx) {
    const I = ctx.ext.intel, name = ctx.R.meta.node.name;
    if (ctx.S.audience === 'customer') return {html: '<div class="card empty">Account intelligence is a preparation tool for the account manager. Switch the audience to KAM to use it.</div>'};
    const snaps = (I.snapshots || []).map(s => `<button type="button" class="chip ${I.report && I.report.company === s.company ? 'on' : ''}" data-intel-snap="${esc(s.company)}">${esc(s.company)} · snapshot ${esc(s.generated_at)}</button>`).join('');
    const note = `<div class="note">${esc(name)} is a fictional customer, so there is nothing public to research. Try the example public company${snaps ? ' below' : ''}. In production the account's legal name would come from the CRM.</div>`;
    const form = `<form data-form="intel" class="intel-form" novalidate>
      <label class="ctl">Company<input type="text" id="intelCompany" maxlength="200" value="${esc(I.company)}" placeholder="e.g. Fazer Group"></label>
      <label class="ctl">Website (optional)<input type="text" id="intelWebsite" maxlength="300" value="${esc(I.website)}" placeholder="https://…"></label>
      <button type="submit" class="btn" ${I.loading ? 'disabled' : ''}>${I.loading ? 'Researching…' : 'Research'}</button></form>
      ${snaps ? `<div class="chips">Examples: ${snaps}</div>` : ''}`;
    let body = '';
    if (I.loading) body = '<div class="card empty">Researching public sources… a live search can take up to a minute.</div>';
    else if (I.error) body = `<div class="alert"><div class="t">Not available</div><div>${esc(I.error)}</div></div>`;
    else if (I.report) {
      const r = I.report, sec = r.sections || {};
      const mode = r.mode === 'live' ? `<span class="badge b-LIVE">Live</span> <span class="small">researched ${esc(r.generated_at)}</span>`
        : `<span class="badge b-SNAP">Snapshot from ${esc(r.generated_at)}</span>`;
      const claims = list => ((list || []).length ? `<ul class="claims">${list.map(c => `<li>${esc(c.text)} <span class="src-link">· ${extLink(c.source_url)}${c.source_date ? `, ${esc(c.source_date)}` : ''}</span></li>`).join('')}</ul>`
        : '<p class="small">Nothing sourced found.</p>');
      const helps = (sec.how_lindstrom_helps || []).map(h => { const c = (ctx.ext.catalogue || []).find(x => x.id === h.offer_id);
        return `<div class="card help"><h2>${esc(h.offer_name)}</h2><p>${esc(h.why)}</p>
          <div class="small">Based on: ${(h.based_on || []).map(u => extLink(u)).join(', ') || '–'}${c && c.lindstrom_offer_url ? ` · ${extLink(c.lindstrom_offer_url, 'Lindström offer')}` : ''}</div></div>`; }).join('');
      const starters = (sec.conversation_starters || []).map(s => `<li>${esc(s)}</li>`).join('');
      const sources = (r.sources || []).map(s => `<li>${extLink(s.url, s.title || s.url)}${s.date ? ` <span class="small">· ${esc(s.date)}</span>` : ''}</li>`).join('');
      body = `<div class="banner ai">⚠ ${esc(r.disclaimer)}</div>
        <div class="intel-head"><h2>${esc(r.company)}</h2>${r.website ? `<span class="small">${extLink(r.website)}</span>` : ''} ${mode}</div>
        <div class="grid c2"><div class="card"><h2>Where they're going</h2>${claims(sec.direction)}</div>
          <div class="card"><h2>Sustainability &amp; reporting</h2>${claims(sec.sustainability)}</div></div>
        <div class="card" style="margin-top:12px"><h2>Industry trends</h2>${claims(sec.trends)}</div>
        <h2 style="margin-top:16px">How Lindström can help</h2><div class="helps">${helps || '<div class="card small">No mapped offers.</div>'}</div>
        <div class="grid c2" style="margin-top:12px"><div class="card"><h2>Conversation starters</h2><ol class="qs">${starters}</ol></div>
          <div class="card"><h2>Sources</h2><ol class="sources">${sources}</ol></div></div>`;
    }
    return {html: `${note}<div class="card">${form}</div><div style="margin-top:12px">${body}</div>`};
  },

  // ---- Built on Lindström's work (design §3): config/lindstrom_fit.yaml ----
  fit_page(ctx) {
    const F = ctx.ext.fit;
    if (F === undefined) return {html: '<div class="card empty">Loading…</div>'};
    if (!F) return {html: '<div class="card empty">Could not load the page content.</div>'};
    const kind = k => { const [t, c] = FIT_KIND[k] || [k, '']; return `<span class="badge ${c}">${esc(t)}</span>`; };
    const rows = (F.assets || []).map(a => `<tr><td class="l"><b>${esc(a.asset)}</b></td><td class="l">${esc(a.today)}</td><td class="l">${esc(a.value_review)}</td>
      <td class="l">${esc(a.brief_line)}</td><td class="l">${kind(a.kind)} ${a.kind === 'PUBLIC_REFERENCE' ? extLink(a.source) : esc(a.source)}</td></tr>`).join('');
    const brief = (F.brief_map || []).map(b => `<tr><td class="l">${esc(b.asked)}</td><td class="l">${esc(b.where)}</td><td class="l">${b.status === 'done' ? '✅ done' : esc(b.status)}</td></tr>`).join('');
    return {html: `<div class="alert small">ℹ ${esc(F.note)}</div>
      <div class="card"><h2>Lindström assets → how Value Review uses or extends them</h2><table class="fit"><tr><th class="l">Lindström asset</th><th class="l">What Lindström has today</th>
        <th class="l">How Value Review uses or extends it</th><th class="l">Brief line answered</th><th class="l">Source</th></tr>${rows}</table></div>
      <div class="card" style="margin-top:12px"><h2>What you asked → where it is</h2><table><tr><th class="l">What you asked</th><th class="l">Where it is</th><th class="l">Status</th></tr>${brief}</table></div>`};
  },
};

/** Simple mode drops the z-score the engine appends to a finding, e.g. " (z = -1.5)". */
const plainFinding = f => (isSimple() ? String(f || '').replace(/\s*\(z\s*=\s*[-−]?[\d.,]+\)/g, '') : f);

function obsHtml(o, i, idx) {
  const warn = o.rule_id === 'R8';
  return `<div class="obs ${warn ? 'warn' : ''}"><div class="t">${warn ? '⚠ ' : (i == null ? '' : (i + 1) + '. ')}${esc(o.title)}</div>
    <div class="d">${gloss(plainFinding(o.finding))}</div><div class="a"><b>Next step:</b> ${esc(o.action)}</div>
    <div class="meta">${badges(o, true)} <span>tags: ${esc(tagLabels(o.tags))}</span> <button type="button" class="link" data-evidence="${idx}">Show evidence &amp; formula</button></div></div>`;
}

window.VR = {Components, PRI, esc, num, fmtV, fmtM, fmtRange, fmtAbout, rangeText, badges, weight, obsHtml,
  setMode, isSimple, setGlossary, glossTerm, gloss, plainFinding, LOCAL, resetLocal, INPUT_CONTRACT};
})();
