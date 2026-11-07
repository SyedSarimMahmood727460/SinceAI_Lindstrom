"""Shared number formatting: the one place a metric value becomes text (used by exports,
the story cards and tests)."""
from __future__ import annotations

import math


def _scale(value: float, unit: str) -> tuple[float, str, int, float]:
    """Return (scaled value, display unit, decimals, divisor) chosen from the headline `value`."""
    a = abs(value)
    if unit == "l" and a >= 100_000:
        return value / 1000, "m³", 0, 1000
    if unit == "kWh" and a >= 100_000:
        return value / 1000, "MWh", 0, 1000
    if unit == "kgCO2e" and a >= 10_000:
        return value / 1000, "t CO2e", 1, 1000
    if unit == "kgCO2e":
        return value, "kg CO2e", 0, 1
    if unit == "ratio":
        return value * 100, "%", 1, 0.01
    if unit == "%":
        return value, "%", 1, 1
    if unit == "h" or unit.startswith("per 100") or unit == "kg/wearer":
        return value, unit, 1, 1
    return value, unit, 0, 1


def fmt_number(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    v, u, dec, _ = _scale(value, unit)
    num = f"{v:,.{dec}f}"
    if u == "%":
        return f"{num}%"
    return f"{num} {u}" if u and u != "count" else num


def fmt_value(metric) -> str:
    """Formatted headline value of a MetricResult/Kpi (shared by the builder and tests)."""
    return fmt_number(metric.value, metric.unit)


def fmt_range(metric) -> str:
    r = metric.range
    if r is None or r.low is None or r.high is None or metric.value is None:
        return ""
    _, u, dec, div = _scale(metric.value, metric.unit)
    lo, hi = r.low / div, r.high / div
    suffix = "%" if u == "%" else (f" {u}" if u else "")
    return f"{lo:,.{dec}f} – {hi:,.{dec}f}{suffix}"


# ---------------------------------------------------------------- compact style (meeting flow)
# Mirrored by fmtCompact in the web UI; vectors in tests/test_format.py. Each tier rounds first
# and then promotes the unit, so 999,999 EUR reads "€1.00M", not "€1,000k".
MINUS = "−"  # U+2212
NO_VALUE = "—"


def compact_num(a: float) -> str:
    """A plain compact count: 0 dp from 10 up (67, 230, 1,152), else 1 dp without a trailing zero."""
    return f"{a:,.0f}" if round(a, 1) >= 10 else f"{a:,.1f}".rstrip("0").rstrip(".")


def _compact_abs(a: float, unit: str) -> str | None:
    """Compact text for a non-negative value; None when the unit has no compact rule."""
    if unit == "EUR":
        if round(a) < 10_000:
            return f"€{a:,.0f}"
        if round(a / 1000) < 1000:
            return f"€{a / 1000:,.0f}k"
        return f"€{a / 1e6:,.2f}M"
    if unit == "l":
        return f"{a / 1000:,.0f} m³"
    if unit == "kgCO2e":
        if round(a) < 1000:
            return f"{a:,.0f} kg CO₂e"
        t = a / 1000
        return f"{t:,.0f} t CO₂e" if round(t, 1) >= 10 else f"{t:,.1f} t CO₂e"
    if unit == "h":
        return f"{a:,.0f} h"
    if unit == "kWh":
        return f"{a / 1000:,.0f} MWh" if round(a) >= 1000 else f"{a:,.0f} kWh"
    if unit == "ratio":
        return f"{a * 100:,.1f}%"
    if unit == "kg/wearer":
        return f"{compact_num(a)} kg per wearer"
    if unit.startswith("per 100"):
        return f"{compact_num(a)} {unit}"
    return None


def fmt_compact(value: float | None, unit: str) -> str:
    """Compact meeting style: €1.96M, €758k, €8,250, 1,407 m³, 255 t CO₂e, 1,152 h, 172 MWh, 98.3%.
    Negative values carry a true minus sign (−€297k); None, nan and inf are a dash."""
    if value is None or not math.isfinite(value):
        return NO_VALUE
    text = _compact_abs(abs(value), unit)
    if text is None:
        return fmt_number(value, unit)
    if value < 0 and any(ch in "123456789" for ch in text):  # never "−€0"
        text = MINUS + text
    return text


def fmt_compact_value(metric) -> str:
    """Compact text of the selected headline value of a MetricResult/Kpi."""
    return fmt_compact(metric.value, metric.unit)


def fmt_compact_range(metric) -> str:
    """'range €1.36M – €2.74M', or '' when there is no range (or both ends read the same)."""
    r = metric.range
    if r is None or r.low is None or r.high is None or metric.value is None:
        return ""
    lo, hi = sorted((r.low, r.high))
    a, b = fmt_compact(lo, metric.unit), fmt_compact(hi, metric.unit)
    return "" if a == b else f"range {a} – {b}"
