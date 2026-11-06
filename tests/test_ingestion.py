import pytest

from config.loader import load_assumptions
from model.load import load_pack


def count(con, table):
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_all_tables_loaded(con):
    assert count(con, "fact_service_month") == 1248
    assert count(con, "fact_service_cycle") == 16415
    assert count(con, "fact_repair_month") == 3635
    assert count(con, "fact_laundry_month") == 48
    assert count(con, "fact_waste_month") == 192
    assert count(con, "org_node") == 37


def test_clean_pack_has_no_quarantine(con):
    assert count(con, "quarantine") == 0


def test_c1_flags_l003(con):
    flagged = {r[0] for r in con.execute("SELECT DISTINCT entity_id FROM dq_flags WHERE check_id='C1'").fetchall()}
    assert "L003" in flagged
    assert not flagged & {"L001", "L004", "L002"}
    months = con.execute("SELECT count(*) FROM dq_flags WHERE check_id='C1' AND entity_id='L003'").fetchone()[0]
    assert months == 12
    detail = con.execute("SELECT detail FROM dq_flags WHERE check_id='C1' AND entity_id='L003' LIMIT 1").fetchone()[0]
    assert "ratio" in detail


def test_injected_rows_quarantined(pack_path):
    con = load_pack(pack_path, inject_bad=True)
    reasons = [r[0] for r in con.execute("SELECT reason FROM quarantine").fetchall()]
    assert len(reasons) == 3
    for word in ("unknown site", "month", "negative"):
        assert any(word in r for r in reasons), word
    assert count(con, "fact_service_month") == 1248


def test_unicode_names_preserved(con):
    name = con.execute("SELECT name FROM org_node WHERE node_id='S024'").fetchone()[0]
    assert name == "NorthStar Łódź"


def test_facts_carry_status_and_provenance(con):
    row = con.execute("SELECT DISTINCT method_status, provenance, source_id FROM fact_service_month").fetchall()
    assert row == [("CALCULATED", "SYNTHETIC", "excel_pack")]
    assert con.execute("SELECT min(month), max(month) FROM fact_service_cycle").fetchone()[0] >= "2025-01"
    assert con.execute("SELECT count(DISTINCT route) FROM fact_waste_month").fetchone()[0] == 4


def test_source_row(con):
    assert con.execute("SELECT tier, system, approved FROM source").fetchall() == [(0, "Excel", False)]


def test_assumptions_config():
    a = load_assumptions()
    assert a["baselines"]["B_LOCAL"]["water_l_per_kg"] == 9.5
    assert [k for k, v in a["baselines"].items() if v["default"]] == ["B_LOCAL"]
    assert [r["id"] for r in a["register"]] == [f"A00{i}" for i in range(1, 9)] + ["T1", "T2"]
    assert a["sensitivity"]["low"] == {"baseline_factor": 0.85, "replacements_per_repair": 0.25}
