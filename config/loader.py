"""YAML config loading (paths are relative to the config/ directory)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent


def load_yaml(name: str) -> dict:
    # VR_CONFIG_DIR (read per call, so tests can swap it) points at an alternative config dir
    base = Path(os.environ.get("VR_CONFIG_DIR") or CONFIG_DIR)
    with open(base / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_assumptions(version: str = "v1") -> dict:
    return load_yaml(f"assumptions/{version}.yaml")
