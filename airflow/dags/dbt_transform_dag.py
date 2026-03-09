"""
dbt_transform_dag.py
──────────────────────
Standalone DAG for running dbt transformations on-demand or on a
separate schedule (e.g., every 15 minutes for near-real-time marts).

Useful for decoupling the ingestion schedule from the transform schedule.

Uses BashOperator with docker exec to run dbt commands in the persistent
dbt-runner container, which has bind-mounted dbt project files and
pre-loaded Snowflake credentials.
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

DBT_CONTAINER = "dbt-runner"
DBT_PROJECT_DIR = "/usr/app/dbt"


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

    compile_models = dbt_exec_task("dbt_compile", "compile")
    run_staging = dbt_exec_task("dbt_run_staging", "run --select staging")
    run_intermediate = dbt_exec_task("dbt_run_intermediate", "run --select intermediate")
    run_marts = dbt_exec_task("dbt_run_marts", "run --select marts")
    run_tests = dbt_exec_task("dbt_test", "test")

    compile_models >> run_staging >> run_intermediate >> run_marts >> run_tests
