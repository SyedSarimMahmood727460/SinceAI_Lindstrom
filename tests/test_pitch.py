"""Pitch deck (Task 11): 8 slides in order, the disclaimer on each, figures from build_review."""
import os

from pptx import Presentation
from pptx.util import Pt

from api.build import build_review
from api.review_model import ReviewParams
from export.format import fmt_range, fmt_value
from model.inputs_store import inputs_dir

TITLES = [
    "What you asked",
    "Built on Lindström's work",
    "Easy to explain: the customer story",
    "Save more by working with us more",
    "Knows where your customers are going",
    "Credible by design",
    "Grows with your business",
    "Exports & path to production",
]
DISCLAIMER = "Prototype · synthetic data · not audited"


def _texts(slide) -> list[str]:
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            out.append(sh.text_frame.text)
        if sh.has_table:
            out += [c.text_frame.text for row in sh.table.rows for c in row.cells]
    return out


def _sizes(slide):
    for sh in slide.shapes:
        frames = [sh.text_frame] if sh.has_text_frame else []
        if sh.has_table:
            frames += [c.text_frame for row in sh.table.rows for c in row.cells]
        for tf in frames:
            for p in tf.paragraphs:
                for r in p.runs:
                    if r.text.strip():
                        yield r.font.size


def test_pitch_deck(tmp_path, con, pack_path):
    from scripts.make_pitch_deck import build_pitch

    env = os.environ.get("VR_INPUTS_DIR"), os.environ.get("VR_EXTENSIONS")
    stored = sorted(inputs_dir().glob("*")) if inputs_dir().exists() else []
    out = build_pitch(tmp_path / "pitch.pptx")
    # the demo inputs went to a private temp dir; the environment is restored
    assert (os.environ.get("VR_INPUTS_DIR"), os.environ.get("VR_EXTENSIONS")) == env
    assert (sorted(inputs_dir().glob("*")) if inputs_dir().exists() else []) == stored
    prs = Presentation(out)
    slides = list(prs.slides)
    assert len(slides) == 8
    assert abs(prs.slide_width / prs.slide_height - 16 / 9) < 1e-3  # 16:9
    for slide, title in zip(slides, TITLES):
        texts = _texts(slide)
        assert texts[0] == title or title in texts, (title, texts[:3])
        assert any(DISCLAIMER in t for t in texts), title
        assert all(s is not None and s >= Pt(14) for s in _sizes(slide)), title
        assert slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip(), title
    # headline figures are the engine's, formatted by the shared formatter (default inputs)
    r = build_review(con, ReviewParams(account_id="CUST001"))
    k = {x.metric_id: x for x in r.kpis}
    story = " ".join(_texts(slides[2]))
    for mid in ("water_saving_l", "co2_saving_kg"):
        assert fmt_value(k[mid]) in story and fmt_range(k[mid]) in story
    assert fmt_value(r.dto.diy_total) in " ".join(_texts(slides[3]))
    # slide 5 cites the committed Fazer snapshot; slide 6 names the L003 warning
    intel = " ".join(_texts(slides[4]))
    assert "Fazer Group" in intel and "cision.com" in intel
    assert "L003" in " ".join(_texts(slides[5]))
    assert "Baltic Harbour Hotels" in " ".join(_texts(slides[6]))

