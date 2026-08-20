-- customerId is already indexed (it's the PRIMARY KEY on gold.customers,
-- and gold.complaints.customerId got its own index in 02_create_gold_tables.sql).
-- These cover the remaining lookup patterns: finding a customer by phone
-- or profileId, and joining complaints back to public.client by profileId.

CREATE INDEX IF NOT EXISTS idx_gold_customers_number
    ON gold.customers ("number");
CREATE INDEX IF NOT EXISTS idx_gold_customers_profile_id
    ON gold.customers ("profileId");
CREATE INDEX IF NOT EXISTS idx_gold_complaints_profile_id
    ON gold.complaints ("profileId");
CREATE INDEX IF NOT EXISTS idx_gold_complaints_number
    ON gold.complaints ("number");