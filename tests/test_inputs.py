"""Account-manager inputs for the service vs do-it-yourself comparison (store + API)."""
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.loader import load_assumptions
from model.inputs_store import (
    effective_inputs, inputs_dir, load_inputs, save_inputs, validate_inputs,
)

SPEC = load_assumptions()["dto_inputs"]
KEYS = ["local_laundry_eur_per_kg", "energy_eur_per_kwh", "water_eur_per_m3",
        "detergent_eur_per_kg", "labour_eur_per_h", "handling_min_per_kg",
        "admin_h_per_site_month", "garment_life_years_no_repair"]


@pytest.fixture
def store(tmp_path, monkeypatch):
    d = tmp_path / "kam_inputs"
    monkeypatch.setenv("VR_INPUTS_DIR", str(d))
    return d


def _by_key(rows):
    return {r["key"]: r for r in rows}


def test_conftest_redirects_inputs_dir():
    # the autouse session fixture keeps tests from writing into the repo
    root = Path(__file__).resolve().parent.parent
    assert not inputs_dir().resolve().is_relative_to(root)


def test_defaults_effective():
    rows = effective_inputs({}, SPEC)
    assert [r["key"] for r in rows] == KEYS + ["contract_price_eur_per_year"]
    by = _by_key(rows)
    assert (by["local_laundry_eur_per_kg"]["value"], by["local_laundry_eur_per_kg"]["low"],
            by["local_laundry_eur_per_kg"]["high"]) == (2.5, 1.8, 3.5)
    assert by["labour_eur_per_h"]["assumption_id"] == "T8"
    assert [by[k]["assumption_id"] for k in KEYS] == [f"T{i}" for i in range(4, 12)]
    for k in KEYS:
        assert by[k]["source"] == "default" and by[k]["entered_at"] is None
        assert by[k]["low"] <= by[k]["value"] <= by[k]["high"]
    c = by["contract_price_eur_per_year"]
    assert c["value"] is None and c["assumption_id"] is None and c["source"] == "default"


def test_save_and_load(store):
    stored = save_inputs("CUST001", {"labour_eur_per_h": 45, "labour_eur_per_h_high": 50,
                                     "contract_price_eur_per_year": 100000}, SPEC)
    assert (store / "CUST001.json").exists()
    assert load_inputs("CUST001") == stored
    by = _by_key(effective_inputs(stored, SPEC))
    lab = by["labour_eur_per_h"]
    assert (lab["value"], lab["low"], lab["high"], lab["source"]) == (45, 45, 50, "kam")
    assert lab["entered_at"]  # ISO date
    assert by["contract_price_eur_per_year"]["value"] == 100000
    assert by["energy_eur_per_kwh"]["source"] == "default"


def test_inputs_reject_non_numeric(store):
    with pytest.raises(ValueError, match="labour_eur_per_h"):
        validate_inputs({"labour_eur_per_h": "2,5"}, SPEC)
    with pytest.raises(ValueError, match="water_eur_per_m3"):
        validate_inputs({"water_eur_per_m3": -1}, SPEC)
    assert not (store / "CUST001.json").exists()


def test_garment_life_must_be_positive():
    for data in ({"garment_life_years_no_repair": 0},
                 {"garment_life_years_no_repair_low": 0}):
        with pytest.raises(ValueError, match="garment_life_years_no_repair"):
            validate_inputs(data, SPEC)
    validate_inputs({"labour_eur_per_h": 0}, SPEC)  # zero is fine where it cannot divide


def test_reject_huge_number():
    with pytest.raises(ValueError, match="labour_eur_per_h"):
        validate_inputs({"labour_eur_per_h": 10 ** 400}, SPEC)


def test_garment_life_help_text():
    assert "longest life" in SPEC["garment_life_years_no_repair"]["help"]
    row = _by_key(effective_inputs({}, SPEC))["garment_life_years_no_repair"]
    assert "cheaper do-it-yourself" in row["help"]


def test_reject_unknown_key():
    with pytest.raises(ValueError, match="bogus_key"):
        validate_inputs({"bogus_key": 1}, SPEC)
    with pytest.raises(ValueError, match="contract_price_eur_per_year_low"):
        validate_inputs({"contract_price_eur_per_year_low": 1}, SPEC)


def test_reject_low_gt_high():
    with pytest.raises(ValueError, match="energy_eur_per_kwh"):
        validate_inputs({"energy_eur_per_kwh_low": 0.3, "energy_eur_per_kwh_high": 0.2}, SPEC)
    with pytest.raises(ValueError, match="labour_eur_per_h"):
        validate_inputs({"labour_eur_per_h": 20, "labour_eur_per_h_low": 25}, SPEC)


def test_inputs_file_corrupt_uses_defaults(store, caplog):
    store.mkdir(parents=True)
    (store / "CUST001.json").write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert load_inputs("CUST001") == {}
    assert "CUST001" in caplog.text
    (store / "CUST002.json").write_text(json.dumps({"values": {"labour_eur_per_h": "x"}}),
                                        encoding="utf-8")
    assert load_inputs("CUST002", SPEC) == {}
    assert load_inputs("CUST003") == {}  # missing file
    # an old file with a zero garment life falls back to defaults (no division by zero)
    (store / "CUST001.json").write_text(
        json.dumps({"values": {"garment_life_years_no_repair": 0}}), encoding="utf-8")
    assert load_inputs("CUST001", SPEC) == {}


def test_inputs_isolated_per_account(store):
    save_inputs("CUST001", {"labour_eur_per_h": 45}, SPEC)
    assert load_inputs("CUST002") == {}
    assert _by_key(effective_inputs(load_inputs("CUST002"), SPEC))["labour_eur_per_h"]["value"] == 30
    with pytest.raises(ValueError):
        load_inputs("../CUST001")


# ---- API --------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client(pack_path):
    from api.main import app
    with TestClient(app) as c:
        yield c


def test_get_inputs_defaults(client, store):
    r = client.get("/accounts/CUST001/inputs")
    assert r.status_code == 200
    assert len(r.json()) == 9
    assert client.get("/accounts/NOPE/inputs").status_code == 404


def test_put_inputs_422(client, store):
    r = client.put("/accounts/CUST001/inputs", json={"labour_eur_per_h": "2,5"})
    assert r.status_code == 422
    assert "labour_eur_per_h" in r.text
    assert client.put("/accounts/CUST001/inputs", json={"nope": 1}).status_code == 422
    assert client.put("/accounts/NOPE/inputs", json={"labour_eur_per_h": 40}).status_code == 404
    assert client.put("/accounts/CUST001/inputs",
                      json={"garment_life_years_no_repair": 0}).status_code == 422
    r = client.put("/accounts/CUST001/inputs", content=b'{"labour_eur_per_h": 1' + b"0" * 400 + b"}",
                   headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert not (store / "CUST001.json").exists()


def test_stored_zero_life_review_ok(client, store):
    store.mkdir(parents=True)
    (store / "CUST001.json").write_text(
        json.dumps({"values": {"garment_life_years_no_repair": 0}}), encoding="utf-8")
    r = client.get("/accounts/CUST001/review")
    assert r.status_code == 200
    assert r.json()["dto"]["diy_total"]["value"] > 0


def test_put_then_review_reflects(client, store):
    q = {"baseline": "B_INHOUSE"}
    before = client.get("/accounts/CUST001/review", params=q).json()
    r = client.put("/accounts/CUST001/inputs", json={"labour_eur_per_h": 50})
    assert r.status_code == 200
    assert _by_key(r.json())["labour_eur_per_h"]["source"] == "kam"
    after = client.get("/accounts/CUST001/review", params=q).json()

    def line(review, lid):
        return next(x["diy"] for x in review["dto"]["lines"] if x["id"] == lid)

    assert line(after, "staff_handling")["range"]["base"] > line(before, "staff_handling")["range"]["base"]
    assert after["dto"]["diy_total"]["range"]["base"] > before["dto"]["diy_total"]["range"]["base"]
    assert after["meta"]["run_id"] != before["meta"]["run_id"]
    # customer audience sees the inputs read-only (same values)
    cust = client.get("/accounts/CUST001/review", params={**q, "audience": "customer"}).json()
    assert _by_key(cust["dto"]["inputs"])["labour_eur_per_h"]["value"] == 50
