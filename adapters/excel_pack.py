"""Adapter for the Lindström × Since AI synthetic Excel data pack (tier 0)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd

from model.contracts import MethodStatus, Provenance

SHEETS = [
    "Customers", "Sites", "Products", "Laundries", "Service_Activity",
    "Service_Cycles", "Repairs", "Laundry_Resources", "Waste_Circularity",
]
WASTE_ROUTES = {
    "recycling_kg": "recycling", "reuse_kg": "reuse",
    "energy_recovery_kg": "energy_recovery", "incineration_kg": "incineration",
}


class ExcelPackAdapter:
    source_id = "excel_pack"
    tier = 0

    def __init__(self, path: Path):
        self.path = Path(path)
        self.load_id = uuid.uuid4().hex

    def extract(self) -> dict[str, pd.DataFrame]:
        return pd.read_excel(self.path, sheet_name=SHEETS)

    def _tag(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["method_status"] = MethodStatus.CALCULATED.value
        df["provenance"] = Provenance.SYNTHETIC.value
        df["source_id"] = self.source_id
        df["load_id"] = self.load_id
        return df

    def to_canonical(self, raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        cust, sites = raw["Customers"], raw["Sites"]
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

        prod = raw["Products"]
        product = pd.DataFrame({
            "product_id": prod["product_id"], "name": prod["product_name"],
            "product_group": prod["product_group"], "service_line": "Workwear",
            "weight_kg": prod["avg_weight_kg"],
            "footprint_kgco2e": prod["synthetic_product_footprint_kgco2e"],
            "purchase_cost_eur": prod["synthetic_purchase_cost_eur"],
        })
        lau = raw["Laundries"]
        laundry = pd.DataFrame({
            "laundry_id": lau["laundry_id"], "name": lau["laundry_name"], "country": lau["country"],
        })

        sa = raw["Service_Activity"]
        service = self._tag(sa[[
            "month", "customer_id", "site_id", "product_id", "laundry_id", "active_wearers",
            "allocated_pieces", "active_assets_scanned", "washed_pieces", "packed_pieces",
        ]].assign(washed_kg=sa["customer_washed_kg"], service_requests=sa["service_requests"]))

        sc = raw["Service_Cycles"]
        cycle = self._tag(sc[[
            "asset_id", "cycle_number", "customer_id", "site_id", "product_id", "laundry_id",
            "pickup_timestamp", "in_laundry_timestamp", "out_laundry_timestamp",
            "delivered_timestamp", "cycle_hours", "performance_flag",
        ]].assign(month=sc["pickup_timestamp"].astype(str).str[:7]))

        rep = raw["Repairs"]
        repair = self._tag(rep[[
            "month", "customer_id", "site_id", "product_id", "laundry_id", "repair_type",
            "repair_count",
        ]])

        lr = raw["Laundry_Resources"]
        fact_laundry = self._tag(lr[[
            "laundry_id", "month", "washed_kg", "fresh_water_l", "process_energy_kwh",
        ]].assign(process_kgco2e=lr["process_emissions_kgco2e"],
                  delivery_kgco2e=lr["delivery_emissions_kgco2e"]))

        wc = raw["Waste_Circularity"]
        waste = wc.melt(id_vars=["laundry_id", "month"], value_vars=list(WASTE_ROUTES),
                        var_name="route", value_name="kg")
        waste["route"] = waste["route"].map(WASTE_ROUTES)
        waste = self._tag(waste.sort_values(["laundry_id", "month", "route"], ignore_index=True))

        return {
            "org_node": org_node, "product": product, "laundry": laundry,
            "fact_service_month": service, "fact_service_cycle": cycle,
            "fact_repair_month": repair, "fact_laundry_month": fact_laundry,
            "fact_waste_month": waste,
        }
