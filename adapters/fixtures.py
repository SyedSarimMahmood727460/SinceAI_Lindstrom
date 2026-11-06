"""Fixture that injects known-bad rows to demonstrate quarantine."""
from __future__ import annotations

import pandas as pd


def inject_bad_rows(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add 3 rows to fact_service_month: unknown site, empty month, negative washed_kg."""
    out = dict(frames)
    base = frames["fact_service_month"]
    bad = pd.DataFrame([base.iloc[0]] * 3).reset_index(drop=True)
    bad.loc[0, "site_id"] = "S999"
    bad.loc[1, "month"] = ""
    bad.loc[2, "washed_kg"] = -5.0
    out["fact_service_month"] = pd.concat([base, bad], ignore_index=True)
    return out
