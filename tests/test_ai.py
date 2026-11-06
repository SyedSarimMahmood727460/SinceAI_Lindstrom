import json
from types import SimpleNamespace

import pytest

from api import build as build_mod
from ai import intent, llm, narrator
from ai.guard import check, render
from ai.templates import placeholder_values, template_narrative, wording_rules
from api.build import build_review
from api.review_model import ReviewParams

ACCOUNTS = [{"node_id": "CUST001", "name": "NorthStar Foods Group"},
            {"node_id": "CUST002", "name": "Apex Manufacturing"},
            {"node_id": "CUST003", "name": "Mediora Health"}]
BASELINES = {"B_LOCAL": {"name": "Outsourced local laundry"}, "B_HOME": {"name": "Home washing"},
             "B_INHOUSE": {"name": "In-house customer laundry"}}
BANNED = ["carbon neutral", "net zero", "CSRD-compliant", "audited", "verified", "guaranteed"]


@pytest.fixture(scope="module")
def review(con):
    return build_review(con, ReviewParams(account_id="CUST001"))


class FakeClient:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return SimpleNamespace(content=out if isinstance(out, list)
                               else [SimpleNamespace(type="text", text=out)])


def _good(review):
    oid = review.observations[0].id
    return json.dumps({
        "exec_summary": "{{account.name}} avoided {{co2_saving_kg.value}} vs {{baseline.name}} "
                        "(estimate). Priority: {{obs:%s}}." % oid,
        "discussion_points": ["Discuss {{obs:%s}}." % oid] * 5})


# --- guard ---
def test_guard_rejects_digits():
    assert check("Saved 255 t", set(), [])
    assert not check("Saved {{co2_saving_kg.base}}", {"co2_saving_kg.base"}, [])


def test_guard_rejects_banned():
    assert check("We are Carbon Neutral", set(), BANNED)


def test_guard_rejects_unknown_placeholder():
    assert check("{{made_up}}", {"x"}, [])


def test_wording_rules_file():
    assert wording_rules()["banned"] == BANNED


def test_render():
    assert render("A {{k}} B {{z}}", {"k": "1 t"}) == "A 1 t B {{z}}"


# --- templates / narrator ---
def test_template_narrative_contains_real_numbers(review):
    n = template_narrative(review)
    vals = placeholder_values(review)
    assert vals["co2_saving_kg.value"] in n.exec_summary
    assert n.generated_by == "template" and "{{" not in n.exec_summary
    assert len(n.exec_summary.split()) <= 120 and len(n.discussion_points) == 5
    assert not [v for v in check(n.exec_summary, set(), BANNED) if v.startswith("banned")]


def test_narrate_falls_back_without_key(monkeypatch, review):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("VR_AI", "on")
    assert llm.use_llm() is False
    assert narrator.narrate(review, llm.use_llm()).generated_by == "template"

    def boom():
        raise RuntimeError("no key")
    monkeypatch.setattr(llm, "get_client", boom)
    assert narrator.narrate(review, True).generated_by == "template"


def test_narrate_uses_llm_when_guard_passes(monkeypatch, review, tmp_path):
    fake = FakeClient(_good(review))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    n = narrator.narrate(review, True)
    assert n.generated_by == "llm" and "{{" not in n.exec_summary
    assert placeholder_values(review)["co2_saving_kg.value"] in n.exec_summary
    assert fake.calls[0]["model"] == "claude-sonnet-5-5" and fake.calls[0]["timeout"] <= 15
    assert "255" not in fake.calls[0]["messages"][0]["content"]  # no computed numbers sent
    logged = json.loads((tmp_path / "logs" / f"{review.meta.run_id}.json").read_text("utf-8"))
    assert logged["generated_by"] == "llm"


def test_narrate_retries_once_then_accepts(monkeypatch, review):
    fake = FakeClient("Saved 999 t", _good(review))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    assert narrator.narrate(review, True).generated_by == "llm" and len(fake.calls) == 2


def test_narrate_rejects_llm_digits(monkeypatch, review):
    fake = FakeClient("Saved 999 t", "Saved 999 t")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    n = narrator.narrate(review, True)
    assert n.generated_by == "template" and "999" not in n.exec_summary and len(fake.calls) == 2


def test_narrate_rejects_banned_and_bad_count(monkeypatch, review):
    bad = json.dumps({"exec_summary": "We are carbon neutral.", "discussion_points": ["a"] * 5})
    few = json.dumps({"exec_summary": "Fine.", "discussion_points": ["a"] * 3})
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(bad, few))
    assert narrator.narrate(review, True).generated_by == "template"


def test_no_log_without_llm(review, tmp_path):
    narrator.narrate(review, False)
    assert not (tmp_path / "logs").exists()


# --- intent ---
def test_intent_keywords():
    v = intent.keyword_intent("Focus on water and emissions, compare with home washing",
                              ACCOUNTS, BASELINES)
    assert v.priorities == ["water", "emissions"]
    assert v.baseline_id == "B_HOME" and v.view == "footprint"
    assert v.interpretation_text.startswith("Understood")


def test_intent_customer():
    v = intent.keyword_intent("Prepare five discussion points for Apex", ACCOUNTS, BASELINES)
    assert v.node_id == "CUST002" and v.view == "steering"


def test_intent_allocation_is_not_local_baseline():
    v = intent.keyword_intent("cost allocation", ACCOUNTS, BASELINES)
    assert v.priorities == ["cost"] and v.baseline_id is None


def test_intent_unrecognised():
    v = intent.keyword_intent("hello there", ACCOUNTS, BASELINES)
    assert v.priorities == [] and v.view is None and v.node_id is None
    assert v.interpretation_text.startswith("Not recognised")


def _tool_use(**inp):
    return [SimpleNamespace(type="tool_use", name="set_view", input=inp)]


def test_parse_intent_llm_drops_unknown_ids(monkeypatch):
    fake = FakeClient(_tool_use(node_id="CUST999", priorities=["water", "luck"],
                                baseline_id="B_X", view="steering"))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    v = intent.parse_intent("water please", ACCOUNTS, BASELINES, True)
    assert v.node_id is None and v.priorities == ["water"] and v.baseline_id is None
    assert v.view == "steering" and fake.calls[0]["tool_choice"]["name"] == "set_view"


def test_parse_intent_llm_nothing_recognised(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(_tool_use(node_id="X")))
    assert intent.parse_intent("zzz", ACCOUNTS, BASELINES, True) \
        .interpretation_text.startswith("Not recognised")


def test_parse_intent_falls_back_on_error(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(TimeoutError("slow")))
    v = intent.parse_intent("focus on water", ACCOUNTS, BASELINES, True)
    assert v.priorities == ["water"]
    assert intent.parse_intent("focus on water", ACCOUNTS, BASELINES, False).priorities == ["water"]


# --- fix round 1 ---
def test_guard_allows_named_numerals():
    ok = {"baseline.name"}
    assert not check("CO2 savings vs {{baseline.name}}", ok, BANNED)
    assert not check("CO₂e and co2e, Scope 3 evidence", ok, BANNED)
    assert check("saved 3 t", ok, BANNED)
    assert check("Scope 4 evidence", ok, BANNED)


def test_guard_rejects_number_words():
    assert check("emissions halved", set(), BANNED)
    assert check("three sites", set(), BANNED)
    assert check("A Quarter of sites", set(), BANNED)
    assert not check("alone, someone, phone and ones", set(), BANNED)


def test_strip_digits_keeps_co2():
    assert narrator._strip_digits("CO2 up 12 at Scope 3 site") == "CO2 up  at Scope 3 site".replace("  ", " ")


def test_retry_feeds_violations_back(monkeypatch, review):
    bad = json.dumps({"exec_summary": "Saved 999 t", "discussion_points": ["a"] * 5})
    fake = FakeClient(bad, _good(review))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    narrator.narrate(review, True)
    first, second = fake.calls[0]["messages"], fake.calls[1]["messages"]
    assert len(first) == 1 and len(second) == 3
    assert second[1] == {"role": "assistant", "content": bad}
    assert "digits outside placeholders" in second[2]["content"]


def test_llm_narrative_cached_per_run_id(monkeypatch, con):
    build_mod._NARRATIVES.clear()
    monkeypatch.setattr(llm, "use_llm", lambda: True)
    params = ReviewParams(account_id="CUST001")
    fake = FakeClient(_good(build_review(con, params)))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    a = build_review(con, params, use_ai=True)
    b = build_review(con, params, use_ai=True)
    assert a.narrative.generated_by == b.narrative.generated_by == "llm" and len(fake.calls) == 1
    build_mod._NARRATIVES.clear()


def test_template_omits_missing_metric_clause(review):
    k = [x.model_copy(update={"value": None, "range": None}) if x.metric_id == "co2_saving_kg"
         else x for x in review.kpis]
    n = template_narrative(review.model_copy(update={"kpis": k}))
    assert "n/a" not in n.exec_summary and "CO₂e" not in n.exec_summary.split(chr(10) * 2)[1]


def test_template_value_follows_sensitivity(con):
    hi = build_review(con, ReviewParams(account_id="CUST001", sensitivity="high"))
    vals = placeholder_values(hi)
    assert vals["co2_saving_kg.value"] == vals["co2_saving_kg.high"] != vals["co2_saving_kg.base"]
    assert vals["co2_saving_kg.value"] in template_narrative(hi).exec_summary


def test_parse_intent_empty_tool_input_uses_keywords(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(_tool_use()))
    assert intent.parse_intent("focus on water", ACCOUNTS, BASELINES, True).priorities == ["water"]


def test_levers_exclude_value_headline_and_data_caveat(review):
    vals = placeholder_values(review)
    titles = {o.title.split(":")[0] for o in review.observations if o.rule_id in ("R7", "R8")}
    assert "lever.1" in vals and vals["lever.1"] not in titles
    assert vals.get("lever.2") not in titles
    text = template_narrative(review).exec_summary
    for t in titles:
        assert t not in text.split("\n\n")[-1]


def test_single_lever_uses_singular_and_none_omits(review):
    one = review.model_copy(update={"observations": [
        o for o in review.observations if o.rule_id in ("R7", "R8", "R2")]})
    assert "improvement lever for next year is" in template_narrative(one).exec_summary
    none = review.model_copy(update={"observations": [
        o for o in review.observations if o.rule_id in ("R7", "R8")]})
    assert "improvement lever" not in template_narrative(none).exec_summary


def test_baseline_named_once_per_sentence(review):
    p2 = template_narrative(review).exec_summary.split("\n\n")[1]
    assert p2.count(review.meta.baseline["name"]) == 1


def test_internal_metrics_never_placeholders(con):
    kam = build_review(con, ReviewParams(account_id="CUST002", audience="kam"))
    assert any(k.metric_id == "idle_stock_value_eur" for k in kam.kpis)
    assert not any(key.startswith("idle_stock_value_eur") for key in placeholder_values(kam))


def test_intent_word_boundaries():
    for q in ("calculate the totals", "Europe overview"):
        assert intent.keyword_intent(q, ACCOUNTS, BASELINES).priorities == []
    assert intent.keyword_intent("recycling and utilisation", ACCOUNTS, BASELINES).priorities \
        == ["cost", "circularity"]
    assert intent.keyword_intent("circular service", ACCOUNTS, BASELINES).priorities \
        == ["circularity"]
    assert intent.keyword_intent("late deliveries", ACCOUNTS, BASELINES).priorities == ["service"]
