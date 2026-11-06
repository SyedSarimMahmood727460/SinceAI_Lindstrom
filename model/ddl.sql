CREATE TABLE org_node (
    node_id VARCHAR PRIMARY KEY, parent_id VARCHAR, level VARCHAR, name VARCHAR,
    industry VARCHAR, segment VARCHAR, country VARCHAR, city VARCHAR, site_type VARCHAR,
    primary_laundry_id VARCHAR, priority_topics VARCHAR[]
);
CREATE TABLE product (
    product_id VARCHAR PRIMARY KEY, name VARCHAR, product_group VARCHAR, service_line VARCHAR,
    weight_kg DOUBLE, footprint_kgco2e DOUBLE, purchase_cost_eur DOUBLE
);
CREATE TABLE laundry (laundry_id VARCHAR PRIMARY KEY, name VARCHAR, country VARCHAR);
CREATE TABLE fact_service_month (
    month VARCHAR, customer_id VARCHAR, site_id VARCHAR, product_id VARCHAR, laundry_id VARCHAR,
    active_wearers DOUBLE, allocated_pieces DOUBLE, active_assets_scanned DOUBLE,
    washed_pieces DOUBLE, packed_pieces DOUBLE, washed_kg DOUBLE, service_requests DOUBLE,
    method_status VARCHAR, provenance VARCHAR, source_id VARCHAR, load_id VARCHAR
);
CREATE TABLE fact_service_cycle (
    asset_id VARCHAR, cycle_number INTEGER, customer_id VARCHAR, site_id VARCHAR,
    product_id VARCHAR, laundry_id VARCHAR, pickup_timestamp TIMESTAMP,
    in_laundry_timestamp TIMESTAMP, out_laundry_timestamp TIMESTAMP,
    delivered_timestamp TIMESTAMP, cycle_hours DOUBLE, performance_flag VARCHAR, month VARCHAR,
    method_status VARCHAR, provenance VARCHAR, source_id VARCHAR, load_id VARCHAR
);
CREATE TABLE fact_repair_month (
    month VARCHAR, customer_id VARCHAR, site_id VARCHAR, product_id VARCHAR, laundry_id VARCHAR,
    repair_type VARCHAR, repair_count DOUBLE,
    method_status VARCHAR, provenance VARCHAR, source_id VARCHAR, load_id VARCHAR
);
CREATE TABLE fact_laundry_month (
    laundry_id VARCHAR, month VARCHAR, washed_kg DOUBLE, fresh_water_l DOUBLE,
    process_energy_kwh DOUBLE, process_kgco2e DOUBLE, delivery_kgco2e DOUBLE,
    method_status VARCHAR, provenance VARCHAR, source_id VARCHAR, load_id VARCHAR
);
CREATE TABLE fact_waste_month (
    laundry_id VARCHAR, month VARCHAR, route VARCHAR, kg DOUBLE,
    method_status VARCHAR, provenance VARCHAR, source_id VARCHAR, load_id VARCHAR
);
CREATE TABLE quarantine ("table" VARCHAR, row_json VARCHAR, reason VARCHAR);
CREATE TABLE dq_flags (
    check_id VARCHAR, severity VARCHAR, entity_type VARCHAR, entity_id VARCHAR,
    month VARCHAR, detail VARCHAR
);
CREATE TABLE source (
    source_id VARCHAR, name VARCHAR, tier INTEGER, system VARCHAR, approved BOOLEAN,
    loaded_at TIMESTAMP, load_id VARCHAR
);
