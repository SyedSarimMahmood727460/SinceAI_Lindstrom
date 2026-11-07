"""Customer story: plain-language cards for the landing page and the head of every export.

Statements are templates filled by code from ReviewModel values (formatted by the shared
`export.format`); nothing here computes a new number except the illustrative
metric / factor comparison, which is always prefixed "≈" and labelled illustrative.
A card whose data is missing is skipped.
"""
from __future__ import annotations

import math
from typing import Any

from config.loader import load_yaml
from export.format import _scale, fmt_value

ILLUSTRATIVE = "illustrative comparison"
CARD_ORDER = ["value_delivered", "vs_diy", "biggest_improvement", "growth", "whats_next"]


def _present(m) -> bool:
    return m is not None and m.value is not None


def _about(m, absolute: bool = False) -> str:
    """'about X (between A and B)' for a ranged metric, 'about X' otherwise."""
    sign = abs if absolute else (lambda x: x)
    value = sign(m.value)
    x = fmt_value(m.model_copy(update={"value": value}))
    r = m.range
    if r is None or r.low is None or r.high is None:
        return f"about {x}"
    _, u, dec, div = _scale(value, m.unit)
    lo, hi = sorted((sign(r.low) / div, sign(r.high) / div))
    if f"{lo:,.{dec}f}" == f"{hi:,.{dec}f}":
        return f"about {x}"
    suffix = "%" if u == "%" else (f" {u}" if u else "")
    return f"about {x} (between {lo:,.{dec}f} and {hi:,.{dec}f}{suffix})"


def round_sig(x: float, sig: int = 2) -> float:
    if x == 0:
        return 0.0
    return round(x, sig - 1 - math.floor(math.log10(abs(x))))


def _num(x: float) -> str:
    return f"{x:,.0f}" if x >= 100 else f"{x:g}"


def relatable_text(kpis: dict[str, Any], metric_ids: list[str]) -> str | None:
    """'≈ n ... (illustrative comparison)' for the factors of the given metrics; None when no
    factor applies or the value is not positive."""
    parts = []
    for f in load_yaml("relatable.yaml"):
        m = kpis.get(f["metric"])
        if f["metric"] not in metric_ids or not _present(m) or m.value <= 0:
            continue
        n = round_sig(m.value / f["factor"])
        label = f["label_one"] if n == 1 and f.get("label_one") else f["label_template"].format(n=_num(n))
        parts.append(f"≈ {label}")
    if not parts:
        return None
    return " and ".join(parts) + f" ({ILLUSTRATIVE})"


def _value_delivered(review, k):
    bits, refs = [], []
    for mid, tmpl in (("water_saving_l", "{} of water"), ("co2_saving_kg", "{} of greenhouse gas")):
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
        word = "more" if d.net.value >= 0 else "less"
        statement += (f", against a Lindström contract of {fmt_value(d.contract_price)}: "
                      f"{_about(d.net, absolute=True)} {word} than the service.")
    else:
        statement += "."
    hrs = d.convenience.get("staff_hours_freed")
    if _present(hrs) and hrs.value > 0:
        refs.append("dto_staff_hours_freed")
        statement += f" It also frees {_about(hrs)} of your staff's time."
    return {"id": "vs_diy", "title": "Service versus doing it yourself",
            "statement": statement, "relatable": None,
            "what_to_say": "The inputs behind this comparison are shown on the page; "
                           "check that they match your own prices.",
            "detail_view": "vs_diy", "value_refs": refs}


def _biggest(review, k):
    # R7 (value headline) and R8 (data caveat) are not improvements
    obs = [o for o in review.observations if o.rule_id not in ("R7", "R8")]
    if not obs:
        return None
    o = obs[0]
    return {"id": "biggest_improvement", "title": "The biggest opportunity",
            "statement": o.finding, "relatable": None, "what_to_say": o.action,
            "detail_view": "overview_observations",
            "value_refs": list(dict.fromkeys(e[0] for e in o.evidence if e[0] in k))}


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
