import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from governance import models  # noqa: F401
from governance.app import app
from governance.db import Base, get_db


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def _register(client, name="orders.fact"):
    return client.post("/api/assets", json={
        "name": name, "source_system": "snowflake",
        "owner": "data-team", "classification": "internal",
    })


def test_register_and_list(client):
    assert _register(client).status_code == 201
    listed = client.get("/api/assets").json()
    assert [a["name"] for a in listed] == ["orders.fact"]


def test_access_workflow_end_to_end(client):
    asset = _register(client).json()
    req = client.post("/api/access-requests", json={
        "asset_id": asset["id"], "requester": "analyst@x", "reason": "reporting",
    })
    assert req.status_code == 201

    decided = client.post(f"/api/access-requests/{req.json()['id']}/decide",
                           json={"decision": "APPROVED", "decided_by": "steward@x"})
    assert decided.status_code == 200

    grants = client.get("/api/grants", params={"principal": "analyst@x"}).json()
    assert len(grants) == 1 and grants[0]["active"] is True


def test_decide_unknown_request_404(client):
    resp = client.post("/api/access-requests/999/decide",
                       json={"decision": "APPROVED", "decided_by": "s"})
    assert resp.status_code == 404


def test_metadata_sync_endpoint_and_report(client):
    resp = client.post("/api/metadata/sync", json={"items": [
        {"name": "a", "source_system": "snowflake", "owner": "o", "classification": "internal"},
        {"name": "b", "source_system": "snowflake"},
    ]})
    assert resp.status_code == 200
    assert resp.json()["upserted"] == 2

    report = client.get("/api/governance/report").json()
    assert [a["name"] for a in report["incomplete"]] == ["b"]


def test_duplicate_asset_409(client):
    _register(client, "dup")
    assert _register(client, "dup").status_code == 409
