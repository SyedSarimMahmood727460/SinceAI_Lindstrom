"""Extension pack (Hospitality, Mats, Estonia) and the service-line filter."""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from api.build import build_review
from api.review_model import ReviewParams
from model.load import load_sources

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "scripts" / "make_extension_pack.py"
PACK_DIR = ROOT / "data" / "extension_pack"
CSVS = ["customers", "sites", "products", "service_activity", "service_cycles", "repairs"]


@pytest.fixture(scope="module")
def con_ext(pack_path):
    old = os.environ.get("VR_EXTENSIONS")
    os.environ["VR_EXTENSIONS"] = "on"
    try:
        con = load_sources()
    finally:
        if old is None:
            os.environ.pop("VR_EXTENSIONS", None)
        else:
            os.environ["VR_EXTENSIONS"] = old
    yield con
    con.close()


def _review(con, **kw):
    return build_review(con, ReviewParams(**kw))


def test_hotel_loaded(con_ext):
    row = con_ext.execute("select name, industry from org_node where node_id = 'CUST004'").fetchone()
    assert row == ("Baltic Harbour Hotels", "Hospitality")
    sites = con_ext.execute(
        "select node_id, country from org_node where parent_id = 'CUST004' order by node_id").fetchall()
    assert len(sites) == 5
    assert {c for _, c in sites} == {"Finland", "Estonia"}
    assert con_ext.execute("select count(*) from quarantine").fetchone()[0] == 0


def test_c1_only_l003(con_ext):
    ids = {r[0] for r in con_ext.execute(
        "select entity_id from dq_flags where check_id = 'C1'").fetchall()}
    assert ids == {"L003"}


def test_existing_accounts_unchanged(con_ext, con):
    q = ("select sum(washed_kg) from fact_service_month where customer_id = ?")
    for acc in ("CUST001", "CUST002", "CUST003"):
        a = _review(con, account_id=acc)
        b = _review(con_ext, account_id=acc)
        for mid in ("co2_saving_kg", "washed_kg", "water_saving_l", "utilisation"):
            ka = next(k for k in a.kpis if k.metric_id == mid)
            kb = next(k for k in b.kpis if k.metric_id == mid)
            assert ka.value == kb.value
        assert con.execute(q, [acc]).fetchone() == con_ext.execute(q, [acc]).fetchone()


def test_service_lines_meta(con_ext, con):
    assert _review(con_ext, account_id="CUST004").meta.service_lines == ["Mats", "Workwear"]
    assert _review(con_ext, account_id="CUST001").meta.service_lines == ["Workwear"]
    assert _review(con, account_id="CUST001").meta.service_line is None


def test_hotel_mats_only_filter(con_ext):
    r = _review(con_ext, account_id="CUST004", service_line="Mats")
    assert r.meta.service_line == "Mats"
    kpi = {k.metric_id: k for k in r.kpis}
    assert kpi["washed_kg"].value > 0
    assert kpi["service_requests_per_100w"].value is None
    json.dumps(r.model_dump(mode="json"), allow_nan=False)  # no NaN anywhere
    allr = _review(con_ext, account_id="CUST004")
    assert {k.metric_id: k for k in allr.kpis}["washed_kg"].value > kpi["washed_kg"].value
    assert r.meta.run_id != allr.meta.run_id
    assert r.meta.service_lines == allr.meta.service_lines  # unfiltered list


def test_hotel_workwear_filter_excludes_mats(con_ext):
    r = _review(con_ext, account_id="CUST004", service_line="Workwear")
    assert {k.metric_id: k for k in r.kpis}["active_wearers"].value > 0


def test_hospitality_defaults(con_ext):
    r = _review(con_ext, account_id="CUST004")
    assert r.context.active_priorities[:2] == ["service", "cost"]
    assert "guest-facing hygiene" in r.context.industry_note


def test_hotel_volume_below_l002(con_ext):
    worst = con_ext.execute(
        "select max(kg) from (select month, sum(washed_kg) kg from fact_service_month "
        "where customer_id = 'CUST004' group by 1)").fetchone()[0]
    assert worst <= 15000


def test_csv_cycles_typed(con_ext):
    typ = {r[0]: r[1] for r in con_ext.execute("describe fact_service_cycle").fetchall()}
    assert typ["pickup_timestamp"] == "TIMESTAMP"
    months = {r[0] for r in con_ext.execute(
        "select distinct month from fact_service_cycle where customer_id = 'CUST004'").fetchall()}
    assert "2025-01" in months and len(months) == 12
    late = con_ext.execute("select count(*) from fact_service_cycle where customer_id = 'CUST004' "
                           "and performance_flag = 'LATE'").fetchone()[0]
    assert late > 0


def test_csv_source_missing_required_files_skipped(tmp_path, pack_path, caplog):
    empty = tmp_path / "bad_pack"
    empty.mkdir()
    (empty / "service_activity.csv").write_text("month\n2025-01\n", encoding="utf-8")
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(yaml.safe_dump({"sources": [
        {"id": "excel_pack", "adapter": "excel", "path": str(pack_path)},
        {"id": "bad_pack", "adapter": "csv", "path": str(empty)}]}), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        con = load_sources(cfg)
    assert "bad_pack" in caplog.text
    assert con.execute("select count(*) from org_node where level = 'ACCOUNT'").fetchone()[0] == 3


def test_generator_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        subprocess.run([sys.executable, str(GENERATOR), "--out", str(out)], check=True, cwd=ROOT)
    for name in CSVS:
        data = (a / f"{name}.csv").read_bytes()
        assert data == (b / f"{name}.csv").read_bytes()
        assert data == (PACK_DIR / f"{name}.csv").read_bytes(), name
        assert b"\r" not in data
