import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BeatStatus = Literal["ok", "degraded", "fail"]
ServiceState = Literal["up", "degraded", "down", "unknown"]
WindowName = Literal["1h", "24h", "7d"]

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    slug: str | None = Field(default=None, max_length=80)
    heartbeat_interval_s: int = Field(default=30, ge=5, le=3600)
    slo_target: float = Field(default=99.5, ge=50, lt=100)

    @field_validator("slug")
    @classmethod
    def slug_is_kebab_case(cls, value: str | None) -> str | None:
        if value is not None and not SLUG_PATTERN.match(value):
            raise ValueError("slug must be lowercase kebab-case, e.g. payments-api")
        return value


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    heartbeat_interval_s: int | None = Field(default=None, ge=5, le=3600)
    slo_target: float | None = Field(default=None, ge=50, lt=100)


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    heartbeat_interval_s: int
    slo_target: float
    created_at: datetime
    status: ServiceState = "unknown"
    last_beat_at: datetime | None = None


class ServiceCreated(ServiceOut):
    ingest_token: str = Field(description="Shown once. Send it as the X-Argus-Token header.")


class TokenOut(BaseModel):
    ingest_token: str


class HeartbeatIn(BaseModel):
    status: BeatStatus = "ok"
    latency_ms: int | None = Field(default=None, ge=0, le=600_000)


class HeartbeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    received_at: datetime
    status: BeatStatus
    latency_ms: int | None


class UptimeOut(BaseModel):
    service_id: int
    slug: str
    window: WindowName
    status: ServiceState
    slo_target: float
    uptime: float | None
    burn_rate: float | None
    allowed_downtime_s: float
    budget_consumed_ratio: float | None
    budget_remaining_ratio: float | None
    sparkline: list[float | None]


class ServiceBudget(BaseModel):
    service_id: int
    slug: str
    name: str
    status: ServiceState
    slo_target: float
    uptime: float | None
    burn_rate: float | None
    budget_remaining_ratio: float | None


class FleetBudgetOut(BaseModel):
    window: WindowName
    services: int
    meeting_slo: int
    breaching_slo: int
    no_data: int
    worst_burn_rate: float | None
    items: list[ServiceBudget]
