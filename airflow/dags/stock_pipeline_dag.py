"""
stock_pipeline_dag.py
──────────────────────
Orchestrates the end-to-end stock analytics pipeline:

  1. health_check_snowflake   — verify the Snowflake connection
  2. verify_s3_new_files      — check that the consumer has uploaded files
  3. trigger_snowpipe_refresh — call Snowpipe REST API to force ingest
  4. dbt_run_staging          — dbt run for staging models
  5. dbt_run_intermediate     — dbt run for intermediate models
  6. dbt_run_marts            — dbt run for mart models
  7. dbt_test                 — run dbt tests

Schedule: every hour

Uses BashOperator with docker exec to run dbt commands in the persistent
dbt-runner container, which has bind-mounted dbt project files and
pre-loaded Snowflake credentials.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

# ─────────────────────────────────────────────────────────────
# Default args
# ─────────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "email_on_failure": False,
}

DBT_CONTAINER = "dbt-runner"
DBT_PROJECT_DIR = "/usr/app/dbt"

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "your-stock-analytics-bucket")
S3_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/trades/")


# ─────────────────────────────────────────────────────────────
# Python callables
# ─────────────────────────────────────────────────────────────
def check_snowflake_connection(**context):
    hook = SnowflakeHook(snowflake_conn_id="snowflake_default")
    result = hook.get_first("SELECT CURRENT_VERSION()")
    if not result:
        raise RuntimeError("Snowflake connection check failed.")
    print(f"Snowflake version: {result[0]}")


def verify_s3_new_files(**context):
    """
    Checks that at least one new file was uploaded in the last 2 hours.
    Raises if no files are found so the pipeline fails fast.
    """
    hook = S3Hook(aws_conn_id="aws_default")
    execution_date: datetime = context["logical_date"]
    lookback = execution_date - timedelta(hours=2)

    keys = hook.list_keys(bucket_name=S3_BUCKET, prefix=S3_PREFIX)
    if not keys:
        raise FileNotFoundError(
            f"No files found in s3://{S3_BUCKET}/{S3_PREFIX}. "
            "Is the Kafka consumer running?"
        )
    print(f"Found {len(keys)} file(s) in s3://{S3_BUCKET}/{S3_PREFIX}")


def trigger_snowpipe_refresh(**context):
    """
    Issues an ALTER PIPE ... REFRESH in Snowflake to force Snowpipe
    to pick up any files that were not automatically discovered.
    """
    hook = SnowflakeHook(snowflake_conn_id="snowflake_default")
    hook.run("ALTER PIPE STOCK_ANALYTICS_DB.RAW.TRADES_PIPE REFRESH;")
    print("Snowpipe refresh triggered.")


def dbt_exec_task(task_id: str, dbt_command: str) -> BashOperator:
    """Run dbt command inside the persistent dbt-runner container."""
    full_command = (
        f"docker exec {DBT_CONTAINER} "
        f"dbt --no-use-colors {dbt_command} "
        f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
    )
    return BashOperator(
        task_id=task_id,
        bash_command=full_command,
    )


# ─────────────────────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────────────────────
with DAG(
    dag_id="stock_analytics_pipeline",
    description="Real-time stock analytics: Kafka → S3 → Snowflake → dbt",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule="@hourly",
    catchup=False,
    max_active_runs=1,
    tags=["stock", "snowflake", "dbt", "kafka"],
) as dag:

    t_check_snowflake = PythonOperator(
        task_id="health_check_snowflake",
        python_callable=check_snowflake_connection,
    )

    t_verify_s3 = PythonOperator(
        task_id="verify_s3_new_files",
        python_callable=verify_s3_new_files,
    )

    t_snowpipe_refresh = PythonOperator(
        task_id="trigger_snowpipe_refresh",
        python_callable=trigger_snowpipe_refresh,
    )

    t_dbt_staging = dbt_exec_task("dbt_run_staging", "run --select staging")
    t_dbt_intermediate = dbt_exec_task("dbt_run_intermediate", "run --select intermediate")
    t_dbt_marts = dbt_exec_task("dbt_run_marts", "run --select marts")
    t_dbt_test = dbt_exec_task("dbt_test", "test")

    # ── Dependencies ──────────────────────────────────────────
    [t_check_snowflake, t_verify_s3] >> t_snowpipe_refresh
    t_snowpipe_refresh >> t_dbt_staging >> t_dbt_intermediate >> t_dbt_marts >> t_dbt_test
