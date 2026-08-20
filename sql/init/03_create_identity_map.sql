CREATE TABLE IF NOT EXISTS gold.customer_identity_map (
    resolution_key VARCHAR(100) PRIMARY KEY,
    customer_id    VARCHAR(26) UNIQUE NOT NULL,
    first_seen     TIMESTAMP NOT NULL DEFAULT NOW()
);