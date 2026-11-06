"""Output guard for generated text: placeholders only, no digits, no banned phrases (spec 10.2)."""
from __future__ import annotations

import re
from functools import lru_cache

from config.loader import load_yaml

PLACEHOLDER = re.compile(r"\{\{([^{}]*)\}\}")


@lru_cache(maxsize=1)
def _rules() -> dict:
    return load_yaml("wording_rules.yaml")


def _alternation(items: list[str]) -> str:
    return "|".join(re.escape(i) for i in sorted(items, key=len, reverse=True))


def strip_numerals(text: str, keep: list[str] | None = None) -> str:
    """Remove digit runs, except those inside an allowed name such as CO2 or Scope 3."""
    keep = _rules().get("allowed_numerals", []) if keep is None else keep
    if not keep:
        return re.sub(r"\d+", "", text)
    return re.sub(rf"({_alternation(keep)})|\d+",
                  lambda m: m.group(1) or "", text, flags=re.IGNORECASE)


def check(text: str, allowed: set[str], banned: list[str], allowed_numerals: list[str] | None = None,
          number_words: list[str] | None = None) -> list[str]:
    """Return the violations in `text`; an empty list means the text is acceptable."""
    rules = _rules()
    allowed_numerals = rules.get("allowed_numerals", []) if allowed_numerals is None else allowed_numerals
    number_words = rules.get("number_words", []) if number_words is None else number_words
    violations: list[str] = []
    for key in PLACEHOLDER.findall(text):
        if key.strip() not in allowed:
            violations.append(f"unknown placeholder: {{{{{key}}}}}")
    bare = PLACEHOLDER.sub(" ", text)
    if "{{" in bare or "}}" in bare:
        violations.append("malformed placeholder")
    protected = (re.sub(rf"({_alternation(allowed_numerals)})", " ", bare, flags=re.IGNORECASE)
                 if allowed_numerals else bare)
    digits = re.findall(r"\d+", protected)
    if digits:
        violations.append(f"digits outside placeholders: {', '.join(digits[:3])}")
    if number_words:
        for w in re.findall(rf"\b(?:{_alternation(number_words)})\b", bare, flags=re.IGNORECASE):
            violations.append(f"number word: {w.lower()}")
    low = text.lower()
    for phrase in banned:
        if phrase.lower() in low:
            violations.append(f"banned phrase: {phrase}")
    return violations


def render(text: str, values: dict[str, str]) -> str:
    """Replace each {{key}} with its value (unknown keys are left untouched)."""
    return PLACEHOLDER.sub(lambda m: values.get(m.group(1).strip(), m.group(0)), text)
