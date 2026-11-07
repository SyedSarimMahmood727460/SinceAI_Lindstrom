"""Generic CSV adapter: a folder of pack-shaped CSV files -> canonical frames (tier 0)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd

from adapters.canonical import canonical_from_sheets

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
                sheets[sheet] = pd.read_csv(f, encoding="utf-8")
            except pd.errors.EmptyDataError:
                continue  # zero-byte file: treat as absent
        return sheets

    def to_canonical(self, raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        return canonical_from_sheets(raw, self.source_id, self.load_id, "Workwear")
