-- gold.customers: one row per resolved identity, upserted (never wiped).
-- customerId is generated in Phase 3, backed by the persistent crosswalk
-- in gold.customer_identity_map -- stable across every run.
CREATE TABLE IF NOT EXISTS gold.customers (
    "customerId"   VARCHAR(26) PRIMARY KEY,
    "profileId"    VARCHAR(50),
    "number"       VARCHAR(20) NOT NULL,
    "number2"      VARCHAR(20),
    "name"         VARCHAR(150) NOT NULL,
    "gender"       VARCHAR(20),
    "dateOfBirth"  DATE,
    "accountType"  VARCHAR(50),
    "branch"       VARCHAR(100)
);

-- gold.complaints: fully refreshed from staging every run (see
-- load_gold.py for why -- no stable complaint-level identity exists in
-- the source data, and a customer can legitimately file the same kind of
-- complaint more than once). id is a surrogate key that only needs to be
-- unique WITHIN a given load, not stable across runs.
CREATE TABLE IF NOT EXISTS gold.complaints (
    id                         SERIAL PRIMARY KEY,
    "customerId"                VARCHAR(26) NOT NULL REFERENCES gold.customers("customerId"),
    "profileId"                VARCHAR(50),
    "number"                    VARCHAR(20) NOT NULL,
    "number2"                   VARCHAR(20),
    "location"                  VARCHAR(150),
    "region"                    VARCHAR(50),
    "logDate"                   DATE NOT NULL,
    "complaintSource"           VARCHAR(100),
    "natureOfComplaint"         VARCHAR(150),
    "subject"                   VARCHAR(255),
    "detailsOfComplaint"        TEXT,
    "comment"                   TEXT,
    "updates"                   TEXT,
    "status"                    VARCHAR(50),
    "turnaroundTime"            INTEGER,
    "resolutionDate"            DATE,
    "reasonForReversalRequest"  TEXT,
    "assign"                    VARCHAR(100),
    "nameOfCcRep"                VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_gold_complaints_customer_id
    ON gold.complaints ("customerId");
CREATE INDEX IF NOT EXISTS idx_gold_complaints_region
    ON gold.complaints ("region");