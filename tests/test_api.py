import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture(scope="module")
def client(pack_path):
    with TestClient(app) as c:
        yield c


def test_accounts(client):
    r = client.get("/accounts")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 3
    assert set(items[0]) == {"node_id", "name", "industry", "site_count"}
    assert {i["name"]: i["site_count"] for i in items}["NorthStar Foods Group"] == 24


def test_review_endpoint(client):
    r = client.get("/accounts/CUST001/review", params={"baseline": "B_HOME"})
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["node"]["name"] == "NorthStar Foods Group"
    assert body["meta"]["baseline"]["id"] == "B_HOME"


def test_review_params_and_priorities(client):
    r = client.get("/accounts/CUST001/review",
                   params={"priorities": "water,emissions", "sens": "high", "audience": "customer"})
    assert r.status_code == 200
    body = r.json()
    assert body["context"]["priority_source"] == "chips"
    assert body["context"]["active_priorities"] == ["water", "emissions"]
    assert body["meta"]["sensitivity"] == "high"


def test_review_unknown_account(client):
    assert client.get("/accounts/NOPE/review").status_code == 404


def test_review_empty_filter(client):
    r = client.get("/accounts/CUST002/review", params={"product": "P1004"})
    assert r.status_code == 200
    assert "NaN" not in r.text


def test_explain(client):
    r = client.get("/metrics/co2_saving_kg/explain", params={"node_id": "CUST001"})
    assert r.status_code == 200
    body = r.json()
    assert body["definition"]["id"] == "co2_saving_kg"
    assert body["result"]["formula_text"]
    assert "A003" in {a["id"] for a in body["assumptions"]}


def test_explain_unknown(client):
    assert client.get("/metrics/nope/explain", params={"node_id": "CUST001"}).status_code == 404
    assert client.get("/metrics/co2_saving_kg/explain", params={"node_id": "NOPE"}).status_code == 404


def test_data_quality(client):
    r = client.get("/data-quality", params={"account_id": "CUST002"})
    assert r.status_code == 200
    body = r.json()
    assert {"sources", "quarantine", "warnings"} <= set(body)
    assert any(w["check_id"] == "C1" and w["entity_id"] == "L003" for w in body["warnings"])


def test_data_quality_unknown(client):
    assert client.get("/data-quality", params={"account_id": "NOPE"}).status_code == 404


def test_config(client):
    a = client.get("/config/assumptions").json()
    assert "baselines" in a and "register" in a
    r = client.get("/config/modules")
    assert r.status_code == 200 and isinstance(r.json(), (list, dict))


def test_intent_hook(client):
    r = client.post("/intent", json={"text": "zzzz"})
    assert r.status_code == 200
    assert "interpretation_text" in r.json()


def test_export_pptx(client):
    r = client.post("/reviews/export", json={"account_id": "CUST001", "format": "pptx"})
    assert r.status_code == 200
    assert r.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    assert "review_CUST001_2025.pptx" in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_review_unicode(client):
    r = client.get("/accounts/CUST001/review")
    assert "Łódź" in r.text


def test_review_unknown_site(client):
    r = client.get("/accounts/CUST001/review", params={"site": "S999"})
    assert r.status_code == 422


def test_export_unknown_site(client):
    r = client.post("/reviews/export", json={"account_id": "CUST001", "site": "S999"})
    assert r.status_code == 422
    r = client.post("/reviews/export", json={"account_id": "CUST001", "sensitivity": "zzz"})
    assert r.status_code in (400, 422)


def test_review_hint_prompt(client):
    r = client.get("/accounts/CUST001/review", params={"priorities": "water", "hint": "prompt"})
    assert r.status_code == 200 and r.json()["context"]["priority_source"] == "prompt"
    assert client.get("/accounts/CUST001/review",
                      params={"priorities": "water", "hint": "bogus"}).status_code == 422


def test_intent_endpoint_keywords(client):
    r = client.post("/intent", json={"text": "Prepare five discussion points for Apex"})
    assert r.json()["node_id"] == "CUST002" and r.json()["view"] == "steering"
    assert client.post("/intent", json={"text": "hello there"}).json()[
        "interpretation_text"].startswith("Not recognised")


def test_explain_bad_period_is_422(client):
    r = client.get("/metrics/co2_saving_kg/explain", params={"node_id": "CUST001", "period": "bad"})
    assert r.status_code == 422


def test_unknown_priorities_are_dropped(client):
    r = client.get("/accounts/CUST001/review", params={"priorities": "water,bogus"})
    assert r.json()["context"]["active_priorities"] == ["water"]


def test_internal_metrics_endpoint(client):
    assert "idle_stock_value_eur" in client.get("/config/internal-metrics").json()


def test_inject_bad_rows_env(pack_path, monkeypatch):
    monkeypatch.setenv("VR_INJECT_BAD_ROWS", "1")
    with TestClient(app) as c:
        q = c.get("/data-quality", params={"account_id": "CUST001"}).json()["quarantine"]
    assert len(q) == 3


def test_missing_pack_names_env_var(monkeypatch):
    import asyncio

    from api.main import lifespan
    monkeypatch.setenv("VR_PACK_PATH", "no/such/pack.xlsx")

    async def enter():
        async with lifespan(app):
            pass
    with pytest.raises(RuntimeError, match="VR_PACK_PATH"):
        asyncio.run(enter())


def test_fit_config(client):
    """'Built on Lindström's work' page content (design §3): >= 8 asset rows, the brief map,
    and every PUBLIC_REFERENCE row links an http(s) source."""
    r = client.get("/config/fit")
    assert r.status_code == 200
    fit = r.json()
    assets = fit["assets"]
    assert len(assets) >= 8
    kinds = {"PUBLIC_REFERENCE", "DATA_PACK", "BRIEF"}
    for a in assets:
        assert {"asset", "today", "value_review", "brief_line", "source", "kind"} <= set(a)
        assert a["kind"] in kinds
    public = [a for a in assets if a["kind"] == "PUBLIC_REFERENCE"]
    assert public and all(a["source"].startswith(("https://", "http://")) for a in public)
    assert fit["brief_map"] and all({"asked", "where", "status"} <= set(b) for b in fit["brief_map"])
    assert "never calculation inputs" in fit["note"]

