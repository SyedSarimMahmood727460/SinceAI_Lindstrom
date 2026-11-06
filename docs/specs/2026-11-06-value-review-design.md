# Value Review — Design Spec

Lindström × Since AI Hackathon 2026 · Challenge: *Customer Value & Sustainability Review Generator*
Status: **draft for approval (solo scope)** · Date: 2026-11-06 · Submission deadline: **Sun 8 Nov 2026, 10:00 EET**

Legend used in this document:
- **[Brief]**: required by the Lindström challenge brief or data pack
- **[Call]**: a design decision we made; can be overruled
- **[Open Qn]**: depends on a question sent to Lindström (numbering follows our question list); a default is given so the build is never blocked

---

## 1. Intent

Lindström customers ask their key account managers (KAMs) for evidence of the value the textile rental service creates: operational, environmental and circular. The evidence is spread across many datasets and sites. Today it can't be turned into a credible, customer-specific story quickly.

We build **Value Review**: a prototype customer-value module that turns multi-source, multi-site data into a **dynamic Customer Value & Sustainability Review**. It is used in annual reviews and steering committees, by the KAM and the customer decision-maker. It is designed to plug into approved Lindström data sources later and to become a module of eLindström.

**Why it wins** [Brief, §06 judging]: transparent and defensible numbers, relevant to the customer and their industry, with actionable next steps and a credible path to production. The size of the claimed savings is not what wins.

## 2. Users and core scenario

| User | Need |
|---|---|
| KAM (primary) | Prepare an annual review for a multi-site customer in minutes; tailor it to the customer's priorities; export a customer-ready deck |
| Customer decision-maker | Understand value received, compare with an alternative, agree improvements |
| Lindström sustainability specialist | Trust the method: baseline, boundaries, assumptions, data status |

**Demo scenario** (main fictional customer **NorthStar Foods Group**: Food & Beverage, 24 sites in FI/SE/PL) [Brief]:
1. The KAM opens NorthStar. The overview is already prioritised by the customer's stated topics plus the food-industry rules: water, then service (hygiene, continuity), then emissions.
2. The KAM types *"Focus on water and emissions"*. The view reorders and the observations change.
3. The KAM drills into an outlier site (e.g. Gdańsk, service requests far above peers) and opens the evidence and formula.
4. The KAM switches the baseline (local laundry → home washing) and watches the savings ranges change.
5. The KAM opens the steering-committee pack, then exports the PPTX.
6. The KAM switches to **Apex Industrial** (Manufacturing). The emphasis changes to cost and repairs, which shows industry awareness.

## 3. Goals, non-goals, anti-goals

**Goals** (each maps to a brief deliverable [Brief §07]):
- G1 An interactive dashboard: customer-level aggregation plus site drill-down, period filter (year or quarter), baseline selection, product filter.
- G2 A customer-ready PPTX review (PDF too).
- G3 Personalisation by priority or prompt, for at least 2 priorities and at least 2 industries.
- G4 At least 3 observations or recommendations with evidence, plus steering-committee discussion points.
- G5 Visible credibility: every figure shows how it was derived and where the data came from, its baseline, assumptions, low/base/high range and limitations.
- G6 A methodology note and a data-readiness note.
- G7 An architecture with a credible path to approved real sources, larger customers, more industries, countries and service lines.

**Non-goals** (designed for, not built):
- Real Lindström data connections; authentication and SSO; multi-tenant hosting; embedding in eLindström.
- Solving the enterprise customer-master-data problem [Brief].
- Audited or CSRD-grade reporting [Brief].

**Anti-goals** (failure even if it works):
- Any number shown that the deterministic engine did not compute (including numbers made up by an LLM).
- Synthetic values presented as real, or estimates presented as measured.
- Maximising claimed savings; showing a single point estimate without a range for estimated values.
- Washing savings and repair (product) savings added together into one headline figure.
- A dashboard and a deck that disagree.

## 4. Constraints

- Time: build from Fri evening to Sun 10:00. A feature freeze at Sat 23:00 is recommended.
- Data: only the supplied synthetic pack (`Lindstrom_SinceAI_Customer_Value_Synthetic_Data_Pack.xlsx`). Public-reference facts are context only, never calculation inputs [Brief].
- Must run locally with one or two commands. A hosted demo is optional.
- Submission: repo, YouTube demo video, source .zip, accept IP terms in sinceai.app [event rules].
- No personal data; LLM calls send only aggregated, synthetic metrics.

## 5. Architecture

Three diagrams were agreed in the session: (1) layered overview, (2) request flow, (3) canonical data model. They are summarised here.

```
Sources (Tier 0 pack · Tier 1 BI/eLindström exports · Tier 2 warehouse)
   → Source adapters (one per source; validate; quarantine)
   → Canonical data model (DuckDB)            ← Config store (assumption set, versioned)
   → Metric engine (registry + scenarios) → Insight engine (rules + industry config)
   → Review API (one ReviewModel per request) ↔ AI layer (intent parser, narrator)
   → Web dashboard · PPTX/PDF export · (future) eLindström embed
```

**Architectural principles** [Call]:
- P1 **The data contract is the centre.** Nothing after the adapters knows which source the data came from.
- P2 **Single source of numbers.** Only the metric engine produces numbers. Dashboard, export and AI all consume one `ReviewModel`.
- P3 **Two labels on every value:** `method_status` ∈ {MEASURED, CALCULATED, ALLOCATED, ESTIMATED} and `provenance` ∈ {SYNTHETIC, PUBLIC_REFERENCE, APPROVED_REAL}. A derived value takes the weakest of its inputs, in that order.
- P4 **Configuration over code** for baselines, sensitivity, industry rules, metrics and dashboard modules.
- P5 **Reproducible.** `run_id` = hash(input load ids + assumption-set version + request parameters).
- P6 **AI is optional and guarded.** Everything works with the AI switched off, using rule templates.

**Tech stack** [Call, solo]: Python 3.12 · pandas + DuckDB · pydantic v2 · FastAPI · python-pptx · Anthropic SDK (`claude-sonnet-5-5`) · pytest. **Frontend = the approved mockup evolved into a static single-page app (vanilla JS + Chart.js) served by FastAPI that reads the ReviewModel from the API**. No React/Vite build step. The module registry stays (JSON config read by the page), so the architecture is unchanged; only the framework is lighter. React is listed as the production frontend in the scalability story.

**Repo layout:**
```
value-review/
  adapters/      excel_pack.py  (base.py: Adapter interface)
  model/         schema.py (pydantic row contracts) · ddl.sql · load.py
  config/        assumptions/v1.yaml · industry_rules.yaml · metrics.yaml · modules.yaml · wording_rules.yaml
  metrics/       registry.py · engine.py · scenarios.py · rollup.py
  insights/      rules.py · discussion.py
  ai/            intent.py · narrator.py · guard.py · templates.py
  api/           main.py · review_model.py
  export/        pptx_builder.py · template.pptx · pdf.py
  web/           index.html · app.js · modules.js · styles.css  (served by FastAPI at /)
  tests/         test_reconciliation.py · test_metrics.py · test_insights.py · test_guard.py · test_api.py
  docs/          specs/ · methodology.md · data_readiness.md · demo_script.md
```

## 6. Data contract (canonical model)

### 6.1 Dimensions
| Table | Key | Fields | Pack source |
|---|---|---|---|
| `org_node` | node_id | parent_id, level ∈ {ACCOUNT, DELIVERY_CUSTOMER, SITE}, name, industry, segment, country, city, site_type, primary_laundry_id, priority_topics[] | Customers (→ ACCOUNT), Sites (→ SITE). The pack has no delivery-customer level, so sites hang directly under the account [Call] |
| `product` | product_id | name, product_group, service_line (= "Workwear" for all pack rows), weight_kg, footprint_kgco2e, purchase_cost_eur | Products |
| `laundry` | laundry_id | name, country | Laundries |
| `source` | source_id | name, tier, system, approved, loaded_at, load_id | generated by adapter |

### 6.2 Facts (each row also carries `method_status`, `provenance`, `source_id`, `load_id`)
| Table | Grain | Measures | Pack source |
|---|---|---|---|
| `fact_service_month` | site × product × laundry × month | active_wearers, allocated_pieces, active_assets_scanned, washed_pieces, packed_pieces, washed_kg, service_requests | Service_Activity |
| `fact_service_cycle` | asset × cycle | pickup/in/out/delivered timestamps, cycle_hours, performance_flag; derived month = month(pickup) | Service_Cycles |
| `fact_repair_month` | site × product × laundry × month × repair_type | repair_count | Repairs (repair_count only; the pack's derived columns are not ingested) |
| `fact_laundry_month` | laundry × month | washed_kg, fresh_water_l, process_energy_kwh, process_kgco2e, delivery_kgco2e | Laundry_Resources |
| `fact_waste_month` | laundry × month × route ∈ {recycling, reuse, energy_recovery, incineration} | kg | Waste_Circularity (unpivoted) |

**Not ingested as data:** `Customer_Impacts`, `Sample_Output` and the derived columns in `Repairs`. They are **reconciliation fixtures** (§12). We recompute these values ourselves.

### 6.3 Config (versioned `assumption_set`, YAML)
- Baselines: B_LOCAL (default), B_HOME, B_INHOUSE, with factors from the pack's `Baselines` sheet.
- Sensitivity: `low|base|high` multipliers on baseline factors = 0.85 / 1.00 / 1.15 [Call, T1]. Replacements postponed per repair = 0.25 / 1.0 / 1.0 [Call; A002 sets 1.0; Open Q11].
- Assumption register A001–A008 from the pack, plus team assumptions T1 (sensitivity) and T2 (wearer de-duplication).
- Industry rules: from `Industry_Priorities`, mapped to our 5 priority keys (§9.2).
- Wording rules: banned or caveated phrases (§10.4) [Open Q12].

### 6.4 Ingestion rules
- Each adapter implements `extract() → raw frames`, `map() → canonical frames`, `validate() → (valid, quarantine)`.
- Validation: required keys present; foreign keys resolve (site, product, laundry, customer); month is `YYYY-MM`; numeric measures ≥ 0; site's customer matches the row's customer.
- Two severities [Call]:
  - **ERROR**: the row can't be used (broken key, bad month, negative value). It goes to the `quarantine` table with a reason. Never silently dropped.
  - **WARNING**: the row is usable but inconsistent. It is loaded with a `dq_flags[]` entry. Every metric that uses it has its confidence lowered by one level and shows a warning icon. Listed in Data Readiness.
- Cross-source consistency checks (WARNING), run after loading:
  - **C1 laundry volume:** Σ customer washed_kg routed to a laundry ≤ that laundry's washed_kg, per month. **The pack fails this for L003 (Nordic Malmö WWS): customer volume = 335,824 kg vs a laundry total of 31,017 kg (10.8×).** This affects all 6 Apex sites and 6 NorthStar Swedish sites. Allocation stays usable because it is per kg (§7.4), but the inconsistency is flagged and shown.
  - C2: every site's primary laundry matches the laundry in its activity rows.
  - C3: wearers ≤ allocated pieces per site-month (informational).
- The pack has **0** ERROR rows. The demo includes a toggle or fixture that injects 3 bad rows (unknown site, missing month, negative kg) to *show* the quarantine working [Call].

## 7. Metric engine

### 7.1 Metric definition (registry entry, `config/metrics.yaml`)
`id, label, unit, priority_tags[], formula (python fn name), inputs[], grain, aggregation ∈ {sum, ratio, snapshot_last, mean}, method_status, confidence, assumptions[], customer_facing (bool), description`

### 7.2 MetricResult (output of every calculation)
```json
{ "metric_id": "co2_saving_vs_baseline", "scope": {"node_id": "CUST001", "level": "ACCOUNT", "period": "2025"},
  "value": 255.1, "unit": "tCO2e", "range": {"low": 205.7, "base": 255.1, "high": 304.4},
  "method_status": "ESTIMATED", "provenance": "SYNTHETIC", "confidence": "Low-Med",
  "assumptions": ["A001","A003","T1"], "lineage": {"facts": ["fact_service_month","fact_laundry_month"], "rows": 288, "load_ids": ["…"]},
  "formula_text": "washed_kg × baseline(process+delivery) × s − allocated(process+delivery)" }
```

### 7.3 Roll-up rules
- **Additive** metrics are summed from the lowest grain.
- **Ratios** are recomputed from summed numerator and denominator at each level. Percentages are never averaged.
- **Snapshots** (wearers, allocated pieces) use the last month of the period. Averages are a separate metric.
- Wearer de-duplication [Call, T2; Open Q16]: `wearers(site, month) = max(active_wearers across product rows)`. Account = Σ sites, assuming no wearer is shared across sites.

### 7.4 Allocation rule [Brief A003]
Implemented as **per-kg intensity**, which is mathematically identical to share × laundry total, but stays meaningful when the data fails check C1 (share > 1):
`intensity_X(laundry, month) = laundry.X(month) / laundry.washed_kg(month)`
`allocated_X(row) = row.washed_kg × intensity_X` for X ∈ {fresh_water_l, process_energy_kwh, process_kgco2e, delivery_kgco2e, waste_kg per route}.
`share` is still computed and stored, for the C1 check and for display.
Verified: this reproduces the pack's `Customer_Impacts` within 1.6% max relative error (rounding in the source).

### 7.5 Metric catalogue (v1)
| id | Formula (per scope, period) | Status | Priority tags | Notes |
|---|---|---|---|---|
| sites | count SITE nodes | CALCULATED | — | |
| active_wearers | Σ_sites max_product(active_wearers), last month | CALCULATED | service | T2; Open Q16 |
| active_wearers_avg | mean over months of the above | CALCULATED | — | denominator for "per 100 wearers" |
| garments_allocated | Σ allocated_pieces, last month | CALCULATED | cost | |
| utilisation | Σ scanned / Σ allocated | CALCULATED | cost, circularity | Open Q18 (meaning of the gap) |
| idle_pieces | mean_month Σ max(0, allocated − scanned) | CALCULATED | cost | |
| idle_stock_value_eur | mean_month Σ idle × purchase_cost | ESTIMATED | cost | customer_facing = false until Open Q20 |
| washed_kg | Σ washed_kg | CALCULATED | water, emissions | |
| washed_kg_per_wearer | washed_kg / active_wearers_avg | CALCULATED | water | |
| washing_pct | Σ washed_pieces / Σ allocated × 100 | CALCULATED | service | |
| on_time_rate | 1 − count(LATE) / count(cycles) | CALCULATED | service | Open Q17 (LATE definition) |
| avg_cycle_hours | mean cycle_hours | CALCULATED | service | |
| service_requests | Σ service_requests | CALCULATED | service | |
| service_requests_per_100w | service_requests / active_wearers_avg × 100 | CALCULATED | service | |
| repairs | Σ repair_count | CALCULATED | circularity | |
| repairs_per_100w | repairs / active_wearers_avg × 100 | CALCULATED | circularity | |
| replacements_postponed | repairs × r(sens) | ESTIMATED | circularity | A002; Open Q11 |
| postponed_product_kgco2e | Σ_p repairs_p × footprint_p × r(sens) | ESTIMATED | circularity, emissions | never added to washing savings |
| allocated_water_l / energy_kwh / co2_kg | §7.4 | ALLOCATED | water / emissions | co2 = process + delivery |
| baseline_water_l / energy_kwh / co2_kg | washed_kg × factor_b × s(sens) | ESTIMATED | water / emissions | |
| water_saving_l / energy_saving_kwh / co2_saving_kg | baseline − allocated, with low/base/high | ESTIMATED | water / emissions | Open Q10, Q13–14 |
| footprint_pct_of_baseline | allocated / baseline × 100 | ESTIMATED | water, emissions | used for the comparison chart |
| textile_waste_kg | Σ allocated waste | ALLOCATED | circularity | |
| recycling_rate | allocated recycling / allocated waste | ALLOCATED | circularity | |
| diverted_from_mixed_waste_kg | allocated (recycling + reuse) | ESTIMATED | circularity | baseline assumes 100% mixed waste (A004) |

All metrics are available at ACCOUNT and SITE level, for the period (2025) and per month (for trends).

### 7.6 Scenarios
A request = (node, period, product_filter, baseline_id, sensitivity). The engine always computes low/base/high and returns all three.
**Range method** [Call]: the sensitivity multiplies the **baseline factors before subtracting** the allocated actuals (`washed_kg × factor × s − allocated`). It is not applied to the saving afterwards. Result: CO₂ 205.7 / 255.1 / 304.4 t and water ≈ 0.69 / 1.41 / 2.12 million l for NorthStar vs local laundry. The water range is wide (≈ ±50%) because the saving is a small difference between two large numbers. This is the honest result, and the UI should explain it in one line.
Repair range: 0.25 / 1.0 / 1.0 replacements per repair. The base equals the pack's A002, which we treat as the upper bound. Shown as "0.25–1.0 (A002 = upper bound)", not as a symmetric range. The selected sensitivity picks the headline. Comparison across all baselines is computed for `co2_saving`, `water_saving` and `energy_saving` (base case).

## 8. Insight engine

### 8.1 Observation object
`id, rule_id, title (template), finding (template), action (template), tags[] (priority keys), scope node_id, evidence: [metric_id + scope pairs], method_status (weakest of evidence), confidence, score`

### 8.2 Rules (v1)
Peer group = the sites of the same account. Requires at least 3 sites. Outlier = |z| ≥ 1.5, or the extreme site when no |z| ≥ 1.5 exists (marked "relative").
| Rule | Signal | Tags | Action template |
|---|---|---|---|
| R1 low utilisation | min utilisation site | cost, circularity | right-size allocation and size mix |
| R2 service-request outlier | max requests per 100 wearers vs peer median (show the multiple) | service | break down by type; agree a target |
| R3 delivery reliability | min on_time_rate site | service | review route, pickup window, delivery day |
| R4 laundry recycling gap | laundries serving the account: max − min recycling_rate ≥ 10 pp (needs ≥ 2 laundries, so in the pack only NorthStar qualifies) | circularity | ask for the laundry roadmap; joint KPI |
| R8 data consistency | any WARNING flag (e.g. C1) touching this account | all | ask Lindström to confirm the laundry volume data before using the figures externally |
| R5 repair intensity | max repairs per 100 wearers | circularity, cost | check product durability fit |
| R6 washing intensity | max washed_kg per wearer | water, emissions | check change frequency vs hygiene needs |
| R7 value headline | account water and CO₂ savings vs baseline, with range | water, emissions | use the range; confirm the baseline with the customer |

### 8.3 Prioritisation
`score = Σ over the observation's tags of weight(tag)`. Weight = 10 − rank of the tag in the active priority list. The active list = user prompt or chips if present, otherwise industry defaults (§9.2). Ties are broken by |z|. The top 4 show on the Overview; all show in the Steering pack.

### 8.4 Discussion points and actions
- 5 discussion points: the actions of the top 4 observations, plus a fixed "reporting" question (baseline agreement and data approval for next year).
- Action table: top 3 observations → owner (template), KPI = the first evidence metric, 2025 value, target (editable in the UI; not persisted in v1 [Call]).

## 9. Personalisation

### 9.1 Priority keys
`water, emissions, cost, circularity, service`. Hygiene maps to service; Scope 3 maps to emissions.

### 9.2 Industry defaults (from `Industry_Priorities`)
| Industry | Default priority order |
|---|---|
| Food & Beverage | service (hygiene, continuity, reliability) → water |
| Manufacturing | cost → circularity → service (safety, availability) |
| Healthcare | service (hygiene, traceability, continuity) → emissions (compliance-ready evidence) [Call] |
The pack's `dashboard_emphasis` text is shown as a one-line "why this view" note.

### 9.3 Inputs, in order of precedence
1. Typed prompt → `ViewSpec` (AI intent parser, keyword fallback).
2. Priority chips (toggle).
3. **The customer's stated priority topics** (`Customers.priority_topics`), as A007 requires [Brief].
4. Industry default (fills in after the customer's stated topics, removing duplicates).

Topic mapping [Call]: Water efficiency → water · Scope 3 evidence → emissions · Cost optimization, Garment utilization → cost · Repair → circularity · Hygiene, Service continuity, Service reliability, Safety, Compliance, Traceability → service.
Resulting defaults: NorthStar → water, service, emissions · Apex → cost, circularity, service · Mediora → service, emissions.

### 9.4 ViewSpec
`{ node_id?, priorities[], baseline_id?, sensitivity?, view? ∈ {overview, sites, footprint, circularity, steering, methodology, readiness}, site_filter? {country?, site_type?}, interpretation_text }`
The UI always shows the interpretation ("Understood: … → priority Water + Emissions, baseline Home washing") so the user can see and correct what the system understood.

## 10. AI layer

### 10.1 Intent parser
- Claude tool use with the `ViewSpec` JSON schema. The system prompt includes the customer list, baseline list and priority keys. It must not invent IDs.
- Validation: unknown IDs → dropped and reported as "not recognised". If nothing is recognised → show the suggested prompt chips.
- Fallback: a keyword matcher (the mockup's logic).

### 10.2 Narrator
- Input: a subset of the ReviewModel (KPIs + top observations + context) as JSON.
- Output: an executive summary (≤ 120 words), observation phrasing, and 5 discussion points. **Numbers are written as placeholders** `{{metric_id.base}}`, `{{metric_id.low}}`, `{{metric_id.high}}` or `{{obs:R2.multiple}}`, and the renderer fills them in.
- Guard (`ai/guard.py`): rejects output that contains any digit outside a placeholder, any unknown placeholder, or any banned phrase. On rejection, retry once, then fall back to templates.
- Every narrative block carries `generated_by ∈ {llm, template}`, shown subtly in the UI.

### 10.3 Q&A (stretch)
A read-only tool-calling agent with the tools `get_metric(metric_id, node_id)`, `list_sites(node_id)` and `explain_metric(metric_id)`. Answers follow the same placeholder and guard rules.

### 10.4 Wording rules (initial; Open Q12)
Banned: "carbon neutral", "net zero", "CSRD-compliant", "audited", "verified", "guaranteed".
Caveat required: "saved/avoided" must be followed by "vs {baseline} (estimate)".

### 10.5 Operations
API key from env `ANTHROPIC_API_KEY`. Timeout of 15 s, then fallback. Prompts and outputs are logged per `run_id` to `logs/`. Only aggregated synthetic metrics are sent.

## 11. API and ReviewModel

### 11.1 Endpoints (FastAPI)
| Method | Path | Returns |
|---|---|---|
| GET | `/accounts` | `[ {node_id, name, industry, site_count} ]` |
| GET | `/accounts/{id}/review?period=2025&baseline=B_LOCAL&sens=base&priorities=water,emissions&site=` | `ReviewModel` |
| POST | `/intent` `{text}` | `ViewSpec` |
| GET | `/metrics/{metric_id}/explain?node_id=` | definition + formula_text + assumptions + lineage |
| POST | `/reviews/export` `{same params as review, format: pptx|pdf}` | file download |
| GET | `/data-quality` | sources, quarantine rows, gaps |
| GET | `/config/assumptions` | the active assumption set |

### 11.2 ReviewModel (pydantic; the contract between all teams)
```
ReviewModel
  meta: run_id, generated_at, node{id,name,industry,segment,countries[]}, period, baseline{id,name,factors}, sensitivity,
        assumption_set_version, sources[{source_id,tier,provenance}], disclaimer
  context: active_priorities[], priority_source ∈ {prompt, chips, industry}, interpretation_text, industry_note
  kpis: [MetricResult + display{rank, module_id}]            # ordered by priority
  sites: [{node_id, name, country, city, site_type, laundry_id, metrics{metric_id: MetricResult}, outlier_flags[metric_id]}]
  trends: {metric_id: [{month, value}]}                       # account level; per site on drill-down request
  comparisons: {baselines: [{baseline_id, name, co2_saving, water_saving, energy_saving}]}
  circularity: {repairs_by_type{}, repairs_by_month[], waste_routes{}}
  observations: [Observation]
  narrative: {exec_summary, discussion_points[], generated_by}
  actions: [{text, owner, kpi_metric_id, value_2025, target_2026: null}]
  methodology: {boundary[], assumptions_used[], limitations[], status_legend[]}
  data_quality: {quarantine_count, gaps[], hidden_modules[]}
```
**A static `review_northstar.json` fixture is committed in step S0**, so the frontend, export and AI work can start before the engine exists.

## 12. Frontend

### 12.1 Pages (same as the approved mockup)
Overview · Sites & drill-down · Footprint & handprint · Circularity & repairs · Steering committee · Methodology & assumptions · Data readiness.

### 12.2 Global header
Customer selector, period (full year 2025 or Q1–Q4), product filter (all or one product group), baseline selector, sensitivity selector, prompt bar + interpretation line, priority chips, suggested-prompt chips, Export button. A persistent synthetic-data banner.

### 12.3 Module registry (`config/modules.yaml`)
Each module has: `id, pack ∈ {general, sustainable, financial}, page, required_metrics[], priority_tags[], industries[]|all, component`.
- Layout: modules on a page are sorted by priority score (§8.3 formula).
- **If a required metric is missing or not customer-facing, the module is hidden and listed in `data_quality.hidden_modules`.**
- The visual style follows Lindström's inspiration mockups: white cards, red accent, KPI row, left nav.

### 12.4 Credibility UI (on every figure)
- A badge for method_status (colour) plus a provenance marker (e.g. a striped badge or "SYN" label for SYNTHETIC).
- Click any KPI or observation → a side drawer with formula_text, inputs, assumptions (linked to Methodology), lineage, and the low/base/high table.
- Estimated values always show their range next to the headline.

### 12.5 Sites page
A sortable table of all sites × key metrics, with outlier dots (|z| ≥ 1.5). Click a row → site detail with KPI cards and monthly trend charts (allocated vs scanned vs wearers; repairs, service requests and late cycles).

## 13. Export (PPTX primary, PDF secondary)

- Built from the same ReviewModel (`run_id` printed in the footer).
- Slides: 1 Cover (customer, period, baseline, focus, synthetic watermark) · 2 Executive summary · 3 Value KPIs (top 8, with badges) · 4 Footprint vs baseline (% of baseline chart + ranges) · 5 Site highlights (top/bottom table) · 6 Observations & next steps · 7 Discussion points + action table · 8 Methodology, assumptions & limitations · 9 Appendix: data readiness.
- Charts: rendered with matplotlib to PNG, or native pptx charts [builder's choice].
- PDF: convert the PPTX with LibreOffice headless if installed; otherwise use an HTML print view of the same content [Call].
- Every number in the deck has its status in a footnote; the deck carries a "Prototype · synthetic data · not audited" footer.

## 14. Documentation deliverables [Brief §07]

- `docs/methodology.md` (and slide 8): baselines, boundary, footprint vs handprint logic, allocation, sensitivity, assumptions, uncertainty, missing data, limitations.
- `docs/data_readiness.md` (and the Data readiness page): field → future Lindström source → status/gap (table from the mockup), and the source-tier roadmap (Tier 0 → 1 → 2 → 3).
- `README.md`: one-command run, environment variables, architecture diagram, how to add an adapter, a metric, a module or an industry rule.
- `docs/demo_script.md`: the 4-minute pitch flow from §2.

## 15. Testing and acceptance

| Test | Pass criterion |
|---|---|
| Reconciliation: allocation | allocated water, energy, CO₂ and waste per row within 2% of `Customer_Impacts` |
| Reconciliation: savings vs local | account totals within 2% of `Sample_Output` (water 1,406,483 l; CO₂ 255,073 kg) |
| Reconciliation: repairs | Σ repairs for NorthStar = 15,233 |
| De-duplication | NorthStar Dec wearers = Σ_site max_product (expected ≈ 9,6xx, not 28,367) |
| Roll-up | account utilisation = Σ scanned / Σ allocated (not the mean of site ratios) |
| Insight rules | NorthStar R2 flags Gdańsk; R1 flags Västerås; R4 flags the Warsaw laundry (based on mockup findings) |
| Guard | narrator output containing a raw digit or banned phrase is rejected and falls back to template |
| API contract | `/review` validates against the ReviewModel schema for all 3 customers × 3 baselines × 3 sensitivities |
| Export | PPTX opens; KPI values identical to the API response for the same run_id |
| Quarantine | injected bad rows appear in `/data-quality` with reasons |
| Consistency warning | C1 flags L003; Apex metrics that use allocation show lowered confidence and a warning icon; R8 fires for Apex and NorthStar |
| Default priorities | NorthStar opens with water first; Apex with cost first |
| Filters | Q1 + product P1004 returns consistent totals (Σ quarters = year) |
| E2E (manual or Playwright) | demo script §2 runs without errors |

## 16. Build steps (input to the implementation plan) — solo builder

**Working model:** one person plus Claude Code. Claude writes the code step by step. The person reviews each step's "done when" check, runs the demo, and owns the Lindström Q&A, pitch and video. Steps run **in sequence**. The ReviewModel fixture (S0) still matters: it lets the UI and export be built and demoed even if the engine slips.

| Step | Scope | Output | Done when | Target |
|---|---|---|---|---|
| **S0 Contracts & skeleton** | repo layout; pydantic models (canonical rows, MetricResult, Observation, ViewSpec, ReviewModel); `review_northstar.json` fixture; FastAPI serving the fixture + static `web/` | shared contract | `GET /accounts/CUST001/review` returns a valid fixture; page loads from FastAPI | Fri 23:30 |
| **S1 Ingestion** | Adapter interface; Excel pack adapter; ERROR → quarantine, WARNING → dq_flags; checks C1–C3; DuckDB DDL + load; source table; bad-row fixture | `model/`, `adapters/` | all sheets loaded; 0 quarantined; C1 warning for L003; 3 quarantined with the injected fixture | Sat 10:00 |
| **S2 Metric engine** | registry loader; §7.5 formulas; per-kg allocation; MetricResult + lineage; roll-up rules | `metrics/` | reconciliation and de-duplication tests pass | Sat 12:30 |
| **S3 Scenarios & filters** | baseline + sensitivity ranges; all-baseline comparison; per-site and per-month series; year/quarter and product filters | `metrics/scenarios.py` | numbers match the mockup within rounding; Σ quarters = year | Sat 14:00 |
| **S4 Insights & personalisation** | rules R1–R8; customer + industry priority resolution; scoring; discussion points; action table | `insights/` | insight and default-priority tests pass | Sat 15:30 |
| **S5 Review API** | assemble the ReviewModel from the engine; `/explain`, `/data-quality`, `/config`, `/intent` (keyword version) | `api/` | contract test passes for 3 customers × 3 baselines × 3 sensitivities | Sat 16:30 |
| **S6 Frontend on live API** | port the mockup to `web/` reading the API; header filters; module registry; 7 pages; drawer with `/explain`; warning icons; quarantine view | `web/` | demo script §2 runs end to end on live data | Sat 19:30 |
| **S8 Export (PPTX)** | python-pptx template + builder; 9 slides; matplotlib charts; PDF = HTML print view | `export/` | PPTX opens; values identical to the API for the same run_id | Sat 21:30 |
| **S7 AI** | Claude intent parser (keyword fallback); narrator with placeholders; guard + wording rules; AI on/off flag | `ai/` | guard tests pass; demo prompts give the right ViewSpec; AI off still works | Sat 23:00 · **freeze** |
| **S9 Docs** | methodology.md, data_readiness.md, README, demo_script.md, architecture diagram images | `docs/` | covers all brief §07 notes | Sun 07:30 |
| **S10 Submission** | full demo run; fresh-clone run check; record ≤ 4-min video; repo + zip; accept IP terms; submit | submission | submitted | Sun 09:30 (deadline 10:00) |

AI (S7) comes after export (S8) on purpose: the PPTX is a required deliverable, while the AI narrative has a working template fallback.

**Cut order if behind schedule** (first cut first): Q&A agent (already out of the solo scope) → AI intent parser (keep the keyword parser) → quarter filter (keep full year) → product filter → monthly trend charts → quarantine demo fixture → AI narrator (keep templates). **Never cut:** badges and ranges, the C1 warning, the methodology page, PPTX export, 2-priority personalisation, site drill-down.

**Sleep:** plan about 5 hours (Sat 23:30 → 04:30, or similar). Steps S9–S10 are written to fit the morning.

## 17. Open questions to Lindström (defaults in place)

| Q | Topic | Default used |
|---|---|---|
| Q7 | depth vs breadth | depth on NorthStar; Apex shown for industry contrast |
| Q10 | baseline | B_LOCAL default, the other two selectable |
| Q11 | repair claim | separate figure, range 0.25–1.0 replacements per repair |
| Q12 | wording | the banned list in §10.4 |
| Q16 | wearer de-duplication | max across products per site-month |
| Q17 | LATE definition | use the pack's flag as-is |
| Q18 | utilisation gap meaning | call it "not scanned in use"; never "lost" |
| Q20 | cost metrics customer-facing | internal-only (hidden in customer view and export) |
| Q22–23 | data platform, eLindström stack | generic Tier 2 "governed warehouse"; embed as module or API |
| Q28 | AI provider limits | Claude; switchable via the `ai/` interface |
| Q29 | AI writing recommendations | allowed under placeholder + guard; templates as fallback |
| Q35 (new) | L003 laundry volume 10.8× lower than the customer kg routed to it: deliberate trap or error? | WARNING flag, per-kg allocation, R8 observation |

## 18. Team
Solo builder with Claude Code (confirmed). §16 is sequenced for one person. Out of scope for solo: Q&A agent, React frontend, Playwright, hosted deployment (optional only if time remains on Sunday).

## 19. Left to the builder

Chart library choice; component library; CSS details; PPTX chart method; exact template phrasing; the Playwright test; hosting choice (if any); logging format.
