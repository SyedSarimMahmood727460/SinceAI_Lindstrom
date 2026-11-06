"""Adapter protocol: every data source maps to the canonical frames."""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class Adapter(Protocol):
    source_id: str
    tier: int

    def extract(self) -> dict[str, pd.DataFrame]: ...

    def to_canonical(self, raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]: ...
