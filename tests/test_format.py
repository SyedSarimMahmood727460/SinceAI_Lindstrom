"""Compact number style (export.format.fmt_compact): shared vectors, mirrored by the JS fmtCompact."""
import pytest

from export.format import fmt_compact, fmt_compact_range, fmt_compact_value
from model.contracts import Range

VECTORS = [
    (1957510, "EUR", "€1.96M"), (757510, "EUR", "€758k"), (8250, "EUR", "€8,250"), (0, "EUR", "€0"),
    (-297100, "EUR", "−€297k"), (1406620, "l", "1,407 m³"), (255073.7, "kgCO2e", "255 t CO₂e"),
    (4200, "kgCO2e", "4.2 t CO₂e"), (850, "kgCO2e", "850 kg CO₂e"), (1152.4, "h", "1,152 h"),
    (172000, "kWh", "172 MWh"), (0.983, "ratio", "98.3%"), (None, "EUR", "—"), (9999, "EUR", "€9,999"),
    (10000, "EUR", "€10k"), (999999, "EUR", "€1.00M"),
    # round first, then promote the unit
    (1000000, "EUR", "€1.00M"), (9999.6, "EUR", "€10k"), (9960, "kgCO2e", "10 t CO₂e"),
    (999.7, "kgCO2e", "1.0 t CO₂e"), (999.6, "kWh", "1 MWh"), (-0.2, "EUR", "€0"),
    # site figures (step 3 tiles, same text as the story statement)
    (67.0175, "kg/wearer", "67 kg per wearer"), (48.81, "kg/wearer", "49 kg per wearer"),
    (230.4, "per 100 wearers", "230 per 100 wearers"), (4.3, "per 100 wearers", "4.3 per 100 wearers"),
    # non-finite values are a dash
    (float("nan"), "EUR", "—"), (float("inf"), "kgCO2e", "—"), (float("-inf"), "h", "—"),
]


@pytest.mark.parametrize("value,unit,expect", VECTORS)
def test_fmt_compact_vectors(value, unit, expect):
    assert fmt_compact(value, unit) == expect


class _M:
    def __init__(self, value, unit, rng=None):
        self.value, self.unit, self.range = value, unit, rng


def test_fmt_compact_range_and_value():
    m = _M(1957510, "EUR", Range(low=1360000, base=1957510, high=2740000))
    assert fmt_compact_value(m) == "€1.96M"
    assert fmt_compact_range(m) == "range €1.36M – €2.74M"
    assert fmt_compact_range(_M(5, "EUR")) == ""
    assert fmt_compact_range(_M(None, "EUR", Range(low=1, base=2, high=3))) == ""
    assert fmt_compact_range(_M(8250, "EUR", Range(low=8250, base=8250, high=8250))) == ""
    assert fmt_compact(24, "count") == "24"  # other units fall back to fmt_number
