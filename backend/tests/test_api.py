from datetime import UTC, datetime, timedelta

import pytest

from app.models import Heartbeat, Service
from tests.conftest import beat


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_checks_the_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_register_service_returns_token_once(client, service):
    assert service["slug"] == "payments-api"
    assert service["ingest_token"].startswith("argus_")
    assert service["status"] == "unknown"
    listed = client.get(f"/api/services/{service['id']}").json()
    assert "ingest_token" not in listed


def test_duplicate_slug_is_rejected(client, service):
    response = client.post("/api/services", json={"name": "Payments API"})
    assert response.status_code == 409


def test_invalid_service_payloads_are_rejected(client):
    assert client.post("/api/services", json={"name": "x"}).status_code == 422
    assert client.post("/api/services", json={"name": "Api", "slo_target": 100}).status_code == 422
    bad_slug = client.post("/api/services", json={"name": "Api", "slug": "Not A Slug"})
    assert bad_slug.status_code == 422


def test_list_and_filter_services(client, service):
    client.post("/api/services", json={"name": "Search", "slo_target": 99.9})
    names = [s["name"] for s in client.get("/api/services").json()]
    assert names == ["Payments API", "Search"]
    only = client.get("/api/services", params={"slug": "search"}).json()
    assert [s["slug"] for s in only] == ["search"]


def test_update_service(client, service):
    response = client.put(f"/api/services/{service['id']}", json={"slo_target": 99.9})
    assert response.status_code == 200
    assert response.json()["slo_target"] == 99.9
    assert response.json()["heartbeat_interval_s"] == 10


def test_delete_service_removes_its_heartbeats(client, service, db):
    beat(client, service)
    assert client.delete(f"/api/services/{service['id']}").status_code == 204
    assert client.get(f"/api/services/{service['id']}").status_code == 404
    assert db.query(Heartbeat).count() == 0


def test_unknown_service_is_404(client):
    assert client.get("/api/services/999").status_code == 404
    assert client.get("/api/services/999/uptime").status_code == 404


def test_heartbeat_requires_the_service_token(client, service):
    missing = client.post(f"/api/services/{service['id']}/heartbeat", json={})
    assert missing.status_code == 401
    assert beat(client, service, token="argus_forged").status_code == 401

    accepted = beat(client, service)
    assert accepted.status_code == 202
    assert accepted.json()["status"] == "ok"
    assert client.get(f"/api/services/{service['id']}").json()["status"] == "up"


def test_rotating_the_token_revokes_the_old_one(client, service):
    rotated = client.post(f"/api/services/{service['id']}/rotate-token").json()["ingest_token"]
    assert beat(client, service).status_code == 401
    assert beat(client, service, token=rotated).status_code == 202


def test_failing_heartbeat_marks_service_down(client, service):
    beat(client, service, status="fail")
    assert client.get(f"/api/services/{service['id']}").json()["status"] == "down"


def test_uptime_for_a_fresh_healthy_service(client, service):
    beat(client, service)
    body = client.get(f"/api/services/{service['id']}/uptime", params={"window": "1h"}).json()
    assert body["uptime"] == 1.0
    assert body["burn_rate"] == 0
    assert body["allowed_downtime_s"] == pytest.approx(18)  # 0.5% of an hour
    assert len(body["sparkline"]) == 30


def test_uptime_rejects_unknown_windows(client, service):
    response = client.get(f"/api/services/{service['id']}/uptime", params={"window": "3y"})
    assert response.status_code == 422


def test_service_that_went_silent_is_down_and_burning_budget(client, service, db):
    """Simulate an hour of history: healthy for 30 minutes, then nothing."""
    now = datetime.now(UTC)
    row = db.get(Service, service["id"])
    row.created_at = now - timedelta(hours=1)
    db.add_all(
        Heartbeat(service_id=row.id, status="ok", received_at=now - timedelta(minutes=60 - m / 6))
        for m in range(180)  # every 10s for the first 30 minutes
    )
    db.commit()

    body = client.get(f"/api/services/{service['id']}/uptime", params={"window": "1h"}).json()
    assert body["status"] == "down"
    assert 0.45 < body["uptime"] < 0.55
    assert body["burn_rate"] > 90
    assert body["budget_remaining_ratio"] < 0


def test_fleet_budget_summarises_every_service(client, service):
    quiet = client.post("/api/services", json={"name": "Batch Jobs"}).json()
    beat(client, service)
    fleet = client.get("/api/slo/budget").json()
    assert fleet["services"] == 2
    assert fleet["meeting_slo"] == 1
    assert fleet["no_data"] == 1
    assert {i["slug"] for i in fleet["items"]} == {"payments-api", quiet["slug"]}


def test_metrics_expose_slo_series(client, service):
    beat(client, service)
    text = client.get("/metrics").text
    assert 'argus_service_up{service="payments-api"} 1.0' in text
    assert 'argus_heartbeats_total{service="payments-api",status="ok"}' in text
    assert 'argus_uptime_ratio{service="payments-api",window="1h"} 1.0' in text
    assert 'argus_burn_rate{service="payments-api",window="5m"} 0.0' in text
    assert 'argus_error_budget_remaining_ratio{service="payments-api"} 1.0' in text
    assert "http_requests_total" in text
