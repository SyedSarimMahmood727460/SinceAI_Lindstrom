"""Pitch deck for the Lindström × Since AI 2026 judges (design §6, Task 11).

    python scripts/make_pitch_deck.py [--out docs/pitch/ValueReview_pitch.pptx]

Eight 16:9 slides in the export's brand style. Wording is static or read from config and the
committed Fazer snapshot; every figure comes from `build_review` (the engine) and goes through the
shared formatters in `export/format.py`. The demo scenario (an example contract price and a growth
scenario typed "by the account manager") is written to a private temp `VR_INPUTS_DIR`, so the
script never writes inputs into the repository. Slide 7 loads the sources with the extension pack
switched on; the other slides use the main pack only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pptx import Presentation  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Emu, Inches, Pt  # noqa: E402

from export.format import (  # noqa: E402
    fmt_compact, fmt_compact_range, fmt_compact_value, fmt_range, fmt_value)
from export.pptx_builder import (  # noqa: E402
    CONTENT_W, GREY, INK, LIGHT, MARGIN, NAVY, RED, SLIDE_H, SLIDE_W, WHITE, _rect, _run, _table,
    _textbox, clip)
from export.sections import PRIORITY_LABEL  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "pitch" / "ValueReview_pitch.pptx"
DISCLAIMER = "Prototype · synthetic data · not audited"
BODY = 14  # minimum font size anywhere on a slide
ACCOUNT = "CUST001"
# The demo scenario a KAM types in (docs/demo_script.md uses the same values).
# The contract price is what "Load demo scenario" computes for NorthStar: 60% of its full-year,
# unfiltered, base-case do-it-yourself total against local laundry (€1.96M), rounded to €10,000.
DEMO_INPUTS = {"contract_price_eur_per_year": 1_170_000, "extra_sites": 4,
               "extra_service_lines": ["mats"]}
FIT_ROWS = 8  # Lindström assets on slide 2 (the brief row is on slide 1)
ASKED = [  # rows of config/lindstrom_fit.yaml brief_map shown on slide 1, in this order
    "Customer-level managerial view with site drill-down",
    "Customer-ready review export",
    "Show customers they can save more by working with Lindström more",
    "Know where customer companies are going and how Lindström can help",
    "Easy to understand and explain for account managers",
    "A credible path to approved sources, more industries, countries and service lines",
]
_C1 = re.compile(r"customer washed_kg ([\d.]+) vs laundry washed_kg ([\d.]+)")


@contextmanager
def _env(**values):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------- drawing

def _slide(prs, title: str, n: int, subtitle: str | None = None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(s, 0, 0, SLIDE_W, Inches(0.95), NAVY)
    _rect(s, 0, Inches(0.95), SLIDE_W, Inches(0.06), RED)
    _, tf = _textbox(s, MARGIN, Inches(0.12), Inches(8.9), Inches(0.75), MSO_ANCHOR.MIDDLE)
    _run(tf.paragraphs[0], title, 30, True, WHITE)
    _, tf = _textbox(s, Inches(9.4), Inches(0.12), Inches(3.35), Inches(0.75), MSO_ANCHOR.MIDDLE)
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], "VALUE REVIEW", 16, True, WHITE)
    _run(tf.add_paragraph(), "Lindström × Since AI 2026", BODY, False, WHITE)
    tf.paragraphs[1].alignment = PP_ALIGN.RIGHT
    _rect(s, MARGIN, Inches(6.95), CONTENT_W, Emu(9525), GREY)
    _, tf = _textbox(s, MARGIN, Inches(6.98), Inches(11), Inches(0.4))
    _run(tf.paragraphs[0], f"{DISCLAIMER} · synthetic Lindström × Since AI data pack", BODY, False, GREY)
    _, tf = _textbox(s, Inches(11.7), Inches(6.98), Inches(1.05), Inches(0.4))
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], str(n), BODY, False, GREY)
    if subtitle:
        _, tf = _textbox(s, MARGIN, Inches(1.1), CONTENT_W, Inches(0.45))
        _run(tf.paragraphs[0], subtitle, 16, False, GREY, italic=True)
    return s


def _notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def _para(tf, first: bool):
    return tf.paragraphs[0] if first else tf.add_paragraph()


def _heading(tf, text, first=False, size=18, color=RED):
    p = _para(tf, first)
    p.space_after = Pt(4)
    _run(p, text, size, True, color)


def _lines(tf, items, size=BODY, color=INK, bullet="•", first=False, space=6):
    for it in (x for x in items if x):
        p = _para(tf, first)
        first = False
        p.space_after = Pt(space)
        _run(p, f"{bullet} {it}" if bullet else it, size, False, color)


def _box(slide, x, y, w, h, fill=LIGHT):
    _rect(slide, x, y, w, h, fill)
    _, tf = _textbox(slide, x + Inches(0.15), y + Inches(0.08), w - Inches(0.3), h - Inches(0.16))
    return tf


def _tile(slide, x, y, w, h, label, value, sub="", stacked=False):
    """Label, a big value and an optional range (on its own line when `stacked`)."""
    tf = _box(slide, x, y, w, h)
    _run(tf.paragraphs[0], label, BODY, False, GREY)
    p = tf.add_paragraph()
    _run(p, value, 22 if stacked else 26, True, NAVY)
    if sub:
        _run(tf.add_paragraph() if stacked else p, sub if stacked else f"   {sub}", BODY, False, GREY)


def _cite(url: str, date: str) -> str:
    host = urlsplit(url).netloc.removeprefix("www.")
    return f"Source: {host}, {date}" if date else f"Source: {host}"


# ---------------------------------------------------------------- data

def _reviews(tmp: Path) -> dict:
    """Every figure the deck shows, from the engine (build_review) and the export builders."""
    from api.build import build_review
    from api.review_model import ReviewParams
    from config.loader import load_assumptions, load_yaml
    from export.pdf_builder import build_pdf
    from export.pptx_builder import build_pptx
    from export.xlsx_builder import build_xlsx
    from model.inputs_store import save_inputs
    from model.load import load_sources

    out: dict = {}
    with _env(VR_INPUTS_DIR=str(tmp / "kam_inputs"), VR_EXTENSIONS="off"):
        con = load_sources()
        out["accounts_off"] = con.execute(
            "select count(*) from org_node where level = 'ACCOUNT'").fetchone()[0]
        plain = build_review(con, ReviewParams(account_id=ACCOUNT))
        save_inputs(ACCOUNT, DEMO_INPUTS, load_assumptions()["dto_inputs"])
        out["review"] = build_review(con, ReviewParams(account_id=ACCOUNT))
        out["plain"] = plain
        customer = build_review(con, ReviewParams(account_id=ACCOUNT, audience="customer"))
        exp = tmp / "exports"
        pptx = build_pptx(customer, exp / "review.pptx")
        pdf = build_pdf(customer, exp / "review.pdf")
        xlsx = build_xlsx(customer, exp / "review.xlsx", audience="customer")
        from openpyxl import load_workbook
        wb = load_workbook(xlsx)
        out["exports"] = {
            "pptx": len(Presentation(pptx).slides),
            "pdf": _pdf_pages(pdf),
            "xlsx": len(wb.sheetnames)}
        wb.close()
    with _env(VR_INPUTS_DIR=str(tmp / "kam_inputs_ext"), VR_EXTENSIONS="on"):
        con = load_sources()
        out["accounts_on"] = con.execute(
            "select count(*) from org_node where level = 'ACCOUNT'").fetchone()[0]
        out["hotel"] = build_review(con, ReviewParams(account_id="CUST004"))
        out["northstar_ext"] = build_review(con, ReviewParams(account_id=ACCOUNT))
        out["c1"] = sorted(r[0] for r in con.execute(
            "select distinct entity_id from dq_flags where check_id = 'C1'").fetchall())
    out["fit"] = load_yaml("lindstrom_fit.yaml")
    return out


def _pdf_pages(path: Path) -> int:
    try:
        from pypdf import PdfReader  # dev dependency
        return len(PdfReader(str(path)).pages)
    except ImportError:  # reportlab writes an uncompressed page tree
        return max(int(x) for x in re.findall(rb"/Count (\d+)", path.read_bytes()))


def _kpi(review, mid):
    return next(k for k in review.kpis if k.metric_id == mid)


def _l003(review) -> dict:
    """Customer kg routed to L003 vs the laundry's own kg over the period, from the C1 warnings."""
    cust = laundry = 0.0
    name = "L003"
    for w in review.data_quality.get("warnings", []):
        m = _C1.match(w.get("detail") or "")
        if w.get("check_id") == "C1" and w.get("entity_id") == "L003" and m:
            cust, laundry = cust + float(m[1]), laundry + float(m[2])
            name = w.get("entity_name") or name
    return {"name": name, "customer_kg": cust, "laundry_kg": laundry,
            "ratio": cust / laundry if laundry else None}


# ---------------------------------------------------------------- slides

def _s1_asked(prs, d, n):
    s = _slide(prs, "What you asked", n,
               "Your brief and your feedback, in our summary: show the imagined solution and "
               "demo it where possible.")
    where = {r["asked"]: r["where"] for r in d["fit"]["brief_map"]}
    rows = [[a, where[a]] for a in ASKED]
    _table(s, MARGIN, Inches(1.7), [6.4, 5.73], rows, ["You asked", "Where it is in Value Review"],
           size=BODY, row_h=0.66, header_size=16)
    _notes(s, "Lindström asked for a customer value and sustainability review a key account manager "
              "can open, tailor and hand to a customer. Your feedback added three things: help your "
              "team show customers they save more by working with Lindström more; AI that knows where "
              "customer companies are going and how Lindström can help; and dashboards that are easy "
              "for account managers to explain. Each row is a page you can click in the live demo.")


def _s2_fit(prs, d, n):
    fit = d["fit"]
    s = _slide(prs, "Built on Lindström's work", n,
               "Each part maps to something Lindström already has. Public facts are context only, never inputs.")
    kind = {"PUBLIC_REFERENCE": "Public", "DATA_PACK": "Data pack", "BRIEF": "Brief"}
    assets = [a for a in fit["assets"] if a["kind"] != "BRIEF"][:FIT_ROWS]
    rows = [[a["asset"].split(" (")[0].split(";")[0], clip(a["value_review"], 118), kind[a["kind"]]] for a in assets]
    _table(s, MARGIN, Inches(1.6), [3.3, 7.3, 1.53], rows,
           ["Lindström asset", "How Value Review uses or extends it", "Source"],
           size=BODY, row_h=0.56, header_size=16)
    _notes(s, "We started from your material, not a blank dashboard: the managerial dashboard mockups "
              "(same modules and packs), eLindström (we propose this as a portal module), RFID "
              "tracking (utilisation and on-time), the Tableau reports (one adapter per report), the "
              "WWS laundry calculator (per-kg allocation), the Sustainability Report (context only), "
              "repairs, and your data-pack assumptions A001–A008 used verbatim. The same table is the "
              "in-app page 'Built on Lindström's work', with the source link for every public fact.\n"
              + "\n".join(f"- {a['asset']}: {a['source']}" for a in assets))


def _s3_story(prs, d, n):
    r, dm = d["plain"], d["review"]
    cards = {c["id"]: c for c in r.story}
    water, co2 = _kpi(r, "water_saving_l"), _kpi(r, "co2_saving_kg")
    dto, g = dm.dto, dm.growth
    hrs = dto.convenience.get("staff_hours_freed")
    best = (cards.get("biggest_improvement") or {}).get("facts") or {}
    t = g["totals"]
    s = _slide(prs, "Easy to explain: a guided customer meeting", n,
               f"Five steps, one message each. {r.meta.node.name} (synthetic), {r.meta.period}, "
               f"vs {r.meta.baseline.get('name', '').lower()}; the demo scenario is switched on.")
    steps = [
        ("1 · What you got",
         [f"{fmt_compact_value(water)} of water saved", f"{fmt_compact_value(co2)} avoided",
          f"{fmt_compact_value(hrs)} of staff time freed" if hrs is not None else ""],
         fmt_compact_range(co2)),
        ("2 · Vs doing it yourself",
         [f"About {fmt_compact(dto.net.value, 'EUR')} less with Lindström",
          f"{fmt_compact_value(dto.diy_total)} do it yourself vs {fmt_compact_value(dto.contract_price)} contract"],
         ("net " + fmt_compact_range(dto.net)) if fmt_compact_range(dto.net) else ""),
        ("3 · Where to improve",
         [f"{best['site_name']}: {best['value']:.0f} kg per wearer",
          f"Typical across sites: {best['typical']:.0f} kg"] if best else ["The site that stands out, in one sentence"],
         "One site, one action"),
        ("4 · Grow together",
         [f"{g['inputs']['extra_sites']} more sites + Mats",
          f"{fmt_compact_value(t["diy_cost_avoided"])} avoided a year",
          f"{fmt_compact_value(t["co2_saving_kg"])} saved"],
         fmt_compact_range(t["diy_cost_avoided"])),
        ("5 · Agree next steps",
         ["Discussion points", "Actions with an owner and a target", "Export: PowerPoint, PDF, Excel"],
         "Same order in the exports"),
    ]
    gap = Inches(0.1)
    w = int((CONTENT_W - gap * 4) / 5)
    for i, (head, lines, rng) in enumerate(steps):
        tf = _box(s, MARGIN + (w + gap) * i, Inches(1.65), w, Inches(3.3))
        _heading(tf, head, first=True, size=16)
        for j, line in enumerate(x for x in lines if x):
            p = tf.add_paragraph()
            p.space_after = Pt(4)
            _run(p, line, 18 if j == 0 else BODY, j == 0, NAVY if j == 0 else INK)
        _run(tf.add_paragraph(), rng, BODY, False, GREY, italic=True)
    _, tf = _textbox(s, MARGIN, Inches(5.1), CONTENT_W, Inches(1.8))
    _lines(tf, ["Each step: one message, two or three big numbers, and the sentence to say (What to say, with Copy).",
                "Steps 2 and 4 never open empty: a KAM-only Load demo scenario button fills example numbers.",
                "Customer view: no edit controls, no Account intelligence, no internal metrics.",
                "Expert shows how each figure is calculated; the exports follow the same five steps."],
           first=True, space=3)
    _notes(s, "The landing page is a five-step meeting a KAM can run: What you got, Versus doing it "
              "yourself, Where to improve, Grow together, Agree next steps. Each step has one message, "
              "two or three big numbers in one compact style (with the range on a second line) and a "
              "What to say line. The demo scenario button fills an example contract price (60% of the "
              "do-it-yourself total, rounded to 10,000 euros), four more sites and the Mats service, so "
              "steps 2 and 4 are never empty; the KAM can edit or reset it. In the customer view the "
              "edit controls, the intelligence page and internal metrics are hidden. PowerPoint, PDF and "
              "Excel follow the same five steps; the coaching lines are in the PowerPoint speaker notes "
              "only.\n" + "\n".join(f"{c['title']}: {c['statement']}" for c in r.story))


def _s4_more(prs, d, n):
    r = d["review"]
    dto, g = r.dto, r.growth
    s = _slide(prs, "Save more by working with us more", n,
               f"{r.meta.node.name}, per year, vs {r.meta.baseline.get('name', '').lower()}. "
               "Typed by the KAM, defaults otherwise.")
    w, gap = Inches(5.95), Inches(0.23)
    for i, head in enumerate(("Service vs doing it yourself",
                              f"Grow with us: {g['inputs']['extra_sites']} more sites + Mats")):
        _, tf = _textbox(s, MARGIN + (w + gap) * i, Inches(1.6), w, Inches(0.45))
        _heading(tf, head, first=True)
    y, h, step = Inches(2.1), Inches(1.05), Inches(1.13)
    x2 = MARGIN + w + gap
    _tile(s, MARGIN, y, w, h, "Doing it yourself would cost", fmt_value(dto.diy_total),
          f"range {fmt_range(dto.diy_total)}", stacked=True)
    _tile(s, MARGIN, y + step, w, h, "Example contract price typed by the KAM",
          fmt_value(dto.contract_price), "entered on the page", stacked=True)
    _tile(s, MARGIN, y + step * 2, w, h, "Net: doing it yourself minus the contract",
          fmt_value(dto.net), f"range {fmt_range(dto.net)}", stacked=True)
    t = g["totals"]
    _tile(s, x2, y, w, h, "Extra do-it-yourself cost avoided", fmt_value(t["diy_cost_avoided"]),
          f"range {fmt_range(t['diy_cost_avoided'])}", stacked=True)
    _tile(s, x2, y + step, w, h, "Extra CO₂e saved", fmt_value(t["co2_saving_kg"]),
          f"range {fmt_range(t['co2_saving_kg'])}", stacked=True)
    _tile(s, x2, y + step * 2, w, h, "Extra water saved", fmt_value(t["water_saving_l"]),
          f"range {fmt_range(t['water_saving_l'])}", stacked=True)
    extra = next((x for x in dto.lines if not x.in_total), None)
    _, tf = _textbox(s, MARGIN, Inches(5.5), w, Inches(1.4))
    _lines(tf, [f"{extra.label}: shown, not in the total." if extra else "",
                "Net appears only once a contract price is entered."], first=True, space=3)
    _, tf = _textbox(s, x2, Inches(5.5), w, Inches(1.4))
    skipped = ", ".join(x["id"].title() for x in g.get("skipped_lines") or [])
    _lines(tf, [f"Skipped {skipped}: already used by this customer." if skipped else "",
                "€, hours and CO₂e are never added into one score."], first=True, space=3)
    _notes(s, "Left: the service versus doing it yourself, from the customer's own volumes and "
              "defaults the KAM can overwrite (local laundry price, energy, water, staff cost, "
              "handling time, admin time, garment life). The net appears only when the KAM types the "
              "contract price; here an example price. "
              f"{extra.label if extra else 'Extra replacements'} are shown but kept out of the total. "
              "Right: growth. The KAM enters sites not yet served and ticks service lines not yet "
              "used; lines the customer already uses are skipped. Each lever is scaled from the "
              "customer's own averages, with a range.\n"
              f"Story line: {g.get('statement') or ''}")


def _s5_intel(prs, d, n):
    from ai.intel import load_snapshot
    rep = load_snapshot("fazer-group")
    sec = rep.sections
    s = _slide(prs, "Knows where your customers are going", n,
               f"Account intelligence · {rep.company} (a real public company) · snapshot from "
               f"{rep.generated_at[:10]}")
    claims = [sec.direction[1], sec.direction[2], sec.sustainability[1]]
    _, tf = _textbox(s, MARGIN, Inches(1.6), Inches(7.3), Inches(4.7))
    _heading(tf, "Where they're going", first=True)
    for c in claims:
        p = tf.add_paragraph()
        p.space_before = Pt(6)
        _run(p, c.text, BODY)
        _run(tf.add_paragraph(), _cite(c.source_url, c.source_date), BODY, False, GREY, italic=True)
    x = MARGIN + Inches(7.55)
    tf = _box(s, x, Inches(1.6), Inches(4.58), Inches(4.7))
    _heading(tf, "How Lindström can help", first=True)
    _lines(tf, [h.offer_name for h in sec.how_lindstrom_helps], space=2)
    _heading(tf, "Ask in the next meeting")
    _run(tf.add_paragraph(), sec.conversation_starters[0], BODY, False, INK, italic=True)
    _, tf = _textbox(s, MARGIN, Inches(6.4), CONTENT_W, Inches(0.5))
    _run(tf.paragraphs[0], rep.disclaimer, BODY, True, RED)
    _notes(s, "The KAM types a company name. Claude researches it with web search; code keeps only "
              "claims whose source the search actually returned, with a date and a safe http(s) "
              "address; Lindström offers must come from our service catalogue and cite a source. No "
              "engine numbers are mixed in. Without an API key, or if the live call fails, the "
              "committed snapshot is shown, and the snapshot chips never call the API. For the "
              "fictional customers the page explains that, in production, the legal name would come "
              "from CRM.\nSources:\n" + "\n".join(f"- {x.title} ({x.date}): {x.url}" for x in rep.sources))


def _s6_credible(prs, d, n):
    r = d["plain"]
    co2 = _kpi(r, "co2_saving_kg")
    l3 = _l003(r)
    s = _slide(prs, "Credible by design", n)
    w, h, gap = Inches(5.95), Inches(2.55), Inches(0.23)
    boxes = [
        ("Every figure has a status and a range",
         [f"CO₂e avoided: {fmt_value(co2)} (range {fmt_range(co2)}), "
          f"{co2.method_status.value.lower()}.",
          "Measured · calculated · allocated · estimated; baselines and assumptions are visible."]),
        ("We flag what doesn't add up",
         [f"Check C1: customer kg routed to laundry {l3['name']} (L003) is "
          f"≈{l3['ratio']:.1f}× the laundry's own total over {r.meta.period}."
          if l3["ratio"] else "Check C1 runs on every load.",
          "Flagged, confidence lowered, open question Q35."]),
        ("Honest comparisons",
         ["The baseline is a visible choice (local laundry, home, in-house).",
          "Extra replacements shown, not in the do-it-yourself total; net only with a contract price."]),
        ("AI never writes numbers",
         ["The narrative uses placeholders the engine fills; a guard rejects invented digits.",
          "Intel keeps only searched, dated, safe sources; snapshot chips don't call the API."]),
    ]
    for i, (head, items) in enumerate(boxes):
        x = MARGIN + (w + gap) * (i % 2)
        y = Inches(1.3) + (h + Inches(0.2)) * (i // 2)
        tf = _box(s, x, y, w, h)
        _heading(tf, head, first=True)
        _lines(tf, items, space=4)
    _notes(s, "Credibility is built in, not added later. Two labels on every value (method status and "
              "provenance), a low/base/high range on every estimate, and the weakest-input rule. The "
              f"consistency check found that customer kg routed to laundry {l3['name']} is about "
              f"{l3['ratio']:.1f} times the laundry's own total over the year. We did not hide or fix it: "
              "affected figures get lower confidence and a warning, and we ask Lindström (Q35). "
              "Washing and repair savings, euros, hours and CO₂e are never summed into one number.")


def _s7_grows(prs, d, n):
    hotel, ns_off, ns_on = d["hotel"], d["plain"], d["northstar_ext"]
    pack = ROOT / "data" / "extension_pack"
    csvs = len(list(pack.glob("*.csv")))
    s = _slide(prs, "Grows with your business", n,
               "A new service line, industry, customer and country: data and config only.")
    tf = _box(s, MARGIN, Inches(1.65), Inches(5.95), Inches(5.1))
    _heading(tf, "The whole change", first=True)
    for path, what in (("config/sources.yaml", "+1 line: the extension pack"),
                       ("data/extension_pack/", f"{csvs} CSV files (synthetic)"),
                       ("config/industry_rules.yaml", "Hospitality priorities and note")):
        p = tf.add_paragraph()
        p.space_before = Pt(6)
        _run(p, path, BODY, True, NAVY).font.name = "Consolas"
        _run(tf.add_paragraph(), what, BODY)
    _heading(tf, "Proof test")
    _run(tf.add_paragraph(), "tests/test_extensibility.py adds Washroom, Restaurants and Latvia "
                             "from a temporary CSV pack: no code edits.", BODY)
    x = MARGIN + Inches(6.18)
    _, tf = _textbox(s, x, Inches(1.65), Inches(5.95), Inches(5.1))
    _heading(tf, "What appears in the app", first=True)
    node = hotel.meta.node
    pri = ", ".join(PRIORITY_LABEL.get(p, p) for p in hotel.context.active_priorities)
    co2_off, co2_on = fmt_value(_kpi(ns_off, "co2_saving_kg")), fmt_value(_kpi(ns_on, "co2_saving_kg"))
    same = "unchanged" if co2_off == co2_on else "changed"
    _lines(tf, [f"Customers: {d['accounts_off']} → {d['accounts_on']}: {node.name} ({node.industry})",
                f"{len(hotel.sites)} sites in {', '.join(node.countries)}",
                f"Service lines: {', '.join(hotel.meta.service_lines)}",
                f"Priorities from the {node.industry} rule: {pri}",
                f"{ns_off.meta.node.name} {same}: CO₂e avoided {co2_on}",
                f"Check C1 still flags only {', '.join(d['c1'])}"], space=8)
    _notes(s, "Lindström adds a service line and a hotel chain in Estonia; this is the whole change. "
              "A second adapter (a generic CSV adapter) reads the pack; the engine, insights, UI and "
              "exports did not change for it. Switch it off with VR_EXTENSIONS=off for a before and "
              "after. Existing customers' figures do not move, and the laundry volume check still "
              "flags only L003. A test builds a third pack (Washroom, Restaurants, Latvia) in a temp "
              "folder and proves it needs no code edits.")


def _s8_exports(prs, d, n):
    e = d["exports"]
    s = _slide(prs, "Exports & path to production", n)
    _, tf = _textbox(s, MARGIN, Inches(1.25), Inches(5.95), Inches(0.45))
    _heading(tf, "One ReviewModel, three formats", first=True)
    for i, (label, val) in enumerate((("PowerPoint", f"{e['pptx']} slides"),
                                      ("PDF", f"{e['pdf']} pages"),
                                      ("Excel", f"{e['xlsx']} sheets"))):
        _tile(s, MARGIN, Inches(1.8) + Inches(1.0) * i, Inches(5.95), Inches(0.9), label, val)
    _, tf = _textbox(s, MARGIN, Inches(4.85), Inches(5.95), Inches(2.0))
    _lines(tf, ["Built for NorthStar while making this deck.",
                "Same numbers as the dashboard; the disclaimer on every page.",
                "Customer audience hides internal metrics."], first=True, space=3)
    tf = _box(s, MARGIN + Inches(6.18), Inches(1.25), Inches(5.95), Inches(5.55))
    _heading(tf, "Path to production", first=True)
    _lines(tf, ["Tier 0: synthetic pack (built)",
                "Tier 1: Tableau / eLindström exports for one pilot customer",
                "Tier 2: governed data platform",
                "Tier 3: a module inside eLindström"], space=2)
    _heading(tf, "What we need from Lindström")
    _lines(tf, ["Q35: which L003 volume figure is right",
                "Approved emission factors and baselines",
                "Contract prices, and CRM legal names for intel"], space=2)
    _notes(s, "Exports work: the same ReviewModel feeds the dashboard, PowerPoint, PDF (server-side, "
              "no Office needed) and Excel (numbers as numbers, with status labels). The counts on the "
              "left come from exports generated while building this deck. Next: one pilot customer's "
              "Tier 1 exports through a new adapter; the engine, UI and exports stay as they are. We "
              "need answers to Q35, approved emission factors, and contract prices plus CRM legal "
              "names so intel can run on real accounts. Prototype, synthetic data, not audited.")


SLIDES = [_s1_asked, _s2_fit, _s3_story, _s4_more, _s5_intel, _s6_credible, _s7_grows, _s8_exports]


def build_pitch(out_path: Path = DEFAULT_OUT) -> Path:
    with tempfile.TemporaryDirectory(prefix="vr_pitch_", ignore_cleanup_errors=True) as tmp:
        data = _reviews(Path(tmp))
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    for i, fn in enumerate(SLIDES, start=1):
        fn(prs, data, i)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return out_path


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    os.environ.setdefault("VR_AI", "off")
    print(build_pitch(args.out))


if __name__ == "__main__":
    main()
