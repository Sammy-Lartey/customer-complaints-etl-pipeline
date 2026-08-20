from sqlalchemy import text
from sqlalchemy.engine import Engine


def upsert_customers(engine: Engine) -> int:
    # Customers have a real, stable identity (customerId, via the crosswalk
    # table) -- so this is a genuine upsert: new customers get inserted,
    # existing ones get their attributes refreshed if anything changed
    # (e.g. a name correction upstream), without touching their row's
    # history or duplicating them.
    upsert_sql = text("""
        INSERT INTO gold.customers
            ("customerId", "profileId", "number", "number2", "name",
             "gender", "dateOfBirth", "accountType", "branch")
        SELECT
            "customerId", "profileId", "number", "number2", "name",
            "gender", "dateOfBirth", "accountType", "branch"
        FROM staging.customers
        ON CONFLICT ("customerId") DO UPDATE SET
            "profileId"    = EXCLUDED."profileId",
            "number"       = EXCLUDED."number",
            "number2"      = EXCLUDED."number2",
            "name"         = EXCLUDED."name",
            "gender"       = EXCLUDED."gender",
            "dateOfBirth"  = EXCLUDED."dateOfBirth",
            "accountType"  = EXCLUDED."accountType",
            "branch"       = EXCLUDED."branch"
    """)
    with engine.begin() as conn:
        result = conn.execute(upsert_sql)
        return result.rowcount


def replace_complaints(engine: Engine) -> int:
    # Complaints have no stable identity of their own in the source data
    # (no complaint ID exists anywhere upstream), and a customer can
    # legitimately file the same kind of complaint multiple times over
    # their lifetime -- so there's no meaningful "is this the same
    # complaint as last time" check to make. staging.complaints is already
    # correctly deduplicated and identity-resolved, so gold.complaints is
    # just a full refresh from that -- honest about what the data
    # actually supports, rather than inventing a synthetic complaint key
    # with no real meaning.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE gold.complaints"))
        result = conn.execute(text("""
            INSERT INTO gold.complaints
                ("customerId", "profileId", "number", "number2", "location",
                 "region", "logDate", "complaintSource", "natureOfComplaint",
                 "subject", "detailsOfComplaint", "comment", "updates",
                 "status", "turnaroundTime", "resolutionDate",
                 "reasonForReversalRequest", "assign", "nameOfCcRep")
            SELECT
                "customerId", "profileId", "number", "number2", "location",
                "region", "logDate", "complaintSource", "natureOfComplaint",
                "subject", "detailsOfComplaint", "comment", "updates",
                "status", "turnaroundTime", "resolutionDate",
                "reasonForReversalRequest", "assign", "nameOfCcRep"
            FROM staging.complaints
        """))
        return result.rowcount


def run_gold_load(engine: Engine) -> tuple[int, int]:
    customer_count = upsert_customers(engine)
    complaint_count = replace_complaints(engine)
    return customer_count, complaint_count