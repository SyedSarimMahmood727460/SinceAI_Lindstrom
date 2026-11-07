"""Row validation (ERROR -> quarantine) and cross-source consistency checks (WARNING)."""
from __future__ import annotations

import json

import duckdb
import pandas as pd

MONTH_RE = r"^\d{4}-(0[1-9]|1[0-2])$"

# per fact table: required keys, foreign keys (column -> dimension table.column), numeric measures
RULES = {
    "fact_service_month": {
        "keys": ["month", "customer_id", "site_id", "product_id", "laundry_id"],
        "measures": ["active_wearers", "allocated_pieces", "active_assets_scanned",
                     "washed_pieces", "packed_pieces", "washed_kg", "service_requests"],
    },
    "fact_service_cycle": {
        "keys": ["month", "asset_id", "customer_id", "site_id", "product_id", "laundry_id"],
        "measures": ["cycle_hours"],
    },
    "fact_repair_month": {
        "keys": ["month", "customer_id", "site_id", "product_id", "laundry_id", "repair_type"],
        "measures": ["repair_count"],
    },
    "fact_laundry_month": {
        "keys": ["month", "laundry_id"],
        "measures": ["washed_kg", "fresh_water_l", "process_energy_kwh", "process_kgco2e",
                     "delivery_kgco2e"],
    },
    "fact_waste_month": {"keys": ["month", "laundry_id", "route"], "measures": ["kg"]},
}


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def _reasons(name: str, df: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.Series:
    """Per-row semicolon-joined error reasons ('' when the row is valid)."""
    rule = RULES[name]
    parts: list[pd.Series] = []

    def add(mask: pd.Series, text: str | pd.Series) -> None:
        parts.append(pd.Series(text, index=df.index).where(mask, ""))

    for col in rule["keys"]:
        if col != "month":
            add(_blank(df[col]), f"missing key {col}")
    month = df["month"].astype(str)
    add(~month.str.match(MONTH_RE), "invalid month (expected YYYY-MM)")

    sites = frames["org_node"].query("level == 'SITE'").set_index("node_id")
    accounts = set(frames["org_node"].query("level == 'ACCOUNT'")["node_id"])
    fks = {"site_id": set(sites.index), "laundry_id": set(frames["laundry"]["laundry_id"]),
           "product_id": set(frames["product"]["product_id"]), "customer_id": accounts}
    for col, valid in fks.items():
        if col in df.columns:
            label = "customer" if col == "customer_id" else col.removesuffix("_id")
            add(~_blank(df[col]) & ~df[col].isin(valid), "unknown " + label + " " + df[col].astype(str))
    if "site_id" in df.columns and "customer_id" in df.columns:
        owner = df["site_id"].map(sites["parent_id"])
        add(owner.notna() & df["customer_id"].isin(accounts) & (owner != df["customer_id"]),
            "site does not belong to customer " + df["customer_id"].astype(str))

    for col in rule["measures"]:
        num = pd.to_numeric(df[col], errors="coerce")
        add(num.isna(), f"non-numeric {col}")
        add(num < 0, f"negative {col}")

    out = pd.Series("", index=df.index)
    for p in parts:
        out = out.where(p == "", out.where(out == "", out + "; ") + p)
    return out


DIM_KEYS = {"org_node": "node_id", "product": "product_id", "laundry": "laundry_id"}


def _dedupe_dimensions(frames: dict[str, pd.DataFrame], bad_rows: list[dict]) -> dict[str, pd.DataFrame]:
    """A dimension id already supplied by an earlier source is quarantined (first source wins)."""
    out = dict(frames)
    for name, key in DIM_KEYS.items():
        df = frames[name]
        if "_source_id" in df.columns:
            first = df.groupby(key)["_source_id"].first()
            dup = df["_source_id"].notna() & (df["_source_id"] != df[key].map(first))
            for idx in df.index[dup]:
                bad_rows.append({
                    "table": name,
                    "row_json": json.dumps(df.loc[idx].to_dict(), default=str, ensure_ascii=False),
                    "reason": f"duplicate key from source {df.loc[idx, '_source_id']}",
                })
            df = df[~dup].reset_index(drop=True)
        out[name] = df.drop(columns=["_source_id"], errors="ignore")
    return out


def validate_frames(frames: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    bad_rows: list[dict] = []
    frames = _dedupe_dimensions(frames, bad_rows)
    valid = dict(frames)
    for name in RULES:
        df = frames[name]
        reasons = _reasons(name, df, frames)
        bad = reasons != ""
        for idx in df.index[bad]:
            bad_rows.append({
                "table": name,
                "row_json": json.dumps(df.loc[idx].to_dict(), default=str, ensure_ascii=False),
                "reason": reasons[idx],
            })
        valid[name] = df[~bad].reset_index(drop=True)
    quarantine = pd.DataFrame(bad_rows, columns=["table", "row_json", "reason"])
    return valid, quarantine


def consistency_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """C1 laundry volume, C2 primary laundry, C3 wearers vs allocated pieces (all WARNING)."""
    c1 = con.execute("""
        SELECT 'C1' AS check_id, 'WARNING' AS severity, 'laundry' AS entity_type,
               s.laundry_id AS entity_id, s.month AS month,
               'customer washed_kg ' || printf('%.0f', s.kg) || ' vs laundry washed_kg '
                 || printf('%.0f', l.washed_kg) || ' (ratio ' || printf('%.2f', s.kg / l.washed_kg) || 'x)' AS detail
        FROM (SELECT laundry_id, month, SUM(washed_kg) AS kg FROM fact_service_month GROUP BY 1, 2) s
        JOIN fact_laundry_month l USING (laundry_id, month)
        WHERE l.washed_kg > 0 AND s.kg / l.washed_kg > 1.0
        ORDER BY entity_id, month""").df()
    c2 = con.execute("""
        SELECT DISTINCT 'C2', 'WARNING', 'site', n.node_id, NULL,
               'primary laundry ' || n.primary_laundry_id || ' but activity rows use ' || f.laundry_id
        FROM org_node n JOIN fact_service_month f ON f.site_id = n.node_id
        WHERE n.level = 'SITE' AND n.primary_laundry_id <> f.laundry_id
        ORDER BY 4""").df()
    c3 = con.execute("""
        SELECT 'C3', 'WARNING', 'site', site_id, month,
               'wearers ' || printf('%.0f', w) || ' > allocated pieces ' || printf('%.0f', p)
        FROM (SELECT site_id, month, MAX(active_wearers) AS w, SUM(allocated_pieces) AS p
              FROM fact_service_month GROUP BY 1, 2)
        WHERE w > p ORDER BY 4, 5""").df()
    cols = ["check_id", "severity", "entity_type", "entity_id", "month", "detail"]
    c2.columns = c3.columns = cols
    frames = [f for f in (c1, c2, c3) if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
