# Value Review

Value Review is a prototype Customer Value & Sustainability Review generator for the Lindström × Since AI 2026 challenge. It turns multi-site service, laundry, repair and waste data into a dynamic review that a key account manager (KAM) can tailor to a customer's priorities and export as a PPTX deck.

**Status: prototype. All data is synthetic (the Lindström × Since AI data pack). Nothing here is audited.** The disclaimer `Prototype · synthetic data · not audited` is shown on the web banner, in every PPTX slide footer and in `ReviewModel.meta.disclaimer`.

What it does:

- Dashboard with customer-level totals and site drill-down, filters for period (2025 or a quarter), product, baseline (local laundry, home washing, in-house laundry), sensitivity (low/base/high) and audience (KAM or customer).
- Personalisation: a typed prompt, priority chips, the customer's stated priority topics and industry rules decide what is shown first.
- Observations with evidence, discussion points and an action table for a steering committee.
- Every figure carries a method status (MEASURED / CALCULATED / ALLOCATED / ESTIMATED), a provenance (SYNTHETIC / PUBLIC_REFERENCE / APPROVED_REAL), a low/base/high range for estimated values, and a "how calculated" drawer.
- PPTX export built from the same `ReviewModel` as the dashboard, so the two cannot disagree.
- A data-quality view: quarantine, and a cross-source consistency warning (C1) that the pack fails for laundry L003.
- AI is optional and guarded. It never writes numbers. The app works fully with no API key.

## Quick start (Windows)

Requires Python 3.12.

```bat
cd value-review
python -m pip install -e .[dev]
set VR_PACK_PATH=C:\path\to\Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx
python -m uvicorn api.main:app --port 8000
```

Then open http://127.0.0.1:8000.

Without `-e .`, install the dependencies directly: `pandas openpyxl duckdb pydantic>=2 PyYAML fastapi uvicorn python-pptx matplotlib anthropic httpx` (plus `pytest` for tests).

PowerShell: `$env:VR_PACK_PATH = "C:\path\to\pack.xlsx"`. Bash: `export VR_PACK_PATH=...`.

The pack is loaded into an in-memory DuckDB at server start (a few seconds). A relative `VR_PACK_PATH` is resolved against the repository root.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `VR_PACK_PATH` | `../lindstrom_pack/Lindstrom_SinceAI2026/Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx` (relative to the repo root) | Path to the Excel data pack. |
| `ANTHROPIC_API_KEY` | unset | Enables the LLM intent parser and narrator (model `claude-sonnet-5-5`, 15 s timeout). Unset means keyword parser and template narrative. |
| `VR_AI` | `on` | `VR_AI=off` disables all LLM calls even when a key is set. |
| `VR_INJECT_BAD_ROWS` | unset | `VR_INJECT_BAD_ROWS=1` injects 3 bad rows (unknown site, empty month, negative kg) at load time to demo the quarantine in the Data readiness view. The loader already supports this (`load_pack(..., inject_bad=True)`); reading the variable in `api/main.py` is being added separately, so check that your checkout reads it before relying on it. |
| `VR_LOG_DIR` | `logs/` in the repo root | Where the narrator writes one JSON log per `run_id` (prompt, output, guard violations, `generated_by`). Only written when the LLM path runs. |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/accounts` | Customers with industry and site count. |
| GET | `/accounts/{id}/review?period=&product=&baseline=&sens=&priorities=&site=&audience=` | One `ReviewModel`. `audience=customer` hides non-customer-facing metrics. |
| POST | `/intent` `{text}` | Prompt to `ViewSpec`. |
| GET | `/metrics/{metric_id}/explain?node_id=` | Definition, formula, assumptions, lineage. |
| POST | `/reviews/export` | PPTX download (same params as review, `format: "pptx"`). PDF is not implemented. |
| GET | `/data-quality?account_id=` | Sources, quarantine rows, warnings for that account. |
| GET | `/config/assumptions`, `/config/modules` | Active assumption set and module registry. |

## Tests

```bat
python -m pytest
```

## Architecture

Full diagrams (layered overview, request flow, data model) are in [docs/architecture.md](docs/architecture.md).

```
Sources (Tier 0 pack · Tier 1 BI/eLindström exports · Tier 2 warehouse)
  → Source adapters (extract, map, validate; quarantine)
  → Canonical model (DuckDB)      ← Config store (assumption set, metrics, rules)
  → Metric engine → Insight engine
  → Review API (one ReviewModel) ↔ AI layer (intent parser, narrator)
  → Web dashboard · PPTX export · (future) eLindström embed
```

Principles: the data contract is the centre; only the metric engine produces numbers; every value has a method status and a provenance (a derived value takes the weakest of its inputs); configuration over code; the AI is optional and guarded.

## Repository layout

```
adapters/   base.py (Adapter protocol), excel_pack.py (Tier 0 pack), fixtures.py (bad-row injection)
model/      ddl.sql (canonical tables), contracts.py (pydantic contracts), load.py, validate.py (ERROR rules, C1-C3 checks)
config/     assumptions/v1.yaml, metrics.yaml, industry_rules.yaml, review_text.yaml, wording_rules.yaml, modules.json, loader.py
metrics/    engine.py (all calculations), frames.py (per-kg allocation), periods.py
insights/   rules.py (R1-R8), priorities.py, discussion.py
ai/         intent.py, narrator.py, guard.py, templates.py, llm.py
api/        main.py (routes), build.py (assembles ReviewModel), review_model.py
export/     pptx_builder.py, charts.py
web/        index.html, app.js, modules.js, styles.css (static SPA served at /)
tests/      pytest suite incl. reconciliation against the pack's reference sheets
docs/       methodology.md, data_readiness.md, demo_script.md, architecture.md, specs/
```

## Documentation

- [Methodology note](docs/methodology.md): baselines, boundary, allocation, sensitivity, repair range, wearer de-duplication, the L003 finding, limitations.
- [Data readiness note](docs/data_readiness.md): field to future source to gap table, Tier 0-3 roadmap, how to add an adapter.
- [Demo script](docs/demo_script.md): 4-minute walkthrough with talking points per judging criterion.
- [Architecture](docs/architecture.md): three Mermaid diagrams.
- [Design spec](docs/specs/2026-11-06-value-review-design.md).

## Extending

**Add an adapter.** Implement the `Adapter` protocol in `adapters/base.py` (`source_id`, `tier`, `extract()`, `to_canonical()`), modelled on `adapters/excel_pack.py`. `to_canonical` must return the eight canonical frames named in `model/load.py` (`TABLES`) and tag fact rows with `method_status`, `provenance`, `source_id`, `load_id`. Add rules to `model/validate.py` if it introduces new keys, and call it from `load_pack` in `model/load.py`. Nothing after the adapters needs to change. See [data_readiness.md](docs/data_readiness.md).

**Add a metric.** Add an entry to `config/metrics.yaml` (id, label, unit, aggregation, method_status, confidence, assumptions, priority_tags, customer_facing, formula_text, inputs). Compute its value in `metrics/engine.py` (`_values`); if it depends on sensitivity add its id to `SENSITIVE`. Set `headline: true` to sort it among the headline KPIs and `customer_facing: false` for internal-only metrics. Add a test in `tests/test_metrics.py`.

**Add a module.** Add an entry to `config/modules.json` (id, pack, page, component, required_metrics, priority_tags, industries) and a renderer for its `component` in `web/modules.js`. A module is hidden when a required metric is missing or not customer-facing, and is listed as hidden.

**Add an industry rule.** Edit `config/industry_rules.yaml`: `defaults` (default priority order per industry), `topic_map` (customer topic to priority key) and `emphasis` (the "why this view" note). Priority keys are `water, emissions, cost, circularity, service`. The observation rules R1-R8 live in `insights/rules.py`; they compare sites of one account and need at least 3 sites (R4 needs at least 2 laundries).
