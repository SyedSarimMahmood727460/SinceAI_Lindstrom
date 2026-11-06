import math

import pytest

from config.loader import load_assumptions, load_yaml
from metrics.engine import Engine


@pytest.fixture(scope="module")
def engine(con):
    return Engine(con, load_assumptions(), load_yaml("metrics.yaml"))


def test_baseline_switch_changes_savings(engine):
    local = engine.compute("CUST001", "2025", baseline_id="B_LOCAL")
    home = engine.compute("CUST001", "2025", baseline_id="B_HOME")
    assert home["co2_saving_kg"].value > local["co2_saving_kg"].value
    assert home["allocated_co2_kg"].value == local["allocated_co2_kg"].value


def test_baseline_comparison_has_three(engine):
    rows = engine.baseline_comparison("CUST001", "2025")
    assert len(rows) == 3
    local = next(r for r in rows if r["baseline_id"] == "B_LOCAL")
    assert local["co2_saving_kg"] == engine.compute("CUST001", "2025")["co2_saving_kg"].value


def test_monthly_baseline_param(engine):
    a = engine.monthly("CUST001", ["co2_saving_kg"], "2025", baseline_id="B_LOCAL")
    b = engine.monthly("CUST001", ["co2_saving_kg"], "2025", baseline_id="B_HOME")
    assert sum(x["value"] for x in b["co2_saving_kg"]) > sum(x["value"] for x in a["co2_saving_kg"])


def test_quarters_sum_to_year(engine):
    year = engine.compute("CUST001", "2025")
    qs = [engine.compute("CUST001", f"2025-Q{i}") for i in range(1, 5)]
    for mid in ("washed_kg", "repairs", "service_requests"):
        assert sum(q[mid].value for q in qs) == pytest.approx(year[mid].value)


def test_product_filter(engine):
    full = engine.compute("CUST001", "2025")["washed_kg"].value
    p = engine.compute("CUST001", "2025", product="P1004")["washed_kg"].value
    assert 0 < p < full


def test_site_metrics_cover_all_sites(engine):
    sm = engine.site_metrics("CUST001", "2025")
    assert len(sm) == 24
    assert sm["S022"]["service_requests_per_100w"].value == pytest.approx(17.5, abs=0.5)


def test_monthly_series(engine):
    out = engine.monthly("CUST001", ["repairs"], "2025", None)["repairs"]
    assert len(out) == 12
    assert sum(x["value"] for x in out) == 15233


def test_monthly_raw_series_and_site(engine):
    out = engine.monthly("CUST001", ["active_assets_scanned", "late_cycles"], "2025-Q1",
                         site_id="S022")
    assert len(out["late_cycles"]) == 3 and len(out["active_assets_scanned"]) == 3


def test_empty_filter_returns_none_values(engine):
    res = engine.compute("CUST001", "2025", product="NOPE")
    assert res["washed_kg"].value is None
    for r in res.values():
        assert r.value is None or not math.isnan(r.value)
    assert all(not math.isnan(x["value"]) for x in
               engine.monthly("CUST001", ["washed_kg"], "2025", "NOPE")["washed_kg"] if x["value"] is not None)
