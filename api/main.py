"""FastAPI service (spec 11.1). The pack is loaded once at startup; one Engine is reused."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from api.build import _narrate, build_review, dq_warning_rows
from api.review_model import ReviewParams
from config.loader import CONFIG_DIR, load_assumptions, load_yaml
from metrics.engine import Engine
from model.contracts import ViewSpec
from model.inputs_store import effective_inputs, load_inputs, save_inputs, stored_growth
from model.load import load_sources

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DEFAULT_PACK = ("data/lindstrom_pack/"
                "Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx")
KNOWN_PRIORITIES = ("water", "emissions", "cost", "circularity", "service")
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class UTF8JSONResponse(JSONResponse):
    """Keep non-ASCII (Łódź, Västerås) unescaped; never emit NaN."""

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")


class State:
    con = None
    engine: Engine | None = None
    lock = threading.RLock()  # one DuckDB connection is shared across worker threads


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.con = load_sources(inject_bad=os.environ.get("VR_INJECT_BAD_ROWS") == "1")
    state.engine = Engine(state.con, load_assumptions(), load_yaml("metrics.yaml"))
    yield
    state.con.close()


app = FastAPI(title="Threadline", lifespan=lifespan, default_response_class=UTF8JSONResponse)


def _account_exists(account_id: str) -> bool:
    return state.con.execute("select 1 from org_node where node_id = ? and level = 'ACCOUNT'",
                             [account_id]).fetchone() is not None


def _build(params: ReviewParams):
    with state.lock:
        if not _account_exists(params.account_id):
            raise HTTPException(404, f"unknown account: {params.account_id}")
        if params.baseline_id not in state.engine.assumptions["baselines"]:
            raise HTTPException(422, f"unknown baseline: {params.baseline_id}")
        try:
            return build_review(state.con, params, engine=state.engine)
        except ValueError as e:  # unknown site / baseline etc.
            raise HTTPException(422, str(e))


def _review(params: ReviewParams):
    """Engine work under the lock; the (slow) LLM narration outside it."""
    review = _build(params)
    review.narrative = _narrate(review, True)
    return review


@app.get("/accounts")
def accounts():
    with state.lock:
        rows = state.con.execute(
            "select a.node_id, a.name, a.industry, "
            "(select count(*) from org_node s where s.parent_id = a.node_id and s.level = 'SITE') "
            "from org_node a where a.level = 'ACCOUNT' order by a.node_id").fetchall()
    return [{"node_id": r[0], "name": r[1], "industry": r[2], "site_count": r[3]} for r in rows]


@app.get("/accounts/{account_id}/review")
def review(account_id: str, period: str = "2025", product: str | None = None,
           baseline: str = "B_LOCAL", sens: str = "base", priorities: str | None = None,
           site: str | None = None, audience: str = "kam", hint: str | None = None,
           service_line: str | None = None):
    chips = [p.strip() for p in priorities.split(",") if p.strip() in KNOWN_PRIORITIES]         if priorities else None
    try:
        params = ReviewParams(account_id=account_id, period=period, product=product,
                              baseline_id=baseline, sensitivity=sens, priorities=chips,
                              priority_source_hint=(hint if hint else "chips") if chips else None,
                              site=site, audience=audience, service_line=service_line or None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _review(params).model_dump(mode="json")


def _inputs_spec() -> dict:
    return state.engine.assumptions["dto_inputs"]


@app.get("/accounts/{account_id}/inputs")
def get_inputs(account_id: str, include: str | None = None):
    """Effective service vs do-it-yourself inputs: defaults unless the KAM entered a value.
    `include=growth` returns {"inputs": [...], "growth": {...stored growth inputs}} so a form
    can send the whole stored set back (PUT replaces it)."""
    with state.lock:
        if not _account_exists(account_id):
            raise HTTPException(404, f"unknown account: {account_id}")
    spec = _inputs_spec()
    stored = load_inputs(account_id, spec)
    rows = effective_inputs(stored, spec)
    if include == "growth":
        return {"inputs": rows, "growth": stored_growth(stored)}
    return rows


@app.put("/accounts/{account_id}/inputs")
def put_inputs(account_id: str, body: dict = Body(...)):
    """Replace the account's entered inputs (no auth in the prototype; the UI shows the form to
    account managers only). 422 for unknown keys, non-numbers, negatives or low > high."""
    with state.lock:
        if not _account_exists(account_id):
            raise HTTPException(404, f"unknown account: {account_id}")
        spec = _inputs_spec()
        try:
            stored = save_inputs(account_id, body, spec)
        except ValueError as e:
            raise HTTPException(422, str(e))
    return effective_inputs(stored, spec)


class IntentRequest(BaseModel):
    text: str
    account_id: str | None = None


def _parse_intent(text: str) -> ViewSpec:
    from ai import llm
    from ai.intent import parse_intent
    with state.lock:
        accounts = [{"node_id": r[0], "name": r[1]} for r in state.con.execute(
            "select node_id, name from org_node where level = 'ACCOUNT' order by node_id").fetchall()]
    return parse_intent(text, accounts, state.engine.assumptions["baselines"], llm.use_llm())


@app.post("/intent")
def intent(req: IntentRequest):
    return _parse_intent(req.text).model_dump(mode="json")


class IntelRequest(BaseModel):
    company: str = Field(max_length=200)
    website: str | None = Field(default=None, max_length=300)
    # snapshot chips / auto-open: use the committed snapshot when there is one (no model call)
    prefer_snapshot: bool = False

    @field_validator("website")
    @classmethod
    def _website(cls, v: str | None) -> str | None:
        from ai.intel import is_http_url
        v = (v or "").strip()
        if v and not is_http_url(v):
            raise ValueError("website: enter an http(s) address such as https://example.com")
        return v or None


@app.post("/intel")
def intel(req: IntelRequest):
    """Account intelligence (G8): sourced public research, or the committed snapshot.
    Independent of the data pack and the engine: no review numbers are mixed in."""
    from ai import llm
    from ai.intel import IntelUnavailable, research_company
    if not req.company.strip():
        raise HTTPException(422, "company: enter a company name")
    try:
        return research_company(req.company, (req.website or "").strip() or None,
                                llm.use_llm(), prefer_snapshot=req.prefer_snapshot
                                ).model_dump(mode="json")
    except IntelUnavailable as e:
        raise HTTPException(503, str(e))


@app.get("/ai/status")
def ai_status():
    """Which AI features are available right now (no key values are ever returned)."""
    from ai import llm
    return {"ai_on": llm.use_llm(), "live_research": llm.use_llm()}


@app.get("/intel/snapshots")
def intel_snapshots():
    from ai.intel import list_snapshots
    return list_snapshots()


@app.get("/metrics/{metric_id}/explain")
def explain(metric_id: str, node_id: str, period: str = "2025", baseline: str = "B_LOCAL"):
    registry = state.engine.registry
    if metric_id not in registry:
        raise HTTPException(404, f"unknown metric: {metric_id}")
    if baseline not in state.engine.assumptions["baselines"]:
        raise HTTPException(422, f"unknown baseline: {baseline}")
    with state.lock:
        if state.con.execute("select 1 from org_node where node_id = ?", [node_id]).fetchone() is None:
            raise HTTPException(404, f"unknown node: {node_id}")
        try:
            result = state.engine.compute(node_id, period=period, baseline_id=baseline)[metric_id]
        except ValueError as e:  # bad period
            raise HTTPException(422, str(e))
    ids = set(result.assumptions)
    register = [r for r in state.engine.assumptions["register"] if r["id"] in ids]
    return {"definition": registry[metric_id], "result": result.model_dump(mode="json"),
            "assumptions": register}


class ExportRequest(ReviewParams):
    format: str = "pptx"


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EXPORT_FORMATS = {"pptx": PPTX_MIME, "pdf": "application/pdf", "xlsx": XLSX_MIME}


def _build_export(review_model, fmt: str, audience: str = "kam") -> bytes:
    from export.pdf_builder import build_pdf
    from export.pptx_builder import build_pptx
    from export.xlsx_builder import build_xlsx
    build = {"pptx": build_pptx, "pdf": build_pdf,
             "xlsx": lambda r, p: build_xlsx(r, p, audience=audience)}[fmt]
    with tempfile.TemporaryDirectory(prefix="vr_export_") as tmp:
        return build(review_model, Path(tmp) / f"review.{fmt}").read_bytes()


@app.post("/reviews/export")
def export(req: ExportRequest):
    if req.format not in EXPORT_FORMATS:
        raise HTTPException(400, f"unsupported format: {req.format}")
    try:
        params = ReviewParams(**req.model_dump(exclude={"format"}))
    except ValueError as e:
        raise HTTPException(422, str(e))
    data = _build_export(_review(params), req.format, params.audience)
    suffix = "_internal" if req.format == "xlsx" and params.audience != "customer" else ""
    return Response(data, media_type=EXPORT_FORMATS[req.format], headers={
        "Content-Disposition": f'attachment; filename="review_{params.account_id}_{params.period}{suffix}.{req.format}"'})


@app.get("/data-quality")
def data_quality(account_id: str = Query(...)):
    with state.lock:
        if not _account_exists(account_id):
            raise HTTPException(404, f"unknown account: {account_id}")
        con = state.con
        sources = [{"source_id": r[0], "name": r[1], "tier": r[2], "system": r[3],
                    "approved": r[4]} for r in con.execute(
            "select source_id, name, tier, system, approved from source order by source_id").fetchall()]
        quarantine = [{"table": r[0], "row_json": r[1], "reason": r[2]}
                      for r in con.execute('select "table", row_json, reason from quarantine').fetchall()]
        entities = [account_id]
        entities += [r[0] for r in con.execute(
            "select node_id from org_node where parent_id = ?", [account_id]).fetchall()]
        entities += [r[0] for r in con.execute(
            "select distinct laundry_id from fact_service_month where customer_id = ? "
            "and laundry_id is not null", [account_id]).fetchall()]
        warnings = dq_warning_rows(con, con.execute(
            "select check_id, severity, entity_type, entity_id, month, detail from dq_flags "
            "where list_contains(?, entity_id) order by check_id, entity_id, month",
            [entities]).fetchall())
    return {"sources": sources, "quarantine": quarantine, "warnings": warnings}


@app.get("/config/assumptions")
def config_assumptions():
    return state.engine.assumptions


@app.get("/config/modules")
def config_modules():
    path = CONFIG_DIR / "modules.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/config/glossary")
def config_glossary():
    return load_yaml("glossary.yaml")["terms"]


@app.get("/config/service-catalogue")
def config_service_catalogue():
    """Lindström service lines for the growth levers (illustrative sizing defaults T12+)."""
    return load_yaml("service_catalogue.yaml")


@app.get("/config/internal-metrics")
def config_internal_metrics():
    """Metric ids that are never customer-facing (the dashboard hides their modules)."""
    return sorted(mid for mid, spec in state.engine.registry.items()
                  if not spec.get("customer_facing", True))


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
