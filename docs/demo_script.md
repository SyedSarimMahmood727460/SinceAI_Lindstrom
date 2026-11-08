# Demo script (4 minutes)

**Setup.** Start the server with the default config (extension pack on): `python -m uvicorn api.main:app --port 8040`, browser at http://127.0.0.1:8040 (any free port). Select **NorthStar Foods Group**, period 2025, **Compare with** "Outsourced local laundry". Open **Settings** and check: sensitivity Base, audience **KAM**, detail **Simple**. Start from empty inputs: delete `data/kam_inputs/CUST001.json`, or use **Reset to defaults** in step 2 (**Your numbers**) and **Clear** in step 4 (Reset to defaults keeps the growth inputs). Do not load the demo scenario before you start: it is part of the show. No API key is needed; account intelligence uses the committed snapshot. Leave ANTHROPIC_API_KEY unset unless the demo machine is reliably online. Have the pitch deck (`docs/pitch/Threadline_pitch.pptx`) open in another window for the opening and closing slides.

Say once, early: "Everything you will see is synthetic data and not audited. The strip under the header says so."

The three things we want you to remember: **an account manager can run a customer meeting with it**, **we built on your work and your ask**, and **it grows with your business without code changes**.

Layout in one breath: the header holds Customer, Period, Compare with, then **Focus**, **Settings** and **Export**. The left navigation is **Meeting** · **Before the meeting** (KAM only) · **Detail** · **Trust**. The Meeting has five steps, each with a message, two or three big numbers, a range on a second line, and a **What to say** box with Copy. Use the step buttons, Back/Next, or the left and right arrow keys.

| Time | Step | Click | Say |
|---|---|---|---|
| 0:00 | 1. Open the Meeting | The app opens on **Meeting**, step **1 What you got**. Point at the three tiles, then at **What to say**. | "You asked for something an account manager can explain. One message per step. NorthStar saved about 1,407 m³ of water, avoided about 255 t CO₂e versus local laundry and freed 1,152 staff hours in 2025, each with its range. Below is the line the KAM can simply read out." |
| 0:30 | 2. Vs doing it yourself | Click **2 Vs doing it yourself**, then **Load demo scenario**. Point at the headline, the bars and the tiles. | "A KAM types the customer's contract price; for the demo one click fills example numbers. About €788k less with Lindström than doing it yourself: €1.96M a year to do it yourself, against a €1.17M contract. The net appears only with a contract price, and euros, hours and CO₂ are never added into one score." |
| 1:10 | 3. Where to improve | Click **Next** to **3 Where to improve**. | "The review is honest about where to improve. Kraków washes 67 kg per wearer, against about 49 kg typically across NorthStar's sites. See all sites opens the detail." |
| 1:30 | 4. Grow together | Click **Next** to **4 Grow together**. | "Your ask: customers save more by working with Lindström more. Four more sites and the Mats service would avoid about €410k a year and about 60 t CO₂e, scaled from NorthStar's own data." |
| 1:55 | 5. Agree next steps | Click **Next** to **5 Agree next steps**. Point at the discussion points and the action table. | "We finish with decisions: discussion points, and actions with an owner and a KPI." |
| 2:10 | Export PDF | Click the **PDF** button in step 5 (or **Export ▾** → **PDF**), open it briefly. Mention PowerPoint and Excel. | "The exports follow the same five steps, with the disclaimer on every page. Coaching lines stay in the speaker notes, and the customer audience removes internal metrics." |
| 2:40 | Expert toggle | Open **Settings**, choose **Expert**, click **1 What you got**, then click the **CO₂e avoided** tile. | "Expert shows what sits behind every figure: status, formula, assumptions, low, base and high. Our consistency check found customer kilos routed to laundry L003 in Malmö at about 10.8 times the laundry's own total. We did not hide it: affected figures get lower confidence and a warning, and we ask you (Q35)." |
| 3:20 | Close | Pitch deck slide 8. | "A meeting a KAM can run, built on your work, ready for one pilot customer." |

**Optional (if there is time, or if asked about "where customers are going"):** open **Before the meeting** → **Account intelligence**. The Fazer Group snapshot opens by itself and leads with **How Lindström can help**. Say: "Your second ask: AI that knows where customer companies are going. A real public company, Fazer. Every claim has a source and a date; code drops anything the web search did not return, and offers come from our service catalogue. This is a committed snapshot, so no API call." The hotel (Baltic Harbour Hotels) shows the extension: new industry, country and service line from data and config only. Pick it in **Customer**; **Load demo scenario** gives a €40,000 contract and adds Washroom, because the hotel already uses Mats.

**Customer view.** Settings → Audience **Customer** removes the edit controls, the demo button, the What to say coaching box and the Before the meeting navigation, and hides step 4 when there is no growth scenario. Use it to show that the same screen can face the customer.

If asked about the net range: it depends entirely on the contract price typed. A higher price can make the low end negative, and the page says so.

## Talking points by judging criterion

**Value (25).** The three Lindström asks are pages, not slides: the **Meeting** a KAM runs in five steps (what you got, versus doing it yourself, where to improve, grow together, next steps: the customer saves more by working with Lindström more), and **Account intelligence** under Before the meeting (where the customer is going and which Lindström offer fits). The headline is a range against a stated baseline, not a maximised claim.

**Completeness (20).** Customer and site levels; header filters for customer, period and compare-with, and Settings for product, service line, sensitivity, audience and detail; personalisation by prompt, chips, customer topics and industry rules for 4 industries; observations with evidence, discussion points and actions; PowerPoint, PDF and Excel exports that follow the five steps; the fit page; methodology, data-readiness and architecture notes; a pitch deck generated from the same engine; a full test suite.

**Credibility (20).** Method status and provenance on every value; weakest-input rule; low/base/high ranges; the baseline is a visible choice; repair range 0.25 to 1.0 with A002 as the upper bound; extra replacements shown but not in the do-it-yourself total; net only with a contract price; euros, hours and CO₂e never summed; the AI never writes numbers (placeholders and a guard); intel keeps only searched, dated, safe sources; snapshot chips never call the API; "Prototype · synthetic data · not audited" everywhere.

**Data (15).** The L003 finding (≈10.8× over the year; monthly 9.6 to 12.6×) flagged as a WARNING with lower confidence and Q35. Bad rows go to quarantine with reasons. The Data readiness page maps every field to the pack, a future approved Lindström source and its gap, now including service-line and industry master data, contract prices and CRM legal names for intel.

**Usability (10).** Simple mode by default, "about X (between A and B)", a guided five-step meeting with one message and big compact numbers per step, "What to say" lines with a Copy button, glossary tooltips, Expert mode one click away; decimal comma or dot both work in the inputs; one Export menu, Next/Back or arrow keys between steps; works without the AI.

**Scalability (10).** Sources are listed in `config/sources.yaml`; a generic CSV adapter added a customer, industry, country and service line with data and config only, and a test proves a further one needs no code. One `ReviewModel` serves the dashboard, three export formats and a future eLindström embed. Tier 0 to 3 roadmap from the synthetic pack to a module inside eLindström.

## Fallbacks

- If the AI is slow or unavailable, nothing changes except the narrative wording (template). Account intelligence shows the snapshot. Say so; it is a feature.
- If a prompt is not recognised, the view stays unchanged and the message says "Not recognised"; use a suggested prompt chip.
- If the PDF viewer is slow to open, show the PowerPoint instead; both come from the same model.
- `VR_EXTENSIONS=off` gives the before picture (3 customers) if someone asks to see it.
- Do not claim the figures are real, audited or verified. Do not read the savings as a Lindström claim.
