"""FastAPI application for the governance service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from . import schemas
from .db import create_all, get_db
from .errors import DuplicateError, InvalidStateError, NotFoundError
from .metadata_sync import AssetMetadata, StaticMetadataSource, sync_metadata
from .service import GovernanceService


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    yield


app = FastAPI(title="data-governance-service", version="0.1.0", lifespan=lifespan)


def get_service(db: Session = Depends(get_db)) -> GovernanceService:
    return GovernanceService(db)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.post("/api/assets", response_model=schemas.AssetOut, status_code=201)
def register_asset(body: schemas.AssetCreate, svc: GovernanceService = Depends(get_service)):
    try:
        return svc.register_asset(body.name, body.source_system, body.owner, body.classification)
    except DuplicateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/assets", response_model=list[schemas.AssetOut])
def list_assets(svc: GovernanceService = Depends(get_service)):
    return svc.list_assets()


@app.post("/api/access-requests", response_model=schemas.AccessRequestOut, status_code=201)
def request_access(body: schemas.AccessRequestCreate, svc: GovernanceService = Depends(get_service)):
    try:
        return svc.request_access(body.asset_id, body.requester, body.reason)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/access-requests/{request_id}/decide", response_model=schemas.AccessRequestOut)
def decide(request_id: int, body: schemas.DecisionRequest, svc: GovernanceService = Depends(get_service)):
    try:
        return svc.decide_request(request_id, body.decision, body.decided_by, body.access_level)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/grants", response_model=list[schemas.GrantOut])
def list_grants(principal: str = Query(...), svc: GovernanceService = Depends(get_service)):
    return svc.list_grants(principal)


@app.post("/api/grants/{grant_id}/revoke", response_model=schemas.GrantOut)
def revoke(grant_id: int, actor: str = Query(...), svc: GovernanceService = Depends(get_service)):
    try:
        return svc.revoke_grant(grant_id, actor)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/governance/report", response_model=schemas.GovernanceReport)
def report(svc: GovernanceService = Depends(get_service)):
    incomplete, stale = svc.governance_report()
    return schemas.GovernanceReport(incomplete=incomplete, stale=stale)


@app.post("/api/metadata/sync", response_model=schemas.SyncResult)
def metadata_sync(body: schemas.SyncRequest, db: Session = Depends(get_db)):
    source = StaticMetadataSource([
        AssetMetadata(i.name, i.source_system, i.owner, i.classification) for i in body.items
    ])
    summary = sync_metadata(db, source)
    return schemas.SyncResult(upserted=summary.upserted, marked_stale=summary.marked_stale)
