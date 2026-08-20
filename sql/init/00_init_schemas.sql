-- Runs once, automatically, when postgres-warehouse first starts.
-- We create schemas up front instead of drop/recreate per run --
-- schema structure is stable, only the DATA inside gets refreshed.

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS staging.ingestion_log (
    id SERIAL PRIMARY KEY,
    sheet_name VARCHAR(255) NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    row_count INT NOT NULL,
    bronze_path VARCHAR(500) NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (sheet_name, source_file, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_sheet_name ON staging.ingestion_log(sheet_name);  


-- Stub for the external client table this pipeline depends on but doesn't
-- own (in reality, owned by an upstream CRM/core banking system).

CREATE TABLE IF NOT EXISTS public.client (
    "profileId"         VARCHAR(50) PRIMARY KEY,
    "accountHolderName" VARCHAR(150),
    "gender"            VARCHAR(20),
    "phoneNumber"        VARCHAR(20),
    "phoneNumber2"       VARCHAR(20),
    "region"            VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_client_phone ON public.client("phoneNumber");

CREATE TABLE IF NOT EXISTS gold.customer_identity_map (
    resolution_key VARCHAR(100) PRIMARY KEY,
    customer_id    VARCHAR(26) UNIQUE NOT NULL,
    first_seen     TIMESTAMP NOT NULL DEFAULT NOW()
);

