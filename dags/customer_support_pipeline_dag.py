import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.exceptions import AirflowSkipException
from airflow.utils.task_group import TaskGroup

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
from ingestion import land_changed_sheets


SOURCE_EXCEL_PATH = os.environ.get(
    "SOURCE_EXCEL_PATH", "/opt/airflow/data/source/CUSTOMER_SUPPORT-2025.xlsx"
)
EXCLUDE_SHEETS = os.environ.get("EXCLUDE_SHEETS", "Unresolved").split(",")
BRONZE_DIR = "/opt/airflow/data/bronze"
SILVER_PATH = "/opt/airflow/data/silver/customer_support_silver.parquet"


def _land_changed_sheets_task(**context):
    hook = PostgresHook(postgres_conn_id="postgres_warehouse")
    engine = hook.get_sqlalchemy_engine()

    changed_paths = land_changed_sheets(
        excel_path=SOURCE_EXCEL_PATH,
        bronze_dir=BRONZE_DIR,
        exclude_sheets=EXCLUDE_SHEETS,
        engine=engine,
    )

    if not changed_paths:
        context["ti"].log.info("No sheets changed since last run -- nothing to land.")
    else:
        context["ti"].log.info(f"Landed {len(changed_paths)} changed sheet(s): {changed_paths}")

    return changed_paths


def _clean_bronze_to_silver_task(**context):
    changed_paths = context["ti"].xcom_pull(task_ids="land_changed_sheets_to_bronze")

    if not changed_paths:
        raise AirflowSkipException("No new bronze data -- skipping silver transform.")

    import pandas as pd
    from cleaning import run_silver_transform, load_and_merge_bronze
    from quality_checks import check_silver_quality

    bronze_row_count = len(load_and_merge_bronze(BRONZE_DIR))
    row_count = run_silver_transform(bronze_dir=BRONZE_DIR, silver_path=SILVER_PATH)

    silver_df = pd.read_parquet(SILVER_PATH)
    check_silver_quality(silver_df, bronze_row_count, context["ti"].log)

    context["ti"].log.info(f"Silver transform complete: {row_count} rows")
    return row_count


def _resolve_ids_task(**context):
    import pandas as pd
    from resolution import run_resolution
    from quality_checks import check_resolution_quality

    hook = PostgresHook(postgres_conn_id="postgres_warehouse")
    engine = hook.get_sqlalchemy_engine()

    customer_count, complaint_count = run_resolution(silver_path=SILVER_PATH, engine=engine)

    customers_df = pd.read_sql('SELECT * FROM staging.customers', engine)
    complaints_df = pd.read_sql('SELECT * FROM staging.complaints', engine)
    check_resolution_quality(customers_df, complaints_df, context["ti"].log)

    context["ti"].log.info(f"Resolved {customer_count} customers, {complaint_count} complaints")
    return {"customers": customer_count, "complaints": complaint_count}


def _load_gold_task(**context):
    from load_gold import run_gold_load
    from quality_checks import check_gold_quality

    hook = PostgresHook(postgres_conn_id="postgres_warehouse")
    engine = hook.get_sqlalchemy_engine()

    customer_count, complaint_count = run_gold_load(engine)
    check_gold_quality(customer_count, complaint_count, context["ti"].log)

    context["ti"].log.info(f"Gold load complete: {customer_count} customers upserted, {complaint_count} complaints loaded")
    return {"customers": customer_count, "complaints": complaint_count}


def _run_sql_file_task(sql_filename, **context):
    from sqlalchemy import text

    hook = PostgresHook(postgres_conn_id="postgres_warehouse")
    engine = hook.get_sqlalchemy_engine()

    sql_path = f"/opt/airflow/sql/{sql_filename}"
    with open(sql_path) as f:
        sql = f.read()

    with engine.begin() as conn:
        conn.execute(text(sql))

    context["ti"].log.info(f"Executed {sql_filename}")


def _refresh_materialized_view_task(**context):
    from sqlalchemy import text

    hook = PostgresHook(postgres_conn_id="postgres_warehouse")
    engine = hook.get_sqlalchemy_engine()

    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW gold.mv_monthly_complaint_summary"))

    context["ti"].log.info("Materialized view refreshed")


default_args = {
    "owner": "sammy",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="customer_support_pipeline",
    description="Customer support complaints ETL -- bronze/silver/gold pipeline",
    default_args=default_args,
    start_date=datetime(2025, 1, 1),
    schedule="@monthly",
    catchup=False,
    max_active_runs=1,
    tags=["customer-support", "medallion", "portfolio"],
) as dag:

    land_changed_sheets_to_bronze = PythonOperator(
        task_id="land_changed_sheets_to_bronze",
        python_callable=_land_changed_sheets_task,
    )

    clean_bronze_to_silver = PythonOperator(
        task_id="clean_bronze_to_silver",
        python_callable=_clean_bronze_to_silver_task,
    )

    resolve_ids_to_staging = PythonOperator(
        task_id="resolve_ids_to_staging",
        python_callable=_resolve_ids_task,
    )

    load_gold = PythonOperator(
        task_id="load_gold",
        python_callable=_load_gold_task,
    )

    with TaskGroup(group_id="analytics") as analytics:
        create_indexes = PythonOperator(
            task_id="create_indexes",
            python_callable=_run_sql_file_task,
            op_kwargs={"sql_filename": "03_indexes.sql"},
        )
        create_views = PythonOperator(
            task_id="create_views",
            python_callable=_run_sql_file_task,
            op_kwargs={"sql_filename": "04_views.sql"},
        )
        refresh_matview = PythonOperator(
            task_id="refresh_matview",
            python_callable=_refresh_materialized_view_task,
        )
        

    land_changed_sheets_to_bronze >> clean_bronze_to_silver >> resolve_ids_to_staging >> load_gold >> analytics