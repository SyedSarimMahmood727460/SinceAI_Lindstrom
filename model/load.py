"""Load data packs into DuckDB: valid frames, quarantine, dq_flags and source."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from adapters.csv_pack import CsvPackAdapter
from adapters.excel_pack import ExcelPackAdapter
from adapters.fixtures import inject_bad_rows
from model.validate import consistency_checks, validate_frames

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = ROOT / "config" / "sources.yaml"
DEFAULT_PACK = ("../lindstrom_pack/Lindstrom_SinceAI2026/"
                "Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx")
DIM_TABLES = ["org_node", "product", "laundry"]
DDL = Path(__file__).with_name("ddl.sql")
TABLES = ["org_node", "product", "laundry", "fact_service_month", "fact_service_cycle",
          "fact_repair_month", "fact_laundry_month", "fact_waste_month"]


def _insert(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> None:
    cols = [r[0] for r in con.execute(f'DESCRIBE "{table}"').fetchall()]
    con.register("_df", df[cols])
    con.execute(f'INSERT INTO "{table}" SELECT * FROM _df')
    con.unregister("_df")


def _finish(adapters: list, frames: dict[str, pd.DataFrame], db: str) -> duckdb.DuckDBPyConnection:
    valid, quarantine = validate_frames(frames)
    con = duckdb.connect(db)
    con.execute(DDL.read_text(encoding="utf-8"))
    for table in TABLES:
        _insert(con, table, valid[table])
    _insert(con, "quarantine", quarantine)
    _insert(con, "dq_flags", consistency_checks(con))
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    source = pd.DataFrame([{
        "source_id": a.source_id, "name": a.name, "tier": a.tier, "system": a.system,
        "approved": False, "loaded_at": loaded_at, "load_id": a.load_id,
    } for a in adapters])
    _insert(con, "source", source)
    return con


def load_pack(path: Path, db: str = ":memory:", inject_bad: bool = False) -> duckdb.DuckDBPyConnection:
    adapter = ExcelPackAdapter(path)
    frames = adapter.to_canonical(adapter.extract())
    if inject_bad:
        frames = inject_bad_rows(frames)
    return _finish([adapter], frames, db)


def _resolve(raw: str) -> Path:
    raw = raw.replace("${VR_PACK_PATH}", os.environ.get("VR_PACK_PATH") or DEFAULT_PACK)
    p = Path(raw)
    return (p if p.is_absolute() else ROOT / p).resolve()


def _build_adapters(config_path: Path) -> list:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    adapters = []
    for src in cfg.get("sources", []):
        sid = src["id"]
        if not src.get("enabled", True):
            continue
        toggle = src.get("toggle_env")
        if toggle and os.environ.get(toggle, "").strip().lower() == "off":
            log.info("source %s disabled by %s=off", sid, toggle)
            continue
        path = _resolve(str(src["path"]))
        kind = src.get("adapter")
        if kind == "excel":
            if not path.is_file():
                raise RuntimeError(f"Data pack not found at {path}. Set VR_PACK_PATH to the "
                                   "Lindstrom data pack .xlsx file.")
            adapters.append(ExcelPackAdapter(path))
        elif kind == "csv":
            if not path.is_dir():
                log.warning("source %s skipped: folder not found: %s", sid, path)
                continue
            adapters.append(CsvPackAdapter(path, source_id=sid))
        else:
            raise ValueError(f"unknown adapter '{kind}' for source {sid}")
    if not adapters:
        raise RuntimeError("no data sources enabled")
    return adapters


def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [p for p in parts if len(p)]
    return pd.concat(non_empty or parts[:1], ignore_index=True)


def load_sources(config_path: Path | None = None, db: str = ":memory:",
                 inject_bad: bool = False) -> duckdb.DuckDBPyConnection:
    adapters = _build_adapters(Path(config_path) if config_path else DEFAULT_SOURCES)
    per_source = []
    for a in adapters:
        fr = a.to_canonical(a.extract())
        for t in DIM_TABLES:  # internal marker for duplicate-key detection; dropped in validation
            fr[t] = fr[t].assign(_source_id=a.source_id)
        per_source.append(fr)
    frames = {t: _concat([fr[t] for fr in per_source]) for t in TABLES}
    if inject_bad:
        frames = inject_bad_rows(frames)
    return _finish(adapters, frames, db)
