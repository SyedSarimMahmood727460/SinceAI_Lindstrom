from model.contracts import (
    Lineage, MetricResult, MethodStatus, Provenance, Scope, weakest,
)


def test_weakest_status():
    M = MethodStatus
    assert weakest(M.CALCULATED, M.ESTIMATED, M.ALLOCATED) == M.ESTIMATED
    assert weakest(M.MEASURED) == M.MEASURED


def test_metric_result_json_roundtrip_with_none():
    r = MetricResult(
        metric_id="x", label="X", unit="kg",
        scope=Scope(node_id="A", level="ACCOUNT", period="2025"),
        value=None, range=None,
        method_status=MethodStatus.CALCULATED, provenance=Provenance.SYNTHETIC,
        confidence="high", assumptions=[],
        lineage=Lineage(facts=[], rows=0, load_ids=[]),
        formula_text="a/b", priority_tags=[],
    )
    js = r.model_dump_json()
    assert "NaN" not in js
    assert MetricResult.model_validate_json(js) == r
