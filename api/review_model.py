"""ReviewModel: the contract between the engine, API, dashboard, export and AI (spec 11.2)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from model.contracts import MetricResult, Narrative, Observation

DISCLAIMER = "Prototype · synthetic data · not audited"


class ReviewParams(BaseModel):
    account_id: str
    period: str = "2025"
    product: str | None = None
    service_line: str | None = None
    baseline_id: str = "B_LOCAL"
    sensitivity: Literal["low", "base", "high"] = "base"
    priorities: list[str] | None = None
    priority_source_hint: Literal["prompt", "chips"] | None = None
    site: str | None = None
    audience: Literal["kam", "customer"] = "kam"


class NodeInfo(BaseModel):
    id: str
    name: str
    industry: str | None = None
    segment: str | None = None
    countries: list[str] = Field(default_factory=list)


class Meta(BaseModel):
    run_id: str
    generated_at: datetime
    node: NodeInfo
    period: str
    baseline: dict[str, Any]
    sensitivity: str
    assumption_set_version: str
    sources: list[dict[str, Any]]
    products: list[dict[str, str]]
    service_lines: list[str] = Field(default_factory=list)
    service_line: str | None = None
    disclaimer: str = DISCLAIMER


class Context(BaseModel):
    active_priorities: list[str]
    priority_source: Literal["prompt", "chips", "customer", "industry"]
    interpretation_text: str = ""
    industry_note: str = ""


class Kpi(MetricResult):
    display: dict[str, Any]


class SiteEntry(BaseModel):
    node_id: str
    name: str
    country: str | None = None
    city: str | None = None
    site_type: str | None = None
    laundry_id: str | None = None
    metrics: dict[str, MetricResult]
    outlier_flags: list[str] = Field(default_factory=list)


class DtoLine(BaseModel):
    id: str
    label: str
    diy: MetricResult


class Dto(BaseModel):
    """Service vs do-it-yourself comparison (design §8a.4 item 4). € lines, hours and the
    environment metrics stay separate; `net` exists only when a contract price was entered."""
    baseline: str
    inputs: list[dict[str, Any]]
    lines: list[DtoLine]
    diy_total: MetricResult
    contract_price: MetricResult | None = None
    net: MetricResult | None = None
    convenience: dict[str, MetricResult | None]
    hygiene_note: str | None = None


class ReviewModel(BaseModel):
    meta: Meta
    context: Context
    kpis: list[Kpi]
    sites: list[SiteEntry]
    trends: dict[str, list[dict[str, Any]]]
    comparisons: dict[str, Any]
    circularity: dict[str, Any]
    observations: list[Observation]
    narrative: Narrative
    actions: list[dict[str, Any]]
    methodology: dict[str, Any]
    data_quality: dict[str, Any]
    dto: Dto | None = None
    story: list[dict[str, Any]] = Field(default_factory=list)
