"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_system: str = Field(min_length=1, max_length=128)
    owner: str | None = None
    classification: str | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_system: str
    owner: str | None
    classification: str | None
    stale: bool
    is_complete: bool
    last_synced_at: datetime | None


class AccessRequestCreate(BaseModel):
    asset_id: int
    requester: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1)


class AccessRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    requester: str
    reason: str
    status: str
    decided_by: str | None
    created_at: datetime
    decided_at: datetime | None


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVED|DENIED)$")
    decided_by: str = Field(min_length=1, max_length=255)
    access_level: str = Field(default="READ", max_length=32)


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    principal: str
    access_level: str
    granted_at: datetime
    revoked_at: datetime | None
    active: bool


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ts: datetime
    actor: str
    action: str
    target: str
    detail: str | None


class GovernanceReport(BaseModel):
    incomplete: list[AssetOut]
    stale: list[AssetOut]


class SyncResult(BaseModel):
    upserted: int
    marked_stale: int


class MetadataItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    source_system: str = Field(min_length=1, max_length=128)
    owner: str | None = None
    classification: str | None = None


class SyncRequest(BaseModel):
    items: list[MetadataItem] = Field(default_factory=list)
