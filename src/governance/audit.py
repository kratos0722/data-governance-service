"""Append-only audit log."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditEntry


def record(db: Session, *, actor: str, action: str, target: str, detail: str | None = None) -> AuditEntry:
    """Append an audit entry in the caller's transaction.

    The entry is flushed (so it gets an id) but not committed here — it commits
    atomically with the action that produced it.
    """
    entry = AuditEntry(actor=actor, action=action, target=target, detail=detail)
    db.add(entry)
    db.flush()
    return entry
