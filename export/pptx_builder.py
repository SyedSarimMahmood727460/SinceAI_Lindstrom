"""PPTX export in meeting order (design §7): cover, the five meeting steps (compact numbers,
export.sections.meeting_steps), then the appendix. Reads only the ReviewModel; every number goes
through export.format."""
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
    APPENDIX, PRIORITY_LABEL, SITE_METRIC, WARN, _customer_kpis, _focus_text, _no_data, _no_internal,
    _top_kpis, meeting_steps, site_groups, tag)

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


def _fit_row_h(n_rows, top, bottom, preferred):
    return min(preferred, (bottom - top) / n_rows)


# ---------------------------------------------------------------- the meeting steps (design §7)
# Layout bands (inches): lead message 1.12–1.95 · hero tiles 2.0–3.5 · supporting content
# 3.65–6.85 · footer from 6.98. The account manager's "What to say" goes to the speaker notes
# only: the deck is customer-facing, coaching never prints on a slide.
LEAD_Y, TILE_Y, TILE_H, BODY_Y, BODY_END = 1.12, 2.0, 1.5, 3.65, 6.85


def _lead(slide, text):
    _, tf = _textbox(slide, MARGIN, Inches(LEAD_Y), CONTENT_W, Inches(TILE_Y - LEAD_Y - 0.05))
    _run(tf.paragraphs[0], clip(text, 340), 15, False, NAVY)  # up to 3 lines


def _tiles(slide, tiles):
    """2–3 hero tiles: label, big compact number, range line, context line."""
    gap = Inches(0.2)
    w = int((CONTENT_W - gap * (len(tiles) - 1)) / len(tiles))
    for i, t in enumerate(tiles):
        x = MARGIN + (w + gap) * i
        _rect(slide, x, Inches(TILE_Y), w, Inches(TILE_H), LIGHT)
        _rect(slide, x, Inches(TILE_Y), Inches(0.07), Inches(TILE_H), RED)
        _, tf = _textbox(slide, x + Inches(0.15), Inches(TILE_Y + 0.08), w - Inches(0.25), Inches(TILE_H - 0.16))
        _run(tf.paragraphs[0], clip(t["label"], 48), 13, True, GREY)
        _run(tf.add_paragraph(), t["value"], 30, True, NAVY)
        if t["range"]:
            _run(tf.add_paragraph(), t["range"], 12, False, GREY)
        if t["context"]:
            _run(tf.add_paragraph(), clip(t["context"], 60), 11, False, GREY, italic=True)


def _step_frame(prs, review, n, step, lead=True):
    """Title, lead message and tiles; What to say goes to the notes. Returns (slide, top of the body band)."""
    slide = _new_slide(prs, step["title"], review, n)
    if lead:
        _lead(slide, step["message"])
    top = LEAD_Y if not lead else TILE_Y
    if step["tiles"]:
        _tiles(slide, step["tiles"])
        top = BODY_Y
    _notes(slide, step["what_to_say"])
    return slide, top


def _step1(prs, review, n, step):
    slide, top = _step_frame(prs, review, n, step)
    _, tf = _textbox(slide, MARGIN, Inches(top), CONTENT_W, Inches(BODY_END - top))
    _run(tf.paragraphs[0], clip(step["statement"] or "No data for this filter", 320), 14)
    if step["relatable"]:
        p = tf.add_paragraph()
        p.space_before = Pt(6)
        _run(p, clip(step["relatable"], 220), 12, False, GREY, italic=True)


def _step2(prs, review, n, step):
    slide, top = _step_frame(prs, review, n, step)
    if not step["lines"]:
        _no_data_note(slide, "No comparison for this filter")
        return
    rows = step["lines"]
    wrapped = sum(1 for r in rows if len(r[0]) > 52)  # long labels wrap to a second line
    row_h = _fit_row_h(len(rows) + 1 + wrapped * 0.6, top, BODY_END, 0.36)
    _table(slide, MARGIN, Inches(top), [5.0, 1.2, 1.8], rows, [step["lines_header"], "Value", "Range (low – high)"],
           size=11, row_h=row_h, header_size=11)
    x, w = Inches(8.75), Inches(3.98)
    _, tf = _textbox(slide, x, Inches(top), w, Inches(0.35))
    _run(tf.paragraphs[0], step["bars_title"], 12, True, RED)
    biggest = max(v for _, v, _ in step["bars"]) or 1
    y = top + 0.4
    for label, value, text in step["bars"]:
        _, tf = _textbox(slide, x, Inches(y), w, Inches(0.28))
        _run(tf.paragraphs[0], f"{label}: ", 11, True, NAVY)
        _run(tf.paragraphs[0], text, 11)
        _rect(slide, x + Inches(0.05), Inches(y + 0.3), int((w - Inches(0.1)) * max(value, 0) / biggest),
              Inches(0.25), NAVY if label.startswith("Lindström") else GREY)
        y += 0.68
    if step["notes"]:
        _, tf = _textbox(slide, x, Inches(y), w, Inches(BODY_END - y))
        _bullets(tf, [clip(t, 150) for t in step["notes"][:2]], 10, GREY, 2, bullet="", first=True)


def _step3(prs, review, n, step):
    slide, top = _step_frame(prs, review, n, step)
    if not step["next"]:
        return
    _, tf = _textbox(slide, MARGIN, Inches(top), CONTENT_W, Inches(BODY_END - top))
    _heading(tf, "Also worth a look", 15, first=True)
    for title, action in step["next"]:
        p = tf.add_paragraph()
        p.space_before = Pt(4)
        _run(p, clip(title, 90), 14, True, NAVY)
        p = tf.add_paragraph()
        _run(p, "Next step: ", 12, True, RED)
        _run(p, clip(action, 140), 12, False, INK, italic=True)


def _step4(prs, review, n, step):
    slide, top = _step_frame(prs, review, n, step)
    rows = [[clip(r[0], 40), *r[1:]] for r in step["levers"]]
    row_h = _fit_row_h(len(rows) + 1, top, BODY_END - 0.75, 0.36)
    _table(slide, MARGIN, Inches(top), [3.73, 2.1, 2.1, 2.1, 2.1], rows, ["Lever", *step["columns"]],
           size=11, row_h=row_h, header_size=11)
    y = top + row_h * (len(rows) + 1) + 0.08
    std = "All figures are estimates per year, scaled from your own current data; ranges run from low to high."
    _, tf = _textbox(slide, MARGIN, Inches(y), CONTENT_W, Inches(BODY_END - y))
    _bullets(tf, [clip(t, 170) for t in step["notes"][:2]] + [std], 10, GREY, 1, bullet="", first=True)


def _step5(prs, review, n, step):
    slide, top = _step_frame(prs, review, n, step, lead=False)
    _, tf = _textbox(slide, MARGIN, Inches(top), Inches(5.5), Inches(BODY_END - top))
    _heading(tf, "Points we suggest discussing", first=True)
    pts = [clip(p, 120) for p in step["points"][:5]]
    _bullets(tf, pts or ["No discussion points for this filter."], 14, space=8, first=False)
    _, tf = _textbox(slide, Inches(6.4), Inches(top), Inches(6.35), Inches(0.4))
    _heading(tf, "Proposed actions", first=True)
    rows = [[clip(a[0], 75), clip(a[1], 22), a[2], clip(a[3], 14)] for a in step["actions"][:6]]
    if rows:
        row_h = _fit_row_h(len(rows) + 1, top + 0.5, BODY_END, 0.7)
        _table(slide, Inches(6.4), Inches(top + 0.5), [2.7, 1.3, 1.25, 1.1], rows,
               ["Action", "Owner", review.meta.period, "2026 target"], size=12, row_h=row_h, header_size=12)


STEP_SLIDES = {1: _step1, 2: _step2, 3: _step3, 4: _step4, 5: _step5}


def _kpi_slide(prs, review, n):
    slide = _new_slide(prs, APPENDIX + "Value KPIs", review, n,
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
    slide = _new_slide(prs, APPENDIX + "Footprint vs baseline", review, n,
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
    slide = _new_slide(prs, APPENDIX + "Site highlights", review, n,
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


def _method_slide(prs, review, n):
    slide = _new_slide(prs, APPENDIX + "Methodology & assumptions", review, n)
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
    slide = _new_slide(prs, APPENDIX + "Data readiness", review, n)
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
    n = 2
    for step in meeting_steps(review):
        STEP_SLIDES[step["n"]](prs, review, n, step)
        n += 1
    for fn in (_kpi_slide, _footprint_slide, _site_slide, _method_slide, _appendix_slide):
        fn(prs, review, n)
        n += 1
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path
