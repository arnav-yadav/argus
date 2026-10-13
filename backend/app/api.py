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

router = APIRouter(prefix="/api", tags=["services"])

DB = Annotated[Session, Depends(get_db)]
Window = Annotated[schemas.WindowName, Query()]


def _get_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    return service


def _last_beat(db: Session, service: Service) -> reporting.LastBeat | None:
    return reporting.last_beats(db, [service.id]).get(service.id)


def _service_out(
    service: Service, last: reporting.LastBeat | None, now: datetime
) -> schemas.ServiceOut:
    return schemas.ServiceOut.model_validate(service).model_copy(
        update={
            "status": reporting.status_of(service, last, now),
            "last_beat_at": last.received_at if last else None,
        }
    )


@router.post("/services", status_code=201)
def register_service(payload: schemas.ServiceCreate, db: DB) -> schemas.ServiceCreated:
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
    created = _service_out(service, None, datetime.now(UTC))
    return schemas.ServiceCreated(**created.model_dump(), ingest_token=token)


@router.get("/services")
def list_services(db: DB, slug: str | None = None) -> list[schemas.ServiceOut]:
    query = select(Service).order_by(Service.name)
    if slug:
        query = query.where(Service.slug == slug)
    services = list(db.scalars(query))
    last = reporting.last_beats(db, [s.id for s in services])
    now = datetime.now(UTC)
    return [_service_out(s, last.get(s.id), now) for s in services]


@router.get("/services/{service_id}")
def get_service(service_id: int, db: DB) -> schemas.ServiceOut:
    service = _get_service(db, service_id)
    return _service_out(service, _last_beat(db, service), datetime.now(UTC))


@router.put("/services/{service_id}")
def update_service(service_id: int, payload: schemas.ServiceUpdate, db: DB) -> schemas.ServiceOut:
    service = _get_service(db, service_id)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return _service_out(service, _last_beat(db, service), datetime.now(UTC))


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: int, db: DB):
    service = _get_service(db, service_id)
    db.delete(service)
    db.commit()
    return Response(status_code=204)


@router.post("/services/{service_id}/rotate-token")
def rotate_token(service_id: int, db: DB) -> schemas.TokenOut:
    service = _get_service(db, service_id)
    token = security.new_token()
    service.ingest_token_hash = security.hash_token(token)
    db.commit()
    return schemas.TokenOut(ingest_token=token)


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


@router.get("/services/{service_id}/uptime")
def service_uptime(service_id: int, db: DB, window: Window = "24h") -> schemas.UptimeOut:
    service = _get_service(db, service_id)
    now = datetime.now(UTC)
    report = reporting.build_report(
        db, service, window, now, _last_beat(db, service), with_sparkline=True
    )
    return schemas.UptimeOut(
        service_id=service.id,
        slug=service.slug,
        window=window,
        status=report.status,
        slo_target=service.slo_target,
        uptime=report.uptime,
        burn_rate=report.burn_rate,
        allowed_downtime_s=slo.allowed_downtime_s(service.slo_target, slo.WINDOWS[window]),
        budget_consumed_ratio=report.budget.consumed_ratio if report.budget else None,
        budget_remaining_ratio=report.budget.remaining_ratio if report.budget else None,
        sparkline=report.sparkline,
    )


@router.get("/slo/budget")
def fleet_budget(db: DB, window: Window = "24h") -> schemas.FleetBudgetOut:
    now = datetime.now(UTC)
    services = list(db.scalars(select(Service).order_by(Service.name)))
    last = reporting.last_beats(db)
    items = []
    for service in services:
        report = reporting.build_report(db, service, window, now, last.get(service.id))
        items.append(
            schemas.ServiceBudget(
                service_id=service.id,
                slug=service.slug,
                name=service.name,
                status=report.status,
                slo_target=service.slo_target,
                uptime=report.uptime,
                burn_rate=report.burn_rate,
                budget_remaining_ratio=report.budget.remaining_ratio if report.budget else None,
            )
        )

    judged = [i for i in items if i.uptime is not None]
    meeting = sum(1 for i in judged if i.uptime * 100 >= i.slo_target)
    burns = [i.burn_rate for i in judged]
    return schemas.FleetBudgetOut(
        window=window,
        services=len(items),
        meeting_slo=meeting,
        breaching_slo=len(judged) - meeting,
        no_data=len(items) - len(judged),
        worst_burn_rate=max(burns) if burns else None,
        items=items,
    )
