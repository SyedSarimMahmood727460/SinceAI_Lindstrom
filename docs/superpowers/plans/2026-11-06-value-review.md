# Value Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-running prototype that turns the Lindström synthetic data pack into a dynamic, transparent Customer Value & Sustainability Review (dashboard + PPTX) for multi-site customers.

**Architecture:** Source adapter → validated DuckDB canonical model → metric engine (registry, per-kg allocation, low/base/high scenarios) → insight engine (rules + priority resolution) → one `ReviewModel` served by FastAPI. The static web page, the PPTX export and the AI narrator all consume that model. The AI never produces numbers: it emits placeholders that code fills, behind a guard.

**Tech Stack:** Python 3.12, pandas, openpyxl, duckdb, pydantic v2, PyYAML, FastAPI + uvicorn, python-pptx, matplotlib, anthropic SDK, pytest, httpx; frontend is vanilla JS + Chart.js (CDN).

**Spec:** `docs/specs/2026-11-06-value-review-design.md` (approved, solo scope). Section references (§) point there.

## Global Constraints

- Project root: `C:\workspace\claude\value-review`. Data pack path is read from env `VR_PACK_PATH`, default `../lindstrom_pack/Lindstrom_SinceAI2026/Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx`.
- Python 3.12; run tests with `python -m pytest`; serve with `python -m uvicorn api.main:app --port 8000`.
- Only the metric engine produces numbers. Dashboard, PPTX and AI read the `ReviewModel` (§5 P2).
- `MethodStatus` order, strongest→weakest: `MEASURED, CALCULATED, ALLOCATED, ESTIMATED`. `Provenance`: `SYNTHETIC, PUBLIC_REFERENCE, APPROVED_REAL`. A derived value takes the weakest of its inputs (§5 P3).
- Sensitivity multipliers on baseline factors: low 0.85 / base 1.00 / high 1.15. Replacements per repair: low 0.25 / base 1.0 / high 1.0 (§6.3, §7.6).
- Default baseline `B_LOCAL`; also `B_HOME`, `B_INHOUSE` with factors from the pack's `Baselines` sheet.
- Allocation is per-kg intensity: `allocated_X = row.washed_kg × laundry.X(month) / laundry.washed_kg(month)` (§7.4).
- Wearers: `max(active_wearers)` across product rows per site-month; account = Σ sites; snapshot = last month in the period (T2).
- Ratios are recomputed from summed numerator and denominator at every level. Percentages are never averaged.
- Washing savings and repair (product) savings are never summed into one figure.
- `idle_stock_value_eur` has `customer_facing: false`. It never appears in the customer view or the PPTX.
- LLM model id: `claude-sonnet-5-5`; key from env `ANTHROPIC_API_KEY`; 15 s timeout, then template fallback; env `VR_AI=off` disables AI.
- Banned phrases (case-insensitive): "carbon neutral", "net zero", "CSRD-compliant", "audited", "verified", "guaranteed".
- Disclaimer string, exact: `Prototype · synthetic data · not audited`. It appears on the web banner, every PPTX slide footer and `ReviewModel.meta.disclaimer`.
- Text is UTF-8 everywhere. Site names contain Ł, ó, ä, ö, å.
- Commit after every task. Messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A filter that leaves no rows** (e.g. Apex + product `P1004`, which Apex doesn't rent). Expect: metrics with `value=None`, observations skipped, the page and the PPTX still render "No data for this filter". No crash and no NaN in JSON. Tests: Task 4 `test_empty_filter_returns_none_values`, Task 7 `test_review_empty_filter`.
2. **A prompt that matches nothing, or names an unknown customer.** Expect: a ViewSpec with empty priorities and `interpretation_text` starting "Not recognised". The current view is unchanged. Test: Task 9 `test_intent_unrecognised`.
3. **LLM unavailable** (no key, timeout, guard rejects twice). Expect: the template narrative with `generated_by="template"`, served within the request. Test: Task 9 `test_narrate_falls_back_without_key`.
4. **Non-ASCII site names in the export and API** (Łódź, Västerås, Jyväskylä). Expect: correct characters in JSON and in PPTX text. Test: Task 8 `test_pptx_unicode_site_names`.
5. **A peer group too small or a single laundry** (R4 for Apex; any rule with fewer than 3 sites). Expect: the rule doesn't fire, and nothing breaks. Test: Task 5 `test_r4_not_fired_single_laundry`, `test_rules_need_three_sites`.

---

## File map

```
value-review/
  pyproject.toml                  deps + pytest config (Task 1)
  .gitignore                      .venv, *.duckdb, logs/, out/
  config/
    assumptions/v1.yaml           baselines, sensitivity, A001–A008, T1, T2 (Task 2)
    metrics.yaml                  metric registry (Task 3)
    industry_rules.yaml           industry defaults + topic map + emphasis text (Task 5)
    wording_rules.yaml            banned phrases (Task 9)
    modules.json                  dashboard module registry (Task 10)
    loader.py                     load_assumptions(), load_yaml()
  model/
    contracts.py                  enums, Scope, Range, Lineage, MetricResult, Observation, ViewSpec, Narrative
    validate.py                   validate_frames(), consistency_checks()
    load.py                       load_pack() → duckdb connection
    ddl.sql                       canonical tables
  adapters/
    base.py                       Adapter protocol
    excel_pack.py                 ExcelPackAdapter
    fixtures.py                   inject_bad_rows()
  metrics/
    periods.py                    period_months()
    frames.py                     base_frames() – enriched row frames from DuckDB
    engine.py                     Engine (compute, site_metrics, monthly, baseline_comparison, circularity)
  insights/
    priorities.py                 resolve_priorities()
    rules.py                      build_observations()
    discussion.py                 discussion_points(), action_rows()
  api/
    review_model.py               ReviewParams, ReviewModel
    build.py                      build_review()
    main.py                       FastAPI app + static web
  ai/
    guard.py                      check(), render()
    templates.py                  template_narrative()
    narrator.py                   narrate()
    intent.py                     keyword_intent(), parse_intent()
  export/
    charts.py                     matplotlib PNGs
    pptx_builder.py               build_pptx()
  web/  index.html  app.js  styles.css
  tests/  conftest.py + test_*.py per task
  docs/   methodology.md  data_readiness.md  demo_script.md  (Task 11)
  README.md
```

---

### Task 1: Project skeleton and contracts (S0, part 1)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `model/__init__.py` (and an empty `__init__.py` in every package dir above), `model/contracts.py`, `tests/conftest.py`, `tests/test_contracts.py`

**Interfaces:**
- Produces (in `model/contracts.py`, pydantic v2):
  - `class MethodStatus(str, Enum)`: MEASURED, CALCULATED, ALLOCATED, ESTIMATED; `def weakest(*s: MethodStatus) -> MethodStatus`
  - `class Provenance(str, Enum)`: SYNTHETIC, PUBLIC_REFERENCE, APPROVED_REAL
  - `Scope(node_id: str, level: Literal["ACCOUNT","SITE"], period: str, product: str | None = None)`
  - `Range(low: float | None, base: float | None, high: float | None)`
  - `Lineage(facts: list[str], rows: int, load_ids: list[str])`
  - `MetricResult(metric_id, label, unit, scope: Scope, value: float | None, range: Range | None, method_status, provenance, confidence: str, assumptions: list[str], lineage: Lineage, formula_text: str, priority_tags: list[str], customer_facing: bool = True, dq_warning: bool = False)`
  - `Observation(id, rule_id, title, finding, action, tags: list[str], node_id, evidence: list[tuple[str, str]], method_status, confidence, score: float = 0, z: float | None = None, dq_warning: bool = False)`
  - `ViewSpec(node_id: str | None = None, priorities: list[str] = [], baseline_id: str | None = None, sensitivity: Literal["low","base","high"] | None = None, view: str | None = None, interpretation_text: str = "")`
  - `Narrative(exec_summary: str, discussion_points: list[str], generated_by: Literal["llm","template"])`
- `tests/conftest.py` fixtures: `pack_path` (env or default; skip the test if the file is missing), `con` (session-scoped `load_pack(pack_path)`; used from Task 2 on).

- [ ] **Step 1:** `git init` in the project root; write `pyproject.toml` (deps from Tech Stack; `[tool.pytest.ini_options] testpaths=["tests"]`) and `.gitignore`. Run `python -m pip install -e .[dev]` (or `pip install` the deps list). Expected: install succeeds.
- [ ] **Step 2: Write failing tests** in `tests/test_contracts.py`:
  - `test_weakest_status`: `weakest(CALCULATED, ESTIMATED, ALLOCATED) == ESTIMATED`; `weakest(MEASURED) == MEASURED`
  - `test_metric_result_json_roundtrip_with_none`: a MetricResult with `value=None, range=None` dumps via `model_dump_json()` without "NaN" and loads back equal
- [ ] **Step 3:** Run `python -m pytest tests/test_contracts.py -v`. Expected: FAIL (import error).
- [ ] **Step 4:** Implement `model/contracts.py` as specified.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6:** Commit `feat: project skeleton and shared contracts`.

### Task 2: Ingestion, validation, consistency checks (S1)

**Files:**
- Create: `config/assumptions/v1.yaml`, `config/loader.py`, `model/ddl.sql`, `model/validate.py`, `model/load.py`, `adapters/base.py`, `adapters/excel_pack.py`, `adapters/fixtures.py`, `tests/test_ingestion.py`

**Interfaces:**
- Consumes: contracts (Task 1).
- Produces:
  - `config/loader.py`: `load_yaml(name: str) -> dict` (path relative to `config/`); `load_assumptions(version="v1") -> dict` with keys `version, baselines{B_LOCAL{name,water_l_per_kg,energy_kwh_per_kg,process_kgco2e_per_kg,delivery_kgco2e_per_kg,mixed_waste_share,note,default}}, sensitivity{low,base,high:{baseline_factor, replacements_per_repair}}, register[{id,assumption,value_or_rule,confidence,treatment}]`. Baseline values are copied from the pack's `Baselines` sheet (B_LOCAL 9.5/1.05/0.62/0.035; B_HOME 20/1.18/0.78/0; B_INHOUSE 12.5/1.12/0.68/0.015). The register holds A001–A008 verbatim from the `Assumptions` sheet, plus T1 and T2 from spec §6.3.
  - `adapters/base.py`: `class Adapter(Protocol): source_id: str; tier: int; def extract(self) -> dict[str, pd.DataFrame]; def to_canonical(self, raw) -> dict[str, pd.DataFrame]`
  - `adapters/excel_pack.py`: `ExcelPackAdapter(path: Path)`, `source_id="excel_pack"`, `tier=0`. `to_canonical` returns frames named `org_node, product, laundry, fact_service_month, fact_service_cycle, fact_repair_month, fact_laundry_month, fact_waste_month` with the columns in spec §6.1–6.2. Accounts come from `Customers` (level ACCOUNT, parent_id None); sites come from `Sites` (level SITE, parent_id = customer_id). `fact_service_cycle.month = pickup_timestamp[:7]`. `fact_waste_month` is unpivoted to `route ∈ {recycling, reuse, energy_recovery, incineration}`. Every fact row gets `method_status="CALCULATED"` for activity facts, `"ALLOCATED"` never at load, `provenance="SYNTHETIC"`, `source_id`, `load_id`.
  - `model/validate.py`: `validate_frames(frames) -> tuple[dict[str, DataFrame], DataFrame]`. The second value is quarantine, with columns `table, row_json, reason`; ERROR rules are per spec §6.4. `consistency_checks(con) -> DataFrame` with columns `check_id, severity("WARNING"), entity_type, entity_id, month, detail`, for checks C1–C3.
  - `adapters/fixtures.py`: `inject_bad_rows(frames) -> frames`. Adds exactly 3 rows to `fact_service_month`: unknown site `S999`, month `""`, `washed_kg = -5`.
  - `model/load.py`: `load_pack(path: Path, db: str = ":memory:", inject_bad: bool = False) -> duckdb.DuckDBPyConnection`. Creates the tables from `ddl.sql`, inserts the valid frames, plus `quarantine`, `dq_flags` (from `consistency_checks`) and `source(source_id, name, tier, system, approved, loaded_at, load_id)`.

- [ ] **Step 1: Write failing tests** in `tests/test_ingestion.py`:
  - `test_all_tables_loaded(con)`: the row counts equal fact_service_month 1248, fact_service_cycle 16415, fact_repair_month 3635, fact_laundry_month 48, fact_waste_month 192, org_node 37 (3 accounts + 34 sites)
  - `test_clean_pack_has_no_quarantine(con)`: `count(quarantine) == 0`
  - `test_c1_flags_l003(con)`: `dq_flags` has rows with `check_id='C1'` and `entity_id='L003'`, and none for `L001`/`L004`
  - `test_injected_rows_quarantined(pack_path)`: `load_pack(pack_path, inject_bad=True)` → quarantine count 3, with the reasons containing "unknown site", "month", "negative"
  - `test_unicode_names_preserved(con)`: the org_node name for `S024` is `"NorthStar Łódź"`
- [ ] **Step 2:** Run `python -m pytest tests/test_ingestion.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the files listed above. C1 compares, per laundry and month, Σ `fact_service_month.washed_kg` vs `fact_laundry_month.washed_kg`; it flags when the ratio is > 1.0, with the ratio in `detail`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit `feat: excel pack adapter, validation, quarantine and consistency checks`.

### Task 3: Metric engine core (S2)

**Files:**
- Create: `config/metrics.yaml`, `metrics/periods.py`, `metrics/frames.py`, `metrics/engine.py`, `tests/test_metrics.py`

**Interfaces:**
- Consumes: `load_pack`, `load_assumptions`, contracts.
- Produces:
  - `metrics/periods.py`: `period_months(period: str) -> list[str]`, where `"2025"` gives 12 months and `"2025-Q2"` gives `["2025-04","2025-05","2025-06"]`.
  - `config/metrics.yaml`: one entry per metric in spec §7.5, with keys `id, label, unit, aggregation, method_status, confidence, assumptions, priority_tags, customer_facing, formula_text`.
  - `metrics/frames.py`: `base_frames(con, account_id: str, months: list[str], product: str | None) -> dict[str, pd.DataFrame]` with keys `activity` (fact_service_month rows plus `allocated_water_l, allocated_energy_kwh, allocated_process_kg, allocated_delivery_kg, allocated_waste_kg, waste_<route>_kg, dq_warning`), `cycles`, `repairs` (joined with product footprint and cost), `sites`.
  - `metrics/engine.py`: `class Engine: __init__(self, con, assumptions: dict, registry: dict)`, and:
    - `compute(self, node_id: str, period: str = "2025", product: str | None = None, baseline_id: str = "B_LOCAL") -> dict[str, MetricResult]`. Works for ACCOUNT or SITE nodes. Ranges are always computed; `value` = the base value.
    - `site_metrics(self, account_id, period, product, baseline_id) -> dict[str, dict[str, MetricResult]]`
    - `monthly(self, account_id, metric_ids: list[str], period, product, site_id: str | None = None) -> dict[str, list[dict]]` (each item `{"month": str, "value": float | None}`)
    - `baseline_comparison(self, node_id, period, product) -> list[dict]` (`baseline_id, name, co2_saving_kg, water_saving_l, energy_saving_kwh`, base case)
    - `circularity(self, node_id, period, product) -> dict` (`repairs_by_type{}, repairs_by_month[], waste_routes{route: kg}`)
    - `laundry_stats(self, account_id, period) -> list[dict]` (`laundry_id, name, recycling_rate, site_ids[], dq_warning`)
  - Metric ids, exactly: `sites, active_wearers, active_wearers_avg, garments_allocated, utilisation, idle_pieces, idle_stock_value_eur, washed_kg, washed_kg_per_wearer, washing_pct, on_time_rate, avg_cycle_hours, service_requests, service_requests_per_100w, repairs, repairs_per_100w, replacements_postponed, postponed_product_kgco2e, allocated_water_l, allocated_energy_kwh, allocated_co2_kg, baseline_water_l, baseline_energy_kwh, baseline_co2_kg, water_saving_l, energy_saving_kwh, co2_saving_kg, footprint_pct_of_baseline_water, footprint_pct_of_baseline_co2, footprint_pct_of_baseline_energy, textile_waste_kg, recycling_rate, diverted_from_mixed_waste_kg`.
  - Rules: a metric whose inputs carry `dq_warning` gets `dq_warning=True`, and its confidence drops one level (High→Medium→Low-Med→Low). A metric with no input rows gets `value=None, range=None`.

- [ ] **Step 1: Write failing tests** in `tests/test_metrics.py` (use `engine` = `Engine(con, load_assumptions(), load_yaml("metrics.yaml"))`; NorthStar = `CUST001`, period `2025`, `B_LOCAL`):
  - `test_period_months`: the "2025" and "2025-Q2" cases above
  - `test_northstar_basics`: `sites == 24`; `washed_kg ≈ 502074.7` (abs 1); `repairs == 15233`; `service_requests == 515`
  - `test_wearers_deduplicated`: `active_wearers.value == 9607` (if the pack sum is 28367, de-duplication must not equal it)
  - `test_allocation_reconciles(con)`: per row, `allocated_water_l`, `allocated_energy_kwh`, `allocated_process_kg + allocated_delivery_kg` and `allocated_waste_kg` are within 2% relative of the pack's `Customer_Impacts` columns (read the sheet in the test as a fixture)
  - `test_savings_match_sample_output`: `water_saving_l.value` within 2% of 1406482.6; `co2_saving_kg.value` within 2% of 255073.1
  - `test_co2_range`: `co2_saving_kg.range.low ≈ 205700`, `high ≈ 304400` (rel 1%)
  - `test_ratio_rollup_not_mean`: account `utilisation` == Σ scanned / Σ allocated, and != the mean of the site utilisations
  - `test_dq_warning_propagates`: for Apex (`CUST002`), `allocated_water_l.dq_warning is True` and confidence is lowered; for Mediora (`CUST003`) it is False
  - `test_empty_filter_returns_none_values`: `compute("CUST002", product="P1004")["washed_kg"].value is None` (no exception), and `utilisation.value is None`
  - `test_idle_value_not_customer_facing`: `idle_stock_value_eur.customer_facing is False`
- [ ] **Step 2:** Run `python -m pytest tests/test_metrics.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Wearers: `groupby(site, month).active_wearers.max()`, then the last month for the snapshot and the mean of the monthly account sums for `_avg`. Savings: `washed_kg × factor × mult − allocated` for each sensitivity. `postponed_product_kgco2e = Σ repair_count × footprint × replacements_per_repair[sens]`. Recycling rate = Σ waste_recycling / Σ allocated_waste.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit `feat: metric engine with per-kg allocation, ranges and roll-ups`.

### Task 4: Scenarios, site series and filters (S3)

**Files:**
- Modify: `metrics/engine.py`
- Create: `tests/test_scenarios.py`

**Interfaces:**
- Consumes/extends Task 3's `Engine` methods (`site_metrics`, `monthly`, `baseline_comparison`, `circularity`). No new public names.

- [ ] **Step 1: Write failing tests** in `tests/test_scenarios.py`:
  - `test_baseline_switch_changes_savings`: NorthStar `co2_saving_kg` under `B_HOME` > under `B_LOCAL`; `allocated_co2_kg` is identical under both
  - `test_baseline_comparison_has_three`: 3 rows; the `B_LOCAL` row's `co2_saving_kg` equals `compute(...)["co2_saving_kg"].value`
  - `test_quarters_sum_to_year`: Σ over Q1–Q4 of `washed_kg`, `repairs` and `service_requests` == the year values
  - `test_product_filter`: NorthStar `washed_kg` with `product="P1004"` < the unfiltered value and > 0
  - `test_site_metrics_cover_all_sites`: 24 keys for NorthStar; `S022` (Gdańsk) `service_requests_per_100w ≈ 17.5` (abs 0.5)
  - `test_monthly_series`: `monthly("CUST001", ["repairs"], "2025", None)["repairs"]` has 12 items, and the values sum to 15233
- [ ] **Step 2:** Run the tests. Expected: FAIL where the behaviour is missing.
- [ ] **Step 3:** Implement whatever the failing tests need.
- [ ] **Step 4:** Run `python -m pytest -v` (the full suite). Expected: PASS.
- [ ] **Step 5:** Commit `feat: scenarios, period and product filters, site and monthly series`.

### Task 5: Insights and priority resolution (S4)

**Files:**
- Create: `config/industry_rules.yaml`, `insights/priorities.py`, `insights/rules.py`, `insights/discussion.py`, `tests/test_insights.py`

**Interfaces:**
- Consumes: `Engine` outputs (`site_metrics`, `compute`, `laundry_stats`), `dq_flags` table, contracts.
- Produces:
  - `config/industry_rules.yaml`: `defaults: {"Food & Beverage": [service, water], "Manufacturing": [cost, circularity, service], "Healthcare": [service, emissions]}`; `topic_map` per spec §9.3; `emphasis` = `dashboard_emphasis` text per industry from the `Industry_Priorities` sheet.
  - `insights/priorities.py`: `resolve_priorities(customer_topics: list[str], industry: str, chips: list[str] | None = None, prompt: list[str] | None = None) -> tuple[list[str], str]`. Returns `(ordered unique priorities, source ∈ {"prompt","chips","customer","industry"})`. Precedence is prompt > chips > customer topics + industry fill.
  - `insights/rules.py`: `build_observations(account_id: str, account_metrics: dict[str, MetricResult], site_metrics: dict[str, dict[str, MetricResult]], site_names: dict[str, str], laundry_stats: list[dict], industry: str, priorities: list[str], baseline_name: str) -> list[Observation]`. Rules R1–R8 per spec §8.2; scored per §8.3 (`weight = 10 − rank`); sorted by score desc, then |z| desc. Titles and findings use plain formatted numbers here (these are templates rendered by code, not the LLM).
  - `insights/discussion.py`: `discussion_points(obs: list[Observation]) -> list[str]` (top-4 actions + a fixed reporting question = 5 items); `action_rows(obs, account_metrics, site_metrics) -> list[dict]` (`text, owner, kpi_metric_id, value_2025, target_2026: None`; top 3; owners "KAM + site manager", "Service owner", "Lindström laundry" in order).

- [ ] **Step 1: Write failing tests** in `tests/test_insights.py`:
  - `test_default_priorities`: NorthStar topics → `(["water","service","emissions"], "customer")`; Apex → starts `["cost","circularity","service"]`; with `prompt=["emissions"]` the source is `"prompt"` and the first item is `"emissions"`
  - `test_northstar_rules`: an observation with `rule_id="R2"` has `node_id="S022"`; R1 has `node_id="S018"`; R4 exists and mentions "Vistula Warsaw WWS"
  - `test_r8_fires_for_l003_accounts`: R8 is present for CUST001 and CUST002, absent for CUST003
  - `test_r4_not_fired_single_laundry`: no R4 for CUST002
  - `test_rules_need_three_sites`: calling `build_observations` with `site_metrics` trimmed to 2 sites returns no R1/R2/R3/R5/R6 and raises nothing
  - `test_priority_changes_order`: with priorities `["cost"]`, the first observation has `"cost"` in its tags; with `["service"]`, it has `"service"`
  - `test_discussion_points_five`: `len(discussion_points(obs)) == 5`, and the last one mentions "baseline"
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Outlier: z computed against the peer sites of the account; peers need ≥ 3 sites; `|z| ≥ 1.5`, otherwise the extreme site is used with `z` set and the title suffixed "(relative)". R4 needs ≥ 2 laundries and a gap ≥ 10 pp. R7 always fires when savings are not None.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit `feat: insight rules R1-R8, priority resolution, discussion points`.

### Task 6: ReviewModel and builder (S0 part 2 + S5 core)

**Files:**
- Create: `api/review_model.py`, `api/build.py`, `tests/fixtures/review_northstar.json` (generated), `tests/test_review.py`

**Interfaces:**
- Consumes: Engine, insights, `ai.templates.template_narrative` (Task 9 provides it; until then `build.py` uses a local stub that returns `Narrative(exec_summary="", discussion_points=discussion_points(obs), generated_by="template")`).
- Produces:
  - `ReviewParams(account_id: str, period: str = "2025", product: str | None = None, baseline_id: str = "B_LOCAL", sensitivity: Literal["low","base","high"] = "base", priorities: list[str] | None = None, priority_source_hint: Literal["prompt","chips"] | None = None, site: str | None = None, audience: Literal["kam","customer"] = "kam")`
  - `ReviewModel` with the fields of spec §11.2: `meta, context, kpis, sites, trends, comparisons, circularity, observations, narrative, actions, methodology, data_quality`. `meta.run_id` = sha256 of (`load_id`, assumption version, params JSON), first 12 hex characters.
  - `build_review(con, params: ReviewParams, engine: Engine | None = None, use_ai: bool = False) -> ReviewModel`. `kpis` are ordered by priority score (same formula as observations, applied to `priority_tags`). With `audience="customer"`, every metric with `customer_facing=False` is removed everywhere.
  - Selected sensitivity: the KPI `value` = `range.<sensitivity>`.
  - `site` set → `trends` holds that site's monthly series (`active_wearers, garments_allocated, active_assets_scanned, repairs, service_requests, late_cycles`); otherwise the account's series for the same ids.
  - `data_quality`: `quarantine_count`, `warnings` (dq_flags rows that touch the account), `gaps` (static list from spec §14 data-readiness), `hidden_modules` (filled by the frontend registry, so `[]` here).

- [ ] **Step 1: Write failing tests** in `tests/test_review.py`:
  - `test_review_validates_all_combinations(con)`: for 3 accounts × 3 baselines × 3 sensitivities, `build_review` returns a model; `model_dump_json()` contains no "NaN"
  - `test_review_context_priorities(con)`: NorthStar default → `context.active_priorities[0] == "water"`, `context.priority_source == "customer"`
  - `test_customer_audience_hides_internal(con)`: with `audience="customer"`, no KPI or site metric has id `idle_stock_value_eur`
  - `test_sensitivity_selects_value(con)`: `co2_saving_kg` KPI value under `"low"` == its range.low
  - `test_run_id_stable(con)`: the same params give the same run_id; a different baseline gives a different one
  - `test_review_empty_filter(con)`: Apex + `P1004` builds without error; `observations == []` except R8
  - `test_disclaimer(con)`: `meta.disclaimer == "Prototype · synthetic data · not audited"`
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Then generate `tests/fixtures/review_northstar.json` from `build_review` and commit it (the frontend and export use it for offline work).
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit `feat: ReviewModel and review builder`.

### Task 7: FastAPI service (S5)

**Files:**
- Create: `api/main.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `load_pack` (once at startup, path from `VR_PACK_PATH`), `build_review`, `Engine`, `ai.intent.parse_intent` (Task 9; until then, a route that returns `ViewSpec(interpretation_text="Not recognised")`), `export.pptx_builder.build_pptx` (Task 8).
- Produces the routes of spec §11.1, exactly:
  - `GET /accounts` → `[{node_id, name, industry, site_count}]`
  - `GET /accounts/{id}/review` with query `period, product, baseline, sens, priorities` (comma-separated), `site`, `audience` → ReviewModel JSON; unknown id → 404
  - `POST /intent {text}` → ViewSpec
  - `GET /metrics/{metric_id}/explain?node_id=&period=&baseline=` → `{definition (registry entry), result: MetricResult, assumptions: [register entries]}`
  - `POST /reviews/export {params…, format: "pptx"}` → file response, `application/vnd.openxmlformats-officedocument.presentationml.presentation`
  - `GET /data-quality?account_id=` → `{sources, quarantine: [...], warnings: [...]}`
  - `GET /config/assumptions` → the active assumption set
  - `GET /config/modules` → `config/modules.json`
  - Static: `/` serves `web/index.html`; `/web/*` serves files

- [ ] **Step 1: Write failing tests** in `tests/test_api.py` with `fastapi.testclient.TestClient`:
  - `test_accounts`: 3 items; NorthStar `site_count == 24`
  - `test_review_endpoint`: 200; `meta.node.name == "NorthStar Foods Group"`; the query `baseline=B_HOME` is reflected in `meta.baseline.id`
  - `test_review_unknown_account`: 404
  - `test_explain`: `/metrics/co2_saving_kg/explain?node_id=CUST001` → has `formula_text` and assumptions including `A003`
  - `test_data_quality`: the warnings for CUST002 include C1 / L003
  - `test_root_serves_html`: `GET /` → 200, and the content-type contains `text/html`
  - `test_review_unicode`: the response text contains `"Łódź"` unescaped (use `JSONResponse` with `ensure_ascii=False`, or pydantic's default)
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS. Then start the server manually and check `curl http://127.0.0.1:8000/accounts`.
- [ ] **Step 5:** Commit `feat: FastAPI review service`.

### Task 8: PPTX export (S8)

**Files:**
- Create: `export/charts.py`, `export/pptx_builder.py`, `tests/test_export.py`

**Interfaces:**
- Consumes: `ReviewModel`.
- Produces: `build_pptx(review: ReviewModel, out_path: Path) -> Path`; `charts.footprint_pct_chart(review) -> Path`, `charts.repairs_by_month_chart(review) -> Path` (PNG files in a temp dir).
- Slides in order (spec §13): Cover · Executive summary · Value KPIs (top 8, with method_status labels) · Footprint vs baseline (% chart + range text) · Site highlights (top/bottom 5 by the first-priority rank metric) · Observations & next steps (top 5) · Discussion points + actions · Methodology, assumptions & limitations · Appendix: data readiness (warnings + gaps).
- Every slide has the footer `Prototype · synthetic data · not audited · run {run_id}`. Each KPI shows `[STATUS]` next to it, and a ⚠ for `dq_warning`. Built from a blank 16:9 presentation, with the red accent `#D71920` and navy `#1B2A4A`.

- [ ] **Step 1: Write failing tests** in `tests/test_export.py`:
  - `test_pptx_has_nine_slides`: built from the NorthStar review → 9 slides
  - `test_pptx_numbers_match_review`: the KPI slide text contains the formatted `co2_saving_kg` value from the same ReviewModel (use the same `fmt` helper the builder uses: `export.pptx_builder.fmt_value(metric) -> str`)
  - `test_pptx_footer_on_every_slide`: each slide's text contains `Prototype · synthetic data · not audited`
  - `test_pptx_unicode_site_names`: the site highlights or appendix contain `"Łódź"` or `"Västerås"`, correctly encoded (read back with python-pptx)
  - `test_pptx_customer_audience`: with an audience=customer review, the text never contains "idle stock"
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement; wire the `/reviews/export` route (Task 7) to it.
- [ ] **Step 4:** Run the full suite. Expected: PASS. Open the generated `out/review_CUST001.pptx` in PowerPoint and check by eye that nothing overflows a slide.
- [ ] **Step 5:** Commit `feat: customer-ready PPTX export`.

### Task 9: AI layer: guard, templates, narrator, intent (S7)

**Files:**
- Create: `config/wording_rules.yaml`, `ai/guard.py`, `ai/templates.py`, `ai/narrator.py`, `ai/intent.py`, `tests/test_ai.py`
- Modify: `api/build.py` (use `narrate`), `api/main.py` (use `parse_intent`)

**Interfaces:**
- Produces:
  - `ai/guard.py`: `check(text: str, allowed: set[str], banned: list[str]) -> list[str]` returns violations: any digit outside `{{…}}`, an unknown placeholder, or a banned phrase. `render(text: str, values: dict[str, str]) -> str` replaces each `{{key}}`.
  - `ai/templates.py`: `placeholder_values(review) -> dict[str, str]` (keys like `co2_saving_kg.base`, `co2_saving_kg.low`, `co2_saving_kg.high`, `water_saving_l.base`, `active_wearers.base`, `sites.base`, `on_time_rate.base`, `repairs.base`, `baseline.name`, `account.name`; formatted with units). `template_narrative(review) -> Narrative`, which writes the executive summary from the placeholders in the mockup's wording, then renders it.
  - `ai/narrator.py`: `narrate(review, use_llm: bool) -> Narrative`. With an LLM: system prompt = role + rules (placeholders only, no digits, banned list, ≤ 120 words, 5 discussion points), and the input = a JSON of KPI ids/labels/tags + observation titles/actions (titles have digits stripped and replaced with placeholders `{{obs:<id>}}`, resolved by code). The output is guard-checked; retry once; otherwise template. The result is logged to `logs/{run_id}.json`.
  - `ai/intent.py`: `keyword_intent(text: str, accounts: list[dict], baselines: dict) -> ViewSpec` (the mockup's keyword logic: priority keyword lists, customer first-word match, baseline name match, view routing on "steer|discussion", "compare|baseline", "which site|outlier", "improve|next year"). `parse_intent(text, accounts, baselines, use_llm: bool) -> ViewSpec`: Claude tool use with the ViewSpec JSON schema; unknown ids are dropped; falls back to `keyword_intent` on error or when `use_llm` is False.
  - `use_llm` = `os.environ.get("VR_AI","on") != "off" and "ANTHROPIC_API_KEY" in os.environ`.

- [ ] **Step 1: Write failing tests** in `tests/test_ai.py` (no network; the LLM is mocked with `monkeypatch`):
  - `test_guard_rejects_digits`: `check("Saved 255 t", set(), [])` is not empty; `check("Saved {{co2_saving_kg.base}}", {"co2_saving_kg.base"}, [])` is empty
  - `test_guard_rejects_banned`: "We are carbon neutral" → a violation
  - `test_guard_rejects_unknown_placeholder`: `{{made_up}}` → a violation
  - `test_template_narrative_contains_real_numbers(review)`: the summary contains the formatted `co2_saving_kg` base from `placeholder_values`; `generated_by == "template"`
  - `test_narrate_falls_back_without_key(monkeypatch, review)`: with no `ANTHROPIC_API_KEY` → `generated_by == "template"`
  - `test_narrate_uses_llm_when_guard_passes(monkeypatch, review)`: a mocked client returns text with valid placeholders → `generated_by == "llm"`, and the rendered text has no `{{`
  - `test_narrate_rejects_llm_digits(monkeypatch, review)`: the mock returns "Saved 999 t" twice → template
  - `test_intent_keywords`: "Focus on water and emissions, compare with home washing" → priorities `["water","emissions"]`, baseline `B_HOME`, view `footprint`
  - `test_intent_customer`: "Prepare five discussion points for Apex" → node_id `CUST002`, view `steering`
  - `test_intent_unrecognised`: "hello there" → priorities `[]`, `interpretation_text` starts with "Not recognised"
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement; switch `build.py` and `main.py` to the real functions.
- [ ] **Step 4:** Run the full suite. Expected: PASS. If a key is available, manual check: `VR_AI=on`, request the NorthStar review, and confirm `narrative.generated_by == "llm"` and that the summary reads well.
- [ ] **Step 5:** Commit `feat: guarded AI narrator and intent parser with template fallback`.

### Task 10: Frontend on the live API (S6)

**Files:**
- Create: `web/index.html`, `web/app.js`, `web/styles.css`, `config/modules.json`
- Source to port: `C:\workspace\claude\lindstrom_mockup\index.html` (layout, styles, drawer, charts, pages). Remove its in-browser calculations: every number now comes from the API.

**Interfaces:**
- Consumes: the API routes from Task 7, the ReviewModel shape from Task 6.
- `config/modules.json`: a list of `{id, pack: "general"|"sustainable"|"financial", page, required_metrics[], priority_tags[], industries: ["*"] | [...], component}`. Components: `kpi_row, observations, site_rank, site_table, site_detail, footprint_cards, footprint_pct_chart, baseline_compare_chart, repairs_month_chart, repairs_type_chart, waste_routes_chart, exec_summary, discussion_points, action_table, methodology, assumption_table, data_quality, readiness_table`.
- Behaviour in `app.js`:
  - State: `{account, period, product, baseline, sens, priorities, prioritySource, audience, view}`. Any change → `GET /accounts/{id}/review?...` → render.
  - Header: customer, period (2025, Q1–Q4), product (All + the products present in the review's sites), baseline, sensitivity, audience toggle (KAM/Customer), Export (POST `/reviews/export`, download), prompt bar → `POST /intent` → apply the ViewSpec → show `interpretation_text`; priority chips; suggested-prompt chips (the 6 from the pack's `Suggested_Prompts`, hardcoded).
  - Module registry: a module renders only if all its `required_metrics` are present with `value !== null` and the industry matches. Otherwise it is listed in a "Hidden: missing data" note on the Data readiness page. Modules on a page are sorted by priority score.
  - Every KPI shows the method_status badge, a SYN marker for provenance SYNTHETIC, the range for ESTIMATED, and ⚠ for `dq_warning`. A click opens the drawer from `/metrics/{id}/explain`.
  - Observations show "Show evidence & formula" → a drawer with the evidence metrics for the site vs the account.
  - The Sites page: a sortable table with outlier dots (`|z| ≥ 1.5` computed client-side from the `sites` values is allowed: display only). A row click → site detail using `trends`, plus a `GET` of the review with `site=` for per-site trends.
  - The Data readiness page: the warnings (C1 shown prominently: "Laundry volume inconsistency: L003 …"), quarantine count, gaps table, hidden modules.
  - Empty filter → each module shows "No data for this filter".

- [ ] **Step 1:** Write `config/modules.json`, and add `test_modules_reference_known_metrics` to `tests/test_api.py`: every `required_metrics` id exists in `config/metrics.yaml`. Run it. Expected: FAIL, then PASS once the file is correct.
- [ ] **Step 2:** Port the layout and styles; implement `app.js` as specified.
- [ ] **Step 3: Verify in the browser** (`python -m uvicorn api.main:app --port 8000`, open `http://127.0.0.1:8000`) by running the demo script (spec §2):
  1. NorthStar opens with the Water chip active first.
  2. The prompt "Focus on water and emissions" reorders the KPIs.
  3. The Gdańsk drill-down shows the trends.
  4. B_HOME changes the savings.
  5. The Steering page shows 5 points.
  6. Export downloads a PPTX.
  7. Apex opens with Cost first and shows ⚠ on the allocated metrics.
  8. Apex + P1004 shows "No data for this filter".
  9. The Customer audience hides idle stock.
  The browser console must show no errors.
- [ ] **Step 4:** Commit `feat: dashboard frontend on live API with module registry`.

### Task 11: Documentation, demo data toggle, submission (S9–S10)

**Files:**
- Create: `README.md`, `docs/methodology.md`, `docs/data_readiness.md`, `docs/demo_script.md`, `docs/architecture.png` (export of the three agreed diagrams, or Mermaid in markdown)
- Modify: `api/main.py` to add env `VR_INJECT_BAD_ROWS=1` → `load_pack(..., inject_bad=True)` (demo of quarantine)

- [ ] **Step 1:** `docs/methodology.md` covers spec §14: baselines with factors, boundary, footprint vs handprint, the per-kg allocation, sensitivity T1, repair range, wearer de-duplication T2, the C1 finding, limitations, and the "not audited" statement.
- [ ] **Step 2:** `docs/data_readiness.md`: the field → future source → status/gap table (from the mockup's Data readiness page) + the Tier 0–3 roadmap + Q35.
- [ ] **Step 3:** `README.md`: setup (`pip install -e .`), env vars (`VR_PACK_PATH, ANTHROPIC_API_KEY, VR_AI, VR_INJECT_BAD_ROWS`), run, test, the architecture diagram, and "how to add an adapter / metric / module / industry rule" (one paragraph each, pointing at the files).
- [ ] **Step 4:** `docs/demo_script.md`: a 4-minute script following the Task 10 step 3 sequence, with talking points per criterion (Value 25, Completeness 20, Credibility 20, Data 15, Usability 10, Scalability 10).
- [ ] **Step 5:** Fresh-clone check: clone to a temp dir, install, `python -m pytest`. Expected: all pass. Start the server; the demo works.
- [ ] **Step 6:** Commit `docs: methodology, data readiness, README, demo script`.
- [ ] **Step 7 (user):** Record the ≤ 4-min video; push the repo; make the source .zip; accept the IP terms; submit in sinceai.app before **Sun 10:00 EET**.

---

## Timeline mapping (spec §16)

**Execution order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 10 → 8 → 9 → 11. The frontend comes before export and AI, matching the spec's solo sequence; Tasks 7 and 6 use the stubs noted in their Interfaces until 8 and 9 land.


Task 1 → Fri 23:30 (with part of 2) · Task 2 → Sat 10:00 · Task 3 → Sat 12:30 · Task 4 → Sat 14:00 · Task 5 → Sat 15:30 · Tasks 6–7 → Sat 16:30 · Task 10 → Sat 19:30 · Task 8 → Sat 21:30 · Task 9 → Sat 23:00 **freeze** · Task 11 → Sun 07:30–09:30.
If behind schedule, follow the spec §16 cut order. Task 9's `parse_intent` LLM path and the narrator LLM path are the first AI pieces to drop; `keyword_intent` and `template_narrative` stay.
