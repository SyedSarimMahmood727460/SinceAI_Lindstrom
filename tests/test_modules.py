"""The dashboard module registry (config/modules.json) only references known metrics."""
import json
import re
from pathlib import Path

from config.loader import CONFIG_DIR, load_yaml

PACKS = {"general", "sustainable", "financial"}
PAGES = {"meeting", "overview", "sites", "footprint", "circularity", "steering", "methodology", "readiness",
         "vs_diy", "growth", "intel", "fit"}
COMPONENTS = {
    "kpi_row", "observations", "site_rank", "site_table", "site_detail", "footprint_cards",
    "footprint_pct_chart", "baseline_compare_chart", "repairs_month_chart", "repairs_type_chart",
    "waste_routes_chart", "exec_summary", "discussion_points", "action_table", "methodology",
    "assumption_table", "data_quality", "readiness_table", "meeting_flow",
    "diy_compare", "diy_cost_chart", "diy_inputs", "growth_inputs", "growth_levers", "intel_page",
    "fit_page",
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


def test_meeting_is_the_landing_page():
    """The guided meeting flow is the first module, and the nav opens on it."""
    mods = _modules()
    assert mods[0]["page"] == "meeting" and mods[0]["component"] == "meeting_flow"
    assert "story" not in {m["page"] for m in mods}
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    first_nav = re.search(r'<a data-v="([a-z_]+)"', html).group(1)
    assert first_nav == "meeting"
    app = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert re.search(r"view: 'meeting'", app)


def test_header_has_settings_ask_and_disclaimer_strip():
    """The calm header: Settings and Ask toggles (buttons with aria-expanded), one-line disclaimer strip."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    for el in ("settingsBtn", "settingsPanel", "askBtn", "askPanel", "disclaimerStrip"):
        assert f'id="{el}"' in html, el
    for btn in ("settingsBtn", "askBtn"):
        tag = re.search(rf'<button[^>]*id="{btn}"[^>]*>', html).group(0)
        assert 'aria-expanded="false"' in tag and "aria-controls" in tag, btn
    strip = re.search(r'id="disclaimerStrip"[^>]*>([^<]*)<', html).group(1)
    assert strip == "Prototype · synthetic data · not audited"
    settings = html[html.index('id="settingsPanel"'):]
    settings = settings[:settings.index('id="exportBtn"')]
    for ctl in ('id="product"', 'id="sline"', 'id="sens"', 'id="aud"', 'id="mode"'):
        assert ctl in settings, ctl
    ask = html[html.index('id="askPanel"'):]
    for ctl in ('id="q"', 'id="pchips"', 'id="interp"'):
        assert ctl in ask, ctl


def test_nav_groups():
    """Meeting · Before the meeting (KAM only) · Detail · Trust; every page keeps a nav link."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    nav = html[html.index('<nav'):html.index('</nav>')]
    order = re.findall(r'<div class="sub[^"]*">([^<]+)</div>|<a data-v="([a-z_]+)"', nav)
    flat = [a or b for a, b in order]
    assert flat == ["meeting", "Before the meeting", "intel",
                    "Detail", "overview", "sites", "vs_diy", "growth", "footprint", "circularity", "steering",
                    "Trust", "fit", "methodology", "readiness"]
    assert re.search(r'<a data-v="intel"[^>]*class="[^"]*kam-only', nav)
    assert re.search(r'<div class="sub[^"]*kam-only[^"]*">Before the meeting', nav)


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


def _meeting_js() -> str:
    """The meeting-flow code in web/modules.js: from the step helpers to the end of meeting_flow."""
    js = (WEB_DIR / "modules.js").read_text(encoding="utf-8")
    start = js.index("// ---------- guided meeting flow")
    end = js.index("  // Customer story (G9)")
    return js[start:end]


def test_meeting_customer_hides_controls():
    """Customer view: every edit control in the meeting flow (Your numbers form, demo button,
    growth form, target inputs) sits behind an audience guard, marked /* kam-only */."""
    code = _meeting_js()
    assert re.search(r"const isCustomer = ctx\.S\.audience === 'customer'", code)
    for control in ("diy_inputs", "demo", "growth_inputs", "targets"):
        lines = [ln for ln in code.splitlines() if f"/* kam-only: {control} */" in ln]
        assert lines, f"no kam-only guard for {control}"
        for ln in lines:
            assert "isCustomer" in ln, ln
    # nothing outside a guarded line renders those controls
    for ln in code.splitlines():
        if "kam-only" in ln:
            continue
        assert "Components.diy_inputs" not in ln and "Components.growth_inputs" not in ln, ln
        assert 'data-action="demo"' not in ln and "<input" not in ln, ln
    # step 4 drops out of the customer's step bar when there is no growth to show
    assert re.search(r"isCustomer && !hasGrowth", code)
