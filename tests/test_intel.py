"""Account intelligence (design §8b G8). No network: the Anthropic client is always a fake."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ai import intel, llm
from api.main import app
from config.loader import load_yaml

CATALOGUE = {c["id"] for c in load_yaml("service_catalogue.yaml")}
CLAIM_SECTIONS = ("direction", "sustainability", "trends")


@pytest.fixture(autouse=True)
def _cache_dir(monkeypatch, tmp_path):
    """Live results are cached in a temp dir: tests never write into the repo."""
    monkeypatch.setenv("VR_INTEL_CACHE_DIR", str(tmp_path / "intel_cache"))


class FakeClient:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _submit(report: dict):
    """A response whose final answer comes through the submit_report tool (after a web search)."""
    return SimpleNamespace(stop_reason="tool_use", content=[
        SimpleNamespace(type="server_tool_use", id="srv1", name="web_search",
                        input={"query": "Acme Oy strategy"}),
        SimpleNamespace(type="web_search_tool_result", tool_use_id="srv1", content=[]),
        SimpleNamespace(type="text", text="Submitting the report."),
        SimpleNamespace(type="tool_use", id="tu1", name=intel.SUBMIT_TOOL, input=report)])


def _claim(text, url="https://example.com/news", date="2026-01-15"):
    return {"text": text, "source_url": url, "source_date": date}


def _raw_report(**over):
    raw = {
        "direction": [_claim("Acme opened a new plant."),
                      _claim("Acme plans to double headcount.", url=""),
                      _claim("Acme is rumoured to merge.", url="not-a-url")],
        "sustainability": [_claim("Acme targets net zero by 2040.",
                                  url="https://acme.example/report.pdf")],
        "trends": [_claim("Food producers automate.", url="ftp://x.example/y")],
        "how_lindstrom_helps": [
            {"offer_id": "workwear", "offer_name": "Made-up name", "why": "Plant staff.",
             "based_on": ["https://example.com/news"]},
            {"offer_id": "jetpacks", "offer_name": "Jetpacks", "why": "Speed.", "based_on": []}],
        "conversation_starters": ["How is the new plant staffed?"],
        "sources": [{"url": "https://example.com/news", "title": "Acme news", "date": "2026-01-15"},
                    {"url": "javascript:alert(1)", "title": "bad", "date": "2026-01-01"}],
    }
    raw.update(over)
    return raw


def _live(monkeypatch, *outputs) -> FakeClient:
    fake = FakeClient(*outputs)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return fake


# --- snapshot ---
def test_snapshot_valid():
    rep = intel.load_snapshot("fazer-group")
    assert rep is not None and rep.mode == "snapshot" and rep.generated_at == "2026-11-07"
    assert rep.company == "Fazer Group" and rep.disclaimer == intel.DISCLAIMER
    claims = [c for s in CLAIM_SECTIONS for c in getattr(rep.sections, s)]
    assert claims and all(c.source_url.startswith(("http://", "https://")) for c in claims)
    assert all(c.source_date for c in claims)
    source_urls = {s.url for s in rep.sources}
    assert {c.source_url for c in claims} <= source_urls  # every cited source is listed
    assert len(rep.sources) >= 3
    assert all(s.url.startswith("https://") and s.title and s.date for s in rep.sources)
    assert 3 <= len(rep.sections.how_lindstrom_helps) <= 5
    assert {h.offer_id for h in rep.sections.how_lindstrom_helps} <= CATALOGUE
    assert all(set(h.based_on) <= source_urls for h in rep.sections.how_lindstrom_helps)
    assert len(rep.sections.conversation_starters) == 4
    for s in CLAIM_SECTIONS:
        assert 1 <= len(getattr(rep.sections, s)) <= 6


def test_list_snapshots():
    assert {"slug": "fazer-group", "company": "Fazer Group", "generated_at": "2026-11-07"} \
        in intel.list_snapshots()


def test_slug():
    assert intel.slugify("  Fazer Group ") == "fazer-group"
    assert intel.slugify("Oy Karl Fazer Ab!") == "oy-karl-fazer-ab"
    assert intel.slugify("../../etc") == "etc"


# --- live path (mocked client) ---
def test_live_path_drops_unsourced_claims(monkeypatch):
    fake = _live(monkeypatch, _submit(_raw_report()))
    rep = intel.research_company("Acme Oy", "https://acme.example", use_llm=True)
    assert rep.mode == "live" and rep.company == "Acme Oy" and rep.disclaimer == intel.DISCLAIMER
    assert [c.text for c in rep.sections.direction] == ["Acme opened a new plant."]
    assert rep.sections.trends == []  # ftp:// is not an http(s) source
    assert [c.source_url for c in rep.sections.sustainability] == ["https://acme.example/report.pdf"]
    urls = [s.url for s in rep.sources]
    assert "javascript:alert(1)" not in urls
    assert "https://acme.example/report.pdf" in urls  # a cited source is always listed
    # the request: the server web search tool plus submit_report, the model, a 60 s budget
    kw = fake.calls[0]
    assert kw["model"] == llm.MODEL == "claude-sonnet-5-5"
    assert intel.WEB_SEARCH_TOOL in kw["tools"]
    assert intel.WEB_SEARCH_TOOL == {"type": "web_search_20250305", "name": "web_search",
                                     "max_uses": 8}
    assert any(t.get("name") == intel.SUBMIT_TOOL and "input_schema" in t for t in kw["tools"])
    assert 0 < kw["timeout"] <= intel.TIMEOUT_S == 60
    assert "Acme Oy" in json.dumps(kw["messages"])


def test_live_path_drops_unknown_offer(monkeypatch):
    _live(monkeypatch, _submit(_raw_report()))
    rep = intel.research_company("Acme Oy", None, use_llm=True)
    helps = rep.sections.how_lindstrom_helps
    assert [h.offer_id for h in helps] == ["workwear"]
    assert helps[0].offer_name == "Workwear"  # the catalogue name, not the model's


def test_live_result_is_cached(monkeypatch, tmp_path):
    _live(monkeypatch, _submit(_raw_report()))
    intel.research_company("Acme Oy", None, use_llm=True)
    cached = tmp_path / "intel_cache" / "acme-oy.json"
    assert cached.exists()
    assert json.loads(cached.read_text(encoding="utf-8"))["mode"] == "live"
    # a second request within the cache window does not call the model again
    _live(monkeypatch, RuntimeError("must not be called"))
    assert intel.research_company("Acme Oy", None, use_llm=True).company == "Acme Oy"


def test_live_continues_after_pause_turn(monkeypatch):
    paused = SimpleNamespace(stop_reason="pause_turn", content=[
        SimpleNamespace(type="server_tool_use", id="srv1", name="web_search", input={"query": "q"})])
    fake = _live(monkeypatch, paused, _submit(_raw_report()))
    assert intel.research_company("Acme Oy", None, use_llm=True).mode == "live"
    assert len(fake.calls) == 2
    assert fake.calls[1]["messages"][-1]["role"] == "assistant"


def test_live_without_submit_asks_once_then_fails(monkeypatch):
    text_only = SimpleNamespace(stop_reason="end_turn",
                                content=[SimpleNamespace(type="text", text="Here is a summary.")])
    fake = _live(monkeypatch, text_only, _submit(_raw_report()))
    assert intel.research_company("Acme Oy", None, use_llm=True).mode == "live"
    assert fake.calls[1]["tool_choice"] == {"type": "tool", "name": intel.SUBMIT_TOOL}
    _live(monkeypatch, text_only, text_only)
    with pytest.raises(intel.IntelUnavailable):
        intel.research_company("Other Oy", None, use_llm=True)


def test_live_failure_falls_back_to_snapshot(monkeypatch):
    _live(monkeypatch, TimeoutError("slow"))
    rep = intel.research_company("Fazer Group", None, use_llm=True)
    assert rep.mode == "snapshot" and rep.generated_at == "2026-11-07"


def test_live_with_no_sourced_claims_is_a_failure(monkeypatch):
    raw = _raw_report(direction=[_claim("x", url="")], sustainability=[], trends=[])
    _live(monkeypatch, _submit(raw))
    with pytest.raises(intel.IntelUnavailable):
        intel.research_company("Acme Oy", None, use_llm=True)


# --- fallback and API ---
def test_fallback_to_snapshot_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("VR_AI", "on")
    monkeypatch.setattr(llm, "get_client", lambda: pytest.fail("no client without a key"))
    rep = intel.research_company("Fazer Group", None, use_llm=llm.use_llm())
    assert rep.mode == "snapshot"
    r = TestClient(app).post("/intel", json={"company": "fazer group"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "snapshot" and body["company"] == "Fazer Group"
    assert body["disclaimer"] == intel.DISCLAIMER and len(body["sources"]) >= 3


def test_unknown_company_without_key_503(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = TestClient(app).post("/intel", json={"company": "Imaginary Bakeries Oy",
                                             "website": "https://imaginary.example"})
    assert r.status_code == 503
    assert "Imaginary Bakeries Oy" in r.json()["detail"]
    assert "API key" in r.json()["detail"]


def test_intel_rejects_blank_company():
    assert TestClient(app).post("/intel", json={"company": "  "}).status_code == 422


def test_intel_snapshots_endpoint():
    r = TestClient(app).get("/intel/snapshots")
    assert r.status_code == 200
    assert {"slug": "fazer-group", "company": "Fazer Group", "generated_at": "2026-11-07"} \
        in r.json()
