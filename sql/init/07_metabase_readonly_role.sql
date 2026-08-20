-- local development only. Password comes from METABASE_READER_PASSWORD,
-- set in .env (never committed) and passed through docker-compose.yml.
\set metabase_pw `echo "$METABASE_READER_PASSWORD"`

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'metabase_reader') THEN
        EXECUTE format('CREATE ROLE metabase_reader WITH LOGIN PASSWORD %L', :'metabase_pw');
    END IF;
END
$$;

GRANT CONNECT ON DATABASE Cus_support TO metabase_reader;
GRANT USAGE ON SCHEMA gold TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO metabase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO metabase_reader;