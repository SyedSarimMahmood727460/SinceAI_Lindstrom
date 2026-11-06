"""Shared LLM plumbing: model id, switch, client factory (monkeypatched in tests)."""
from __future__ import annotations

import os

MODEL = "claude-sonnet-5-5"
TIMEOUT_S = 15.0


def use_llm() -> bool:
    return os.environ.get("VR_AI", "on") != "off" and "ANTHROPIC_API_KEY" in os.environ


def get_client():
    import anthropic
    return anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)
