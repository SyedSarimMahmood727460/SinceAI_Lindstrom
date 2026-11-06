"""Output guard for generated text: placeholders only, no digits, no banned phrases (spec 10.2)."""
from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{([^{}]*)\}\}")


def check(text: str, allowed: set[str], banned: list[str]) -> list[str]:
    """Return the violations in `text`; an empty list means the text is acceptable."""
    violations: list[str] = []
    for key in PLACEHOLDER.findall(text):
        if key.strip() not in allowed:
            violations.append(f"unknown placeholder: {{{{{key}}}}}")
    bare = PLACEHOLDER.sub("", text)
    if "{{" in bare or "}}" in bare:
        violations.append("malformed placeholder")
    digits = re.findall(r"\d+", bare)
    if digits:
        violations.append(f"digits outside placeholders: {', '.join(digits[:3])}")
    low = text.lower()
    for phrase in banned:
        if phrase.lower() in low:
            violations.append(f"banned phrase: {phrase}")
    return violations


def render(text: str, values: dict[str, str]) -> str:
    """Replace each {{key}} with its value (unknown keys are left untouched)."""
    return PLACEHOLDER.sub(lambda m: values.get(m.group(1).strip(), m.group(0)), text)
