# Value Review

Value Review is a prototype Customer Value & Sustainability Review generator for the Lindström × Since AI 2026 challenge. It turns multi-site service, laundry, repair and waste data into a dynamic review that a key account manager (KAM) can tailor to a customer's priorities, explain in plain language and export as PowerPoint, PDF or Excel.

**Status: prototype. All data is synthetic (the Lindström × Since AI data pack, plus a synthetic extension pack). Nothing here is audited.** The disclaimer `Prototype · synthetic data · not audited` is shown in the web strip under the header, on every PPTX slide and PDF page, in the Excel Summary sheet, on every pitch-deck slide and in `ReviewModel.meta.disclaimer`.

What it does:

- **Guided meeting** (the landing page): five steps, each with one message, two or three big numbers in one compact style (`€1.96M`, `255 t CO₂e`, `1,152 h`) with the range on a second line, and a "What to say" line for the KAM: **1 What you got · 2 Vs doing it yourself · 3 Where to improve · 4 Grow together · 5 Agree next steps**. The header keeps Customer, Period and Compare-with in view; **Ask** (prompt and chips), **Settings** (product, service line, sensitivity, audience, detail) and **Export** sit beside them. Navigation: Meeting · Before the meeting (Account intelligence, KAM only) · Detail · Trust. A KAM-only **Load demo scenario** button on steps 2 and 4 fills example numbers so neither step opens empty: a contract price of 60% of the account's full-year, unfiltered, base-case do-it-yourself total against local laundry, rounded to €10,000, so it is the same whichever quarter, filter, baseline or sensitivity is on screen (NorthStar: €1,170,000, "About €788k less with Lindström"), 4 more sites and the Mats service (Washroom if the account already uses Mats). It merges with any stored inputs; **Reset to defaults** (step 2, Your numbers) clears the do-it-yourself inputs and the contract price, and **Clear** (step 4) clears the growth inputs. The customer audience shows no edit controls, no What to say coaching, no Account intelligence and no internal metrics. A **Simple / Expert** toggle (default Simple) hides or shows status badges, z-scores, formulas and lineage. Glossary tooltips explain terms such as baseline, allocation, Scope 3 and utilisation.
- Dashboard with customer-level totals and site drill-down, filters for period (2025 or a quarter), product, service line, baseline (local laundry, home washing, in-house laundry), sensitivity (low/base/high) and audience (KAM or customer).
- **Service vs do-it-yourself**: cost, convenience and environment against the selected alternative. The KAM can overwrite the defaults ("Your numbers", assumptions T4–T11) and type the contract price. The net comparison appears only when a contract price is entered.
- **Growth opportunities**: the extra value if the customer adds more sites, more employees or a service line it does not use yet, sized from the customer's own data and the service catalogue.
- **Account intelligence**: sourced public research on a real company (Claude with web search). Every claim carries a source and a date. A committed Fazer Group snapshot works without an API key.
- **Built on Lindström's work**: a page that maps each part of the solution to a Lindström asset and to the brief line it answers (`config/lindstrom_fit.yaml`).
- Personalisation: a typed prompt, priority chips, the customer's stated priority topics and industry rules decide what is shown first.
- Observations with evidence, discussion points and an action table for a steering committee.
- Every figure carries a method status (MEASURED / CALCULATED / ALLOCATED / ESTIMATED), a provenance (SYNTHETIC / PUBLIC_REFERENCE / APPROVED_REAL), a low/base/high range for estimated values, and a "how calculated" drawer.
- Exports to **PowerPoint, PDF and Excel**, all built from the same `ReviewModel` as the dashboard, so they cannot disagree.
- A data-quality view: quarantine, and a cross-source consistency warning (C1) that the pack fails for laundry L003.
- **Grows without code changes**: a second source (a CSV extension pack) adds a hotel chain, a new industry (Hospitality), a new country (Estonia) and a new service line (Mats) through data and config only.
- AI is optional and guarded. It never writes numbers. The app works fully with no API key.

## Quick start (Windows)

Requires Python 3.12.

**The data pack is not in this repository.** By default the server looks for it at `../lindstrom_pack/Lindstrom_SinceAI2026/Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx`, relative to the repository root (so next to the `value-review` folder). If it lives elsewhere, point `VR_PACK_PATH` at the `.xlsx` file as below. If the file is missing, the server stops at start-up with an error naming `VR_PACK_PATH`.

```bat
cd value-review
python -m pip install -e ".[dev]"
set VR_PACK_PATH=C:\path\to\Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx
python -m uvicorn api.main:app --port 8000
```

Then open http://127.0.0.1:8000.

Without `-e .`, install the dependencies directly: `pandas openpyxl duckdb "pydantic>=2" PyYAML fastapi uvicorn python-pptx matplotlib "anthropic>=2.6,<3" httpx reportlab` (plus `pytest pypdf` for tests). New in this round: `reportlab` (server-side PDF export in pure Python, so no Office or LibreOffice is needed), `anthropic>=2.6` (account intelligence), `pypdf` (tests and the pitch-deck script only). `openpyxl` now also writes the Excel export.

The `pip install` line is quoted so it works in cmd, PowerShell and bash. PowerShell: `$env:VR_PACK_PATH = "C:\path\to\pack.xlsx"`. Bash: `export VR_PACK_PATH=...`.

The pack is loaded into an in-memory DuckDB at server start (a few seconds). A relative `VR_PACK_PATH` is resolved against the repository root.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `VR_PACK_PATH` | `../lindstrom_pack/Lindstrom_SinceAI2026/Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx` (relative to the repo root) | Path to the Excel data pack (the `excel_pack` entry in `config/sources.yaml`). |
| `VR_EXTENSIONS` | `on` | `VR_EXTENSIONS=off` disables the extension pack (its `toggle_env` in `config/sources.yaml`): 3 customers instead of 4, for a before/after demo. The test suite runs with it off (`tests/conftest.py`); extension tests switch it on. |
| `VR_INPUTS_DIR` | `data/kam_inputs/` (gitignored) | Where the account manager's inputs ("Your numbers" and the growth scenario) are stored, one JSON file per account. Tests and the pitch-deck script point it at a temp dir. |
| `VR_CONFIG_DIR` | `config/` | Alternative config directory (used by the extensibility test). |
| `ANTHROPIC_API_KEY` | unset | Enables the LLM intent parser and narrator (model `claude-sonnet-5-5`, 15 s timeout) and live account intelligence (web search, 60 s timeout). Without a key: keyword parser, template narrative and the committed intel snapshot. After an LLM error or timeout the narrator uses the template for 120 s without retrying. Leave `ANTHROPIC_API_KEY` unset unless the demo machine is reliably online. |
| `VR_INTEL_CACHE_DIR` | `data/intel_cache/` | Where account intelligence caches live research results, one file per company. Tests point it at a temp dir. |
| `VR_AI` | `on` | `VR_AI=off` disables all LLM calls even when a key is set. |
| `VR_INJECT_BAD_ROWS` | unset | `VR_INJECT_BAD_ROWS=1` injects 3 bad rows (unknown site, empty month, negative kg) at load time to demo the quarantine in the Data readiness view. |
| `VR_LOG_DIR` | `logs/` in the repo root | Where the narrator writes one JSON log per `run_id` (prompt, output, guard violations, `generated_by`) and account intelligence logs each live call. Only written when the LLM path runs. |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/accounts` | Customers with industry and site count (4 with the extension pack, 3 with `VR_EXTENSIONS=off`). |
| GET | `/accounts/{id}/review?period=&product=&service_line=&baseline=&sens=&priorities=&hint=&site=&audience=` | One `ReviewModel` (KPIs, sites, observations, narrative, `dto`, `growth`, `story`, methodology, data quality). `audience=customer` hides non-customer-facing metrics. |
| GET | `/accounts/{id}/inputs` (`?include=growth`) | The effective "Your numbers": each input with value, low, high, unit, source (`default` or `kam`), date entered and assumption id. `include=growth` adds the stored growth scenario. |
| PUT | `/accounts/{id}/inputs` | Replace the account's entered inputs: the DIY keys (and `<key>_low` / `<key>_high`), `contract_price_eur_per_year`, `extra_sites`, `extra_wearers`, `extra_service_lines`, `expansion_price_eur_per_site_year`. Returns 422 for unknown keys, non-numbers, negatives or low > high. No auth in the prototype. |
| POST | `/intent` `{text}` | Prompt to `ViewSpec`. |
| POST | `/intel` `{company, website?, prefer_snapshot?}` | Account intelligence report: live (cached for 7 days) or the committed snapshot. `prefer_snapshot` returns a committed snapshot without a model call. 503 when no live research is possible and there is no snapshot. |
| GET | `/intel/snapshots` | The committed snapshots (Fazer Group). |
| GET | `/metrics/{metric_id}/explain?node_id=` | Definition, formula, assumptions, lineage. |
| POST | `/reviews/export` | Same params as the review plus `format`: `pptx`, `pdf` or `xlsx`. Returns the file `review_{account}_{period}.{ext}`; the KAM Excel file is suffixed `_internal`. |
| GET | `/data-quality?account_id=` | Sources, quarantine rows, warnings for that account. |
| GET | `/config/assumptions`, `/config/modules`, `/config/glossary` | Active assumption set (including `dto_inputs`), module registry, glossary terms. |
| GET | `/config/service-catalogue` | Lindström service lines used by growth and intel (illustrative sizing defaults T12–T16). |
| GET | `/config/fit` | The "Built on Lindström's work" content. |
| GET | `/config/internal-metrics` | Metric ids that are never customer-facing. |

### Exports

In the app: **Export ▾** → PowerPoint · PDF · Excel.

| Format | Content |
|---|---|
| PowerPoint | Cover, then the five meeting steps (What you got, Vs doing it yourself, Where to improve, Grow together when a scenario is entered, Next steps), then an appendix: value KPIs, footprint, site highlights, methodology and assumptions, data readiness. Coaching lines are in the speaker notes only. |
| PDF | The same sections, rendered server-side with reportlab. It uses DejaVu Sans so that Ł, ó, ä, ö, å and õ render. Same charts; footer with the disclaimer and run id. |
| Excel | `Meeting` (the five steps), `Summary` (meta, baseline, sensitivity, priorities, audience, disclaimer), `Story`, `KPIs` (value, low, base, high, status, provenance, confidence, assumptions, formula), `Sites`, `Observations`, `Actions`, `DIY comparison`, `Growth` (when a scenario is entered), `Inputs`, `Assumptions`, `Data quality`. Numbers are stored as numbers, with units in the headers. |

All three respect the audience: the customer version contains no internal-only metric (for example idle stock value).

### Pitch deck

`docs/pitch/ValueReview_pitch.pptx` (8 slides, 16:9) is generated by `python scripts/make_pitch_deck.py`. Every figure in it comes from `build_review` and the shared formatters in `export/format.py`. The demo scenario (an example contract price and a growth scenario) is written to a temp `VR_INPUTS_DIR`, never into the repository. Slide 3 describes the five-step meeting with the demo-scenario figures. Slide 5 uses the committed Fazer snapshot with its sources. The speaker notes carry the talk track.

## Tests

```bat
python -m pytest -q -W error
```

Tests that need the data pack are skipped when the pack is not found (see `VR_PACK_PATH`).

## Architecture

Full diagrams (layered overview, request flow, data model) are in [docs/architecture.md](docs/architecture.md).

```
Sources (Tier 0 pack + CSV extension pack · Tier 1 BI/eLindström exports · Tier 2 warehouse)
  → Source adapters, listed in config/sources.yaml (extract, map, validate; quarantine)
  → Canonical model (DuckDB)      ← Config store (assumption set, metrics, rules, catalogue)
  → Metric engine (incl. do-it-yourself and growth) → Insight engine (rules, story)
  → Review API (one ReviewModel) ↔ AI layer (intent parser, narrator, account intelligence)
  → Web dashboard · PowerPoint / PDF / Excel export · (future) eLindström embed
```

Principles: the data contract is the centre; only the metric engine produces numbers; every value has a method status and a provenance (a derived value takes the weakest of its inputs); configuration over code; the AI is optional and guarded.

## Repository layout

```
adapters/   base.py (Adapter protocol), canonical.py (pack-shaped sheets -> canonical frames),
            excel_pack.py (Tier 0 pack), csv_pack.py (generic CSV pack), fixtures.py (bad-row injection)
model/      ddl.sql, contracts.py, load.py (load_sources over config/sources.yaml),
            validate.py (ERROR rules, C1-C3), inputs_store.py (account-manager inputs)
config/     sources.yaml, assumptions/v1.yaml (incl. dto_inputs), metrics.yaml, industry_rules.yaml,
            service_catalogue.yaml, relatable.yaml, glossary.yaml, lindstrom_fit.yaml,
            review_text.yaml, wording_rules.yaml, modules.json, loader.py
metrics/    engine.py (all calculations), dto.py (service vs do-it-yourself), growth.py (growth levers),
            frames.py (per-kg allocation), periods.py
insights/   rules.py (R1-R8), priorities.py, discussion.py, story.py (customer story cards)
ai/         intent.py, narrator.py, guard.py, templates.py, llm.py, intel.py (account intelligence)
api/        main.py (routes), build.py (assembles ReviewModel), review_model.py
export/     format.py (the one number formatter), sections.py (shared wording),
            pptx_builder.py, pdf_builder.py, xlsx_builder.py, charts.py
data/       extension_pack/ (synthetic CSV pack), intel_snapshots/ (committed Fazer snapshot)
scripts/    make_extension_pack.py, make_pitch_deck.py
web/        index.html, app.js, modules.js, styles.css (static SPA served at /)
tests/      pytest suite incl. reconciliation against the pack's reference sheets
docs/       methodology.md, data_readiness.md, demo_script.md, architecture.md, pitch/, specs/
```

## Documentation

- [Methodology note](docs/methodology.md): baselines, boundary, allocation, sensitivity, repair range, wearer de-duplication, the L003 finding, the service vs do-it-yourself and growth formulas, inputs T3–T16, relatable comparisons, the AI intel guardrails, limitations.
- [Data readiness note](docs/data_readiness.md): field to future source to gap table (including service line and industry master data, contract prices and CRM legal names), Tier 0–3 roadmap, how to add an adapter.
- [Demo script](docs/demo_script.md): 4-minute walkthrough of the five-step meeting (load the demo scenario, steps 1–5, export, Expert, built on Lindström's work) with exact clicks and talking points per judging criterion.
- [Pitch deck](docs/pitch/ValueReview_pitch.pptx): 8 slides, generated by `scripts/make_pitch_deck.py`.
- [Architecture](docs/architecture.md): three Mermaid diagrams.
- Design specs: [base](docs/specs/2026-11-06-value-review-design.md), [extensions](docs/specs/2026-11-07-extensions-design.md).

## Extending

### Worked example: a hotel chain in Estonia with a new service line

The extension pack shows the whole change Lindström would make to add a service line (**Mats**), an industry (**Hospitality**), a customer (**Baltic Harbour Hotels**, 5 hotels) and a country (**Estonia**). No engine, insight, UI or export code changes for it.

1. **Register the source** in `config/sources.yaml` (one line):

   ```yaml
   sources:
     - {id: excel_pack, adapter: excel, path: "${VR_PACK_PATH}", enabled: true}
     - {id: extension_pack, adapter: csv, path: data/extension_pack, enabled: true, toggle_env: VR_EXTENSIONS}
   ```

   `adapter: csv` is the generic CSV adapter (`adapters/csv_pack.py`): a folder of CSV files shaped like the pack's sheets. `toggle_env` lets `VR_EXTENSIONS=off` switch it off.

2. **Add the data** to the folder `data/extension_pack/` (synthetic; regenerate with `python scripts/make_extension_pack.py --out data/extension_pack`): `customers.csv`, `sites.csv`, `products.csv` (P2001 Entrance Mat Standard and P2002 Logo Mat, `service_line = Mats`), `service_activity.csv`, `service_cycles.csv`, `repairs.csv`. Optional files: `laundries.csv`, `laundry_resources.csv`, `waste.csv`. Ids must be unique across sources: a duplicate goes to quarantine and the first source wins. The hotels are served by laundry L002 and stay below its own volume, so check C1 still flags only L003.

3. **Add the industry rule** in `config/industry_rules.yaml`: a default priority order (`"Hospitality": [service, cost, water]`), the emphasis note, and a topic-map entry for a new customer topic ("Guest experience" → service).

Result with the default config: `/accounts` lists 4 customers. Baltic Harbour Hotels opens with the Hospitality priorities, 5 sites in Finland and Estonia, and the service-line filter offers Mats and Workwear. NorthStar, Apex and Mediora figures do not change. A Mats-only filter shows "No data for this filter" for wearer-based metrics (mats have no wearers); this is expected. Mats use the workwear per-kg baseline factors (assumption T3, confidence Low).

**The proof that it needs no code:** `tests/test_extensibility.py` writes a third CSV pack into a temp folder: service line **Washroom**, industry **Restaurants**, two customers in **Latvia** with their own Riga laundry, plus Washroom rows for NorthStar. It registers the pack in a temp `sources.yaml`, adds the Restaurants rule to a temp config, and asserts that the customers load, their reviews build, the filter lists Washroom, the industry defaults apply, nothing is quarantined and C1 still flags only L003.

To offer a service line in growth sizing and account intelligence, add an entry to `config/service_catalogue.yaml` (typical kg per site per month and price per kg, each with default/low/high, and an assumption id).

### Other extension points

**Add an adapter.** Implement the `Adapter` protocol in `adapters/base.py` (`source_id`, `tier`, `extract()`, `to_canonical()`), modelled on `adapters/excel_pack.py` or `adapters/csv_pack.py`. `to_canonical` must return the canonical frames named in `model/load.py` (`TABLES`) and tag fact rows with `method_status`, `provenance`, `source_id`, `load_id`. Register the new adapter type once in `model/load.py`, then list sources of that type in `config/sources.yaml`. Validation, quarantine and C1–C3 run over the union of all sources. See [data_readiness.md](docs/data_readiness.md).

**Add a metric.** Add an entry to `config/metrics.yaml` (id, label, unit, aggregation, method_status, confidence, assumptions, priority_tags, customer_facing, formula_text, inputs). Compute its value in `metrics/engine.py` (`_values`); if it depends on sensitivity add its id to `SENSITIVE`. Set `headline: true` to sort it among the headline KPIs and `customer_facing: false` for internal-only metrics. Add a test in `tests/test_metrics.py`.

**Add a module.** Add an entry to `config/modules.json` (id, pack, page, component, required_metrics, priority_tags, industries) and a renderer for its `component` in `web/modules.js`. A module is hidden when a required metric is missing or not customer-facing, and is listed as hidden.

**Add an industry rule.** Edit `config/industry_rules.yaml`: `defaults` (default priority order per industry), `topic_map` (customer topic to priority key) and `emphasis` (the "why this view" note). Priority keys are `water, emissions, cost, circularity, service`. The observation rules R1–R8 live in `insights/rules.py`; R1–R3 and R5–R6 compare sites of one account and need at least 3 sites; R4 needs at least 2 laundries; R7 needs a saving to report; R8 is account-level (it fires when an input laundry carries a consistency warning).

**Add a relatable comparison or a glossary term.** Edit `config/relatable.yaml` (metric, factor, label, derivation, source URL) or `config/glossary.yaml`.
