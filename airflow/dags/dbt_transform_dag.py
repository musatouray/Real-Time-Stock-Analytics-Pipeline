"""
dbt_transform_dag.py
──────────────────────
Standalone DAG for running dbt transformations on-demand or on a
separate schedule (e.g., every 15 minutes for near-real-time marts).

Useful for decoupling the ingestion schedule from the transform schedule.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
}

DBT_DIR = "/usr/app/dbt"


def _dbt(selector: str, command: str = "run") -> str:
    return (
        f"dbt --no-use-colors {command} "
        f"--project-dir {DBT_DIR} "
        f"--profiles-dir {DBT_DIR} "
        f"--select {selector}"
    )


with DAG(
    dag_id="dbt_transforms",
    description="Run dbt transformations independently of ingestion",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule="*/15 * * * *",   # every 15 minutes
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "snowflake"],
) as dag:

    compile_models = BashOperator(
        task_id="dbt_compile",
        bash_command=f"dbt compile --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
    )

    run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=_dbt("staging"),
    )

    run_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=_dbt("intermediate"),
    )

    run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=_dbt("marts"),
    )

    run_tests = BashOperator(
        task_id="dbt_test",
        bash_command=f"dbt test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
    )

    compile_models >> run_staging >> run_intermediate >> run_marts >> run_tests
