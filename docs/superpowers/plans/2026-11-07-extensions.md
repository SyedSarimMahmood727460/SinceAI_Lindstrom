# Value Review Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show Lindström judges that the solution (1) builds on their existing work, (2) extends to new service lines, industries, sites and countries without code changes, (3) exports PPTX/PDF/Excel, and (4) compares Lindström's service with do-it-yourself on cost, convenience and environment, using account-manager inputs over defaults.

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

### Task 5: Frontend: fit page, service-line filter, DIY page, export menu

**Files:** Create `config/lindstrom_fit.yaml`. Modify `api/main.py` (`GET /config/fit`), `web/index.html`, `web/app.js`, `web/modules.js`, `web/styles.css`, `config/modules.json`, `tests/test_modules.py`, `tests/test_api.py` (fit endpoint test).

**Interfaces:**
- Consumes: `meta.service_lines`, `meta.service_line`, `dto` (Task 4), inputs endpoints (Task 4), export formats pptx|pdf|xlsx (Task 6; until Task 6 lands, pdf/xlsx return 400 → the UI shows "Export available soon").
- `config/lindstrom_fit.yaml`: `assets: [{asset, today, value_review, brief_line, source, kind}]` with the 8 rows from design §3, plus `brief_map: [{requirement, where, status}]`. Sources for PUBLIC_REFERENCE rows:
  - eLindström emissions: https://lindstromgroup.com/uk/article/bringing-greater-transparency-to-emissions-data-in-our-online-portal/
  - RFID: https://lindstromgroup.com/sustainability-goes-digital/
  - Sustainability Report 2025: https://d2ris6qfzcz0wn.cloudfront.net/wp-content/uploads/sites/8/2026/04/Lindstrom-Sustainability-Report-2025.pdf
  - Dashboard mockups / data pack / brief: "Challenge pack (provided)"
- UI changes:
  - nav item "Built on Lindström's work" (Trust section) renders both tables, with a PUBLIC badge + link for public rows and the note "Public facts are context only — never calculation inputs".
  - header "Service line" select (All + meta.service_lines) → `service_line` query.
  - new Review page "Service vs do-it-yourself": 4 columns (Environment uses existing savings KPIs; Cost lines + DIY total + contract + net, or the prompt "Enter the contract price to see the net comparison"; Time = staff hours freed + on-time + utilisation; Hygiene note), a cost-breakdown bar chart, and a "uses figures entered by the account manager" chip when any source == "kam".
  - "Your numbers" panel (KAM audience only): one row per input (label, value field prefilled, low/high fields, unit, source badge, entered date), Save (PUT, then reload review), "Reset to defaults" (PUT {}). The comma → dot normalisation and blank → omit happen before sending; a 422 message is shown inline. Customer audience: a read-only inputs table.
  - Export button → menu: PowerPoint · PDF · Excel.
  - modules.json: register the new components with `required_metrics: []` (DTO components check `dto` presence instead).

- [ ] **Step 1:** Add `test_fit_config` (`/config/fit` returns ≥ 8 assets, every PUBLIC_REFERENCE row has an http source) and update `test_modules.py` for the new components. Run → FAIL → implement the endpoint/config → PASS.
- [ ] **Step 2:** Implement the UI.
- [ ] **Step 3: Verify in the browser** (server on port 8000; the controller runs the visual check if you can't):
  1. Fit page renders both tables.
  2. Service-line select shows Mats for Baltic Harbour Hotels (start the server with extensions on).
  3. DIY page with defaults; enter contract price 120000 → net appears; enter "2,5" for local laundry → saved as 2.5.
  4. Customer audience: inputs read-only, no edit form.
  5. Export menu shows three options.
  6. No console errors.
- [ ] **Step 4:** Commit `feat: fit page, service-line filter, DIY comparison page, export menu`.

### Task 6: PDF and Excel export; PPTX DIY slide

**Files:** Create `export/pdf_builder.py`, `export/xlsx_builder.py`, `tests/test_exports_more.py`. Modify `export/pptx_builder.py`, `api/main.py`, `tests/test_export.py` (slide count 9 → 10).

**Interfaces:**
- Consumes: ReviewModel incl. `dto`, `meta.service_line`; `export.charts` PNG helpers; `fmt_value`.
- Produces:
  - `build_pdf(review, out_path: Path) -> Path` (reportlab platypus, A4 landscape). Sections in PPTX order, with "Service vs do-it-yourself" inserted after Footprint (10 sections). DejaVuSans registered. Footer on every page with the disclaimer + run_id.
  - `build_xlsx(review, out_path: Path) -> Path`, with sheets Summary, KPIs, Sites, Observations, Actions, DIY comparison, Inputs, Assumptions, Data quality (columns per design §5 and §8a; numbers stored as numbers).
  - PPTX: a new slide "Service vs do-it-yourself" after Footprint (lines table + net or the contract prompt + staff hours); the cover shows the service line when filtered.
  - `/reviews/export` accepts `format` ∈ {pptx, pdf, xlsx}. MIME types `application/pdf` and `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; filename `review_{id}_{period}.{ext}`.

- [ ] **Step 1: Write failing tests** in `tests/test_exports_more.py`:
  - `test_pdf_has_sections` (pypdf: ≥ 10 pages, or the texts "Service vs do-it-yourself", "Methodology", and the disclaimer are present)
  - `test_pdf_unicode` (text contains "Kraków")
  - `test_xlsx_sheets` (all 9 sheet names)
  - `test_xlsx_kpi_matches_api` (the KPIs sheet row co2_saving_kg value == review KPI value at sens "low")
  - `test_xlsx_unicode` (Sites sheet contains "Łódź")
  - `test_xlsx_customer_audience` (no cell anywhere contains "idle_stock_value_eur")
  - `test_export_formats_api` (pptx/pdf/xlsx → 200 + MIME; "docx" → 400)
  - `test_pptx_has_diy_slide` (slide titled "Service vs do-it-yourself" present)
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Reuse `fmt_value`/`fmt_number` (move them to `export/format.py` if both builders need them, then import them back into pptx_builder).
- [ ] **Step 4:** Run the new tests, then the full suite. Expected: pass.
- [ ] **Step 5:** Commit `feat: PDF and Excel exports, DIY slide in PowerPoint`.

### Task 7: Pitch deck and docs

**Files:** Create `scripts/make_pitch_deck.py`, `docs/pitch/ValueReview_pitch.pptx`, `tests/test_pitch.py`. Modify `README.md`, `docs/demo_script.md`, `docs/methodology.md`, `docs/data_readiness.md`.

- [ ] **Step 1:** `tests/test_pitch.py::test_pitch_deck` builds the deck to tmp_path and asserts 6 slides, with the titles in this order:
  1. "What you asked"
  2. "Built on Lindström's work"
  3. "How it works"
  4. "Credible by design"
  5. "Grows with your business"
  6. "Exports & path to production"

  It also asserts the disclaimer is on every slide. Run → FAIL.
- [ ] **Step 2:** Implement the script (content per design §6; reads `config/lindstrom_fit.yaml` for slide 2; slide 4 includes the L003 example and "AI never writes numbers"; slide 5 the Mats/Hospitality/Estonia + Washroom/Latvia proof; slide 6 the three exports + Tier 0→3 + Q35 + the service-vs-DIY comparison). Headline figures come from `build_review` for CUST001 (base, B_LOCAL) via `fmt_value`. Generate `docs/pitch/ValueReview_pitch.pptx` and commit it.
- [ ] **Step 3:** Docs:
  - README: rewrite "How to extend" as the extension-pack worked example (sources.yaml + CSV folder + industry rule) and point to `tests/test_extensibility.py`; add the env vars `VR_EXTENSIONS` and `VR_INPUTS_DIR`; the inputs endpoints; the export formats; reportlab in the deps.
  - methodology: add the DTO formulas, the inputs table (T4–T11) and T3; state the limitations (no auth on inputs; no cross-border distance modelling).
  - data_readiness: add rows for service line master data, industry master data and contract prices.
  - demo_script: add the extension moment (30 s), the DIY page with a typed contract price (30 s) and the export menu. The total stays ≤ 4 min (trim elsewhere).
- [ ] **Step 4:** Run the full suite. Expected: pass.
- [ ] **Step 5:** Commit `docs: pitch deck, extension worked example, DIY methodology`.
