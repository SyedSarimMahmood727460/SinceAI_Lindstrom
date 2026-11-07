"""Base data frames for the metric engine (allocation per spec 7.4 happens here)."""
from __future__ import annotations

import duckdb
import pandas as pd

_LAUNDRY_COLS = {
    "fresh_water_l": "allocated_water_l",
    "process_energy_kwh": "allocated_energy_kwh",
    "process_kgco2e": "allocated_process_kg",
    "delivery_kgco2e": "allocated_delivery_kg",
}


def _node_column(con: duckdb.DuckDBPyConnection, node_id: str) -> str:
    row = con.execute("select level from org_node where node_id = ?", [node_id]).fetchone()
    if row is None:
        raise ValueError(f"unknown node: {node_id}")
    return "customer_id" if row[0] == "ACCOUNT" else "site_id"


def _fact(con, table: str, col: str, node_id: str, months: list[str],
          product: str | None, service_line: str | None = None) -> pd.DataFrame:
    sql = f"select * from {table} where {col} = ? and list_contains(?, month)"
    params: list = [node_id, months]
    if product is not None:
        sql += " and product_id = ?"
        params.append(product)
    if service_line is not None:
        sql += " and product_id in (select product_id from product where service_line = ?)"
        params.append(service_line)
    return con.execute(sql + " order by month, site_id, product_id", params).df()


def base_frames(con: duckdb.DuckDBPyConnection, account_id: str, months: list[str],
                product: str | None, service_line: str | None = None) -> dict[str, pd.DataFrame]:
    """Frames for an ACCOUNT or SITE node (`account_id` may also be a site id)."""
    col = _node_column(con, account_id)
    flagged = {
        (r[0], r[1]) for r in con.execute(
            "select entity_id, month from dq_flags where entity_type = 'laundry'").fetchall()
    }
    products = con.execute(
        "select product_id, footprint_kgco2e, purchase_cost_eur from product").df()

    act = _fact(con, "fact_service_month", col, account_id, months, product, service_line)
    lm = con.execute(
        "select laundry_id, month, washed_kg as laundry_kg, fresh_water_l, process_energy_kwh, "
        "process_kgco2e, delivery_kgco2e, load_id as laundry_load_id from fact_laundry_month").df()
    act = act.merge(lm, on=["laundry_id", "month"], how="left")
    denom = act["laundry_kg"].where(act["laundry_kg"] > 0)
    for src, dst in _LAUNDRY_COLS.items():
        act[dst] = act["washed_kg"] * act[src] / denom
    act = act.drop(columns=list(_LAUNDRY_COLS))

    waste = con.execute(
        "select laundry_id, month, route, kg, load_id as waste_load_id from fact_waste_month").df()
    routes = sorted(waste["route"].unique())
    per_route = waste.pivot_table(index=["laundry_id", "month"], columns="route",
                                  values="kg", aggfunc="sum").reset_index()
    per_route.columns = [c if c in ("laundry_id", "month") else f"kg_{c}"
                         for c in per_route.columns]
    wl = waste.groupby(["laundry_id", "month"], as_index=False)["waste_load_id"].first()
    act = act.merge(per_route, on=["laundry_id", "month"], how="left").merge(
        wl, on=["laundry_id", "month"], how="left")
    for r in routes:
        act[f"waste_{r}_kg"] = act["washed_kg"] * act.pop(f"kg_{r}") / denom
    act["allocated_waste_kg"] = act[[f"waste_{r}_kg" for r in routes]].sum(axis=1, min_count=1)
    act = act.drop(columns=["laundry_kg"])
    act = act.merge(products[["product_id", "purchase_cost_eur"]], on="product_id", how="left")
    act["dq_warning"] = [(lid, m) in flagged for lid, m in zip(act["laundry_id"], act["month"])]

    cycles = _fact(con, "fact_service_cycle", col, account_id, months, product, service_line)
    repairs = _fact(con, "fact_repair_month", col, account_id, months, product, service_line).merge(
        products[["product_id", "footprint_kgco2e"]], on="product_id", how="left")
    sites = con.execute(
        f"select * from org_node where level = 'SITE' and "
        f"{'parent_id' if col == 'customer_id' else 'node_id'} = ? order by node_id",
        [account_id]).df()
    return {"activity": act, "cycles": cycles, "repairs": repairs, "sites": sites,
            "months": list(months)}
