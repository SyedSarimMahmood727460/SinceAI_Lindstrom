import os
from pathlib import Path

import pytest

# the existing suite runs on the main pack only; extension tests switch this on explicitly
os.environ.setdefault("VR_EXTENSIONS", "off")

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


@pytest.fixture(autouse=True)
def _no_llm_by_default(monkeypatch, tmp_path):
    """No test touches the network: AI is off and logs go to a temp dir unless a test opts in."""
    monkeypatch.setenv("VR_AI", "off")
    monkeypatch.setenv("VR_LOG_DIR", str(tmp_path / "logs"))
