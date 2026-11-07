"""Account intelligence (design §8b G8): sourced public research on a real company.

Live path: Claude with the Anthropic server-side web search tool; the answer must come through
the ``submit_report`` tool. Code then drops every claim without an http(s) source and every
"how Lindström can help" item that is not in the service catalogue. Live results are cached per
company. Without an API key (or when the call fails) a committed snapshot is served.
No numbers from the value engine are mixed in.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field

from ai import llm
from config.loader import load_yaml

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / "data" / "intel_snapshots"
TIMEOUT_S = 60
CACHE_MAX_AGE = timedelta(days=7)
MAX_TURNS = 5  # server-tool continuations (pause_turn) plus one "submit now" nudge
DISCLAIMER = ("AI-generated from public sources — verify before use. "
              "Example public company; no relationship with Lindström is implied.")
SUBMIT_TOOL = "submit_report"
# The Anthropic server tool is plain JSON, so it works with any SDK version.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
CLAIM_SECTIONS = ("direction", "sustainability", "trends")
_HTTP = re.compile(r"^https?://[^\s/]+\.[^\s]+$", re.IGNORECASE)
_BAD_URL_CHARS = re.compile(r"[\s\"<>'`]")
_DATE = re.compile(r"^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")


class Claim(BaseModel):
    text: str
    source_url: str
    source_date: str


class HelpItem(BaseModel):
    offer_id: str
    offer_name: str
    why: str
    based_on: list[str] = Field(default_factory=list)


class Source(BaseModel):
    url: str
    title: str
    date: str


class IntelSections(BaseModel):
    direction: list[Claim] = Field(default_factory=list)
    sustainability: list[Claim] = Field(default_factory=list)
    trends: list[Claim] = Field(default_factory=list)
    how_lindstrom_helps: list[HelpItem] = Field(default_factory=list)
    conversation_starters: list[str] = Field(default_factory=list)


class IntelReport(BaseModel):
    company: str
    website: str | None = None
    generated_at: str
    mode: Literal["live", "snapshot"]
    sections: IntelSections
    sources: list[Source]
    disclaimer: str = DISCLAIMER


class IntelUnavailable(Exception):
    """No live research possible and no snapshot for this company."""


def slugify(company: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", company).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.strip().lower()).strip("-")


def _cache_dir() -> Path:
    return Path(os.environ.get("VR_INTEL_CACHE_DIR", ROOT / "data" / "intel_cache"))


def _catalogue() -> dict[str, str]:
    return {c["id"]: c["name"] for c in load_yaml("service_catalogue.yaml")}


# --- snapshots ---
def load_snapshot(slug: str) -> IntelReport | None:
    path = SNAPSHOT_DIR / f"{slug}.json"
    if not slug or not path.is_file():
        return None
    return IntelReport.model_validate_json(path.read_text(encoding="utf-8"))


def list_snapshots() -> list[dict]:
    out = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append({"slug": path.stem, "company": data["company"],
                    "generated_at": data["generated_at"]})
    return out


# --- live research ---
_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "One factual sentence."},
        "source_url": {"type": "string", "description": "Exact http(s) URL of the source."},
        "source_date": {"type": "string", "description": "Publication date, YYYY-MM-DD."},
    },
    "required": ["text", "source_url", "source_date"],
}


def _submit_tool(offer_ids: list[str]) -> dict:
    claims = {"type": "array", "items": _CLAIM_SCHEMA, "maxItems": 6}
    return {
        "name": SUBMIT_TOOL,
        "description": "Submit the final account intelligence report. Every claim must cite the "
                       "exact URL and date of the public source it comes from.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {**claims, "description": "Strategy, expansion or closures, sites, "
                              "workforce, M&A."},
                "sustainability": {**claims, "description": "Targets, progress, sustainability "
                                   "reporting (e.g. CSRD, Scope 3)."},
                "trends": {**claims, "maxItems": 4, "description": "2-4 trends in the "
                           "company's industry."},
                "how_lindstrom_helps": {
                    "type": "array", "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "offer_id": {"type": "string", "enum": offer_ids},
                            "offer_name": {"type": "string"},
                            "why": {"type": "string", "description": "One neutral sentence."},
                            "based_on": {"type": "array", "items": {"type": "string"},
                                         "description": "Source URLs this item relies on."},
                        },
                        "required": ["offer_id", "why", "based_on"],
                    },
                },
                "conversation_starters": {"type": "array", "items": {"type": "string"},
                                          "maxItems": 5},
                "sources": {
                    "type": "array",
                    "items": {"type": "object",
                              "properties": {"url": {"type": "string"},
                                             "title": {"type": "string"},
                                             "date": {"type": "string"}},
                              "required": ["url", "title", "date"]},
                },
            },
            "required": ["direction", "sustainability", "trends", "how_lindstrom_helps",
                         "conversation_starters", "sources"],
        },
    }


def _system(catalogue: dict[str, str]) -> str:
    offers = "; ".join(f"{k} = {v}" for k, v in catalogue.items())
    return (
        "You research a real public company for a Lindström key account manager preparing a "
        "first conversation. Use the web_search tool and rely only on recent (last 24 months), "
        "reputable public sources: the company's own website, annual and sustainability reports, "
        "press releases and established news media. "
        "Every claim is one factual sentence with the exact URL and publication date of its "
        "source; never invent facts, figures or URLs, and leave out anything you cannot source. "
        "Keep a neutral, factual tone. Do not state or imply that the company is a Lindström "
        "customer. Map at most five items to Lindström offers, using only these offer ids: "
        f"{offers}. Write up to four open conversation starters. "
        f"Finish by calling the {SUBMIT_TOOL} tool with the complete report.")


def _user_prompt(company: str, website: str | None) -> str:
    return f"Company: {company}" + (f"\nWebsite: {website}" if website else "")


def is_http_url(url) -> bool:
    """An http(s) URL with a dotted host and none of the characters that could break out of an
    HTML attribute or a Markdown link."""
    return isinstance(url, str) and not _BAD_URL_CHARS.search(url) and bool(_HTTP.match(url))


def normalise_url(url: str) -> str:
    """Comparison key: lower-case scheme and host, no fragment, no trailing slash."""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
                       parts.query, ""))


def _str(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _searched_urls(responses: list) -> set[str]:
    """Every URL a web_search_tool_result block returned, across all collected responses."""
    urls: set[str] = set()
    for resp in responses:
        for b in getattr(resp, "content", None) or []:
            if getattr(b, "type", "") != "web_search_tool_result":
                continue
            results = getattr(b, "content", None)
            for r in results if isinstance(results, list) else []:
                url = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
                if isinstance(url, str):
                    urls.add(normalise_url(url))
    return urls


def _sanitise(raw: dict, company: str, website: str | None, catalogue: dict[str, str],
              searched: set[str]) -> IntelReport:
    """Keep only claims whose source the web search actually returned, with a date, and catalogue
    offers backed by such a source; the disclaimer is always ours."""
    def found(url) -> bool:
        return is_http_url(url) and normalise_url(url) in searched

    sections: dict = {}
    for name in CLAIM_SECTIONS:
        items = raw.get(name) if isinstance(raw.get(name), list) else []
        sections[name] = [Claim(text=_str(c.get("text")), source_url=c["source_url"].strip(),
                                source_date=_str(c.get("source_date")))
                          for c in items if isinstance(c, dict) and _str(c.get("text"))
                          and found(c.get("source_url"))
                          and _DATE.match(_str(c.get("source_date")))]
    if not any(sections[n] for n in CLAIM_SECTIONS):
        raise ValueError("no sourced claims in the report")
    helps = raw.get("how_lindstrom_helps") if isinstance(raw.get("how_lindstrom_helps"), list)         else []
    sections["how_lindstrom_helps"] = []
    for h in helps:
        if not (isinstance(h, dict) and h.get("offer_id") in catalogue and _str(h.get("why"))):
            continue
        based_on = h.get("based_on") if isinstance(h.get("based_on"), list) else []
        based_on = [u.strip() for u in based_on if found(u)]
        if based_on:  # an offer mapping without a real source is dropped
            sections["how_lindstrom_helps"].append(HelpItem(
                offer_id=h["offer_id"], offer_name=catalogue[h["offer_id"]],
                why=_str(h.get("why")), based_on=based_on))
    starters = raw.get("conversation_starters")
    sections["conversation_starters"] = [_str(s) for s in starters or [] if _str(s)]         if isinstance(starters, list) else []

    sources: dict[str, Source] = {}
    for s in raw.get("sources") if isinstance(raw.get("sources"), list) else []:
        if isinstance(s, dict) and found(s.get("url")):
            url = s["url"].strip()
            sources.setdefault(normalise_url(url), Source(
                url=url, title=_str(s.get("title")) or url, date=_str(s.get("date"))))
    cited = [c for n in CLAIM_SECTIONS for c in sections[n]]
    for c in cited:  # the sources list always covers every cited URL
        sources.setdefault(normalise_url(c.source_url),
                           Source(url=c.source_url, title=c.source_url, date=c.source_date))
    for h in sections["how_lindstrom_helps"]:
        for u in h.based_on:
            sources.setdefault(normalise_url(u), Source(url=u, title=u, date=""))
    return IntelReport(company=company, website=website,
                       generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       mode="live", sections=IntelSections(**sections),
                       sources=list(sources.values()))


def _submitted(resp) -> dict | None:
    for b in resp.content:
        if getattr(b, "type", "") == "tool_use" and getattr(b, "name", "") == SUBMIT_TOOL:
            return dict(b.input or {})
    return None


def _live(company: str, website: str | None, record: dict) -> IntelReport:
    catalogue = _catalogue()
    tools = [WEB_SEARCH_TOOL, _submit_tool(list(catalogue))]
    system = _system(catalogue)
    messages: list[dict] = [{"role": "user", "content": _user_prompt(company, website)}]
    record.update(model=llm.MODEL, system=system, input=messages[0]["content"], turns=[])
    deadline = time.monotonic() + TIMEOUT_S
    client = llm.get_client()
    nudged = False
    responses: list = []
    for _ in range(MAX_TURNS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no report within {TIMEOUT_S} s")
        kw = dict(model=llm.MODEL, max_tokens=8000, system=system, messages=messages,
                  tools=tools, timeout=remaining)
        if nudged:
            kw["tool_choice"] = {"type": "tool", "name": SUBMIT_TOOL}
        resp = client.messages.create(**kw)
        responses.append(resp)
        stop = getattr(resp, "stop_reason", None)
        record["turns"].append({"stop_reason": stop})
        raw = _submitted(resp)
        if raw is not None:
            record["output"] = raw
            return _sanitise(raw, company, website, catalogue, _searched_urls(responses))
        messages = [*messages, {"role": "assistant", "content": resp.content}]
        if stop == "pause_turn":  # the server tool loop paused: let the model continue
            continue
        if nudged:
            break
        nudged = True
        messages.append({"role": "user",
                         "content": f"Call {SUBMIT_TOOL} now with the complete, sourced report."})
    raise ValueError(f"the model did not call {SUBMIT_TOOL}")


def _log(slug: str, record: dict) -> None:
    try:
        d = Path(os.environ.get("VR_LOG_DIR", ROOT / "logs"))
        d.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        (d / f"intel-{slug}-{stamp}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def _read_cache(slug: str) -> IntelReport | None:
    path = _cache_dir() / f"{slug}.json"
    try:
        rep = IntelReport.model_validate_json(path.read_text(encoding="utf-8"))
        age = datetime.now(timezone.utc) - datetime.fromisoformat(rep.generated_at)
        return rep if age <= CACHE_MAX_AGE else None
    except (OSError, ValueError, TypeError):  # missing, corrupt or naive timestamp: research again
        return None


def _write_cache(slug: str, rep: IntelReport) -> None:
    try:
        d = _cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{slug}.json").write_text(rep.model_dump_json(indent=2), encoding="utf-8")
    except OSError:
        pass


def research_company(company: str, website: str | None, use_llm: bool,
                     prefer_snapshot: bool = False) -> IntelReport:
    """Live research (cached), else the committed snapshot. With `prefer_snapshot` a committed
    snapshot is returned straight away, without a model call (snapshot chips, auto-open)."""
    company = company.strip()
    slug = slugify(company)
    if not slug:
        raise IntelUnavailable("Enter a company name.")
    if prefer_snapshot:
        snapshot = load_snapshot(slug)
        if snapshot is not None:
            return snapshot
    reason = "no Anthropic API key is configured (or AI is switched off)"
    if use_llm:
        cached = _read_cache(slug)
        if cached is not None:
            return cached
        record: dict = {"company": company, "website": website}
        try:
            rep = _live(company, website, record)
            _write_cache(slug, rep)
            return rep
        except Exception as e:  # network, timeout, malformed output: snapshot or unavailable
            record["error"] = f"{type(e).__name__}: {e}"
            reason = "the live research failed"
        finally:
            _log(slug, record)
    snapshot = load_snapshot(slug)
    if snapshot is not None:
        return snapshot
    examples = ", ".join(f"'{s['company']}'" for s in list_snapshots())
    raise IntelUnavailable(
        f"Account intelligence for '{company}' is not available: {reason}, and there is no "
        "snapshot for this company. Set ANTHROPIC_API_KEY for live research"
        + (f", or try the example {examples}." if examples else "."))
