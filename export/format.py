"""Shared number formatting: the one place a metric value becomes text (used by exports,
the story cards and tests)."""
from __future__ import annotations


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
