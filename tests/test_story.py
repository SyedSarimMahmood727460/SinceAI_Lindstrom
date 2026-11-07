"""Customer story cards, relatable comparisons and glossary (insights/story.py)."""
import re

from fastapi.testclient import TestClient

from api.build import build_review
from api.main import app
from api.review_model import ReviewParams
from config.loader import load_yaml
from export.format import fmt_value
from insights.story import CARD_ORDER, build_story

CARD_KEYS = {"id", "title", "statement", "relatable", "what_to_say", "detail_view", "value_refs"}


def test_story_cards_northstar(con):
    r = build_review(con, ReviewParams(account_id="CUST001"))
    ids = [c["id"] for c in r.story]
    assert ids == [i for i in CARD_ORDER if i in ids]
    assert "value_delivered" in ids and "growth" not in ids  # growth arrives with Task 6
    for c in r.story:
        assert set(c) == CARD_KEYS
        text = c["statement"] + (c["relatable"] or "")
        assert not re.search(r"\bNone\b|\bnan\b", text, re.I)
    assert r.story == build_story(r)


def test_story_uses_review_values(con):
    for sens in ("low", "base", "high"):
        r = build_review(con, ReviewParams(account_id="CUST001", sensitivity=sens))
        k = {x.metric_id: x for x in r.kpis}
        st = next(c for c in r.story if c["id"] == "value_delivered")["statement"]
        assert fmt_value(k["water_saving_l"]) in st or fmt_value(k["co2_saving_kg"]) in st
    d = next(c for c in r.story if c["id"] == "vs_diy")["statement"]
    assert fmt_value(r.dto.diy_total) in d and "(between " in d


def test_story_growth_card_when_present(con):
    r = build_review(con, ReviewParams(account_id="CUST001"))
    r.__dict__["growth"] = {"statement": "Wearers grew.", "value_refs": []}
    ids = [c["id"] for c in build_story(r)]
    assert ids.index("growth") == ids.index("biggest_improvement") + 1


def test_relatable_labelled(con):
    factors = load_yaml("relatable.yaml")
    assert {"household_water_year", "car_co2_year"} <= {f["id"] for f in factors}
    for f in factors:
        assert f["source_url"].startswith("https://") and f["factor"] > 0
        assert f["note"] == "illustrative comparison" and f["unit"]
    r = build_review(con, ReviewParams(account_id="CUST001"))
    rel = next(c for c in r.story if c["id"] == "value_delivered")["relatable"]
    assert rel.startswith("≈") and "illustrative" in rel
    assert all(c["relatable"] is None or c["relatable"].startswith("≈") for c in r.story)


def test_story_customer_audience(con):
    r = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    internal = {m for m, s in load_yaml("metrics.yaml").items()
                if not s.get("customer_facing", True)}
    assert internal
    for c in r.story:
        assert not internal & set(c["value_refs"])


def test_story_empty_filter(con):
    r = build_review(con, ReviewParams(account_id="CUST002", product="P1004"))
    assert isinstance(r.story, list)
    for c in r.story:
        assert "None" not in c["statement"]


def test_glossary_endpoint(pack_path):
    with TestClient(app) as c:
        r = c.get("/config/glossary")
    assert r.status_code == 200
    terms = {t["id"]: t for t in r.json()}
    assert {"baseline", "allocation", "scope3", "utilisation", "range_sensitivity", "estimate",
            "repair_handprint", "data_consistency_warning"} <= set(terms)
    assert all(len(t["definition"].split()) <= 30 for t in terms.values())


def _texts(story):
    return [c["statement"] + " " + c["what_to_say"] for c in story]


def test_story_no_expert_jargon(con):
    for acc, kw in (("CUST001", {}), ("CUST002", {}), ("CUST003", {}),
                    ("CUST001", {"audience": "customer"})):
        r = build_review(con, ReviewParams(account_id=acc, **kw))
        for t in _texts(r.story):
            assert "z =" not in t and "peer median" not in t and "z-score" not in t.lower()
    r = build_review(con, ReviewParams(account_id="CUST001"))
    c = next(c for c in r.story if c["id"] == "biggest_improvement")
    assert c["title"] == "Your biggest opportunity to improve"
    assert "typically about" in c["statement"] and c["what_to_say"].startswith("Shall we")


def test_story_vs_diy_partial_and_hours(con):
    r = build_review(con, ReviewParams(account_id="CUST001"))
    d = r.dto
    assert not d.missing_lines
    base = next(c for c in r.story if c["id"] == "vs_diy")["statement"]
    assert "partial" not in base
    assert re.search(r"\d h\b", base) and not re.search(r"\.\d h\b", base)
    stub = r.model_copy(update={"dto": d.model_copy(update={"missing_lines": ["admin"]})})
    label = next(x.label for x in d.lines if x.id == "admin").lower()
    st = next(c for c in build_story(stub) if c["id"] == "vs_diy")["statement"]
    assert f"(partial — no data for: {label})" in st


def test_story_no_redundant_unit_words(con):
    r = build_review(con, ReviewParams(account_id="CUST001"))
    st = next(c for c in r.story if c["id"] == "value_delivered")["statement"]
    assert "greenhouse gas" not in st and "CO2e of" not in st
