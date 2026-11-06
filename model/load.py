"""Load a data pack into DuckDB: valid frames, quarantine, dq_flags and source."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from adapters.excel_pack import ExcelPackAdapter
from adapters.fixtures import inject_bad_rows
from model.validate import consistency_checks, validate_frames

DDL = Path(__file__).with_name("ddl.sql")
TABLES = ["org_node", "product", "laundry", "fact_service_month", "fact_service_cycle",
          "fact_repair_month", "fact_laundry_month", "fact_waste_month"]


def _insert(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    cols = [r[0] for r in con.execute(f'DESCRIBE "{table}"').fetchall()]
    con.register("_df", df[cols])
    con.execute(f'INSERT INTO "{table}" SELECT * FROM _df')
    con.unregister("_df")


def load_pack(path: Path, db: str = ":memory:", inject_bad: bool = False) -> duckdb.DuckDBPyConnection:
    adapter = ExcelPackAdapter(path)
    frames = adapter.to_canonical(adapter.extract())
    if inject_bad:
        frames = inject_bad_rows(frames)
    valid, quarantine = validate_frames(frames)

    con = duckdb.connect(db)
    con.execute(DDL.read_text(encoding="utf-8"))
    for table in TABLES:
        _insert(con, table, valid[table])
    _insert(con, "quarantine", quarantine)
    _insert(con, "dq_flags", consistency_checks(con))
    source = pd.DataFrame([{
        "source_id": adapter.source_id, "name": "Lindström × Since AI synthetic data pack",
        "tier": adapter.tier, "system": "Excel", "approved": False,
        "loaded_at": datetime.now(timezone.utc).replace(tzinfo=None), "load_id": adapter.load_id,
    }])
    _insert(con, "source", source)
    return con
