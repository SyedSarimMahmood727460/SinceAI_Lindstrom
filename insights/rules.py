"""Insight rules R1-R8 (spec section 8). Titles and findings are templates rendered by code."""
from __future__ import annotations

import statistics

from model.contracts import MetricResult, Observation, weakest

MIN_SITES = 3
Z_OUTLIER = 1.5
CONFIDENCE = ["High", "Medium", "Low-Med", "Low"]
ALL_TAGS = ["water", "emissions", "cost", "circularity", "service"]


def _weight(tags: list[str], priorities: list[str]) -> float:
    """Weight = 10 - rank (1-based) of each tag in the active list; unlisted tags weigh 0."""
    return float(sum(10 - (priorities.index(t) + 1) for t in tags if t in priorities))


def _outlier(values: dict[str, float], kind: str) -> tuple[str, float, bool] | None:
    """Extreme site (min/max) with its z against the account's sites; relative when |z| < 1.5."""
    if len(values) < MIN_SITES:
        return None
    vals = list(values.values())
    mean, sd = statistics.fmean(vals), statistics.pstdev(vals)
    site = (min if kind == "min" else max)(values, key=values.get)
    z = 0.0 if sd == 0 else (values[site] - mean) / sd
    return site, z, abs(z) < Z_OUTLIER


def _worst_conf(metrics: list[MetricResult]) -> str:
    rank = lambda c: CONFIDENCE.index(c) if c in CONFIDENCE else 0  # noqa: E731
    return max((m.confidence for m in metrics), key=rank)


def _fmt(x: float, digits: int = 0) -> str:
    return f"{x:,.{digits}f}"


def build_observations(account_id: str, account_metrics: dict[str, MetricResult],
                       site_metrics: dict[str, dict[str, MetricResult]], site_names: dict[str, str],
                       laundry_stats: list[dict], industry: str, priorities: list[str],
                       baseline_name: str) -> list[Observation]:
    """Rules need >= 3 sites (site rules) or >= 2 laundries (R4); `industry` is accepted for
    API symmetry (industry shapes `priorities`, resolved by the caller)."""
    obs: list[Observation] = []

    def add(rule_id, node_id, title, finding, action, tags, evidence, metrics, z=None,
            relative=False, confidence=None):
        obs.append(Observation(
            id=f"{account_id}-{rule_id}", rule_id=rule_id,
            title=title + (" (relative)" if relative else ""), finding=finding, action=action,
            tags=list(tags), node_id=node_id, evidence=evidence,
            method_status=weakest(*[m.method_status for m in metrics]),
            confidence=confidence or _worst_conf(metrics), z=z,
            dq_warning=any(m.dq_warning for m in metrics),
            score=_weight(tags, priorities)))

    def site_values(metric_id: str) -> dict[str, float]:
        return {s: m[metric_id].value for s, m in site_metrics.items()
                if metric_id in m and m[metric_id].value is not None}

    def site_rule(rule_id, metric_id, kind, tags, title_fmt, finding_fmt, action):
        vals = site_values(metric_id)
        found = _outlier(vals, kind)
        if found is None:
            return
        site, z, relative = found
        name = site_names.get(site, site)
        median = statistics.median(vals.values())
        add(rule_id, site, title_fmt(name), finding_fmt(name, vals[site], median, z), action, tags,
            [(metric_id, site)], [site_metrics[site][metric_id]], z=z, relative=relative)

    site_rule("R1", "utilisation", "min", ["cost", "circularity"],
              lambda n: f"Low garment utilisation at {n}",
              lambda n, v, med, z: (f"{n} uses {v:.0%} of its allocated garments against a "
                                    f"peer median of {med:.0%} (z = {z:.1f})."),
              "Right-size the allocation and size mix.")

    def r2_finding(n, v, med, z):
        mult = f"{v / med:.1f} times the peer median ({_fmt(med, 1)})" if med else "above a zero peer median"
        return f"{n} logs {_fmt(v, 1)} service requests per 100 wearers, {mult} (z = {z:.1f})."

    site_rule("R2", "service_requests_per_100w", "max", ["service"],
              lambda n: f"High service-request rate at {n}", r2_finding,
              "Break the requests down by type and agree a target.")
    site_rule("R3", "on_time_rate", "min", ["service"],
              lambda n: f"Lowest on-time delivery at {n}",
              lambda n, v, med, z: (f"{n} delivers {v:.1%} of cycles on time against a peer median "
                                    f"of {med:.1%} (z = {z:.1f})."),
              "Review route, pickup window and delivery day.")

    # R4: laundry recycling gap (needs >= 2 laundries with a rate and a gap of >= 10 pp)
    rated = [x for x in laundry_stats if x.get("recycling_rate") is not None]
    if len(rated) >= 2:
        hi = max(rated, key=lambda x: x["recycling_rate"])
        lo = min(rated, key=lambda x: x["recycling_rate"])
        gap = hi["recycling_rate"] - lo["recycling_rate"]
        rec = account_metrics.get("recycling_rate")
        if gap >= 0.10 and rec is not None:
            add("R4", account_id, f"Recycling gap between laundries: {lo['name']} is lowest",
                f"{lo['name']} recycles {lo['recycling_rate']:.0%} of textile waste against "
                f"{hi['recycling_rate']:.0%} at {hi['name']}, a gap of {gap * 100:.0f} percentage points.",
                "Ask for the laundry roadmap and agree a joint recycling KPI.", ["circularity"],
                [("recycling_rate", account_id)], [rec])

    site_rule("R5", "repairs_per_100w", "max", ["circularity", "cost"],
              lambda n: f"High repair intensity at {n}",
              lambda n, v, med, z: (f"{n} needs {_fmt(v, 1)} repairs per 100 wearers against a "
                                    f"peer median of {_fmt(med, 1)} (z = {z:.1f})."),
              "Check product durability fit.")
    site_rule("R6", "washed_kg_per_wearer", "max", ["water", "emissions"],
              lambda n: f"High washing intensity at {n}",
              lambda n, v, med, z: (f"{n} washes {_fmt(v, 1)} kg per wearer against a peer median "
                                    f"of {_fmt(med, 1)} kg (z = {z:.1f})."),
              "Check change frequency against hygiene needs.")

    # R7: value headline (fires whenever a saving exists)
    water, co2 = account_metrics.get("water_saving_l"), account_metrics.get("co2_saving_kg")
    have = [m for m in (water, co2) if m is not None and m.value is not None]
    if have:
        parts = []
        for m, label, unit in ((water, "water", "m3"), (co2, "CO2e", "tonnes")):
            if m is not None and m.value is not None:
                rng = (f" (range {_fmt(m.range.low / 1000, 1)} to {_fmt(m.range.high / 1000, 1)})"
                       if m.range and m.range.low is not None and m.range.high is not None else "")
                parts.append(f"{_fmt(m.value / 1000, 1)} {unit} {label}{rng}")
        add("R7", account_id, "Estimated savings versus the baseline",
            f"Against the {baseline_name} baseline the account saves about " + " and ".join(parts) + ".",
            "Use the range, and confirm the baseline with the customer.", ["water", "emissions"],
            [(m.metric_id, account_id) for m in have], have)

    # R8: data consistency
    flagged = [m for m in account_metrics.values() if m.dq_warning]
    laundries = [x for x in laundry_stats if x.get("dq_warning")]
    fallback = [account_metrics["recycling_rate"]] if "recycling_rate" in account_metrics else []
    metrics = flagged or fallback
    no_data = all(m.value is None for m in account_metrics.values())  # empty filter
    if (flagged or laundries) and metrics and not no_data:
        ev = [(m.metric_id, account_id) for m in metrics]
        names = ", ".join(x["name"] for x in laundries) or "a serving laundry"
        add("R8", account_id, "Laundry volume data needs confirmation",
            f"Data from {names} carries a consistency warning, so allocated water, energy, CO2e "
            "and waste figures for this account are less certain.",
            "Ask Lindström to confirm the laundry volume data before using the figures externally.",
            ALL_TAGS, ev, metrics, confidence="Low")
        obs[-1].score = -1.0  # controller ruling: data-consistency caveat is not prioritised; sorts last

    obs.sort(key=lambda o: (-o.score, -abs(o.z or 0.0)))
    return obs
