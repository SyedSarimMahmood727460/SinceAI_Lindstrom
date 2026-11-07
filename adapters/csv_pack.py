"""Generic CSV adapter: a folder of pack-shaped CSV files -> canonical frames (tier 0)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd

from adapters.canonical import canonical_from_sheets

# CSV text is read as strings (ids stay text, "NA" stays "NA") and the known typed columns
# are converted here, so the frames match what the Excel adapter produces.
NUMERIC = {
    "avg_weight_kg", "synthetic_product_footprint_kgco2e", "synthetic_purchase_cost_eur",
    "active_wearers", "allocated_pieces", "active_assets_scanned", "washed_pieces",
    "packed_pieces", "customer_washed_kg", "service_requests", "cycle_number", "cycle_hours",
    "repair_count", "washed_kg", "fresh_water_l", "process_energy_kwh",
    "process_emissions_kgco2e", "delivery_emissions_kgco2e",
    "recycling_kg", "reuse_kg", "energy_recovery_kg", "incineration_kg",
}
TIMESTAMPS = ("pickup_timestamp", "in_laundry_timestamp", "out_laundry_timestamp",
              "delivered_timestamp")


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.where(df != "", None)
    for col in df.columns:
        if col in NUMERIC:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif col in TIMESTAMPS:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

FILES = {
    "customers.csv": "Customers", "sites.csv": "Sites", "products.csv": "Products",
    "laundries.csv": "Laundries", "service_activity.csv": "Service_Activity",
    "service_cycles.csv": "Service_Cycles", "repairs.csv": "Repairs",
    "laundry_resources.csv": "Laundry_Resources", "waste.csv": "Waste_Circularity",
}


class CsvPackAdapter:
    tier = 0
    system = "CSV"

    def __init__(self, path: Path, source_id: str | None = None):
        self.path = Path(path)
        self.source_id = source_id or self.path.name
        self.name = f"CSV pack {self.source_id}"
        self.load_id = uuid.uuid4().hex

    def extract(self) -> dict[str, pd.DataFrame]:
        sheets: dict[str, pd.DataFrame] = {}
        for fname, sheet in FILES.items():
            f = self.path / fname
            if not f.is_file():
                continue
            try:
                sheets[sheet] = _typed(pd.read_csv(
                    f, encoding="utf-8", dtype=str, keep_default_na=False))
            except pd.errors.EmptyDataError:
                continue  # zero-byte file: treat as absent
        return sheets

    def to_canonical(self, raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        return canonical_from_sheets(raw, self.source_id, self.load_id, "Workwear")
