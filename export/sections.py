"""Export content shared by the PPTX, PDF and Excel builders.

Everything here reads the ReviewModel only; every metric value goes through
`export.format` (fmt_value / fmt_number / fmt_range), so the three formats and the dashboard
show the same text. Builders decide layout; this module decides wording.
"""
from __future__ import annotations

from export.format import fmt_number, fmt_range, fmt_value

WARN = "⚠"
PRIORITY_LABEL = {"water": "Water", "emissions": "Emissions", "cost": "Cost & utilisation",
                  "circularity": "Circularity", "service": "Service quality"}
# Site highlight metric per first priority; the bool says "lowest first" is the interesting end.
SITE_METRIC = {"water": ("washed_kg_per_wearer", False), "emissions": ("co2_saving_kg", False),
               "cost": ("utilisation", True), "circularity": ("repairs_per_100w", False),
               "service": ("service_requests_per_100w", False)}

NET_PROMPT = "Enter the contract price to see the net comparison"
NOT_IN_TOTAL = "explanatory, not in total"
SOURCE_LABEL = {"default": "Default", "kam": "Entered by account manager"}


def tag(metric) -> str:
    return f"[{metric.method_status.value}]" + (f" {WARN}" if metric.dq_warning else "")


def _no_internal(text: str) -> str:
    """Drop clauses that mention internal-only metrics (the deck is customer-facing)."""
    parts = [t for t in str(text).replace(";", ".").split(".") if t.strip() and "idle stock" not in t.lower()]
    parts = [t.strip()[0].upper() + t.strip()[1:] for t in parts]
    return ". ".join(parts) + ("." if parts else "")


def _customer_kpis(review):
    return [k for k in review.kpis if k.customer_facing]


def _no_data(review) -> bool:
    return not any(k.value is not None for k in _customer_kpis(review))


def _focus_text(review) -> str:
    labels = [PRIORITY_LABEL.get(p, p.title()) for p in review.context.active_priorities[:3]]
    return ", ".join(labels) if labels else "General overview"


def _top_kpis(review, n=8):
    """First n headline KPIs (the review already orders headline-first, then by priority)."""
    return [k for k in _customer_kpis(review)
            if k.display.get("headline") and k.value is not None][:n]


def status_text(m) -> str:
    """'ESTIMATED' plus a warning sign when the underlying data raised a quality warning."""
    return m.method_status.value + (" ⚠" if m.dq_warning else "")


def _flat(m) -> bool:
    r = m.range
    return r is not None and r.low == r.base == r.high


def _range_text(m) -> str:
    """Range text, or a dash when there is no range or low = base = high (a fixed number)."""
    return "–" if _flat(m) else (fmt_range(m) or "–")


def fmt_input(value, unit: str) -> str:
    """An input the account manager can type: keep its own precision (2.5, 0.05, 900,000)."""
    if value is None:
        return "–"
    num = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{num} {unit}".strip()


def input_range(inp: dict) -> str:
    lo, hi, v = inp.get("low"), inp.get("high"), inp.get("value")
    if lo is None or hi is None or lo == hi == v:
        return "–"
    return f"{fmt_input(lo, '')} – {fmt_input(hi, inp.get('unit', ''))}"


def site_groups(review):
    """(metric label, focus priority, [(title, [(site, metric)])], number of sites with data)."""
    pri = review.context.active_priorities[0] if review.context.active_priorities else "water"
    mid, low_first = SITE_METRIC.get(pri, SITE_METRIC["water"])
    entries = [(s, s.metrics[mid]) for s in review.sites
               if mid in s.metrics and s.metrics[mid].customer_facing and s.metrics[mid].value is not None]
    label = entries[0][1].label if entries else mid
    entries.sort(key=lambda e: e[1].value, reverse=True)
    top = entries[:5]
    bottom = [e for e in entries[::-1][:5] if e not in top]
    groups = [("Highest 5", top), ("Lowest 5", bottom)]
    if low_first:
        groups.reverse()
    return label, pri, groups, len(entries)


# ---------------------------------------------------------------- service vs do-it-yourself

def diy_view(review) -> dict | None:
    """Rows for the comparison: [label, value, range, status] plus notes and the inputs used.
    None when the review has no comparison."""
    d = review.dto
    if d is None:
        return None
    rows, labels = [], {}
    for ln in d.lines:
        m = ln.diy
        labels[ln.id] = ln.label
        name = ln.label if ln.in_total else f"{ln.label} ({NOT_IN_TOTAL})"
        rows.append([name, fmt_value(m), _range_text(m), status_text(m)])
    t = d.diy_total
    rows.append(["Do-it-yourself total", fmt_value(t), _range_text(t), status_text(t)])
    notes: list[str] = []
    if d.missing_lines:
        names = ", ".join(labels.get(i, i) for i in d.missing_lines)
        notes.append(f"Partial total: no data for {names}.")
    if d.contract_price is not None and d.contract_price.value is not None:
        c = d.contract_price
        rows.append(["Lindström contract price", fmt_value(c), _range_text(c), status_text(c)])
    if d.net is not None and d.net.value is not None:
        n = d.net
        rows.append(["Net: do-it-yourself total minus contract price", fmt_value(n), _range_text(n),
                     status_text(n)])
        word = "more" if n.value >= 0 else "less"
        notes.append(f"Doing it yourself would cost {fmt_number(abs(n.value), n.unit)} {word} "
                     "than the Lindström service.")
    else:
        notes.append(NET_PROMPT + ".")
    hours = (d.convenience or {}).get("staff_hours_freed")
    hours_row = None
    if hours is not None and hours.value is not None:
        hours_row = ["Your staff hours freed by the service", fmt_value(hours), _range_text(hours),
                     status_text(hours)]
    inputs = [{"label": i["label"], "value": fmt_input(i["value"], i.get("unit", "")),
               "range": input_range(i), "source": SOURCE_LABEL.get(i.get("source"), str(i.get("source")))}
              for i in d.inputs if i.get("value") is not None]
    return {"rows": rows, "notes": notes, "hours_row": hours_row, "inputs": inputs,
            "hygiene": d.hygiene_note, "baseline": d.baseline}


# ---------------------------------------------------------------- growth

GROWTH_COLUMNS = [("diy_cost_avoided", "Cost avoided per year"), ("staff_hours_freed", "Staff hours freed"),
                  ("co2_saving_kg", "CO2e saved"), ("water_saving_l", "Water saved")]


def growth_view(review) -> dict | None:
    """Lever table: [lever label, (value, range) per GROWTH_COLUMNS...]; None without growth."""
    g = review.growth
    if not g or not g.get("levers"):  # nothing to size (e.g. only already-used service lines)
        return None

    def cells(src):
        return [(fmt_value(src[k]), "" if _flat(src[k]) else fmt_range(src[k])) if src.get(k) is not None and src[k].value is not None
                else ("–", "") for k, _ in GROWTH_COLUMNS]

    rows = [[lv["label"], *cells(lv)] for lv in g["levers"]]
    totals = g.get("totals") or {}
    if totals:
        rows.append(["Total", *cells(totals)])
    notes = list(g.get("notes") or [])
    for s in g.get("skipped_lines") or []:
        notes.append(f"Skipped {s['id']}: {s['reason']}.")
    if g.get("partial"):
        notes.append("Based on partial data: some do-it-yourself cost lines have no data.")
    net = totals.get("net")
    if net is not None and net.value is not None:
        word = "less" if net.value >= 0 else "more"
        notes.append(f"Including the Lindström expansion price, the service would cost "
                     f"{fmt_number(abs(net.value), net.unit)} {word} than doing it yourself.")
    return {"rows": rows, "notes": notes, "statement": g.get("statement") or g.get("narrative_line") or "",
            "columns": [c for _, c in GROWTH_COLUMNS]}
