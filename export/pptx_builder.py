"""PPTX export (spec 13). Reads only the ReviewModel; every number goes through fmt_value / fmt_number."""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from export import charts
from export.format import _scale, fmt_number, fmt_range, fmt_value  # noqa: F401  (re-exported)
from export.sections import (  # noqa: F401  (PRIORITY_LABEL / SITE_METRIC re-exported)
    PRIORITY_LABEL, SITE_METRIC, WARN, _customer_kpis, _focus_text, _no_data, _no_internal, _top_kpis,
    diy_view, growth_view, site_groups, tag)

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
RED = RGBColor(0xD7, 0x19, 0x20)
GREY = RGBColor(0x6B, 0x72, 0x80)
LIGHT = RGBColor(0xF1, 0xF3, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1F, 0x29, 0x37)
FONT = "Calibri"

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
CONTENT_W = SLIDE_W - 2 * MARGIN

# ---------------------------------------------------------------- formatting

def clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    cut = text[: n - 1].rsplit(" ", 1)[0].rstrip(",;:. ")
    return cut + "…"


# ---------------------------------------------------------------- drawing helpers

def _run(p, text, size=14, bold=False, color=INK, italic=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.name, f.size, f.bold, f.italic = FONT, Pt(size), bold, italic
    f.color.rgb = color
    return r


def _textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    return tb, tf


def _rect(slide, x, y, w, h, color):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def _new_slide(prs, title, review, number, subtitle=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, SLIDE_W, Inches(0.95), NAVY)
    _rect(slide, 0, Inches(0.95), SLIDE_W, Inches(0.06), RED)
    _, tf = _textbox(slide, MARGIN, Inches(0.12), Inches(8.6), Inches(0.75), MSO_ANCHOR.MIDDLE)
    _run(tf.paragraphs[0], clip(title, 52), 28, True, WHITE)
    _, tf = _textbox(slide, Inches(9.3), Inches(0.12), Inches(3.45), Inches(0.75), MSO_ANCHOR.MIDDLE)
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], clip(f"{review.meta.node.name} · {review.meta.period}", 38), 13, False, WHITE)
    _footer(slide, review, number)
    if subtitle:
        _, tf = _textbox(slide, MARGIN, Inches(1.12), CONTENT_W, Inches(0.4))
        _run(tf.paragraphs[0], clip(subtitle, 150), 14, False, GREY, italic=True)
    return slide


def _footer(slide, review, number):
    _rect(slide, MARGIN, Inches(6.98), CONTENT_W, Emu(9525), GREY)
    _, tf = _textbox(slide, MARGIN, Inches(7.02), Inches(11), Inches(0.35))
    _run(tf.paragraphs[0], f"{review.meta.disclaimer} · run {review.meta.run_id}", 12, False, GREY)
    _, tf = _textbox(slide, Inches(11.7), Inches(7.02), Inches(1.05), Inches(0.35))
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], str(number), 12, False, GREY)


def _bullets(tf, items, size=14, color=INK, space=6, bullet="•", first=True):
    for it in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(space)
        _run(p, f"{bullet} {it}" if bullet else it, size, False, color)


def _heading(tf, text, size=16, first=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(4)
    _run(p, text, size, True, RED)


def _cell(cell, text, size, bold, color, fill):
    cell.fill.solid()
    cell.fill.fore_color.rgb = fill
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = cell.margin_right = Inches(0.08)
    cell.margin_top = cell.margin_bottom = Inches(0.03)
    tf = cell.text_frame
    tf.word_wrap = True
    first, *rest = str(text).split("\n")
    _run(tf.paragraphs[0], first, size, bold, color)
    for line in rest:  # later lines (e.g. a range) are smaller and grey
        _run(tf.add_paragraph(), line, max(size - 2, 9), False, GREY)


def _table(slide, x, y, widths, rows, header, size=13, row_h=0.42, header_size=None):
    n_rows = len(rows) + 1
    shape = slide.shapes.add_table(n_rows, len(widths), x, y, Inches(sum(widths)), Inches(row_h * n_rows))
    tbl = shape.table
    for i, w in enumerate(widths):
        tbl.columns[i].width = Inches(w)
    for r in range(n_rows):
        tbl.rows[r].height = Inches(row_h)
    for c, h in enumerate(header):
        _cell(tbl.cell(0, c), h, header_size or size, True, WHITE, NAVY)
    for r, row in enumerate(rows, start=1):
        fill = LIGHT if r % 2 == 0 else WHITE
        for c, val in enumerate(row):
            _cell(tbl.cell(r, c), val, size, False, INK, fill)
    return shape


# ---------------------------------------------------------------- content helpers

def _no_data_note(slide, text="No data for this filter"):
    _, tf = _textbox(slide, MARGIN, Inches(2.5), CONTENT_W, Inches(1))
    _run(tf.paragraphs[0], text, 24, True, GREY)


# ---------------------------------------------------------------- slides

def _cover(prs, review):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, SLIDE_W, SLIDE_H, NAVY)
    _rect(slide, MARGIN, Inches(1.9), Inches(0.12), Inches(2.5), RED)
    _, tf = _textbox(slide, MARGIN, Inches(0.6), Inches(8), Inches(0.5))
    _run(tf.paragraphs[0], "LINDSTRÖM  ·  CUSTOMER VALUE & SUSTAINABILITY REVIEW", 16, True, WHITE)
    _, tf = _textbox(slide, Inches(0.95), Inches(1.9), Inches(11.5), Inches(1.5), MSO_ANCHOR.MIDDLE)
    _run(tf.paragraphs[0], clip(review.meta.node.name, 45), 44, True, WHITE)
    _, tf = _textbox(slide, Inches(0.95), Inches(3.4), Inches(11.5), Inches(0.8))
    _run(tf.paragraphs[0], f"Value review {review.meta.period}", 28, False, WHITE)
    info = [f"Period: {review.meta.period}",
            f"Comparison baseline: {clip(review.meta.baseline.get('name', ''), 60)}",
            f"Sensitivity: {review.meta.sensitivity}",
            f"Focus: {_focus_text(review)}"]
    if review.meta.node.industry:
        info.insert(0, f"Industry: {review.meta.node.industry}")
    if review.meta.service_line:
        info.append(f"Service line: {review.meta.service_line}")
    _, tf = _textbox(slide, Inches(0.95), Inches(4.6), Inches(11.5), Inches(2.0))
    _bullets(tf, info, 16, WHITE, 4, bullet="")
    _, tf = _textbox(slide, Inches(8.4), Inches(0.55), Inches(4.35), Inches(0.6), MSO_ANCHOR.MIDDLE)
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], "SYNTHETIC DATA", 20, True, RED)
    _, tf = _textbox(slide, MARGIN, Inches(7.02), Inches(11), Inches(0.35))
    _run(tf.paragraphs[0], f"{review.meta.disclaimer} · run {review.meta.run_id}", 12, False, WHITE)


def _notes(slide, text):
    if text:
        slide.notes_slide.notes_text_frame.text = text


def _story_slide(prs, review, n):
    slide = _new_slide(prs, "Customer story", review, n,
                       "What the service delivers, in plain language; every figure is an estimate with a range.")
    cards = review.story
    if not cards:
        _no_data_note(slide, "No story for this filter")
        return
    _, tf = _textbox(slide, MARGIN, Inches(1.55), CONTENT_W, Inches(5.3))
    for i, c in enumerate(cards):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(0 if i == 0 else 8)
        _run(p, c["title"], 15, True, RED)
        _run(tf.add_paragraph(), c["statement"], 13)
        if c.get("relatable"):
            _run(tf.add_paragraph(), c["relatable"], 11, False, GREY, italic=True)
    _notes(slide, "\n".join(f"{c['title']}: {c['what_to_say']}" for c in cards if c.get("what_to_say")))


def _fit_row_h(n_rows, top, bottom, preferred):
    return min(preferred, (bottom - top) / n_rows)


def _diy_slide(prs, review, n):
    v = diy_view(review)
    slide = _new_slide(prs, "Service vs do-it-yourself", review, n,
                       "What you would spend doing it yourself instead of using the service "
                       f"(baseline: {clip(review.meta.baseline.get('name', ''), 60)}).")
    if v is None:
        _no_data_note(slide, "No comparison for this filter")
        return
    rows = [[r[0], r[1], r[2], r[3].title()] for r in v["rows"]]
    if v["hours_row"]:
        rows.append([*v["hours_row"][:3], "Estimated"])
    row_h = _fit_row_h(len(rows) + 1, 1.6, 5.3, 0.45)
    wrapped = sum(1 for r in rows if len(r[0]) > 38)  # long labels wrap to a second line
    _table(slide, MARGIN, Inches(1.6), [3.9, 1.4, 1.8, 1.2], rows,
           ["Item (per year)", "Value", "Range (low – high)", "Status"], size=12, row_h=row_h, header_size=12)
    y = 1.6 + row_h * (len(rows) + 1) + 0.2 * wrapped + 0.15
    _, tf = _textbox(slide, MARGIN, Inches(y), Inches(8.3), Inches(6.9 - y))
    _bullets(tf, [clip(t, 170) for t in v["notes"]] + ([clip(v["hygiene"], 170)] if v["hygiene"] else []),
             12, GREY, 3, bullet="", first=True)
    _, tf = _textbox(slide, Inches(9.2), Inches(1.6), Inches(3.55), Inches(5.3))
    _heading(tf, "Your numbers", 15, first=True)
    for i in v["inputs"]:
        p = tf.add_paragraph()
        p.space_after = Pt(2)
        _run(p, f"{clip(i['label'], 40)}: ", 11, True, NAVY)
        _run(p, f"{i['value']} ({'default' if i['source'] == 'Default' else 'account manager'})", 11)


def _growth_slide(prs, review, n):
    v = growth_view(review)
    slide = _new_slide(prs, "Growth opportunities", review, n)
    _, tf = _textbox(slide, MARGIN, Inches(1.12), CONTENT_W, Inches(0.8))
    _run(tf.paragraphs[0], v["statement"], 14, False, NAVY, italic=True)
    rows = [[clip(r[0], 38)] + [val + ("\n" + rng if rng else "") for val, rng in r[1:]]
            for r in v["rows"]]
    row_h = _fit_row_h(len(rows) + 1, 2.05, 5.7, 0.7)
    _table(slide, MARGIN, Inches(2.05), [2.9, 2.6, 2.2, 2.4, 2.03], rows, ["Lever", *v["columns"]],
           size=12, row_h=row_h, header_size=12)
    y = 2.05 + row_h * (len(rows) + 1) + 0.15
    _, tf = _textbox(slide, MARGIN, Inches(y), CONTENT_W, Inches(6.9 - y))
    std = "All figures are estimates per year, scaled from your own current data; ranges run from low to high."
    items = (v["notes"][:2] + [std]) if len(v["notes"]) > 2 else (v["notes"] + [std])  # at most 3 bullets
    _bullets(tf, [clip(t, 200) for t in items], 12, GREY, 3, bullet="", first=True)
    _notes(slide, review.growth.get("what_to_say") or "")


def _exec_summary(prs, review, n):
    slide = _new_slide(prs, "Executive summary", review, n)
    kpis = _customer_kpis(review)
    chart_ok = bool((review.circularity or {}).get("repairs_by_month")) and not _no_data(review)
    w = Inches(7.4) if chart_ok else CONTENT_W
    _, tf = _textbox(slide, MARGIN, Inches(1.25), w, Inches(5.6))
    summary = (review.narrative.exec_summary or "").strip()
    if _no_data(review):
        _heading(tf, "No data for this filter", first=True)
        _bullets(tf, ["There is no service activity for the selected customer, period and product filter.",
                      "Change the filter to see results."], 16, first=False)
    elif summary:
        _heading(tf, "Summary", first=True)
        _run(tf.add_paragraph(), clip(summary, 900), 15)
    else:
        _heading(tf, "Headline results", first=True)
        heads = [k for k in kpis if k.value is not None][:4]
        _bullets(tf, [clip(f"{k.label}: {fmt_value(k)} {tag(k)}", 90) for k in heads], 15, first=False)
        obs = review.observations[:3]
        if obs:
            _heading(tf, "What stands out")
            _bullets(tf, [clip(o.title, 90) for o in obs], 15, first=False)
    if chart_ok:
        slide.shapes.add_picture(str(charts.repairs_by_month_chart(review)), Inches(8.2), Inches(1.5),
                                 width=Inches(4.55))
        r = next((k for k in kpis if k.metric_id == "repairs"), None)
        if r is not None and r.value is not None:
            _, tf = _textbox(slide, Inches(8.2), Inches(4.4), Inches(4.55), Inches(0.6))
            _run(tf.paragraphs[0], f"Repairs completed: {fmt_value(r)} {tag(r)}", 13, True, NAVY)


def _kpi_slide(prs, review, n):
    slide = _new_slide(prs, "Value KPIs", review, n,
                       "Each figure carries its method status; ranges are shown where the value is an estimate.")
    if _no_data(review):
        _no_data_note(slide)
        return
    kpis = _top_kpis(review)
    rows = [[clip(k.label, 48), fmt_value(k), fmt_range(k) or "–", tag(k)] for k in kpis]
    _table(slide, MARGIN, Inches(1.6), [4.6, 2.4, 3.2, 1.93], rows,
           ["KPI", "Value", "Range (low – high)", "Status"], size=14, row_h=0.5)
    _, tf = _textbox(slide, MARGIN, Inches(6.3), CONTENT_W, Inches(0.6))
    _run(tf.paragraphs[0], f"{WARN} = data-quality warning on the underlying data (see appendix). "
         "MEASURED, CALCULATED, ALLOCATED, ESTIMATED run from strongest to weakest evidence.", 12, False, GREY)


def _footprint_slide(prs, review, n):
    slide = _new_slide(prs, "Footprint vs baseline", review, n,
                       "Lindström allocated footprint as % of baseline: "
                       f"{clip(review.meta.baseline.get('name', ''), 60)}")
    if _no_data(review):
        _no_data_note(slide)
        return
    by_id = {k.metric_id: k for k in _customer_kpis(review)}
    slide.shapes.add_picture(str(charts.footprint_pct_chart(review)), MARGIN, Inches(1.7), width=Inches(7.3))
    _, tf = _textbox(slide, Inches(8.2), Inches(1.7), Inches(4.55), Inches(5.1))
    first = True
    for mid, label in charts.FOOTPRINT_IDS:
        k = by_id.get(mid)
        if k is None:
            continue
        _heading(tf, f"{label} footprint", 15, first=first)
        first = False
        _run(tf.add_paragraph(), f"{fmt_value(k)} of baseline {tag(k)}", 14, True, NAVY)
        if fmt_range(k):
            _run(tf.add_paragraph(), f"Range: {fmt_range(k)}", 13, False, GREY)
    sav = [by_id[m] for m in ("water_saving_l", "energy_saving_kwh", "co2_saving_kg") if m in by_id]
    if sav:
        _heading(tf, "Estimated saving vs baseline", 15, first=first)
        for k in sav:
            line = f"{fmt_value(k)} ({fmt_range(k)}) {tag(k)}" if fmt_range(k) else f"{fmt_value(k)} {tag(k)}"
            _run(tf.add_paragraph(), line, 13)


def _site_slide(prs, review, n):
    label, pri, groups, count = site_groups(review)
    slide = _new_slide(prs, "Site highlights", review, n,
                       f"Ranked by {label.lower()} (focus: {PRIORITY_LABEL.get(pri, pri)}) · "
                       f"{count} sites with data")
    if not count:
        _no_data_note(slide)
        return
    for i, (title, grp) in enumerate(groups):
        x = MARGIN + Inches(6.35 * i)
        _, tf = _textbox(slide, x, Inches(1.65), Inches(6.0), Inches(0.4))
        _run(tf.paragraphs[0], title, 17, True, RED)
        rows = [[clip(s.name, 30), fmt_value(m), tag(m).replace("[", "").replace("]", "").title()]
                for s, m in grp]
        _table(slide, x, Inches(2.15), [2.9, 1.7, 1.4], rows, ["Site", clip(label, 18), "Status"],
               size=13, row_h=0.55, header_size=13)
    _, tf = _textbox(slide, MARGIN, Inches(6.2), CONTENT_W, Inches(0.6))
    _run(tf.paragraphs[0], "Differences between sites are a prompt for a conversation, not a judgement; "
         "see observations for context.", 12, False, GREY)


def _obs_slide(prs, review, n):
    slide = _new_slide(prs, "Observations & next steps", review, n)
    obs = review.observations[:5]
    _, tf = _textbox(slide, MARGIN, Inches(1.2), CONTENT_W, Inches(5.7))
    if not obs:
        _run(tf.paragraphs[0], "No observations for this filter", 18, True, GREY)
        return
    for i, o in enumerate(obs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(0 if i == 0 else 7)
        _run(p, clip(o.title, 85), 15, True, NAVY)
        _run(p, f"  [{o.method_status.value}]" + (f" {WARN}" if o.dq_warning else ""), 12, False, GREY)
        _run(tf.add_paragraph(), clip(o.finding, 230), 12)
        p = tf.add_paragraph()
        _run(p, "Next step: ", 12, True, RED)
        _run(p, clip(o.action, 130), 12, False, INK, italic=True)


def _discussion_slide(prs, review, n):
    slide = _new_slide(prs, "Discussion points & actions", review, n)
    _, tf = _textbox(slide, MARGIN, Inches(1.25), Inches(5.5), Inches(5.6))
    _heading(tf, "For the review meeting", first=True)
    pts = [clip(p, 120) for p in review.narrative.discussion_points[:5]]
    _bullets(tf, pts or ["No discussion points for this filter."], 14, space=8, first=False)
    kpi_unit = {k.metric_id: k.unit for k in review.kpis}
    rows = []
    for a in review.actions[:6]:
        v = a.get("value_2025")
        target = a.get("target_2026")
        rows.append([clip(a.get("text", ""), 75), clip(a.get("owner", ""), 22),
                     fmt_number(v, kpi_unit.get(a.get("kpi_metric_id"), "")) if v is not None else "–",
                     clip(str(target), 14) if target not in (None, "") else "to agree"])
    _, tf = _textbox(slide, Inches(6.4), Inches(1.25), Inches(6.35), Inches(0.4))
    _heading(tf, "Proposed actions", first=True)
    if rows:
        _table(slide, Inches(6.4), Inches(1.75), [2.7, 1.3, 1.25, 1.1], rows,
               ["Action", "Owner", review.meta.period, "2026 target"], size=12, row_h=0.7, header_size=12)


def _method_slide(prs, review, n):
    slide = _new_slide(prs, "Methodology, assumptions & limitations", review, n)
    m = review.methodology
    colw, gap = Inches(3.95), Inches(0.27)
    cols = [("Boundary & method", [clip(t, 150) for t in m.get("boundary", [])[:5]]),
            ("Limitations", [clip(t, 135) for t in m.get("limitations", [])[:6]])]
    for i, (head, items) in enumerate(cols):
        _, tf = _textbox(slide, MARGIN + (colw + gap) * i, Inches(1.2), colw, Inches(5.7))
        _heading(tf, head, first=True)
        _bullets(tf, items, 12, space=5, first=False)
    _, tf = _textbox(slide, MARGIN + (colw + gap) * 2, Inches(1.2), colw, Inches(5.7))
    _heading(tf, "Status legend", first=True)
    for s in m.get("status_legend", [])[:4]:
        p = tf.add_paragraph()
        p.space_after = Pt(3)
        _run(p, f"{s['status']}: ", 12, True, NAVY)
        _run(p, clip(s["meaning"], 80), 12)
    _heading(tf, "Key assumptions")
    for a in m.get("assumptions_used", [])[:5]:
        p = tf.add_paragraph()
        p.space_after = Pt(3)
        _run(p, f"{a['id']} ", 12, True, NAVY)
        _run(p, clip(f"{a['assumption']}: {a['value_or_rule']}", 85), 12)


def _appendix_slide(prs, review, n):
    slide = _new_slide(prs, "Appendix: data readiness", review, n)
    dq = review.data_quality
    warnings = dq.get("warnings", [])
    groups: dict[tuple, list] = {}
    for w in warnings:
        groups.setdefault((w.get("check_id"), w.get("entity_id")), []).append(w)
    _, tf = _textbox(slide, MARGIN, Inches(1.15), CONTENT_W, Inches(1.1))
    _heading(tf, f"Data-quality warnings ({len(warnings)})", 15, first=True)
    if not groups:
        _bullets(tf, ["None raised for this selection."], 12, space=2, first=False)
    for (check, ent), ws in list(groups.items())[:2]:
        w0 = ws[0]
        who = f"{w0['entity_name']} ({ent})" if w0.get("entity_name") else str(ent)
        what = w0.get("message") or w0.get("detail", "")
        _run(tf.add_paragraph(), clip(f"{check} · {who} · {len(ws)} month(s), e.g. {w0.get('month', '')}: {what}", 170), 12)
    if len(groups) > 2:
        _run(tf.add_paragraph(), f"+ {len(groups) - 2} more warning group(s)", 12, False, GREY)
    gaps = dq.get("gaps", [])[:7]
    rows = [[clip(g["field"], 36), clip(g["future_source"], 48), g["status"], clip(_no_internal(g["note"]), 80)] for g in gaps]
    if rows:
        _table(slide, MARGIN, Inches(2.3), [2.6, 3.4, 0.9, 5.23], rows,
               ["Field", "Future Lindström source", "Status", "Note"], size=12, row_h=0.46, header_size=12)


def build_pptx(review, out_path: Path) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    _cover(prs, review)
    steps = [_story_slide, _exec_summary, _kpi_slide, _footprint_slide, _diy_slide]
    if growth_view(review):
        steps.append(_growth_slide)
    steps += [_site_slide, _obs_slide, _discussion_slide, _method_slide, _appendix_slide]
    for i, fn in enumerate(steps, start=2):
        fn(prs, review, i)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
