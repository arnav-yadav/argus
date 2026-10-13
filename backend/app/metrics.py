"""Prometheus metrics.

SLO gauges are computed at scrape time by a custom collector that reads the database.
That keeps every replica stateless: there is no background scheduler to run twice when
the backend is scaled out, and every replica reports the same numbers.
"""

import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from prometheus_client import REGISTRY, Counter
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import reporting, slo
from app.models import Service

log = logging.getLogger(__name__)

HEARTBEATS = Counter(
    "argus_heartbeats",
    "Heartbeats accepted by this replica.",
    ["service", "status"],
)

# 5m and 1h feed the fast-burn alert; 24h feeds the slow-burn alert and the budget gauge.
SCRAPE_WINDOWS = ("5m", "1h", "24h")
BUDGET_WINDOW = "24h"


class SLOCollector(Collector):
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def describe(self) -> list:
        # Returning nothing stops the registry calling collect() at registration time,
        # which would hit the database before the app has finished starting.
        return []

    def collect(self) -> Iterator[GaugeMetricFamily]:
        up = GaugeMetricFamily(
            "argus_service_up", "1 when the service is up or degraded, else 0.", labels=["service"]
        )
        uptime = GaugeMetricFamily(
            "argus_uptime_ratio", "Share of good heartbeat slots.", labels=["service", "window"]
        )
        burn = GaugeMetricFamily(
            "argus_burn_rate",
            "Error-budget burn rate. 1 = on budget.",
            labels=["service", "window"],
        )
        budget = GaugeMetricFamily(
            "argus_error_budget_remaining_ratio",
            f"Error budget left over {BUDGET_WINDOW}. Negative once the SLO is breached.",
            labels=["service"],
        )
        slo_target = GaugeMetricFamily(
            "argus_slo_target_ratio", "Configured SLO target as a ratio.", labels=["service"]
        )

        try:
            with self._session_factory() as db:
                now = datetime.now(UTC)
                services = list(db.scalars(select(Service)))
                last = reporting.last_beats(db)
                for service in services:
                    slug = service.slug
                    last_beat = last.get(service.id)
                    state = reporting.status_of(service, last_beat, now)
                    up.add_metric([slug], 1.0 if slo.is_available(state) else 0.0)
                    slo_target.add_metric([slug], service.slo_target / 100)
                    for window in SCRAPE_WINDOWS:
                        report = reporting.build_report(db, service, window, now, last_beat)
                        if report.uptime is not None:
                            uptime.add_metric([slug, window], report.uptime)
                            burn.add_metric([slug, window], report.burn_rate)
                        if window == BUDGET_WINDOW and report.budget is not None:
                            budget.add_metric([slug], report.budget.remaining_ratio)
        except Exception:  # a broken database must not take /metrics down with it
            log.exception("SLO collector failed")
            return

        yield from (up, uptime, burn, budget, slo_target)


_registered = False


def register_slo_collector(session_factory: Callable[[], Session]) -> None:
    global _registered
    if not _registered:
        REGISTRY.register(SLOCollector(session_factory))
        _registered = True
