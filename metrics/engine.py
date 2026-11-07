"""Metric engine: the only place numbers are calculated (spec section 7)."""
from __future__ import annotations

import math

import pandas as pd

from metrics.frames import base_frames
from metrics.periods import period_months
from model.contracts import (
    Lineage, MethodStatus, MetricResult, Provenance, Range, Scope, weakest,
)

CONFIDENCE = ["High", "Medium", "Low-Med", "Low"]
_PROV_STRENGTH = [Provenance.APPROVED_REAL, Provenance.PUBLIC_REFERENCE, Provenance.SYNTHETIC]
SENSITIVITIES = ("low", "base", "high")
# Metrics that depend on the sensitivity multipliers; only these carry a range.
SENSITIVE = {
    "baseline_water_l", "baseline_energy_kwh", "baseline_co2_kg", "water_saving_l",
    "energy_saving_kwh", "co2_saving_kg", "footprint_pct_of_baseline_water",
    "footprint_pct_of_baseline_co2", "footprint_pct_of_baseline_energy",
    "replacements_postponed", "postponed_product_kgco2e",
}
FACT_FRAME = {
    "fact_service_month": ("activity", "load_id"), "fact_laundry_month": ("activity", "laundry_load_id"),
    "fact_waste_month": ("activity", "waste_load_id"), "fact_service_cycle": ("cycles", "load_id"),
    "fact_repair_month": ("repairs", "load_id"), "product": ("activity", None),
}
RAW_SERIES = ("active_assets_scanned", "late_cycles")


def _num(x) -> float | None:
    """Plain float, or None for missing/NaN (NaN never leaves the engine)."""
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) else x


def _sum(s: pd.Series) -> float | None:
    return None if s.notna().sum() == 0 else _num(s.sum())


def _div(a, b, scale: float = 1.0) -> float | None:
    return None if a is None or b is None or b == 0 else a / b * scale


def _sub(a, b) -> float | None:
    return None if a is None or b is None else a - b


def _mul(a, k) -> float | None:
    return None if a is None else a * k


def _wearers_by_month(act: pd.DataFrame) -> pd.Series:
    """Account/site wearers per month: max over products per site-month, summed over sites (T2)."""
    return act.groupby(["site_id", "month"]).active_wearers.max().groupby("month").sum().sort_index()


def _values(frames: dict[str, pd.DataFrame], baseline: dict, factor: float, r: float) -> dict:
    """All registry metrics for one set of frames and one sensitivity (factor, r)."""
    act, cyc, rep = frames["activity"], frames["cycles"], frames["repairs"]
    v: dict[str, float | None] = {}
    if len(act):
        months_p = frames["months"]
        # Snapshots are taken at the last month of the period; missing months count as 0.
        w = _wearers_by_month(act).reindex(months_p, fill_value=0)
        last = act[act.month == months_p[-1]]
        idle = (act.allocated_pieces - act.active_assets_scanned).clip(lower=0)
        months = act.month
        v["sites"] = float(act.site_id.nunique())
        v["active_wearers"] = _num(w.iloc[-1])
        v["active_wearers_avg"] = _num(w.mean())
        v["garments_allocated"] = _sum(last.allocated_pieces) or 0.0
        v["utilisation"] = _div(_sum(act.active_assets_scanned), _sum(act.allocated_pieces))
        v["idle_pieces"] = _num(idle.groupby(months).sum().mean())
        v["idle_stock_value_eur"] = _num((idle * act.purchase_cost_eur).groupby(months).sum().mean())
        v["washed_kg"] = _sum(act.washed_kg)
        v["washed_kg_per_wearer"] = _div(v["washed_kg"], v["active_wearers_avg"])
        v["washing_pct"] = _div(_sum(act.washed_pieces), _sum(act.allocated_pieces), 100)
        v["service_requests"] = _sum(act.service_requests)
        v["service_requests_per_100w"] = _div(v["service_requests"], v["active_wearers_avg"], 100)
        v["allocated_water_l"] = _sum(act.allocated_water_l)
        v["allocated_energy_kwh"] = _sum(act.allocated_energy_kwh)
        v["allocated_co2_kg"] = _sum(act.allocated_process_kg + act.allocated_delivery_kg)
        wkg = v["washed_kg"]
        v["baseline_water_l"] = _mul(wkg, baseline["water_l_per_kg"] * factor)
        v["baseline_energy_kwh"] = _mul(wkg, baseline["energy_kwh_per_kg"] * factor)
        v["baseline_co2_kg"] = _mul(
            wkg, (baseline["process_kgco2e_per_kg"] + baseline["delivery_kgco2e_per_kg"]) * factor)
        for pct, base, alloc, saving in (
                ("water", "baseline_water_l", "allocated_water_l", "water_saving_l"),
                ("energy", "baseline_energy_kwh", "allocated_energy_kwh", "energy_saving_kwh"),
                ("co2", "baseline_co2_kg", "allocated_co2_kg", "co2_saving_kg")):
            v[saving] = _sub(v[base], v[alloc])
            v[f"footprint_pct_of_baseline_{pct}"] = _div(v[alloc], v[base], 100)
        v["textile_waste_kg"] = _sum(act.allocated_waste_kg)
        recycled = _sum(act.waste_recycling_kg) if "waste_recycling_kg" in act else None
        reused = _sum(act.waste_reuse_kg) if "waste_reuse_kg" in act else None
        v["recycling_rate"] = _div(recycled, v["textile_waste_kg"])
        v["diverted_from_mixed_waste_kg"] = (
            None if recycled is None and reused is None else (recycled or 0) + (reused or 0))
    if len(cyc):
        v["on_time_rate"] = 1 - (cyc.performance_flag == "LATE").sum() / len(cyc)
        v["avg_cycle_hours"] = _num(cyc.cycle_hours.mean())
    if len(rep):
        v["repairs"] = _sum(rep.repair_count)
        v["repairs_per_100w"] = _div(v["repairs"], v.get("active_wearers_avg"), 100)
        v["replacements_postponed"] = _mul(v["repairs"], r)
        v["postponed_product_kgco2e"] = _num((rep.repair_count * rep.footprint_kgco2e).sum() * r)
    return {k: _num(x) for k, x in v.items()}


class Engine:
    def __init__(self, con, assumptions: dict, registry: dict):
        self.con = con
        self.assumptions = assumptions
        self.registry = registry

    # ---- scope helpers -------------------------------------------------------------------
    def _level(self, node_id: str) -> str:
        row = self.con.execute("select level from org_node where node_id = ?", [node_id]).fetchone()
        if row is None:
            raise ValueError(f"unknown node: {node_id}")
        return row[0]

    def _baseline(self, baseline_id: str) -> dict:
        return self.assumptions["baselines"][baseline_id]

    def _sens(self, key: str) -> tuple[float, float]:
        s = self.assumptions["sensitivity"][key]
        return s["baseline_factor"], s["replacements_per_repair"]

    @staticmethod
    def _subset(frames: dict, site_id: str | None = None, month: str | None = None) -> dict:
        out = dict(frames)
        if month is not None:
            out["months"] = [month]
        for key in ("activity", "cycles", "repairs"):
            df = frames[key]
            if site_id is not None:
                df = df[df.site_id == site_id]
            if month is not None:
                df = df[df.month == month]
            out[key] = df
        return out

    # ---- result building -----------------------------------------------------------------
    def _results(self, node_id: str, level: str, period: str, product: str | None,
                 frames: dict, baseline_id: str) -> dict[str, MetricResult]:
        baseline = self._baseline(baseline_id)
        by_sens = {k: _values(frames, baseline, *self._sens(k)) for k in SENSITIVITIES}
        scope = Scope(node_id=node_id, level=level, period=period, product=product)
        out = {}
        for mid, spec in self.registry.items():
            used = {FACT_FRAME[t][0] for t in spec["inputs"]}
            has_rows = all(len(frames[f]) for f in used)
            value = by_sens["base"].get(mid) if has_rows else None
            rng = None
            if value is not None and mid in SENSITIVE:
                vals = [by_sens[k][mid] for k in SENSITIVITIES]
                rng = Range(low=min(vals), base=value, high=max(vals))
            out[mid] = self._result(mid, spec, scope, frames, used, value, rng)
        return out

    def _result(self, mid, spec, scope, frames, used, value, rng) -> MetricResult:
        status = MethodStatus(spec["method_status"])
        provs: set[Provenance] = set()
        for f in used:
            df = frames[f]
            for s in df["method_status"].unique() if len(df) else []:
                status = weakest(status, MethodStatus(s))
            for p in df["provenance"].unique() if len(df) else []:
                provs.add(Provenance(p))
        prov = max(provs, key=_PROV_STRENGTH.index) if provs else Provenance.SYNTHETIC
        load_ids: set[str] = set()
        for t in spec["inputs"]:
            frame, col = FACT_FRAME[t]
            if col and col in frames[frame]:
                load_ids |= set(frames[frame][col].dropna().unique())
        act = frames["activity"]
        allocation_derived = bool({"fact_laundry_month", "fact_waste_month"} & set(spec["inputs"]))
        dq = bool(allocation_derived and len(act) and act["dq_warning"].any())
        conf = spec["confidence"]
        if dq and conf in CONFIDENCE:
            conf = CONFIDENCE[min(CONFIDENCE.index(conf) + 1, len(CONFIDENCE) - 1)]
        return MetricResult(
            metric_id=mid, label=spec["label"], unit=spec["unit"], scope=scope, value=value,
            range=rng, method_status=status, provenance=prov, confidence=conf,
            assumptions=list(spec["assumptions"]),
            lineage=Lineage(facts=list(spec["inputs"]), rows=sum(len(frames[f]) for f in used),
                            load_ids=sorted(load_ids)),
            formula_text=spec["formula_text"], priority_tags=list(spec["priority_tags"]),
            customer_facing=spec["customer_facing"], dq_warning=dq)

    # ---- public API ----------------------------------------------------------------------
    def compute(self, node_id: str, period: str = "2025", product: str | None = None,
                baseline_id: str = "B_LOCAL", service_line: str | None = None
                ) -> dict[str, MetricResult]:
        level = self._level(node_id)
        frames = base_frames(self.con, node_id, period_months(period), product, service_line)
        return self._results(node_id, level, period, product, frames, baseline_id)

    def site_metrics(self, account_id: str, period: str = "2025", product: str | None = None,
                     baseline_id: str = "B_LOCAL", service_line: str | None = None
                     ) -> dict[str, dict[str, MetricResult]]:
        frames = base_frames(self.con, account_id, period_months(period), product, service_line)
        return {
            sid: self._results(sid, "SITE", period, product, self._subset(frames, site_id=sid),
                               baseline_id)
            for sid in frames["sites"].node_id if sid in set(frames["activity"].site_id)
        }

    def monthly(self, account_id: str, metric_ids: list[str], period: str = "2025",
                product: str | None = None, site_id: str | None = None,
                baseline_id: str = "B_LOCAL", service_line: str | None = None
                ) -> dict[str, list[dict]]:
        unknown = [m for m in metric_ids if m not in self.registry and m not in RAW_SERIES]
        if unknown:
            raise ValueError(f"unknown metric ids: {unknown}")
        months = period_months(period)
        frames = base_frames(self.con, site_id or account_id, months, product, service_line)
        base = self._baseline(baseline_id)
        out: dict[str, list[dict]] = {m: [] for m in metric_ids}
        for month in months:
            sub = self._subset(frames, month=month)
            vals = _values(sub, base, *self._sens("base"))
            act, cyc = sub["activity"], sub["cycles"]
            vals["active_assets_scanned"] = _sum(act.active_assets_scanned) if len(act) else None
            vals["late_cycles"] = float((cyc.performance_flag == "LATE").sum()) if len(cyc) else None
            for m in metric_ids:
                out[m].append({"month": month, "value": vals.get(m)})
        return out

    def baseline_comparison(self, node_id: str, period: str = "2025",
                            product: str | None = None,
                            service_line: str | None = None) -> list[dict]:
        frames = base_frames(self.con, node_id, period_months(period), product, service_line)
        rows = []
        for bid, b in self.assumptions["baselines"].items():
            v = _values(frames, b, *self._sens("base"))
            rows.append({"baseline_id": bid, "name": b["name"],
                         "co2_saving_kg": v.get("co2_saving_kg"),
                         "water_saving_l": v.get("water_saving_l"),
                         "energy_saving_kwh": v.get("energy_saving_kwh")})
        return rows

    def circularity(self, node_id: str, period: str = "2025", product: str | None = None,
                    service_line: str | None = None) -> dict:
        frames = base_frames(self.con, node_id, period_months(period), product, service_line)
        rep, act = frames["repairs"], frames["activity"]
        by_type = rep.groupby("repair_type").repair_count.sum()
        by_month = rep.groupby("month").repair_count.sum()
        routes = {c[len("waste_"):-len("_kg")]: _sum(act[c]) for c in act.columns
                  if c.startswith("waste_") and c.endswith("_kg")}
        return {
            "repairs_by_type": {k: float(x) for k, x in by_type.items()},
            "repairs_by_month": [{"month": m, "repairs": float(x)} for m, x in by_month.items()],
            "waste_routes": routes,
        }

    def laundry_stats(self, account_id: str, period: str = "2025",
                      service_line: str | None = None) -> list[dict]:
        months = period_months(period)
        act = base_frames(self.con, account_id, months, None, service_line)["activity"]
        out = []
        for lid, rows in act.groupby("laundry_id"):
            name, = self.con.execute("select name from laundry where laundry_id = ?", [lid]).fetchone()
            kg = dict(self.con.execute(
                "select route, sum(kg) from fact_waste_month where laundry_id = ? "
                "and list_contains(?, month) group by route", [lid, months]).fetchall())
            total = sum(kg.values())
            out.append({"laundry_id": lid, "name": name,
                        "recycling_rate": _div(kg.get("recycling", 0.0), total),
                        "site_ids": sorted(rows.site_id.unique()),
                        "dq_warning": bool(rows.dq_warning.any())})
        return out
