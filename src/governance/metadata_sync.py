"""Metadata sync: keep the asset catalog current from source systems.

In production this runs on an Airflow schedule against Snowflake and operational
databases (see ``dags/metadata_sync_dag.py``). The source is a port, so tests
drive it with a static fake and the flagging logic is verified without any
external system.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .models import DataAsset


@dataclass(frozen=True)
class AssetMetadata:
    name: str
    source_system: str
    owner: str | None = None
    classification: str | None = None


class MetadataSource(Protocol):
    def fetch(self) -> list[AssetMetadata]:
        ...


class StaticMetadataSource:
    """A fixed set of metadata (used for tests and the demo)."""

    def __init__(self, items: list[AssetMetadata]) -> None:
        self._items = list(items)

    def fetch(self) -> list[AssetMetadata]:
        return list(self._items)


class SnowflakeMetadataSource:
    """Reads asset metadata from Snowflake. Imported lazily."""

    def __init__(self, query: str, **connect_kwargs: object) -> None:
        self._query = query
        self._connect_kwargs = connect_kwargs

    def fetch(self) -> list[AssetMetadata]:  # pragma: no cover - needs a live warehouse
        import snowflake.connector  # lazy import

        conn = snowflake.connector.connect(**self._connect_kwargs)
        try:
            cur = conn.cursor()
            cur.execute(self._query)
            return [
                AssetMetadata(name=row[0], source_system=row[1], owner=row[2], classification=row[3])
                for row in cur.fetchall()
            ]
        finally:
            conn.close()


@dataclass
class SyncSummary:
    upserted: int
    marked_stale: int


def sync_metadata(db: Session, source: MetadataSource) -> SyncSummary:
    """Upsert assets from ``source`` and flag ones no longer present as stale.

    Runs within the caller's session so it can share a transaction (API request)
    or be given a dedicated session (scheduled job).
    """
    now = datetime.now(timezone.utc)
    incoming = {m.name: m for m in source.fetch()}

    existing = {a.name: a for a in db.scalars(select(DataAsset))}
    upserted = 0
    for name, meta in incoming.items():
        asset = existing.get(name)
        if asset is None:
            asset = DataAsset(name=name, source_system=meta.source_system)
            db.add(asset)
        asset.source_system = meta.source_system
        if meta.owner is not None:
            asset.owner = meta.owner
        if meta.classification is not None:
            asset.classification = meta.classification
        asset.stale = False
        asset.last_synced_at = now
        upserted += 1

    marked_stale = 0
    for name, asset in existing.items():
        if name not in incoming and not asset.stale:
            asset.stale = True
            marked_stale += 1

    audit.record(db, actor="metadata-sync", action="METADATA_SYNCED",
                 target="catalog", detail=f"upserted={upserted} stale={marked_stale}")
    db.commit()
    return SyncSummary(upserted=upserted, marked_stale=marked_stale)


class MetadataSyncJob:
    """Scheduled wrapper around :func:`sync_metadata` with its own session."""

    def __init__(self, session_factory: Callable[[], Session], source: MetadataSource) -> None:
        self._session_factory = session_factory
        self._source = source

    def run(self) -> SyncSummary:
        db = self._session_factory()
        try:
            return sync_metadata(db, self._source)
        finally:
            db.close()
