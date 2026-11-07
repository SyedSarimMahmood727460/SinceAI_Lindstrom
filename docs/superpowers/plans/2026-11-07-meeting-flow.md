# Guided Meeting Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the landing page with a 5-step guided customer meeting. Calm the header, use one compact number style, add a demo-scenario button, and make the exports follow the meeting order.

**Architecture:** Server side gains two things: `fmt_compact` (export/format.py) and structured `facts` on the biggest-improvement story card. The ReviewModel gains nothing else. The web client renders the meeting from the existing ReviewModel (`story`, `dto`, `growth`, `observations`, `narrative`, `actions`, `kpis`) and mirrors `fmt_compact` in JS for display only. The exports are reordered to the meeting steps.

**Tech Stack:** existing (Python 3.12, FastAPI, python-pptx, reportlab, openpyxl, vanilla JS, Chart.js optional; CSS bars preferred).

**Spec:** `docs/specs/2026-11-07-meeting-flow-design.md` (approved; §10a decisions override earlier text).

## Global Constraints
- Branch `meeting-flow` from `main` @ b8c98d2. Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- JS formats only; it never computes new figures. Step 3 tiles come from server-side `facts`.
- Customer audience:
  - no edit controls (no Your numbers form, no demo button, no growth form, no target inputs);
  - no Account intelligence nav;
  - no internal metrics anywhere;
  - step 4 hidden when `growth` has no totals.
- Disclaimer strip text exactly `Prototype · synthetic data · not audited`. Exports keep the disclaimer and run_id on every page and slide.
- Compact rules (spec §5):
  - EUR: ≥1,000,000 → `€1.96M`; ≥10,000 → `€410k`; else `€8,250`.
  - l → m³ (÷1000, 0 dp, thousands separator).
  - kgCO2e: ≥1,000 → t (0 dp if ≥10 t, else 1 dp), suffix ` t CO₂e`; else ` kg CO₂e`.
  - h: 0 dp → `1,152 h`.
  - kWh: ≥1,000 → `172 MWh`.
  - ratio → `98.3%`.
  - None → `—`.
  - Ranges: `range €1.36M – €2.74M`.
- Demo scenario input set: `contract_price_eur_per_year: 1200000, extra_sites: 4, extra_service_lines: ["mats"]` (`["washroom"]` if "Mats" ∈ `meta.service_lines`). It is merged with the stored inputs from `GET /accounts/{id}/inputs?include=growth`.
- Steps 1–4 must fit above the fold at 1440×900. Step 5 may scroll.
- Don't use ports 8000/8030 (the user's). Use 8040+ for your own server, and stop it afterwards.

## Review Focus
1. **The customer view must never show an edit control or the intel nav.** Expect read-only steps. Test: Task 3 browser check plus `test_meeting_customer_hides_controls` (static check that the meeting renderer branches on audience: a grep-style test on `web/modules.js` is acceptable).
2. **An account with no growth inputs and no contract price.** Expect step 2 to show DIY + hours only; step 4 shows the KAM form or is hidden for customers. No empty tiles. Covered by Task 3's browser check (NorthStar, before loading the demo).
3. **R4 or a fallback biggest-improvement with no site pair.** Expect no tiles, statement only. Test: Task 1 `test_biggest_facts_absent_for_r4`.
4. **The demo scenario on an account already using Mats** (Baltic Harbour Hotels). Expect washroom instead of mats. Covered by Task 3's browser check (hotel).
5. **Very large or tiny numbers in the compact format** (0, None, 9,999, 10,000, 999,999, 1,000,000, negative net). Test: Task 1 `test_fmt_compact_vectors`.

---

### Task 1: Compact formatter, story facts, exports in meeting order

**Files:**
- Modify: `export/format.py`, `insights/story.py`, `export/sections.py`, `export/pptx_builder.py`, `export/pdf_builder.py`, `export/xlsx_builder.py`.
- Tests: `tests/test_format.py` (new), `tests/test_story.py`, `tests/test_export.py`, `tests/test_exports_more.py`, `tests/test_pitch.py` (only if a figure format changes there).

**Interfaces:**
- Produces:
  - `fmt_compact(value: float | None, unit: str) -> str`;
  - `fmt_compact_range(metric) -> str` (`"range A – B"` or `""` if no range);
  - `fmt_compact_value(metric) -> str` (uses the selected `value`);
  - the story card `biggest_improvement` gains `facts: {site_name: str, metric_label: str, value: float, typical: float, unit: str} | None`;
  - the export section order: Cover · `1 · What you got` · `2 · Vs doing it yourself` · `3 · Where to improve` · `4 · Grow together` (only when growth has totals) · `5 · Agree next steps` · Appendix: Value KPIs · Footprint vs baseline · Site highlights · Methodology & assumptions · Data readiness;
  - the xlsx first sheet is `Meeting` (one row per step: step, message, figures, what_to_say);
  - story statements use the compact style for EUR, l, kgCO2e, h (`_about`, `signed_about`, `_fmt`).

- [ ] **Step 1: Write the failing tests.**
  - `test_fmt_compact_vectors`:
    ```
    (1957510,"EUR")→"€1.96M"; (757510,"EUR")→"€758k"; (8250,"EUR")→"€8,250"; (0,"EUR")→"€0";
    (-297100,"EUR")→"−€297k" (U+2212 minus); (1406620,"l")→"1,407 m³"; (255073.7,"kgCO2e")→"255 t CO₂e";
    (4200,"kgCO2e")→"4.2 t CO₂e"; (850,"kgCO2e")→"850 kg CO₂e"; (1152.4,"h")→"1,152 h";
    (172000,"kWh")→"172 MWh"; (0.983,"ratio")→"98.3%"; (None,"EUR")→"—"; (9999,"EUR")→"€9,999"; (10000,"EUR")→"€10k"; (999999,"EUR")→"€1.00M"
    ```
  - `test_story_uses_compact`: the NorthStar value_delivered statement contains `"1,407 m³"` and `"255 t CO₂e"`; vs_diy contains `"€1.96M"`.
  - `test_biggest_facts_present`: NorthStar facts has site_name `"NorthStar Kraków"`, value ≈ 67.0, typical ≈ 48.8.
  - `test_biggest_facts_absent_for_r4`: a stub review whose top business observation is R4 → facts None.
  - `test_pptx_meeting_order`: slide titles start with ["…cover…", "1 · What you got", "2 · Vs doing it yourself", "3 · Where to improve"]. Find them by `startswith`. With growth, "4 · Grow together" precedes "5 · Agree next steps"; without growth, it's absent.
  - `test_pdf_meeting_order` (pypdf text order of the same headings).
  - `test_xlsx_meeting_sheet_first`.
  - Update the existing count/index assertions to locate slides by title.
- [ ] **Step 2:** Run the new and updated tests → FAIL.
- [ ] **Step 3:** Implement. The step sections reuse existing section content in `export/sections.py`, regrouped:
  - step 1 = value_delivered + water/CO₂/hours;
  - step 2 = DIY lines/net/bars;
  - step 3 = biggest improvement + next 2 business observations;
  - step 4 = growth;
  - step 5 = discussion + actions.

  Step slides use compact numbers.
- [ ] **Step 4:** Run the changed test files, then the full suite `python -m pytest -q -W error` → PASS.
- [ ] **Step 5:** Commit `feat: compact numbers, story facts, exports in meeting order`.

### Task 2: Calm header, Settings popover, Ask panel, regrouped nav

**Files:** Modify `web/index.html`, `web/app.js`, `web/modules.js`, `web/styles.css`, `config/modules.json`, `tests/test_modules.py`.

**Interfaces:**
- Produces:
  - DOM ids `#settingsBtn`, `#settingsPanel`, `#askBtn`, `#askPanel`, `#disclaimerStrip`;
  - nav groups `Meeting` (`data-v="meeting"`), `Before the meeting` (`data-v="intel"`, KAM only), `Detail` (overview, sites, vs_diy, growth, footprint, circularity, steering), `Trust` (fit, methodology, readiness);
  - `S.view` default `'meeting'`;
  - modules.json: page `meeting` with component `meeting_flow` registered first (the renderer is a stub until Task 3: "Meeting flow loads here"). The `story` page is removed (story cards are now rendered inside the meeting).

- [ ] **Step 1:** Update `tests/test_modules.py`: `test_meeting_is_the_landing_page` (module[0] page `meeting`, component `meeting_flow`; first nav link `data-v="meeting"`); the PAGES/COMPONENTS allow-lists updated → FAIL → implement → PASS.
- [ ] **Step 2: Header:**
  - visible: Customer, Period, Compare-with (baseline), then Ask, Settings, Export ▾;
  - the Settings popover holds Product, Service line, Sensitivity, Audience (KAM/Customer), Detail (Simple/Expert); the button shows a dot when any of these differs from its default; Esc/outside click closes it;
  - the Ask panel holds the prompt input, suggested chips, priority chips and the interpretation + "why this view" lines, toggled by Ask; it closes after a prompt is applied;
  - the banner becomes `#disclaimerStrip` (one line). The long text moves to the top of Methodology.
- [ ] **Step 3: Browser check** (port 8040, 1440×900):
  1. The header is one row.
  2. Settings and Ask open and close.
  3. Every old page is still reachable from the nav.
  4. The customer view hides the "Before the meeting" group.
  5. No console errors.
- [ ] **Step 4:** Full suite → PASS. Commit `feat: calm header with settings and ask panels, regrouped navigation`.

### Task 3: Meeting flow page + demo scenario

**Files:** Modify `web/app.js`, `web/modules.js`, `web/styles.css`, `tests/test_modules.py`.

**Interfaces:**
- Consumes:
  - the ReviewModel fields `story` (cards incl. `biggest_improvement.facts`), `dto` (`diy_total`, `contract_price`, `net`, `convenience.staff_hours_freed`, `hygiene_note`, `missing_lines`, `inputs`), `growth` (`totals`, `statement`, `what_to_say`, `levers`, `skipped_lines`, `notes`), `observations`, `narrative.discussion_points`, `actions`, `kpis`, `meta.service_lines`, `meta.node.name`, `meta.period`;
  - the endpoints `GET/PUT /accounts/{id}/inputs(?include=growth)`;
  - `fmt_compact` rules (mirror them in JS as `fmtCompact(value, unit)` and `fmtCompactRange(metric)`).
- Produces: the `meeting_flow` renderer. `S.step` 1–5, persisted in `location.hash` `#meeting/N`.

- [ ] **Step 1:** Add `test_meeting_customer_hides_controls` to `tests/test_modules.py`. It is a static check that `web/modules.js`'s meeting renderer references `audience` / `isCustomer` guards around `diy_inputs`/demo-button/growth-form/target-input rendering. It's acceptable as a grep on markers you add (e.g. `/* kam-only */` comments next to each guarded block). → FAIL → implement → PASS.
- [ ] **Step 2: Implement the steps exactly per spec §3 and §10a:**
  - Step tabs (buttons), Back/Next, and ←/→ when focus isn't in an input.
  - Hero tiles: label, big compact number, a small range line, and a context line.
  - "What to say" box with Copy (reuse the existing copy helper).
  - Footnote line on every step.
  - Clicking a tile opens the existing explain drawer.
  - Step 2: CSS horizontal bars for Lindström contract vs DIY total, with the gap caption from `dto.net` (signed, compact). With no contract price, show only the DIY bar plus (KAM only) "Enter the contract price or load the demo scenario". "Your numbers" goes in a `<details>` fold (KAM only), reusing the existing diy_inputs renderer.
  - Step 3: tiles from `facts` (site value vs typical). Without facts, no tiles. Next 2 business observations (exclude R7/R8): title + action. A "See all sites" button.
  - Step 4: tiles from `growth.totals`; lever list; skipped_lines/notes. Without totals: KAM sees the growth form in a fold plus the demo button; the customer view hides step 4 from the bar.
  - Step 5: numbered discussion points; the action table (target inputs KAM only); inline Export buttons (PowerPoint / PDF / Excel) calling the existing export function.
- [ ] **Step 3: "Load demo scenario" button** (KAM only; steps 2 and 4 when data is missing):
  - GET the stored inputs with `?include=growth`, merge the demo set (constraints), then PUT the full set;
  - toast "Demo scenario loaded — example numbers; edit or reset in Your numbers.";
  - reload the review.
- [ ] **Step 4: Browser check** (port 8040; 1440×900 and 1280×720), NorthStar:
  1. Steps 1–4 fit above the fold at 1440×900.
  2. Before the demo: step 2 shows DIY + hours with no empty tiles; step 4 shows the form.
  3. After loading the demo, step 2 shows two bars + the gap and step 4 shows totals.
  4. ←/→ work and the hash persists on reload.
  5. Customer view: no edit controls, step 4 hidden when there's no growth.
  6. Hotel: the demo uses washroom.
  7. No console errors.

  Reset the demo inputs afterwards (Reset button or delete the temp VR_INPUTS_DIR).
- [ ] **Step 5:** Full suite → PASS. Commit `feat: guided meeting flow with demo scenario`.

### Task 4: Demo script, pitch deck, README

**Files:** Modify `docs/demo_script.md`, `scripts/make_pitch_deck.py`, `docs/pitch/ValueReview_pitch.pptx` (regenerated), `README.md`, `tests/test_pitch.py` (titles).

- [ ] **Step 1:** `tests/test_pitch.py`: slide 3's title is now `"Easy to explain: a guided customer meeting"` → FAIL.
- [ ] **Step 2:** Update the pitch slide 3 content to the 5 steps, using compact figures from `build_review` + `fmt_compact`. Regenerate the deck (temp VR_INPUTS_DIR).
- [ ] **Step 3:** Rewrite `docs/demo_script.md` (≤ 4 min):
  1. Open the Meeting.
  2. Load demo scenario.
  3. Steps 1–5 with the lines to say.
  4. Export PDF.
  5. Toggle Expert to show credibility.
  6. "Built on Lindström's work".
  7. Optional: Before the meeting → Fazer intel.

  Plus a README line about the meeting flow and the demo scenario.
- [ ] **Step 4:** Full suite → PASS. Commit `docs: demo script and pitch for the guided meeting`.

## Cut list (first cut first)
1. Hash persistence of the step.
2. The xlsx Meeting sheet.
3. The ←/→ shortcut.
