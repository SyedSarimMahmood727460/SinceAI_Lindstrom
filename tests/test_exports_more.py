"""PDF and Excel exports, plus the story / DIY / growth slides of the deck (Task 10)."""
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

from api.build import build_review
from api.main import app
from api.review_model import DISCLAIMER, ReviewModel, ReviewParams
from config.loader import load_assumptions
from export.format import fmt_value
from export.pdf_builder import build_pdf
from export.pptx_builder import build_pptx
from export.xlsx_builder import build_xlsx
from model.inputs_store import save_inputs

FIXTURE = Path(__file__).parent / "fixtures" / "review_northstar.json"
SPEC = load_assumptions()["dto_inputs"]


@pytest.fixture(scope="module")
def review() -> ReviewModel:
    return ReviewModel(**json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def pdf(review, tmp_path_factory):
    return build_pdf(review, tmp_path_factory.mktemp("pdf") / "r.pdf")


def _pdf_text(path) -> str:
    return " ".join(" ".join(p.extract_text().split()) for p in PdfReader(str(path)).pages)


def _ppt_texts(path):
    out = []
    for slide in Presentation(str(path)).slides:
        parts = []
        for sh in slide.shapes:
            if sh.has_text_frame:
                parts.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                parts += [c.text_frame.text for r in sh.table.rows for c in r.cells]
        out.append("\n".join(parts))
    return out


@pytest.fixture
def growth_review(con, tmp_path, monkeypatch):
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path / "inputs"))
    save_inputs("CUST001", {"extra_sites": 4, "extra_service_lines": ["mats"],
                            "contract_price_eur_per_year": 900000}, SPEC)
    return build_review(con, ReviewParams(account_id="CUST001"))


def test_pdf_has_sections(pdf, review):
    text = _pdf_text(pdf)
    for s in ("Customer story", "Service vs do-it-yourself", "Methodology", DISCLAIMER,
              f"run {review.meta.run_id}"):
        assert s in text
    assert len(PdfReader(str(pdf)).pages) >= 10


def test_pdf_footer_on_every_page(pdf):
    for page in PdfReader(str(pdf)).pages:
        assert DISCLAIMER in page.extract_text()


def test_pdf_unicode(pdf):
    text = _pdf_text(pdf)
    assert "Kraków" in text and "Västerås" in text


def test_pdf_numbers_match_review(pdf, review):
    k = next(k for k in review.kpis if k.metric_id == "co2_saving_kg")
    assert fmt_value(k) in _pdf_text(pdf)


def test_pdf_growth_and_diy_notes(growth_review, tmp_path):
    text = _pdf_text(build_pdf(growth_review, tmp_path / "g.pdf"))
    assert "Growth opportunities" in text and "Add Mats" in text
    assert "explanatory, not in total" in text
    assert fmt_value(growth_review.dto.net) in text
    assert "Enter the contract price" not in text


def test_diy_prompt_when_no_contract(con, tmp_path, monkeypatch):
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path / "i"))
    rv = build_review(con, ReviewParams(account_id="CUST001"))
    assert rv.dto.net is None and rv.growth is None
    text = _pdf_text(build_pdf(rv, tmp_path / "d.pdf"))
    assert "Enter the contract price to see the net comparison" in text
    assert "Growth opportunities" not in text


def test_xlsx_sheets(growth_review, review, tmp_path):
    names = load_workbook(build_xlsx(growth_review, tmp_path / "g.xlsx")).sheetnames
    assert names == ["Summary", "Story", "KPIs", "Sites", "Observations", "Actions", "DIY comparison",
                     "Growth", "Inputs", "Assumptions", "Data quality"]
    plain = load_workbook(build_xlsx(review, tmp_path / "p.xlsx")).sheetnames
    assert "Growth" not in plain and "Summary" in plain


def test_xlsx_summary_has_disclaimer(review, tmp_path):
    ws = load_workbook(build_xlsx(review, tmp_path / "s.xlsx"))["Summary"]
    assert DISCLAIMER in [c.value for row in ws.iter_rows() for c in row]


@pytest.mark.parametrize("sens", ["low", "base", "high"])
def test_xlsx_kpi_matches_api(con, tmp_path, sens):
    rv = build_review(con, ReviewParams(account_id="CUST001", sensitivity=sens))
    ws = load_workbook(build_xlsx(rv, tmp_path / "k.xlsx"))["KPIs"]
    rows = {r[0].value: r for r in ws.iter_rows(min_row=2)}
    k = next(k for k in rv.kpis if k.metric_id == "co2_saving_kg")
    assert rows["co2_saving_kg"][3].value == pytest.approx(k.value)
    assert isinstance(rows["co2_saving_kg"][3].value, float)
    assert rows["co2_saving_kg"][7].value.startswith(fmt_value(k))


def test_xlsx_unicode(review, tmp_path):
    wb = load_workbook(build_xlsx(review, tmp_path / "u.xlsx"))
    cells = [str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value]
    assert any("Łódź" in c for c in cells)


def test_xlsx_customer_audience(con, tmp_path):
    rv = build_review(con, ReviewParams(account_id="CUST001", audience="customer"))
    wb = load_workbook(build_xlsx(rv, tmp_path / "c.xlsx"))
    text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value).lower()
    assert "idle_stock_value_eur" not in text and "idle stock" not in text
    pdf_text = _pdf_text(build_pdf(rv, tmp_path / "c.pdf")).lower()
    assert "idle stock" not in pdf_text and "idle_stock_value_eur" not in pdf_text


def test_xlsx_diy_and_inputs(growth_review, tmp_path):
    wb = load_workbook(build_xlsx(growth_review, tmp_path / "d.xlsx"))
    diy = {r[0].value: r for r in wb["DIY comparison"].iter_rows(min_row=2)}
    assert diy["Do-it-yourself total"][2].value == pytest.approx(growth_review.dto.diy_total.value)
    assert diy["Extra replacements without repairs"][1].value == "no"
    sources = {r[1].value: r[6].value for r in wb["Inputs"].iter_rows(min_row=2)}
    assert sources["contract_price_eur_per_year"] == "Entered by account manager"
    assert sources["local_laundry_eur_per_kg"] == "Default"
    assert wb["Growth"].max_row > 5


def test_export_formats_api(pack_path):
    with TestClient(app) as c:
        mimes = {"pptx": "presentationml", "pdf": "application/pdf", "xlsx": "spreadsheetml"}
        bodies = {}
        for fmt, mime in mimes.items():
            r = c.post("/reviews/export", json={"account_id": "CUST001", "format": fmt})
            assert r.status_code == 200 and mime in r.headers["content-type"], fmt
            name = "review_CUST001_2025_internal.xlsx" if fmt == "xlsx" else f"review_CUST001_2025.{fmt}"
            assert f'filename="{name}"' in r.headers["content-disposition"]
            bodies[fmt] = r.content
        assert bodies["pdf"][:4] == b"%PDF"
        assert load_workbook(io.BytesIO(bodies["xlsx"])).sheetnames[0] == "Summary"
        bad = c.post("/reviews/export", json={"account_id": "CUST001", "format": "docx"})
        assert bad.status_code == 400 and bad.json()["detail"] == "unsupported format: docx"


def test_pptx_story_first(review, tmp_path):
    texts = _ppt_texts(build_pptx(review, tmp_path / "s.pptx"))
    assert "Customer story" in texts[1] and "Customer story" not in texts[2]
    assert "Growth opportunities" not in "\n".join(texts)


def test_pptx_growth_slide_when_inputs(growth_review, tmp_path):
    texts = _ppt_texts(build_pptx(growth_review, tmp_path / "g.pptx"))
    assert len(texts) == 12
    at = {name: next(i for i, t in enumerate(texts) if name in t.split("\n")[:4])
          for name in ("Growth opportunities", "Service vs do-it-yourself")}
    assert at["Growth opportunities"] == at["Service vs do-it-yourself"] + 1
    g = texts[at["Growth opportunities"]]
    assert fmt_value(growth_review.growth["totals"]["diy_cost_avoided"]) in g
    assert "Add Mats" in g and "4 more sites" in g
    diy = texts[at["Service vs do-it-yourself"]]
    assert fmt_value(growth_review.dto.net) in diy and "explanatory, not in total" in diy


def _save(tmp_path, monkeypatch, values):
    monkeypatch.setenv("VR_INPUTS_DIR", str(tmp_path / "inputs"))
    save_inputs("CUST001", values, SPEC)


def test_growth_without_levers_skips_section(con, tmp_path, monkeypatch):
    _save(tmp_path, monkeypatch, {"extra_service_lines": ["workwear"]})
    rv = build_review(con, ReviewParams(account_id="CUST001"))
    assert rv.growth is not None and rv.growth["levers"] == []
    assert len(_ppt_texts(build_pptx(rv, tmp_path / "n.pptx"))) == 11
    assert "Growth opportunities" not in _pdf_text(build_pdf(rv, tmp_path / "n.pdf"))
    assert "Growth" not in load_workbook(build_xlsx(rv, tmp_path / "n.xlsx")).sheetnames
    with TestClient(app) as c:
        for fmt in ("pptx", "pdf", "xlsx"):
            r = c.post("/reviews/export", json={"account_id": "CUST001", "format": fmt})
            assert r.status_code == 200, fmt


def test_growth_slide_stays_above_footer(con, tmp_path, monkeypatch):
    from pptx.util import Inches
    _save(tmp_path, monkeypatch, {"extra_sites": 4, "extra_wearers": 100,
                                  "extra_service_lines": ["workwear", "mats", "washroom"]})
    rv = build_review(con, ReviewParams(account_id="CUST001"))
    assert rv.growth["notes"] and rv.growth["skipped_lines"]
    prs = Presentation(str(build_pptx(rv, tmp_path / "g.pptx")))
    assert len(prs.slides) == 12
    slide = prs.slides[6]
    assert "Growth opportunities" in [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    footer_top = Inches(6.98)
    for sh in slide.shapes:
        if sh.top < footer_top:
            assert sh.top + sh.height <= footer_top, sh.name
    bullets = [sh for sh in slide.shapes if sh.has_text_frame and "All figures are estimates" in sh.text_frame.text]
    assert len(bullets[0].text_frame.paragraphs) <= 3


def test_xlsx_audience_row(con, tmp_path):
    for aud, expect in (("kam", "Account manager"), ("customer", "Customer")):
        rv = build_review(con, ReviewParams(account_id="CUST001", audience=aud))
        ws = load_workbook(build_xlsx(rv, tmp_path / f"{aud}.xlsx", audience=aud))["Summary"]
        rows = {r[0].value: r[1].value for r in ws.iter_rows(min_row=2)}
        assert rows["Audience"].startswith(expect)
