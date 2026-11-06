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


def test_export_not_wired(client):
    r = client.post("/reviews/export", json={"account_id": "CUST001", "format": "pptx"})
    assert r.status_code in (200, 501)


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_review_unicode(client):
    r = client.get("/accounts/CUST001/review")
    assert "Łódź" in r.text
