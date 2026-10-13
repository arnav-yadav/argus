import os

# Point the app at a throwaway in-memory SQLite database before it is imported, so no
# test can ever touch the real Postgres database.
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def service(client):
    """A registered service. The plaintext token is only available from this response."""
    response = client.post(
        "/api/services",
        json={"name": "Payments API", "heartbeat_interval_s": 10, "slo_target": 99.5},
    )
    assert response.status_code == 201
    return response.json()


def beat(client, service, status="ok", token=None, latency_ms=42):
    return client.post(
        f"/api/services/{service['id']}/heartbeat",
        json={"status": status, "latency_ms": latency_ms},
        headers={"X-Argus-Token": token or service["ingest_token"]},
    )
