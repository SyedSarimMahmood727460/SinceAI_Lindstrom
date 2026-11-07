"""Shared mapping from pack-shaped sheets (Excel sheets or CSV files) to canonical frames."""
from __future__ import annotations

import pandas as pd

from model.contracts import MethodStatus, Provenance

WASTE_ROUTES = {
    "recycling_kg": "recycling", "reuse_kg": "reuse",
    "energy_recovery_kg": "energy_recovery", "incineration_kg": "incineration",
}
REQUIRED = ["Customers", "Sites", "Products"]
_COLUMNS = {
    "Laundries": ["laundry_id", "laundry_name", "country"],
    "Service_Activity": [
        "month", "customer_id", "site_id", "product_id", "laundry_id", "active_wearers",
        "allocated_pieces", "active_assets_scanned", "washed_pieces", "packed_pieces",
        "customer_washed_kg", "service_requests"],
    "Service_Cycles": [
        "asset_id", "cycle_number", "customer_id", "site_id", "product_id", "laundry_id",
        "pickup_timestamp", "in_laundry_timestamp", "out_laundry_timestamp",
        "delivered_timestamp", "cycle_hours", "performance_flag"],
    "Repairs": ["month", "customer_id", "site_id", "product_id", "laundry_id", "repair_type",
                "repair_count"],
    "Laundry_Resources": [
        "laundry_id", "month", "washed_kg", "fresh_water_l", "process_energy_kwh",
        "process_emissions_kgco2e", "delivery_emissions_kgco2e"],
    "Waste_Circularity": ["laundry_id", "month", *WASTE_ROUTES],
}


def canonical_from_sheets(sheets: dict[str, pd.DataFrame], source_id: str, load_id: str,
                          default_service_line: str = "Workwear") -> dict[str, pd.DataFrame]:
    for name in REQUIRED:
        if name not in sheets:
            raise ValueError(f"missing required sheet {name}")

    def sheet(name: str) -> pd.DataFrame:
        df = sheets.get(name)
        return df if df is not None else pd.DataFrame(columns=_COLUMNS[name])

    def tag(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["method_status"] = MethodStatus.CALCULATED.value
        df["provenance"] = Provenance.SYNTHETIC.value
        df["source_id"] = source_id
        df["load_id"] = load_id
        return df

    cust, sites = sheets["Customers"], sheets["Sites"]
    accounts = pd.DataFrame({
        "node_id": cust["customer_id"], "parent_id": None, "level": "ACCOUNT",
        "name": cust["customer_name"], "industry": cust["industry"],
        "segment": cust["segment"], "country": cust["hq_country"], "city": None,
        "site_type": None, "primary_laundry_id": None,
        "priority_topics": cust["priority_topics"],
    })
    cust_info = cust.set_index("customer_id")
    site_nodes = pd.DataFrame({
        "node_id": sites["site_id"], "parent_id": sites["customer_id"], "level": "SITE",
        "name": sites["site_name"],
        "industry": sites["customer_id"].map(cust_info["industry"]),
        "segment": sites["customer_id"].map(cust_info["segment"]),
        "country": sites["country"], "city": sites["city"],
        "site_type": sites["site_type"], "primary_laundry_id": sites["primary_laundry_id"],
        "priority_topics": sites["customer_id"].map(cust_info["priority_topics"]),
    })
    org_node = pd.concat([accounts, site_nodes], ignore_index=True)
    org_node["priority_topics"] = org_node["priority_topics"].map(
        lambda s: s.split("|") if isinstance(s, str) else [])

    prod = sheets["Products"]
    service_line = prod["service_line"] if "service_line" in prod.columns else default_service_line
    product = pd.DataFrame({
        "product_id": prod["product_id"], "name": prod["product_name"],
        "product_group": prod["product_group"], "service_line": service_line,
        "weight_kg": prod["avg_weight_kg"],
        "footprint_kgco2e": prod["synthetic_product_footprint_kgco2e"],
        "purchase_cost_eur": prod["synthetic_purchase_cost_eur"],
    })
    lau = sheet("Laundries")
    laundry = pd.DataFrame({
        "laundry_id": lau["laundry_id"], "name": lau["laundry_name"], "country": lau["country"],
    })

    sa = sheet("Service_Activity")
    service = tag(sa[[
        "month", "customer_id", "site_id", "product_id", "laundry_id", "active_wearers",
        "allocated_pieces", "active_assets_scanned", "washed_pieces", "packed_pieces",
    ]].assign(washed_kg=sa["customer_washed_kg"], service_requests=sa["service_requests"]))

    sc = sheet("Service_Cycles")
    cycle = tag(sc[[
        "asset_id", "cycle_number", "customer_id", "site_id", "product_id", "laundry_id",
        "pickup_timestamp", "in_laundry_timestamp", "out_laundry_timestamp",
        "delivered_timestamp", "cycle_hours", "performance_flag",
    ]].assign(month=sc["pickup_timestamp"].astype(str).str[:7]))

    rep = sheet("Repairs")
    repair = tag(rep[[
        "month", "customer_id", "site_id", "product_id", "laundry_id", "repair_type",
        "repair_count",
    ]])

    lr = sheet("Laundry_Resources")
    fact_laundry = tag(lr[[
        "laundry_id", "month", "washed_kg", "fresh_water_l", "process_energy_kwh",
    ]].assign(process_kgco2e=lr["process_emissions_kgco2e"],
              delivery_kgco2e=lr["delivery_emissions_kgco2e"]))

    wc = sheet("Waste_Circularity")
    waste = wc.melt(id_vars=["laundry_id", "month"], value_vars=list(WASTE_ROUTES),
                    var_name="route", value_name="kg")
    waste["route"] = waste["route"].map(WASTE_ROUTES)
    waste = tag(waste.sort_values(["laundry_id", "month", "route"], ignore_index=True))

    return {
        "org_node": org_node, "product": product, "laundry": laundry,
        "fact_service_month": service, "fact_service_cycle": cycle,
        "fact_repair_month": repair, "fact_laundry_month": fact_laundry,
        "fact_waste_month": waste,
    }
