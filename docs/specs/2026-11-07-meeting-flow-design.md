# Value Review — Guided Meeting Flow (UX redesign)

Status: **draft for approval** · Date: 2026-11-07 · Builds on `main` @ b8c98d2. Deadline: Sun 8 Nov 2026, 10:00 EET.
Legend: **[User]** = decided by the user · **[Call]** = my decision, can be overruled.

## 1. Why
The judges are **Lindström's own account managers and management** [User]. They'll judge whether their account managers could actually run a customer meeting with this. They also judge whether management sees the value.

The UX review (2026-11-07) found that today's screens bury the value:
- controls take half the screen;
- 8 header controls;
- no big numbers;
- inconsistent formats;
- no visual Lindström-vs-DIY comparison;
- empty growth page;
- intel is a wall of text.

The user chose direction **B: a guided meeting flow** [User] (mockup: `C:\workspace\claude\ux_mockups\index.html`, option B).

## 2. Goals / non-goals / anti-goals
**Goals**
- G1 The landing page is a **5-step guided meeting**. Each step shows one message, 2–3 big proof numbers, and the sentence to say [User].
- G2 A **calm header**: Customer · Period · Compare-with visible; everything else in a Settings popover; prompt + chips behind an **Ask** button [User].
- G3 **One compact number style** in the UI and exports [User].
- G4 Steps 2 and 4 never open empty: a visible **"Load demo scenario"** button (KAM only) [User agreed to my guess].
- G5 **Exports follow the same 5-step order** [User agreed to my guess].
- G6 Accounts intelligence is under **"Before the meeting"** (KAM only) and leads with "How Lindström can help" [User].

**Non-goals:** new metrics or engine logic; mobile layout; removing existing detail pages.

**Anti-goals**
- JS computing new figures (formatting only).
- Any internal metric or edit control visible in the customer view.
- Breaking the existing tests or exports.
- Hiding ranges entirely: the range stays on a small second line.

## 3. The meeting flow (new default page `meeting`)

**Navigation**
- Step tabs across the top (buttons): `1 What you got · 2 Vs doing it yourself · 3 Where to improve · 4 Grow together · 5 Agree next steps`.
- Back/Next buttons at the bottom of each step.
- Keyboard ←/→ moves between steps when focus is not in an input.
- The current step lives in the URL hash (`#meeting/2`), so a reload keeps the place [Call].

**Each step's layout**
1. Step title (a message, not a label).
2. A hero row of 2–3 big tiles: label, big number, small range line, relatable/context line.
3. One supporting visual or list.
4. A "What to say" box with Copy.
5. A small footnote: "Estimates with ranges · Expert shows how each figure is calculated". Clicking any tile opens the existing explain drawer.

| Step | Message (title) | Hero tiles | Supporting element | What to say | Data source |
|---|---|---|---|---|---|
| 1 What you got | "What {customer} got from Lindström in {period}" | water saved · CO₂e avoided · staff hours freed (+ on-time % as a context line) | relatable lines (≈ households / cars) | story card `value_delivered.what_to_say` | `kpis` water_saving_l, co2_saving_kg; `dto.convenience`; `story` |
| 2 Vs doing it yourself | with contract price: "About {net} less with Lindström than doing it yourself"; without: "Doing it yourself would cost about {diy_total} a year" | net (if any) · DIY total · staff hours freed | **horizontal bars: Lindström contract vs DIY total** (DIY only if there's no price, plus the prompt "Enter the contract price or load the demo scenario"); folded "Your numbers" panel (existing form, KAM only); hygiene note if any | story `vs_diy.what_to_say` | `dto` |
| 3 Where to improve | story `biggest_improvement.title` statement (plain) | the site's figure vs typical (2 tiles) | next 2 business observations (title + action) as a short list; "See all sites" link | story `biggest_improvement.what_to_say` | `story`, `observations` (exclude R7/R8) |
| 4 Grow together | with growth: growth `statement`; without: "What if more sites and services came to Lindström?" | € avoided · CO₂e · hours (totals) | lever list; the growth form folded open when empty (KAM only); skipped lines and notes | growth `what_to_say` | `growth` |
| 5 Agree next steps | "Agree the next steps" | – (no tiles) | discussion points (numbered) + action table (owner, KPI, value, target input); Export buttons (PowerPoint / PDF / Excel) inline | story `whats_next.what_to_say` | `narrative.discussion_points`, `actions` |

**Empty and edge states**
- A missing metric shows "—" with "no data for this filter".
- Step 3 with no business observations: "No site stands out — performance is even across sites."
- Step 4 in the customer view with no growth: hidden from the step bar [Call].

## 4. Header, navigation, settings

**Header**
- Visible: logo · Customer select · Period select · **Compare with** (baseline) select · spacer · **Ask** button · **Settings** button · **Export ▾**.
- Settings popover: Product, Service line, Sensitivity, Audience (KAM/Customer), Detail (Simple/Expert). The Settings button shows a dot when any setting differs from its default.
- **Ask** opens a panel under the header: prompt input + suggested chips + priority chips. It closes after a prompt is applied. The interpretation line shows inside the panel only.
- The disclaimer becomes a one-line strip under the header: `Prototype · synthetic data · not audited`. The long banner text moves to Methodology.
- The "Emphasis / Why this view" lines move into the Ask panel.

**Left nav (new grouping)**
- **Meeting** (default)
- **Before the meeting** (KAM only): Account intelligence
- **Detail:** Overview · Sites · Service vs do-it-yourself (full) · Growth (full) · Footprint · Circularity · Steering pack
- **Trust:** Built on Lindström's work · Methodology · Data readiness

The old "Customer story" page is replaced by the Meeting; its cards are the step content.

## 5. Compact number style (G3)
Rules [Call]. Implemented once in Python (`export/format.py: fmt_compact(value, unit) -> str`) and mirrored in JS (`fmtCompact`), with shared test vectors in `tests/test_format.py` and a JSON list the JS can be checked against manually.

| Unit | Rule | Examples |
|---|---|---|
| EUR | ≥ 1,000,000 → `€1.96M` (2 dp); ≥ 10,000 → `€410k` (0 dp); else `€8,250` | €1.96M, €757k, €8,250 |
| l | show as m³: value/1000, 0 dp with thousands separator | 1,407 m³ |
| kgCO2e | ≥ 1,000 kg → t, 0 dp if ≥ 10 t else 1 dp; else kg | 255 t CO₂e, 4.2 t CO₂e |
| h | 0 dp, thousands separator | 1,152 h |
| kWh | ≥ 1,000 → MWh 0 dp | 172 MWh |
| ratio | % 1 dp | 98.3% |
| other | existing fmt_value | — |

- Ranges in compact style: `range €1.36M – €2.74M`.
- Existing detail pages may keep their current formatting. The **meeting flow, the step exports and the pitch figures use compact**.

## 6. Demo scenario (G4)
- A KAM-only button **"Load demo scenario"** in steps 2 and 4 when the data is missing. It PUTs the full input set for the current account, keeping any existing entries: `contract_price_eur_per_year: 1200000, extra_sites: 4, extra_service_lines: ["mats"]` (for accounts already using mats, use `["washroom"]`).
- A toast says "Demo scenario loaded — these are example numbers; edit or reset in Your numbers."
- "Reset" clears everything, as today.
- No server change is needed (it uses the existing PUT) [Call].

## 7. Exports follow the meeting (G5)
PPTX and PDF order:
1. Cover
2. **1 What you got**
3. **2 Vs doing it yourself**
4. **3 Where to improve**
5. **4 Grow together** (only if growth)
6. **5 Next steps** (discussion + actions)
7. Appendix: Value KPIs · Footprint vs baseline · Site highlights · Methodology & assumptions · Data readiness

- Slide titles mirror the step messages.
- Compact numbers on the step slides.
- The Excel sheet order gets a "Meeting" summary sheet first.
- Update the tests for the new counts and titles.

## 8. Docs, pitch
- `docs/demo_script.md` is rewritten around the 5 steps (≤ 4 min): Load demo scenario → steps 1–5 → Export → Expert toggle → "Built on Lindström's work".
- The pitch deck's slide 3 is retitled "Easy to explain: a guided customer meeting", describing the 5 steps. Regenerate the deck.
- README: a line about the meeting flow and the demo scenario.

## 9. Testing / acceptance
- Python: compact formatter vectors; export order/titles/counts; customer audience still clean; the existing suite stays green.
- Browser check at 1440×900 and 1280×720:
  - every step fits **above the fold** at 1440×900 (hero + main element + What to say);
  - Next/Back and ←/→ work;
  - Settings popover;
  - Ask panel;
  - demo scenario;
  - customer view (no edit controls, no intel nav);
  - no console errors.

## 10. Build order (fits before Sunday 10:00)
1. Compact formatter (Py + JS) + export reorder.
2. Header/settings/Ask/nav reorg.
3. Meeting flow page (steps 1–5) + demo scenario.
4. Docs, demo script, pitch deck refresh.

**Cut order** (first cut first):
1. URL-hash step persistence
2. Excel "Meeting" sheet
3. The keyboard ←/→ shortcut (keep the buttons)

## 10a. Decisions from the builder check (all [Call])
1. **Tests may be rewritten.** `meeting` replaces `story` as the landing page in modules.json, nav and tests. Update `test_story_is_the_landing_page` → `test_meeting_is_the_landing_page`, the PAGES/COMPONENTS allow-lists, and slide-index/count assertions (find slides by title, not position, where practical). The `story_cards` component may stay registered for a detail view or be removed; the builder chooses.
2. **The Excel "Meeting" sheet goes first.** Update the `sheetnames[0]` assertions (it's still cuttable).
3. **Step 1 hours.** `dto` is computed from defaults even without KAM inputs, so staff hours should exist. If `staff_hours_freed` is None, the third tile becomes **on-time delivery %** instead (never an empty tile).
4. **Step 3 tiles.** Extend `insights/story.py` (insights layer, not the metric engine) so `biggest_improvement` also returns structured `facts: {site_name, metric_label, value, typical, unit}`, using the median it already computes. JS only formats them. For R4 or the fallback (no site pair), show no tiles; the statement and the next observations carry the step.
5. **Growth shape** (from `metrics/growth.py`):
   - `growth = {levers[{id,label,diy_cost_avoided,staff_hours_freed,co2_saving_kg,water_saving_l,net}], totals{same keys}|None, statement, what_to_say, narrative_line, skipped_lines[{id,reason}], notes[], partial}` (all values are MetricResult dicts).
   - Tiles use `totals.diy_cost_avoided`, `totals.co2_saving_kg` and `totals.staff_hours_freed`.
   - The builder confirms the keys by reading growth.py and api/review_model.py.
6. **Customer view:**
   - Step 2 is shown with DIY total + hours, plus net only if a contract price exists. No form and no demo button.
   - With no contract price the customer sees no prompt text (the KAM-only hint is hidden).
   - Step 4 is hidden when there's no growth.
   - Step 5 shows discussion points and actions with targets read-only. Export stays (the KAM drives the screen).
   - Customer exports use the same new order, with no internal metrics (as today).
7. **Compact style also applies to story statements.** `_about` and the story `_fmt` switch to `fmt_compact` for EUR, l→m³, kgCO2e→t, h. Update the story/export tests that assert the old number text. Detail pages keep their formatting.
8. **Above the fold** is a hard check for steps 1–4 at 1440×900. Step 5 is exempt (it scrolls). 1280×720 is best-effort.
9. **Demo scenario:**
   - The existing PUT accepts `extra_service_lines`.
   - "Already used" = the catalogue line's `service_line` appears in `meta.service_lines`. Use `["mats"]` unless Mats is already used, then `["washroom"]`.
   - Merge with stored inputs via `GET /accounts/{id}/inputs?include=growth` before the PUT.

## 11. Left to the builder
Exact CSS; tile visuals; animation (none required); chart library usage for the step-2 bars (Chart.js or plain CSS bars — CSS preferred, for crisp projection) [Call].
