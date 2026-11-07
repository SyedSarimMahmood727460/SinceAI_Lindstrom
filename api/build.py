"""Review builder: assembles the ReviewModel from the engine and insight modules."""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import threading
from datetime import datetime, timezone

from api.review_model import (
    Context, Dto, Kpi, Meta, NodeInfo, ReviewModel, ReviewParams, SiteEntry,
)
from config.loader import load_assumptions, load_yaml
from insights.discussion import action_rows, discussion_points
from insights.priorities import resolve_priorities
from insights.rules import _weight, build_observations
from metrics.dto import compute_dto
from metrics.engine import Engine
from metrics.periods import period_months
from model.contracts import MetricResult, Narrative, Observation
from model.inputs_store import effective_inputs, load_inputs

TREND_IDS = ["active_wearers", "garments_allocated", "active_assets_scanned", "repairs",
             "service_requests", "late_cycles"]
# Site outlier flags: metric -> the "bad" direction among peers (|z| >= 1.5, at least 3 sites).
OUTLIER_METRICS = {"utilisation": "min", "on_time_rate": "min", "service_requests_per_100w": "max",
                   "repairs_per_100w": "max", "washed_kg_per_wearer": "max"}
Z_OUTLIER = 1.5
MIN_SITES = 3


_NARRATIVES: dict[str, Narrative] = {}  # LLM narratives by run_id, so chip clicks don't re-call
_CACHE_MAX = 256
_NARRATIVES_LOCK = threading.Lock()  # guards the dict only, never the LLM call

_C1 = re.compile(r"customer washed_kg ([\d.]+) vs laundry washed_kg ([\d.]+) \(ratio ([\d.]+)x\)")
DQ_COLS = ("check_id", "severity", "entity_type", "entity_id", "month", "detail")


def dq_warning_rows(con, rows, months: list[str] | None = None) -> list[dict]:
    """dq_flags rows as dicts, with the laundry's name and a readable message; optionally
    restricted to the given months."""
    names = dict(con.execute("select laundry_id, name from laundry").fetchall())
    out = []
    for r in rows:
        w = dict(zip(DQ_COLS, r))
        if months is not None and w["month"] not in months:
            continue
        w["entity_name"] = names.get(w["entity_id"]) if w["entity_type"] == "laundry" else None
        m = _C1.fullmatch(w["detail"] or "")
        w["message"] = (f"Customer volume routed {float(m[1]):,.0f} kg vs laundry total "
                        f"{float(m[2]):,.0f} kg ({float(m[1]) / float(m[2]):.1f}×)") if m else w["detail"]
        out.append(w)
    return out


def _narrate(review: ReviewModel, use_llm: bool) -> Narrative:
    """LLM narrative when enabled (VR_AI, API key), else the template; always guard-checked."""
    from ai import llm
    from ai.narrator import narrate
    if not (use_llm and llm.use_llm()):
        return narrate(review, False)
    key = review.meta.run_id
    with _NARRATIVES_LOCK:
        if key in _NARRATIVES:
            return _NARRATIVES[key]
    result = narrate(review, True)
    if result.generated_by == "llm":  # a template fallback is retried on the next request
        with _NARRATIVES_LOCK:
            if len(_NARRATIVES) >= _CACHE_MAX:
                _NARRATIVES.pop(next(iter(_NARRATIVES)))
            _NARRATIVES[key] = result
    return result


def _select(m: MetricResult, sensitivity: str) -> MetricResult:
    """The selected sensitivity picks the headline value from the range."""
    if m.range is not None and getattr(m.range, sensitivity) is not None:
        return m.model_copy(update={"value": getattr(m.range, sensitivity)})
    return m


def _select_dto(dto: dict, sensitivity: str) -> Dto:
    """The selected sensitivity picks every DTO headline value (like the KPIs)."""
    for line in dto["lines"]:
        line["diy"] = _select(line["diy"], sensitivity)
    for k in ("diy_total", "contract_price", "net"):
        if dto[k] is not None:
            dto[k] = _select(dto[k], sensitivity)
    conv = dto["convenience"]
    conv["staff_hours_freed"] = _select(conv["staff_hours_freed"], sensitivity)
    return Dto(**dto)


def _visible(metrics: dict[str, MetricResult], audience: str) -> dict[str, MetricResult]:
    return {k: m for k, m in metrics.items() if audience != "customer" or m.customer_facing}


def _outlier_flags(site_metrics: dict[str, dict[str, MetricResult]]) -> dict[str, list[str]]:
    flags: dict[str, list[str]] = {s: [] for s in site_metrics}
    for mid, kind in OUTLIER_METRICS.items():
        vals = {s: m[mid].value for s, m in site_metrics.items()
                if mid in m and m[mid].value is not None}
        if len(vals) < MIN_SITES:
            continue
        mean, sd = statistics.fmean(vals.values()), statistics.pstdev(vals.values())
        if sd == 0:
            continue
        for s, v in vals.items():
            z = (v - mean) / sd
            if (z <= -Z_OUTLIER) if kind == "min" else (z >= Z_OUTLIER):
                flags[s].append(mid)
    return flags


def _interpretation(priorities: list[str], source: str) -> str:
    if source in ("prompt", "chips"):
        return f"Priorities from your {source}: " + ", ".join(priorities)
    return ""


def build_review(con, params: ReviewParams, engine: Engine | None = None,
                 use_ai: bool = False) -> ReviewModel:
    engine = engine or Engine(con, load_assumptions(), load_yaml("metrics.yaml"))
    acc, sens, aud = params.account_id, params.sensitivity, params.audience
    row = con.execute("select name, industry, segment, priority_topics from org_node "
                      "where node_id = ? and level = 'ACCOUNT'", [acc]).fetchone()
    if row is None:
        raise ValueError(f"unknown account: {acc}")
    name, industry, segment, topics = row
    assumptions = engine.assumptions
    if params.baseline_id not in assumptions["baselines"]:
        raise ValueError(f"unknown baseline_id: {params.baseline_id}")
    if params.site is not None and params.site not in {
            r[0] for r in con.execute("select node_id from org_node where level = 'SITE' "
                                      "and parent_id = ?", [acc]).fetchall()}:
        raise ValueError(f"unknown site: {params.site}")
    baseline = assumptions["baselines"][params.baseline_id]

    # priorities
    hint = params.priority_source_hint
    chosen = params.priorities or None
    priorities, source = resolve_priorities(
        list(topics or []), industry,
        chips=chosen if chosen and hint != "prompt" else None,
        prompt=chosen if chosen and hint == "prompt" else None)

    # metrics (the selected sensitivity picks every headline value)
    sl = params.service_line
    q = dict(period=params.period, product=params.product, baseline_id=params.baseline_id,
             service_line=sl)
    account_all = {k: _select(m, sens) for k, m in engine.compute(acc, **q).items()}
    sites_all = {s: {k: _select(m, sens) for k, m in ms.items()}
                 for s, ms in engine.site_metrics(acc, **q).items()}
    laundry_stats = engine.laundry_stats(acc, params.period, sl)

    site_rows = con.execute(
        "select node_id, name, country, city, site_type, primary_laundry_id from org_node "
        "where level = 'SITE' and parent_id = ? order by node_id", [acc]).fetchall()
    site_names = {r[0]: r[1] for r in site_rows}

    obs: list[Observation] = build_observations(
        acc, account_all, sites_all, site_names, laundry_stats, industry, priorities,
        baseline["name"])
    if aud == "customer":
        hidden = {k for k, m in account_all.items() if not m.customer_facing}
        obs = [o for o in obs if not any(e[0] in hidden for e in o.evidence)]
    actions = action_rows(obs, account_all, sites_all)

    # KPIs: headline metrics first, each group ordered by priority score (stable)
    visible = _visible(account_all, aud)
    headline = {mid for mid, spec in engine.registry.items() if spec.get("headline")}
    ordered = sorted(visible.values(),
                     key=lambda m: (m.metric_id not in headline, -_weight(m.priority_tags, priorities)))
    kpis = [Kpi(**m.model_dump(), display={"rank": i, "module_id": None,
                                           "headline": m.metric_id in headline})
            for i, m in enumerate(ordered, 1)]

    flags = _outlier_flags(sites_all)
    sites = [SiteEntry(node_id=r[0], name=r[1], country=r[2], city=r[3], site_type=r[4],
                       laundry_id=r[5], metrics=_visible(sites_all[r[0]], aud),
                       outlier_flags=flags[r[0]])
             for r in site_rows if r[0] in sites_all]

    trends = engine.monthly(acc, TREND_IDS, params.period, params.product,
                            site_id=params.site, baseline_id=params.baseline_id, service_line=sl)
    bl = engine.baseline_comparison(acc, params.period, params.product, sl)
    circ = engine.circularity(acc, params.period, params.product, sl)

    # service vs do-it-yourself (account-manager inputs; customers see them read-only)
    spec = assumptions["dto_inputs"]
    inputs = effective_inputs(load_inputs(acc, spec), spec)
    dto = _select_dto(compute_dto(engine, acc, params.period, params.product, sl,
                                  params.baseline_id, inputs, assumptions, results=account_all),
                      sens)
    inputs_hash = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode("utf-8")).hexdigest()[:8]

    # meta
    countries = sorted({r[2] for r in site_rows if r[2]})
    srows = con.execute(
        "select distinct s.source_id, s.tier, f.provenance, s.load_id from source s "
        "left join fact_service_month f on f.source_id = s.source_id "
        "order by s.source_id, f.provenance").fetchall()
    sources = [{"source_id": r[0], "tier": r[1], "provenance": r[2] or "SYNTHETIC"} for r in srows]
    load_ids = "|".join(sorted({r[3] for r in srows if r[3]}))
    run_id = hashlib.sha256(
        f"{load_ids}|{assumptions.get('version')}|{params.model_dump_json()}|{inputs_hash}"
        .encode("utf-8")
    ).hexdigest()[:12]
    products = [{"id": r[0], "name": r[1]} for r in con.execute(
        "select distinct p.product_id, p.name from fact_service_month f "
        "join product p on p.product_id = f.product_id where f.customer_id = ? "
        "order by p.product_id", [acc]).fetchall()]
    service_lines = [r[0] for r in con.execute(
        "select distinct p.service_line from fact_service_month f "
        "join product p on p.product_id = f.product_id where f.customer_id = ? "
        "and p.service_line is not null order by 1", [acc]).fetchall()]
    meta = Meta(
        run_id=run_id, generated_at=datetime.now(timezone.utc),
        node=NodeInfo(id=acc, name=name, industry=industry, segment=segment, countries=countries),
        period=params.period,
        baseline={"id": params.baseline_id, "name": baseline["name"],
                  "factors": {k: v for k, v in baseline.items()
                              if k.endswith(("_per_kg", "_share"))}},
        sensitivity=sens, assumption_set_version=assumptions.get("version", ""),
        sources=sources, products=products,
        service_lines=service_lines, service_line=sl)

    note = load_yaml("industry_rules.yaml")["emphasis"].get(industry, "")
    context = Context(active_priorities=priorities, priority_source=source,
                      interpretation_text=_interpretation(priorities, source), industry_note=note)

    # methodology and data quality (data-driven from config)
    text = load_yaml("review_text.yaml")
    used = {a for k in kpis for a in k.assumptions}
    used |= {a for x in dto.lines for a in x.diy.assumptions}
    used |= set(dto.convenience["staff_hours_freed"].assumptions)
    methodology = {
        "boundary": list(text["boundary"]),
        "assumptions_used": [r for r in assumptions["register"] if r["id"] in used],
        "limitations": list(text["limitations"]),
        "status_legend": list(text["status_legend"]),
    }
    entities = [acc, *site_names, *[x["laundry_id"] for x in laundry_stats]]
    flag_rows = con.execute(
        "select check_id, severity, entity_type, entity_id, month, detail from dq_flags "
        "where list_contains(?, entity_id) order by check_id, entity_id, month", [entities]).fetchall()
    data_quality = {
        "quarantine_count": con.execute("select count(*) from quarantine").fetchone()[0],
        "warnings": dq_warning_rows(con, flag_rows, period_months(params.period)),
        "gaps": list(text["gaps"]),
        "hidden_modules": [],
    }

    review = ReviewModel(
        meta=meta, context=context, kpis=kpis, sites=sites, trends=trends,
        comparisons={"baselines": bl}, circularity=circ, observations=obs,
        narrative=Narrative(exec_summary="", discussion_points=[], generated_by="template"),
        actions=actions, methodology=methodology, data_quality=data_quality, dto=dto)
    review.narrative = _narrate(review, use_ai)
    return review
