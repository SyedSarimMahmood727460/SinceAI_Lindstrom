"""Discussion points and action table (spec section 8.4)."""
from __future__ import annotations

from model.contracts import MetricResult, Observation

REPORTING_QUESTION = ("Reporting: do we agree the baseline and approve the data for the next "
                      "annual review?")
OWNERS = ["KAM + site manager", "Service owner", "Lindström laundry"]


def discussion_points(obs: list[Observation]) -> list[str]:
    return [o.action for o in obs[:4]] + [REPORTING_QUESTION]


def action_rows(obs: list[Observation], account_metrics: dict[str, MetricResult],
                site_metrics: dict[str, dict[str, MetricResult]]) -> list[dict]:
    rows = []
    for o, owner in zip(obs[:3], OWNERS):
        metric_id, node = o.evidence[0]
        pool = site_metrics.get(node) or account_metrics
        m = pool.get(metric_id)
        rows.append({"text": o.action, "owner": owner, "kpi_metric_id": metric_id,
                     "value_2025": m.value if m else None, "target_2026": None})
    return rows
