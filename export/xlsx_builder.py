"""Excel export: the ReviewModel as a workbook. Numbers are numbers (not strings), units sit in
the headers or a unit column, and a Display column carries the same text the dashboard shows
(export.format). What the review contains is what is written, so a customer-audience review
yields a customer-safe workbook."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from export.format import fmt_range, fmt_value
from export.sections import _focus_text, _no_internal, NET_PROMPT, NOT_IN_TOTAL, SOURCE_LABEL, diy_view, growth_view

HEAD_FILL = PatternFill("solid", fgColor="1B2A4A")
HEAD_FONT = Font(bold=True, color="FFFFFF")
NUM = "#,##0.00"
WRAP = Alignment(wrap_text=True, vertical="top")


def _sheet(wb, title, header, rows, widths, disclaimer):
    ws = wb.create_sheet(title)
    ws.append(header)
    for c in ws[1]:
        c.fill, c.font, c.alignment = HEAD_FILL, HEAD_FONT, Alignment(wrap_text=True, vertical="center")
    for r in rows:
        ws.append(r)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = WRAP
            if isinstance(c.value, float):
                c.number_format = NUM
    ws.freeze_panes = "A2"
    ws.oddFooter.center.text = disclaimer
    ws.oddFooter.center.size = 8
    return ws


def _ends(m):
    r = m.range if m is not None else None
    return (r.low, r.base, r.high) if r is not None else (None, None, None)


def _metric_row(label, m, *extra):
    lo, base, hi = _ends(m)
    return [label, *extra, m.value, lo, base, hi, m.unit, fmt_value(m), m.method_status.value,
            "yes" if m.dq_warning else ""]


def build_xlsx(review, out_path: Path, audience: str = "kam") -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    m = review.meta
    gv = growth_view(review)
    disc = m.disclaimer

    # Summary
    rows = [["Disclaimer", disc],
            ["Audience", "Customer" if audience == "customer"
             else "Account manager (internal — may include internal metrics)"],
            ["Customer", m.node.name], ["Industry", m.node.industry or ""],
            ["Period", m.period], ["Comparison baseline", m.baseline.get("name", "")],
            ["Sensitivity", m.sensitivity], ["Focus", _focus_text(review)],
            ["Service line", m.service_line or ", ".join(m.service_lines) or ""],
            ["Run id", m.run_id], ["Generated at", m.generated_at.isoformat(timespec="seconds")],
            ["Assumption set version", m.assumption_set_version],
            ["Sheets", "Story, KPIs, Sites, Observations, Actions, DIY comparison, "
                       + ("Growth, " if gv else "") + "Inputs, Assumptions, Data quality"]]
    ws = _sheet(wb, "Summary", ["Item", "Value"], rows, [28, 90], disc)
    ws["A2"].font = ws["B2"].font = Font(bold=True, color="D71920")

    # Story
    _sheet(wb, "Story", ["Topic", "Statement", "Relatable comparison", "What to say"],
           [[c["title"], c["statement"], c.get("relatable") or "", c.get("what_to_say") or ""]
            for c in review.story], [30, 80, 50, 60], disc)

    # KPIs
    _sheet(wb, "KPIs", ["metric_id", "Label", "Unit", "Value", "Low", "Base", "High", "Display",
                        "Method status", "Provenance", "Confidence", "Data-quality warning",
                        "Assumptions", "Formula"],
           [[k.metric_id, k.label, k.unit, k.value, *_ends(k), fmt_value(k) + (f" ({fmt_range(k)})" if fmt_range(k) else ""),
             k.method_status.value, k.provenance.value, k.confidence, "yes" if k.dq_warning else "",
             ", ".join(k.assumptions), k.formula_text] for k in review.kpis],
           [30, 38, 12, 14, 14, 14, 14, 40, 14, 14, 12, 12, 18, 60], disc)

    # Sites: one row per site, one column per metric ("label (unit)")
    cols: dict[str, tuple[str, str]] = {}
    for s in review.sites:
        for mid, mr in s.metrics.items():
            cols.setdefault(mid, (mr.label, mr.unit))
    _sheet(wb, "Sites", ["Site", "Country", "City", "Laundry", "Site type",
                         *[f"{lab} ({unit})" for lab, unit in cols.values()]],
           [[s.name, s.country or "", s.city or "", s.laundry_id or "", s.site_type or "",
             *[(s.metrics[mid].value if mid in s.metrics else None) for mid in cols]] for s in review.sites],
           [34, 10, 16, 10, 14] + [20] * len(cols), disc)

    # Observations / Actions
    _sheet(wb, "Observations", ["Title", "Finding", "Next step", "Method status", "Confidence",
                                "Data-quality warning", "Node"],
           [[o.title, o.finding, o.action, o.method_status.value, o.confidence,
             "yes" if o.dq_warning else "", o.node_id] for o in review.observations],
           [40, 80, 60, 14, 12, 12, 12], disc)
    kpi_unit = {k.metric_id: k.unit for k in review.kpis}
    _sheet(wb, "Actions", ["Action", "Owner", "KPI", "Unit", f"Value {m.period}", "2026 target"],
           [[a.get("text", ""), a.get("owner", ""), a.get("kpi_metric_id") or "",
             kpi_unit.get(a.get("kpi_metric_id"), ""), a.get("value_2025"), a.get("target_2026") or "to agree"]
            for a in review.actions], [60, 26, 28, 12, 16, 14], disc)

    # DIY comparison
    d = review.dto
    diy_rows: list[list] = []
    if d is not None:
        for ln in d.lines:
            diy_rows.append(_metric_row(ln.label, ln.diy, "no" if not ln.in_total else "yes"))
        diy_rows.append(_metric_row("Do-it-yourself total", d.diy_total, ""))
        if d.contract_price is not None and d.contract_price.value is not None:
            diy_rows.append(_metric_row("Lindström contract price", d.contract_price, ""))
        if d.net is not None and d.net.value is not None:
            diy_rows.append(_metric_row("Net: do-it-yourself total minus contract price", d.net, ""))
        else:
            diy_rows.append([NET_PROMPT, "", None, None, None, None, "", "", "", ""])
        hours = (d.convenience or {}).get("staff_hours_freed")
        if hours is not None and hours.value is not None:
            diy_rows.append(_metric_row("Staff hours freed by the service", hours, ""))
        for note in diy_view(review)["notes"] + ([d.hygiene_note] if d.hygiene_note else []):
            diy_rows.append([note] + [""] * 9)
        for ln in d.lines:
            if not ln.in_total:
                diy_rows.append([f"{ln.label}: {NOT_IN_TOTAL}."] + [""] * 9)
    _sheet(wb, "DIY comparison", ["Item (per year)", "In total", "Value", "Low", "Base", "High", "Unit",
                                  "Display", "Method status", "Data-quality warning"],
           diy_rows, [52, 10, 16, 16, 16, 16, 10, 18, 14, 12], disc)

    # Growth
    if gv:
        g = review.growth
        grows = []
        for lv in [*g["levers"], {"label": "Total", **(g.get("totals") or {})}]:
            for key in ("diy_cost_avoided", "staff_hours_freed", "co2_saving_kg", "water_saving_l", "net"):
                mr = lv.get(key)
                if mr is not None and mr.value is not None:
                    lo, base, hi = _ends(mr)
                    grows.append([lv["label"], mr.label.split(" — ")[0], mr.value, lo, base, hi, mr.unit,
                                  fmt_value(mr), mr.method_status.value])
        for note in [gv["statement"], *gv["notes"]]:
            grows.append([note] + [""] * 8)
        _sheet(wb, "Growth", ["Lever", "Measure (per year)", "Value", "Low", "Base", "High", "Unit",
                              "Display", "Method status"], grows, [40, 36, 16, 16, 16, 16, 10, 20, 14], disc)

    # Inputs
    inputs = [[i["label"], i["key"], i["value"], i.get("low"), i.get("high"), i.get("unit", ""),
               SOURCE_LABEL.get(i.get("source"), str(i.get("source"))), i.get("entered_at") or "",
               i.get("assumption_id") or ""] for i in (d.inputs if d else []) if i.get("value") is not None]
    if gv:
        gi = review.growth.get("inputs", {})
        for key, label, unit in (("extra_sites", "Extra sites", "sites"), ("extra_wearers", "Extra employees", "people"),
                                 ("expansion_price_eur_per_site_year", "Expansion price", "EUR/site/year")):
            if gi.get(key):
                inputs.append([label, key, gi[key], None, None, unit, SOURCE_LABEL["kam"],
                               gi.get("entered_at") or "", ""])
        if gi.get("extra_service_lines"):
            inputs.append(["Extra service lines", "extra_service_lines", ", ".join(gi["extra_service_lines"]),
                           None, None, "", SOURCE_LABEL["kam"], gi.get("entered_at") or "", ""])
    _sheet(wb, "Inputs", ["Input", "Key", "Value", "Low", "High", "Unit", "Source", "Entered", "Assumption"],
           inputs, [44, 34, 16, 12, 12, 14, 28, 12, 12], disc)

    # Assumptions
    _sheet(wb, "Assumptions", ["ID", "Assumption", "Value or rule", "Confidence", "Treatment"],
           [[a["id"], a["assumption"], a["value_or_rule"], a.get("confidence", ""), a.get("treatment", "")]
            for a in review.methodology.get("assumptions_used", [])], [8, 50, 70, 12, 14], disc)

    # Data quality
    dq = review.data_quality
    dq_rows = [["Warning", w.get("check_id"), w.get("entity_id"), w.get("entity_name") or "", w.get("month") or "",
                w.get("message") or w.get("detail", "")] for w in dq.get("warnings", [])]
    dq_rows.append(["Quarantined rows", "", "", "", "", dq.get("quarantine_count", 0)])
    dq_rows += [["Gap", g["status"], "", g["field"], "", f"{g['future_source']}: {_no_internal(g['note'])}"]
                for g in dq.get("gaps", [])]
    _sheet(wb, "Data quality", ["Type", "Check / status", "Entity", "Name / field", "Month", "Detail"],
           dq_rows, [16, 16, 14, 34, 12, 100], disc)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
