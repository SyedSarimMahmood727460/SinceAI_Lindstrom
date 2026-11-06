# Architecture

Three diagrams: layered overview, request flow, canonical data model. They render in any Mermaid-capable viewer (GitHub, VS Code).

## 1. Layered overview

```mermaid
flowchart LR
  subgraph S[Sources]
    T0[Tier 0: synthetic Excel pack]
    T1[Tier 1: BI / eLindström exports]
    T2[Tier 2: governed warehouse]
  end
  subgraph A[Source adapters]
    AD[extract, map, validate]
    Q[(quarantine + dq_flags)]
  end
  CM[(Canonical model - DuckDB)]
  CS[Config store: assumption set, metric registry, industry rules, modules]
  ME[Metric engine: the only source of numbers]
  IE[Insight engine: rules R1-R8, priorities]
  API[Review API: one ReviewModel per request]
  AI[AI layer: intent parser, narrator, guard]
  subgraph O[Outputs]
    D[Web dashboard]
    P[PPTX export]
    EL[future eLindström embed]
  end
  T0 --> AD
  T1 -.future.-> AD
  T2 -.future.-> AD
  AD --> CM
  AD --> Q
  CM --> ME
  CS --> ME
  CS --> IE
  ME --> IE
  ME --> API
  IE --> API
  API <--> AI
  API --> D
  API --> P
  API -.future.-> EL
```

## 2. Request flow

```mermaid
sequenceDiagram
  actor KAM
  participant UI as Dashboard
  participant IP as Intent parser (AI or keywords)
  participant ME as Metric engine
  participant IE as Insight engine
  participant NA as Narrator (AI, placeholders only, then guard)
  participant RM as ReviewModel
  participant PX as PPTX export
  KAM->>UI: prompt "Focus on water and emissions"
  UI->>IP: POST /intent
  IP-->>UI: ViewSpec (priorities, baseline, view, interpretation)
  UI->>RM: GET /accounts/{id}/review
  RM->>ME: compute KPIs, sites, trends, ranges
  ME-->>RM: MetricResults (value, range, status, provenance, lineage)
  RM->>IE: observations, discussion points, actions
  IE-->>RM: ranked by active priorities
  RM->>NA: structure + allowed placeholders (no numbers)
  NA-->>RM: text with placeholders, guarded, else template
  RM-->>UI: one ReviewModel
  KAM->>UI: Export
  UI->>PX: POST /reviews/export (same parameters)
  PX-->>KAM: PPTX built from the same ReviewModel
```

## 3. Canonical data model

```mermaid
erDiagram
  ORG_NODE ||--o{ ORG_NODE : "account has sites"
  ORG_NODE ||--o{ FACT_SERVICE_MONTH : site
  ORG_NODE ||--o{ FACT_SERVICE_CYCLE : site
  ORG_NODE ||--o{ FACT_REPAIR_MONTH : site
  PRODUCT ||--o{ FACT_SERVICE_MONTH : product
  PRODUCT ||--o{ FACT_SERVICE_CYCLE : product
  PRODUCT ||--o{ FACT_REPAIR_MONTH : product
  LAUNDRY ||--o{ FACT_SERVICE_MONTH : routed_to
  LAUNDRY ||--o{ FACT_LAUNDRY_MONTH : resources
  LAUNDRY ||--o{ FACT_WASTE_MONTH : waste
  SOURCE ||--o{ FACT_SERVICE_MONTH : loaded_by
  ORG_NODE {
    string node_id PK
    string parent_id
    string level "ACCOUNT or SITE"
    string industry
    string primary_laundry_id
    list priority_topics
  }
  PRODUCT {
    string product_id PK
    string product_group
    float weight_kg
    float footprint_kgco2e
    float purchase_cost_eur
  }
  LAUNDRY {
    string laundry_id PK
    string name
    string country
  }
  FACT_SERVICE_MONTH {
    string month
    float active_wearers
    float allocated_pieces
    float active_assets_scanned
    float washed_kg
    float service_requests
  }
  FACT_SERVICE_CYCLE {
    string asset_id
    float cycle_hours
    string performance_flag
  }
  FACT_REPAIR_MONTH {
    string repair_type
    float repair_count
  }
  FACT_LAUNDRY_MONTH {
    float washed_kg
    float fresh_water_l
    float process_energy_kwh
    float process_kgco2e
    float delivery_kgco2e
  }
  FACT_WASTE_MONTH {
    string route "recycling, reuse, energy_recovery, incineration"
    float kg
  }
  SOURCE {
    string source_id PK
    int tier
    bool approved
    string load_id
  }
```

Every fact row also carries `method_status`, `provenance`, `source_id` and `load_id`. Two further tables, `quarantine` (rejected rows with reasons) and `dq_flags` (WARNING-level consistency findings), sit beside the model.

## Notes

- The pack has no delivery-customer level, so sites hang directly under the account.
- Allocation of laundry resources to customers happens in `metrics/frames.py` (per kg), not in the stored tables.
- Spec items not built: PDF export, the Q&A agent, authentication, real source connections.
