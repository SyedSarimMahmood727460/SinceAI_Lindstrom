# Value Review Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (Round 3: also story landing + simple mode, growth opportunities, AI account intelligence.) Show Lindström judges that the solution (1) builds on their existing work, (2) extends to new service lines, industries, sites and countries without code changes, (3) exports PPTX/PDF/Excel, and (4) compares Lindström's service with do-it-yourself on cost, convenience and environment, using account-manager inputs over defaults.

**Architecture:** Generalise loading to a list of configured adapters (Excel pack + CSV extension packs). Add a service-line filter through engine → review → API → UI. Add a deterministic DIY-comparison module (`metrics/dto.py`) fed by validated, per-account stored inputs over config defaults. Add PDF (reportlab) and Excel (openpyxl) builders beside the PPTX builder, all rendering one ReviewModel. Static content (fit page, pitch deck) is config/script driven.

**Tech Stack:** existing (Python 3.12, pandas, duckdb, pydantic v2, FastAPI, python-pptx, matplotlib, openpyxl, vanilla JS) + **reportlab** (PDF) + **pypdf** (dev, PDF text checks in tests).

**Spec:** `docs/specs/2026-11-07-extensions-design.md` (approved; §9a and §8a.4 decisions override earlier text in that doc). Base spec: `docs/specs/2026-11-06-value-review-design.md`.

## Global Constraints

- Branch `extensions` from `main` @ 5fa9ccc. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Only the engine produces numbers. Exports, UI and pitch deck render ReviewModel values via the existing `export.pptx_builder.fmt_value` family (or a shared extraction of it).
- Disclaimer `Prototype · synthetic data · not audited` on every export page/slide and in the PDF/xlsx Summary.
- `audience="customer"` → no `customer_facing: false` metric anywhere (UI, PPTX, PDF, xlsx). DTO inputs are shown read-only to customers.
- NorthStar (CUST001), Apex (CUST002) and Mediora (CUST003) figures must not change: the extension pack adds no rows for them.
- The existing test suite runs with `VR_EXTENSIONS=off` (set in `tests/conftest.py`). New extension tests enable it explicitly.
- Extension data is SYNTHETIC. The hotel is served by L002, with monthly volume ≤ 15,000 kg (L002 washes 78–95 t/month), so the C1 check still flags only L003.
- New assumptions: T3 = Mats use workwear per-kg baseline factors (confidence Low); T4–T11 = DTO inputs in this order: local_laundry_eur_per_kg, energy_eur_per_kwh, water_eur_per_m3, detergent_eur_per_kg, labour_eur_per_h, handling_min_per_kg, admin_h_per_site_month, garment_life_years_no_repair (confidence Low, "illustrative Nordic values").
- DTO defaults (default, low, high): local laundry 2.5 (1.8, 3.5) €/kg; energy 0.15 (0.10, 0.25) €/kWh; water 4 (3, 6) €/m³; detergent 0.05 (0.03, 0.08) €/kg; labour 30 (25, 40) €/h; handling 3 (2, 5) min/kg; admin 4 (2, 8) h/site/month; garment life 2 (1.5, 3) years; contract_price_eur_per_year: no default.
- Never sum €, hours and CO₂ into one figure. Net cost appears only when a contract price is entered.
- Tests never write into the repo. `tests/conftest.py` sets an autouse `VR_INPUTS_DIR` to a session tmp dir; generator/pitch tests write to tmp_path.
- PDF text must render non-ASCII (Ł, ó, ä, ö, å, õ). Register matplotlib's bundled `DejaVuSans.ttf` (`matplotlib.get_data_path()/fonts/ttf/`) with reportlab. Never use built-in Helvetica for body text.

## Review Focus

1. **KAM enters a decimal comma** ("2,5") or blank in the inputs form. Expect: the UI normalises the comma to a dot and treats blank as "use default"; the API stays strict (422 with a clear message for non-numeric input). Tests: Task 4 `test_inputs_reject_non_numeric`; Task 5 UI check step.
2. **Mats-only filter for the hotel.** Expect: no crash; wearer-based metrics None; DTO still computed (washing, garments); the page shows "No data" only where data is truly absent. Test: Task 2 `test_hotel_mats_only_filter`, Task 4 `test_dto_mats_only`.
3. **A corrupt or missing inputs file, or inputs for a disabled account.** Expect: defaults are used and a warning is logged; no 500. Inputs never leak between accounts. Test: Task 4 `test_inputs_file_corrupt_uses_defaults`, `test_inputs_isolated_per_account`.
4. **Extensions toggled off while a hotel inputs file exists.** Expect: 3 accounts; the hotel URL gives 404; nothing else breaks. Test: Task 1 `test_extensions_off_three_accounts`.
5. **Non-ASCII names in PDF/xlsx** (Pärnu, Łódź, Kraków). Expect: correct glyphs/characters. Test: Task 6 `test_pdf_unicode`, `test_xlsx_unicode`.

---

## File map (new / changed)

```
config/sources.yaml                 NEW  configured adapters (Task 1)
config/lindstrom_fit.yaml           NEW  fit-page content (Task 5)
config/assumptions/v1.yaml          MOD  T3–T11 register rows + dto_inputs block (Tasks 2, 4)
config/industry_rules.yaml          MOD  Hospitality defaults/emphasis + "Guest experience" topic (Task 2)
adapters/canonical.py               NEW  canonical_from_sheets() shared by both adapters (Task 1)
adapters/excel_pack.py              MOD  uses canonical_from_sheets (Task 1)
adapters/csv_pack.py                NEW  CsvPackAdapter (Task 1)
model/load.py                       MOD  load_sources(); load_pack() wrapper (Task 1)
model/validate.py                   MOD  duplicate-id across sources → ERROR (Task 1)
scripts/make_extension_pack.py      NEW  deterministic generator (Task 2)
data/extension_pack/*.csv + README  NEW  generated, committed (Task 2)
metrics/frames.py, metrics/engine.py MOD service_line filter (Task 2)
api/review_model.py, api/build.py   MOD  service_line param, meta.service_lines, dto field, inputs hash in run_id (Tasks 2, 4)
api/main.py                         MOD  service_line query; inputs endpoints; /config/fit; export formats (Tasks 2, 4, 5, 6)
model/inputs_store.py               NEW  load/save/validate/effective inputs (Task 4)
metrics/dto.py                      NEW  compute_dto() (Task 4)
web/index.html, app.js, modules.js, styles.css, config/modules.json  MOD (Task 5)
export/pdf_builder.py, export/xlsx_builder.py  NEW (Task 6)
export/pptx_builder.py              MOD  DIY slide + service line on cover (Task 6)
scripts/make_pitch_deck.py, docs/pitch/ValueReview_pitch.pptx  NEW (Task 7)
README.md, docs/*.md                MOD (Task 7)
tests/test_sources.py, test_extension.py, test_extensibility.py, test_dto.py, test_inputs.py, test_exports_more.py, test_pitch.py  NEW
tests/conftest.py, tests/test_export.py  MOD
```

---

### Task 1: Multi-source loading and CSV adapter

**Files:** Create `config/sources.yaml`, `adapters/canonical.py`, `adapters/csv_pack.py`, `tests/test_sources.py`. Modify `adapters/excel_pack.py`, `model/load.py`, `model/validate.py`, `tests/conftest.py`, `pyproject.toml` (add reportlab; pypdf to dev).

**Interfaces:**
- Consumes: existing `ExcelPackAdapter`, `validate_frames`, `consistency_checks`, DDL.
- Produces:
  - `adapters/canonical.py`: `canonical_from_sheets(sheets: dict[str, pd.DataFrame], source_id: str, load_id: str, default_service_line: str = "Workwear") -> dict[str, pd.DataFrame]`. Sheet keys are the pack sheet names: Customers, Sites, Products, Laundries, Service_Activity, Service_Cycles, Repairs, Laundry_Resources, Waste_Circularity (each optional except Customers/Sites/Products). If a Products frame has a `service_line` column it is used, else the default.
  - `CsvPackAdapter(path: Path, source_id: str | None = None)`; `source_id` defaults to the folder name; tier 0; system "CSV". The CSV file name maps to the sheet name: customers.csv→Customers, sites.csv→Sites, products.csv→Products, laundries.csv→Laundries, service_activity.csv→Service_Activity, service_cycles.csv→Service_Cycles, repairs.csv→Repairs, laundry_resources.csv→Laundry_Resources, waste.csv→Waste_Circularity. Columns are identical to the pack sheets.
  - `config/sources.yaml`:
    ```yaml
    sources:
      - {id: excel_pack, adapter: excel, path: "${VR_PACK_PATH}", enabled: true}
      - {id: extension_pack, adapter: csv, path: data/extension_pack, enabled: true, toggle_env: VR_EXTENSIONS}
    ```
    Relative paths resolve against the repo root. `${VR_PACK_PATH}` falls back to the existing default. `toggle_env` set to "off" disables that source. A missing folder for an enabled CSV source logs a warning and is skipped (no crash).
  - `model/load.py`: `load_sources(config_path: Path | None = None, db: str = ":memory:", inject_bad: bool = False) -> duckdb.DuckDBPyConnection`. It concatenates the canonical frames of all enabled sources and keeps an internal `_source_id` column for duplicate detection (dropped before insert). One `source` row per adapter. `load_pack(path, db=":memory:", inject_bad=False)` keeps its signature and behaviour (Excel only).
  - `validate_frames`: a dimension row (org_node, product, laundry) whose id already came from an earlier source → ERROR quarantine with reason `duplicate key from source <id>`. The first source wins.
  - `api/main.py` lifespan calls `load_sources()` (still honouring `VR_INJECT_BAD_ROWS`).
  - `tests/conftest.py`: an autouse session-level `os.environ.setdefault("VR_EXTENSIONS", "off")` before app import.

- [ ] **Step 1: Write failing tests** in `tests/test_sources.py`:
  - `test_load_pack_unchanged(pack_path)`: `load_pack` org_node count 37, fact_service_month 1248
  - `test_csv_adapter_roundtrip(tmp_path)`: write minimal CSVs (1 customer, 1 site, 1 product with service_line "Mats", 1 activity row on L001) → `load_sources` with a temp sources.yaml (excel + this csv) → customer present; product service_line "Mats"; source table has 2 rows
  - `test_duplicate_id_quarantined(tmp_path)`: the csv pack re-declares site `S001` → quarantine has reason containing "duplicate key from source"; S001 still belongs to CUST001
  - `test_extensions_off_three_accounts(monkeypatch)`: `VR_EXTENSIONS=off` → `load_sources()` gives 3 ACCOUNT nodes
  - `test_missing_csv_folder_skipped(tmp_path)`: an enabled csv source with a non-existent path → loads the Excel pack only, no exception
- [ ] **Step 2:** Run `python -m pytest tests/test_sources.py -q -W error`. Expected: FAIL.
- [ ] **Step 3:** Implement. Refactor ExcelPackAdapter's mapping into `canonical_from_sheets` with no behaviour change.
- [ ] **Step 4:** Run the new tests, then the full suite. Expected: all pass (existing tests unchanged thanks to the conftest toggle).
- [ ] **Step 5:** Commit `feat: multi-source loading with CSV adapter`.

### Task 2: Extension pack, Hospitality, service-line filter

**Files:** Create `scripts/make_extension_pack.py`, `data/extension_pack/{customers,sites,products,service_activity,service_cycles,repairs}.csv`, `data/extension_pack/README.md`, `tests/test_extension.py`. Modify `config/industry_rules.yaml`, `config/assumptions/v1.yaml` (T3), `metrics/frames.py`, `metrics/engine.py`, `api/review_model.py`, `api/build.py`, `api/main.py`.

**Interfaces:**
- Consumes: `load_sources` (Task 1).
- Produces:
  - Pack content (seed 2026):
    - CUST004 "Baltic Harbour Hotels", Hospitality, High Value, Finland, topics "Hygiene|Guest experience|Cost optimization|Water efficiency".
    - Sites S101 Helsinki FI, S102 Turku FI, S103 Tallinn EE, S104 Tartu EE, S105 Pärnu EE; site_type "Hotel"; laundry L002.
    - Products P2001 "Entrance Mat Standard" and P2002 "Logo Mat" (service_line Mats, product_group Mats, weight 2.8 / 3.5 kg, footprint 21.0 / 26.5 kgCO2e, cost 85 / 140 €).
    - The hotel also rents P1001, P1002.
    - 12 months 2025. Monthly total for the hotel ≤ 15,000 kg. Mats rows have `active_wearers = 0`.
    - Service cycles for all products (≈ 2 per asset per month, a few LATE). Repairs only for P1001/P1002.
  - `config/industry_rules.yaml`: Hospitality defaults `[service, cost, water]`; emphasis text "Highlight guest-facing hygiene and textile availability, cost per room-night drivers and water efficiency."; topic map "Guest experience" → service.
  - Engine: `base_frames(con, account_id, months, product, service_line: str | None = None)`. Every Engine public method gains a keyword `service_line: str | None = None` and filters activity, cycles and repairs by product service_line.
  - `ReviewParams.service_line: str | None = None`; API query `service_line`; `meta.service_lines: list[str]` = the service lines present for the account (unfiltered); `meta.service_line: str | None`. The run_id includes it (it is part of params).

- [ ] **Step 1: Write failing tests** in `tests/test_extension.py`, using a module fixture `con_ext` = `load_sources()` with `VR_EXTENSIONS=on` via monkeypatch-free env setup inside the fixture:
  - `test_hotel_loaded(con_ext)`: CUST004 present, 5 sites, countries {"Finland","Estonia"}, industry "Hospitality"
  - `test_c1_only_l003(con_ext)`: dq_flags C1 entity_ids == {"L003"}
  - `test_existing_accounts_unchanged(con_ext, con)`: NorthStar `co2_saving_kg` and `washed_kg` are identical between `con` (Excel only) and `con_ext`
  - `test_service_lines_meta(con_ext)`: review CUST004 `meta.service_lines == ["Mats", "Workwear"]` (sorted); CUST001 == ["Workwear"]
  - `test_hotel_mats_only_filter(con_ext)`: review CUST004 `service_line="Mats"` builds; `washed_kg.value > 0`; `service_requests_per_100w.value is None`; no NaN in JSON
  - `test_hospitality_defaults(con_ext)`: CUST004 `context.active_priorities[:2] == ["service", "cost"]`
  - `test_generator_deterministic(tmp_path)`: running the generator into tmp_path twice gives byte-identical CSVs, equal to the committed ones
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement the generator (args: `--out data/extension_pack`), run it, commit its outputs, then implement the service-line filter. Add T3 to the assumptions register.
- [ ] **Step 4:** Run the new tests, then the full suite. Expected: pass.
- [ ] **Step 5:** Commit `feat: extension pack (Mats, Hospitality, Estonia) and service-line filter`.

### Task 3: Proof of zero-code-change extensibility

**Files:** Create `tests/test_extensibility.py`.

**Interfaces:** Consumes `load_sources(config_path)`, `build_review`, the industry-rules config loader (`config.loader.load_yaml`). If industry rules are read through a cached loader, the test must be able to point them at a temp file. If that needs a hook, add `VR_CONFIG_DIR` override support to `config/loader.py` (the only code change allowed here, and it is generic).

- [ ] **Step 1: Write the test** `test_new_line_industry_country_without_code_changes(tmp_path, monkeypatch)`:
  - write a third pack: laundries.csv (L901 "Daugava Riga WWS", Latvia), laundry_resources.csv and waste.csv for L901 (12 months), customers.csv (CUST901 "Riga Bistro Group", industry "Restaurants", topics "Hygiene|Cost optimization"), sites.csv (S901, S902 in Riga, Latvia), products.csv (P9001 "Washroom Towel Roll", service_line "Washroom"), service_activity.csv (12 months, both sites, P9001 + P1002), service_cycles.csv;
  - **also add Washroom rows for an existing account**: service_activity rows for CUST001 site S001 with P9001 on laundry L001, ≤ 50 kg per month (keeps C1 clean);
  - write a temp sources.yaml (excel + this pack) and a temp config dir copying the real config, plus an industry_rules entry for Restaurants `[service, cost]`;
  - assert:
    - CUST901 review builds, `meta.service_lines` contains "Washroom";
    - countries include "Latvia";
    - `context.active_priorities[0] == "service"`;
    - CUST001 `meta.service_lines` == ["Washroom", "Workwear"];
    - CUST001 review with `service_line="Washroom"` builds;
    - no ERROR quarantine rows; C1 entity_ids == {"L003"}.
- [ ] **Step 2:** Run. Expected: PASS once Tasks 1–2 exist. If it fails, fix only generic loader/config code, never by special-casing these ids.
- [ ] **Step 3:** Commit `test: prove new service line, industry and country need no code changes`.

### Task 4: DIY comparison engine, inputs store and API

**Files:** Create `metrics/dto.py`, `model/inputs_store.py`, `tests/test_dto.py`, `tests/test_inputs.py`. Modify `config/assumptions/v1.yaml` (`dto_inputs` + T4–T11 register rows), `api/review_model.py`, `api/build.py`, `api/main.py`, `.gitignore` (`data/kam_inputs/`).

**Interfaces:**
- Consumes: `Engine.compute` results (washed_kg, garments_allocated, replacements_postponed, active_wearers, sites, on_time_rate, utilisation, service_requests_per_100w), baselines + sensitivity from assumptions, product purchase cost (extend `metrics/frames.py` so repairs and activity carry `purchase_cost_eur`, if not already).
- Produces:
  - `model/inputs_store.py`:
    - `inputs_dir() -> Path` (env `VR_INPUTS_DIR`, default `data/kam_inputs`)
    - `load_inputs(account_id) -> dict` ({} if missing or corrupt; a corrupt file logs a warning)
    - `validate_inputs(data: dict, spec: dict) -> dict` (allowed keys = each input key, `<key>_low`, `<key>_high`, `contract_price_eur_per_year`; numbers ≥ 0; low ≤ high; else ValueError with the key named)
    - `save_inputs(account_id, data, spec) -> dict` (validates, adds `entered_at` ISO date per key, writes JSON UTF-8)
    - `effective_inputs(stored: dict, spec: dict) -> list[dict]`, each `{key, label, unit, value, low, high, source: "default" | "kam", entered_at, assumption_id}`; contract price: value None unless entered, assumption_id None
  - `metrics/dto.py`: `compute_dto(engine, account_id: str, period: str, product: str | None, service_line: str | None, baseline_id: str, inputs: list[dict], assumptions: dict) -> dict`, matching the design §8a.4 item 4:
    - lines (ids): `garment_purchases`, `extra_replacements`, `washing`, `employee_time` (B_HOME only), `staff_handling` (B_INHOUSE only), `admin`
    - `diy_total`, `contract_price`, `net`, `convenience.staff_hours_freed`
    - each line is a MetricResult (unit "EUR" or "h", method_status ESTIMATED, provenance SYNTHETIC, confidence "Low", assumptions = the relevant T-ids + A001/T1, range low/base/high per §8a.4 items 1–2, formula_text)
  - Formulas (m = months in period, s = sensitivity baseline factor, input values at the same low/base/high end):
    - `garment_purchases` = garments_allocated × weighted purchase cost ÷ garment_life × m/12
    - `extra_replacements` = Σ over products of replacements_postponed × purchase_cost
    - `washing`:
      - B_LOCAL = washed_kg × local_laundry_eur_per_kg
      - B_INHOUSE / B_HOME = washed_kg × (energy_kwh_per_kg × s × energy_price + water_l_per_kg × s ÷ 1000 × water_price + detergent)
    - `staff_handling` (B_INHOUSE) and `employee_time` (B_HOME) = washed_kg × handling_min ÷ 60 × labour
    - `admin` = sites × admin_h × m × labour
    - `diy_total` = Σ lines
    - `contract_price` = price × m/12 (if entered)
    - `net` = diy_total − contract_price (if entered)
    - `staff_hours_freed` = (handling hours for B_INHOUSE/B_HOME) + admin hours
  - `ReviewModel.dto: dict | None` (a pydantic model is welcome). `build_review` loads stored inputs for the account, computes the DTO, and includes `sha256(json(effective_inputs))[:8]` in the run_id input. Customer audience: DTO included, inputs read-only (no change in data), hygiene_note for Food & Beverage / Healthcare = "Industrial laundering gives process control that home washing cannot — context, not compliance advice."
  - API: `GET /accounts/{id}/inputs` → effective inputs; `PUT /accounts/{id}/inputs` (body = dict) → 422 on ValueError, 404 on unknown account; returns the effective inputs.

- [ ] **Step 1: Write failing tests:**
  - `tests/test_inputs.py`:
    - `test_defaults_effective` (8 defaulted + contract price None)
    - `test_save_and_load(tmp_path, monkeypatch)`
    - `test_inputs_reject_non_numeric` ("2,5" → ValueError naming the key)
    - `test_reject_unknown_key`
    - `test_reject_low_gt_high`
    - `test_inputs_file_corrupt_uses_defaults`
    - `test_inputs_isolated_per_account`
    - API: `test_put_inputs_422`, `test_put_then_review_reflects` (labour 50 → in-house washing line base increases; run_id changes)
  - `tests/test_dto.py`:
    - `test_dto_defaults_northstar` (diy_total not None; net None; contract None)
    - `test_dto_net_with_contract` (contract 100000/yr, period 2025 → net.base == diy_total.base − 100000)
    - `test_dto_baseline_formula_switch` (B_LOCAL washing == washed_kg × 2.5; B_INHOUSE has staff_handling; B_HOME has employee_time)
    - `test_dto_ranges_ordered` (low ≤ base ≤ high for every line)
    - `test_dto_quarter_scaling` (Q1 garment_purchases ≈ year × 3/12 ± 25%, since snapshots differ)
    - `test_dto_mats_only` (with `VR_EXTENSIONS` on: CUST004 Mats filter → washing not None)
    - `test_dto_customer_audience`: no idle_stock_value_eur anywhere
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the new tests, then the full suite. Expected: pass.
- [ ] **Step 5:** Commit `feat: service vs do-it-yourself comparison with account-manager inputs`.

### Task 5: Customer story backend (plain-language cards)

**Files:** Create `insights/story.py`, `config/relatable.yaml`, `config/glossary.yaml`, `tests/test_story.py`. Modify `api/review_model.py`, `api/build.py`, `api/main.py` (`GET /config/glossary`).

**Interfaces:**
- Consumes: ReviewModel KPIs, `dto` (Task 4), `growth` (Task 6; the card is omitted while it's absent), observations/actions, and the `fmt_value` formatter (move it to `export/format.py` and re-import it in pptx_builder, so `insights/` doesn't import from `export/`).
- Produces:
  - `build_story(review) -> list[dict]`. Each card has `{id, title, statement, relatable: str|None, what_to_say, detail_view, value_refs: [metric_id]}`, with ids in this order: `value_delivered`, `vs_diy`, `biggest_improvement`, `growth`, `whats_next`. Any card whose data is missing is skipped.
  - `ReviewModel.story: list[dict]`.
  - Statements are templates filled by code. Ranges are phrased "about X (between A and B)".
- `config/relatable.yaml`: conversion factors **researched by the implementer with sources**, each `{id, factor, unit, label_template, source_url, note: "illustrative comparison"}`. At least:
  - household water per year (Finland);
  - average passenger car CO₂ per year (EU or Finland).

  Relatable text = metric value ÷ factor, rounded to 2 significant figures, prefixed "≈" and labelled illustrative.
- `config/glossary.yaml`: plain-language definitions (≤ 30 words each) for baseline, allocation, Scope 3, utilisation, range/sensitivity, estimate, repair handprint, data-consistency warning.

- [ ] **Step 1: Failing tests** in `tests/test_story.py`:
  - `test_story_cards_northstar` (ids are an ordered subset of the 5; value_delivered present; no statement contains "None"/"nan")
  - `test_story_uses_review_values` (the value_delivered statement contains the formatted `water_saving_l` or `co2_saving_kg` value from the same review)
  - `test_relatable_labelled` (every relatable string starts with "≈"; every yaml factor has a source_url)
  - `test_story_customer_audience` (no internal metric ids in value_refs)
  - `test_story_empty_filter` (Apex + P1004 builds without exception)
  - `test_glossary_endpoint`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run the new tests + full suite → PASS. **Step 5:** Commit `feat: customer story cards with relatable comparisons and glossary`.

### Task 6: Growth opportunities engine ("work with us more")

**Files:** Create `metrics/growth.py`, `config/service_catalogue.yaml`, `tests/test_growth.py`. Modify `model/inputs_store.py` (new keys), `config/assumptions/v1.yaml` (T12+), `api/review_model.py`, `api/build.py`, `api/main.py` (`GET /config/service-catalogue`).

**Interfaces:**
- Consumes: the Task 4 DTO machinery (per-kg cost formulas, effective inputs), `Engine.compute`.
- Produces:
  - `config/service_catalogue.yaml`: `[{id, name, service_line, description, typical_kg_per_site_month: {default, low, high}, typical_price_eur_per_kg: {default, low, high}, assumption_id, lindstrom_offer_url}]`. Ids: `workwear`, `mats`, `washroom`, `cleanroom`, `hospitality_textiles` (illustrative; T12–T16; offer URLs on lindstromgroup.com).
  - New input keys: `extra_sites` (int ≥ 0), `extra_wearers` (int ≥ 0), `extra_service_lines` (list of catalogue ids), `expansion_price_eur_per_site_year` (optional ≥ 0). An unknown catalogue id → ValueError.
  - `compute_growth(engine, account_id, period, baseline_id, inputs, assumptions, catalogue) -> dict | None` = `{levers: [{id: "sites"|"wearers"|"line:<id>", label, diy_cost_avoided, staff_hours_freed, co2_saving_kg, water_saving_l (MetricResults), net: MetricResult|None}], totals: {same + net}, narrative_line: str}`. Returns None when no growth inputs are set.
    - sites lever = current per-site averages (DTO lines ÷ sites, savings ÷ sites) × extra_sites;
    - wearers lever = per-wearer averages × extra_wearers;
    - service line lever = typical kg/site/month × (current sites + extra_sites) × months, valued with the baseline's DIY washing cost per kg and its savings per kg;
    - net only if the expansion price is given.
    All are ESTIMATED, with low/base/high in the same direction rule as design §8a.4 item 1.
  - `ReviewModel.growth: dict | None`.

- [ ] **Step 1: Failing tests** in `tests/test_growth.py`:
  - `test_growth_none_without_inputs`
  - `test_growth_sites_scales_linearly` (extra_sites 2 vs 4 → the base doubles within 1%)
  - `test_growth_wearers`
  - `test_growth_new_line_mats` (values > 0)
  - `test_growth_net_needs_price`
  - `test_growth_ranges_ordered`
  - `test_growth_unknown_line_422` (API PUT)
  - `test_growth_narrative_line_has_values`
  - `test_service_catalogue_endpoint`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS + full suite. **Step 5:** Commit `feat: growth opportunities from account-manager expansion inputs`.

### Task 7: Account intelligence (AI research on a real public company)

**Files:** Create `ai/intel.py`, `data/intel_snapshots/fazer-group.json`, `tests/test_intel.py`. Modify `api/main.py`, `.gitignore` (`data/intel_cache/`).

**Interfaces:**
- Produces:
  - `IntelReport` (pydantic): `{company, website|None, generated_at, mode: "live"|"snapshot", sections: {direction: [Claim], sustainability: [Claim], trends: [Claim], how_lindstrom_helps: [{offer_id, offer_name, why, based_on: [str]}], conversation_starters: [str]}, sources: [{url, title, date}], disclaimer}`. `Claim = {text, source_url, source_date}`.
  - `research_company(company: str, website: str | None, use_llm: bool) -> IntelReport`:
    - live path: Anthropic Messages API, model `claude-sonnet-5-5`, tools = the server web search tool `{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}` plus a `submit_report` tool with the JSON schema; the final answer must come via `submit_report`;
    - code drops claims without an http(s) source_url, and drops how_lindstrom_helps items whose offer_id is not in `config/service_catalogue.yaml`;
    - 60 s timeout;
    - live results cached in `data/intel_cache/<slug>.json`.
    - Fallback: if use_llm is False or the call fails and a snapshot exists for the slug → the snapshot (mode "snapshot"); otherwise raise `IntelUnavailable`.
  - `list_snapshots() -> list[{slug, company, generated_at}]`.
  - API: `POST /intel {company, website?}` → IntelReport (503 with a clear message on IntelUnavailable); `GET /intel/snapshots`.
  - The disclaimer, exactly: "AI-generated from public sources — verify before use. Example public company; no relationship with Lindström is implied."
- **Snapshot:** research **Fazer Group** with web search now: recent strategy/expansion, sites/workforce, sustainability targets and reporting, 2–4 food-industry trends. Use real URLs and dates only; never invent facts. Map 3–5 items to catalogue offers; write 4 conversation starters. Set mode "snapshot", generated_at "2026-11-07".

- [ ] **Step 1: Failing tests** in `tests/test_intel.py` (no network; a mocked Anthropic client):
  - `test_snapshot_valid` (parses; every claim has an http source_url; offer_ids are in the catalogue; ≥ 3 sources)
  - `test_live_path_drops_unsourced_claims`
  - `test_live_path_drops_unknown_offer`
  - `test_fallback_to_snapshot_without_key`
  - `test_unknown_company_without_key_503`
  - `test_intel_snapshots_endpoint`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement + research the snapshot. **Step 4:** Run → PASS + full suite. **Step 5:** Commit `feat: account intelligence with sourced live research and Fazer snapshot`.

### Task 8: Frontend A: story landing, simple/expert mode, glossary, service-line filter, export menu

**Files:** Modify `web/index.html`, `web/app.js`, `web/modules.js`, `web/styles.css`, `config/modules.json`, `tests/test_modules.py`.

- **Customer story** = the new default page (top of the nav). It shows the cards from `review.story`: title, big statement, relatable line (small, "illustrative"), a "What to say" box with a copy-to-clipboard button, and a "Show the detail" link to `detail_view`.
- **Simple / Expert toggle** in the header, default Simple, persisted in localStorage.
  - Simple hides z-scores, the method-status/provenance badges (one "estimate" pill for ESTIMATED values), lineage and formula text in drawers. Ranges read "about X (between A and B)".
  - Expert shows everything.
- **Glossary:** marked terms get a dotted underline + a tooltip from `/config/glossary`.
- **Service line** select (All + `meta.service_lines`) → `service_line`.
- **Export** button → menu: PowerPoint · PDF · Excel (a 400 → "Export available soon").
- [ ] **Step 1:** Update `test_modules.py` for the new components → FAIL → update modules.json → PASS.
- [ ] **Step 2:** Implement.
- [ ] **Step 3: Browser check** (port 8000):
  1. The story landing renders.
  2. The toggle changes the badges.
  3. A tooltip shows.
  4. The service-line select works for the hotel (extensions on).
  5. No console errors.
- [ ] **Step 4:** Commit `feat: customer story landing, simple mode, glossary, service-line filter, export menu`.

### Task 9: Frontend B: DIY comparison, growth, account intelligence, fit page

**Files:** Create `config/lindstrom_fit.yaml`. Modify `api/main.py` (`GET /config/fit`), `web/*`, `config/modules.json`, `tests/test_api.py` (`test_fit_config`).

- **Service vs do-it-yourself page:**
  - 4 columns: Environment, Cost, Time, Hygiene;
  - the cost-breakdown chart;
  - the "uses figures entered by the account manager" chip;
  - the "Your numbers" panel (KAM only): defaults prefilled, low/high, source badge, Save/Reset;
  - comma → dot, blank → omitted, the 422 message inline;
  - the customer audience sees a read-only inputs table.
- **Growth opportunities page:**
  - inputs: extra sites, extra wearers, service-line checkboxes from `/config/service-catalogue`, optional expansion price;
  - lever cards (€ avoided, hours, CO₂, water as "about X (A–B)");
  - the narrative line with a copy button.
- **Account intelligence page:**
  - a company + website form;
  - snapshot chips from `/intel/snapshots` (Fazer Group preselected);
  - sections with a source link per claim;
  - the "How Lindström can help" cards and conversation starters;
  - the disclaimer banner and a mode badge ("Live" / "Snapshot from …");
  - for the fictional accounts, a note "fictional customer — try the example public company".
- **Built on Lindström's work page:** `config/lindstrom_fit.yaml`, with the 8 asset rows and the brief map per design §3. PUBLIC rows link:
  - https://lindstromgroup.com/uk/article/bringing-greater-transparency-to-emissions-data-in-our-online-portal/
  - https://lindstromgroup.com/sustainability-goes-digital/
  - https://d2ris6qfzcz0wn.cloudfront.net/wp-content/uploads/sites/8/2026/04/Lindstrom-Sustainability-Report-2025.pdf

  It carries the note "Public facts are context only — never calculation inputs".
- [ ] **Step 1:** `test_fit_config` (≥ 8 assets; PUBLIC rows have an http source) → FAIL → implement → PASS.
- [ ] **Step 2:** Implement the UI.
- [ ] **Step 3: Browser check:**
  1. Contract price 120000 → net appears.
  2. "2,5" is accepted.
  3. Growth with 4 sites + Mats → levers appear.
  4. The intel page shows the Fazer snapshot with sources.
  5. The fit page renders.
  6. The customer audience gets read-only inputs.
  7. No console errors.
- [ ] **Step 4:** Commit `feat: DIY, growth, account intelligence and fit pages`.

### Task 10: PDF and Excel export; PPTX story, DIY and growth slides

**Files:** Create `export/pdf_builder.py`, `export/xlsx_builder.py`, `tests/test_exports_more.py`. Modify `export/pptx_builder.py`, `api/main.py`, `tests/test_export.py`.

- **Deck/PDF order:** Cover · **Customer story** · Executive summary · Value KPIs · Footprint vs baseline · **Service vs do-it-yourself** · **Growth opportunities** (only if `growth` is present) · Site highlights · Observations · Discussion & actions · Methodology · Appendix. That is 11 slides, or 12 with growth; update the counts in `test_export.py`.
- `build_pdf(review, out_path) -> Path`: reportlab, A4 landscape, DejaVuSans registered, footer with the disclaimer + run_id.
- `build_xlsx(review, out_path) -> Path`, with sheets Summary, Story, KPIs, Sites, Observations, Actions, DIY comparison, Growth (if present), Inputs, Assumptions, Data quality.
- `/reviews/export` `format` ∈ {pptx, pdf, xlsx}, with MIME types `application/pdf` and `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Filename `review_{id}_{period}.{ext}`.
- [ ] **Step 1: Failing tests:**
  - `test_pdf_has_sections` ("Customer story", "Service vs do-it-yourself", "Methodology", the disclaimer)
  - `test_pdf_unicode` ("Kraków")
  - `test_xlsx_sheets`
  - `test_xlsx_kpi_matches_api` (co2_saving_kg at sens "low")
  - `test_xlsx_unicode` ("Łódź")
  - `test_xlsx_customer_audience` (no "idle_stock_value_eur")
  - `test_export_formats_api` (3 formats 200; "docx" 400)
  - `test_pptx_story_first` (slide 2 title "Customer story")
  - `test_pptx_growth_slide_when_inputs`
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS + full suite. **Step 5:** Commit `feat: PDF and Excel exports; story, DIY and growth in the decks`.

### Task 11: Pitch deck and docs

**Files:** Create `scripts/make_pitch_deck.py`, `docs/pitch/ValueReview_pitch.pptx`, `tests/test_pitch.py`. Modify `README.md`, `docs/demo_script.md`, `docs/methodology.md`, `docs/data_readiness.md`.

- Pitch slides (titles, in order):
  1. "What you asked"
  2. "Built on Lindström's work"
  3. "Easy to explain: the customer story"
  4. "Save more by working with us more"
  5. "Knows where your customers are going"
  6. "Credible by design"
  7. "Grows with your business"
  8. "Exports & path to production"

  The disclaimer is on every slide. Headline figures come from `build_review` CUST001 via `fmt_value`. Slide 5 uses the Fazer snapshot with sources.
- [ ] **Step 1:** `test_pitch_deck` (8 slides, titles in order, the disclaimer on each) → FAIL.
- [ ] **Step 2:** Implement the script; generate and commit the deck.
- [ ] **Step 3: Docs:**
  - README: the extension worked example; `VR_EXTENSIONS`, `VR_INPUTS_DIR`; the inputs, intel and catalogue endpoints; the export formats; the new deps.
  - methodology: DTO + growth formulas, inputs T4–T16, T3, relatable factors with sources, the AI intel guardrails, the limitations.
  - data_readiness: service line / industry master data, contract prices, CRM legal names for intel.
  - demo_script ≤ 4 min:
    1. story landing (Simple);
    2. DIY with a typed contract price;
    3. growth;
    4. Fazer intel;
    5. extension (hotel, Mats, Estonia);
    6. export menu;
    7. Expert toggle → credibility.
- [ ] **Step 4:** Full suite → PASS. **Step 5:** Commit `docs: pitch deck and updated docs`.

## Cut list (if behind schedule; first cut first)
1. Excel export (Task 10)
2. The Latvia part of Task 3 (keep Washroom)
3. Glossary tooltips (Tasks 5/8)
4. The live-web path of Task 7 (keep the snapshot)
5. The fit page UI (keep the pitch slide)
