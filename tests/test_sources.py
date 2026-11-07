import logging

import pandas as pd
import pytest
import yaml

from adapters.csv_pack import CsvPackAdapter
from model.load import load_pack, load_sources


def _write_csv_pack(folder, site_id="S901", site_customer="CUST901"):
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "customer_id": "CUST901", "customer_name": "Test Hotels", "industry": "Hospitality",
        "segment": "High Value", "hq_country": "Finland", "priority_topics": "Hygiene|Cost optimization",
    }]).to_csv(folder / "customers.csv", index=False)
    pd.DataFrame([{
        "site_id": site_id, "customer_id": site_customer, "site_name": "Test Site",
        "country": "Finland", "city": "Turku", "site_type": "Hotel", "primary_laundry_id": "L002",
    }]).to_csv(folder / "sites.csv", index=False)
    pd.DataFrame([{
        "product_id": "P9001", "product_name": "Entrance Mat", "product_group": "Mats",
        "service_line": "Mats", "avg_weight_kg": 3.0,
        "synthetic_product_footprint_kgco2e": 10.0, "synthetic_purchase_cost_eur": 50.0,
    }]).to_csv(folder / "products.csv", index=False)
    pd.DataFrame([{
        "month": "2025-01", "customer_id": "CUST901", "site_id": site_id, "product_id": "P9001",
        "laundry_id": "L001", "active_wearers": 0, "allocated_pieces": 10,
        "active_assets_scanned": 9, "washed_pieces": 10, "packed_pieces": 10,
        "customer_washed_kg": 30.0, "service_requests": 0,
    }]).to_csv(folder / "service_activity.csv", index=False)


def _config(tmp_path, pack_path, csv_dir):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(yaml.safe_dump({"sources": [
        {"id": "excel_pack", "adapter": "excel", "path": str(pack_path), "enabled": True},
        {"id": csv_dir.name, "adapter": "csv", "path": str(csv_dir), "enabled": True},
    ]}), encoding="utf-8")
    return cfg


def test_load_pack_unchanged(pack_path):
    con = load_pack(pack_path)
    assert con.execute("select count(*) from org_node").fetchone()[0] == 37
    assert con.execute("select count(*) from fact_service_month").fetchone()[0] == 1248


def test_csv_adapter_roundtrip(tmp_path, pack_path):
    csv_dir = tmp_path / "ext"
    _write_csv_pack(csv_dir)
    assert CsvPackAdapter(csv_dir).source_id == "ext"
    con = load_sources(_config(tmp_path, pack_path, csv_dir))
    assert con.execute("select count(*) from org_node where node_id='CUST901'").fetchone()[0] == 1
    assert con.execute("select service_line from product where product_id='P9001'").fetchone()[0] == "Mats"
    assert con.execute("select count(*) from source").fetchone()[0] == 2
    assert con.execute("select count(*) from fact_service_month where site_id='S901'").fetchone()[0] == 1


def test_duplicate_id_quarantined(tmp_path, pack_path):
    csv_dir = tmp_path / "ext"
    _write_csv_pack(csv_dir, site_id="S001")
    con = load_sources(_config(tmp_path, pack_path, csv_dir))
    reasons = [r[0] for r in con.execute("select reason from quarantine").fetchall()]
    assert any("duplicate key from source" in r for r in reasons)
    assert con.execute("select parent_id from org_node where node_id='S001'").fetchone()[0] == "CUST001"


def test_extensions_off_three_accounts(monkeypatch):
    monkeypatch.setenv("VR_EXTENSIONS", "off")
    con = load_sources()
    assert con.execute("select count(*) from org_node where level='ACCOUNT'").fetchone()[0] == 3


def test_missing_csv_folder_skipped(tmp_path, pack_path, caplog):
    cfg = _config(tmp_path, pack_path, tmp_path / "nope")
    with caplog.at_level(logging.WARNING):
        con = load_sources(cfg)
    assert con.execute("select count(*) from org_node where level='ACCOUNT'").fetchone()[0] == 3
    assert con.execute("select count(*) from source").fetchone()[0] == 1
    assert "nope" in caplog.text


@pytest.mark.parametrize("val", ["off"])
def test_toggle_env_disables(tmp_path, pack_path, monkeypatch, val):
    csv_dir = tmp_path / "ext"
    _write_csv_pack(csv_dir)
    cfg = _config(tmp_path, pack_path, csv_dir)
    d = yaml.safe_load(cfg.read_text())
    d["sources"][1]["toggle_env"] = "VR_TEST_TOGGLE"
    cfg.write_text(yaml.safe_dump(d))
    monkeypatch.setenv("VR_TEST_TOGGLE", val)
    con = load_sources(cfg)
    assert con.execute("select count(*) from source").fetchone()[0] == 1
