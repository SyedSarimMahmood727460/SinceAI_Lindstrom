"""matplotlib charts for the PPTX export (PNG files in a temp dir). Numbers come from the ReviewModel only."""
from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401

NAVY = "#1B2A4A"
RED = "#D71920"
GREY = "#6B7280"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FOOTPRINT_IDS = [("footprint_pct_of_baseline_water", "Water"),
                 ("footprint_pct_of_baseline_energy", "Energy"),
                 ("footprint_pct_of_baseline_co2", "CO₂e")]


def _tmp_png(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix="vr_chart_")) / name


def _placeholder(path: Path, size: tuple[float, float], text: str) -> Path:
    fig, ax = plt.subplots(figsize=size, dpi=200)
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=16, color=GREY)
    fig.savefig(path, bbox_inches="tight", transparent=False, facecolor="white")
    plt.close(fig)
    return path


def footprint_pct_chart(review) -> Path:
    """Allocated footprint as % of baseline (100% = baseline), with low-high whiskers."""
    path = _tmp_png("footprint_pct.png")
    by_id = {k.metric_id: k for k in review.kpis}
    rows = [(label, by_id[mid]) for mid, label in FOOTPRINT_IDS
            if mid in by_id and by_id[mid].value is not None]
    if not rows:
        return _placeholder(path, (7.2, 4.6), "No data for this filter")
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    labels = [r[0] for r in rows][::-1]
    vals = [r[1].value for r in rows][::-1]
    lo = [(r[1].range.low if r[1].range and r[1].range.low is not None else r[1].value) for r in rows][::-1]
    hi = [(r[1].range.high if r[1].range and r[1].range.high is not None else r[1].value) for r in rows][::-1]
    err = [[max(v - a, 0) for v, a in zip(vals, lo)], [max(b - v, 0) for v, b in zip(vals, hi)]]
    ax.barh(labels, vals, color=NAVY, height=0.5, xerr=err,
            error_kw={"ecolor": RED, "capsize": 5, "elinewidth": 1.6})
    ax.axvline(100, color=RED, linestyle="--", linewidth=1.5)
    ax.text(100, len(rows) - 0.45, "Baseline = 100%", color=RED, ha="right", va="bottom", fontsize=11)
    xmax = max(max(hi), 100) * 1.18
    ax.set_xlim(0, xmax)
    for i, v in enumerate(vals):
        ax.text(min(v, 100) / 2 if v > 18 else v + 1.5, i, f"{v:.1f}%",
                va="center", ha="center" if v > 18 else "left",
                color="white" if v > 18 else NAVY, fontsize=13, fontweight="bold")
    ax.set_xlabel("Allocated footprint as % of baseline (whiskers: low–high range)", fontsize=11, color=GREY)
    ax.tick_params(axis="y", labelsize=13)
    ax.tick_params(axis="x", labelsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def repairs_by_month_chart(review) -> Path:
    path = _tmp_png("repairs_by_month.png")
    data = (review.circularity or {}).get("repairs_by_month") or []
    data = [d for d in data if d.get("repairs") is not None]
    if not data:
        return _placeholder(path, (5.2, 3.2), "No repair data")
    labels = []
    for d in data:
        try:
            labels.append(MONTHS[int(str(d["month"])[5:7]) - 1])
        except (ValueError, IndexError):
            labels.append(str(d["month"]))
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=200)
    ax.bar(labels, [d["repairs"] for d in data], color=NAVY)
    ax.set_title("Repairs completed per month", fontsize=12, color=NAVY, loc="left")
    ax.tick_params(axis="both", labelsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path
