# Cus_Pipeline

Customer support teams often export complaints from Excel. This project takes that kind of workbook, cleans it, and loads it into a database you can chart.

It is a rebuild of the first pipeline I worked on. The old version reprocessed everything, and running it twice could duplicate rows. This version skips spreadsheet tabs that have not changed, keeps the same customer IDs across runs, and stops if the data looks too broken to trust.

You run it on your own machine with Docker. The point is the design, not a live company deployment.

The folders still use the names `bronze`, `silver`, and `gold` because that is how the files and database are laid out. In plain terms they mean **raw copy**, **cleaned file**, and **reporting tables**.

---

## The problem

The source is a monthly Excel file. Each tab is a month of complaints. Names, phone numbers, regions, and dates are inconsistent. There is no reliable complaint ID. A customer can file the same kind of complaint more than once, so the pipeline cannot treat two similar rows as “the same complaint.”

A fake customer list stands in for the bank’s real customer system (the pipeline does not own that system). About 60% of phones in the spreadsheet overlap that list, the way a real extract only partly matches a CRM.

The Excel in this repo is generated and contains no real customer data.

---

## What happens when the pipeline runs

```text
Excel file (one tab per month)
        │
        ▼
Raw copies of each changed tab     data/bronze/
        │
        ▼
One cleaned file                   data/silver/
        │
        ▼
Working tables in Postgres         staging (match customers, set aside bad rows)
        │
        ▼
Reporting tables in Postgres       gold.customers and gold.complaints
        │
        ▼
Ready-made report queries  →  charts in Metabase
```

**1. Copy only what changed.**  
Each tab is given a fingerprint of its contents. If the tab looks the same as last successful run, it is not copied again. The `Unresolved` tab is ignored.

**2. Clean everything we have.**  
If at least one tab *did* change, all of the raw copies are merged and cleaned into a single file: phone numbers, Ghana regions, dates, and how many days a complaint took to close. Unchanged tabs are not “incrementally merged” into the database row by row. The cleaned file is rebuilt from the full set of raw copies.

**3. Split customers from complaints, then identify people.**  
Customer details and complaint details are split apart. Phones are matched to the customer list. Each person gets a stable ID that the pipeline remembers. Next month, the same person keeps the same ID.

**4. Load the reporting database.**  
Known customers are inserted or updated. Complaint rows are wiped and loaded fresh from this run’s cleaned data. That is honest: the spreadsheet is a full current picture, not a stream of new events with IDs.

**5. Remember the fingerprints last.**  
Only after the reporting tables succeed does the pipeline record “this tab was processed.” If cleaning or loading fails, the next run tries those tabs again.

**6. Refresh reports.**  
Indexes and saved queries used for charts are created or refreshed.

If nothing in the spreadsheet changed, steps 2–6 are skipped.

The pipeline also refuses to finish when data looks wrong: a name or region missing after cleaning, too many complaints that cannot be loaded (more than 20%), duplicate customer IDs, or empty reporting tables. A large drop in row count from the raw copies to the cleaned file is logged as a warning but does not stop the run. Complaints with no phone and no customer match, or with no log date, are written to a side table (`staging.rejected_complaints`) instead of being deleted quietly.

Cleaning that matches this spreadsheet:

- Ghana region spellings. Ambiguous values such as `"Upper"` become `Unknown` rather than a guess
- Excel phone numbers (including numbers that arrived as `540663527.0`) into `+233…`
- Negative “days to close” when the log date and resolution date were swapped

---

## What you can query at the end

Two main tables:

- **Customers** — one row per person the pipeline has identified. If their name or branch changes in a later file, the row is updated in place.
- **Complaints** — one row per complaint that passed the checks. The numeric `id` on this table is only unique for that load. It is not a lasting complaint number from the source.

Saved queries on top of those tables (for charts):

| Query | What it answers |
|---|---|
| `gold.vw_monthly_trends` | How many complaints per month |
| `gold.mv_monthly_complaint_summary` | Same idea, stored so it does not recompute every time |
| `gold.vw_regional_stats` | Volume and resolution by region (`Unknown` left out) |
| `gold.vw_complaint_status` | Mix of statuses |
| `gold.vw_complaint_summary` | Each complaint plus a “closed in 1 day / 3 days / longer” bucket |
| `gold.vw_customer_overview` | How often each customer has complained |

Airflow (the job runner) has its own database. The reporting data lives in a **second** Postgres. That keeps Airflow’s internals away from the numbers you chart.

The reporting database is created the first time Postgres starts (`sql/init/`). Chart queries and indexes are applied by the pipeline after a successful load (`sql/`).

---

## Tools

**Python** does the data work. pandas reads each Excel tab, fingerprints it, cleans columns, and matches phones to the customer list. RapidFuzz scores region names when the spelling is off. python-ulid mints the customer IDs the pipeline stores. Intermediate copies are written as Parquet (a compact columnar file), not left as Excel.

**Apache Airflow** is the job runner. The workflow is `cus_pipeline`: copy changed tabs → clean → match IDs → load reporting tables → record success → refresh chart queries. It is scheduled monthly, retries a failed step twice, and will not start a second run while one is still going. If no tab changed, later steps are marked skipped instead of running empty. Progress and logs are in the Airflow UI.

**PostgreSQL** is two databases. One is only for Airflow (which jobs ran, which failed). The other is the reporting database: customers, complaints, the ID map, and the saved queries Metabase reads. Constraints (for example complaints must point at a known customer) live here, not in the spreadsheet.

**Docker Compose** starts all of that together — Airflow, both Postgres instances, and Metabase — with the project folders mounted in so the job can see `data/`, `scripts/`, and `sql/`.

**Metabase** is the charting UI. It connects to the reporting database as `metabase_reader`, a user that can read reporting tables and cannot write.

**Pytest** runs the cleaning and matching rules on small example tables. You can check those rules without booting Docker or Airflow.

---

## How to run it

You need Docker, Docker Compose, Git, and Python 3.11+ on your computer for two short generator scripts.

### 1. Create a local config file

```bash
cp .env.example .env
```

Fill in:

- `AIRFLOW_FERNET_KEY` — Airflow uses this to encrypt its own secrets. Generate one with:  
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Database name, user, and password for the **reporting** database
- A password for the Metabase read-only database user

Keep `.env` off git.

The pipeline looks for `data/source/CUSTOMER_SUPPORT-2025.xlsx` and skips the `Unresolved` tab. Those paths are set in the Airflow job, not by Compose, unless you add them to the Airflow service yourself.

### 2. Create the fake Excel and customer list

The spreadsheet is not stored in git.

```bash
pip install -r requirements.txt
python scripts/generate_synthetic_source.py
python scripts/generate_client_seed.py
```

Do this **before** the first `docker compose up`. The customer list is loaded only when the reporting database is first created. If you generate it after that, either start with a fresh database volume (this wipes reporting data) or insert the rows yourself.

### 3. Start everything

```bash
docker compose up -d --build
```

| Open this | Address |
|---|---|
| Airflow (run the job) | http://localhost:8080 — user `admin`, password `admin` (local only) |
| Metabase (charts) | http://localhost:3000 |
| Reporting database | `localhost:5433` |

### 4. Run the job

1. In Airflow, open `cus_pipeline`, unpause it, click Trigger.
2. Wait until `load_gold` and `analytics.refresh_matview` succeed.
3. You should see rows in `gold.customers` and `gold.complaints`.

Run it again with the same file: cleaning and loading should skip. Change a tab and run again: that tab is copied, the cleaned file and complaint table are rebuilt, and existing customer IDs should stay the same.

---

## Tests

```bash
pytest
```

These check region matching, phone formatting, date repairs, “do not load this complaint” rules, and “empty reporting tables must fail.” They do not start Docker or Airflow.

---

## Charts in Metabase

After a successful run, add a Postgres connection in Metabase:

| | Metabase talking to Docker | You talking from your laptop |
|---|---|---|
| Host | `postgres-warehouse` | `localhost` |
| Port | `5432` | `5433` |
| Database | the name you set in `.env` | same |
| User | `metabase_reader` | `metabase_reader` |

That user can only **read** the reporting tables and saved queries listed above. It cannot change data, and it cannot see the side table of rejected complaints. To inspect rejects, connect as the main reporting database user.

If a saved query exists but Metabase cannot read it, grant read access on those queries to `metabase_reader` (they are created by the job after the database first starts).

---

## Why it is built this way

**The spreadsheet is a full snapshot, not a list of new rows.** Each month you get the current book, not “only complaints since last time,” and a complaint has no lasting ID. So the pipeline fingerprints each tab and skips the copy step when the tab has not changed. If anything *did* change, it rebuilds the cleaned file from every raw copy it has, then reloads complaints as a whole. Updating complaints one-by-one would require a key the source does not give us. Customers are different: they have a stable ID, so they are inserted or updated in place.

**Success is recorded after the reporting tables load, not after the copy.** The fingerprint log is written last. If cleaning or loading fails, the tab is still treated as unprocessed. The next run copies it again instead of skipping a load that never finished.

**Customer IDs belong to this pipeline, not to Excel.** A generated ID is stored against “this CRM profile” or “this phone number.” Regenerating the fake spreadsheet, or getting a new export with the same people, should not mint a new ID for someone already seen.

**Bad rows are kept, and too many of them fail the job.** A complaint with no way to identify the customer, or with no log date, goes to `staging.rejected_complaints` so you can see what was left out. If more than 20% of complaints land there, the job errors. Publishing a report that quietly dropped a fifth of the file is worse than a red run.

**Python files on disk match the size of the data.** This sample is about a thousand rows. pandas, local Parquet, and Postgres are enough. A cluster or a data lake would not make the result more correct; it would only add moving parts.

Drawings of the layout are in [`docs/architecture-diagrams.drawio`](docs/architecture-diagrams.drawio).

---

## What’s in the repo

```text
Cus_Pipeline/
├── dags/cus_pipeline_dag.py      Airflow job (the step order)
├── scripts/                      cleaning, matching, loading, fake-data generators
├── sql/                          chart queries, run after each successful load
│   └── init/                     database setup, only on first start
├── tests/
├── data/                         Excel and intermediate files (generated, not in git)
├── docker-compose.yml            starts Airflow, databases, Metabase
├── .env.example
└── README.md
```

---

Educational / portfolio use.

**Samuel Lartey**
