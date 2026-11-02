"""Governance application service: assets, access workflow, grants, reporting."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .errors import DuplicateError, InvalidStateError, NotFoundError
from .models import AccessRequest, DataAsset, Grant


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GovernanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- assets ---------------------------------------------------------
    def register_asset(self, name: str, source_system: str,
                       owner: str | None = None, classification: str | None = None) -> DataAsset:
        if self.db.scalar(select(DataAsset).where(DataAsset.name == name)) is not None:
            raise DuplicateError(f"Asset '{name}' already exists")
        asset = DataAsset(name=name, source_system=source_system,
                          owner=owner, classification=classification)
        self.db.add(asset)
        self.db.flush()
        audit.record(self.db, actor="system", action="ASSET_REGISTERED", target=name)
        self.db.commit()
        return asset

    def list_assets(self) -> list[DataAsset]:
        return list(self.db.scalars(select(DataAsset).order_by(DataAsset.name)))

    def get_asset(self, asset_id: int) -> DataAsset:
        asset = self.db.get(DataAsset, asset_id)
        if asset is None:
            raise NotFoundError(f"No asset with id {asset_id}")
        return asset

    # --- access workflow ------------------------------------------------
    def request_access(self, asset_id: int, requester: str, reason: str) -> AccessRequest:
        self.get_asset(asset_id)  # existence check
        req = AccessRequest(asset_id=asset_id, requester=requester, reason=reason, status="PENDING")
        self.db.add(req)
        self.db.flush()
        audit.record(self.db, actor=requester, action="ACCESS_REQUESTED",
                     target=f"asset:{asset_id}", detail=reason)
        self.db.commit()
        return req

    def decide_request(self, request_id: int, decision: str, decided_by: str,
                       access_level: str = "READ") -> AccessRequest:
        req = self.db.get(AccessRequest, request_id)
        if req is None:
            raise NotFoundError(f"No access request with id {request_id}")
        if req.status != "PENDING":
            raise InvalidStateError(f"Request {request_id} is already {req.status}")

        req.status = decision
        req.decided_by = decided_by
        req.decided_at = _now()

        if decision == "APPROVED":
            grant = Grant(asset_id=req.asset_id, principal=req.requester, access_level=access_level)
            self.db.add(grant)
            self.db.flush()
            audit.record(self.db, actor=decided_by, action="ACCESS_APPROVED",
                         target=f"request:{request_id}")
            audit.record(self.db, actor=decided_by, action="GRANT_CREATED",
                         target=f"grant:{grant.id}", detail=f"{req.requester} -> asset:{req.asset_id}")
        else:
            audit.record(self.db, actor=decided_by, action="ACCESS_DENIED",
                         target=f"request:{request_id}")

        self.db.commit()
        return req

    # --- grants ---------------------------------------------------------
    def list_grants(self, principal: str) -> list[Grant]:
        return list(self.db.scalars(
            select(Grant).where(Grant.principal == principal).order_by(Grant.granted_at)))

    def revoke_grant(self, grant_id: int, actor: str) -> Grant:
        grant = self.db.get(Grant, grant_id)
        if grant is None:
            raise NotFoundError(f"No grant with id {grant_id}")
        if grant.revoked_at is not None:
            raise InvalidStateError(f"Grant {grant_id} is already revoked")
        grant.revoked_at = _now()
        audit.record(self.db, actor=actor, action="GRANT_REVOKED", target=f"grant:{grant_id}")
        self.db.commit()
        return grant

    # --- reporting ------------------------------------------------------
    def governance_report(self) -> tuple[list[DataAsset], list[DataAsset]]:
        assets = self.list_assets()
        incomplete = [a for a in assets if not a.is_complete]
        stale = [a for a in assets if a.stale]
        return incomplete, stale
