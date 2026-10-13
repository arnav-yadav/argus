"""Turns stored heartbeats into SLO reports. Shared by the API and the metrics collector."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import slo
from app.config import settings
from app.models import Heartbeat, Service


@dataclass(frozen=True)
class LastBeat:
    received_at: datetime
    status: str


@dataclass(frozen=True)
class Report:
    service: Service
    window: str
    status: str
    uptime: float | None
    burn_rate: float | None
    budget: slo.ErrorBudget | None
    sparkline: list[float | None]


def last_beats(db: Session, service_ids: list[int] | None = None) -> dict[int, LastBeat]:
    """Most recent heartbeat per service, in one query."""
    latest = select(
        Heartbeat.service_id, func.max(Heartbeat.received_at).label("last_at")
    ).group_by(Heartbeat.service_id)
    if service_ids is not None:
        latest = latest.where(Heartbeat.service_id.in_(service_ids))
    latest = latest.subquery()

    rows = db.execute(
        select(Heartbeat.service_id, Heartbeat.received_at, Heartbeat.status).join(
            latest,
            and_(
                Heartbeat.service_id == latest.c.service_id,
                Heartbeat.received_at == latest.c.last_at,
            ),
        )
    )
    return {row.service_id: LastBeat(row.received_at, row.status) for row in rows}


def status_of(service: Service, last: LastBeat | None, now: datetime) -> str:
    return slo.current_status(
        last.received_at if last else None,
        last.status if last else None,
        service.heartbeat_interval_s,
        now,
        settings.missed_beats_before_down,
    )


def good_beats_since(db: Session, service_id: int, since: datetime) -> list[datetime]:
    return list(
        db.scalars(
            select(Heartbeat.received_at).where(
                Heartbeat.service_id == service_id,
                Heartbeat.received_at >= since,
                Heartbeat.status.in_(slo.AVAILABLE_STATUSES),
            )
        )
    )


def build_report(
    db: Session,
    service: Service,
    window: str,
    now: datetime,
    last: LastBeat | None,
    with_sparkline: bool = False,
) -> Report:
    span: timedelta = slo.WINDOWS[window]
    start = now - span
    beats = good_beats_since(db, service.id, start)

    uptime = slo.slot_uptime(beats, start, now, service.heartbeat_interval_s, service.created_at)
    budget = slo.error_budget(service.slo_target, uptime, span) if uptime is not None else None
    burn = slo.burn_rate(uptime, service.slo_target) if uptime is not None else None
    spark = (
        slo.sparkline(beats, start, now, service.heartbeat_interval_s, service.created_at)
        if with_sparkline
        else []
    )
    return Report(service, window, status_of(service, last, now), uptime, burn, budget, spark)
