"""Pitch deck for the Lindström × Since AI 2026 judges (design §6, Task 11).

    python scripts/make_pitch_deck.py [--out docs/pitch/Threadline_pitch.pptx]

Twelve 16:9 slides in the export's brand style, with real screenshots (docs/pitch/img), charts and tables. Wording is static or read from config and the
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
from export import charts as chart_lib  # noqa: E402
from export.sections import PRIORITY_LABEL  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "pitch" / "Threadline_pitch.pptx"
IMG_DIR = ROOT / "docs" / "pitch" / "img"  # real screenshots of the app, taken at 1600 x 900
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
    _run(tf.paragraphs[0], "THREADLINE", 16, True, WHITE)
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
               "Threadline turns a multi-site customer's data into a clear, honest review for the "
               "annual meeting.")
    where = {r["asked"]: r["where"] for r in d["fit"]["brief_map"]}
    rows = [[a, where[a]] for a in ASKED]
    _table(s, MARGIN, Inches(1.7), [6.4, 5.73], rows, ["You asked", "Where it is in Threadline"],
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
           ["Lindström asset", "How Threadline uses or extends it", "Source"],
           size=BODY, row_h=0.56, header_size=16)
    _notes(s, "We started from your material, not a blank dashboard: the managerial dashboard mockups "
              "(same modules and packs), eLindström (we propose this as a portal module), RFID "
              "tracking (utilisation and on-time), the Tableau reports (one adapter per report), the "
              "WWS laundry calculator (per-kg allocation), the Sustainability Report (context only), "
              "repairs, and your data-pack assumptions A001–A008 used verbatim. "
              "Every public fact is listed below with its source link.\n"
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
               "demo scenario on.")
    steps = [
        ("1 · What you got",
         [f"{fmt_compact_value(water)} of water saved", f"{fmt_compact_value(co2)} avoided",
          f"{fmt_compact_value(hrs)} of staff time freed" if hrs is not None else ""],
         fmt_compact_range(co2)),
        ("2 · Vs doing it yourself",
         [f"About {fmt_compact(dto.net.value, 'EUR')} less with Lindström",
          f"{fmt_compact_value(dto.diy_total)} do it yourself vs {fmt_compact_value(dto.contract_price)} example contract"],
         ("net " + fmt_compact_range(dto.net)) if fmt_compact_range(dto.net) else ""),
        ("3 · Where to improve",
         [f"{best['site_name']}: {best['value']:.0f} kg per wearer",
          f"Typical across sites: {best['typical']:.0f} kg"] if best else ["The site that stands out, in one sentence"],
         "One site, one action"),
        ("4 · Grow together",
         [f"{g['inputs']['extra_sites']} more sites + Mats",
          f"{fmt_compact_value(t["diy_cost_avoided"])} do-it-yourself cost avoided a year",
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
                "Customer view: no edit controls, no Company insights, no internal metrics.",
                "Expert shows how each figure is calculated; the exports follow the same five steps."],
           first=True, space=3)
    _notes(s, "The landing page is a five-step meeting a KAM can run: What you got, Versus doing it "
              "yourself, Where to improve, Grow together, Agree next steps. Each step has one message, "
              "two or three big numbers in one compact style (with the range on a second line) and a "
              "What to say line. The demo scenario button fills an example contract price (60% of the "
              "do-it-yourself total, rounded to 10,000 euros), four more sites and the Mats service, so "
              "steps 2 and 4 are never empty; the KAM can edit or reset it. In the customer view the "
              "edit controls, the Company insights page and internal metrics are hidden. PowerPoint, PDF and "
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
               f"Internal view for the account manager · {rep.company}, a real public company · "
               f"snapshot from {rep.generated_at[:10]}")
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
        ("Every figure has a status, every estimate a range",
         [f"CO₂e avoided: {fmt_value(co2)} (range {fmt_range(co2)}), "
          f"{co2.method_status.value.lower()}.",
          "Measured · calculated · allocated · estimated; baselines and assumptions are visible."]),
        ("We flag what doesn't add up",
         [f"One laundry ({l3['name']}, L003) reports about {l3['ratio']:.0f} times more customer "
          f"volume than it processed in {r.meta.period}."
          if l3["ratio"] else "Volume checks run on every load.",
          "We flag it, lower the confidence and ask Lindström which figure is right."]),
        ("Honest comparisons",
         ["The baseline is a visible choice (local laundry, home, in-house).",
          "Extra replacements shown, not in the do-it-yourself total; net only with a contract price."]),
        ("AI never writes numbers",
         ["The narrative uses placeholders the engine fills; a guard rejects invented digits.",
          "Company insights keeps only searched, dated sources with safe links."]),
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
    _heading(tf, "One review, three formats", first=True)
    for i, (label, val) in enumerate((("PowerPoint", f"{e['pptx']} slides"),
                                      ("PDF", f"{e['pdf']} pages"),
                                      ("Excel", f"{e['xlsx']} sheets"))):
        _tile(s, MARGIN, Inches(1.8) + Inches(1.0) * i, Inches(5.95), Inches(0.9), label, val)
    _, tf = _textbox(s, MARGIN, Inches(4.85), Inches(5.95), Inches(2.0))
    _lines(tf, ["Counts are for the NorthStar customer review export, not this deck.",
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
                "Contract prices, and CRM legal names for Company insights"], space=2)
    _notes(s, "Exports work: the same ReviewModel feeds the dashboard, PowerPoint, PDF (server-side, "
              "no Office needed) and Excel (numbers as numbers, with status labels). The counts on the "
              "left come from exports generated while building this deck. Next: one pilot customer's "
              "Tier 1 exports through a new adapter; the engine, UI and exports stay as they are. We "
              "need answers to Q35, approved emission factors, and contract prices plus CRM legal "
              "names so Company insights can run on real accounts. Prototype, synthetic data, not audited.")


# ---------------------------------------------------------------- pictures, graphs and tables

def _picture(slide, path: Path, x, y, w=None, h=None):
    """Add a PNG, keeping its aspect ratio inside the given width or height."""
    return slide.shapes.add_picture(str(path), x, y, width=w, height=h)


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _style(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=11)
    ax.grid(axis=grid_axis, color="#E5E7EB", linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, facecolor="white", dpi=200)
    _plt().close(fig)
    return path


def _short(name: str) -> str:
    return name.split(" ", 1)[1] if " " in name else name


def _make_charts(r, tmp: Path) -> dict:
    """matplotlib PNGs for the picture slides. Every value is read from the review (the engine)."""
    plt = _plt()
    tmp.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    by_id = {k.metric_id: k for k in r.kpis}
    fp = [(label, by_id[mid]) for mid, label in chart_lib.FOOTPRINT_IDS if mid in by_id and by_id[mid].value is not None]
    fig, ax = plt.subplots(figsize=(4.6, 3.7))
    fp = fp[::-1]
    vals = [k.value for _, k in fp]
    lo = [k.range.low if k.range and k.range.low is not None else k.value for _, k in fp]
    hi = [k.range.high if k.range and k.range.high is not None else k.value for _, k in fp]
    ax.barh([lab for lab, _ in fp], vals, color=chart_lib.NAVY, height=0.55,
            xerr=[[max(v - a, 0) for v, a in zip(vals, lo)], [max(b - v, 0) for v, b in zip(vals, hi)]],
            error_kw={"ecolor": chart_lib.RED, "capsize": 5, "elinewidth": 1.8})
    ax.axvline(100, color=chart_lib.RED, linestyle="--", linewidth=1.6)
    ax.set_xlim(0, max(max(hi), 100) * 1.1)
    for i, v in enumerate(vals):
        ax.text(2, i, f"{v:.0f}%", va="center", ha="left", fontsize=13, fontweight="bold", color="white")
    ax.set_title("What remains vs the baseline", fontsize=13, color=chart_lib.NAVY, loc="left")
    ax.set_xlabel("% of baseline footprint (dashed line = 100%)", fontsize=11, color=chart_lib.GREY)
    ax.tick_params(axis="y", labelsize=13)
    ax.tick_params(axis="x", labelsize=11)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    out["footprint"] = _save(fig, tmp / "footprint.png")
    months = [m["month"][5:7] for m in (r.trends.get("active_wearers") or [])]
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    labels = [names[int(m) - 1] for m in months]

    def series(key):
        return [p["value"] for p in r.trends.get(key) or []]

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(labels, series("garments_allocated"), color=chart_lib.NAVY, linewidth=2.4, label="Allocated to wearers")
    ax.plot(labels, series("active_assets_scanned"), color=chart_lib.RED, linewidth=2.4, label="Scanned in use (garments)")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.legend(frameon=False, fontsize=11, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.32))
    _style(ax)
    out["trend_pieces"] = _save(fig, tmp / "trend_pieces.png")

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    xs = list(range(len(labels)))
    ax.bar(xs, series("repairs"), width=0.6, color=chart_lib.NAVY, label="Repairs (left axis)")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylim(bottom=0)
    ax2 = ax.twinx()
    ax2.plot(xs, series("service_requests"), color="#7B8DB5", linewidth=2.4, marker="o", markersize=4,
             label="Service requests (right axis)")
    ax2.plot(xs, series("late_cycles"), color=chart_lib.RED, linewidth=2.4, marker="o", markersize=4,
             label="Late cycles (right axis)")
    ax2.set_ylim(bottom=0)
    ax2.tick_params(labelsize=11)
    ax2.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=10, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.42))
    _style(ax)
    out["trend_service"] = _save(fig, tmp / "trend_service.png")
    alloc, scanned = sum(series("garments_allocated")), sum(series("active_assets_scanned"))
    out["scan_share"] = scanned / alloc if alloc else None

    sites = [x for x in r.sites if x.metrics.get("co2_saving_kg") and x.metrics["co2_saving_kg"].value is not None]
    top = sorted(sites, key=lambda x: x.metrics["co2_saving_kg"].value, reverse=True)[:10][::-1]
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    vals = [x.metrics["co2_saving_kg"].value / 1000 for x in top]
    ax.barh([_short(x.name) for x in top], vals, color=chart_lib.NAVY, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.015, i, f"{v:.1f}", va="center", fontsize=11, color=chart_lib.NAVY, fontweight="bold")
    ax.set_xlim(0, max(vals) * 1.15)
    ax.set_xlabel("CO₂e avoided per site, tonnes (estimate, vs baseline)", fontsize=11, color=chart_lib.GREY)
    _style(ax, "x")
    out["sites_co2"] = _save(fig, tmp / "sites_co2.png")
    return out


def _s3a_screens(prs, d, n):
    s = _slide(prs, "The dashboard at a glance", n,
               "A real screen from the prototype: the Overview page for the synthetic NorthStar Foods Group.")
    pic = _picture(s, IMG_DIR / "dashboard_overview.png", MARGIN, Inches(1.65), w=CONTENT_W)
    pic.line.color.rgb = GREY
    pic.line.width = Pt(0.75)
    _, tf = _textbox(s, MARGIN, Inches(6.25), CONTENT_W, Inches(0.6))
    _run(tf.paragraphs[0], "Each figure has a status and, for estimates, a low to high range. Sites, observations and the "
         "priority view sit below.", BODY, False, INK)
    _notes(s, "A real screen of the Overview page. The headline figures each carry a status label (for example "
              "estimate) and a low to high range. Below the fold: observations that are rules-generated and "
              "ranked by the chosen priority, and the sites ranked on a metric. A click on a site opens its "
              "own detail with monthly trends. The data is synthetic.")


def _s3b_numbers(prs, d, n):
    r = d["plain"]
    s = _slide(prs, "The customer's numbers, with ranges", n,
               f"{r.meta.node.name}, {r.meta.period}, against {r.meta.baseline.get('name', '').lower()}.")
    ids = ["water_saving_l", "co2_saving_kg", "energy_saving_kwh", "active_wearers", "repairs",
           "on_time_rate", "recycling_rate"]
    have = {k.metric_id: k for k in r.kpis}
    rows = []
    for mid in ids:
        k = have.get(mid)
        if k is None or k.value is None:
            continue
        rng = fmt_range(k) if getattr(k, "range", None) else "n/a"
        rows.append([clip(k.label.replace(" vs baseline", "").replace("CO2e", "CO₂e"), 34), fmt_value(k).replace("CO2e", "CO₂e"),
                     rng.replace("CO2e", "CO₂e"),
                     k.method_status.value.title()])
    _table(s, MARGIN, Inches(1.7), [3.3, 1.5, 2.1, 1.25], rows,
           ["Measure", "Value", "Low to high", "Status"], size=BODY, row_h=0.52, header_size=BODY)
    _picture(s, d["charts"]["footprint"], MARGIN + Inches(8.3), Inches(1.7), w=Inches(3.85))
    _, tf = _textbox(s, MARGIN + Inches(8.3), Inches(4.75), Inches(3.85), Inches(1.9))
    _lines(tf, ["Lower is better: 71% means 29% less than the baseline.",
                "Whiskers show the low to high range. Estimates, not audited."], first=True, space=4)
    _, tf = _textbox(s, MARGIN, Inches(6.05), Inches(8.1), Inches(0.8))
    _run(tf.paragraphs[0], "Status tells the reader how each figure was made: measured, calculated, allocated or estimated.",
         BODY, False, GREY, italic=True)
    _notes(s, "The table is the headline set from the engine, formatted by the shared formatter used "
              "everywhere. Each estimate has a low and high case instead of one false-precision number. The "
              "chart shows the allocated footprint as a share of the selected baseline; 100 percent is the "
              "baseline and the whiskers are the low to high range. These are prototype estimates on synthetic data.")


def _s3c_sites(prs, d, n):
    r = d["plain"]
    s = _slide(prs, "Savings by site, and where to look", n,
               "Customer level first, then the sites: the biggest savings and the ones that stand out.")
    _, tf = _textbox(s, MARGIN, Inches(1.6), Inches(6.4), Inches(0.45))
    _heading(tf, "Top 10 of 24 sites: CO₂e avoided", first=True, size=16)
    _picture(s, d["charts"]["sites_co2"], MARGIN, Inches(2.1), w=Inches(6.4))
    ranked = [x for x in r.sites if x.metrics.get("washed_kg_per_wearer") and x.metrics["washed_kg_per_wearer"].value is not None]
    ranked.sort(key=lambda x: x.metrics["washed_kg_per_wearer"].value, reverse=True)
    pick = ranked[:3] + ranked[-3:]

    def cell(site, key):
        m = site.metrics.get(key)
        return fmt_value(m).replace(" kg/wearer", "") if m is not None and m.value is not None else "n/a"

    rows = [[_short(x.name), cell(x, "washed_kg_per_wearer"), cell(x, "utilisation"), cell(x, "on_time_rate")] for x in pick]
    _, tf = _textbox(s, MARGIN + Inches(6.75), Inches(1.6), Inches(5.4), Inches(0.45))
    _heading(tf, "Highest and lowest washing per wearer", first=True, size=16)
    _table(s, MARGIN + Inches(6.75), Inches(2.1), [1.5, 1.3, 1.45, 1.15], rows,
           ["Site", "kg / wearer", "Utilisation", "On time"], size=BODY, row_h=0.5, header_size=BODY)
    _, tf = _textbox(s, MARGIN + Inches(6.75), Inches(5.7), Inches(5.4), Inches(1.1))
    _lines(tf, ["Three highest and three lowest of 24 sites, per year.",
                "Site figures are indicative estimates. A site far from its peers gets an observation, not a verdict."],
           first=True, space=3)
    _notes(s, "Left: the ten sites with the largest estimated CO2e avoided against the baseline. Right: the three "
              "highest and three lowest sites on washed kilograms per wearer, with utilisation and on-time "
              "delivery. Outliers become observations with a suggested next step in the dashboard. All values "
              "are synthetic and estimated.")


def _s3d_trends(prs, d, n):
    r = d["plain"]
    s = _slide(prs, "Month by month", n,
               f"Account totals for each month of {r.meta.period}, all sites together.")
    w, gap = Inches(5.95), Inches(0.23)
    for i, (key, head) in enumerate((("trend_pieces", "Garments in the service"),
                                     ("trend_service", "Repairs, service requests, late cycles"))):
        x = MARGIN + (w + gap) * i
        _, tf = _textbox(s, x, Inches(1.55), w, Inches(0.4))
        _heading(tf, head, first=True, size=16)
        _picture(s, d["charts"][key], x, Inches(2.0), w=w)
    _, tf = _textbox(s, MARGIN, Inches(5.95), CONTENT_W, Inches(0.9))
    share = d["charts"].get("scan_share")
    _lines(tf, [f"About {share * 100:.0f}% of allocated pieces were scanned in use across the year." if share else "",
                "Left: pieces allocated against pieces scanned. Right: repairs on the left axis, service requests and late cycles on the right.",
                "Click a site in the dashboard to see the same two charts for that site."], first=True, space=3)
    _notes(s, "The two charts show the 12 monthly totals for the whole account: pieces allocated against "
              "pieces scanned in use, and repairs, service requests and late cycles. The same charts exist "
              "for every site. Monthly values come straight from the data pack; they are synthetic.")


SLIDES = [_s1_asked, _s2_fit, _s3_story, _s3a_screens, _s3b_numbers, _s3c_sites, _s3d_trends, _s4_more, _s5_intel, _s6_credible, _s7_grows, _s8_exports]


def build_pitch(out_path: Path = DEFAULT_OUT) -> Path:
    with tempfile.TemporaryDirectory(prefix="vr_pitch_", ignore_cleanup_errors=True) as tmp:
        data = _reviews(Path(tmp))
        data["charts"] = _make_charts(data["plain"], Path(tmp) / "charts")
        prs = Presentation()
        prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
        for i, fn in enumerate(SLIDES, start=1):
            fn(prs, data, i)
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(out_path)  # the chart PNGs are read into the file here, before the temp dir goes
    return out_path


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    os.environ.setdefault("VR_AI", "off")
    print(build_pitch(args.out))


if __name__ == "__main__":
    main()
