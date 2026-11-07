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
// lineage and formula text; ranges read "about X (between A and B)". Expert shows everything.
let MODE = 'simple';
const setMode = m => { MODE = m === 'expert' ? 'expert' : 'simple'; };
const isSimple = () => MODE === 'simple';
/** Range line for a metric in the current mode ('' when the metric has no range). */
const rangeText = m => (!m || !m.range ? '' : (isSimple() ? fmtAbout(m) : fmtRange(m)));

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
          <span class="link" data-detail="${esc(c.detail_view || '')}">Show the detail →</span></div></div>`;
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
      <div class="small" style="margin-top:6px">Showing ${Math.min(10, rows.length)} of ${rows.length}. Open <span class="link" data-go="sites">Sites</span> for all.</div></div>`};
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
      <span class="link small" style="float:right" data-close-site="1">close</span></h2>
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
      <div class="legend">${ms.map(m => `<span>${esc(m.label)}: ${isSimple() ? esc(rangeText(m) || fmtM(m)) : `${esc(fmtM(m))} (${esc(fmtRange(m))})`} ${badges(m)}</span>`).join('')}</div>
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
};

/** Simple mode drops the z-score the engine appends to a finding, e.g. " (z = -1.5)". */
const plainFinding = f => (isSimple() ? String(f || '').replace(/\s*\(z\s*=\s*[-−]?[\d.,]+\)/g, '') : f);

function obsHtml(o, i, idx) {
  const warn = o.rule_id === 'R8';
  return `<div class="obs ${warn ? 'warn' : ''}"><div class="t">${warn ? '⚠ ' : (i == null ? '' : (i + 1) + '. ')}${esc(o.title)}</div>
    <div class="d">${gloss(plainFinding(o.finding))}</div><div class="a"><b>Next step:</b> ${esc(o.action)}</div>
    <div class="meta">${badges(o, true)} <span>tags: ${esc(tagLabels(o.tags))}</span> <span class="link" data-evidence="${idx}">Show evidence &amp; formula</span></div></div>`;
}

window.VR = {Components, PRI, esc, num, fmtV, fmtM, fmtRange, fmtAbout, rangeText, badges, weight, obsHtml,
  setMode, isSimple, setGlossary, glossTerm, gloss, plainFinding};
})();
