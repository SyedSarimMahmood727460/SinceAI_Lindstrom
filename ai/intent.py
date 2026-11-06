"""Intent parser: free text -> ViewSpec. Claude tool use, with a keyword fallback (spec 10.1)."""
from __future__ import annotations

import re

from ai import llm
from model.contracts import ViewSpec

PRIORITY_KEYWORDS = {
    "water": ["water", "litre", "liter"],
    "emissions": ["emission", "co2", "carbon", "climate", "scope"],
    "cost": ["cost", "money", "euro", "€", "budget", "allocation", "utili", "optimi"],
    "circularity": ["circular", "repair", "waste", "recycl", "lifetime", "reuse"],
    "service": ["service", "delivery", "on-time", "late", "reliab", "hygiene", "continuity",
                "request"],
}
PRIORITY_LABELS = {"water": "Water", "emissions": "Emissions", "cost": "Cost",
                   "circularity": "Circularity", "service": "Service"}
VIEWS = ["overview", "sites", "footprint", "circularity", "steering", "methodology", "readiness"]
SENSITIVITIES = ["low", "base", "high"]
# Order matters: the first matching rule wins (as in the mockup).
VIEW_RULES = [(r"steer|discussion", "steering"), (r"compare|baseline", "footprint"),
              (r"which site|outlier", "sites"), (r"improve|next year", "steering")]
BASELINE_PATTERNS = {"B_HOME": r"\bhome\b", "B_INHOUSE": r"in-house|\binhouse\b",
                     "B_LOCAL": r"\blocal\b"}
NOT_RECOGNISED = "Not recognised"


def _baseline_names(baselines: dict) -> dict[str, str]:
    return {k: (v.get("name", k) if isinstance(v, dict) else str(v)) for k, v in baselines.items()}


def _interpretation(text: str, spec: ViewSpec, accounts: list[dict], baselines: dict) -> ViewSpec:
    parts: list[str] = []
    if spec.priorities:
        parts.append("priority " + " + ".join(PRIORITY_LABELS[p] for p in spec.priorities))
    if spec.node_id:
        name = next((a.get("name", spec.node_id) for a in accounts if a["node_id"] == spec.node_id),
                    spec.node_id)
        parts.append("customer " + name)
    if spec.baseline_id:
        parts.append("baseline " + _baseline_names(baselines)[spec.baseline_id])
    if spec.sensitivity:
        parts.append("sensitivity " + spec.sensitivity)
    if spec.view:
        parts.append("view " + spec.view)
    spec.interpretation_text = (f"Understood: “{text}” → " + ", ".join(parts) if parts
                                else f"{NOT_RECOGNISED}: “{text}”. Try a suggested prompt.")
    return spec


def keyword_intent(text: str, accounts: list[dict], baselines: dict) -> ViewSpec:
    q = text.lower()
    spec = ViewSpec(priorities=[k for k, kws in PRIORITY_KEYWORDS.items()
                                if any(w in q for w in kws)])
    for a in accounts:
        first = (a.get("name") or "").split(" ")[0].lower()
        if first and first in q:
            spec.node_id = a["node_id"]
    for bid, pat in BASELINE_PATTERNS.items():
        if bid in baselines and re.search(pat, q):
            spec.baseline_id = bid
    for pat, view in VIEW_RULES:
        if re.search(pat, q):
            spec.view = view
            break
    return _interpretation(text, spec, accounts, baselines)


TOOL_NAME = "set_view"


def _tool(accounts: list[dict], baselines: dict) -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Set the review view from the user's request. Use only the listed ids.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "enum": [a["node_id"] for a in accounts]},
                "priorities": {"type": "array",
                               "items": {"type": "string", "enum": list(PRIORITY_KEYWORDS)}},
                "baseline_id": {"type": "string", "enum": list(baselines)},
                "sensitivity": {"type": "string", "enum": SENSITIVITIES},
                "view": {"type": "string", "enum": VIEWS},
            },
        },
    }


def _validated(raw: dict, accounts: list[dict], baselines: dict) -> ViewSpec:
    """Drop every id the model invented."""
    ids = {a["node_id"] for a in accounts}
    pri = raw.get("priorities")
    return ViewSpec(
        node_id=raw.get("node_id") if raw.get("node_id") in ids else None,
        priorities=[p for p in dict.fromkeys(pri if isinstance(pri, list) else [])
                    if p in PRIORITY_KEYWORDS],
        baseline_id=raw.get("baseline_id") if raw.get("baseline_id") in baselines else None,
        sensitivity=raw.get("sensitivity") if raw.get("sensitivity") in SENSITIVITIES else None,
        view=raw.get("view") if raw.get("view") in VIEWS else None)


def _llm_intent(text: str, accounts: list[dict], baselines: dict) -> ViewSpec:
    system = (
        "You map a key account manager's request to a view of a customer value review. "
        "Call the set_view tool. Use only these customers: "
        + "; ".join(f"{a['node_id']} = {a.get('name')}" for a in accounts)
        + ". Baselines: " + "; ".join(f"{k} = {v}" for k, v in _baseline_names(baselines).items())
        + ". Priorities: " + ", ".join(PRIORITY_KEYWORDS) + ". Views: " + ", ".join(VIEWS)
        + ". Never invent ids; omit a field when the request does not say.")
    resp = llm.get_client().messages.create(
        model=llm.MODEL, max_tokens=400, system=system, timeout=llm.TIMEOUT_S,
        messages=[{"role": "user", "content": text}],
        tools=[_tool(accounts, baselines)], tool_choice={"type": "tool", "name": TOOL_NAME})
    block = next(b for b in resp.content
                 if getattr(b, "type", "") == "tool_use" and b.name == TOOL_NAME)
    if not block.input:
        raise ValueError("empty tool input")  # parse_intent falls back to the keyword matcher
    return _interpretation(text, _validated(dict(block.input), accounts, baselines),
                           accounts, baselines)


def parse_intent(text: str, accounts: list[dict], baselines: dict, use_llm: bool) -> ViewSpec:
    if use_llm:
        try:
            return _llm_intent(text, accounts, baselines)
        except Exception:  # timeout, API error, malformed tool output: use the keyword matcher
            pass
    return keyword_intent(text, accounts, baselines)
