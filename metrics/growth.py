"""Growth opportunities: "work with Lindström more" (design §8b G7).

Sizes the extra value if the customer moves more to Lindström, from three levers the account
manager enters (`model.inputs_store.growth_inputs`):

- sites:   the customer's own current per-site averages × extra_sites;
- wearers: the customer's own current per-wearer averages × extra_wearers;
- line:<id> (a service line not yet used): typical kg/site/month from the service catalogue
  × (current sites + extra_sites) × 12, valued with the baseline's do-it-yourself washing cost
  per kg and the account's own savings (CO₂e, water) per washed kg.

Every figure is per year (period values × 12 / months in the period), ESTIMATED, and carries a
low/base/high range in the direction rule of design §8a.4 item 1 (low = the smallest benefit
for Lindström; the DIY cost, hours and savings it scales already follow that rule).
€, hours, CO₂e and water stay separate; `net` exists only when the account manager entered an
expansion price per site and year. The sizing is account-wide (review filters do not apply).
"""
from __future__ import annotations

from metrics.dto import HANDLING_LINE, compute_dto
from metrics.engine import SENSITIVITIES
from metrics.periods import period_months
from model.contracts import Lineage, MethodStatus, MetricResult, Provenance, Range, Scope
from model.inputs_store import GROWTH_PRICE_KEY, effective_inputs, growth_inputs

METRICS = {  # key -> (label, unit)
    "diy_cost_avoided": ("Do-it-yourself cost avoided", "EUR"),
    "staff_hours_freed": ("Staff hours freed", "h"),
    "co2_saving_kg": ("CO2e saving vs baseline", "kgCO2e"),
    "water_saving_l": ("Water saving vs baseline", "l"),
}
# human labels for formula texts
HUMAN = {"diy_cost_avoided": "do-it-yourself cost avoided", "staff_hours_freed": "staff hours freed",
         "co2_saving_kg": "CO2e saving", "water_saving_l": "water saving"}
ALREADY_USED = "already used by this customer"
OVERLAP_NOTE = ("Sites and employees may overlap — don't add the two levers if the new sites "
                "bring the new employees.")
PARTIAL = "(based on partial data)"
TAGS = {"diy_cost_avoided": "cost", "staff_hours_freed": "service",
        "co2_saving_kg": "emissions", "water_saving_l": "water"}
OPPOSITE = {"low": "high", "base": "base", "high": "low"}

Ends = dict[str, float | None]


def _ends(m: MetricResult | None) -> Ends:
    if m is None:
        return {e: None for e in SENSITIVITIES}
    if m.range is None:
        return {e: m.value for e in SENSITIVITIES}
    return {e: getattr(m.range, e) for e in SENSITIVITIES}


def _map(fn, *args: Ends) -> Ends:
    out = {}
    for e in SENSITIVITIES:
        xs = [a[e] for a in args]
        out[e] = None if any(x is None for x in xs) else fn(e, *xs)
    return out


def _sum(vals: list[Ends]) -> Ends:
    return {e: (None if not vals or any(v[e] is None for v in vals)
                else sum(v[e] for v in vals)) for e in SENSITIVITIES}


def _about(m: MetricResult, absolute: bool = False) -> str:
    from insights.story import _about as about  # the shared "about X (between A and B)"
    return about(m, absolute=absolute)


def compute_growth(engine, account_id: str, period: str, baseline_id: str, inputs: dict,
                   assumptions: dict, catalogue: list[dict],
                   sensitivity: str = "base") -> dict | None:
    """Growth levers for the account; None when no growth inputs are set.

    `inputs` is the stored inputs dict (`load_inputs`): the DIY inputs and the growth inputs.
    `sensitivity` picks each headline value from its range (like the KPIs).
    """
    g = growth_inputs(inputs)
    if g is None:
        return None
    months = period_months(period)
    per_year = 12 / len(months)
    res = engine.compute(account_id, period=period, baseline_id=baseline_id)
    spec = assumptions["dto_inputs"]
    eff = effective_inputs(inputs, spec)
    dto = compute_dto(engine, account_id, period, None, None, baseline_id, eff, assumptions,
                      results=res)
    by_key = {r["key"]: r for r in eff}
    lines = {x["id"]: x["diy"] for x in dto["lines"]}
    current = {"diy_cost_avoided": dto["diy_total"],
               "staff_hours_freed": dto["convenience"]["staff_hours_freed"],
               "co2_saving_kg": res.get("co2_saving_kg"),
               "water_saving_l": res.get("water_saving_l")}
    cur = {k: _ends(m) for k, m in current.items()}
    sites = res["sites"].value if res.get("sites") else None
    wearers = res["active_wearers"].value if res.get("active_wearers") else None
    kg = res["washed_kg"].value if res.get("washed_kg") else None
    price = g[GROWTH_PRICE_KEY]
    scope = Scope(node_id=account_id, level="ACCOUNT", period=period)
    cat = {c["id"]: c for c in catalogue}
    used_lines = {r[0] for r in engine.con.execute(
        "select distinct p.service_line from fact_service_month f "
        "join product p on p.product_id = f.product_id where f.customer_id = ? "
        "and p.service_line is not null", [account_id]).fetchall()}
    skipped = [{"id": cid, "reason": ALREADY_USED} for cid in g["extra_service_lines"]
               if cid in cat and cat[cid]["service_line"] in used_lines]
    skipped_ids = {x["id"] for x in skipped}
    partial = bool(dto["missing_lines"])
    notes = [OVERLAP_NOTE] if g["extra_sites"] and g["extra_wearers"] else []

    def result(mid: str, key: str, label: str, vals: Ends, assumption_ids: list[str],
               formula: str, lineage_from: MetricResult | None, unit: str | None = None):
        base = vals["base"]
        present = [x for x in vals.values() if x is not None]
        rng = None if base is None else Range(low=min(present), base=base, high=max(present))
        lin = lineage_from.lineage if lineage_from is not None else Lineage(
            facts=["fact_service_month"], rows=0, load_ids=[])
        value = None if rng is None else getattr(rng, sensitivity)
        return MetricResult(
            metric_id=mid, label=label, unit=unit or METRICS[key][1], scope=scope, value=value,
            range=rng, method_status=MethodStatus.ESTIMATED, provenance=Provenance.SYNTHETIC,
            confidence="Low", assumptions=list(dict.fromkeys(assumption_ids)), lineage=lin,
            formula_text=formula + " (per year)",
            priority_tags=[TAGS[key]],
            customer_facing=True)

    def lever(lid: str, label: str, vals: dict[str, Ends], charge: Ends | None,
              ids: dict[str, list[str]], formulas: dict[str, str], extra: dict | None = None):
        slug = lid.replace(":", "_")
        out = {"id": lid, "label": label, **(extra or {})}
        for key, (mlabel, _) in METRICS.items():
            out[key] = result(f"growth_{slug}_{key}", key, f"{mlabel} — {label}", vals[key],
                              ids[key], formulas[key], current[key])
        out["net"] = None
        if charge is not None:
            net = _map(lambda e, d, c: d - c, vals["diy_cost_avoided"], charge)
            out["net"] = result(f"growth_{slug}_net", "diy_cost_avoided",
                                f"Do-it-yourself cost avoided minus Lindström price — {label}",
                                net, ids["diy_cost_avoided"],
                                f"do-it-yourself cost avoided − {formulas['charge']}",
                                current["diy_cost_avoided"], unit="EUR")
        out["_vals"], out["_charge"] = vals, charge
        return out

    levers = []
    ids = {k: list(m.assumptions) if m is not None else [] for k, m in current.items()}
    if g["extra_sites"] and sites:
        n = g["extra_sites"]
        vals = {k: _map(lambda e, x: x / sites * n * per_year, v) for k, v in cur.items()}
        charge = None if price is None else {e: price * n for e in SENSITIVITIES}
        levers.append(lever(
            "sites", f"{n} more site{'s' if n != 1 else ''}", vals, charge, ids,
            {**{k: f"current {HUMAN[k]} ÷ {sites:g} sites × {n} extra sites × 12 / "
                   f"{len(months)} months" for k in METRICS},
             "charge": f"expansion price per site and year × {n}"}))
    if g["extra_wearers"] and wearers:
        n = g["extra_wearers"]
        # garment admin is driven by sites, not wearers: excluded from the per-wearer averages
        admin_eur = _ends(lines.get("admin"))
        admin_h = {e: sites * by_key["admin_h_per_site_month"]["value" if e == "base" else e]
                   * len(months) if sites else None for e in SENSITIVITIES}
        per_wearer_base = {
            **cur,
            "diy_cost_avoided": _map(lambda e, t, a: t - a, cur["diy_cost_avoided"], admin_eur),
            "staff_hours_freed": _map(lambda e, t, a: t - a, cur["staff_hours_freed"], admin_h)}
        vals = {k: _map(lambda e, x: x / wearers * n * per_year, v)
                for k, v in per_wearer_base.items()}
        # per-wearer price derived from the per-site price and current wearers per site
        charge = None if price is None or not sites else {
            e: price * sites / wearers * n for e in SENSITIVITIES}
        levers.append(lever(
            "wearers", f"{n:,} more employee{'s' if n != 1 else ''} on the service", vals,
            charge, ids,
            {**{k: f"current {HUMAN[k]}"
                   + (" excluding garment admin (driven by sites, not wearers)"
                      if k in ("diy_cost_avoided", "staff_hours_freed") else "")
                   + f" ÷ {wearers:g} active wearers × {n} extra wearers × 12 / "
                   f"{len(months)} months" for k in METRICS},
             "charge": f"expansion price per site and year × {sites:g} sites ÷ {wearers:g} "
                       f"wearers × {n}"}))
    for cid in g["extra_service_lines"]:
        c = cat.get(cid)
        if c is None or cid in skipped_ids or not sites or not kg:
            continue
        n_sites = sites + g["extra_sites"]
        tk, tp = c["typical_kg_per_site_month"], c["typical_price_eur_per_kg"]
        kg_line = {e: tk["default" if e == "base" else e] * n_sites * 12 for e in SENSITIVITIES}
        wash = _ends(lines.get("washing"))
        handling = HANDLING_LINE.get(baseline_id)
        h_per_kg = {e: (by_key["handling_min_per_kg"]["value" if e == "base" else e] / 60
                        if handling else 0.0) for e in SENSITIVITIES}
        vals = {
            "diy_cost_avoided": _map(lambda e, k, w: k * w / kg, kg_line, wash),
            "staff_hours_freed": _map(lambda e, k, h: k * h, kg_line, h_per_kg),
            "co2_saving_kg": _map(lambda e, k, s: k * s / kg, kg_line, cur["co2_saving_kg"]),
            "water_saving_l": _map(lambda e, k, s: k * s / kg, kg_line, cur["water_saving_l"]),
        }
        # the Lindström charge: the low (conservative) end uses the high price
        charge = None if price is None else {
            e: kg_line[e] * tp["default" if e == "base" else OPPOSITE[e]] for e in SENSITIVITIES}
        aid = c["assumption_id"]
        factor_ids = [aid] + (["T3"] if cid == "mats" else [])
        line_ids = {
            "diy_cost_avoided": [*(lines["washing"].assumptions if "washing" in lines else []),
                                 aid],
            "staff_hours_freed": ["A001", "T1", aid]
            + ([by_key["handling_min_per_kg"]["assumption_id"]] if handling else []),
            "co2_saving_kg": [*ids["co2_saving_kg"], *factor_ids],
            "water_saving_l": [*ids["water_saving_l"], *factor_ids]}
        kgf = (f"typical {tk['default']:g} kg/site/month ({aid}) × {n_sites:g} sites × 12 "
               "months")
        levers.append(lever(
            f"line:{cid}", f"Add {c['name']}", vals, charge, line_ids,
            {"diy_cost_avoided": f"{kgf} × do-it-yourself washing cost per kg of the baseline",
             "staff_hours_freed": f"{kgf} × handling min/kg ÷ 60" if handling else
             f"{kgf} × 0 (the baseline has no customer-side washing time)",
             "co2_saving_kg": f"{kgf} × the account's CO2e saving per washed kg",
             "water_saving_l": f"{kgf} × the account's water saving per washed kg",
             "charge": f"{kgf} × typical Lindström price per kg ({aid})"},
            extra={"service_line": c["service_line"],
                   "lindstrom_offer_url": c["lindstrom_offer_url"]}))
    extra = {"inputs": g, "skipped_lines": skipped, "partial": partial, "notes": notes}
    if not levers:  # e.g. every chosen line is already used: nothing to size
        return {**extra, "levers": [], "totals": None, "narrative_line": None,
                "statement": None, "what_to_say": None, "value_refs": []}

    totals = {}
    for key, (mlabel, _) in METRICS.items():
        totals[key] = result(
            f"growth_total_{key}", key, f"{mlabel} — all growth levers",
            _sum([lv["_vals"][key] for lv in levers]),
            [a for lv in levers for a in lv[key].assumptions],
            "sum over the growth levers", current[key])
    totals["net"] = None
    if price is not None and all(lv["net"] is not None for lv in levers):
        net = _sum([_map(lambda e, d, c: d - c, lv["_vals"]["diy_cost_avoided"], lv["_charge"])
                    for lv in levers])
        totals["net"] = result(
            "growth_total_net", "diy_cost_avoided",
            "Do-it-yourself cost avoided minus Lindström price — all growth levers", net,
            [a for lv in levers for a in lv["net"].assumptions],
            "sum over the growth levers of (cost avoided − Lindström price)",
            current["diy_cost_avoided"], unit="EUR")
    for lv in levers:
        del lv["_vals"], lv["_charge"]

    narrative = _narrative(levers, totals)
    if partial:
        narrative = narrative[:-1] + f" {PARTIAL}."
    what_to_say = ("These are estimates per year, scaled from your own current data; the extra "
                   "sites, employees and services are what we discussed — check they match "
                   "your plans.")
    if notes:
        what_to_say += " " + " ".join(notes)
    return {
        **extra,
        "levers": levers,
        "totals": totals,
        "narrative_line": narrative,
        # read by the customer story card (insights/story.py)
        "statement": narrative,
        "what_to_say": what_to_say,
        "value_refs": [m.metric_id for m in (totals["diy_cost_avoided"],
                                             totals["co2_saving_kg"]) if m.value is not None],
    }


def _narrative(levers: list[dict], totals: dict) -> str:
    """'Bringing {subject} on board would avoid about {range} a year in laundry and garment
    costs and save {co2 range}.' (design §8b G7, code-filled)."""
    parts = []
    for lv in levers:
        if lv["id"] == "sites":
            parts.append(lv["label"])
        elif lv["id"] == "wearers":
            parts.append(lv["label"].replace(" on the service", ""))
        else:
            parts.append(f"the {lv['label'][4:]} service")
    subject = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    diy, co2 = totals["diy_cost_avoided"], totals["co2_saving_kg"]
    line = f"Bringing {subject} on board"
    if diy.value is None:
        return line + " would extend the service; the cost effect cannot be sized from the data."
    line += f" would avoid {_about(diy)} a year in laundry and garment costs"
    if co2.value is not None and co2.value > 0:
        line += f" and save {_about(co2)}"
    if totals["net"] is not None and totals["net"].value is not None:
        word = "less" if totals["net"].value >= 0 else "more"
        line += (f"; including the Lindström price, the service would cost "
                 f"{_about(totals['net'], absolute=True)} {word} than doing it yourself")
    return line + "."

