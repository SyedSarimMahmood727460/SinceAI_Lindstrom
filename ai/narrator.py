"""Narrator: LLM-drafted executive summary and discussion points, guarded, with template fallback."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from ai import llm
from ai.guard import check, render
from ai.templates import placeholder_values, template_narrative, wording_rules
from api.review_model import ReviewModel
from model.contracts import Narrative

ROOT = Path(__file__).resolve().parent.parent
MAX_WORDS = 120
N_POINTS = 5

SYSTEM_TEMPLATE = """You write the narrative for a customer value and sustainability review.
Rules:
- Write NO digits at all. Every number must be a placeholder written as {{{{key}}}}, using only the
  allowed keys listed in the input. Never invent a key.
- Refer to an observation as {{{{obs:<id>}}}} (it is replaced by the observation title).
- The executive summary has at most {max_words} words.
- Write exactly {n_points} discussion points, one sentence each.
- Never use these phrases: {banned}.
- "saved" or "avoided" must be followed by "vs {{{{baseline.name}}}} (estimate)".
- Use plain, factual language. Do not claim certification or guarantees.
Reply with JSON only: {{"exec_summary": "...", "discussion_points": ["...", ...]}}"""


def _strip_digits(s: str) -> str:
    return re.sub(r"\d+", "", s).replace("  ", " ").strip()


def _llm_input(review: ReviewModel, keys: list[str]) -> dict:
    return {
        "account": "{{account.name}}",
        "priorities": review.context.active_priorities,
        "allowed_keys": keys,
        "kpis": [{"id": k.metric_id, "label": k.label, "tags": k.priority_tags}
                 for k in review.kpis if k.customer_facing],
        "observations": [{"id": o.id, "placeholder": "{{obs:%s}}" % o.id,
                          "title": _strip_digits(o.title), "action": _strip_digits(o.action),
                          "tags": o.tags} for o in review.observations],
    }


def _parse(text: str) -> tuple[str, list[str]]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    data = json.loads(text)
    summary, points = data["exec_summary"], data["discussion_points"]
    if not isinstance(summary, str) or not isinstance(points, list) \
            or not all(isinstance(p, str) for p in points):
        raise ValueError("bad shape")
    return summary, points


def _validate(summary: str, points: list[str], allowed: set[str], banned: list[str],
              values: dict[str, str]) -> list[str]:
    problems = check(summary, allowed, banned)
    for p in points:
        problems += check(p, allowed, banned)
    if len(points) != N_POINTS:
        problems.append(f"expected {N_POINTS} discussion points, got {len(points)}")
    if len(render(summary, values).split()) > MAX_WORDS:
        problems.append(f"summary longer than {MAX_WORDS} words")
    return problems


def _log(review: ReviewModel, record: dict) -> None:
    try:
        d = Path(os.environ.get("VR_LOG_DIR", ROOT / "logs"))
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{review.meta.run_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def narrate(review: ReviewModel, use_llm: bool) -> Narrative:
    if not use_llm:
        return template_narrative(review)
    values = placeholder_values(review)
    allowed = set(values)
    banned = wording_rules()["banned"]
    system = SYSTEM_TEMPLATE.format(max_words=MAX_WORDS, n_points=N_POINTS, banned=", ".join(banned))
    payload = json.dumps(_llm_input(review, sorted(allowed)), ensure_ascii=False)
    messages = [{"role": "user", "content": payload}]
    record: dict = {"run_id": review.meta.run_id, "model": llm.MODEL, "system": system,
                    "input": payload, "attempts": []}
    deadline = time.monotonic() + llm.TIMEOUT_S
    result: Narrative | None = None
    try:
        client = llm.get_client()
        for _ in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                record["attempts"].append({"error": "timeout"})
                break
            attempt: dict = {}
            record["attempts"].append(attempt)
            try:
                resp = client.messages.create(model=llm.MODEL, max_tokens=1200, system=system,
                                              messages=messages, timeout=remaining)
                out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                attempt["output"] = out
                summary, points = _parse(out)
            except Exception as e:  # network, timeout, malformed output: try again, then fall back
                attempt["error"] = f"{type(e).__name__}: {e}"
                continue
            problems = _validate(summary, points, allowed, banned, values)
            attempt["violations"] = problems
            if not problems:
                result = Narrative(exec_summary=render(summary, values),
                                   discussion_points=[render(p, values) for p in points],
                                   generated_by="llm")
                break
    except Exception as e:  # no client / no key
        record["attempts"].append({"error": f"{type(e).__name__}: {e}"})
    record["generated_by"] = result.generated_by if result else "template"
    _log(review, record)
    return result or template_narrative(review)
