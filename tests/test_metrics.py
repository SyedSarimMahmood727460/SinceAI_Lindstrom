import math

import pandas as pd
import pytest

from config.loader import load_assumptions, load_yaml
from metrics.engine import Engine
from metrics.frames import base_frames
from metrics.periods import period_months


@pytest.fixture(scope="module")
def engine(con):
    return Engine(con, load_assumptions(), load_yaml("metrics.yaml"))


@pytest.fixture(scope="module")
def northstar(engine):
    return engine.compute("CUST001", "2025")


def test_period_months():
    assert len(period_months("2025")) == 12
    assert period_months("2025")[0] == "2025-01"
    assert period_months("2025-Q2") == ["2025-04", "2025-05", "2025-06"]


def test_northstar_basics(northstar):
    assert northstar["sites"].value == 24
    assert northstar["washed_kg"].value == pytest.approx(502074.7, abs=1)
    assert northstar["repairs"].value == 15233
    assert northstar["service_requests"].value == 515


def test_registry_covers_all_metrics(northstar):
    assert len(northstar) == 33
    assert set(northstar) == set(load_yaml("metrics.yaml"))


def test_wearers_deduplicated(con, northstar):
    naive = con.execute(
        "select sum(active_wearers) from fact_service_month "
        "where customer_id='CUST001' and month='2025-12'"
    ).fetchone()[0]
    assert northstar["active_wearers"].value == 9607
    assert northstar["active_wearers"].value != naive


def test_allocation_reconciles(con, pack_path):
    ref = pd.read_excel(pack_path, sheet_name="Customer_Impacts")
    act = base_frames(con, "CUST001", period_months("2025"), None)["activity"]
    ref = ref[ref.customer_id == "CUST001"]
    r = ref.set_index(["month", "site_id", "product_id"])
    a = act.set_index(["month", "site_id", "product_id"])
    common = a.index.intersection(r.index)
    assert len(common) == len(r) == len(a)
    r, a = r.loc[common], a.loc[common]

    def close(x, y):
        return ((x - y).abs() <= 0.02 * y.abs() + 0.05).all()

    assert close(a.allocated_water_l, r.allocated_water_l)
    assert close(a.allocated_energy_kwh, r.allocated_energy_kwh)
    assert close(
        a.allocated_process_kg + a.allocated_delivery_kg,
        r.allocated_process_kgco2e + r.allocated_delivery_kgco2e,
    )
    assert close(a.allocated_waste_kg, r.allocated_textile_waste_kg)


def test_savings_match_sample_output(northstar):
    assert northstar["water_saving_l"].value == pytest.approx(1406482.6, rel=0.02)
    assert northstar["co2_saving_kg"].value == pytest.approx(255073.1, rel=0.02)


def test_co2_range(northstar):
    r = northstar["co2_saving_kg"].range
    assert r.low == pytest.approx(205700, rel=0.01)
    assert r.high == pytest.approx(304400, rel=0.01)
    assert r.base == northstar["co2_saving_kg"].value


def test_ratio_rollup_not_mean(con, engine, northstar):
    sums = con.execute(
        "select sum(active_assets_scanned), sum(allocated_pieces) "
        "from fact_service_month where customer_id='CUST001'"
    ).fetchone()
    assert northstar["utilisation"].value == pytest.approx(sums[0] / sums[1])
    sites = [r[0] for r in con.execute(
        "select node_id from org_node where parent_id='CUST001'").fetchall()]
    site_u = [engine.compute(s)["utilisation"].value for s in sites]
    site_u = [u for u in site_u if u is not None]
    assert northstar["utilisation"].value != pytest.approx(sum(site_u) / len(site_u), rel=1e-9)


def test_dq_warning_propagates(engine):
    reg = load_yaml("metrics.yaml")["allocated_water_l"]["confidence"]
    clean = engine.compute("CUST003")
    flagged = engine.compute("CUST002")
    assert clean["allocated_water_l"].dq_warning is False
    assert flagged["allocated_water_l"].dq_warning is True
    assert reg == "Medium" and flagged["allocated_water_l"].confidence == "Low-Med"
    assert clean["allocated_water_l"].confidence == reg
    # counts are not allocation-derived, so they are never flagged
    for mid in ("washed_kg", "utilisation", "sites", "active_wearers", "repairs"):
        assert flagged[mid].dq_warning is False


def test_snapshot_uses_last_month_of_period(con, engine):
    from metrics.engine import _values

    months = period_months("2025")
    frames = base_frames(con, "CUST001", months, None)
    full = _values(frames, load_assumptions()["baselines"]["B_LOCAL"], 1.0, 1.0)
    act = frames["activity"]
    frames["activity"] = act[act.month != "2025-12"]
    cut = _values(frames, load_assumptions()["baselines"]["B_LOCAL"], 1.0, 1.0)
    assert cut["active_wearers"] == 0 and cut["garments_allocated"] == 0
    dec = act[act.month == "2025-12"].groupby("site_id").active_wearers.max().sum()
    assert cut["active_wearers_avg"] == pytest.approx(
        (full["active_wearers_avg"] * 12 - dec) / 12)


def _stub_frames(prov):
    import pandas as pd

    act = pd.DataFrame({"method_status": ["CALCULATED"] * len(prov), "provenance": prov,
                        "load_id": ["x"] * len(prov), "dq_warning": [False] * len(prov)})
    empty = pd.DataFrame()
    return {"activity": act, "cycles": empty, "repairs": empty}


@pytest.mark.parametrize("prov,expected", [
    (["APPROVED_REAL", "APPROVED_REAL"], "APPROVED_REAL"),
    (["APPROVED_REAL", "SYNTHETIC"], "SYNTHETIC"),
    (["APPROVED_REAL", "PUBLIC_REFERENCE"], "PUBLIC_REFERENCE"),
])
def test_provenance_is_weakest_of_inputs(engine, prov, expected):
    from model.contracts import Scope

    spec = load_yaml("metrics.yaml")["washed_kg"]
    res = engine._result("washed_kg", spec, Scope(node_id="X", level="ACCOUNT", period="2025"),
                         _stub_frames(prov), {"activity"}, 1.0, None)
    assert res.provenance.value == expected


def test_empty_filter_returns_none_values(engine):
    res = engine.compute("CUST002", product="P1004")
    assert res["washed_kg"].value is None
    assert res["utilisation"].value is None
    for r in res.values():
        assert r.value is None and r.range is None
        assert not (isinstance(r.value, float) and math.isnan(r.value))


def test_idle_value_not_customer_facing(northstar):
    assert northstar["idle_stock_value_eur"].customer_facing is False
    assert northstar["washed_kg"].customer_facing is True


def test_site_compute_and_lineage(engine):
    res = engine.compute("S001")
    assert res["sites"].value == 1
    assert res["washed_kg"].scope.level == "SITE"
    lin = res["washed_kg"].lineage
    assert lin.facts == ["fact_service_month"] and lin.rows > 0 and lin.load_ids


def test_monthly_series(engine):
    out = engine.monthly("CUST001", ["washed_kg", "active_assets_scanned", "late_cycles"], "2025", None)
    assert [p["month"] for p in out["washed_kg"]] == period_months("2025")
    total = engine.compute("CUST001")["washed_kg"].value
    assert sum(p["value"] for p in out["washed_kg"]) == pytest.approx(total)
    assert all(p["value"] is not None for p in out["late_cycles"])
    assert sum(p["value"] for p in out["active_assets_scanned"]) > 0


def test_baseline_comparison_and_circularity(engine):
    rows = engine.baseline_comparison("CUST001", "2025", None)
    assert {r["baseline_id"] for r in rows} == {"B_LOCAL", "B_HOME", "B_INHOUSE"}
    local = next(r for r in rows if r["baseline_id"] == "B_LOCAL")
    assert local["co2_saving_kg"] == pytest.approx(255073.1, rel=0.02)
    circ = engine.circularity("CUST001", "2025", None)
    assert sum(circ["repairs_by_type"].values()) == 15233
    assert len(circ["repairs_by_month"]) == 12
    assert "recycling" in circ["waste_routes"]


def test_site_metrics_and_laundry_stats(engine):
    sm = engine.site_metrics("CUST001", "2025", None, "B_LOCAL")
    assert len(sm) == 24
    stats = engine.laundry_stats("CUST001", "2025")
    assert {s["laundry_id"] for s in stats} >= {"L001"}
    l3 = [s for s in stats if s["laundry_id"] == "L003"]
    assert l3 and l3[0]["dq_warning"] is True and l3[0]["site_ids"]
    assert all(0 <= s["recycling_rate"] <= 1 for s in stats)
