# Cus_Pipeline

> A customer support data pipeline that transforms raw customer support data into clean, analytics-ready datasets. Built in **Python**, orchestrated with **Apache Airflow**, containerized with **Docker**, and stored and modeled in **PostgreSQL** following a Medallion Architecture.

Cus_Pipeline is a rebuild of the first data pipeline I worked on, redesigned using the data engineering practices and concepts I've learned since then.

The original pipeline processed customer support data exported from Excel and prepared it for reporting and analysis. This version focuses on **incremental processing, idempotency, data quality, reproducibility, maintainability, and reliable orchestration**.

Rather than reprocessing an entire dataset on every run, Cus_Pipeline detects new or changed source data, processes only what is necessary, and safely supports repeated pipeline runs.

---

## Architecture

Cus_Pipeline follows a **Medallion Architecture** consisting of Bronze, Silver, and Gold layers.

```text
                    ┌─────────────────────┐
                    │      SOURCE         │
                    │                     │
                    │ Excel Workbooks     │
                    │ Monthly Sheets      │
                    │ Synthetic Data      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       BRONZE        │
                    │                     │
                    │ Raw Parquet Data    │
                    │ SHA-256 Hashing     │
                    │ Ingestion Logging   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │       SILVER        │
                    │                     │
                    │ Cleaning            │
                    │ Standardization     │
                    │ Validation          │
                    │ Data Quality Checks │
                    │ Resolution Logic    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │        GOLD         │
                    │                     │
                    │ Analytics-ready     │
                    │ PostgreSQL Tables   │
                    │ Views               │
                    │ Materialized Views  │
                    │ Indexes              │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      Metabase       │
                    │                     │
                    │ BI / Reporting      │
                    │ Read-only Access    │
                    └─────────────────────┘

                    ▲
                    │
            ┌───────┴────────┐
            │ Apache Airflow │
            │ Orchestration  │
            └────────────────┘
```

Apache Airflow orchestrates the pipeline, while Docker Compose provides a reproducible local development environment.

---

## Why This Rebuild?

The original pipeline worked, but it had several limitations common in early-stage ETL workflows:

- Full datasets could be reprocessed unnecessarily.
- Re-running the pipeline could produce duplicate or inconsistent results.
- Source changes were not explicitly tracked.
- Ingestion and transformation responsibilities were tightly coupled.
- Data quality handling was inconsistent.
- Pipeline state was difficult to reason about.
- The workflow had limited protection against repeated processing.

Cus_Pipeline addresses these limitations through:

- **Incremental ingestion**
- **Idempotent processing**
- **Source-data hashing**
- **Ingestion logging**
- **Medallion architecture**
- **Data quality validation**
- **Customer identity mapping**
- **Separation of pipeline stages**
- **Containerized infrastructure**
- **Airflow orchestration**
- **Automated tests**

---

# Key Features

## Incremental Ingestion

Source Excel sheets are hashed using **SHA-256** during ingestion.

The generated hash is compared against the pipeline's ingestion history to determine whether a sheet is new or has changed.

```text
Source Sheet
     │
     ▼
Calculate SHA-256
     │
     ▼
Compare with ingestion history
     │
     ├── Unchanged ──► Skip
     │
     └── New/Changed ──► Process
```

This prevents unchanged source data from being repeatedly ingested and transformed.

---

## Idempotent Processing

The pipeline is designed to safely handle repeated runs.

Running the same source data multiple times should not result in unnecessary duplicate processing or inconsistent downstream state.

This is particularly important when working with Airflow, where tasks can be retried and DAGs can be manually rerun.

The pipeline therefore separates:

- Source change detection
- Ingestion
- Cleaning and transformation
- Resolution processing
- Customer identity mapping
- Database loading

---

## Medallion Architecture

### Bronze

The Bronze layer contains landed source data with minimal transformation.

Responsibilities include:

- Reading source workbooks
- Processing individual sheets
- Calculating source hashes
- Recording ingestion activity
- Writing raw data to Parquet

Bronze data is stored under:

```text
data/bronze/
```

---

### Silver

The Silver layer contains cleaned, standardized, and validated data.

Transformations include:

- Column normalization
- Data type standardization
- Phone number normalization
- Region correction
- Date handling
- Turnaround-time validation
- Data cleaning
- Resolution processing
- Data quality checks

Silver data is stored under:

```text
data/silver/
```

---

### Gold

The Gold layer contains analytics-ready data loaded into PostgreSQL.

Rather than storing Gold as another local file layer, Cus_Pipeline uses PostgreSQL as the final analytical storage layer.

The Gold layer includes:

- Customer data
- Complaint data
- Resolution information
- Customer identity mappings
- Analytical views
- Materialized views
- Supporting indexes

This provides a relational interface for downstream reporting and BI workloads.

---

# Data Quality

Data quality is treated as a pipeline responsibility rather than something left entirely to downstream reporting users.

Cus_Pipeline includes dedicated quality-check logic in:

```text
scripts/quality_checks.py
```

### Region Validation

Known Ghanaian regions are validated and standardized.

Fuzzy matching is used where appropriate to identify and correct inconsistent region values.

### Phone Number Standardization

Phone numbers are normalized into a consistent format, including conversion to Ghana's international format where applicable.

### Turnaround Time Validation

Complaint logging and resolution timestamps are validated to ensure that calculated turnaround times are meaningful.

Where timestamps produce negative turnaround times, the pipeline evaluates whether the values have been reversed and corrects them when appropriate.

Missing turnaround times are identified rather than silently discarded.

---

# Customer Identity Management

Cus_Pipeline separates source-system customer information from the internal customer identity used by the analytical pipeline.

Customer records are matched against client reference data and assigned stable identifiers using **ULIDs**.

The repository includes a dedicated identity mapping table and supporting SQL objects to maintain this relationship.

This allows the pipeline to:

- Maintain stable customer identities
- Avoid unnecessary reassignment of identifiers
- Separate source identifiers from analytical identifiers
- Support repeatable pipeline runs

Client seed data for the local development environment is generated using:

```text
scripts/generate_client_seed.py
```

---

# Resolution Processing

Complaint resolution is handled as a dedicated stage of the pipeline through:

```text
scripts/resolution.py
```

This keeps resolution-related business logic separate from the core ingestion and cleaning processes.

Resolution information ultimately becomes part of the analytics-ready customer support dataset.

---

# Data Model

Cus_Pipeline separates customer-level information from complaint-level information.

### Customer

Customer-level attributes include:

- Customer identifier
- Name
- Gender
- Date of birth
- Account type
- Branch
- Profile identifier

### Complaint

Complaint-level information includes:

- Complaint identifier
- Customer identifier
- Complaint details
- Complaint category
- Logging date
- Resolution date
- Turnaround time
- Resolution result
- Other complaint attributes

Separating these entities reduces unnecessary repetition of customer information across complaint records and provides a cleaner analytical model.

---

# PostgreSQL Analytics Layer

PostgreSQL serves as the analytical storage layer for the Gold data.

The repository contains SQL for:

- Schema initialization
- Gold table creation
- Customer identity mapping
- Index creation
- Analytical views
- Materialized views
- Metabase read-only access

```text
sql/
├── 03_indexes.sql
├── 04_views.sql
└── 05_materialized_view.sql

sql/init/
├── 00_init_schemas.sql
├── 01_seed_client.sql
├── 02_create_gold_tables.sql
├── 03_create_identity_map.sql
├── 04_indexes.sql
├── 05_views.sql
├── 06_materialized_view.sql
└── 07_metabase_readonly_role.sql
```

A dedicated read-only database role is provided for Metabase so that BI workloads do not require write access to the analytical database.

---

# Technology Stack

| Technology | Purpose |
|---|---|
| **Python** | Pipeline logic and data transformation |
| **Pandas** | Data processing |
| **SQLAlchemy** | PostgreSQL connectivity |
| **PostgreSQL** | Gold / analytical storage |
| **Apache Airflow** | Workflow orchestration |
| **Docker** | Containerization |
| **Docker Compose** | Local multi-service environment |
| **Parquet** | Bronze and Silver storage |
| **RapidFuzz** | Fuzzy matching and data standardization |
| **ULID** | Stable internal identifiers |
| **Metabase** | BI and reporting |
| **Pytest** | Automated testing |
| **Git** | Version control |

---

# Project Structure

```text
Cus_Pipeline/
│
├── dags/
│   └── customer_support_pipeline_dag.py
│
├── data/
│   ├── .gitkeep
│   ├── source/
│   │   └── .gitkeep
│   ├── bronze/
│   │   └── .gitkeep
│   └── silver/
│       └── .gitkeep
│
├── scripts/
│   ├── cleaning.py
│   ├── generate_client_seed.py
│   ├── generate_synthetic_source.py
│   ├── ingestion.py
│   ├── load_gold.py
│   ├── quality_checks.py
│   └── resolution.py
│
├── sql/
│   ├── 03_indexes.sql
│   ├── 04_views.sql
│   ├── 05_materialized_view.sql
│   │
│   └── init/
│       ├── 00_init_schemas.sql
│       ├── 01_seed_client.sql
│       ├── 02_create_gold_tables.sql
│       ├── 03_create_identity_map.sql
│       ├── 04_indexes.sql
│       ├── 05_views.sql
│       ├── 06_materialized_view.sql
│       └── 07_metabase_readonly_role.sql
│
├── tests/
│   ├── conftest.py
│   ├── test_cleaning.py
│   └── test_resolution.py
│
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

# Pipeline Flow

The pipeline can be summarized as:

```text
1. Generate / receive source data
                │
                ▼
2. Read Excel workbook
                │
                ▼
3. Process individual sheets
                │
                ▼
4. Generate SHA-256 hash
                │
                ▼
5. Check ingestion history
                │
                ├── Already processed & unchanged
                │             │
                │             └──► Skip
                │
                └── New / changed
                              │
                              ▼
6. Write Bronze Parquet
                              │
                              ▼
7. Clean and standardize
                              │
                              ▼
8. Run data quality checks
                              │
                              ▼
9. Process resolution data
                              │
                              ▼
10. Write Silver Parquet
                              │
                              ▼
11. Map customer identities
                              │
                              ▼
12. Load Gold data
                              │
                              ▼
13. Create / refresh analytical objects
                              │
                              ▼
14. Consume through Metabase
```

Airflow manages the execution and dependency order of these stages.

---

# Synthetic Data

The repository includes:

```text
scripts/generate_synthetic_source.py
```

which can be used to generate synthetic customer support source data for local development and testing.

This allows the pipeline to be demonstrated without relying on proprietary production data.

Client reference data can similarly be generated using:

```text
scripts/generate_client_seed.py
```

This makes the project reproducible as a standalone portfolio project.

---

# Testing

The project includes automated tests using **Pytest**.

Current test coverage includes:

```text
tests/
├── conftest.py
├── test_cleaning.py
└── test_resolution.py
```

Tests cover important transformation and resolution logic independently of the full Airflow workflow.

Run the test suite with:

```bash
pytest
```

---

# Running the Project

## Prerequisites

Make sure the following are installed:

- Docker
- Docker Compose
- Git
- Python 3.12+ if running the pipeline logic or tests outside Docker

PostgreSQL and Airflow do not need to be installed directly when using the provided Docker environment.

---

## Clone the Repository

```bash
git clone <repository-url>

cd Cus_Pipeline
```

---

## Configure Environment Variables

Create a local `.env` file from the provided example:

```bash
cp .env.example .env
```

Populate the required values in `.env`.

**Do not commit `.env` to version control.**

The `.env.example` file documents the configuration required to run the project without exposing actual credentials.

---

## Start the Environment

Build and start the containers:

```bash
docker compose up -d --build
```

Check the running services:

```bash
docker compose ps
```

View container logs:

```bash
docker compose logs -f
```

---

## Run the Pipeline

Once the environment is running:

1. Open the Airflow web interface.
2. Locate the `customer_support_pipeline` DAG.
3. Trigger the DAG.
4. Monitor task execution through the Airflow interface.
5. Verify the resulting Gold tables and analytical objects in PostgreSQL.
6. Connect to the data through Metabase using the configured read-only role.

---

# Local Development

The project separates application logic from infrastructure responsibilities.

### Docker handles

- Apache Airflow
- PostgreSQL
- Metabase
- Supporting services

### Python handles

- Source ingestion
- Data cleaning
- Transformation
- Data quality checks
- Resolution processing
- Customer identity management
- Gold loading

This allows pipeline logic to be developed and tested independently while keeping the infrastructure reproducible.

---

# Example Pipeline Results

During development, the pipeline successfully demonstrated processing of a synthetic customer support dataset:

```text
Aligned all sheets to have 25 columns

Merged DataFrame shape: (1035, 25)

Cleaned data:
1029 rows, 25 columns

Invalid TATs:
3 negative
3 swapped
11 missing

Valid TATs:
1024
negative: 0
swapped: 3
missing: 5

Customer records:
951

Complaint records:
1029
```

These figures represent the development dataset and may change as the synthetic source data or pipeline logic evolves.

---

# Reliability Considerations

Cus_Pipeline is designed around several principles used in reliable data platforms.

### Re-runnable

The pipeline is designed to safely handle repeated executions.

### Incremental

Unchanged source sheets are identified through hashing and skipped rather than unnecessarily reprocessed.

### Idempotent

Pipeline reruns should not arbitrarily create duplicate downstream records or regenerate customer identities.

### Observable

Ingestion activity is recorded so the pipeline can determine what source data has already been processed.

### Validated

Data quality checks are performed during the transformation process.

### Reproducible

Docker Compose and synthetic source generation make the project reproducible without requiring access to production data.

### Maintainable

Ingestion, cleaning, quality checks, resolution processing, database loading, and orchestration are separated into distinct components.

---

# Design Decisions

## Why Parquet?

Parquet is a columnar storage format well suited to analytical workloads and intermediate pipeline stages.

It provides an efficient boundary between the source data and the structured PostgreSQL layer.

## Why PostgreSQL?

PostgreSQL provides reliable relational storage for the Gold layer and supports the analytical views, materialized views, indexes, and downstream BI workloads used by the project.

## Why Airflow?

The pipeline contains multiple dependent processing stages that benefit from explicit orchestration, scheduling, retries, and task-level observability.

## Why Docker?

Docker provides a consistent environment for running the pipeline's infrastructure without requiring each service to be installed and configured manually.

## Why ULIDs?

ULIDs provide stable, globally unique internal identifiers while keeping the analytical model independent from source-system identifiers.

## Why Hash the Source Data?

SHA-256 hashing allows the pipeline to detect whether an individual source sheet has changed.

This enables incremental ingestion without relying solely on filenames or timestamps.

## Why a Read-only Metabase Role?

BI tools should not require write access to the analytical database.

Cus_Pipeline therefore creates a dedicated read-only role for Metabase, providing a safer boundary between reporting workloads and the underlying data platform.

---

# Data Security

Sensitive configuration values should be supplied through environment variables.

The following should **never** be committed to the repository:

- Database passwords
- API keys
- Access tokens
- Private credentials
- Production connection strings
- Other secrets

Use `.env.example` to document required configuration without exposing actual credentials.

The repository contains only synthetic development data and generated seed data.

---

# Future Improvements

Potential future iterations include:

- Expanded unit and integration test coverage
- CI/CD with GitHub Actions
- Automated pipeline monitoring and alerting
- More comprehensive data quality reporting
- Data lineage
- Cloud deployment
- Object storage for Bronze data
- Infrastructure as Code
- Production-grade secret management
- Additional analytical marts
- More comprehensive observability and pipeline metrics

---

# What This Project Demonstrates

Cus_Pipeline demonstrates practical data engineering concepts beyond simply moving data from one system to another.

It covers:

- ETL pipeline design
- Incremental data processing
- Idempotent workflows
- Source change detection
- Data ingestion
- Data cleaning
- Data validation
- Data quality engineering
- Data modeling
- Customer identity management
- PostgreSQL analytical design
- Workflow orchestration
- Containerization
- Automated testing
- BI integration
- Reproducible development environments

The project is intentionally designed as a **production-style rebuild**, applying lessons learned from an earlier pipeline to create a more reliable, maintainable, and reproducible data platform.

---

## License

This project is intended for educational and portfolio purposes.

---

## Author

**Samuel Lartey**

---

> **Cus_Pipeline** — turning messy customer support exports into reliable, analytics-ready data.