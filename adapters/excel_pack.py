"""Adapter for the Lindström × Since AI synthetic Excel data pack (tier 0)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd

from adapters.canonical import canonical_from_sheets

SHEETS = [
    "Customers", "Sites", "Products", "Laundries", "Service_Activity",
    "Service_Cycles", "Repairs", "Laundry_Resources", "Waste_Circularity",
]


class ExcelPackAdapter:
    name = "Lindström × Since AI synthetic data pack"
    system = "Excel"
    source_id = "excel_pack"
    tier = 0

    def __init__(self, path: Path):
        self.path = Path(path)
        self.load_id = uuid.uuid4().hex

    def extract(self) -> dict[str, pd.DataFrame]:
        return pd.read_excel(self.path, sheet_name=SHEETS)

    def to_canonical(self, raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        return canonical_from_sheets(raw, self.source_id, self.load_id, "Workwear")
