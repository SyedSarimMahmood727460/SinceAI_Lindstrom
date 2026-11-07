"""Generate the synthetic extension pack (Baltic Harbour Hotels, Mats, Estonia).

Deterministic: seeded RNG, fixed float formatting, LF line endings, UTF-8 without BOM.
Usage: python scripts/make_extension_pack.py --out data/extension_pack
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 2026
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
CUSTOMER = "CUST004"
LAUNDRY = "L002"
STATUS = "SYNTHETIC"
CUSTOMERS = [{
    "customer_id": CUSTOMER, "customer_name": "Baltic Harbour Hotels", "industry": "Hospitality",
    "segment": "High Value", "hq_country": "Finland",
    "priority_topics": "Hygiene|Guest experience|Cost optimization|Water efficiency",
    "data_status": STATUS,
}]
# site_id, name, country, city, relative size
SITES = [
    ("S101", "Harbour Hotel Helsinki", "Finland", "Helsinki", 1.3),
    ("S102", "Harbour Hotel Turku", "Finland", "Turku", 0.9),
    ("S103", "Harbour Hotel Tallinn", "Estonia", "Tallinn", 1.1),
    ("S104", "Harbour Hotel Tartu", "Estonia", "Tartu", 0.8),
    ("S105", "Harbour Hotel Pärnu", "Estonia", "Pärnu", 0.7),
]
# product_id, name, group, service_line, weight kg, footprint kgCO2e, cost EUR
NEW_PRODUCTS = [
    ("P2001", "Entrance Mat Standard", "Mats", "Mats", 2.8, 21.0, 85),
    ("P2002", "Logo Mat", "Mats", "Mats", 3.5, 26.5, 140),
]
# product_id -> (weight kg, footprint kgCO2e, service line, allocated pieces per unit size,
#                washes per piece per month (lo, hi), has wearers)
RENTED = {
    "P1001": (0.85, 18.5, "Workwear", 24, (2.5, 3.5), True),
    "P1002": (0.62, 13.2, "Workwear", 24, (2.5, 3.5), True),
    "P2001": (2.8, 21.0, "Mats", 16, (3.5, 4.5), False),
    "P2002": (3.5, 26.5, "Mats", 6, (3.5, 4.5), False),
}
REPAIR_TYPES = ["BUTTON", "DARNING / PATCHING", "ZIPPER", "OTHER SEAM STITCHING"]
LATE_SHARE = 0.03


def _write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([r[h] for h in header])


def _f(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}"


def _alloc(base: int, size: float) -> int:
    return max(2, round(base * size))


def _activity(rng: random.Random) -> list[dict]:
    rows = []
    for month in MONTHS:
        for sid, _n, _c, _city, size in SITES:
            for pid, (wt, _fp, _sl, base, (lo, hi), wearers) in RENTED.items():
                alloc = _alloc(base, size)
                scanned = round(alloc * rng.uniform(0.85, 0.97))
                washed = round(alloc * rng.uniform(lo, hi))
                packed = washed - rng.randint(0, 6)
                n_wear = round(alloc * rng.uniform(0.88, 0.97)) if wearers else 0
                rows.append({
                    "month": month, "customer_id": CUSTOMER, "site_id": sid, "laundry_id": LAUNDRY,
                    "product_id": pid, "active_wearers": n_wear, "allocated_pieces": alloc,
                    "active_assets_scanned": scanned, "washed_pieces": washed,
                    "packed_pieces": packed, "washing_pct": _f(washed / alloc * 100),
                    "customer_washed_kg": _f(washed * wt),
                    "service_requests": rng.randint(0, 2 if wearers else 1), "data_status": STATUS,
                })
    return rows


def _cycles(rng: random.Random) -> list[dict]:
    rows = []
    fmt = "%Y-%m-%d %H:%M:%S"
    for sid, _n, _c, _city, size in SITES:
        for pid, (_wt, _fp, _sl, base, _w, _wr) in RENTED.items():
            for i in range(1, _alloc(base, size) + 1):
                asset = f"H{sid[1:]}{pid[1:]}{i:03d}"
                n = 0
                for mi in range(12):
                    for day in sorted(rng.sample(range(1, 29), 2)):  # ~2 cycles per asset-month
                        n += 1
                        pickup = datetime(2025, mi + 1, day)
                        hours = rng.randint(30, 134)
                        late = rng.random() < LATE_SHARE
                        if late:
                            hours += rng.randint(48, 96)
                        delivered = pickup + timedelta(hours=hours)
                        in_lau = pickup + timedelta(hours=rng.randint(6, 30))
                        out_lau = in_lau + timedelta(
                            hours=max(1, int((hours - 30) * rng.uniform(0.4, 0.7))))
                        rows.append({
                            "asset_id": asset, "cycle_number": n, "customer_id": CUSTOMER,
                            "site_id": sid, "laundry_id": LAUNDRY, "product_id": pid,
                            "pickup_timestamp": pickup.strftime("%Y-%m-%d"),
                            "in_laundry_timestamp": in_lau.strftime(fmt),
                            "out_laundry_timestamp": out_lau.strftime(fmt),
                            "delivered_timestamp": delivered.strftime(fmt),
                            "cycle_hours": hours,
                            "performance_flag": "LATE" if late else "ON_TIME",
                            "data_status": STATUS,
                        })
    return rows


def _repairs(rng: random.Random) -> list[dict]:
    rows = []
    for month in MONTHS:
        for sid, _n, _c, _city, size in SITES:
            for pid in ("P1001", "P1002"):
                _wt, fp, _sl, base, _w, _wr = RENTED[pid]
                alloc = _alloc(base, size)
                for rtype in REPAIR_TYPES:
                    if rng.random() < 0.35:
                        continue
                    n = rng.randint(1, 3)
                    rows.append({
                        "month": month, "customer_id": CUSTOMER, "site_id": sid,
                        "product_id": pid, "laundry_id": LAUNDRY, "repair_type": rtype,
                        "repair_count": n, "repair_quotient_pct": _f(n / alloc * 100, 2),
                        "estimated_replacements_postponed": n,
                        "product_footprint_kgco2e": _f(fp),
                        "estimated_avoided_product_kgco2e": _f(n * fp),
                        "data_status": "SYNTHETIC_ESTIMATE",
                    })
    return rows


def generate(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    _write(out / "customers.csv", list(CUSTOMERS[0]), CUSTOMERS)
    sites = [{"site_id": s, "customer_id": CUSTOMER, "site_name": n, "country": c, "city": city,
              "site_type": "Hotel", "primary_laundry_id": LAUNDRY, "data_status": STATUS}
             for s, n, c, city, _ in SITES]
    _write(out / "sites.csv", list(sites[0]), sites)
    products = [{"product_id": p, "product_name": n, "product_group": g, "service_line": sl,
                 "avg_weight_kg": _f(w, 2), "synthetic_product_footprint_kgco2e": _f(fp),
                 "synthetic_purchase_cost_eur": str(cost), "material_note": "synthetic mat"}
                for p, n, g, sl, w, fp, cost in NEW_PRODUCTS]
    _write(out / "products.csv", list(products[0]), products)
    act = _activity(rng)
    _write(out / "service_activity.csv", list(act[0]), act)
    cyc = _cycles(rng)
    _write(out / "service_cycles.csv", list(cyc[0]), cyc)
    rep = _repairs(rng)
    _write(out / "repairs.csv", list(rep[0]), rep)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/extension_pack", type=Path)
    generate(ap.parse_args().out)


if __name__ == "__main__":
    main()
