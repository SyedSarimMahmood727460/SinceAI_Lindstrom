# Data readiness note

**Prototype · synthetic data · not audited.** This note says which data the review needs, where each field comes from today (the synthetic pack), which approved Lindström source would replace it, and what is still missing. The same table is shown on the Data readiness page and in the PPTX appendix (`config/review_text.yaml`, `gaps`).

Status key: **Ready** = the pack field maps cleanly and the real source is expected to match. **Partial** = usable, but a definition or a consistency question is open. **Gap** = the value is an assumption or a placeholder and a real source is needed.

## 1. Field to source to status

| Field needed | Pack sheet and columns (Tier 0) | Future approved Lindström source | Status | Gap / open point |
|---|---|---|---|---|
| Customer hierarchy (account, sites, industry, priority topics) | `Customers`, `Sites` | Customer master data / eLindström account structure | Partial | Pack has account and site only; no delivery-customer level. Enterprise customer master data is not solved here. |
| Active wearers | `Service_Activity.active_wearers` | eLindström user and garment assignment | Gap | Monthly counts per site × product only. Same wearer may appear in several product rows; de-duplicated as max across products (T2, to confirm). |
| Allocated garments | `Service_Activity.allocated_pieces` | Garment assignment / inventory system | Partial | Counts per site × product × month. |
| Scans (utilisation) | `Service_Activity.active_assets_scanned` | RFID and scan events | Partial | Meaning of the allocated-versus-scanned gap is unconfirmed; shown as "not scanned in use". |
| Washed kg per customer | `Service_Activity.customer_washed_kg` | Laundry production system | Partial | Fails check C1 for laundry L003 (see section 3, Q35). |
| Washing %: washed and packed pieces | `Service_Activity.washed_pieces`, `packed_pieces` | Laundry production system | Ready | Share of garments washed = washed pieces / allocated pieces. |
| Service cycles and on-time flag | `Service_Cycles` (pickup, in, out, delivered timestamps, `performance_flag`) | Route and delivery system | Partial | Cycle month = month of pickup. `LATE` definition used as supplied (Q17). |
| Service requests | `Service_Activity.service_requests` | Service request / ticketing system | Partial | Counts only; no type breakdown, so the "break down by type" action cannot yet be evidenced. |
| Repairs | `Repairs` (`repair_type`, `repair_count`) | Repair workshop system and order history | Gap | Counts are usable. Postponed replacements are an assumption (A002), not an observed outcome. The pack's derived columns are not ingested. |
| Laundry water, energy, CO2e | `Laundry_Resources` (fresh water l, process energy kWh, process and delivery kgCO2e) | Laundry process metering (Tier 1 BI export) | Partial | Monthly laundry totals. Allocated to customers by washed kg (A003). L003 volume inconsistent with customer kg. |
| Waste routes | `Waste_Circularity` (recycling, reuse, energy recovery, incineration kg) | Laundry waste reporting | Partial | Attributed to the customer by washed-kg share (A003). Baseline assumes 100% mixed waste (A004). |
| Product footprints and cost | `Products` (`synthetic_product_footprint_kgco2e`, `synthetic_purchase_cost_eur`, weight) | Product master data and LCA | Gap | Synthetic (A005, confidence Low). Idle stock value is internal only until cost metrics are approved (Q20). |
| Baseline factors | `Baselines` (via the assumption set `config/assumptions/v1.yaml`) | Approved public or customer-specific emission factors | Gap | Illustrative values; need approval before external use. Baseline choice to confirm with the customer (A001, Q10). |
| Assumption register | `Assumptions` (A001-A008) plus team T1, T2 | Governed assumption set owned by Lindström sustainability | Partial | Versioned YAML in this prototype; needs an owner and an approval process. |

Not ingested as data, used as test reference only: `Customer_Impacts`, `Sample_Output`, and the derived columns of `Repairs`.

## 2. How the prototype treats data quality

- **ERROR rows** (unknown site, product, laundry or customer; missing key; invalid month; non-numeric or negative measure; site not belonging to the stated customer) go to the `quarantine` table with a reason. They are never silently dropped. The pack has none. `VR_INJECT_BAD_ROWS=1` injects 3 to demonstrate it.
- **WARNING findings** (C1 laundry volume, C2 primary laundry mismatch, C3 wearers above allocated pieces) are stored in `dq_flags`. The rows still load. Metrics derived from flagged laundry-months get confidence lowered by one level and a warning icon, and observation R8 asks Lindström to confirm the data.
- Every figure keeps its `method_status` and `provenance` through to the dashboard and the deck.

## 3. The open consistency finding (Q35)

Customer kg routed to laundry L003 (Nordic Malmö WWS) in 2025 is 335,824 kg, against 31,017 kg reported by the laundry itself, about 10.8 times as much. It touches all 6 Apex sites and 6 NorthStar sites in Sweden. Allocation is per kg, so figures remain computable, but they are flagged as less certain.

**Q35 to Lindström:** is the L003 volume gap deliberate or an error, and which figure is authoritative? Until it is answered, the figures for affected sites should not be used externally.

## 4. Source roadmap

| Tier | Source | What it adds | Approval needed |
|---|---|---|---|
| **0** | Synthetic Excel pack (built, `adapters/excel_pack.py`) | End-to-end demo; all values `SYNTHETIC`. | None |
| **1** | Scheduled BI / eLindström exports of the same fields (CSV or Excel) for one real pilot customer | First `APPROVED_REAL` values; checks C1-C3 and quarantine run on real rows; measured fields can move from `CALCULATED` to `MEASURED` where the source is a system of record. | Data owner sign-off per field; customer consent |
| **2** | Governed warehouse / data platform with a stable schema | Scheduled loads, history, many customers; same canonical model, no change after the adapters. | Platform access; data governance |
| **3** | Embedded in eLindström as a module or API consumer of the review service; optional extra service lines | Customer self-service views; service lines beyond workwear; more countries and industries via config. | Product ownership; security review; wording and claims approval |

Production would also need authentication and tenancy, approved emission factors, a governed assumption register, an approval workflow for external claims, and an audit of the method if the figures are to be used in reporting.

## 5. How to add an adapter

1. Create `adapters/<source>.py` with a class that has `source_id`, `tier`, `extract() -> dict of raw frames` and `to_canonical(raw) -> dict of canonical frames` (protocol in `adapters/base.py`; model it on `adapters/excel_pack.py`).
2. Return the eight canonical frames named in `model/load.py` (`TABLES`): `org_node`, `product`, `laundry`, `fact_service_month`, `fact_service_cycle`, `fact_repair_month`, `fact_laundry_month`, `fact_waste_month`. Columns follow `model/ddl.sql`. Waste is one row per laundry × month × route.
3. Tag every fact row with `method_status` (use `MEASURED` only for system-of-record readings), `provenance` (`APPROVED_REAL` only after approval), `source_id` and `load_id`.
4. Do not clean data in the adapter. Rows are validated afterwards by `model/validate.py` (ERROR to quarantine) and the consistency checks (WARNING to `dq_flags`). Add rules there if the source introduces new keys.
5. Call the adapter from `load_pack` in `model/load.py` and register its row in the `source` table (`tier`, `approved`).
6. Add a test that loads a small fixture and checks quarantine and flags. The metric engine, insight rules, API, dashboard and PPTX need no change.
