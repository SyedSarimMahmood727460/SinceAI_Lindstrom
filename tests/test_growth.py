"""Growth opportunities (metrics/growth.py, ReviewModel.growth, design §8b G7)."""
import os

import pytest
from fastapi.testclient import TestClient

from api.build import build_review
from api.main import app
from api.review_model import ReviewParams
from config.loader import load_assumptions, load_yaml
from export.format import fmt_value
from metrics.engine import Engine
from metrics.growth import OVERLAP_NOTE, compute_growth
from model.inputs_store import save_inputs, validate_inputs

A = load_assumptions()
SPEC = A["dto_inputs"]
CAT = load_yaml("service_catalogue.yaml")
METRICS = ("diy_cost_avoided", "staff_hours_freed", "co2_saving_kg", "water_saving_l")


@pytest.fixture(scope="module")
def engine(con):
    return Engine(con, A, load_yaml("metrics.yaml"))


def _growth(engine, values=None, baseline="B_LOCAL", period="2025", sens="base"):
    return compute_growth(engine, "CUST001", period, baseline, {"values": values or {}},
                          A, CAT, sensitivity=sens)


def _lever(g, lid):
    return next(lv for lv in g["levers"] if lv["id"] == lid)


def test_growth_none_without_inputs(engine, con):
    assert _growth(engine) is None
    assert _growth(engine, {"extra_sites": 0, "extra_service_lines": []}) is None
    assert _growth(engine, {"local_laundry_eur_per_kg": 3.0}) is None
    assert build_review(con, ReviewParams(account_id="CUST001")).growth is None


def test_growth_sites_scales_linearly(engine):
    g2, g4 = _growth(engine, {"extra_sites": 2}), _growth(engine, {"extra_sites": 4})
    for key in METRICS:
        a, b = _lever(g2, "sites")[key], _lever(g4, "sites")[key]
        assert b.value == pytest.approx(2 * a.value, rel=0.01)
        assert b.method_status.value == "ESTIMATED"
    assert [lv["id"] for lv in g4["levers"]] == ["sites"]
    # per-site average of the current DIY total (in-total lines only), × 4
    from metrics.dto import compute_dto
    from model.inputs_store import effective_inputs
    d = compute_dto(engine, "CUST001", "2025", None, None, "B_LOCAL",
                    effective_inputs({}, SPEC), A)
    sites = engine.compute("CUST001", period="2025")["sites"].value
    assert _lever(g4, "sites")["diy_cost_avoided"].value == pytest.approx(
        d["diy_total"].value / sites * 4)


def _dto_now(engine, period="2025"):
    from metrics.dto import compute_dto
    from model.inputs_store import effective_inputs
    return compute_dto(engine, "CUST001", period, None, None, "B_LOCAL",
                       effective_inputs({}, SPEC), A)


def test_growth_annualised_for_a_quarter(engine):
    q = _growth(engine, {"extra_sites": 4}, period="2025-Q2")
    d = _dto_now(engine, "2025-Q2")
    in_total = sum(x["diy"].value for x in d["lines"] if x["in_total"])
    sites = engine.compute("CUST001", period="2025-Q2")["sites"].value
    assert _lever(q, "sites")["diy_cost_avoided"].value == pytest.approx(
        in_total / sites * 4 * 12 / 3, rel=1e-6)


def test_growth_wearers(engine):
    g = _growth(engine, {"extra_wearers": 500})
    lv = _lever(g, "wearers")
    for key in METRICS:
        assert lv[key].value is not None
    assert lv["diy_cost_avoided"].value > 0 and lv["co2_saving_kg"].value > 0
    g2 = _growth(engine, {"extra_wearers": 1000})
    assert _lever(g2, "wearers")["diy_cost_avoided"].value == pytest.approx(
        2 * lv["diy_cost_avoided"].value)
    # garment admin (site-driven) is excluded from the per-wearer averages
    d = _dto_now(engine)
    lines = {x["id"]: x["diy"].value for x in d["lines"]}
    wearers = engine.compute("CUST001", period="2025")["active_wearers"].value
    assert lv["diy_cost_avoided"].value == pytest.approx(
        (d["diy_total"].value - lines["admin"]) / wearers * 500)
    assert lv["staff_hours_freed"].value == pytest.approx(0)  # B_LOCAL: admin hours only
    assert "excluding garment admin" in lv["diy_cost_avoided"].formula_text
    assert "diy_cost_avoided" not in lv["diy_cost_avoided"].formula_text
    assert "do-it-yourself cost avoided" in lv["diy_cost_avoided"].formula_text
    assert g["notes"] == []


def test_growth_overlap_note(engine):
    g = _growth(engine, {"extra_sites": 4, "extra_wearers": 100})
    assert g["notes"] == [OVERLAP_NOTE]
    assert OVERLAP_NOTE == ("The total assumes the new employees are in addition to those at the "
                            "new sites; if the new sites bring them, use the sites figure alone.")
    assert OVERLAP_NOTE in g["what_to_say"]


def test_growth_partial_data(engine, monkeypatch):
    import metrics.growth as growth_mod
    real = growth_mod.compute_dto

    def partial(*a, **kw):
        return {**real(*a, **kw), "missing_lines": ["garment_purchases"]}
    monkeypatch.setattr(growth_mod, "compute_dto", partial)
    g = _growth(engine, {"extra_sites": 4})
    assert g["partial"] is True
    assert g["narrative_line"].endswith(" (based on partial data).")
    monkeypatch.undo()
    assert _growth(engine, {"extra_sites": 4})["partial"] is False


def test_growth_skips_lines_already_used(engine, pack_path):
    g = _growth(engine, {"extra_service_lines": ["workwear"]})
    assert g["levers"] == [] and g["totals"] is None and g["statement"] is None
    assert g["skipped_lines"] == [{"id": "workwear", "reason": "already used by this customer"}]
    g = _growth(engine, {"extra_sites": 4, "extra_service_lines": ["workwear", "mats"]})
    assert [lv["id"] for lv in g["levers"]] == ["sites", "line:mats"]
    assert [x["id"] for x in g["skipped_lines"]] == ["workwear"]
    # the hotel (extension pack) already rents Mats
    from model.load import load_sources
    old = os.environ.get("VR_EXTENSIONS")
    os.environ["VR_EXTENSIONS"] = "on"
    try:
        con = load_sources()
    finally:
        if old is None:
            os.environ.pop("VR_EXTENSIONS", None)
        else:
            os.environ["VR_EXTENSIONS"] = old
    try:
        eng = Engine(con, A, load_yaml("metrics.yaml"))
        h = compute_growth(eng, "CUST004", "2025", "B_LOCAL",
                           {"values": {"extra_service_lines": ["mats", "washroom"]}}, A, CAT)
        assert [x["id"] for x in h["skipped_lines"]] == ["mats"]
        assert [lv["id"] for lv in h["levers"]] == ["line:washroom"]
    finally:
        con.close()


def test_growth_new_line_mats(engine):
    g = _growth(engine, {"extra_service_lines": ["mats"]})
    lv = _lever(g, "line:mats")
    assert lv["diy_cost_avoided"].value > 0
    assert lv["co2_saving_kg"].value > 0 and lv["water_saving_l"].value > 0
    assert lv["staff_hours_freed"].value == 0  # B_LOCAL has no customer-side washing time
    assert {"T13", "T3"} <= set(lv["co2_saving_kg"].assumptions)
    assert lv["lindstrom_offer_url"].startswith("https://lindstromgroup.com/")
    h = _lever(_growth(engine, {"extra_service_lines": ["mats"]}, baseline="B_INHOUSE"),
               "line:mats")
    assert h["staff_hours_freed"].value > 0
    # the line is sized over current + extra sites
    g4 = _growth(engine, {"extra_service_lines": ["mats"], "extra_sites": 4})
    sites = engine.compute("CUST001", period="2025")["sites"].value
    assert _lever(g4, "line:mats")["diy_cost_avoided"].value == pytest.approx(
        lv["diy_cost_avoided"].value * (sites + 4) / sites)


def test_growth_net_needs_price(engine):
    v = {"extra_sites": 4, "extra_wearers": 100, "extra_service_lines": ["mats"]}
    g = _growth(engine, v)
    assert g["totals"]["net"] is None and all(lv["net"] is None for lv in g["levers"])
    gp = _growth(engine, {**v, "expansion_price_eur_per_site_year": 20000})
    assert all(lv["net"] is not None for lv in gp["levers"])
    s = _lever(gp, "sites")
    assert s["net"].value == pytest.approx(s["diy_cost_avoided"].value - 4 * 20000)
    assert gp["totals"]["net"].value == pytest.approx(sum(lv["net"].value for lv in gp["levers"]))
    # never one combined score: €, hours, CO2e and water stay separate metrics
    assert {m.unit for m in gp["totals"].values() if m is not None} == {"EUR", "h", "kgCO2e", "l"}


def test_growth_ranges_ordered(engine):
    v = {"extra_sites": 4, "extra_wearers": 100, "extra_service_lines": ["mats", "washroom"],
         "expansion_price_eur_per_site_year": 20000}
    for baseline in ("B_LOCAL", "B_INHOUSE", "B_HOME"):
        g = _growth(engine, v, baseline=baseline)
        ms = [m for lv in g["levers"] for m in lv.values() if hasattr(m, "range")]
        ms += [m for m in g["totals"].values() if m is not None]
        for m in ms:
            assert m.range.low <= m.range.base <= m.range.high, m.metric_id
            assert m.value == m.range.base
        # low = the smallest benefit: the cost avoided rises from low to high
        t = g["totals"]["diy_cost_avoided"].range
        assert t.low < t.base < t.high
    # the selected sensitivity picks the headline value
    lo = _growth(engine, v, sens="low")["totals"]["diy_cost_avoided"]
    assert lo.value == lo.range.low


def test_growth_unknown_line_422(tmp_path, monkeypatch):
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="unknown service catalogue id"):
        validate_inputs({"extra_service_lines": ["jetpacks"]}, SPEC)
    for bad in ({"extra_sites": 2.5}, {"extra_sites": -1}, {"extra_wearers": "3"},
                {"extra_service_lines": "mats"}, {"expansion_price_eur_per_site_year": -5}):
        with pytest.raises(ValueError):
            validate_inputs(bad, SPEC)
    with TestClient(app) as c:
        r = c.put("/accounts/CUST001/inputs", json={"extra_service_lines": ["mats", "jetpacks"]})
        assert r.status_code == 422 and "jetpacks" in r.json()["detail"]
        r = c.put("/accounts/CUST001/inputs", json={"extra_sites": 4,
                                                    "extra_service_lines": ["mats"]})
        assert r.status_code == 200
        g = c.get("/accounts/CUST001/review").json()["growth"]
        assert [lv["id"] for lv in g["levers"]] == ["sites", "line:mats"]
        assert g["inputs"]["extra_sites"] == 4
        assert c.get("/accounts/CUST002/review").json()["growth"] is None  # per account
    assert not list(tmp_path.glob("CUST002*"))


def test_growth_narrative_line_has_values(engine, con, tmp_path, monkeypatch):
    g = _growth(engine, {"extra_sites": 4})
    line = g["narrative_line"]
    assert line.startswith("Bringing 4 more sites on board would avoid about ")
    assert fmt_value(g["totals"]["diy_cost_avoided"]) in line
    assert fmt_value(g["totals"]["co2_saving_kg"]) in line and "(between " in line
    assert "None" not in line and "nan" not in line.lower()
    gp = _growth(engine, {"extra_sites": 4, "extra_service_lines": ["mats"],
                          "expansion_price_eur_per_site_year": 20000})
    assert "4 more sites and the Mats service" in gp["narrative_line"]
    assert "Lindström price" in gp["narrative_line"]
    # the customer story shows the growth card when growth inputs exist
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path))
    save_inputs("CUST001", {"extra_sites": 4}, SPEC)
    r = build_review(con, ReviewParams(account_id="CUST001"))
    card = next(c for c in r.story if c["id"] == "growth")
    assert card["statement"] == r.growth["narrative_line"]
    assert card["value_refs"] == ["growth_total_diy_cost_avoided", "growth_total_co2_saving_kg"]
    assert "T12" not in {a["id"] for a in r.methodology["assumptions_used"]}
    save_inputs("CUST001", {"extra_service_lines": ["mats"]}, SPEC)
    r2 = build_review(con, ReviewParams(account_id="CUST001"))
    assert "T13" in {a["id"] for a in r2.methodology["assumptions_used"]}
    assert r2.meta.run_id != r.meta.run_id  # growth inputs invalidate caches


def test_service_catalogue_endpoint():
    with TestClient(app) as c:
        cat = c.get("/config/service-catalogue").json()
    ids = [x["id"] for x in cat]
    assert ids == ["workwear", "mats", "washroom", "cleanroom", "hospitality_textiles"]
    assert [x["assumption_id"] for x in cat] == [f"T{i}" for i in range(12, 17)]
    register = {r["id"] for r in A["register"]}
    for x in cat:
        assert x["assumption_id"] in register
        assert x["lindstrom_offer_url"].startswith("https://lindstromgroup.com/")
        for k in ("typical_kg_per_site_month", "typical_price_eur_per_kg"):
            r = x[k]
            assert 0 < r["low"] <= r["default"] <= r["high"]
        assert x["name"] and x["service_line"] and x["description"]


def test_growth_net_range_sign(engine):
    from metrics.growth import _narrative
    from model.contracts import Range
    gp = _growth(engine, {"extra_sites": 4, "expansion_price_eur_per_site_year": 20000})

    def line(low, base, high):
        net = gp["totals"]["net"].model_copy(
            update={"value": base, "range": Range(low=low, base=base, high=high)})
        return _narrative(gp["levers"], {**gp["totals"], "net": net})

    assert ("the service would cost about 297,100 EUR less than doing it yourself — but the "
            "range runs from 297,100 EUR more to 1,079,363 EUR less, so it depends on the "
            "assumptions.") in line(-297100, 297100, 1079363)
    assert ("the service would cost about 500,000 EUR (between 100,000 and 900,000 EUR) more "
            "than doing it yourself.") in line(-900000, -500000, -100000)
    assert ("the service would cost about 500,000 EUR (between 100,000 and 900,000 EUR) less "
            "than doing it yourself.") in line(100000, 500000, 900000)
