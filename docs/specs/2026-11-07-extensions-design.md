# Value Review — Extensions Design (round 2)

Status: **draft for approval** · Date: 2026-11-07 · Builds on: `docs/specs/2026-11-06-value-review-design.md` (the "base spec") and the merged code on `main`.
Deadline: Sun 8 Nov 2026, 10:00 EET.

Legend: **[User]** = what the user decided · **[Call]** = my decision, can be overruled.

---

## 1. Intent

The prototype already meets every line of the Lindström brief (audit done 2026-11-07). This round is about what a Lindström judge should **walk away believing** [User]:

1. **"They understood our existing work and what we asked for."** The solution visibly builds on Lindström's real assets and the brief's own words. It is not a generic dashboard.
2. **"It grows with our business."** Lindström can add **more products / service lines**, **more sites and countries**, and **new kinds of customers / industries** (e.g. hotels, restaurants, healthcare) without redesigning anything [User: "both" sites/countries and new customer types].
3. **"The exports actually work."** The suggested solution exports a customer-ready review.

Success = in the 4-minute pitch, each of the three is *shown*, not just claimed.

## 2. Goals, non-goals, anti-goals

**Goals**
- G1 An in-app **"How this fits Lindström"** page that maps each part of the solution to a Lindström asset and to the brief line it answers.
- G2 A **live extensibility demo**:
  - a second synthetic **extension pack** adds a new service line (**Mats**), a new industry (**Hospitality**), a new customer, and a new country (**Estonia**);
  - it loads through a **second adapter**, with **no engine, insight or UI code changes**;
  - a test proves the "no code change" claim.
- G3 **Exports**: PPTX (existing), **PDF** (new, server-side), and an **Excel data export** of the review figures with their status labels. All three come from the same ReviewModel and respect the audience setting.
- G4 A **6-slide pitch deck** (separate from the customer review deck) that tells the three-takeaway story.
- G5 Docs updated: README "extend" section rewritten as a worked example using the extension pack; demo script updated.

**Non-goals**
- What-if simulator, industry regulatory panel, per-recommendation data gaps. All deferred from the audit.
- Real Lindström data, authentication, eLindström embedding.

**Anti-goals**
- Public facts about Lindström used as calculation inputs (base spec: PUBLIC_REFERENCE is context only).
- Any number on the fit page that isn't sourced.
- An "extension" that secretly needed engine/UI edits.
- Exports that disagree with the dashboard.
- Extension data that breaks the C1 laundry-volume check (it must be internally consistent).

## 3. G1: "How this fits Lindström" page

- **Where**: a new nav item under "Trust", titled "Built on Lindström's work". It is also slide 2 of the pitch deck and a README section.
- **Content source**: `config/lindstrom_fit.yaml` (data-driven, editable). Each row: `asset`, `what Lindström has today`, `how Value Review uses or extends it`, `brief line answered`, `source` (URL or "data pack: <sheet>"), `kind` ∈ {PUBLIC_REFERENCE, DATA_PACK, BRIEF}.
- **Rows** (content [Call]; wording to be kept factual):

| Lindström asset | Today | Value Review uses / extends it |
|---|---|---|
| Managerial dashboard mockups (inspiration deck) | Core/add-on views; General / Sustainable actions / Financial packs; customisable canvas | Same module + pack model (`config/modules.json`); same KPI-row layout |
| eLindström customer portal | 24/7 portal; since Nov 2025 shows customer GHG emissions (GHG Protocol, invoice-based, annual) | Proposed as an eLindström module; per-kg, monthly, per-site allocation; baselines and ranges |
| RFID garment tracking | RFID tag per garment; status in use / laundry / repair | Utilisation = scanned ÷ allocated; service cycles and on-time rate |
| Tableau reports (Allocated pieces, Washing %, End-to-end delivery, Repairs table, WWS washed kg) | Operational reports | One adapter per report type; these are the Tier 1 source path |
| WWS laundry environmental-impact calculator; Textile waste kg report | Laundry-level factors and waste routes | Laundry intensities and waste routes, allocated by kg (A003) |
| Sustainability Report 2025 (CSRD-referenced, EY-assured) | Group targets (−50% value-chain GHG by 2030), 66% textile waste recycled 2025 | Context only; status labels keep prototype estimates separate from reported figures |
| Workwear Alarm / repairs service | Products that reduce losses and extend life | Observations R1/R5 point to these levers |
| Data pack Assumptions A001–A008, Baselines, Industry_Priorities | Lindström's own assumption framing | Used verbatim; team assumptions T1/T2 added and labelled |
| Brief §02/§04/§06/§07 | The ask and judging criteria | Requirement → feature checklist (second table on the page) |

- **Second table — "What you asked → where it is"**: each brief requirement (e.g. "customer-level managerial view with site drill-down") → page or feature → status ✅. Same content as the 2026-11-07 audit.
- Every PUBLIC_REFERENCE row shows its source link and the badge `PUBLIC`. The page states that these are context, not calculation inputs.

## 4. G2: Extensibility demo

### 4.1 The extension pack (synthetic, committed)
- Location: `data/extension_pack/` — CSV files mirroring the canonical row shapes. Files: customers, sites, products, service_activity, service_cycles, repairs (may be empty), laundry_resources (optional), waste (optional), README.md.
- Generated by `scripts/make_extension_pack.py` (seeded, deterministic; committed outputs). Every row has `data_status = SYNTHETIC`.
- Contents [Call]:
  - **New industry + customer + country**: `CUST004 "Baltic Harbour Hotels"`, industry **Hospitality**, segment High Value, HQ Finland. 5 sites: Helsinki, Turku (FI), **Tallinn, Tartu, Pärnu (EE — new country)**. Served by the currently unused laundry **L002 Aurora Turku WWS**. Volumes are scaled so that, for every month, Σ customer kg routed to L002 stays ≤ the L002 washed kg in the main pack, so C1 does not fire.
  - **New service line "Mats"**: products `P2001 Entrance Mat Standard`, `P2002 Logo Mat` (service_line Mats, weight, synthetic footprint and cost). Rented by Baltic Harbour Hotels (all sites) **and** by NorthStar (6 Finnish sites). This shows a new service line for an *existing* customer too.
  - Hospitality also rents workwear (existing products P1001/P1002), so the hotel isn't mats-only.
  - Mats have no wearers. Wearer-based metrics (per-100-wearers) for a mats-only filter return None and show "No data for this filter". This is expected behaviour, not an error.
  - Repairs: none for mats (empty rows are fine).
- Customer priority topics for CUST004: "Hygiene|Guest experience|Cost optimization|Water efficiency". New topic "Guest experience" maps to `service`.

### 4.2 What may change, and what must not
- **May change (data + config only):** `data/extension_pack/*`; `config/industry_rules.yaml` (add Hospitality defaults + emphasis text + topic map entry); `config/sources.yaml` (new, see below).
- **One-time generalisations to existing code, done once and allowed in this round, because the base build hard-wired them** [Call]:
  1. `model/load.py`: load **a list of adapters** from `config/sources.yaml` (each: adapter class, path, tier, enabled). The `source` table gets one row per adapter. Validation, quarantine and C1–C3 run over the union. Default config: the Excel pack + the extension pack (enabled). Env `VR_EXTENSIONS=off` disables the extension pack for a before/after demo.
  2. `adapters/csv_pack.py`: a generic CSV adapter (canonical-shaped CSVs → canonical frames). This *is* the "add an adapter" example.
  3. **Service-line filter**: engine `base_frames(..., service_line=None)`, ReviewParams `service_line`, API query `service_line`, UI dropdown (All / Workwear / Mats, from `meta.service_lines`), PPTX/PDF cover shows it.
  4. `meta.service_lines` and `meta.countries` in ReviewModel.
- **Must not change after the generalisation:** adding a *further* service line, industry, country or customer requires **zero** code edits. **Proof test** `tests/test_extensibility.py`:
  - it writes a tiny third CSV pack into a temp dir (a new service line "Washroom" and an industry "Restaurants" with one customer in a new country "Latvia");
  - it registers that pack via a temp sources config;
  - it asserts the customer appears in `/accounts`, the review builds, the service-line filter lists Washroom, the industry defaults apply (via the config added in the test), and no exception occurs.

### 4.3 Demo moment (≈30 s in the pitch)
"Lindström adds a service line and a hotel chain in Estonia: here's the whole change." Show `config/sources.yaml` + the CSV folder + the 6-line industry rule. Then in the app: the customer dropdown now has Baltic Harbour Hotels (Hospitality priorities apply), the country list includes Estonia, and NorthStar's service-line filter shows Mats.

## 5. G3: Exports

All three formats come from the same ReviewModel and the same `run_id`. All carry the disclaimer `Prototype · synthetic data · not audited`. All respect `audience` (no customer_facing=False metrics in customer exports).

| Format | Endpoint | Content |
|---|---|---|
| PPTX (exists) | `POST /reviews/export {format:"pptx"}` | 9 slides (base spec §13); cover adds service line |
| **PDF (new)** | `format:"pdf"` | Same 9 sections as the PPTX, rendered server-side with **reportlab** [Call: pure-Python, no LibreOffice/PowerPoint needed on a judge's machine]. Same charts (reuse `export/charts.py` PNGs), same `fmt_value`, footer with disclaimer + run_id. |
| **Excel (new)** | `format:"xlsx"` | openpyxl workbook. Sheets: `Summary` (meta, baseline, sensitivity, priorities, disclaimer); `KPIs` (metric_id, label, unit, value, low, base, high, method_status, provenance, confidence, dq_warning, assumptions, formula_text); `Sites` (one row per site × headline metrics); `Observations`; `Actions`; `Assumptions` (register used); `Data quality` (warnings with laundry name, quarantine count, gaps). Numbers as numbers (not strings), units in headers. |

- UI: the Export button becomes a split button / dropdown: PowerPoint · PDF · Excel.
- Tests:
  - each format returns 200 and the right MIME type and filename;
  - the PDF has 9 pages (or ≥ 9 with overflow), contains the disclaimer and "Kraków";
  - the xlsx KPI value for co2_saving_kg equals the API value at the selected sensitivity;
  - the customer-audience xlsx has no idle_stock_value_eur anywhere.

## 6. G4: Pitch deck

- `scripts/make_pitch_deck.py` → `docs/pitch/ValueReview_pitch.pptx` (committed). 16:9, same brand colours as the export.
- Slides [Call]:
  1. **The ask, in Lindström's words**: the brief's guiding question, and the three things a KAM must answer.
  2. **Built on your work**: the fit table from G1 (condensed).
  3. **The workflow**: prompt → priorities → engine → observations → steering pack → export (request-flow diagram).
  4. **Credibility by design**: status labels, ranges, baselines, C1 warning example (L003), "AI never writes numbers".
  5. **Grows with your business**: architecture layers + the extension example (Mats, Hospitality, Estonia) + "zero code change" test.
  6. **Exports & path to production**: PPTX / PDF / Excel; Tier 0→3 sources; open questions (Q35) and the ask to Lindström.
- Content is static text from config/docs. No metric numbers except the headline figures taken from a review run at build time via `fmt_value`.

## 7. G5: Docs
- README "How to extend": rewrite as a worked example using the extension pack (sources.yaml + CSV folder + industry rule), plus the Washroom/Latvia example from the proof test.
- `docs/demo_script.md`: add the 30-second extension moment and the export dropdown. Keep the total ≤ 4 min.
- `docs/data_readiness.md`: add a row for service line and industry master data.

## 8. Acceptance
- All existing tests are still green, plus the new tests in §4.2 and §5.
- With the default config:
  - `/accounts` lists 4 customers incl. Baltic Harbour Hotels (Hospitality, 5 sites, FI+EE);
  - NorthStar's `meta.service_lines` = [Workwear, Mats];
  - C1 flags only L003 (L002 stays clean).
- With `VR_EXTENSIONS=off`, the app behaves exactly as today (3 customers).
- Visual check in the browser: the fit page, the service-line filter, the export dropdown.

## 8a. G6: Service vs do-it-yourself comparison (added 2026-11-07)

**Why** [User]: customers want to know the impact of using Lindström's service versus doing it themselves, on **cost, convenience and environment**. The key account manager must be able to enter the customer's own figures, which then flow into the comparison, with sensible defaults in place [User].

### 8a.1 Inputs ("Your numbers"), per account
- Stored server-side in `data/kam_inputs/{account_id}.json` (gitignored). API: `GET /accounts/{id}/inputs`, `PUT /accounts/{id}/inputs` (validated; unknown keys rejected; numbers ≥ 0). An entered value applies to all three of low/base/high unless the KAM gives a range.
- Defaults live in `config/assumptions/v1.yaml` under `dto_inputs`. Each has `default`, `low`, `high`, `unit`, `label`, and assumption id **T4–T12** [Call: illustrative Nordic values, confidence Low]:

| key | label | default (low–high) |
|---|---|---|
| contract_price_eur_per_year | Lindström contract price | **none** (blank → no net comparison) |
| local_laundry_eur_per_kg | Local laundry price | 2.5 (1.8–3.5) €/kg |
| energy_eur_per_kwh | Energy price | 0.15 (0.10–0.25) |
| water_eur_per_m3 | Water price | 4 (3–6) |
| detergent_eur_per_kg | Detergent & chemicals | 0.05 (0.03–0.08) €/kg |
| labour_eur_per_h | Staff cost | 30 (25–40) €/h |
| handling_min_per_kg | Washing & handling time (in-house/home) | 3 (2–5) min/kg |
| admin_h_per_site_month | Garment admin time without service | 4 (2–8) h/site/month |
| garment_life_years_no_repair | Garment life without repair service | 2 (1.5–3) years |

- Each input shows its source: `default (T7)` or `entered by KAM, <date>`. The provenance of derived figures becomes `KAM_INPUT` (a new Provenance value) whenever any input was entered; otherwise it stays as before.

### 8a.2 Calculations (engine, `metrics/dto.py`; all ESTIMATED with low/base/high)
Per account, period-scaled (annual inputs × months/12):
- **Garment purchases (DIY)** = garments_allocated × weighted purchase cost ÷ garment_life_years_no_repair (annualised).
- **Extra replacements without repairs** = replacements_postponed × product purchase cost (from the pack's Repairs + Products).
- **Washing cost** by the selected baseline:
  - B_LOCAL: washed_kg × local_laundry_eur_per_kg;
  - B_INHOUSE: washed_kg × (baseline kWh/kg × energy price + baseline l/kg ÷ 1000 × water price + detergent) + washed_kg × handling_min_per_kg ÷ 60 × labour cost;
  - B_HOME: the same energy/water/detergent formula with the home factors, plus employee time at the labour rate (shown separately as "employee time").
- **Admin** = sites × admin_h_per_site_month × months × labour cost (all baselines).
- **DIY total** = sum of the above. **Net vs Lindström** = DIY total − contract price, *only if* a contract price was entered. Otherwise the UI says "Enter the contract price to see the net comparison".
- **Convenience**:
  - staff hours freed = washing/handling hours (in-house, home) + admin hours;
  - on-time rate, utilisation and service requests per 100 wearers (existing metrics);
  - a qualitative hygiene note for Food & Beverage and Healthcare: "industrial process control vs home washing — context, not compliance advice".
- **Environment**: the existing savings metrics (no new maths).
- Never sum different kinds of benefit (€, hours, CO₂) into one score.

### 8a.3 UI, export, tests
- New page **"Service vs do-it-yourself"** (Review section):
  - a 4-column comparison: Environment · Cost · Time · Hygiene, with Lindström vs the selected alternative;
  - a "Your numbers" side panel (form with defaults, low/high, a save button, and reset to default);
  - a cost breakdown bar (purchases, replacements, washing, admin vs contract price);
  - every figure has a badge + range + an explain drawer.
- The customer audience shows the comparison but not the inputs form. The contract price is shown only if entered.
- Exports: a PPTX slide and PDF section "Service vs do-it-yourself" (inserted after Footprint), an Excel sheet `DIY comparison` + `Inputs` (with sources), and a pitch deck mention on slide 4/6.
- Tests:
  - defaults produce non-None DIY costs for NorthStar;
  - contract price absent → net None; present → net = DIY total − price;
  - a KAM override changes the value and marks provenance KAM_INPUT;
  - switching the baseline changes the washing-cost formula;
  - invalid input → 422;
  - the customer audience hides the inputs;
  - export contains the comparison;
  - with extensions on, hotel inputs are independent of NorthStar's.

### 8a.4 Decisions from the builder check (all [Call]; these override §8a.1–8a.3 where they differ)
1. **Ranges:**
   - low = the most conservative DIY cost: every input at its low, and the baseline factor at the low sensitivity (×0.85, which also scales the kWh/kg and l/kg used in the washing-cost formula). high = the opposite.
   - This mirrors the savings: low = the smallest benefit for Lindström. Reuse the existing per-sensitivity loop.
   - A KAM-entered value is fixed across low/base/high, unless the KAM also enters `<key>_low` / `<key>_high`.
2. **Period scaling:**
   - per-kg inputs are not scaled (washed_kg is already for the period);
   - admin = sites with activity in the period × admin_h_per_site_month × number of months in the period × labour cost;
   - annual items (contract price, garment purchases) × months/12;
   - garment purchases = garments_allocated (period-end snapshot) × weighted purchase cost ÷ garment_life_years_no_repair × months/12.
3. **Weighted purchase cost:** weighted by period-end allocated pieces per product. The extra-replacements cost uses each product's own purchase cost from the repairs rows. Extending `metrics/frames.py` to carry the product cost on repairs is allowed if needed.
4. **Inputs in the review:**
   - `build_review` reads the stored inputs for the account;
   - a hash of the effective inputs is included in `run_id`, so the narrative cache and exports invalidate when inputs change;
   - the DTO is a new ReviewModel field `dto` = {baseline, inputs[{key,label,value,low,high,unit,source:"default"|"kam",entered_at,assumption_id}], lines[{id,label,diy: MetricResult}], diy_total: MetricResult, contract_price: MetricResult|null, net: MetricResult|null, convenience{staff_hours_freed: MetricResult, on_time_rate, utilisation, service_requests_per_100w}, hygiene_note|null};
   - the narrative and observations are unchanged in this round.
5. **No new Provenance value.** Avoid the enum ripple. Instead, DTO results list the input assumption ids in `assumptions`, and `dto.inputs[].source` shows default vs KAM. The UI shows a "uses figures entered by the account manager" chip when any source is "kam". (This replaces the KAM_INPUT provenance in §8a.1.)
6. **Assumption ids:**
   - T3 = Mats factors (§9a);
   - T4–T11 = the eight defaulted inputs, in table order (local_laundry … garment_life);
   - the contract price is not an assumption, so it has no id.
7. **B_HOME:** employee time is a separate line, "Employee time (if washing happens on paid time)", and it **is** included in the DIY total. Only the selected baseline's formula is applied, so nothing is double-counted.
8. **Customer audience:**
   - the inputs are shown read-only (credibility: the customer sees what was assumed);
   - the edit form is KAM-only, enforced in the UI;
   - PUT has no auth in the prototype, which is a stated limitation;
   - the contract price is shown in the customer view only if entered.
9. **Validation:** allowed keys are each input key plus `<key>_low` / `<key>_high`. Anything else, negative numbers, or low > high → 422.

## 9. Left to the builder
reportlab layout details; exact CSV column order (must match canonical names); the synthetic volumes for the extension pack (within the C1 constraint); the pitch deck's visual details; the fit page's styling (reuse existing card/table styles).

## 9a. Decisions from the builder check (all [Call])

1. **NorthStar stays Workwear-only.** Mats are rented only by Baltic Harbour Hotels. This keeps every existing NorthStar/Apex/Mediora figure, fixture, doc number and test unchanged, even with extensions on. The "new service line for an existing customer" case is covered by the proof test (§4.2), which adds Washroom rows to an existing account. **This replaces the NorthStar-mats bullet in §4.1.**
2. **Mats in the engine:** mats are washed by kg in the same laundries, so the per-kg allocation and the existing baseline factors apply. This is a new team assumption **T3**: "Mats use the same per-kg baseline factors as workwear — illustrative", confidence Low, added to assumptions/v1.yaml.
   - Mats rows carry `active_wearers = 0` (no wearers). Wearer de-dup (max per site-month) is unaffected when workwear rows exist.
   - For a Mats-only filter, per-wearer metrics are None via the existing None-safe division. The rules skip None, and the template omits None clauses (already built).
   - Mats have allocated/scanned pieces (synthetic RFID) and service cycles, so utilisation and on-time work.
   - If a mats-only filter exposes a code path that crashes, fixing that crash is allowed. It's a bug fix, not an extension change.
3. **Laundry for the hotel:** L002 Aurora Turku WWS serves all 5 hotel sites, including Estonia. L002 washes 78–95 t per month in the main pack. The hotel's synthetic volume is ≤ 15 t per month, so C1 stays clean. Cross-border delivery isn't distance-modelled (delivery emissions are allocated per kg, A003); this is listed as a limitation. The proof-test pack includes its own `laundries.csv` and `laundry_resources.csv` (a new Riga laundry), so the CSV file list gains these optional files.
4. **Multi-source merge:**
   - Ids must be unique across sources. A duplicate dimension id from a later source is an ERROR row in quarantine ("duplicate key from source X"); the first source wins.
   - `load_pack(path, ...)` stays as a backward-compatible wrapper. The new `load_sources(config_path=None, ...)` reads `config/sources.yaml`.
   - The main pack path in sources.yaml defaults to `VR_PACK_PATH` (env still honoured).
   - The CSV adapter: source_id = the folder name (e.g. `extension_pack`), tier 0, approved False, system "CSV".
5. **Peers and baselines:** peer rules use the account's sites regardless of service line (same as today). B_LOCAL stays the default baseline for Hospitality.
6. **No new country filter.** Estonia shows in the header countries, the site table and the fit page. (A country filter can be a later extension.)
7. **reportlab** is added to pyproject dependencies. An empty chart in the PDF gets the same placeholder text as the PPTX. The pitch deck's headline figures come from a NorthStar review (all service lines, base sensitivity, B_LOCAL), rendered with `fmt_value`.
8. **Existing tests:** `tests/conftest.py` sets `VR_EXTENSIONS=off` for the existing suite, so the 3-account assertions stay valid. New extension tests switch it on explicitly. `excel_pack.py` keeps "Workwear" as its service line, which is now correct by definition.

## 10. Open for the user
- Whether to also hand the API key over for a live AI demo (separate; not needed for this round).
