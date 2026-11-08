/* Customisable dashboard layer. Modelled on Looker Studio's edit mode (12-column grid, move / resize
 * / remove, add from a library) and the GA4 Library (preset collections, reset to the standard view).
 * It only re-orders, resizes and hides the modules the registry already produced; it never changes
 * a number. The layout is saved per customer and page in this browser (localStorage). */
(() => {
'use strict';

const PAGES = new Set(['overview', 'sites', 'footprint', 'circularity', 'steering']);
const SPANS = [[4, '⅓'], [6, '½'], [8, '⅔'], [12, 'Full']];
const PRESETS = {  // like the Executive / Operations / Sustainability templates: filter by priority tag
  executive: {label: 'Executive', tags: null, only: ['overview_kpis', 'overview_observations', 'steering_summary', 'steering_points', 'footprint_savings']},
  operations: {label: 'Operations', tags: ['service', 'cost']},
  sustainability: {label: 'Sustainability', tags: ['water', 'emissions', 'circularity']},
};
const KEY = (acc, view) => `vr-layout:${acc}:${view}`;
let editing = false, rerender = () => {}, dragId = null, lastEntries = [], ctx = {acc: '', view: ''};

const nice = id => id.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

function load(acc, view) {
  try { const v = JSON.parse(localStorage.getItem(KEY(acc, view)) || 'null'); if (v && Array.isArray(v.order)) return v; } catch (e) { /* storage blocked */ }
  return {order: [], hidden: [], span: {}};
}
function save(acc, view, l) {
  try {
    if (!l.order.length && !l.hidden.length && !Object.keys(l.span).length) localStorage.removeItem(KEY(acc, view));
    else localStorage.setItem(KEY(acc, view), JSON.stringify(l));
  } catch (e) { /* storage blocked: the layout lasts for this session only */ }
}
const isCustom = l => l.order.length || l.hidden.length || Object.keys(l.span).length;

/** Entries arrive in the default (priority-ranked) order. Returns the ones to draw, in saved order. */
function arrange(view, acc, entries) {
  ctx = {acc, view}; lastEntries = entries;
  const l = load(acc, view);
  const pos = id => { const i = l.order.indexOf(id); return i < 0 ? 1e6 + entries.findIndex(e => e.id === id) : i; };
  const shown = entries.filter(e => !l.hidden.includes(e.id)).sort((a, b) => pos(a.id) - pos(b.id));
  return {shown, layout: l};
}

function attrs(id) {
  const s = load(ctx.acc, ctx.view).span[id];
  return `${s ? ` style="--span:${s}"` : ''}${editing ? ` draggable="true" data-lay-id="${esc(id)}"` : ''}`;
}

function chrome(id) {
  if (!editing) return '';
  const cur = load(ctx.acc, ctx.view).span[id];
  const opts = SPANS.map(([n, t]) => `<button type="button" class="lay-w${cur === n ? ' on' : ''}" data-lay="span" data-id="${esc(id)}" data-n="${n}" aria-label="Width ${t}" title="Width ${t}">${t}</button>`).join('');
  return `<div class="lay-bar" role="group" aria-label="Edit ${esc(nice(id))}">
    <span class="lay-grip" title="Drag to move" aria-hidden="true">⋮⋮</span><span class="lay-name">${esc(nice(id))}</span>
    <button type="button" data-lay="move" data-id="${esc(id)}" data-d="-1" aria-label="Move earlier" title="Move earlier">↑</button>
    <button type="button" data-lay="move" data-id="${esc(id)}" data-d="1" aria-label="Move later" title="Move later">↓</button>
    <span class="lay-widths">${opts}</span>
    <button type="button" class="lay-x" data-lay="hide" data-id="${esc(id)}" aria-label="Remove widget" title="Remove from this dashboard">✕</button></div>`;
}

function toolbar() {
  const l = load(ctx.acc, ctx.view);
  const titles = Object.fromEntries(lastEntries.map(e => [e.id, e.id]));
  const lib = l.hidden.filter(id => titles[id]);
  const add = editing ? `<label class="lay-add">Add widget <select data-lay="add" aria-label="Add widget"><option value="">${lib.length ? 'Choose…' : 'All widgets are shown'}</option>${lib.map(id => `<option value="${esc(id)}">${esc(nice(id))}</option>`).join('')}</select></label>
    <label class="lay-add">Start from <select data-lay="preset" aria-label="Preset view"><option value="">Preset…</option>${Object.entries(PRESETS).map(([k, p]) => `<option value="${k}">${p.label}</option>`).join('')}</select></label>
    <button type="button" class="btn ghost sm" data-lay="reset" ${isCustom(l) ? '' : 'disabled'}>Reset layout</button>` : '';
  return `<div class="lay-toolbar${editing ? ' is-editing' : ''}" role="toolbar" aria-label="Dashboard layout">
    <button type="button" class="btn ${editing ? '' : 'ghost'} sm" data-lay="toggle" aria-pressed="${editing}">${editing ? 'Done' : 'Customize'}</button>${add}
    ${editing ? '<span class="small">Drag a widget by its bar, or use ↑ ↓ and the width buttons. Saved in this browser for this customer.</span>'
      : (isCustom(l) ? '<span class="small">Custom layout active</span>' : '')}</div>`;
}

function commit(l) { save(ctx.acc, ctx.view, l); rerender(); }
function currentOrder(l) {
  const ids = lastEntries.map(e => e.id);
  const pos = id => { const i = l.order.indexOf(id); return i < 0 ? 1e6 + ids.indexOf(id) : i; };
  return ids.filter(id => !l.hidden.includes(id)).sort((a, b) => pos(a) - pos(b));
}

function act(el) {
  const l = load(ctx.acc, ctx.view), id = el.dataset.id, a = el.dataset.lay;
  if (a === 'toggle') { editing = !editing; rerender(); return; }
  if (a === 'reset') { commit({order: [], hidden: [], span: {}}); return; }
  if (a === 'span') { l.span[id] = +el.dataset.n; l.order = currentOrder(l); commit(l); return; }
  if (a === 'hide') { l.order = currentOrder(l).filter(x => x !== id); l.hidden = [...new Set([...l.hidden, id])]; commit(l); return; }
  if (a === 'move') {
    const o = currentOrder(l), i = o.indexOf(id), j = i + (+el.dataset.d);
    if (i < 0 || j < 0 || j >= o.length) return;
    [o[i], o[j]] = [o[j], o[i]]; l.order = o; commit(l);
    const b = document.querySelector(`[data-lay="move"][data-id="${CSS.escape(id)}"][data-d="${el.dataset.d}"]`); if (b) b.focus();
  }
}

document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('button[data-lay]'); if (b) act(b); });
document.addEventListener('change', e => {
  const s = e.target; if (!s.matches || !s.matches('select[data-lay]')) return;
  const l = load(ctx.acc, ctx.view);
  if (s.dataset.lay === 'add' && s.value) { l.hidden = l.hidden.filter(x => x !== s.value); commit(l); }
  if (s.dataset.lay === 'preset' && s.value) {
    const p = PRESETS[s.value], ids = lastEntries.map(x => x.id);
    const tagsOf = id => (window.VRLayout.tagsOf && window.VRLayout.tagsOf(id)) || [];
    const keep = id => p.only ? p.only.includes(id) : (p.tags || []).some(t => tagsOf(id).includes(t)) || /kpis$/.test(id);
    const hide = ids.filter(id => !keep(id));
    commit({order: [], hidden: hide.length === ids.length ? [] : hide, span: {}});
  }
});

// drag and drop (edit mode only): drop a widget before the one it lands on
document.addEventListener('dragstart', e => {
  const m = e.target.closest && e.target.closest('.mod[data-lay-id]'); if (!m || !editing) return;
  dragId = m.dataset.layId; e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', dragId); } catch (x) { /* ignore */ }
  m.classList.add('lay-drag');
});
document.addEventListener('dragend', () => { dragId = null; document.querySelectorAll('.lay-drag,.lay-over').forEach(n => n.classList.remove('lay-drag', 'lay-over')); });
document.addEventListener('dragover', e => {
  const m = e.target.closest && e.target.closest('.mod[data-lay-id]'); if (!m || !dragId) return;
  e.preventDefault(); document.querySelectorAll('.lay-over').forEach(n => n.classList.remove('lay-over')); m.classList.add('lay-over');
});
document.addEventListener('drop', e => {
  const m = e.target.closest && e.target.closest('.mod[data-lay-id]'); if (!m || !dragId) return;
  e.preventDefault();
  const to = m.dataset.layId; if (to === dragId) return;
  const l = load(ctx.acc, ctx.view), o = currentOrder(l).filter(x => x !== dragId);
  o.splice(o.indexOf(to), 0, dragId); l.order = o; commit(l);
});

window.VRLayout = {
  supports: v => PAGES.has(v), arrange, attrs, chrome, toolbar, isEditing: () => editing,
  init: o => { rerender = o.rerender; window.VRLayout.tagsOf = o.tagsOf; },
};
})();
