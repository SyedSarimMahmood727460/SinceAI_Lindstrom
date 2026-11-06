import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches

from api.build import build_review
from api.review_model import ReviewModel, ReviewParams
from export.pptx_builder import build_pptx, fmt_value

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


@pytest.fixture(scope="module")
def deck(review, tmp_path_factory):
    return build_pptx(review, tmp_path_factory.mktemp("deck") / "r.pptx")


def test_pptx_has_nine_slides(deck):
    assert len(Presentation(str(deck)).slides) == 9


def test_pptx_numbers_match_review(review, deck):
    kpi = next(k for k in review.kpis if k.metric_id == "co2_saving_kg")
    texts = _slides_text(deck)
    assert fmt_value(kpi) in texts[2]
    assert "[ESTIMATED]" in texts[2]


def test_pptx_footer_on_every_slide(review, deck):
    for t in _slides_text(deck):
        assert "Prototype · synthetic data · not audited" in t
        assert f"run {review.meta.run_id}" in t


def test_pptx_unicode_site_names(deck):
    text = "\n".join(_slides_text(deck))
    assert "Västerås" in text or "Łódź" in text


def test_pptx_customer_audience(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    text = "\n".join(_slides_text(build_pptx(rv, tmp_path / "c.pptx"))).lower()
    assert "idle stock" not in text


def test_pptx_empty_filter(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST002", product="P1004"))
    path = build_pptx(rv, tmp_path / "e.pptx")
    texts = _slides_text(path)
    assert len(texts) == 9 and "No data for this filter" in texts[2]
