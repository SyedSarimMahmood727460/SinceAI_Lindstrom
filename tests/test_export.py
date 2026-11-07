import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches

from api.build import build_review
from api.review_model import ReviewModel, ReviewParams
from config.loader import load_assumptions
from export.pptx_builder import build_pptx, fmt_value
from model.inputs_store import save_inputs

FIXTURE = Path(__file__).parent / "fixtures" / "review_northstar.json"


@pytest.fixture(scope="module")
def review() -> ReviewModel:
    return ReviewModel(**json.loads(FIXTURE.read_text(encoding="utf-8")))


def _slides_text(path):
    out = []
    for slide in Presentation(str(path)).slides:
        parts = []
        for sh in slide.shapes:
            if sh.has_text_frame:
                parts.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    parts.extend(c.text_frame.text for c in row.cells)
        out.append("\n".join(parts))
    return out


def slide_titles(path):
    """The title of each slide: its first non-empty text frame (header bars carry no text)."""
    out = []
    for slide in Presentation(str(path)).slides:
        texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        out.append(texts[0] if texts else "")
    return out


def slide_index(path, title):
    return next(i for i, t in enumerate(slide_titles(path)) if t.startswith(title))


@pytest.fixture(scope="module")
def deck(review, tmp_path_factory):
    return build_pptx(review, tmp_path_factory.mktemp("deck") / "r.pptx")


@pytest.fixture
def full_deck(con, tmp_path, monkeypatch):
    """A deck with every step: contract price (net + bars) and growth (step 4)."""
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path / "inputs"))
    save_inputs("CUST001", {"contract_price_eur_per_year": 1200000, "extra_sites": 4,
                            "extra_service_lines": ["mats"]}, load_assumptions()["dto_inputs"])
    rv = build_review(con, ReviewParams(account_id="CUST001"))
    return build_pptx(rv, tmp_path / "full.pptx")


STEPS = ["1 · What you got", "2 · Vs doing it yourself", "3 · Where to improve"]
APPENDIX = ["Appendix · Value KPIs", "Appendix · Footprint vs baseline", "Appendix · Site highlights",
            "Appendix · Methodology & assumptions", "Appendix · Data readiness"]


def test_pptx_meeting_order(deck, full_deck):
    titles = slide_titles(deck)  # no growth inputs: step 4 is absent
    assert titles[0].startswith("LINDSTRÖM") and "REVIEW" in titles[0]  # the cover
    assert titles[1:4] == STEPS
    assert titles[4] == "5 · Agree next steps" and not any(t.startswith("4 · ") for t in titles)
    assert titles[5:] == APPENDIX
    full = slide_titles(full_deck)
    assert full[1:4] == STEPS and full[4] == "4 · Grow together" and full[5] == "5 · Agree next steps"
    assert full[6:] == APPENDIX


def test_pptx_numbers_match_review(review, deck):
    kpi = next(k for k in review.kpis if k.metric_id == "co2_saving_kg")
    text = _slides_text(deck)[slide_index(deck, "Appendix · Value KPIs")]
    assert fmt_value(kpi) in text
    assert "[ESTIMATED]" in text


def test_pptx_steps_use_compact(review, deck):
    from export.format import fmt_compact_value
    texts = _slides_text(deck)
    k = {x.metric_id: x for x in review.kpis}
    step1 = texts[slide_index(deck, "1 · What you got")]
    assert fmt_compact_value(k["water_saving_l"]) in step1 and "255 t CO₂e" in step1
    step2 = texts[slide_index(deck, "2 · Vs doing it yourself")]
    assert "€1.96M" in step2 and "explanatory, not in total" in step2
    step3 = texts[slide_index(deck, "3 · Where to improve")]
    assert "NorthStar Kraków" in step3 and "Typical site" in step3


def test_pptx_footer_on_every_slide(review, deck):
    for t in _slides_text(deck):
        assert "Prototype · synthetic data · not audited" in t
        assert f"run {review.meta.run_id}" in t


def test_pptx_unicode_site_names(deck):
    texts = _slides_text(deck)
    highlights = next(t for t in texts if "Site highlights" in t)
    assert "Kraków" in highlights  # highest washed kg per wearer for NorthStar
    assert "Gdańsk" in "\n".join(texts)  # step 3: the next observations


def test_kpi_slide_uses_headline_kpis(review, deck):
    kpi_text = _slides_text(deck)[slide_index(deck, "Appendix · Value KPIs")]
    shown = [k for k in review.kpis if k.customer_facing and k.display["headline"]][:8]
    assert len(shown) == 8
    positions = [kpi_text.index(k.label) for k in shown]
    assert positions == sorted(positions)  # same order as the review
    for k in shown:
        assert fmt_value(k) in kpi_text


@pytest.mark.parametrize("which", ["deck", "full_deck"])
def test_no_shape_runs_into_footer(which, request):
    """Every slide, the step slides included (with net, bars and growth), stays above the footer."""
    prs = Presentation(str(request.getfixturevalue(which)))
    footer_top = Inches(6.98)
    for i, slide in enumerate(prs.slides, 1):
        if i == 1:  # cover has a full-bleed background
            continue
        for sh in slide.shapes:
            if sh.top < footer_top:  # footer rule/text/number start at or below this line
                assert sh.top + sh.height <= footer_top, (i, sh.name)
            assert sh.left >= 0 and sh.left + sh.width <= prs.slide_width, (i, sh.name)


def test_pptx_customer_audience(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    text = "\n".join(_slides_text(build_pptx(rv, tmp_path / "c.pptx"))).lower()
    assert "idle stock" not in text


def test_pptx_empty_filter(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST002", product="P1004"))
    path = build_pptx(rv, tmp_path / "e.pptx")
    texts = _slides_text(path)
    assert slide_titles(path)[1:4] == STEPS
    assert "No data for this filter" in texts[slide_index(path, "Appendix · Value KPIs")]
    assert "no data for this filter" in texts[slide_index(path, "1 · What you got")]
    for t in texts:
        assert "Prototype · synthetic data · not audited" in t and f"run {rv.meta.run_id}" in t


def test_pptx_appendix_names_laundry_and_period(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST002", period="2025-Q2"))
    ws = rv.data_quality["warnings"]
    assert ws and {w["month"] for w in ws} <= {"2025-04", "2025-05", "2025-06"}
    assert ws[0]["entity_name"] == "Nordic Malmö WWS" and "×" in ws[0]["message"]
    text = "\n".join(_slides_text(build_pptx(rv, tmp_path / "a.pptx")))
    assert "Nordic Malmö WWS (L003)" in text and "Customer volume routed" in text
    assert "2025-Q2" in text.split("2026 target")[0].split("Proposed actions")[-1]


def test_fmt_number_count_has_no_unit_and_no_lowercase_start():
    from export.pptx_builder import _no_internal, fmt_number
    assert fmt_number(24, "count") == "24"
    out = _no_internal("Idle stock is high; the note stays. other text")
    assert all(p.strip()[0].isupper() for p in out.split(". ") if p.strip())


def _strip_volatile(x):
    """Drop per-load / per-run identifiers (load ids, run id, timestamps)."""
    if isinstance(x, dict):
        return {k: _strip_volatile(v) for k, v in x.items()
                if k not in ("load_ids", "load_id", "run_id", "generated_at")}
    if isinstance(x, list):
        return [_strip_volatile(v) for v in x]
    return x


def test_fixture_is_current(review, con):
    """The committed fixture matches today's build_review (regenerate it when the model changes:
    build_review(con, ReviewParams(account_id="CUST001")), UTF-8, indent 2)."""
    live = build_review(con, ReviewParams(account_id="CUST001")).model_dump(mode="json")
    live = _strip_volatile(live)
    fixed = _strip_volatile(review.model_dump(mode="json"))
    assert fixed.keys() == live.keys()
    for key in live:
        assert fixed[key] == live[key], key


def _notes_text(path):
    return [s.notes_slide.notes_text_frame.text if s.has_notes_slide else ""
            for s in Presentation(str(path)).slides]


def test_pptx_coaching_only_in_notes(review, deck, full_deck):
    """What to say is the account manager's coaching: speaker notes only, never on a slide."""
    for path in (deck, full_deck):
        text = "\n".join(_slides_text(path))
        notes = "\n".join(_notes_text(path))
        assert "What to say" not in text
        from export.sections import meeting_steps
        says = [st["what_to_say"] for st in meeting_steps(review) if st["what_to_say"]]
        assert len(says) >= 4
        for say in says:
            assert say[:60] not in text
            assert say in notes
    for c in review.story:
        assert c["what_to_say"][:60] not in "\n".join(_slides_text(deck))


def test_pptx_step2_without_contract_has_no_prompt(deck):
    text = _slides_text(deck)[slide_index(deck, "2 · Vs doing it yourself")]
    assert "Enter the contract price" not in text and "contract price" not in text.lower()
    assert "Doing it yourself, per year" in text and "€1.96M" in text


def _r4_review(review):
    from insights.story import build_story
    r4 = next(o for o in review.observations if o.rule_id == "R4")
    stub = review.model_copy(update={"observations": [r4]})
    stub.story = build_story(stub)
    return stub, r4


def test_step3_without_facts_has_no_tiles(review, tmp_path):
    from export.pdf_builder import build_pdf
    from pypdf import PdfReader
    stub, r4 = _r4_review(review)
    path = build_pptx(stub, tmp_path / "r4.pptx")
    text = _slides_text(path)[slide_index(path, "3 · Where to improve")]
    assert r4.finding[:50] in text and "Typical site" not in text
    shapes = Presentation(str(path)).slides[slide_index(path, "3 · Where to improve")].shapes
    assert not any(sh.top == Inches(2.0) for sh in shapes)  # nothing in the tile band
    pdf = " ".join(" ".join(p.extract_text().split()) for p in PdfReader(str(build_pdf(stub, tmp_path / "r4.pdf"))).pages)
    step3 = pdf.split("3 · Where to improve")[1].split("5 · Agree next steps")[0]
    assert " ".join(r4.finding.split())[:50] in step3 and "Typical site" not in step3


def _net_review(review, low, base, high):
    from model.contracts import Range
    d = review.dto
    net = d.diy_total.model_copy(update={"value": base, "range": Range(low=low, base=base, high=high)})
    return review.model_copy(update={"dto": d.model_copy(update={"net": net, "contract_price": d.diy_total})})


def test_step2_net_wording(review):
    from export.sections import meeting_steps
    st = meeting_steps(_net_review(review, -297100, 297100, 1079363))[1]
    assert st["message"].startswith("About €297k less with Lindström than doing it yourself — but the range "
                                     "runs from €297k more to €1.08M less, so it depends on the assumptions")
    tile = st["tiles"][0]
    assert tile["label"] == "Saving with Lindström" and tile["value"] == "€297k"
    assert tile["range"] == "range −€297k – €1.08M" and "depends on the assumptions" in tile["context"]
    st = meeting_steps(_net_review(review, -900000, -500000, -100000))[1]
    assert st["message"].startswith("About €500k (between €100k and €900k) more with Lindström")
    tile = st["tiles"][0]
    assert tile["label"] == "Extra cost with Lindström" and tile["value"] == "€500k"
    assert tile["range"] == "range €100k – €900k" and tile["context"] == "per year"
