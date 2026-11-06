"""The dashboard module registry (config/modules.json) only references known metrics."""
import json

from config.loader import CONFIG_DIR, load_yaml

PACKS = {"general", "sustainable", "financial"}
PAGES = {"overview", "sites", "footprint", "circularity", "steering", "methodology", "readiness"}
COMPONENTS = {
    "kpi_row", "observations", "site_rank", "site_table", "site_detail", "footprint_cards",
    "footprint_pct_chart", "baseline_compare_chart", "repairs_month_chart", "repairs_type_chart",
    "waste_routes_chart", "exec_summary", "discussion_points", "action_table", "methodology",
    "assumption_table", "data_quality", "readiness_table",
}


def _modules():
    return json.loads((CONFIG_DIR / "modules.json").read_text(encoding="utf-8"))


def test_modules_reference_known_metrics():
    registry = load_yaml("metrics.yaml")
    unknown = [(m["id"], mid) for m in _modules() for mid in m["required_metrics"]
               if mid not in registry]
    assert unknown == []


def test_modules_schema():
    mods = _modules()
    ids = [m["id"] for m in mods]
    assert len(ids) == len(set(ids))
    for m in mods:
        assert set(m) == {"id", "pack", "page", "required_metrics", "priority_tags",
                          "industries", "component"}, m["id"]
        assert m["pack"] in PACKS and m["page"] in PAGES and m["component"] in COMPONENTS
        assert m["industries"] == ["*"] or all(isinstance(i, str) for i in m["industries"])
