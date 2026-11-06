# Demo script (4 minutes)

Setup: server running (`python -m uvicorn api.main:app --port 8000`), browser at http://127.0.0.1:8000, NorthStar Foods Group selected, period 2025, baseline "Outsourced local laundry", sensitivity Base, audience KAM. Optional: `ANTHROPIC_API_KEY` set. The demo works the same without it (template narrative). Optional: start with `VR_INJECT_BAD_ROWS=1` to show quarantine in step 8 (see the README for the status of that variable).

Say once, early: "Everything you will see is synthetic data and not audited. The banner says so."

| Time | Step | Do | Say |
|---|---|---|---|
| 0:00 | 1. Open NorthStar | Overview loads. Point at priority order and the interpretation line. | "NorthStar is a food and beverage group with 24 sites in Finland, Sweden and Poland. The view opens water first, then service, then emissions. That order comes from the customer's own stated topics plus a food-industry rule, so the KAM starts from the customer's priorities, not a generic page." |
| 0:30 | 2. Prompt | Type "Focus on water and emissions", press Tailor view. | "The KAM can say what matters. The system shows what it understood: priority Water and Emissions. Modules and observations reorder." Point at the badges: "Every figure has a status: calculated, allocated or estimated, and a provenance: synthetic." |
| 1:00 | 3. Drill-down | Sites page, sort by service requests, click Gdańsk. Open a KPI drawer. | "Gdańsk logs far more service requests per 100 wearers than its peers, flagged as an outlier with the multiple shown. Click any figure: formula, inputs, assumptions, lineage, low/base/high." |
| 1:25 | 4. Baseline | Footprint page. Note CO2e and water savings with ranges. Switch baseline to Home washing. | "Savings are against a baseline, so the baseline is a visible choice. Against home washing the estimated saving is much larger. Estimates always show a range, and the water range is wide because it is a small difference between two large numbers." |
| 2:00 | 5. Steering pack | Steering committee page. | "Discussion points and an action table for the steering committee, each tied to evidence. Every number in the text is filled in by the engine. The AI writes words and placeholders only, and a guard rejects any digit it invents. With no key we fall back to templates." |
| 2:30 | 6. Export | Click Export review (PPTX). Open the file briefly. | "Same data model, so the deck matches the dashboard. Status footnotes and the disclaimer are on every slide." |
| 2:50 | 7. Apex | Switch customer to Apex Industrial. | "Apex is manufacturing. The emphasis shifts to cost, circularity and repairs. Industry awareness is configuration, not code." Point at the warning icons on allocated and estimated metrics: "These carry a warning and lower confidence. I'll show why." |
| 3:20 | 8. Data readiness | Open Data readiness. | "Our consistency check found that customer kg routed to laundry L003 is about 10.8 times that laundry's own total (335,824 kg against 31,017 kg). We did not hide it or fix it: allocation is per kg so figures stay computable, but affected metrics get lower confidence, a warning icon, an observation for Lindström, and an open question (Q35). The table also shows each field's future approved source and gap." (If injected: "Three deliberately bad rows are quarantined with reasons, not dropped.") |
| 3:50 | Close | Back to overview. | "Prototype, synthetic, not audited. It is built to swap in approved sources one adapter at a time." |

Keep washing savings and repair savings apart if asked: "We never add them into one number."

## Talking points by judging criterion

**Value (25).** KAMs get a tailored review in minutes: prompt, priorities, observations with actions, steering-committee pack and a customer-ready PPTX. The headline is a range and a method, not a maximised claim. Different customers get different emphasis (NorthStar water, Apex cost).

**Completeness (20).** Dashboard with customer and site levels, filters (period, product, baseline, sensitivity, audience), PPTX export, personalisation for 3 industries, at least 3 observations with evidence, discussion points, methodology note, data-readiness note, architecture, tests.

**Credibility (20).** Two labels on every value (method status, provenance); weakest-input rule; low/base/high ranges; baselines and factors visible and editable in config; repair range 0.25 to 1.0 with A002 as the upper bound; wearer de-duplication (9,607 for NorthStar in December 2025, not the 28,367 you get by summing product rows); reconciliation tests against the pack's reference sheets; washing and repair savings never summed; the AI never writes numbers; banned wording ("net zero", "verified", "guaranteed" and others); "Prototype · synthetic data · not audited" everywhere.

**Data (15).** We found the L003 inconsistency (335,824 kg versus 31,017 kg, 10.8 times), flagged it as a WARNING, lowered confidence and asked Q35. Bad rows go to a quarantine with reasons. The Data readiness page maps every field to the pack sheet, a future approved Lindström source and its gap.

**Usability (10).** One prompt bar with an interpretation line the user can correct; chips; a "how calculated" drawer on every figure; a customer view that hides internal metrics; one-click export; works offline from the AI.

**Scalability (10).** Adapters feed one canonical model, so nothing downstream knows the source. Metrics, baselines, industry rules and dashboard modules are configuration. Tier 0 to 3 roadmap (pack, BI exports, governed warehouse, eLindström embed). One `ReviewModel` serves dashboard, PPTX and a future embed. More customers, industries and countries need data and config, not new code paths.

## Fallbacks

- If the AI is slow or unavailable, nothing changes except the narrative wording (template). Say so; it is a feature.
- If a prompt is not recognised, the view stays unchanged and the message says "Not recognised"; use a suggested prompt chip.
- Do not claim the figures are real, audited or verified. Do not read the savings as a Lindström claim.
