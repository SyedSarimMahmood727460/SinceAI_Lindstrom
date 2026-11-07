"""The dashboard module registry (config/modules.json) only references known metrics."""
import json
import re
from pathlib import Path

from config.loader import CONFIG_DIR, load_yaml

PACKS = {"general", "sustainable", "financial"}
PAGES = {"story", "overview", "sites", "footprint", "circularity", "steering", "methodology", "readiness"}
COMPONENTS = {
    "kpi_row", "observations", "site_rank", "site_table", "site_detail", "footprint_cards",
    "footprint_pct_chart", "baseline_compare_chart", "repairs_month_chart", "repairs_type_chart",
    "waste_routes_chart", "exec_summary", "discussion_points", "action_table", "methodology",
    "assumption_table", "data_quality", "readiness_table", "story_cards",
}
WEB_DIR = Path(__file__).resolve().parents[1] / "web"


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


def test_story_is_the_landing_page():
    """The customer story (G9) is the first module, and the nav opens on it."""
    mods = _modules()
    assert mods[0]["page"] == "story" and mods[0]["component"] == "story_cards"
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    first_nav = re.search(r'<a data-v="([a-z_]+)"', html).group(1)
    assert first_nav == "story"


def test_components_are_implemented_in_web():
    """Every registry component has a renderer in web/modules.js, and every page a nav link."""
    js = (WEB_DIR / "modules.js").read_text(encoding="utf-8")
    body = js[js.index("const Components = {"):]
    defined = set(re.findall(r"^  ([a-z_]+)\(ctx\) \{", body, re.M))
    mods = _modules()
    assert {m["component"] for m in mods} <= defined
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    nav = set(re.findall(r'<a data-v="([a-z_]+)"', html))
    assert {m["page"] for m in mods} <= nav
