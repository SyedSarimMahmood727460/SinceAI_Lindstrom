"""Service vs do-it-yourself comparison (design §8a, decisions §8a.4).

What the customer would spend doing it themselves under the selected baseline, line by line,
in EUR, plus the staff hours the service frees (kept separate: €, hours and CO₂ are never
summed). Every figure is ESTIMATED with a low/base/high range:

- low  = the cheapest DIY case: every input at the end that minimises DIY cost (its low; for
  garment life the longest life) and the low sensitivity (baseline factor ×0.85, which also
  scales the kWh/kg and l/kg used in the washing formula; 0.25 replacements per repair);
- high = the opposite; base = the entered/default values and the base sensitivity.

A value the account manager entered is fixed across the three ends unless a range was given
(see `model.inputs_store.effective_inputs`).
"""
from __future__ import annotations

from metrics.engine import SENSITIVITIES
from metrics.frames import base_frames
from metrics.periods import period_months
from model.contracts import Lineage, MethodStatus, MetricResult, Provenance, Range, Scope

# Inputs where a larger value makes doing it yourself cheaper.
INVERSE = {"garment_life_years_no_repair"}
# Baselines whose washing happens on the customer's side, and the name of the time line.
HANDLING_LINE = {"B_INHOUSE": ("staff_handling", "Staff washing & handling time"),
                 "B_HOME": ("employee_time", "Employee time (if washing happens on paid time)")}
HYGIENE_INDUSTRIES = {"Food & Beverage", "Healthcare"}
HYGIENE_NOTE = ("Industrial laundering gives process control that home washing cannot — "
                "context, not compliance advice.")
BASE_ASSUMPTIONS = ["A001", "T1"]
CONTRACT_KEY = "contract_price_eur_per_year"


def _base(m: MetricResult | None) -> float | None:
    if m is None:
        return None
    return m.range.base if m.range is not None and m.range.base is not None else m.value


def _total(vals: list[float | None]) -> float | None:
    present = [v for v in vals if v is not None]
    return sum(present) if present else None


def compute_dto(engine, account_id: str, period: str, product: str | None,
                service_line: str | None, baseline_id: str, inputs: list[dict],
                assumptions: dict, results: dict[str, MetricResult] | None = None) -> dict:
    """The DIY comparison for one account/period/filter and the selected baseline.

    `inputs` are effective inputs (`effective_inputs`); `results` may pass the engine results
    already computed for the same scope (saves a second engine run).
    """
    months = period_months(period)
    n_months = len(months)
    res = results if results is not None else engine.compute(
        account_id, period=period, product=product, baseline_id=baseline_id,
        service_line=service_line)
    frames = base_frames(engine.con, account_id, months, product, service_line)
    act, rep = frames["activity"], frames["repairs"]
    baseline = assumptions["baselines"][baseline_id]
    by_key = {r["key"]: r for r in inputs}

    def inp(key: str, end: str) -> float:
        if key in INVERSE and end != "base":
            end = "high" if end == "low" else "low"
        return by_key[key]["value" if end == "base" else end]

    def aid(*keys: str) -> list[str]:
        return BASE_ASSUMPTIONS + [by_key[k]["assumption_id"] for k in keys]

    kg = _base(res.get("washed_kg"))
    sites = _base(res.get("sites"))
    garments = _base(res.get("garments_allocated"))
    # weighted purchase cost by period-end allocated pieces per product (§8a.4 item 3)
    wcost = None
    if len(act):
        last = act[(act.month == months[-1]) & act.purchase_cost_eur.notna()]
        if last.allocated_pieces.sum() > 0:
            wcost = float((last.allocated_pieces * last.purchase_cost_eur).sum()
                          / last.allocated_pieces.sum())
    repair_cost = None
    if len(rep) and (rep.repair_count * rep.purchase_cost_eur).notna().any():
        repair_cost = float((rep.repair_count * rep.purchase_cost_eur).sum())

    handling = HANDLING_LINE.get(baseline_id)
    lines: dict[str, dict[str, float | None]] = {}
    hours: dict[str, float | None] = {}
    for end in SENSITIVITIES:
        s, r = engine._sens(end)
        labour = inp("labour_eur_per_h", end)
        v: dict[str, float | None] = {}
        v["garment_purchases"] = (
            None if garments is None or wcost is None
            else garments * wcost / inp("garment_life_years_no_repair", end) * n_months / 12)
        v["extra_replacements"] = None if repair_cost is None else repair_cost * r
        if kg is None:
            v["washing"] = None
        elif baseline_id == "B_LOCAL":
            v["washing"] = kg * inp("local_laundry_eur_per_kg", end)
        else:
            v["washing"] = kg * (
                baseline["energy_kwh_per_kg"] * s * inp("energy_eur_per_kwh", end)
                + baseline["water_l_per_kg"] * s / 1000 * inp("water_eur_per_m3", end)
                + inp("detergent_eur_per_kg", end))
        handling_h = None
        if handling is not None:
            handling_h = None if kg is None else kg * inp("handling_min_per_kg", end) / 60
            v[handling[0]] = None if handling_h is None else handling_h * labour
        admin_h = None if sites is None else sites * inp("admin_h_per_site_month", end) * n_months
        v["admin"] = None if admin_h is None else admin_h * labour
        v["diy_total"] = _total(list(v.values()))
        hours[end] = _total([handling_h, admin_h])
        for k, x in v.items():
            lines.setdefault(k, {})[end] = x

    price = by_key[CONTRACT_KEY]["value"]
    contract = {e: None if price is None else by_key[CONTRACT_KEY][
        "value" if e == "base" else e] * n_months / 12 for e in SENSITIVITIES}
    net = {e: None if contract[e] is None or lines["diy_total"][e] is None
           else lines["diy_total"][e] - contract[e] for e in SENSITIVITIES}

    scope = Scope(node_id=account_id, level="ACCOUNT", period=period, product=product)
    act_ids = sorted(set(act.load_id.dropna())) if len(act) else []
    rep_ids = sorted(set(rep.load_id.dropna())) if len(rep) else []

    def result(mid, label, unit, vals, assumption_ids, formula, facts, tags=("cost",)):
        base = vals["base"]
        present = [x for x in vals.values() if x is not None]
        rows = (len(act) if "fact_service_month" in facts else 0) + (
            len(rep) if "fact_repair_month" in facts else 0)
        load_ids = sorted({*(act_ids if "fact_service_month" in facts else []),
                           *(rep_ids if "fact_repair_month" in facts else [])})
        return MetricResult(
            metric_id=f"dto_{mid}", label=label, unit=unit, scope=scope, value=base,
            range=None if base is None else Range(low=min(present), base=base, high=max(present)),
            method_status=MethodStatus.ESTIMATED, provenance=Provenance.SYNTHETIC,
            confidence="Low", assumptions=list(dict.fromkeys(assumption_ids)),
            lineage=Lineage(facts=list(facts), rows=rows, load_ids=load_ids),
            formula_text=formula, priority_tags=list(tags), customer_facing=True)

    m12 = f"× {n_months}/12"
    washing_ids = (aid("local_laundry_eur_per_kg") if baseline_id == "B_LOCAL" else
                   aid("energy_eur_per_kwh", "water_eur_per_m3", "detergent_eur_per_kg"))
    washing_formula = (
        "washed_kg × local laundry price (T4)" if baseline_id == "B_LOCAL" else
        f"washed_kg × ({baseline['name']} kWh/kg × s × energy price (T5) + l/kg × s ÷ 1000 × "
        "water price (T6) + detergent (T7)); s = baseline sensitivity factor (T1)")
    spec = [
        ("garment_purchases", "Garment purchases",
         aid("garment_life_years_no_repair"),
         f"garments allocated (period end) × weighted purchase cost ÷ garment life without "
         f"repair (T11) {m12}", ["fact_service_month", "product"]),
        ("extra_replacements", "Extra replacements without repairs",
         BASE_ASSUMPTIONS + ["A002"],
         "Σ over products of repairs × replacements per repair (T1) × product purchase cost",
         ["fact_repair_month", "product"]),
        ("washing", "Washing cost", washing_ids, washing_formula, ["fact_service_month"]),
    ]
    if handling is not None:
        spec.append((handling[0], handling[1], aid("handling_min_per_kg", "labour_eur_per_h"),
                     "washed_kg × handling min/kg (T9) ÷ 60 × staff cost (T8)",
                     ["fact_service_month"]))
    spec.append(("admin", "Garment admin", aid("admin_h_per_site_month", "labour_eur_per_h"),
                 f"sites with activity × admin h/site/month (T10) × {n_months} months × "
                 "staff cost (T8)", ["fact_service_month"]))
    line_results = [{"id": lid, "label": label,
                     "diy": result(lid, label, "EUR", lines[lid], ids, formula, facts)}
                    for lid, label, ids, formula, facts in spec]
    all_ids = [a for x in line_results for a in x["diy"].assumptions]
    all_facts = list(dict.fromkeys(f for *_, facts in spec for f in facts))
    diy_total = result("diy_total", "Do-it-yourself total", "EUR", lines["diy_total"], all_ids,
                       "sum of the do-it-yourself cost lines above", all_facts)
    contract_r = None if price is None else result(
        "contract_price", "Lindström contract price", "EUR", contract, [],
        f"contract price per year (entered by the account manager) {m12}", [])
    net_r = None if price is None else result(
        "net", "Do-it-yourself cost minus Lindström contract price", "EUR", net, all_ids,
        "do-it-yourself total − contract price", all_facts)
    hours_ids = (aid("handling_min_per_kg", "admin_h_per_site_month") if handling
                 else aid("admin_h_per_site_month"))
    staff_hours = result(
        "staff_hours_freed", "Staff hours freed", "h", hours, hours_ids,
        ("washed_kg × handling min/kg ÷ 60 + " if handling else "")
        + f"sites × admin h/site/month × {n_months} months", ["fact_service_month"],
        tags=("service",))

    industry = engine.con.execute("select industry from org_node where node_id = ?",
                                  [account_id]).fetchone()
    return {
        "baseline": baseline_id,
        "inputs": inputs,
        "lines": line_results,
        "diy_total": diy_total,
        "contract_price": contract_r,
        "net": net_r,
        "convenience": {"staff_hours_freed": staff_hours,
                        **{k: res.get(k) for k in
                           ("on_time_rate", "utilisation", "service_requests_per_100w")}},
        "hygiene_note": HYGIENE_NOTE if industry and industry[0] in HYGIENE_INDUSTRIES else None,
    }
