from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    heartbeat_interval_s: Mapped[int] = mapped_column(Integer)
    slo_target: Mapped[float] = mapped_column(Float)  # percent, e.g. 99.5
    ingest_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    heartbeats: Mapped[list["Heartbeat"]] = relationship(
        back_populates="service", cascade="all, delete-orphan", passive_deletes=True
    )


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    __table_args__ = (Index("ix_heartbeats_service_received", "service_id", "received_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(10))  # ok | degraded | fail
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    service: Mapped[Service] = relationship(back_populates="heartbeats")
