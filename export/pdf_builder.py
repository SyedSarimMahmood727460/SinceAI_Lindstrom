"""PDF export in meeting order, the same sections as the deck, rendered with reportlab (pure Python).

Reads only the ReviewModel; numbers go through export.format (via export.sections and the
shared helpers of the PPTX builder). Body text uses matplotlib's bundled DejaVuSans so
non-ASCII names (Ł, ó, ä, ö, å, õ) render; the built-in Helvetica is never used for text.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from export import charts
from export.format import fmt_range, fmt_value
from export.sections import (APPENDIX, PRIORITY_LABEL, _customer_kpis, _focus_text, _no_data, _no_internal,
                             _top_kpis, diy_view, meeting_steps, site_groups, tag)

NAVY = colors.HexColor("#1B2A4A")
RED = colors.HexColor("#D71920")
GREY = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F1F3F7")
INK = colors.HexColor("#1F2937")
PAGE = landscape(A4)
MARGIN = 15 * mm
FONT, FONT_B, FONT_I = "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans-Oblique"
_registered = False


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for name, file in ((FONT, "DejaVuSans.ttf"), (FONT_B, "DejaVuSans-Bold.ttf"),
                       (FONT_I, "DejaVuSans-Oblique.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(ttf / file)))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_B, italic=FONT_I, boldItalic=FONT_B)
    _registered = True


def _styles() -> dict[str, ParagraphStyle]:
    base = dict(fontName=FONT, textColor=INK, alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", fontSize=10, leading=14, spaceAfter=4, **base),
        "small": ParagraphStyle("small", fontSize=8.5, leading=11.5, spaceAfter=2,
                                **{**base, "textColor": GREY}),
        "italic": ParagraphStyle("italic", fontSize=9, leading=12, spaceAfter=4,
                                 **{**base, "fontName": FONT_I, "textColor": GREY}),
        "h1": ParagraphStyle("h1", fontSize=20, leading=24, spaceAfter=4,
                             **{**base, "fontName": FONT_B, "textColor": NAVY}),
        "sub": ParagraphStyle("sub", fontSize=10, leading=13, spaceAfter=8,
                              **{**base, "fontName": FONT_I, "textColor": GREY}),
        "h2": ParagraphStyle("h2", fontSize=12, leading=15, spaceBefore=8, spaceAfter=3,
                             **{**base, "fontName": FONT_B, "textColor": RED}),
        "cell": ParagraphStyle("cell", fontSize=9, leading=11.5, **base),
        "cellb": ParagraphStyle("cellb", fontSize=9, leading=11.5, **{**base, "fontName": FONT_B}),
        "head": ParagraphStyle("head", fontSize=9, leading=11.5,
                               **{**base, "fontName": FONT_B, "textColor": colors.white}),
        "tile_l": ParagraphStyle("tile_l", fontSize=9, leading=12, **{**base, "fontName": FONT_B, "textColor": GREY}),
        "tile_v": ParagraphStyle("tile_v", fontSize=22, leading=27, **{**base, "fontName": FONT_B, "textColor": NAVY}),
        "cover_t": ParagraphStyle("cover_t", fontSize=34, leading=40, **{**base, "fontName": FONT_B,
                                                                         "textColor": colors.white}),
        "cover_s": ParagraphStyle("cover_s", fontSize=18, leading=24, **{**base, "textColor": colors.white}),
        "cover_i": ParagraphStyle("cover_i", fontSize=12, leading=18, **{**base, "textColor": colors.white}),
    }


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text)), style)


class _Doc(BaseDocTemplate):
    def __init__(self, path, review):
        super().__init__(str(path), pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=14 * mm, bottomMargin=16 * mm,
                         title=f"Value review {review.meta.node.name} {review.meta.period}",
                         author="Lindström value review (prototype)")
        self.review = review
        frame = Frame(MARGIN, 16 * mm, PAGE[0] - 2 * MARGIN, PAGE[1] - 30 * mm, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="cover", frames=[frame], onPage=self._cover_page),
                               PageTemplate(id="page", frames=[frame], onPage=self._page)])

    def _footer(self, canvas, color):
        canvas.setFont(FONT, 8)
        canvas.setFillColor(color)
        canvas.drawString(MARGIN, 9 * mm, f"{self.review.meta.disclaimer} · run {self.review.meta.run_id}")
        canvas.drawRightString(PAGE[0] - MARGIN, 9 * mm, str(canvas.getPageNumber()))

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE[0], PAGE[1], stroke=0, fill=1)
        canvas.setFillColor(RED)
        canvas.rect(MARGIN, PAGE[1] - 128 * mm, 3 * mm, 62 * mm, stroke=0, fill=1)
        canvas.setFont(FONT_B, 11)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, PAGE[1] - 20 * mm, "LINDSTRÖM · CUSTOMER VALUE & SUSTAINABILITY REVIEW")
        canvas.setFillColor(RED)
        canvas.drawRightString(PAGE[0] - MARGIN, PAGE[1] - 20 * mm, "SYNTHETIC DATA")
        self._footer(canvas, colors.white)
        canvas.restoreState()

    def _page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RED)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN, PAGE[1] - 11 * mm, PAGE[0] - MARGIN, PAGE[1] - 11 * mm)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(GREY)
        canvas.drawRightString(PAGE[0] - MARGIN, PAGE[1] - 9 * mm,
                               f"{self.review.meta.node.name} · {self.review.meta.period}")
        canvas.setStrokeColor(GREY)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 13 * mm, PAGE[0] - MARGIN, 13 * mm)
        self._footer(canvas, GREY)
        canvas.restoreState()


def _table(rows, widths_mm, st, header=None, bold_last=False):
    """A zebra table of wrapping Paragraph cells; repeats its header when it spans pages."""
    data = []
    if header:
        data.append([_p(h, st["head"]) for h in header])
    for r in rows:
        data.append([_p(c, st["cell"]) for c in r])
    t = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB"))]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    for i in range(1 if header else 0, len(data)):
        if (i - (1 if header else 0)) % 2 == 1:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    t.setStyle(TableStyle(style))
    return t


def _section(title, st, subtitle=None, first=False):
    out = [] if first else [PageBreak()]
    out.append(_p(title, st["h1"]))
    out.append(_p(subtitle, st["sub"]) if subtitle else Spacer(1, 4 * mm))
    return out


def _bullets(items, st, style="body"):
    return [Paragraph("• " + escape(str(t)), st[style]) for t in items]


def _image(path, width_mm):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(str(path)).getSize()
    return Image(str(path), width=width_mm * mm, height=width_mm * mm * h / w)


# ---------------------------------------------------------------- sections

def _cover(review, st):
    m = review.meta
    info = [f"Period: {m.period}", f"Comparison baseline: {m.baseline.get('name', '')}",
            f"Sensitivity: {m.sensitivity}", f"Focus: {_focus_text(review)}"]
    if m.node.industry:
        info.insert(0, f"Industry: {m.node.industry}")
    if m.service_line:
        info.append(f"Service line: {m.service_line}")
    return ([Spacer(1, 38 * mm), _p(m.node.name, st["cover_t"]), Spacer(1, 3 * mm),
             _p(f"Value review {m.period}", st["cover_s"]), Spacer(1, 10 * mm)]
            + [_p(t, st["cover_i"]) for t in info])


# ---------------------------------------------------------------- the meeting steps (design §7)
# Customer-facing: the account manager's "What to say" is never printed (it is in the deck notes
# and the Excel Meeting sheet).

def _tiles(tiles, st):
    """The hero row: 2–3 tiles with label, big compact number, range line and context line."""
    width = (PAGE[0] - 2 * MARGIN) / len(tiles)
    cells = []
    for t in tiles:
        cell = [_p(t["label"], st["tile_l"]), _p(t["value"], st["tile_v"])]
        if t["range"]:
            cell.append(_p(t["range"], st["small"]))
        if t["context"]:
            cell.append(_p(t["context"], st["italic"]))
        cells.append(cell)
    tbl = Table([cells], colWidths=[width] * len(tiles))
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
             ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEAFTER", (0, 0), (-2, 0), 4, colors.white)]
    style += [("LINEBEFORE", (i, 0), (i, 0), 2.5, RED) for i in range(len(tiles))]
    tbl.setStyle(TableStyle(style))
    return [tbl, Spacer(1, 4 * mm)]


def _step_head(review, st, step, message=True):
    out = _section(step["title"], st, step["message"] if message else None)
    return out + (_tiles(step["tiles"], st) if step["tiles"] else [])


def _step1(review, st, step):
    out = _step_head(review, st, step)
    out.append(_p(step["statement"] or "No data for this filter", st["body"]))
    if step["relatable"]:
        out.append(_p(step["relatable"], st["italic"]))
    return out


def _bars(bars, st):
    """Horizontal bars: Lindström contract vs the do-it-yourself total (lengths from the values)."""
    from reportlab.graphics.shapes import Drawing, Rect, String
    w, bar_h, label_h, gap = 85 * mm, 6 * mm, 5 * mm, 4 * mm
    biggest = max(v for _, v, _ in bars) or 1
    step = bar_h + label_h + gap
    d = Drawing(w, len(bars) * step)
    for i, (label, value, text) in enumerate(bars):
        y = (len(bars) - 1 - i) * step
        d.add(Rect(0, y, max(value, 0) / biggest * w, bar_h, strokeColor=None,
                   fillColor=NAVY if label.startswith("Lindström") else GREY))
        d.add(String(0, y + bar_h + 1.5 * mm, f"{label}: {text}", fontName=FONT, fontSize=9, fillColor=INK))
    return d


def _step2(review, st, step):
    out = _step_head(review, st, step)
    if not step["lines"]:
        return out + [_p("No comparison for this filter", st["h2"])]
    table = _table(step["lines"], [95, 30, 45], st, ["Per year", "Value", "Range (low – high)"])
    side = [_p(step["bars_title"], st["h2"]), _bars(step["bars"], st)]
    side += [_p(t, st["small"]) for t in step["notes"]]
    t = Table([[table, side]], colWidths=[176 * mm, 91 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    out += [t]
    v = diy_view(review)
    if v and v["inputs"]:
        out.append(_p("The numbers behind this comparison", st["h2"]))
        out.append(_table([[i["label"], i["value"], i["range"], i["source"]] for i in v["inputs"]],
                          [100, 40, 55, 60], st, ["Input", "Value", "Range (low – high)", "Source"]))
    return out


def _step3(review, st, step):
    out = _step_head(review, st, step)
    if step["next"]:
        out.append(_p("Also worth a look", st["h2"]))
        for title, action in step["next"]:
            out.append(KeepTogether([_p(title, st["cellb"]),
                                     Paragraph(f"<b>Next step:</b> <i>{escape(action)}</i>", st["body"])]))
    return out


def _step4(review, st, step):
    out = _step_head(review, st, step)
    out.append(_table(step["levers"], [75, 48, 48, 48, 48], st, ["Lever", *step["columns"]]))
    out.append(Spacer(1, 2 * mm))
    out += _bullets(step["notes"] + ["All figures are estimates per year, scaled from your own current data; "
                                     "ranges run from low to high."], st, "small")
    return out


def _step5(review, st, step):
    out = _step_head(review, st, step, message=False)
    out.append(_p("Points we suggest discussing", st["h2"]))
    out += _bullets(step["points"][:8] or ["No discussion points for this filter."], st)
    if step["actions"]:
        out.append(_p("Proposed actions", st["h2"]))
        out.append(_table(step["actions"], [110, 55, 40, 40], st,
                          ["Action", "Owner", review.meta.period, "2026 target"]))
    return out


STEP_SECTIONS = {1: _step1, 2: _step2, 3: _step3, 4: _step4, 5: _step5}


def _kpis(review, st):
    out = _section(APPENDIX + "Value KPIs", st, "Each figure carries its method status; ranges are shown where "
                   "the value is an estimate.")
    if _no_data(review):
        return out + [_p("No data for this filter", st["h2"])]
    kpis = _top_kpis(review, n=len(review.kpis))
    rows = [[k.label, fmt_value(k), fmt_range(k) or "–", tag(k)] for k in kpis]
    out.append(_table(rows, [100, 45, 70, 40], st, ["KPI", "Value", "Range (low – high)", "Status"]))
    out.append(Spacer(1, 3 * mm))
    out.append(_p("⚠ = data-quality warning on the underlying data (see appendix). MEASURED, CALCULATED, "
                  "ALLOCATED, ESTIMATED run from strongest to weakest evidence.", st["small"]))
    return out


def _footprint(review, st):
    out = _section(APPENDIX + "Footprint vs baseline", st, "Lindström allocated footprint as % of baseline: "
                   f"{review.meta.baseline.get('name', '')}")
    if _no_data(review):
        return out + [_p("No data for this filter", st["h2"])]
    by_id = {k.metric_id: k for k in _customer_kpis(review)}
    side = []
    for mid, label in charts.FOOTPRINT_IDS:
        k = by_id.get(mid)
        if k is None:
            continue
        side += [_p(f"{label} footprint", st["h2"]), _p(f"{fmt_value(k)} of baseline {tag(k)}", st["cellb"])]
        if fmt_range(k):
            side.append(_p(f"Range: {fmt_range(k)}", st["small"]))
    sav = [by_id[m] for m in ("water_saving_l", "energy_saving_kwh", "co2_saving_kg") if m in by_id]
    if sav:
        side.append(_p("Estimated saving vs baseline", st["h2"]))
        for k in sav:
            side.append(_p(f"{fmt_value(k)} ({fmt_range(k)}) {tag(k)}" if fmt_range(k)
                           else f"{fmt_value(k)} {tag(k)}", st["cell"]))
    t = Table([[_image(charts.footprint_pct_chart(review), 150), side]],
              colWidths=[158 * mm, 100 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return out + [t]


def _sites(review, st):
    label, pri, groups, count = site_groups(review)
    out = _section(APPENDIX + "Site highlights", st, f"Ranked by {label.lower()} (focus: "
                   f"{PRIORITY_LABEL.get(pri, pri)}) · {count} sites with data")
    if not count:
        return out + [_p("No data for this filter", st["h2"])]
    cells = []
    for title, grp in groups:
        rows = [[s.name, fmt_value(m), m.method_status.value.title()] for s, m in grp]
        cells.append([_p(title, st["h2"]), _table(rows, [60, 35, 30], st, ["Site", label, "Status"])])
    t = Table([cells], colWidths=[132 * mm, 132 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return out + [t, Spacer(1, 4 * mm),
                  _p("Differences between sites are a prompt for a conversation, not a judgement; "
                     "see observations for context.", st["small"])]


def _method(review, st):
    m = review.methodology
    out = _section(APPENDIX + "Methodology & assumptions", st)
    out += [_p("Boundary & method", st["h2"])] + _bullets(m.get("boundary", []), st)
    out += [_p("Limitations", st["h2"])] + _bullets(m.get("limitations", []), st)
    out.append(_p("Status legend", st["h2"]))
    out.append(_table([[s["status"], s["meaning"]] for s in m.get("status_legend", [])], [40, 225], st))
    rows = [[a["id"], a["assumption"], a["value_or_rule"], a.get("confidence", "")]
            for a in m.get("assumptions_used", [])]
    if rows:
        out.append(_p("Assumptions used", st["h2"]))
        out.append(_table(rows, [20, 85, 125, 35], st, ["ID", "Assumption", "Value or rule", "Confidence"]))
    return out


def _appendix(review, st):
    dq = review.data_quality
    out = _section(APPENDIX + "Data readiness", st)
    warnings = dq.get("warnings", [])
    out.append(_p(f"Data-quality warnings ({len(warnings)})", st["h2"]))
    groups: dict[tuple, list] = {}
    for w in warnings:
        groups.setdefault((w.get("check_id"), w.get("entity_id")), []).append(w)
    if not groups:
        out += _bullets(["None raised for this selection."], st)
    for (check, ent), ws in groups.items():
        w0 = ws[0]
        who = f"{w0['entity_name']} ({ent})" if w0.get("entity_name") else str(ent)
        out.append(_p(f"{check} · {who} · {len(ws)} month(s), e.g. {w0.get('month', '')}: "
                      f"{w0.get('message') or w0.get('detail', '')}", st["body"]))
    gaps = dq.get("gaps", [])
    if gaps:
        out.append(_p("Data gaps", st["h2"]))
        out.append(_table([[g["field"], g["future_source"], g["status"], _no_internal(g["note"])]
                           for g in gaps], [50, 75, 20, 120], st,
                          ["Field", "Future Lindström source", "Status", "Note"]))
    return out


def build_pdf(review, out_path: Path) -> Path:
    from reportlab.platypus import NextPageTemplate
    _register_fonts()
    st = _styles()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    story = [NextPageTemplate("page")] + _cover(review, st)
    for step in meeting_steps(review):
        story += STEP_SECTIONS[step["n"]](review, st, step)
    for fn in (_kpis, _footprint, _sites, _method, _appendix):
        story += fn(review, st)
    _Doc(out_path, review).build(story)
    return out_path
