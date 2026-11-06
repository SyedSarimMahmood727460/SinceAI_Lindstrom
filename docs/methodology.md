# Methodology note

**Prototype · synthetic data · not audited.** All inputs are the synthetic Lindström × Since AI data pack. Baseline factors are illustrative placeholders. Nothing in this prototype is audited, verified or suitable for CSRD or other regulatory reporting.

This note describes what the code does (`metrics/`, `config/assumptions/v1.yaml`, `config/metrics.yaml`). Only the metric engine produces numbers. The dashboard, the PPTX and the AI layer read one `ReviewModel`; the AI never writes a figure.

## 1. Boundary

- **In scope:** the Lindström textile rental service delivered to the selected customer account and its sites (in the pack: workwear only).
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

## 12. Limitations

- All data is synthetic. Figures illustrate the method and are not claims about Lindström or any customer.
- Baseline factors are illustrative and need approval or replacement by customer-specific or public emission factors before external use.
- Savings are small differences between large numbers: ranges are wide, water especially. They reflect only the stated sensitivity, not every source of error.
- Postponed replacements are an assumption, not an observed outcome. A002 is an upper bound.
- Wearer counts depend on de-duplication assumption T2. Utilisation (scanned versus allocated) is described as "not scanned in use", never "lost", as the meaning of the gap is unconfirmed.
- The L003 volume inconsistency is unresolved (Q35). Allocated figures for the affected sites are less certain.
- "On time" uses the pack's `LATE` flag as supplied; its definition is unconfirmed.
- Idle stock value (`idle_stock_value_eur`) is an internal estimate, not customer-facing. It is hidden when the audience is set to customer and absent from the PPTX.
- Delivery-customer level of the hierarchy is missing in the pack, so sites hang directly under the account.
- Not audited. Not suitable for CSRD or other regulatory reporting. Wording rules require "saved" or "avoided" to be qualified as "vs {baseline} (estimate)".
