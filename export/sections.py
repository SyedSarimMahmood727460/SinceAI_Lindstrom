"""Export content shared by the PPTX, PDF and Excel builders.

Everything here reads the ReviewModel only; every metric value goes through
`export.format` (fmt_value / fmt_number / fmt_range), so the three formats and the dashboard
show the same text. Builders decide layout; this module decides wording.
"""
from __future__ import annotations

import re

from export.format import fmt_compact, fmt_compact_range, fmt_compact_value, fmt_number, fmt_range, fmt_value

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
                  ("co2_saving_kg", "CO₂e saved"), ("water_saving_l", "Water saved")]


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
                     f"{fmt_compact(abs(net.value), net.unit)} {word} than doing it yourself.")
    return {"rows": rows, "notes": notes, "statement": g.get("statement") or g.get("narrative_line") or "",
            "columns": [c for _, c in GROWTH_COLUMNS]}


# ---------------------------------------------------------------- the meeting steps (design §3, §7)
# The step exports follow the guided meeting: every figure here is compact (€1.96M, 255 t CO₂e)
# and read from the ReviewModel (KPIs, dto, story facts, growth); nothing is computed here.

NO_DATA = "no data for this filter"
NO_STANDOUT = "No site stands out — performance is even across sites."
APPENDIX = "Appendix · "
STEP_TITLES = {1: "1 · What you got", 2: "2 · Vs doing it yourself", 3: "3 · Where to improve",
               4: "4 · Grow together", 5: "5 · Agree next steps"}


def _present(m) -> bool:
    return m is not None and m.value is not None


def _tile(label: str, m, context: str = "") -> dict:
    """A hero tile: label, compact value, compact range line and a context line.
    A missing metric reads '—' with 'no data for this filter' (never an empty tile)."""
    if not _present(m):
        return {"label": label, "value": fmt_compact(None, ""), "range": "", "context": NO_DATA}
    return {"label": label, "value": fmt_compact_value(m), "range": fmt_compact_range(m),
            "context": context}


def _bare_range(m) -> str:
    return fmt_compact_range(m).removeprefix("range ") or "–"


def has_growth(review) -> bool:
    """Step 4 exists only when growth has totals (design §3)."""
    g = review.growth
    return bool(g and g.get("totals") and g.get("levers"))


def _step1(review, cards):
    k = {x.metric_id: x for x in _customer_kpis(review)}
    hours = (review.dto.convenience or {}).get("staff_hours_freed") if review.dto else None
    on_time = k.get("on_time_rate")
    on_time_line = f"On-time delivery {fmt_compact_value(on_time)}" if _present(on_time) else ""
    tiles = [_tile("Water saved", k.get("water_saving_l")), _tile("CO₂e avoided", k.get("co2_saving_kg"))]
    if _present(hours):
        tiles.append(_tile("Staff hours freed", hours, on_time_line))
    else:  # never an empty tile: on-time delivery takes the third place
        tiles.append(_tile("On-time delivery", on_time))
    card = cards.get("value_delivered") or {}
    return {"n": 1, "title": STEP_TITLES[1],
            "message": f"What {review.meta.node.name} got from Lindström in {review.meta.period}",
            "tiles": tiles, "statement": card.get("statement", ""), "relatable": card.get("relatable") or "",
            "what_to_say": card.get("what_to_say", "")}


def per_period(period: str) -> str:
    """'per year' for a full-year review ('2025'), else 'in 2025-Q3': a quarter is not a year."""
    return "per year" if re.fullmatch(r"\d{4}", str(period)) else f"in {period}"


def _net_tile(net, per: str = "per year") -> dict:
    """The net (do-it-yourself total minus the contract) in plain words: a saving with Lindström,
    or an extra cost when the headline is negative (then the figures are shown as positive)."""
    saving = net.value >= 0
    sign = 1 if saving else -1
    r = net.range
    rng = ""
    if r is not None and r.low is not None and r.high is not None:
        lo, hi = sorted((sign * r.low, sign * r.high))
        a, b = fmt_compact(lo, net.unit), fmt_compact(hi, net.unit)
        rng = "" if a == b else f"range {a} – {b}"
    crosses = bool(rng) and min(r.low, r.high) < 0 < max(r.low, r.high)
    return {"label": "Saving with Lindström" if saving else "Extra cost with Lindström",
            "value": fmt_compact(sign * net.value, net.unit), "range": rng,
            "context": f"{per} · depends on the assumptions" if crosses else per}


def _step2(review, cards):
    d = review.dto
    card = cards.get("vs_diy") or {}
    per = per_period(review.meta.period)
    step = {"n": 2, "title": STEP_TITLES[2], "statement": card.get("statement", ""),
            "what_to_say": card.get("what_to_say", ""), "tiles": [], "lines": [], "bars": [], "notes": [],
            "bars_title": "", "lines_header": per[0].upper() + per[1:]}
    if d is None or not _present(d.diy_total):
        return {**step, "message": "No do-it-yourself comparison for this filter"}
    net = d.net if _present(d.net) else None
    contract = d.contract_price if _present(d.contract_price) else None
    if net is not None:
        from insights.story import signed_about  # the story's honest wording when the range crosses zero
        text = signed_about(net, "less", "more", " with Lindström than doing it yourself")
        step["message"] = text[0].upper() + text[1:]
        step["tiles"].append(_net_tile(net, per))
    else:
        step["message"] = f"Doing it yourself would cost about {fmt_compact_value(d.diy_total)} {per}"
    step["tiles"].append(_tile("Doing it yourself would cost", d.diy_total, per))
    hours = (d.convenience or {}).get("staff_hours_freed")
    if _present(hours):
        step["tiles"].append(_tile("Staff hours freed", hours, "of your staff's time"))
    step["lines"] = [[ln.label if ln.in_total else f"{ln.label} ({NOT_IN_TOTAL})",
                      fmt_compact_value(ln.diy), _bare_range(ln.diy)]
                     for ln in d.lines if _present(ln.diy)]
    step["lines"].append(["Do-it-yourself total", fmt_compact_value(d.diy_total), _bare_range(d.diy_total)])
    if contract is not None:
        step["lines"].append(["Lindström contract price", fmt_compact_value(contract), _bare_range(contract)])
        step["bars"].append(("Lindström contract", contract.value, fmt_compact_value(contract)))
    step["bars"].append(("Doing it yourself", d.diy_total.value, fmt_compact_value(d.diy_total)))
    step["bars_title"] = "Contract vs doing it yourself" if contract is not None else f"Doing it yourself, {per}"
    if d.missing_lines:
        labels = {x.id: x.label for x in d.lines}
        step["notes"].append("Partial total: no data for "
                             + ", ".join(labels.get(i, i) for i in d.missing_lines) + ".")
    if d.hygiene_note:
        step["notes"].append(d.hygiene_note)
    return step


def _step3(review, cards):
    card = cards.get("biggest_improvement")
    obs = [o for o in review.observations if o.rule_id not in ("R7", "R8")]
    facts = (card or {}).get("facts")
    tiles = []
    if facts:  # R4 or a fallback without a site pair: statement only, no tiles
        tiles = [{"label": facts["site_name"], "value": fmt_compact(facts["value"], facts["unit"]),
                  "range": "", "context": facts["metric_label"]},
                 {"label": "Typical site", "value": fmt_compact(facts["typical"], facts["unit"]),
                  "range": "", "context": "the middle of your sites"}]
    return {"n": 3, "title": STEP_TITLES[3], "message": card["statement"] if card else NO_STANDOUT,
            "tiles": tiles, "statement": "", "what_to_say": (card or {}).get("what_to_say", ""),
            "next": [(o.title.replace(" (relative)", ""), o.action) for o in obs[1:3]]}


def _compact_cells(src) -> list[str]:
    return [fmt_compact_value(src[k]) if _present(src.get(k)) else "–" for k, _ in GROWTH_COLUMNS]


def _step4(review, cards):
    g = review.growth
    t = g["totals"]
    gv = growth_view(review)
    return {"n": 4, "title": STEP_TITLES[4],
            "message": g.get("statement") or "What if more sites and services came to Lindström?",
            "tiles": [_tile("Cost avoided per year", t.get("diy_cost_avoided")),
                      _tile("CO₂e saved", t.get("co2_saving_kg")),
                      _tile("Staff hours freed", t.get("staff_hours_freed"))],
            "levers": [[lv["label"], *_compact_cells(lv)] for lv in g["levers"]] + [["Total", *_compact_cells(t)]],
            "columns": [c for _, c in GROWTH_COLUMNS], "notes": gv["notes"] if gv else [],
            "statement": "", "what_to_say": g.get("what_to_say") or ""}


def _step5(review, cards):
    kpi_unit = {k.metric_id: k.unit for k in review.kpis}
    actions = []
    for a in review.actions:
        v, target = a.get("value_2025"), a.get("target_2026")
        actions.append([a.get("text", ""), a.get("owner", ""),
                        fmt_compact(v, kpi_unit.get(a.get("kpi_metric_id"), "")) if v is not None else "–",
                        str(target) if target not in (None, "") else "to agree"])
    card = cards.get("whats_next") or {}
    return {"n": 5, "title": STEP_TITLES[5], "message": "Agree the next steps", "tiles": [],
            "points": list(review.narrative.discussion_points), "actions": actions, "statement": "",
            "what_to_say": card.get("what_to_say")
            or "Agree an owner and a date for each step before the meeting ends."}


def meeting_steps(review) -> list[dict]:
    """The guided meeting in order: steps 1-3, step 4 only when growth has totals, then step 5.
    Each step: n, title ('1 · What you got'), message, tiles [{label, value, range, context}],
    statement, what_to_say, plus step content (lines/bars/notes, next, levers/notes, points/actions)."""
    cards = {c["id"]: c for c in review.story}
    steps = [_step1(review, cards), _step2(review, cards), _step3(review, cards)]
    if has_growth(review):
        steps.append(_step4(review, cards))
    return steps + [_step5(review, cards)]


def step_figures(step: dict) -> str:
    """One line of the step's hero figures (the Excel Meeting sheet)."""
    return "; ".join(f"{t['label']}: {t['value']}" + (f" ({t['range']})" if t["range"] else "")
                     for t in step["tiles"])
