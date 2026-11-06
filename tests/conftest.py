import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK = (
    "../lindstrom_pack/Lindstrom_SinceAI2026/"
    "Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx"
)


@pytest.fixture(scope="session")
def pack_path() -> Path:
    path = (ROOT / os.environ.get("VR_PACK_PATH", DEFAULT_PACK)).resolve()
    if not path.exists():
        pytest.skip(f"data pack not found: {path}")
    return path


@pytest.fixture(scope="session")
def con(pack_path):
    from model.load import load_pack

    return load_pack(pack_path)
