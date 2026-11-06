"""Shared pydantic contracts for the value review pipeline."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MethodStatus(str, Enum):
    MEASURED = "MEASURED"
    CALCULATED = "CALCULATED"
    ALLOCATED = "ALLOCATED"
    ESTIMATED = "ESTIMATED"


_STRENGTH = list(MethodStatus)  # strongest -> weakest


def weakest(*s: MethodStatus) -> MethodStatus:
    """Return the weakest status; a derived value is only as strong as its inputs."""
    return max(s, key=_STRENGTH.index)


class Provenance(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"
    APPROVED_REAL = "APPROVED_REAL"


class Scope(BaseModel):
    node_id: str
    level: Literal["ACCOUNT", "SITE"]
    period: str
    product: str | None = None


class Range(BaseModel):
    low: float | None = None
    base: float | None = None
    high: float | None = None


class Lineage(BaseModel):
    facts: list[str]
    rows: int
    load_ids: list[str]


class MetricResult(BaseModel):
    metric_id: str
    label: str
    unit: str
    scope: Scope
    value: float | None
    range: Range | None
    method_status: MethodStatus
    provenance: Provenance
    confidence: str
    assumptions: list[str]
    lineage: Lineage
    formula_text: str
    priority_tags: list[str]
    customer_facing: bool = True
    dq_warning: bool = False


class Observation(BaseModel):
    id: str
    rule_id: str
    title: str
    finding: str
    action: str
    tags: list[str]
    node_id: str
    evidence: list[tuple[str, str]]
    method_status: MethodStatus
    confidence: str
    score: float = 0
    z: float | None = None
    dq_warning: bool = False


class ViewSpec(BaseModel):
    node_id: str | None = None
    priorities: list[str] = Field(default_factory=list)
    baseline_id: str | None = None
    sensitivity: Literal["low", "base", "high"] | None = None
    view: str | None = None
    interpretation_text: str = ""


class Narrative(BaseModel):
    exec_summary: str
    discussion_points: list[str]
    generated_by: Literal["llm", "template"]
