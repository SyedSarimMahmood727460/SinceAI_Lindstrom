"""Customer story: plain-language cards for the landing page and the head of every export.

Statements are templates filled by code from ReviewModel values (formatted by the shared
`export.format`); nothing here computes a new number except the illustrative
metric / factor comparison, which is always prefixed "≈" and labelled illustrative.
A card whose data is missing is skipped.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

from config.loader import load_yaml
from export.format import _scale, fmt_compact, fmt_number

ILLUSTRATIVE = "illustrative comparison"
CARD_ORDER = ["value_delivered", "vs_diy", "biggest_improvement", "growth", "whats_next"]


def _present(m) -> bool:
    return m is not None and m.value is not None


COMPACT_UNITS = {"EUR", "l", "kgCO2e", "h"}


def _fmt(value: float, unit: str) -> str:
    """Compact meeting style for money, water, CO₂e and hours (€1.96M, 1,407 m³, 255 t CO₂e,
    1,152 h); other units as export.format."""
    return fmt_compact(value, unit) if unit in COMPACT_UNITS else fmt_number(value, unit)


def _about(m, absolute: bool = False) -> str:
    """'about X (between A and B)' for a ranged metric, 'about X' otherwise."""
    sign = abs if absolute else (lambda x: x)
    value = sign(m.value)
    x = _fmt(value, m.unit)
    r = m.range
    if r is None or r.low is None or r.high is None:
        return f"about {x}"
    if m.unit in COMPACT_UNITS:  # each end carries its own unit: "between €1.36M and €2.74M"
        lo, hi = sorted((sign(r.low), sign(r.high)))
        a, b = _fmt(lo, m.unit), _fmt(hi, m.unit)
        return f"about {x}" if a == b else f"about {x} (between {a} and {b})"
    _, u, dec, div = _scale(value, m.unit)
    lo, hi = sorted((sign(r.low) / div, sign(r.high) / div))
    if f"{lo:,.{dec}f}" == f"{hi:,.{dec}f}":
        return f"about {x}"
    suffix = "%" if u == "%" else (f" {u}" if u else "")
    return f"about {x} (between {lo:,.{dec}f} and {hi:,.{dec}f}{suffix})"


def signed_about(m, more: str, less: str, tail: str) -> str:
    """'about X {more|less}{tail}' for a signed amount (e.g. a net cost), worded honestly.

    The direction word follows the headline value. When the range stays on one side of zero
    the absolute range is appended as usual; when it crosses zero the sentence says so:
    'about X more than the service — but the range runs from A less to B more, so it
    depends on the assumptions'."""
    word = more if m.value >= 0 else less
    r = m.range
    if r is not None and r.low is not None and r.high is not None:
        lo, hi = min(r.low, r.high), max(r.low, r.high)
        if lo < 0 < hi:
            return (f"about {_fmt(abs(m.value), m.unit)} {word}{tail} — but the range runs "
                    f"from {_fmt(-lo, m.unit)} {less} to {_fmt(hi, m.unit)} {more}, "
                    "so it depends on the assumptions")
    return f"{_about(m, absolute=True)} {word}{tail}"


def round_sig(x: float, sig: int = 2) -> float:
    if x == 0:
        return 0.0
    return round(x, sig - 1 - math.floor(math.log10(abs(x))))


def _num(x: float) -> str:
    return f"{x:,.0f}" if x >= 100 else f"{x:g}"


def relatable_text(kpis: dict[str, Any], metric_ids: list[str]) -> str | None:
    """'≈ n ... (illustrative comparison)' for the factors of the given metrics; None when no
    factor applies, the value is not positive or the ratio is below 1."""
    parts = []
    for f in load_yaml("relatable.yaml"):
        m = kpis.get(f["metric"])
        if f["metric"] not in metric_ids or not _present(m) or m.value <= 0:
            continue
        ratio = m.value / f["factor"]
        if ratio < 1:  # "≈ 0.42 households" is not relatable
            continue
        n = round_sig(ratio)
        label = f["label_one"] if n == 1 and f.get("label_one") else f["label_template"].format(n=_num(n))
        parts.append(f"≈ {label}")
    if not parts:
        return None
    return " and ".join(parts) + f" ({ILLUSTRATIVE})"


def _value_delivered(review, k):
    bits, refs = [], []
    for mid, tmpl in (("water_saving_l", "{} of water"), ("co2_saving_kg", "{}")):
        m = k.get(mid)
        if _present(m) and m.value > 0:
            bits.append(tmpl.format(_about(m)))
            refs.append(mid)
    if not bits:
        return None
    base = review.meta.baseline["name"]
    statement = (f"Compared with {base[0].lower() + base[1:]}, the Lindström service saved "
                 f"{' and '.join(bits)} in {review.meta.period}.")
    return {"id": "value_delivered", "title": "What the service delivered",
            "statement": statement, "relatable": relatable_text(k, refs),
            "what_to_say": "These are estimates against an agreed baseline, shown with a range. "
                           "Ask whether the baseline matches how you would otherwise do this.",
            "detail_view": "footprint_savings", "value_refs": refs}


def _vs_diy(review, k):
    d = review.dto
    if d is None or not _present(d.diy_total):
        return None
    refs = ["dto_diy_total"]
    statement = f"Doing the same yourself would cost {_about(d.diy_total)} in {review.meta.period}"
    if d.contract_price is not None and _present(d.contract_price) and _present(d.net):
        refs += ["dto_contract_price", "dto_net"]
        statement += (f", against a Lindström contract of {_fmt(d.contract_price.value, d.contract_price.unit)}: "
                      f"{signed_about(d.net, 'more', 'less', ' than the service')}.")
    else:
        statement += "."
    if d.missing_lines:
        labels = {x.id: x.label.lower() for x in d.lines}
        statement = statement[:-1] + (" (partial — no data for: "
                                      + ", ".join(labels.get(i, i) for i in d.missing_lines) + ").")
    hrs = d.convenience.get("staff_hours_freed")
    if _present(hrs) and hrs.value > 0:
        refs.append("dto_staff_hours_freed")
        statement += f" It also frees {_about(hrs)} of your staff's time."
    return {"id": "vs_diy", "title": "Service versus doing it yourself",
            "statement": statement, "relatable": None,
            "what_to_say": "The inputs behind this comparison are shown on the page; "
                           "check that they match your own prices.",
            "detail_view": "vs_diy", "value_refs": refs}


# Plain-language templates per site rule: (metric, text with {name} {v} {med}, closing line,
# what to say). No z-scores or "peer" jargon reaches the customer.
def _pct(x):
    return f"{x:.0%}"


def _num1(x):
    return f"{x:,.0f}" if x >= 100 else f"{x:,.1f}".rstrip("0").rstrip(".")


SITE_STORY = {
    "R1": ("utilisation", "{name} uses {v} of its garments, less than your other sites "
           "(typically about {med}).", "Right-sizing the garment allocation there could cut cost.",
           "Shall we look at the garment allocation at {name} together?", _pct),
    "R2": ("service_requests_per_100w", "{name} makes {v} service requests per 100 wearers, "
           "more than your other sites (typically about {med}).",
           "Understanding what the requests are about could improve the service.",
           "Shall we go through what the requests at {name} are about?", _num1),
    "R3": ("on_time_rate", "At {name}, {v} of deliveries arrive on time, less than at your other "
           "sites (typically about {med}).",
           "Adjusting the route or delivery day could help.",
           "Would a different pickup window or delivery day suit {name}?", _pct),
    "R5": ("repairs_per_100w", "{name} needs {v} repairs per 100 wearers, more than your other "
           "sites (typically about {med}).",
           "Checking that the garments fit the work there could reduce repairs.",
           "Shall we check whether the garments at {name} suit the work?", _num1),
    "R6": ("washed_kg_per_wearer", "{name} washes {v} kg per wearer, more than your other "
           "sites (typically about {med} kg).",
           "Reviewing how often garments are changed there could cut cost and water.",
           "Shall we look at change frequency at {name} together? Hygiene needs come first.",
           _num1),
}


def _plain_site_story(review, o):
    spec = SITE_STORY.get(o.rule_id)
    if spec is None or not o.evidence:
        return None
    metric_id, node = o.evidence[0]
    metric, text, close, say, fmt = spec
    vals = {e.node_id: e.metrics[metric].value for e in review.sites
            if metric in e.metrics and e.metrics[metric].value is not None}
    site = next((e for e in review.sites if e.node_id == node), None)
    if site is None or node not in vals or len(vals) < 2:
        return None
    med = statistics.median(vals.values())
    name = site.name
    m = site.metrics[metric]
    facts = {"site_name": name, "metric_label": m.label, "value": vals[node], "typical": med,
             "unit": m.unit}
    return (text.format(name=name, v=fmt(vals[node]), med=fmt(med)) + " " + close,
            say.format(name=name), [metric_id], facts)


def _biggest(review, k):
    # R7 (value headline) and R8 (data caveat) are not improvements
    obs = [o for o in review.observations if o.rule_id not in ("R7", "R8")]
    if not obs:
        return None
    o = obs[0]
    plain = _plain_site_story(review, o)
    if plain is None:  # account-level rule (R4) or missing site data: a jargon-free fallback
        title = o.title.replace(" (relative)", "")
        statement = o.finding if o.rule_id == "R4" else title + "."
        plain = (statement, o.action, [], None)  # no site pair: no figure tiles
    statement, say, refs, facts = plain
    refs = refs or [e[0] for e in o.evidence if e[0] in k]
    return {"id": "biggest_improvement", "title": "Your biggest opportunity to improve",
            "statement": statement, "relatable": None, "what_to_say": say,
            "detail_view": "overview_observations", "value_refs": list(dict.fromkeys(refs)),
            # the site's figure vs the typical (median) site, for the meeting step-3 tiles
            "facts": facts}


def _growth(review, k):
    """ReviewModel.growth (metrics/growth.py): a dict or model with `statement`
    (or `summary`), optional `what_to_say` and `value_refs`."""
    g = getattr(review, "growth", None)
    if not g:
        return None
    get = (lambda a: g.get(a)) if isinstance(g, dict) else (lambda a: getattr(g, a, None))
    statement = get("statement") or get("summary")
    if not statement:
        return None
    return {"id": "growth", "title": "Growing together",
            "statement": str(statement), "relatable": None,
            "what_to_say": get("what_to_say") or "Ask which sites and services come next.",
            "detail_view": "growth", "value_refs": list(get("value_refs") or [])}


def _whats_next(review, k):
    acts = [a for a in review.actions if a.get("text")][:3]
    if not acts:
        return None
    return {"id": "whats_next", "title": "What happens next",
            "statement": "Suggested next steps: " + "; ".join(a["text"].rstrip(".") for a in acts) + ".",
            "relatable": None,
            "what_to_say": "Agree an owner and a date for each step before the meeting ends.",
            "detail_view": "steering_actions",
            "value_refs": list(dict.fromkeys(a["kpi_metric_id"] for a in acts
                                             if a.get("kpi_metric_id") in k))}


def build_story(review) -> list[dict]:
    k = {x.metric_id: x for x in review.kpis}
    makers = {"value_delivered": _value_delivered, "vs_diy": _vs_diy,
              "biggest_improvement": _biggest, "growth": _growth, "whats_next": _whats_next}
    cards = [makers[i](review, k) for i in CARD_ORDER]
    return [c for c in cards if c is not None]
