import pytest

from config.loader import load_assumptions, load_yaml
from insights.discussion import action_rows, discussion_points
from insights.priorities import resolve_priorities
from insights.rules import build_observations
from metrics.engine import Engine

ACCOUNTS = {"CUST001": "NorthStar Foods Group", "CUST002": "Apex Industrial Systems",
            "CUST003": "Mediora Health Network"}


@pytest.fixture(scope="module")
def engine(con):
    return Engine(con, load_assumptions(), load_yaml("metrics.yaml"))


def _topics(con, account_id):
    row = con.execute("select industry, priority_topics from org_node where node_id = ?",
                      [account_id]).fetchone()
    return row[0], list(row[1])


@pytest.fixture(scope="module")
def inputs(con, engine):
    out = {}
    for acc in ACCOUNTS:
        sm = engine.site_metrics(acc)
        names = dict(con.execute("select node_id, name from org_node where level = 'SITE'").fetchall())
        industry, topics = _topics(con, acc)
        out[acc] = dict(account_id=acc, account_metrics=engine.compute(acc), site_metrics=sm,
                        site_names=names, laundry_stats=engine.laundry_stats(acc),
                        industry=industry, baseline_name="Local washing", topics=topics)
    return out


def _obs(inputs, acc, priorities=None, **over):
    args = {k: v for k, v in inputs[acc].items() if k != "topics"}
    args["priorities"] = priorities or resolve_priorities(inputs[acc]["topics"], args["industry"])[0]
    args.update(over)
    return build_observations(**args)


def test_default_priorities(inputs):
    n = inputs["CUST001"]
    assert resolve_priorities(n["topics"], n["industry"]) == (["water", "service", "emissions"], "customer")
    a = inputs["CUST002"]
    assert resolve_priorities(a["topics"], a["industry"])[0][:3] == ["cost", "circularity", "service"]
    m = inputs["CUST003"]
    assert resolve_priorities(m["topics"], m["industry"])[0] == ["service", "emissions"]
    got, src = resolve_priorities(n["topics"], n["industry"], prompt=["emissions"])
    assert src == "prompt" and got[0] == "emissions"
    got, src = resolve_priorities(n["topics"], n["industry"], chips=["cost"])
    assert src == "chips" and got[0] == "cost"
    assert resolve_priorities([], "Food & Beverage") == (["service", "water"], "industry")


def test_northstar_rules(inputs):
    obs = {o.rule_id: o for o in _obs(inputs, "CUST001")}
    assert obs["R2"].node_id == "S022"
    assert obs["R1"].node_id == "S018"
    assert "Vistula Warsaw WWS" in obs["R4"].finding + obs["R4"].title
    assert all("nan" not in (o.title + o.finding).lower() for o in obs.values())
    assert obs["R7"].node_id == "CUST001"


def test_r8_fires_for_l003_accounts(inputs):
    assert any(o.rule_id == "R8" for o in _obs(inputs, "CUST001"))
    assert any(o.rule_id == "R8" for o in _obs(inputs, "CUST002"))
    assert not any(o.rule_id == "R8" for o in _obs(inputs, "CUST003"))


def test_r4_not_fired_single_laundry(inputs):
    assert not any(o.rule_id == "R4" for o in _obs(inputs, "CUST002"))


def test_rules_need_three_sites(inputs):
    d = inputs["CUST001"]
    two = dict(list(d["site_metrics"].items())[:2])
    obs = _obs(inputs, "CUST001", site_metrics=two)
    assert not {o.rule_id for o in obs} & {"R1", "R2", "R3", "R5", "R6"}
    assert any(o.rule_id == "R7" for o in obs)
    assert _obs(inputs, "CUST001", site_metrics={}) is not None


def test_priority_changes_order(inputs):
    assert "cost" in _obs(inputs, "CUST001", ["cost"])[0].tags
    assert "service" in _obs(inputs, "CUST001", ["service"])[0].tags


def test_discussion_points_five(inputs):
    obs = _obs(inputs, "CUST001")
    pts = discussion_points(obs)
    assert len(pts) == 5 and "baseline" in pts[-1]


def test_action_rows(inputs):
    d = inputs["CUST001"]
    obs = _obs(inputs, "CUST001")
    rows = action_rows(obs, d["account_metrics"], d["site_metrics"])
    assert len(rows) == 3
    assert [r["owner"] for r in rows] == ["KAM + site manager", "Service owner", "Lindström laundry"]
    assert all(r["target_2026"] is None and r["kpi_metric_id"] for r in rows)
    assert rows[0]["kpi_metric_id"] == obs[0].evidence[0][0]


def test_sorted_by_score(inputs):
    obs = _obs(inputs, "CUST001")
    assert [o.score for o in obs] == sorted((o.score for o in obs), reverse=True)
