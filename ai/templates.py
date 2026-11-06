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
        base = k.range.base if k.range and k.range.base is not None else k.value
        vals[f"{k.metric_id}.base"] = fmt_value(base, k.unit)
        if k.range is not None:
            vals[f"{k.metric_id}.low"] = fmt_value(k.range.low, k.unit)
            vals[f"{k.metric_id}.high"] = fmt_value(k.range.high, k.unit)
    for mid in ("active_wearers", "sites", "on_time_rate", "repairs", "water_saving_l",
                "co2_saving_kg"):
        vals.setdefault(f"{mid}.base", "n/a")
        vals.setdefault(f"{mid}.low", "n/a")
        vals.setdefault(f"{mid}.high", "n/a")
    vals["account.name"] = review.meta.node.name
    vals["baseline.name"] = review.meta.baseline["name"]
    vals["period"] = review.meta.period
    vals["countries"] = ", ".join(review.meta.node.countries)
    for o in review.observations:
        vals[f"obs:{o.id}"] = o.title
    for i, o in enumerate(review.observations[:2], 1):
        vals[f"lever.{i}"] = o.title.split(":")[0]
    return vals


def template_narrative(review: ReviewModel) -> Narrative:
    from ai.guard import render
    vals = placeholder_values(review)
    p1 = ("In {{period}}, Lindström served {{active_wearers.base}} wearers across {{sites.base}} "
          "sites in {{countries}}. {{on_time_rate.base}} of service cycles were on time, and "
          "{{repairs.base}} garment repairs kept textiles in use.")
    p2 = ("Compared with {{baseline.name}}, the circular service is estimated to have avoided "
          "{{water_saving_l.base}} of water and {{co2_saving_kg.base}} "
          "({{co2_saving_kg.low}} to {{co2_saving_kg.high}}) in washing and logistics, "
          "vs {{baseline.name}} (estimate).")
    levers = [k for k in ("lever.1", "lever.2") if k in vals]
    p3 = ("The biggest improvement levers for next year are "
          + " and ".join("{{%s}}" % k for k in levers) + ".") if levers else ""
    text = "\n\n".join(p for p in (p1, p2, p3) if p)
    return Narrative(exec_summary=render(text, vals),
                     discussion_points=discussion_points(review.observations),
                     generated_by="template")
