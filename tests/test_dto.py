"""Service vs do-it-yourself comparison (metrics/dto.py and ReviewModel.dto)."""
import os

import pytest

from api.build import build_review
from api.review_model import ReviewParams
from config.loader import load_assumptions, load_yaml
from metrics.dto import compute_dto
from metrics.engine import Engine
from model.inputs_store import effective_inputs, save_inputs

A = load_assumptions()
SPEC = A["dto_inputs"]


@pytest.fixture(scope="module")
def engine(con):
    return Engine(con, A, load_yaml("metrics.yaml"))


def _dto(engine, stored=None, period="2025", baseline="B_LOCAL", acc="CUST001",
         product=None, service_line=None):
    return compute_dto(engine, acc, period, product, service_line, baseline,
                       effective_inputs(stored or {}, SPEC), A)


def _lines(dto):
    return {x["id"]: x["diy"] for x in dto["lines"]}


def test_dto_defaults_northstar(engine):
    d = _dto(engine)
    assert d["diy_total"].value is not None and d["diy_total"].value > 0
    assert d["net"] is None and d["contract_price"] is None
    assert set(_lines(d)) == {"garment_purchases", "extra_replacements", "washing", "admin"}
    for m in [*_lines(d).values(), d["diy_total"]]:
        assert m.unit == "EUR" and m.method_status.value == "ESTIMATED"
        assert m.provenance.value == "SYNTHETIC" and m.confidence == "Low"
        assert {"A001", "T1"} <= set(m.assumptions)
        assert m.formula_text
    assert d["convenience"]["staff_hours_freed"].unit == "h"
    assert d["convenience"]["staff_hours_freed"].value > 0
    total = sum(m.range.base for m in _lines(d).values())
    assert d["diy_total"].range.base == pytest.approx(total)


def test_dto_net_with_contract(engine):
    d = _dto(engine, {"values": {"contract_price_eur_per_year": 100000}})
    assert d["contract_price"].range.base == pytest.approx(100000)
    assert d["net"].range.base == pytest.approx(d["diy_total"].range.base - 100000)
    q = _dto(engine, {"values": {"contract_price_eur_per_year": 100000}}, period="2025-Q1")
    assert q["contract_price"].range.base == pytest.approx(25000)


def test_dto_baseline_formula_switch(engine):
    kg = engine.compute("CUST001")["washed_kg"].value
    local = _lines(_dto(engine, baseline="B_LOCAL"))
    assert local["washing"].range.base == pytest.approx(kg * 2.5)
    assert "staff_handling" not in local and "employee_time" not in local
    inhouse = _lines(_dto(engine, baseline="B_INHOUSE"))
    assert "staff_handling" in inhouse and "employee_time" not in inhouse
    b = A["baselines"]["B_INHOUSE"]
    assert inhouse["washing"].range.base == pytest.approx(
        kg * (b["energy_kwh_per_kg"] * 0.15 + b["water_l_per_kg"] / 1000 * 4 + 0.05))
    assert inhouse["staff_handling"].range.base == pytest.approx(kg * 3 / 60 * 30)
    home = _lines(_dto(engine, baseline="B_HOME"))
    assert "employee_time" in home and "staff_handling" not in home
    assert home["washing"].range.base != pytest.approx(inhouse["washing"].range.base)


def test_dto_ranges_ordered(engine):
    for baseline in A["baselines"]:
        d = _dto(engine, {"values": {"contract_price_eur_per_year": 50000}}, baseline=baseline)
        results = [*_lines(d).values(), d["diy_total"], d["net"],
                   d["convenience"]["staff_hours_freed"]]
        for m in results:
            r = m.range
            assert r.low <= r.base <= r.high, (baseline, m.metric_id, r)
            assert r.low < r.high, (baseline, m.metric_id)


def test_dto_entered_value_fixed(engine):
    d = _dto(engine, {"values": {"local_laundry_eur_per_kg": 3.0}})
    kg = engine.compute("CUST001")["washed_kg"].value
    r = _lines(d)["washing"].range
    assert r.low == r.base == r.high == pytest.approx(kg * 3.0)


def test_dto_quarter_scaling(engine):
    year = _lines(_dto(engine))["garment_purchases"].range.base
    q1 = _lines(_dto(engine, period="2025-Q1"))["garment_purchases"].range.base
    assert q1 == pytest.approx(year * 3 / 12, rel=0.25)


def test_dto_mats_only(pack_path):
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
        d = _dto(eng, acc="CUST004", service_line="Mats")
        assert _lines(d)["washing"].value is not None
        assert d["diy_total"].value is not None
        review = build_review(con, ReviewParams(account_id="CUST004", service_line="Mats"))
        assert review.dto is not None and review.dto.hygiene_note is None
    finally:
        con.close()


def test_dto_customer_audience(con):
    r = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    assert r.dto is not None and r.dto.inputs
    assert "idle_stock_value_eur" not in r.model_dump_json()
    assert r.dto.hygiene_note.startswith("Industrial laundering")  # Food & Beverage


def test_dto_in_review_and_run_id(con, tmp_path, monkeypatch):
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path / "kam"))
    p = ReviewParams(account_id="CUST001")
    a = build_review(con, p)
    assert a.dto.baseline == "B_LOCAL"
    assert {"T4", "T8", "T10"} <= {x["id"] for x in a.methodology["assumptions_used"]}
    save_inputs("CUST001", {"admin_h_per_site_month": 6}, SPEC)
    b = build_review(con, p)
    assert b.meta.run_id != a.meta.run_id
    lines_a = {x.id: x.diy for x in a.dto.lines}
    lines_b = {x.id: x.diy for x in b.dto.lines}
    assert lines_b["admin"].value > lines_a["admin"].value
    # the selected sensitivity picks the headline value from the range
    low = build_review(con, ReviewParams(account_id="CUST001", sensitivity="low"))
    assert low.dto.diy_total.value == pytest.approx(low.dto.diy_total.range.low)
