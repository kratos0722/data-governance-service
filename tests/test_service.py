import pytest
from sqlalchemy import func, select

from governance.errors import DuplicateError, InvalidStateError, NotFoundError
from governance.models import AuditEntry
from governance.service import GovernanceService


def _svc(db):
    return GovernanceService(db)


def test_register_and_list_assets(db):
    svc = _svc(db)
    svc.register_asset("orders.fact", "snowflake", owner="data-team", classification="internal")
    assets = svc.list_assets()
    assert [a.name for a in assets] == ["orders.fact"]
    assert assets[0].is_complete


def test_register_duplicate_rejected(db):
    svc = _svc(db)
    svc.register_asset("dup", "snowflake")
    with pytest.raises(DuplicateError):
        svc.register_asset("dup", "snowflake")


def test_access_request_then_approve_creates_grant_and_audit(db):
    svc = _svc(db)
    asset = svc.register_asset("pii.customers", "postgres", owner="o", classification="restricted")
    req = svc.request_access(asset.id, "analyst@x", "quarterly report")
    assert req.status == "PENDING"

    decided = svc.decide_request(req.id, "APPROVED", "steward@x")
    assert decided.status == "APPROVED"

    grants = svc.list_grants("analyst@x")
    assert len(grants) == 1 and grants[0].active

    actions = set(db.scalars(select(AuditEntry.action)))
    assert {"ASSET_REGISTERED", "ACCESS_REQUESTED", "ACCESS_APPROVED", "GRANT_CREATED"} <= actions


def test_deny_does_not_create_grant(db):
    svc = _svc(db)
    asset = svc.register_asset("a", "snowflake")
    req = svc.request_access(asset.id, "user@x", "need it")
    svc.decide_request(req.id, "DENIED", "steward@x")
    assert svc.list_grants("user@x") == []


def test_cannot_decide_twice(db):
    svc = _svc(db)
    asset = svc.register_asset("a", "snowflake")
    req = svc.request_access(asset.id, "user@x", "need it")
    svc.decide_request(req.id, "APPROVED", "steward@x")
    with pytest.raises(InvalidStateError):
        svc.decide_request(req.id, "DENIED", "steward@x")


def test_revoke_grant(db):
    svc = _svc(db)
    asset = svc.register_asset("a", "snowflake")
    req = svc.request_access(asset.id, "user@x", "need it")
    svc.decide_request(req.id, "APPROVED", "steward@x")
    grant = svc.list_grants("user@x")[0]

    svc.revoke_grant(grant.id, "steward@x")
    assert not svc.list_grants("user@x")[0].active
    with pytest.raises(InvalidStateError):
        svc.revoke_grant(grant.id, "steward@x")


def test_request_access_unknown_asset(db):
    with pytest.raises(NotFoundError):
        _svc(db).request_access(999, "user@x", "need it")


def test_governance_report_flags_incomplete(db):
    svc = _svc(db)
    svc.register_asset("complete", "snowflake", owner="o", classification="internal")
    svc.register_asset("incomplete", "snowflake")  # no owner/classification
    incomplete, stale = svc.governance_report()
    assert [a.name for a in incomplete] == ["incomplete"]
    assert stale == []
