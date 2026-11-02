"""Airflow DAG that refreshes the asset catalog from Snowflake on a schedule.

This file is only loaded by an Airflow scheduler (it is not imported by the test
suite). It wraps :class:`MetadataSyncJob`, which carries the actual sync logic.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from governance.db import SessionLocal
from governance.metadata_sync import MetadataSyncJob, SnowflakeMetadataSource


def _sync() -> None:
    source = SnowflakeMetadataSource(
        query=os.environ["SNOWFLAKE_ASSET_QUERY"],
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE"),
    )
    summary = MetadataSyncJob(SessionLocal, source).run()
    print(f"metadata sync: upserted={summary.upserted} marked_stale={summary.marked_stale}")


with DAG(
    dag_id="governance_metadata_sync",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["governance"],
) as dag:
    PythonOperator(task_id="sync_catalog_metadata", python_callable=_sync)
