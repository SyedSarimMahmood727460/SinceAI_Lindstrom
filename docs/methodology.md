# Methodology note

**Prototype · synthetic data · not audited.** All inputs are the synthetic Lindström × Since AI data pack. Baseline factors are illustrative placeholders. Nothing in this prototype is audited, verified or suitable for CSRD or other regulatory reporting.

This note describes what the code does (`metrics/`, `config/assumptions/v1.yaml`, `config/metrics.yaml`, `config/service_catalogue.yaml`, `config/relatable.yaml`, `ai/intel.py`). Only the metric engine produces numbers. The dashboard, the PowerPoint, PDF and Excel exports, the pitch deck and the AI layer read one `ReviewModel`; the AI never writes a figure.

## 1. Boundary

- **In scope:** the Lindström textile rental service delivered to the selected customer account and its sites (in the pack: workwear only; the synthetic extension pack adds mats, see section 14). A service-line filter restricts every metric to one service line.
- **Footprint:** laundry fresh water, process energy and process CO2e, plus delivery CO2e, allocated to the customer by washed kg (section 4).
- **Baseline:** the selected alternative way of doing the same washing (section 2), applied to the same washed kg.
- **Handprint:** repairs completed and the product replacements they may postpone (section 6). Shown separately.
- **Not covered:** product manufacturing footprint inside the washing saving, customer commuting, end-of-life beyond the four waste routes in the pack.

## 2. Baselines and factors

The default baseline is `B_LOCAL`. The other two are selectable in the header. Factors come from the pack's `Baselines` sheet and are stored in `config/assumptions/v1.yaml`.

| Baseline | Water (l/kg) | Energy (kWh/kg) | Process CO2e (kg/kg) | Delivery CO2e (kg/kg) |
|---|---|---|---|---|
| B_LOCAL: outsourced local laundry (default) | 9.5 | 1.05 | 0.62 | 0.035 |
| B_HOME: home washing | 20 | 1.18 | 0.78 | 0 |
| B_INHOUSE: in-house customer laundry | 12.5 | 1.12 | 0.68 | 0.015 |

All three assume no systematic repair and 100% mixed-waste treatment of textile waste (A004). The factors are illustrative until approved.

For each baseline: `baseline_X = washed_kg × factor_X × s`, where CO2e uses process plus delivery.

## 3. Footprint versus handprint

- **Footprint (washing):** the saving is `baseline − allocated` for water, energy and CO2e. A positive value means the Lindström service used less than the baseline for the same kg of textile.
- **Handprint (repair):** postponed replacements and the product footprint they avoid. This depends on a different assumption (A002) and a different data source.
- **The two are never summed into one headline figure.** Washing savings and repair (product) savings answer different questions and have different uncertainty. The code keeps them in separate metrics (`co2_saving_kg`, `postponed_product_kgco2e`) and the UI and deck present them apart.

## 4. Allocation (A003)

Laundries wash for several customers, so the laundry's monthly water, energy, CO2e and waste are shared out in proportion to washed kg. The code uses per-kg intensity, which is mathematically the same as "customer share × laundry total":

```
intensity_X(laundry, month) = laundry.X(month) / laundry.washed_kg(month)
allocated_X(row)            = row.washed_kg × intensity_X
```

for X in fresh water, process energy, process CO2e, delivery CO2e and each waste route. This is implemented in `metrics/frames.py`, row by row (site × product × laundry × month), then summed. The tests reconcile it against the pack's reference sheets (`Customer_Impacts`, `Sample_Output`): for NorthStar the CO2e saving is 255,074 kg against the reference 255,073 kg, and the water saving is 1,406,620 l against 1,406,483 l. These reference sheets are used only as test fixtures, not as inputs.

Allocated values carry the status `ALLOCATED` (confidence Medium).

## 5. Sensitivity (T1)

The engine always computes low, base and high and returns all three.

| | Low | Base | High |
|---|---|---|---|
| Multiplier on baseline factors | 0.85 | 1.00 | 1.15 |
| Replacements postponed per repair | 0.25 | 1.0 | 1.0 |

The multiplier is applied to the baseline factors **before** subtracting the allocated actuals: `saving = washed_kg × factor × s − allocated`. It is not applied to the saving afterwards. The allocated actuals are not scaled.

Consequence: the saving is a small difference between two large numbers, so ranges are wide, especially for water. For NorthStar against local laundry in 2025 (all synthetic):

| Metric | Low | Base | High |
|---|---|---|---|
| CO2e saving | 205.7 t | 255.1 t | 304.4 t |
| Water saving | 0.69 million l | 1.41 million l | 2.12 million l |

The selected sensitivity in the header picks which of the three becomes the headline value. Estimated values are always shown with their range.

## 6. Repair range (A002)

The pack's assumption A002 is that one completed repair postpones one replacement. We treat this as the **upper bound**, not the central case: the range is 0.25 to 1.0 replacements per repair (low 0.25, base 1.0, high 1.0). It is therefore an asymmetric range, shown as "0.25-1.0 (A002 = upper bound)". `replacements_postponed = repairs × r` and `postponed_product_kgco2e = Σ_products repairs × product footprint × r`. Both are `ESTIMATED`, confidence Low-Med. Product footprints are synthetic (A005, confidence Low). The repair count itself (for NorthStar 15,233 in the pack) is calculated from the source and not estimated.

## 7. Wearer de-duplication (T2)

The pack's `Service_Activity` has one row per site × product × month, and the same wearer can appear in several product rows. Summing rows would double count (the pack sample gives 28,367 for NorthStar in December 2025). We take `wearers(site, month) = max(active_wearers across product rows)`, sum over sites for the account, and report the snapshot at the last month of the period. For NorthStar December 2025 this gives **9,607**. The "per 100 wearers" ratios use the monthly average of the de-duplicated count.

This is an assumption (T2), not a measurement. It assumes no wearer works at two sites and that a wearer wears at least the product with the highest count. It needs confirmation from the data owner. Metrics that use it list T2 in their assumptions.

## 8. Roll-up rules

- Additive metrics are summed from the lowest grain (site × product × laundry × month).
- Ratios (utilisation, recycling rate, per-100-wearers) are recomputed from summed numerators and denominators at each level. Percentages are never averaged.
- Snapshots (wearers, garments allocated) use the last month of the period.
- Filters (quarter, product, site) re-run the same calculation on the filtered rows. A filter with no rows gives `value = None` and the UI and deck show "No data for this filter".

## 9. Status labels and confidence

Two labels on every value:

- **method_status**, strongest to weakest: `MEASURED` (read directly from a source system), `CALCULATED` (derived arithmetically from measured data), `ALLOCATED` (shared laundry data allocated by washed kg), `ESTIMATED` (depends on an assumption, baseline or sensitivity). A derived value takes the weakest status of its inputs. The pack adapter tags source rows `CALCULATED`, as the pack does not say whether values are measured.
- **provenance**: `SYNTHETIC`, `PUBLIC_REFERENCE`, `APPROVED_REAL`. Every value in this prototype is `SYNTHETIC`. A derived value takes the weakest provenance of its inputs. Public-reference facts are context only and not calculation inputs.

Each metric also has a confidence level (High, Medium, Low-Med, Low) set in `config/metrics.yaml`. A metric derived from data that failed a WARNING check (section 10) is lowered by one level and flagged with a warning icon.

## 10. The C1 finding: laundry L003

After loading, the pipeline runs cross-source consistency checks and records each failure as a WARNING (not an error: the rows stay usable).

**C1, laundry volume:** the sum of customer washed kg routed to a laundry, per month, should not exceed that laundry's own washed kg. The pack fails this for **laundry L003 (Nordic Malmö WWS)**: customer kg routed to it totals 335,824 kg in 2025, against 31,017 kg reported by the laundry, about 10.8 times as much. It affects all 6 Apex sites and the 6 NorthStar sites in Sweden. (Monthly ratios vary from 9.6 to 12.6 times, for example 11.25 times in January.)

Handling:

- Per-kg allocation (section 4) stays usable, because it needs only the ratio of resources to the laundry's own kg, not a share below 100%. We have no evidence which of the two volume figures is wrong.
- Every metric derived from allocation (allocated water/energy/CO2e/waste, savings, recycling rate, and everything built on them) gets confidence lowered by one level and a warning icon. For NorthStar and Apex the headline savings show "Low".
- Observation R8 ("Laundry volume data needs confirmation") fires for any account touching a flagged laundry. It sorts last and is not turned into an action. It asks Lindström to confirm the laundry volume data before the figures are used externally.
- The Data readiness page and `/data-quality` list the warnings. Open question **Q35** to Lindström: is the L003 volume gap deliberate or an error?

Two further checks run as WARNING: C2 (a site's primary laundry matches the laundry in its activity rows) and C3 (wearers not above allocated pieces). Rows with ERROR-level problems (unknown site, product, laundry or customer; missing key; invalid month; non-numeric or negative measure; site not belonging to the stated customer) are never loaded: they go to the `quarantine` table with a reason and are never silently dropped. The pack itself has no ERROR rows. Setting `VR_INJECT_BAD_ROWS=1` injects three to demonstrate the quarantine.

## 11. What the AI does and does not do

- The intent parser maps a typed request to priorities, customer, baseline, sensitivity and view. Unknown ids are dropped. If nothing is recognised the view stays unchanged and the message starts "Not recognised". A keyword matcher is the fallback.
- The narrator drafts the executive summary and 5 discussion points. It must write numbers only as placeholders (for example `{{co2_saving_kg.base}}`), which the renderer fills from the `ReviewModel`. A guard rejects any text with a digit outside a placeholder, an unknown placeholder, or a banned phrase ("carbon neutral", "net zero", "CSRD-compliant", "audited", "verified", "guaranteed"). On rejection it retries once, then uses the template narrative. Each narrative block records `generated_by` as `llm` or `template`.
- With no API key, `VR_AI=off`, a timeout (15 s) or repeated guard failure, the template narrative is served and the product behaves the same apart from the wording.
- Account intelligence (section 17) is separate research on a real public company; no engine number is mixed in.

## 12. Service vs do-it-yourself (`metrics/dto.py`)

What the customer would spend doing the same itself under the **selected baseline**, line by line, in EUR, plus the staff hours the service frees. Every figure is `ESTIMATED` with a low/base/high range. Euros, hours and CO2e are kept separate and never summed into one score.

**Inputs ("Your numbers").** Defaults live in `config/assumptions/v1.yaml` under `dto_inputs` (illustrative Nordic values, confidence Low). The account manager can overwrite any of them per account (`PUT /accounts/{id}/inputs`). An entered value applies to low, base and high unless the KAM also enters `<key>_low` / `<key>_high`. Each input shows its source: default (with its assumption id) or entered by the account manager, with the date.

| Id | Input | Default (low – high) |
|---|---|---|
| — | Lindström contract price (EUR/year) | **none**: no net comparison until entered |
| T4 | Local laundry price | 2.5 (1.8 – 3.5) EUR/kg |
| T5 | Energy price | 0.15 (0.10 – 0.25) EUR/kWh |
| T6 | Water price | 4 (3 – 6) EUR/m³ |
| T7 | Detergent & chemicals | 0.05 (0.03 – 0.08) EUR/kg |
| T8 | Staff cost | 30 (25 – 40) EUR/h |
| T9 | Washing & handling time (in-house / home) | 3 (2 – 5) min/kg |
| T10 | Garment admin time without service | 4 (2 – 8) h/site/month |
| T11 | Garment life without repair service | 2 (1.5 – 3) years |

**Lines** (period-scaled; `m` = months in the period):

- **Garment purchases** = garments allocated (period end) × purchase cost weighted by allocated pieces per product ÷ garment life without repair (T11) × m/12.
- **Extra replacements without repairs** = Σ over products of repairs × replacements per repair (T1) × product purchase cost. **Shown for explanation, not added to the total**: garment purchases already use the shorter no-repair life, so adding these would count the same garments twice.
- **Washing cost**, by baseline:
  - B_LOCAL: washed kg × local laundry price (T4);
  - B_INHOUSE and B_HOME: washed kg × (baseline kWh/kg × s × energy price (T5) + baseline l/kg × s ÷ 1000 × water price (T6) + detergent (T7)), with s the sensitivity factor (T1).
- **Staff washing & handling time** (B_INHOUSE) or **Employee time, if washing happens on paid time** (B_HOME) = washed kg × handling min/kg (T9) ÷ 60 × staff cost (T8). Only the selected baseline's formula is applied, so nothing is counted twice.
- **Garment admin** = sites with activity × admin h/site/month (T10) × m × staff cost (T8).
- **Do-it-yourself total** = the sum of the lines in the total. If a line has no data, the total is marked partial.
- **Net** = do-it-yourself total − contract price, **only if a contract price was entered**. Otherwise the page says "Enter the contract price to see the net comparison".

**Ranges.** low = the cheapest do-it-yourself case: every input at the end that minimises the cost (for garment life, the longest life) and the low sensitivity (baseline factors × 0.85, also applied to the kWh/kg and l/kg in the washing formula; 0.25 replacements per repair). high = the opposite. This mirrors the savings: the low end is the smallest benefit for Lindström.

**Convenience.** Staff hours freed = washing/handling hours (in-house, home) + admin hours, plus the existing on-time rate, utilisation and service requests per 100 wearers. For Food & Beverage and Healthcare a qualitative hygiene note is shown ("context, not compliance advice"). **Environment** uses the existing savings (section 3).

Example (NorthStar, 2025, B_LOCAL, defaults, all synthetic): do-it-yourself total about 1,957,510 EUR (1,363,310 – 2,739,773 EUR); staff hours freed 1,152 h (24 sites × 4 h × 12 months). Extra replacements without repairs, 660,082 EUR, are shown but not in the total.

The inputs enter the review's `run_id` (a hash of the effective inputs), so narrative caches and exports refresh when they change. The customer audience sees the inputs read-only; the edit form is for the account manager only (enforced in the UI; no auth in the prototype).

## 13. Growth opportunities (`metrics/growth.py`)

The extra value if the customer moves more to Lindström. The account manager enters up to three levers (stored with the inputs): `extra_sites`, `extra_wearers` and `extra_service_lines` (from the service catalogue), plus an optional `expansion_price_eur_per_site_year`. Every figure is per year (period values × 12 ÷ months), `ESTIMATED`, with a low/base/high range in the same direction as section 12. Sizing is account-wide (review filters do not apply). For each lever and in total it shows: do-it-yourself cost avoided (EUR), staff hours freed, CO2e saving and water saving, never one combined score.

- **More sites:** each current figure ÷ current sites × extra sites.
- **More employees:** each current figure ÷ current active wearers × extra wearers. Garment admin is driven by sites, not wearers, so it is excluded from the per-wearer cost and hours. If both sites and employees are entered, a note warns that the two may overlap.
- **A service line not yet used:** typical kg per site per month from `config/service_catalogue.yaml` × (current + extra sites) × 12, valued with the baseline's do-it-yourself washing cost per kg and the account's own CO2e and water saving per washed kg; staff hours use the handling time (T9) only when the baseline has customer-side washing. **A line the customer already uses is skipped** and listed as "already used by this customer".
- **Net:** only when an expansion price was entered: cost avoided − Lindström price (per site and year × extra sites; per wearer derived from the per-site price; for a service line, kg × the catalogue price per kg, with the conservative low end using the high price).

Service catalogue defaults (illustrative, confidence Low):

| Id | Service line | Typical kg/site/month (low – high) | Typical price EUR/kg (low – high) |
|---|---|---|---|
| T12 | Workwear | 1,500 (800 – 2,500) | 3.0 (2.2 – 4.0) |
| T13 | Mats | 100 (50 – 200) | 4.0 (3.0 – 5.5) |
| T14 | Washroom | 60 (30 – 120) | 3.5 (2.5 – 5.0) |
| T15 | Cleanroom | 200 (100 – 400) | 8.0 (6.0 – 12.0) |
| T16 | Hospitality textiles | 2,000 (1,000 – 4,000) | 1.8 (1.4 – 2.5) |

The narrative line is code-filled: "Bringing {levers} on board would avoid about {range} a year in laundry and garment costs and save {CO2e range}."

## 14. Mats (T3)

Mats are washed by kg in the same laundries, so per-kg allocation applies. Assumption **T3** (confidence Low): mats use the same per-kg baseline factors as workwear; replace with mat-specific factors for production. Mats rows carry `active_wearers = 0`, so wearer de-duplication (T2) is unaffected when workwear rows exist, and per-wearer metrics for a Mats-only filter are `None` ("No data for this filter"). This is expected, not an error.

## 15. Relatable comparisons (`config/relatable.yaml`)

The customer story turns two savings into everyday terms: value ÷ factor, rounded to 2 significant figures, prefixed "≈" and always labelled "illustrative comparison". They are never inputs to a calculation. A comparison is omitted when the ratio is below 1. The car factor is CO₂ only while the saving is CO₂e, so that comparison is approximate.

| Metric | Factor | Derivation | Sources |
|---|---|---|---|
| Water saving | 100,156 l per Finnish household per year | 140 l per person per day × 365 × 1.96 persons per household | Motiva figure as quoted by Cozify; Statistics Finland (household size 2020) |
| CO2e saving | 1,908.2 kg CO2 per average Finnish passenger car per year | 136.3 g/km × 14,000 km | Traficom average via OpenCO2.net (2025); Traficom emissions calculator default mileage |

Example (NorthStar, 2025, B_LOCAL): ≈ 14 households' yearly water use and ≈ the yearly CO₂ emissions of 130 cars (car figure CO₂ only; the saving is CO₂e).

## 16. Customer story and Simple mode

The landing page shows up to five cards (value delivered, versus doing it yourself, biggest improvement, growth opportunity, what's next). Each statement is a template filled from the `ReviewModel` ("about X (between A and B)"), with a "What to say" line for the account manager. Simple mode (the default) replaces status badges with one "estimate" pill and hides z-scores, lineage and formulas; Expert mode shows everything. Ranges are visible in both.

## 17. Account intelligence guardrails (`ai/intel.py`)

- **Live path:** Claude (`claude-sonnet-5-5`) with the Anthropic server-side web search tool (at most 5 searches, 60 s overall timeout), asked for recent public sources. The answer must come through a `submit_report` tool with a JSON schema.
- **Code-side filtering:** a claim is kept only if its source URL was **actually returned by the web search** in that session, is a safe http(s) address, and has a date (YYYY, YYYY-MM or YYYY-MM-DD). A "How Lindström can help" item is kept only if it names an offer in `config/service_catalogue.yaml` and cites at least one such searched source. If no sourced claim survives, the report is rejected. The sources list always covers every cited URL. The disclaimer is always the code's own.
- **No engine numbers** are mixed in, and the report never claims the company is a Lindström customer ("Example public company; no relationship with Lindström is implied").
- **Cache and fallback:** live results are cached per company for 7 days (`data/intel_cache/`, gitignored). With no API key, `VR_AI=off`, or a failed call, the committed snapshot is served (Fazer Group, researched 2026-11-07, every claim with its source and date). The **snapshot chips and the page's automatic first open request the snapshot directly and never call the API**; only the Research button can start live research.
- The fictional customers (NorthStar, Apex, Mediora) have no public footprint; the page says so and offers the example company. In production the account's legal name would come from CRM.

## 18. Limitations

- All data is synthetic. Figures illustrate the method and are not claims about Lindström or any customer.
- Baseline factors are illustrative and need approval or replacement by customer-specific or public emission factors before external use.
- Savings are small differences between large numbers: ranges are wide, water especially. They reflect only the stated sensitivity, not every source of error.
- Postponed replacements are an assumption, not an observed outcome. A002 is an upper bound.
- Wearer counts depend on de-duplication assumption T2. Utilisation (scanned versus allocated) is described as "not scanned in use", never "lost", as the meaning of the gap is unconfirmed.
- The L003 volume inconsistency is unresolved (Q35). Allocated figures for the affected sites are less certain.
- "On time" uses the pack's `LATE` flag as supplied; its definition is unconfirmed.
- Idle stock value (`idle_stock_value_eur`) is an internal estimate, not customer-facing. It is hidden when the audience is set to customer and absent from the PPTX.
- Delivery-customer level of the hierarchy is missing in the pack, so sites hang directly under the account.
- The do-it-yourself defaults (T4–T11) and the service catalogue sizing (T12–T16) are illustrative, not market data. The comparison is only as good as the inputs; the customer should check them. The net comparison depends entirely on the contract price entered.
- Growth sizing scales the customer's current averages; new sites or employees may differ, and the site and employee levers can overlap.
- Mats use workwear baseline factors (T3). Cross-border delivery (the Estonian hotels served from Turku) is not distance-modelled; delivery emissions are allocated per kg (A003).
- The inputs API has no authentication in the prototype; the edit form is hidden from the customer view in the UI only.
- Account intelligence is AI-generated from public sources and can be incomplete or out of date: verify before use. It is not advice about the company.
- Relatable comparisons are illustrative only.
- Not audited. Not suitable for CSRD or other regulatory reporting. Wording rules require "saved" or "avoided" to be qualified as "vs {baseline} (estimate)".
