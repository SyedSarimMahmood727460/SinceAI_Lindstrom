"""Priority resolution (spec section 9.3): prompt > chips > customer topics + industry fill."""
from __future__ import annotations

from config.loader import load_yaml

PRIORITY_KEYS = ["water", "emissions", "cost", "circularity", "service"]


def _unique(items) -> list[str]:
    out: list[str] = []
    for x in items:
        if x in PRIORITY_KEYS and x not in out:
            out.append(x)
    return out


def resolve_priorities(customer_topics: list[str], industry: str, chips: list[str] | None = None,
                       prompt: list[str] | None = None) -> tuple[list[str], str]:
    rules = load_yaml("industry_rules.yaml")
    if prompt and (p := _unique(prompt)):
        return p, "prompt"
    if chips and (c := _unique(chips)):
        return c, "chips"
    mapped = _unique(rules["topic_map"].get(t) for t in customer_topics or [])
    defaults = rules["defaults"].get(industry, [])
    if mapped:
        return _unique(mapped + defaults), "customer"
    return _unique(defaults), "industry"
