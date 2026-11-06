"""Template narrative: the no-LLM fallback. Real numbers come only from the ReviewModel."""
from __future__ import annotations

from api.review_model import ReviewModel
from config.loader import load_yaml
from insights.discussion import discussion_points
from model.contracts import Narrative

# Display scaling: kg -> tonnes, l -> m3, kWh -> MWh.
_SCALED = {"kgCO2e": (1000.0, "t CO₂e"), "l": (1000.0, "m³"), "kWh": (1000.0, "MWh"),
           "kg": (1000.0, "t")}


def wording_rules() -> dict:
    return load_yaml("wording_rules.yaml")


def fmt_value(v: float | None, unit: str) -> str:
    if v is None:
        return "n/a"
    if unit in ("ratio", "%"):
        return f"{v * 100:.1f}%" if unit == "ratio" else f"{v:.1f}%"
    if unit in _SCALED:
        div, label = _SCALED[unit]
        return f"{v / div:,.0f} {label}"
    if unit in ("count", "persons", "pieces", "replacements"):
        return f"{v:,.0f}"
    return f"{v:,.1f} {unit}".strip()


def placeholder_values(review: ReviewModel) -> dict[str, str]:
    """Every KPI as `<metric_id>.base|low|high`, plus names and observation titles."""
    vals: dict[str, str] = {}
    for k in review.kpis:
        if not k.customer_facing:  # internal metrics are never offered to the LLM
            continue
        base = k.range.base if k.range and k.range.base is not None else k.value
        vals[f"{k.metric_id}.base"] = fmt_value(base, k.unit)
        vals[f"{k.metric_id}.value"] = fmt_value(k.value, k.unit)  # the selected sensitivity
        if k.range is not None:
            vals[f"{k.metric_id}.low"] = fmt_value(k.range.low, k.unit)
            vals[f"{k.metric_id}.high"] = fmt_value(k.range.high, k.unit)
    for mid in ("active_wearers", "sites", "on_time_rate", "repairs", "water_saving_l",
                "co2_saving_kg"):
        vals.setdefault(f"{mid}.base", "n/a")
        vals.setdefault(f"{mid}.value", "n/a")
        vals.setdefault(f"{mid}.low", "n/a")
        vals.setdefault(f"{mid}.high", "n/a")
    vals["account.name"] = review.meta.node.name
    vals["baseline.name"] = review.meta.baseline["name"]
    vals["period"] = review.meta.period
    vals["countries"] = ", ".join(review.meta.node.countries)
    for o in review.observations:
        vals[f"obs:{o.id}"] = o.title
    levers = [o for o in review.observations if o.rule_id not in ("R7", "R8")]
    for i, o in enumerate(levers[:2], 1):
        vals[f"lever.{i}"] = o.title.split(":")[0]
    return vals


def _has(review: ReviewModel, metric_id: str, part: str = "value") -> bool:
    k = next((k for k in review.kpis if k.metric_id == metric_id), None)
    if k is None:
        return False
    if part == "value":
        return k.value is not None
    return k.range is not None and getattr(k.range, part) is not None


def template_narrative(review: ReviewModel) -> Narrative:
    """Executive summary from placeholders; a clause whose metric has no value is omitted."""
    from ai.guard import render
    vals = placeholder_values(review)
    has = lambda mid, part="value": _has(review, mid, part)  # noqa: E731
    lead = "In {{period}}, Lindström"
    if has("active_wearers"):
        lead += " served {{active_wearers.value}} wearers"
        lead += " across {{sites.value}} sites" if has("sites") else ""
    elif has("sites"):
        lead += " served {{sites.value}} sites"
    else:
        lead += " delivered service to {{account.name}}"
    lead += " in {{countries}}." if vals["countries"] else "."
    facts = []
    if has("on_time_rate"):
        facts.append("{{on_time_rate.value}} of service cycles were on time")
    if has("repairs"):
        facts.append("{{repairs.value}} garment repairs kept textiles in use")
    p1 = lead + (" " + ", and ".join(facts) + "." if facts else "")
    saved = []
    if has("water_saving_l"):
        saved.append("{{water_saving_l.value}} of water")
    if has("co2_saving_kg"):
        co2 = "{{co2_saving_kg.value}}"
        if has("co2_saving_kg", "low") and has("co2_saving_kg", "high"):
            co2 += " ({{co2_saving_kg.low}} to {{co2_saving_kg.high}})"
        saved.append(co2)
    p2 = ("Compared with {{baseline.name}}, the circular service is estimated to have avoided "
          + " and ".join(saved) + " in washing and logistics (estimate).") \
        if saved else ""
    levers = [k for k in ("lever.1", "lever.2") if k in vals]
    p3 = (("The biggest improvement lever for next year is " if len(levers) == 1
           else "The biggest improvement levers for next year are ")
          + " and ".join("{{%s}}" % k for k in levers) + ".") if levers else ""
    text = "\n\n".join(p for p in (p1, p2, p3) if p)
    return Narrative(exec_summary=render(text, vals),
                     discussion_points=discussion_points(review.observations),
                     generated_by="template")
