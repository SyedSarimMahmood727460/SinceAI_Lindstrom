"""Period strings to month lists."""
from __future__ import annotations

import re


def period_months(period: str) -> list[str]:
    """'2025' -> 12 months; '2025-Q2' -> its 3 months; '2025-04' -> that month."""
    if re.fullmatch(r"\d{4}", period):
        return [f"{period}-{mo:02d}" for mo in range(1, 13)]
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", period):
        q = int(m.group(2))
        return [f"{m.group(1)}-{mo:02d}" for mo in range(3 * q - 2, 3 * q + 1)]
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        return [period]
    raise ValueError(f"unrecognised period: {period!r}")
