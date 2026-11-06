"""YAML config loading (paths are relative to the config/ directory)."""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_assumptions(version: str = "v1") -> dict:
    return load_yaml(f"assumptions/{version}.yaml")
