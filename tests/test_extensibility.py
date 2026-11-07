"""Zero-code-change extensibility: a new service line, industry and country come from data and config only."""
import csv
import shutil
from pathlib import Path

import yaml

from api.build import build_review
from api.review_model import ReviewParams
from model.load import load_sources

ROOT = Path(__file__).resolve().parent.parent
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _activity(cust, site, laundry, product, month, kg):
    return [month, cust, site, laundry, product, 20, 22, 20, 60, 58, 100.0, kg, 0, "SYNTHETIC"]


def test_new_line_industry_country_without_code_changes(tmp_path, monkeypatch, pack_path):
    pack = tmp_path / "riga_pack"
    pack.mkdir()
    _write(pack / "laundries.csv", ["laundry_id", "laundry_name", "country"],
           [["L901", "Daugava Riga WWS", "Latvia"]])
    _write(pack / "laundry_resources.csv",
           ["laundry_id", "month", "washed_kg", "fresh_water_l", "process_energy_kwh",
            "process_emissions_kgco2e", "delivery_emissions_kgco2e"],
           [["L901", m, 6000, 18000, 4200, 900, 150] for m in MONTHS])
    _write(pack / "waste.csv",
           ["laundry_id", "month", "recycling_kg", "reuse_kg", "energy_recovery_kg", "incineration_kg"],
           [["L901", m, 60, 20, 30, 10] for m in MONTHS])
    _write(pack / "customers.csv",
           ["customer_id", "customer_name", "industry", "segment", "hq_country", "priority_topics",
            "data_status"],
           [["CUST901", "Riga Bistro Group", "Restaurants", "Mid", "Latvia",
             "Hygiene|Cost optimization", "SYNTHETIC"],
            ["CUST902", "Riga Cafe Co", "Restaurants", "Mid", "Latvia", "", "SYNTHETIC"]])
    _write(pack / "sites.csv",
           ["site_id", "customer_id", "site_name", "country", "city", "site_type",
            "primary_laundry_id", "data_status"],
           [["S901", "CUST901", "Bistro Old Town", "Latvia", "Riga", "Restaurant", "L901", "SYNTHETIC"],
            ["S902", "CUST901", "Bistro Harbour", "Latvia", "Riga", "Restaurant", "L901", "SYNTHETIC"],
            ["S903", "CUST902", "Cafe Central", "Latvia", "Riga", "Cafe", "L901", "SYNTHETIC"]])
    _write(pack / "products.csv",
           ["product_id", "product_name", "product_group", "service_line", "avg_weight_kg",
            "synthetic_product_footprint_kgco2e", "synthetic_purchase_cost_eur", "material_note"],
           [["P9001", "Washroom Towel Roll", "Washroom", "Washroom", 1.2, 4.0, 18, "synthetic"]])
    act_header = ["month", "customer_id", "site_id", "laundry_id", "product_id", "active_wearers",
                  "allocated_pieces", "active_assets_scanned", "washed_pieces", "packed_pieces",
                  "washing_pct", "customer_washed_kg", "service_requests", "data_status"]
    rows = []
    for m in MONTHS:
        for site in ("S901", "S902"):
            rows.append(_activity("CUST901", site, "L901", "P9001", m, 400.0))
            rows.append(_activity("CUST901", site, "L901", "P1002", m, 300.0))
        rows.append(_activity("CUST902", "S903", "L901", "P9001", m, 150.0))
        rows.append(_activity("CUST001", "S001", "L001", "P9001", m, 40.0))  # stays far below L001
    _write(pack / "service_activity.csv", act_header, rows)
    _write(pack / "service_cycles.csv",
           ["asset_id", "cycle_number", "customer_id", "site_id", "laundry_id", "product_id",
            "pickup_timestamp", "in_laundry_timestamp", "out_laundry_timestamp",
            "delivered_timestamp", "cycle_hours", "performance_flag", "data_status"],
           [[f"H901{i:03d}", 1, "CUST901", "S901", "L901", "P9001", f"{m}-10",
             f"{m}-10 13:00:00", f"{m}-11 13:00:00", f"{m}-12 13:00:00", 48, "ON_TIME",
             "SYNTHETIC"] for i, m in enumerate(MONTHS)])

    cfg_dir = tmp_path / "config"
    shutil.copytree(ROOT / "config", cfg_dir, ignore=shutil.ignore_patterns("__pycache__"))
    rules_path = cfg_dir / "industry_rules.yaml"
    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    rules["defaults"]["Restaurants"] = ["service", "cost"]
    rules["emphasis"]["Restaurants"] = "Highlight guest-facing hygiene for restaurants."
    rules_path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("VR_CONFIG_DIR", str(cfg_dir))

    sources = tmp_path / "sources.yaml"
    sources.write_text(yaml.safe_dump({"sources": [
        {"id": "excel_pack", "adapter": "excel", "path": str(pack_path)},
        {"id": "riga_pack", "adapter": "csv", "path": str(pack)}]}), encoding="utf-8")
    con = load_sources(sources)

    def review(**kw):
        return build_review(con, ReviewParams(**kw))

    r = review(account_id="CUST901")
    assert "Washroom" in r.meta.service_lines
    assert "Latvia" in r.meta.node.countries
    assert r.context.active_priorities[0] == "service"
    cafe = review(account_id="CUST902")  # no topics: priorities come from the Restaurants rule
    assert cafe.context.active_priorities == ["service", "cost"]
    assert cafe.context.priority_source == "industry"
    assert "restaurants" in cafe.context.industry_note
    monkeypatch.delenv("VR_CONFIG_DIR")  # negative control: the real config has no such rule
    assert review(account_id="CUST902").context.active_priorities != ["service", "cost"]
    monkeypatch.setenv("VR_CONFIG_DIR", str(cfg_dir))
    assert review(account_id="CUST001").meta.service_lines == ["Washroom", "Workwear"]
    assert review(account_id="CUST001", service_line="Washroom").meta.service_line == "Washroom"

    assert con.execute("select count(*) from quarantine").fetchone()[0] == 0
    c1 = {x[0] for x in con.execute("select entity_id from dq_flags where check_id = 'C1'").fetchall()}
    assert c1 == {"L003"}
