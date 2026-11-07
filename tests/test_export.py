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
