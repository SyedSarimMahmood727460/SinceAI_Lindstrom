"""FastAPI service (spec 11.1). The pack is loaded once at startup; one Engine is reused."""
from __future__ import annotations

import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.build import build_review
from api.review_model import ReviewParams
from config.loader import CONFIG_DIR, load_assumptions, load_yaml
from metrics.engine import Engine
from model.contracts import ViewSpec
from model.load import load_pack

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DEFAULT_PACK = ("../lindstrom_pack/Lindstrom_SinceAI2026/"
                "Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx")
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
    pack = (ROOT / os.environ.get("VR_PACK_PATH", DEFAULT_PACK)).resolve()
    state.con = load_pack(pack)
    state.engine = Engine(state.con, load_assumptions(), load_yaml("metrics.yaml"))
    yield
    state.con.close()


app = FastAPI(title="Value Review", lifespan=lifespan, default_response_class=UTF8JSONResponse)


def _account_exists(account_id: str) -> bool:
    return state.con.execute("select 1 from org_node where node_id = ? and level = 'ACCOUNT'",
                             [account_id]).fetchone() is not None


def _review(params: ReviewParams):
    with state.lock:
        if not _account_exists(params.account_id):
            raise HTTPException(404, f"unknown account: {params.account_id}")
        if params.baseline_id not in state.engine.assumptions["baselines"]:
            raise HTTPException(422, f"unknown baseline: {params.baseline_id}")
        return build_review(state.con, params, engine=state.engine)


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
           site: str | None = None, audience: str = "kam"):
    chips = [p.strip() for p in priorities.split(",") if p.strip()] if priorities else None
    try:
        params = ReviewParams(account_id=account_id, period=period, product=product,
                              baseline_id=baseline, sensitivity=sens, priorities=chips,
                              priority_source_hint="chips" if chips else None,
                              site=site, audience=audience)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _review(params).model_dump(mode="json")


class IntentRequest(BaseModel):
    text: str
    account_id: str | None = None


def _parse_intent(text: str) -> ViewSpec:
    """Hook for Task 9: uses ai.intent.keyword_intent when importable."""
    try:
        from ai.intent import keyword_intent
    except ImportError:
        return ViewSpec(interpretation_text="Not recognised")
    with state.lock:
        return keyword_intent(text, state.con)


@app.post("/intent")
def intent(req: IntentRequest):
    return _parse_intent(req.text).model_dump(mode="json")


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
        result = state.engine.compute(node_id, period=period, baseline_id=baseline)[metric_id]
    ids = set(result.assumptions)
    register = [r for r in state.engine.assumptions["register"] if r["id"] in ids]
    return {"definition": registry[metric_id], "result": result.model_dump(mode="json"),
            "assumptions": register}


class ExportRequest(ReviewParams):
    format: str = "pptx"


def _build_pptx(review_model) -> bytes | None:
    """Hook for Task 8: return `export.pptx_builder.build_pptx(review_model)` bytes."""
    return None


@app.post("/reviews/export")
def export(req: ExportRequest):
    if req.format != "pptx":
        raise HTTPException(400, f"unsupported format: {req.format}")
    params = ReviewParams(**req.model_dump(exclude={"format"}))
    data = _build_pptx(_review(params))
    if data is None:
        raise HTTPException(501, "PPTX export is not available yet")
    return Response(data, media_type=PPTX_MIME, headers={
        "Content-Disposition": f'attachment; filename="value-review-{params.account_id}.pptx"'})


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
        cols = ("check_id", "severity", "entity_type", "entity_id", "month", "detail")
        warnings = [dict(zip(cols, r)) for r in con.execute(
            "select check_id, severity, entity_type, entity_id, month, detail from dq_flags "
            "where list_contains(?, entity_id) order by check_id, entity_id, month",
            [entities]).fetchall()]
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


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
