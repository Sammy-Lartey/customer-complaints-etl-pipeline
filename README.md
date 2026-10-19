# Cus_Pipeline
[![tests](https://github.com/Sammy-Lartey/customer-complaints-etl-pipeline/actions/workflows/tests.yml/badge.svg)](https://github.com/Sammy-Lartey/customer-complaints-etl-pipeline/actions/workflows/tests.yml)

Customer support teams often export complaints from Excel. This project takes that kind of workbook, cleans it, and loads it into a database you can chart.

It is a rebuild of the first pipeline I worked on. The old version reprocessed everything on every run, and running it twice could duplicate rows. This version skips spreadsheet tabs that have not changed, keeps the same customer IDs from run to run, sets aside rows it cannot load, and stops if too much of the data looks broken.

You run it on your own machine with Docker. The point is the design, not a live company deployment.

The folders and database use the names `bronze`, `silver`, and `gold`, a common way to label data stages. In plain terms they mean **raw copy**, **cleaned file**, and **reporting tables**.

---

## The problem

The source is a monthly Excel file. Each tab is one month of complaints. Names, phone numbers, regions, and dates are inconsistent. There is no reliable complaint ID, and a customer can file the same kind of complaint more than once, so the pipeline cannot treat two similar rows as "the same complaint."

A fake customer list stands in for the bank's real customer system, which this pipeline does not own. About 60% of the phone numbers in the spreadsheet also appear in that list, the way a real extract only partly matches a customer database.

The Excel file in this project is generated and contains no real customer data.

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
Each tab gets a fingerprint (a SHA-256 hash of its contents). If a tab has the same fingerprint as the last successful run, it is not copied again. The `Unresolved` tab is ignored.

**2. Clean everything.**
If at least one tab changed, the pipeline merges all the raw copies, old and new, and cleans them into a single file: phone numbers, Ghana regions, dates, and how many days each complaint took to close. Unchanged tabs are not merged into the database row by row. The cleaned file is rebuilt from the full set of raw copies.

**3. Split customers from complaints, then identify people.**
Customer details and complaint details are separated. Each phone number is matched against the customer list. If it matches, the person's ID is tied to their profile in that list. If it does not match, the ID is tied to the phone number. The pipeline remembers every ID, so next month the same person keeps the same ID.

**4. Load the reporting tables.**
Customers are inserted, or updated if they already exist. Complaints are wiped and loaded fresh from this run's cleaned data. That is deliberate: the spreadsheet is a full picture of the current state, not a stream of new events with IDs. The customer update and the complaint reload happen in one database transaction, so a failed load is rolled back and the reporting tables keep their previous contents.

**5. Remember the fingerprints last.**
Only after the reporting tables load successfully does the pipeline record "this tab was processed." If any earlier step fails, nothing is recorded, and the next run tries those tabs again.

**6. Refresh the reports.**
The indexes, saved queries, and the stored monthly summary used for charts are created or refreshed.

If nothing in the spreadsheet changed, steps 2 to 6 are skipped.

### Checks and rejected rows

The run fails when:

- a name or region is still missing after cleaning
- more than 20% of complaints cannot be loaded
- two customers end up with the same ID
- the reporting tables come out empty

A big drop in row count between the raw copies and the cleaned file (more than 20%) is only logged as a warning.

Complaints that cannot be loaded are not deleted quietly. A complaint with no usable phone number, or with no log date, is written to `staging.rejected_complaints` along with the reason (`no phone number` or `missing logDate`). That table is rebuilt on every run. The rejected row is still in the spreadsheet, so if you fix it there, the tab changes and the next run picks it up.

### What the cleaning does

- **Regions.** Exact region names are kept as they are, and spelling mistakes are fixed. Anything unclear becomes `Unknown` instead of a guess. For example, `Upper` could be Upper East or Upper West, so it becomes `Unknown`. The old name `Brong Ahafo Region` is kept as its own value. That region was later split into the Bono, Bono East, and Ahafo regions, and there is no way to tell which one an old row belongs to.
- **Phone numbers.** Numbers become `+233…`, including numbers Excel stored as `540663527.0`.
- **Days to close.** If the log date and resolution date were swapped, they are put back in order and the days are recalculated. Negative or missing values are also recalculated when both dates are present. If a value cannot be worked out, it stays empty and the row is kept.

---

## What you can query at the end

Two main tables:

- **Customers.** One row per person the pipeline has identified. If their name or branch changes in a later file, the row is updated in place.
- **Complaints.** One row per complaint that passed the checks. The numeric `id` on this table is only unique within one load. It is not a lasting complaint number from the source.

Saved queries on top of those tables, for charts:

| Query | What it answers |
|---|---|
| `gold.vw_monthly_trends` | Complaints per month, with the most common complaint type and region |
| `gold.mv_monthly_complaint_summary` | A smaller monthly summary, stored so it does not recompute every time |
| `gold.vw_regional_stats` | Volume and resolution by region (`Unknown` is left out) |
| `gold.vw_complaint_status` | The mix of statuses |
| `gold.vw_complaint_summary` | Each complaint, plus how fast it closed: within 1 day, within 3 days, over 3 days, or unknown |
| `gold.vw_customer_overview` | How many complaints each customer has filed |

Airflow (the job runner) has its own database. The reporting data lives in a **second** Postgres. That keeps Airflow's internal records away from the numbers you chart.

The reporting database is set up the first time Postgres starts, using the files in `sql/init/`. The indexes, saved queries, and monthly summary are created by the pipeline after a successful load, using the files in `sql/`. That means the saved queries do not exist on a brand-new database until the first run finishes.

---

## Tools

**Python** does the data work. pandas reads each Excel tab, fingerprints it, cleans the columns, and matches phone numbers to the customer list. RapidFuzz compares region names when the spelling is off. python-ulid creates the customer IDs the pipeline stores. Intermediate copies are saved as Parquet, a compact file format for tables, instead of staying as Excel.

**Apache Airflow** runs the job. The workflow is called `cus_pipeline`: copy changed tabs, clean, match IDs, load reporting tables, record success, refresh the chart queries. It is scheduled monthly, retries a failed step twice, and will not start a second run while one is still going. If no tab changed, the later steps are marked as skipped instead of running on nothing. Progress and logs are in the Airflow UI.

**PostgreSQL** runs as two separate servers in Docker. One is only for Airflow (which jobs ran, which failed). The other is the reporting database: customers, complaints, the ID table, and the saved queries Metabase reads. Database rules live here too. For example, every complaint must point to a customer that exists.

**Docker Compose** starts everything together: Airflow, both Postgres servers, and Metabase. The project folders are shared into the containers so the job can see `data/`, `scripts/`, and `sql/`.

**Metabase** is the charting tool. It connects to the reporting database as `metabase_reader`, a user that can read the reporting tables and cannot change anything.

**Pytest** runs the cleaning and matching rules on small example tables, so you can check them without starting Docker or Airflow.

---

## How to run it

You need Docker, Docker Compose, Git, and Python 3.11 or newer on your computer. Python is only needed for two short data-generator scripts and for the tests.

### 1. Install the Python packages

```bash
pip install -r requirements.txt
```

### 2. Create a local config file

```bash
cp .env.example .env
```

Fill in:

- `AIRFLOW_FERNET_KEY`. Airflow uses it to encrypt its own secrets. Generate one with:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  If Python says `cryptography` is missing, run `pip install cryptography` and try again.
- The database name, user, and password for the **reporting** database.
- A password for the Metabase read-only database user.

Keep `.env` out of git.

The job reads `data/source/CUSTOMER_SUPPORT-2025.xlsx` and ignores the `Unresolved` tab. These defaults are set in `dags/cus_pipeline_dag.py`. Putting them in `.env` does not change them unless you also pass the values to the Airflow service in `docker-compose.yml`.

### 3. Create the fake Excel file and customer list

The spreadsheet is not stored in git. From the project folder, run:

```bash
python scripts/generate_synthetic_source.py
python scripts/generate_client_seed.py
```

Both scripts use fixed random seeds, so they produce the same data every time.

Do this **before** the first `docker compose up`. The customer list is loaded only when the reporting database is first created. If you generate it after that, either start from a fresh database (see "Start over" below, which wipes the reporting data) or insert the rows yourself.

### 4. Start everything

```bash
docker compose up -d --build
```

| Open this | Address |
|---|---|
| Airflow (run the job) | http://localhost:8080, user `admin`, password `admin` (local use only) |
| Metabase (charts) | http://localhost:3000 |
| Reporting database | `localhost:5433` |

### 5. Run the job

1. In Airflow, open `cus_pipeline`, unpause it, and click Trigger.
2. Wait until every task is green, including `load_gold` and `analytics.refresh_matview`.
3. Check that `gold.customers` and `gold.complaints` have rows.

Run it again with the same file: everything after the first step should be skipped. Change a tab and run again: that tab is copied again, the cleaned file and complaints table are rebuilt, and existing customers keep their IDs.

### Start over

To reset everything:

1. Run `docker compose down -v`. This deletes the database volumes (reporting data, Airflow history, and Metabase settings).
2. Delete the contents of `data/bronze/` and `data/silver/`, but keep the folders. They live on your computer, so `down -v` does not touch them.
3. Run `docker compose up -d`.

The reporting database's setup files run only when its volume is empty, which is why the reset needs the `-v`.

---

## Tests

```bash
pytest
```

The tests are in `tests/`: cleaning, ingestion, quality checks, and customer matching. They cover region matching, phone formatting, date repairs, and the quality checks, including the rule that fails the run when more than 20% of complaints are rejected and the one that fails it when the reporting tables come out empty. They do not start Docker or Airflow.

---

## Charts in Metabase

After a successful run, add a Postgres connection in Metabase:

| | Metabase, inside Docker | You, from your own computer |
|---|---|---|
| Host | `postgres-warehouse` | `localhost` |
| Port | `5432` | `5433` |
| Database | the name you set in `.env` | same |
| User | `metabase_reader` | `metabase_reader` |

That user can read everything in the `gold` schema: the tables, the saved queries, and the monthly summary. Access to anything the job creates later in `gold` is granted automatically. It cannot change data, and it cannot see the `staging` tables, including the rejected complaints. To look at the rejects, connect as the main reporting database user.

---

## Why it is built this way

**The spreadsheet is a full copy, not a list of new rows.** Each month you get the whole current book, not "only complaints since last time," and a complaint has no lasting ID. So the pipeline fingerprints each tab and skips the copy step when a tab has not changed. If anything did change, it rebuilds the cleaned file from every raw copy and reloads the complaints as a whole. Updating complaints one by one would need a key the source does not give us. Customers are different: they have a stable ID, so they are inserted or updated in place.

**Success is recorded after the reporting tables load, not after the copy.** The fingerprint log is written last. If cleaning or loading fails, the tab still counts as unprocessed, and the next run copies it again instead of skipping a load that never finished.

**Customer IDs belong to this pipeline, not to Excel.** A generated ID is stored against either a customer profile or a phone number. Regenerating the fake spreadsheet, or receiving a new export with the same people, does not create new IDs for people the pipeline has already seen. The IDs are kept in the reporting database, so they last as long as that database does. See "Known limits" for one case where a person can end up with two.

**Rows that cannot be loaded are set aside, and too many of them stop the job.** Losing a complaint quietly is the worst outcome, and failing the whole run over one bad row would block the monthly load. So bad rows go to `staging.rejected_complaints` with a reason and the rest continues. If more than 20% of complaints are rejected, something is wrong with the source, and the job fails. A report that quietly dropped a fifth of the file is worse than a red run.

**Unclear regions become `Unknown` instead of a guess.** An earlier version of the region matching scored any name whose words appeared inside another name as a perfect match, then picked whichever came first in the list. On the sample data it filed `Ahafo Region` under `Brong Ahafo Region` and `Western North Region` under `Western Region`. The current version keeps exact names, fixes small spelling mistakes, and refuses to guess when two regions are about equally close. Tests in `tests/test_cleaning.py` cover these cases.

**The tools are sized to the data.** The sample has about a thousand rows. pandas, local Parquet files, and Postgres are enough. A cluster or a data lake would not make the result more correct. It would only add moving parts.

Drawings of the layout are in [`docs/architecture-diagrams.drawio`](docs/architecture-diagrams.drawio).

---

## Known limits

- **A person can get two IDs.** Someone who first appears by phone number only, and later shows up in the customer list, is treated as a new person.
- **Blank or unclear regions are left out of regional reports.** They are kept as `Unknown`, but `gold.vw_regional_stats` does not show them. In the sample data this is about 14% of rows.
- **Duplicate rows are removed without a count.** Exact duplicates are dropped during cleaning. The log shows how many rows came out, but it only warns about a drop of more than 20%.
- **Each phone number must appear once in the customer list.** The pipeline assumes it does.
- **Built for local use.** There are default passwords and no alerts or monitoring.

---

## What's in the repo

```text
Cus_Pipeline/
├── dags/cus_pipeline_dag.py      Airflow job (the step order)
├── scripts/                      cleaning, matching, loading, fake-data generators
├── sql/                          chart queries, run after each successful load
│   └── init/                     database setup, only on first start
├── tests/
├── docs/                         architecture drawings
├── data/                         Excel and intermediate files (generated, not in git)
├── docker-compose.yml            starts Airflow, databases, Metabase
├── .env.example
└── README.md
```

---

Educational / portfolio use.

**Samuel Lartey**