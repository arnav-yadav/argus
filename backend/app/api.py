from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import reporting, schemas, security, slo
from app.db import get_db
from app.metrics import HEARTBEATS
from app.models import Heartbeat, Service

router = APIRouter(prefix="/api")

DB = Annotated[Session, Depends(get_db)]
Window = Annotated[schemas.WindowName, Query()]


def _get_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    return service


def _service_out(service: Service, last: reporting.LastBeat | None, now: datetime) -> dict:
    return {
        **schemas.ServiceOut.model_validate(service).model_dump(),
        "status": reporting.status_of(service, last, now),
        "last_beat_at": last.received_at if last else None,
    }


@router.post("/services", response_model=schemas.ServiceCreated, status_code=201)
def register_service(payload: schemas.ServiceCreate, db: DB):
    token = security.new_token()
    service = Service(
        name=payload.name,
        slug=payload.slug or schemas.slugify(payload.name),
        heartbeat_interval_s=payload.heartbeat_interval_s,
        slo_target=payload.slo_target,
        ingest_token_hash=security.hash_token(token),
    )
    db.add(service)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already registered") from None
    db.refresh(service)
    return {**_service_out(service, None, datetime.now(UTC)), "ingest_token": token}


@router.get("/services", response_model=list[schemas.ServiceOut])
def list_services(db: DB, slug: str | None = None):
    query = select(Service).order_by(Service.name)
    if slug:
        query = query.where(Service.slug == slug)
    services = list(db.scalars(query))
    last = reporting.last_beats(db, [s.id for s in services])
    now = datetime.now(UTC)
    return [_service_out(s, last.get(s.id), now) for s in services]


@router.get("/services/{service_id}", response_model=schemas.ServiceOut)
def get_service(service_id: int, db: DB):
    service = _get_service(db, service_id)
    last = reporting.last_beats(db, [service.id]).get(service.id)
    return _service_out(service, last, datetime.now(UTC))


@router.put("/services/{service_id}", response_model=schemas.ServiceOut)
def update_service(service_id: int, payload: schemas.ServiceUpdate, db: DB):
    service = _get_service(db, service_id)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    last = reporting.last_beats(db, [service.id]).get(service.id)
    return _service_out(service, last, datetime.now(UTC))


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: int, db: DB):
    service = _get_service(db, service_id)
    db.delete(service)
    db.commit()
    return Response(status_code=204)


@router.post("/services/{service_id}/rotate-token", response_model=schemas.TokenOut)
def rotate_token(service_id: int, db: DB):
    service = _get_service(db, service_id)
    token = security.new_token()
    service.ingest_token_hash = security.hash_token(token)
    db.commit()
    return {"ingest_token": token}


@router.post(
    "/services/{service_id}/heartbeat", response_model=schemas.HeartbeatOut, status_code=202
)
def ingest_heartbeat(
    service_id: int,
    payload: schemas.HeartbeatIn,
    db: DB,
    x_argus_token: Annotated[str | None, Header()] = None,
):
    service = _get_service(db, service_id)
    if not security.verify_token(x_argus_token, service.ingest_token_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid X-Argus-Token")
    beat = Heartbeat(service_id=service.id, status=payload.status, latency_ms=payload.latency_ms)
    db.add(beat)
    db.commit()
    db.refresh(beat)
    HEARTBEATS.labels(service=service.slug, status=payload.status).inc()
    return beat


@router.get("/services/{service_id}/uptime", response_model=schemas.UptimeOut)
def service_uptime(service_id: int, db: DB, window: Window = "24h"):
    service = _get_service(db, service_id)
    now = datetime.now(UTC)
    last = reporting.last_beats(db, [service.id]).get(service.id)
    report = reporting.build_report(db, service, window, now, last, with_sparkline=True)
    budget = report.budget
    return {
        "service_id": service.id,
        "slug": service.slug,
        "window": window,
        "status": report.status,
        "slo_target": service.slo_target,
        "uptime": report.uptime,
        "burn_rate": report.burn_rate,
        "allowed_downtime_s": (1 - service.slo_target / 100) * slo.WINDOWS[window].total_seconds(),
        "budget_consumed_ratio": budget.consumed_ratio if budget else None,
        "budget_remaining_ratio": budget.remaining_ratio if budget else None,
        "sparkline": report.sparkline,
    }


@router.get("/slo/budget", response_model=schemas.FleetBudgetOut)
def fleet_budget(db: DB, window: Window = "24h"):
    now = datetime.now(UTC)
    services = list(db.scalars(select(Service).order_by(Service.name)))
    last = reporting.last_beats(db)
    items = []
    for service in services:
        report = reporting.build_report(db, service, window, now, last.get(service.id))
        items.append(
            {
                "service_id": service.id,
                "slug": service.slug,
                "name": service.name,
                "status": report.status,
                "slo_target": service.slo_target,
                "uptime": report.uptime,
                "burn_rate": report.burn_rate,
                "budget_remaining_ratio": report.budget.remaining_ratio if report.budget else None,
            }
        )

    judged = [i for i in items if i["uptime"] is not None]
    meeting = sum(1 for i in judged if i["uptime"] * 100 >= i["slo_target"])
    burns = [i["burn_rate"] for i in judged]
    return {
        "window": window,
        "services": len(items),
        "meeting_slo": meeting,
        "breaching_slo": len(judged) - meeting,
        "no_data": len(items) - len(judged),
        "worst_burn_rate": max(burns) if burns else None,
        "items": items,
    }
