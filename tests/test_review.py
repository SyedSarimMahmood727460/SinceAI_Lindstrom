import json

import pytest

from api.build import build_review
from api.review_model import ReviewParams

ACCOUNTS = ["CUST001", "CUST002", "CUST003"]
BASELINES = ["B_LOCAL", "B_HOME", "B_INHOUSE"]
SENS = ["low", "base", "high"]


def _kpi(model, mid):
    return next(k for k in model.kpis if k.metric_id == mid)


def test_review_validates_all_combinations(con):
    for acc in ACCOUNTS:
        for b in BASELINES:
            for s in SENS:
                model = build_review(con, ReviewParams(account_id=acc, baseline_id=b, sensitivity=s))
                assert "NaN" not in model.model_dump_json()
                assert model.meta.node.id == acc and model.kpis and model.sites


def test_review_context_priorities(con):
    m = build_review(con, ReviewParams(account_id="CUST001"))
    assert m.context.active_priorities[0] == "water"
    assert m.context.priority_source == "customer"
    assert m.context.industry_note.startswith("Show service continuity")


def test_priorities_param(con):
    m = build_review(con, ReviewParams(account_id="CUST001", priorities=["cost"],
                                       priority_source_hint="chips"))
    assert m.context.priority_source == "chips" and m.context.active_priorities == ["cost"]
    m = build_review(con, ReviewParams(account_id="CUST001", priorities=["emissions"],
                                       priority_source_hint="prompt"))
    assert m.context.priority_source == "prompt"


def test_kpis_ordered_by_priority(con):
    m = build_review(con, ReviewParams(account_id="CUST001"))
    assert "water" in m.kpis[0].priority_tags
    assert [k.display["rank"] for k in m.kpis] == list(range(1, len(m.kpis) + 1))


def test_headline_kpis_first(con):
    m = build_review(con, ReviewParams(account_id="CUST001"))
    flags = [k.display["headline"] for k in m.kpis]
    assert flags == sorted(flags, reverse=True)  # headline group first
    n = sum(flags)
    assert n == 12 and all(flags[:n])
    ids = [k.metric_id for k in m.kpis[:12]]
    assert "co2_saving_kg" in ids and "water_saving_l" in ids


def test_customer_audience_hides_internal(con):
    kam = build_review(con, ReviewParams(account_id="CUST001"))
    assert any(k.metric_id == "idle_stock_value_eur" for k in kam.kpis)
    m = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    assert all(k.metric_id != "idle_stock_value_eur" for k in m.kpis)
    for s in m.sites:
        assert "idle_stock_value_eur" not in s.metrics


def test_sensitivity_selects_value(con):
    low = _kpi(build_review(con, ReviewParams(account_id="CUST001", sensitivity="low")), "co2_saving_kg")
    high = _kpi(build_review(con, ReviewParams(account_id="CUST001", sensitivity="high")), "co2_saving_kg")
    assert low.value == low.range.low and high.value == high.range.high
    assert low.value < high.value


def test_run_id_stable(con):
    a = build_review(con, ReviewParams(account_id="CUST001")).meta.run_id
    assert a == build_review(con, ReviewParams(account_id="CUST001")).meta.run_id
    assert len(a) == 12
    assert a != build_review(con, ReviewParams(account_id="CUST001", baseline_id="B_HOME")).meta.run_id


def test_review_empty_filter(con):
    m = build_review(con, ReviewParams(account_id="CUST002", product="P1004"))
    assert all(o.rule_id == "R8" for o in m.observations)
    assert "NaN" not in m.model_dump_json()
    assert m.actions == []


def test_disclaimer(con):
    m = build_review(con, ReviewParams(account_id="CUST001"))
    assert m.meta.disclaimer == "Prototype · synthetic data · not audited"


def test_trends_account_and_site(con):
    ids = {"active_wearers", "garments_allocated", "active_assets_scanned", "repairs",
           "service_requests", "late_cycles"}
    m = build_review(con, ReviewParams(account_id="CUST001"))
    assert set(m.trends) == ids and len(m.trends["repairs"]) == 12
    site = m.sites[0].node_id
    ms = build_review(con, ReviewParams(account_id="CUST001", site=site))
    assert ms.trends["active_wearers"] != m.trends["active_wearers"]


def test_meta_products_unfiltered(con):
    a = build_review(con, ReviewParams(account_id="CUST001"))
    b = build_review(con, ReviewParams(account_id="CUST001", product=a.meta.products[0]["id"]))
    assert a.meta.products == b.meta.products and {"id", "name"} == set(a.meta.products[0])


def test_review_sections(con):
    m = build_review(con, ReviewParams(account_id="CUST001"))
    assert m.narrative.generated_by == "template" and m.narrative.discussion_points
    assert len(m.actions) == 3 and m.comparisons["baselines"] and m.circularity["repairs_by_type"]
    assert m.methodology["boundary"] and m.methodology["status_legend"]
    assert {a["id"] for a in m.methodology["assumptions_used"]} >= {"A003"}
    assert m.data_quality["gaps"] and m.data_quality["hidden_modules"] == []
    assert m.data_quality["warnings"] and m.data_quality["quarantine_count"] >= 0
    json.loads(m.model_dump_json())


def test_priorities_without_hint_are_chips(con):
    m = build_review(con, ReviewParams(account_id="CUST001", priorities=["cost"]))
    assert m.context.active_priorities[0] == "cost" and m.context.priority_source == "chips"


def test_unknown_baseline_or_site_raises_value_error(con):
    with pytest.raises(ValueError, match="unknown baseline_id: B_X"):
        build_review(con, ReviewParams(account_id="CUST001", baseline_id="B_X"))
    with pytest.raises(ValueError, match="unknown site: S999"):
        build_review(con, ReviewParams(account_id="CUST001", site="S999"))


def test_customer_audience_observations_and_actions_clean(con):
    for acc in ACCOUNTS:
        m = build_review(con, ReviewParams(account_id=acc, audience="customer",
                                           priorities=["cost"]))
        assert all(e[0] != "idle_stock_value_eur" for o in m.observations for e in o.evidence)
        hidden = {k.metric_id for k in build_review(con, ReviewParams(account_id=acc)).kpis
                  if not k.customer_facing}
        assert hidden and all(a["kpi_metric_id"] not in hidden for a in m.actions)
