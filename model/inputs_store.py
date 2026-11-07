"""Account-manager inputs ("Your numbers") for the service vs do-it-yourself comparison.

One JSON file per account in `VR_INPUTS_DIR` (default `data/kam_inputs/`, gitignored):
`{"values": {key: number}, "entered_at": {key: "YYYY-MM-DD"}}`. Only keys the account
manager entered are stored; everything else falls back to the `dto_inputs` defaults in the
assumption set.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_KEY = "contract_price_eur_per_year"
CONTRACT = {"label": "Lindström contract price", "unit": "EUR/year"}
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_-]+")


def inputs_dir() -> Path:
    return Path(os.environ.get("VR_INPUTS_DIR") or ROOT / "data" / "kam_inputs")


def _path(account_id: str) -> Path:
    if not _ACCOUNT_ID.fullmatch(account_id or ""):
        raise ValueError(f"invalid account id: {account_id!r}")
    return inputs_dir() / f"{account_id}.json"


def _allowed(spec: dict) -> set[str]:
    return {CONTRACT_KEY} | {f"{k}{sfx}" for k in spec for sfx in ("", "_low", "_high")}


def validate_inputs(data: dict, spec: dict) -> dict:
    """Strictly validated copy of `data`: known keys, finite numbers >= 0, low <= value <= high.

    A null value means "not entered" and is dropped. Strings (also "2,5") are rejected; the UI
    normalises decimal commas before sending.
    """
    if not isinstance(data, dict):
        raise ValueError("inputs must be an object of key: number")
    allowed = _allowed(spec)
    out: dict[str, float] = {}
    positive = {f"{k}{sfx}" for k, s in spec.items() if s.get("positive")
                for sfx in ("", "_low", "_high")}
    for key, v in data.items():
        if key not in allowed:
            raise ValueError(f"unknown input key: {key}")
        if v is None:
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{key}: must be a number, got {v!r}")
        try:
            v = float(v)
        except OverflowError:
            raise ValueError(f"{key}: number too large") from None
        if not math.isfinite(v):
            raise ValueError(f"{key}: must be a finite number")
        if key in positive and v <= 0:
            raise ValueError(f"{key}: must be > 0, got {v:g}")
        if v < 0:
            raise ValueError(f"{key}: must be >= 0, got {v:g}")
        out[key] = int(v) if v.is_integer() and abs(v) < 2 ** 53 else v
    for key, s in spec.items():
        lo = out.get(f"{key}_low", out.get(key, s["low"]))
        base = out.get(key, s["default"])
        hi = out.get(f"{key}_high", out.get(key, s["high"]))
        if not lo <= base <= hi:
            raise ValueError(f"{key}: low <= value <= high required, got {lo}, {base}, {hi}")
    return out


def load_inputs(account_id: str, spec: dict | None = None) -> dict:
    """Stored inputs for the account; {} if missing or unreadable (a warning is logged)."""
    path = _path(account_id)
    if not path.exists():
        return {}
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(stored, dict) or not isinstance(stored.get("values", {}), dict) \
                or not isinstance(stored.get("entered_at", {}), dict):
            raise ValueError("unexpected structure")
        if spec is not None:
            validate_inputs(stored.get("values", {}), spec)
    except (OSError, ValueError) as e:  # JSONDecodeError is a ValueError
        log.warning("inputs file for %s is unreadable, using defaults: %s", account_id, e)
        return {}
    return stored


def save_inputs(account_id: str, data: dict, spec: dict) -> dict:
    """Validate and store (replace) the account's inputs; unchanged keys keep their date."""
    values = validate_inputs(data, spec)
    path = _path(account_id)
    old = load_inputs(account_id)
    old_values, old_dates = old.get("values", {}), old.get("entered_at", {})
    today = date.today().isoformat()
    stored = {"values": values,
              "entered_at": {k: old_dates[k] if k in old_dates and old_values.get(k) == v else today
                             for k, v in values.items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return stored


def effective_inputs(stored: dict, spec: dict) -> list[dict]:
    """Every input with its effective value and range: defaults unless the KAM entered one.

    An entered value is fixed across low/base/high unless `<key>_low` / `<key>_high` is given.
    """
    values, dates = stored.get("values", {}), stored.get("entered_at", {})
    rows = []
    for key, s in spec.items():
        entered = [k for k in (key, f"{key}_low", f"{key}_high") if k in values]
        base = values.get(key, s["default"])
        fixed = key in values
        rows.append({
            "key": key, "label": s["label"], "unit": s["unit"], "value": base,
            "low": values.get(f"{key}_low", base if fixed else s["low"]),
            "high": values.get(f"{key}_high", base if fixed else s["high"]),
            "source": "kam" if entered else "default",
            "entered_at": max((dates[k] for k in entered if k in dates), default=None),
            "assumption_id": s["assumption_id"], "help": s.get("help")})
    price = values.get(CONTRACT_KEY)
    rows.append({"key": CONTRACT_KEY, **CONTRACT, "value": price, "low": price, "high": price,
                 "source": "kam" if price is not None else "default",
                 "entered_at": dates.get(CONTRACT_KEY) if price is not None else None,
                 "assumption_id": None, "help": None})
    return rows
