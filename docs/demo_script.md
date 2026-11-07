# Demo script (4 minutes)

**Setup.** Start the server with the default config (extension pack on): `python -m uvicorn api.main:app --port 8000`, browser at http://127.0.0.1:8000. Select **NorthStar Foods Group**, period 2025, baseline "Outsourced local laundry", sensitivity Base, audience **KAM**, detail **Simple**. Reset NorthStar's inputs before you start: on *Service vs do-it-yourself* click **Reset to defaults**, and on *Growth opportunities* click **Clear** (or delete `data/kam_inputs/CUST001.json`). No API key is needed; account intelligence uses the committed snapshot. Leave ANTHROPIC_API_KEY unset unless the demo machine is reliably online. Have the pitch deck (`docs/pitch/ValueReview_pitch.pptx`) open in another window for the opening and closing slides.

Say once, early: "Everything you will see is synthetic data and not audited. The banner says so."

The three things we want you to remember: **we built on your work and your ask**, **it grows with your business without code changes**, and **the exports work**.

| Time | Step | Click | Say |
|---|---|---|---|
| 0:00 | 1. Customer story (Simple) | The app opens on **Customer story**. Point at the first card, then at **What to say**. | "You asked for dashboards an account manager can explain. This is the landing page: plain-language cards. NorthStar saved about 1,407 m³ of water and about 255 t CO₂e versus local laundry in 2025, always with a range (691 to 2,122 m³; 205.7 to 304.4 t). That is roughly 14 Finnish households' water for a year and the yearly CO₂ emissions of about 130 cars, labelled as an illustrative comparison. Under each card is a line the KAM can simply read out." |
| 0:35 | 2. Do-it-yourself with a typed contract price | Click **Service vs do-it-yourself**. In **Your numbers**, type `1200000` in **Lindström contract price**, click **Save**. | "Doing the same yourself would cost about 1.96 million euros a year: garment purchases, washing at the local laundry price, admin time. The defaults are visible and the KAM can type the customer's own prices. Only once a contract price is entered do we show the net: about 757,510 euros in the customer's favour, with a range. Extra replacements without repairs are shown for explanation but not added to the total, so nothing is counted twice. Euros, hours and CO₂ are never added together." |
| 1:05 | 3. Growth | Click **Growth opportunities**. Type `4` in **Sites not yet served**, tick **Mats** (Workwear says *already used, will be skipped*), click **Size the opportunity**. | "This is your first ask: show customers they save more by working with Lindström more. Four more sites and the Mats service would avoid about 410,000 euros a year in laundry and garment costs and save about 60 t CO₂e, each with a range, scaled from NorthStar's own data. Service lines they already use are skipped." |
| 1:35 | 4. Fazer intel | Click **Account intelligence**. The Fazer Group snapshot opens by itself. Scroll to **How Lindström can help** and the sources. | "Your second ask: AI that knows where customer companies are going. This is a real public company, Fazer: the new Lahti chocolate factory from 2028, 4,693 employees across Finland, Sweden and the Baltics, Scope 3 above its 2020 baseline. Every claim has a source and a date; code drops anything the web search did not actually return. Offers must come from our service catalogue. This is a committed snapshot, so no API call; with a key the Research button runs it live." |
| 2:10 | 5. Extension: hotel, Mats, Estonia | Open the **Customer** dropdown, pick **Baltic Harbour Hotels**. Open the **Service line** dropdown (Mats, Workwear). Optionally show `config/sources.yaml` and `data/extension_pack/` in the editor. | "It grows with your business. We added a hotel chain in Estonia, a new industry and a new service line, Mats. The whole change is one line in `sources.yaml`, six CSV files and a three-entry Hospitality rule. No engine, UI or export code changed. Hospitality priorities apply by themselves, and Estonia appears in the sites. A test adds Washroom, restaurants and Latvia the same way." |
| 2:45 | 6. Export menu | Switch back to **NorthStar Foods Group**. Click **Export ▾** → **PDF**, open it briefly. Mention **PowerPoint** and **Excel** in the same menu. | "The exports work. PowerPoint, PDF and Excel come from the same review model, so they match the dashboard: the story, the do-it-yourself comparison and the growth scenario are in there, and the disclaimer is on every page. The customer audience removes internal metrics." |
| 3:10 | 7. Expert toggle → credibility | Click **Expert**. Click the CO₂e figure to open the drawer. Click **Data readiness**. | "Expert mode shows what sits behind every figure: status badge, formula, assumptions, low/base/high. Our consistency check found that customer kilos routed to laundry L003 in Malmö are about 10.8 times the laundry's own total for the year. We did not hide or fix it: affected figures get lower confidence and a warning, and we ask you (Q35)." |
| 3:50 | Close | Pitch deck slide 8. | "Built on your work, grows with your business, exports that work. Prototype, synthetic data, not audited, and ready for one pilot customer's real exports." |

If asked about the net range: it depends entirely on the contract price typed. A higher price can make the low end negative, and the page says so.

## Talking points by judging criterion

**Value (25).** The three Lindström asks are pages, not slides: the **Customer story** a KAM reads out, **Service vs do-it-yourself** and **Growth opportunities** (the customer saves more by working with Lindström more), and **Account intelligence** (where the customer is going and which Lindström offer fits). The headline is a range against a stated baseline, not a maximised claim.

**Completeness (20).** Customer and site levels; filters for period, product, service line, baseline, sensitivity and audience; personalisation by prompt, chips, customer topics and industry rules for 4 industries; observations with evidence, discussion points and actions; PowerPoint, PDF and Excel exports; the fit page; methodology, data-readiness and architecture notes; a pitch deck generated from the same engine; a full test suite.

**Credibility (20).** Method status and provenance on every value; weakest-input rule; low/base/high ranges; the baseline is a visible choice; repair range 0.25 to 1.0 with A002 as the upper bound; extra replacements shown but not in the do-it-yourself total; net only with a contract price; euros, hours and CO₂e never summed; the AI never writes numbers (placeholders and a guard); intel keeps only searched, dated, safe sources; snapshot chips never call the API; "Prototype · synthetic data · not audited" everywhere.

**Data (15).** The L003 finding (≈10.8× over the year; monthly 9.6 to 12.6×) flagged as a WARNING with lower confidence and Q35. Bad rows go to quarantine with reasons. The Data readiness page maps every field to the pack, a future approved Lindström source and its gap, now including service-line and industry master data, contract prices and CRM legal names for intel.

**Usability (10).** Simple mode by default, "about X (between A and B)", "What to say" lines with a Copy button, glossary tooltips, Expert mode one click away; decimal comma or dot both work in the inputs; one Export menu; works without the AI.

**Scalability (10).** Sources are listed in `config/sources.yaml`; a generic CSV adapter added a customer, industry, country and service line with data and config only, and a test proves a further one needs no code. One `ReviewModel` serves the dashboard, three export formats and a future eLindström embed. Tier 0 to 3 roadmap from the synthetic pack to a module inside eLindström.

## Fallbacks

- If the AI is slow or unavailable, nothing changes except the narrative wording (template). Account intelligence shows the snapshot. Say so; it is a feature.
- If a prompt is not recognised, the view stays unchanged and the message says "Not recognised"; use a suggested prompt chip.
- If the PDF viewer is slow to open, show the PowerPoint instead; both come from the same model.
- `VR_EXTENSIONS=off` gives the before picture (3 customers) if someone asks to see it.
- Do not claim the figures are real, audited or verified. Do not read the savings as a Lindström claim.
