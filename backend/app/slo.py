"""SLO maths for Argus.

Everything here is a pure function of its inputs. Callers pass `now` explicitly, so the
behaviour is deterministic and the tests need no clock mocking.

Vocabulary
----------
slot        One heartbeat interval. A service promises at least one beat per slot.
good slot   A slot that received at least one beat whose status counts as available
            (`ok` or `degraded`). A `fail` beat, or silence, leaves the slot bad.
uptime      good slots / counted slots, over a window.
error budget  The downtime the SLO allows over a window: (1 - target) x window length.
            A 99.5% SLO allows 432 seconds a day.
burn rate   How fast the budget is being spent. 1.0 spends exactly the budget over the
            window; 14.4 would exhaust a 30-day budget in about 2 days.
"""

from bisect import bisect_left
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# What a heartbeat reports.
BEAT_OK = "ok"
BEAT_DEGRADED = "degraded"
BEAT_FAIL = "fail"

# What Argus concludes about a service.
UP = "up"
DEGRADED = "degraded"
DOWN = "down"
UNKNOWN = "unknown"

AVAILABLE_STATUSES = frozenset({BEAT_OK, BEAT_DEGRADED})

# 5m, 30m and 6h exist for the burn-rate alerts' short and long windows; the API offers
# only 1h, 24h and 7d.
WINDOWS: dict[str, timedelta] = {
    "5m": timedelta(minutes=5),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


def as_utc(moment: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat those as UTC."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def current_status(
    last_beat_at: datetime | None,
    last_beat_status: str | None,
    interval_s: int,
    now: datetime,
    missed_beats_before_down: int = 2,
) -> str:
    """Liveness is inferred from absence: silence for N intervals means DOWN."""
    if last_beat_at is None:
        return UNKNOWN
    silence = (as_utc(now) - as_utc(last_beat_at)).total_seconds()
    if silence > interval_s * missed_beats_before_down:
        return DOWN
    if last_beat_status == BEAT_FAIL:
        return DOWN
    if last_beat_status == BEAT_DEGRADED:
        return DEGRADED
    return UP


def is_available(state: str) -> bool:
    """Up or degraded: the service is still serving, so it counts as available."""
    return state in (UP, DEGRADED)


@dataclass(frozen=True)
class SlotCount:
    good: int
    counted: int

    @property
    def bad(self) -> int:
        return self.counted - self.good

    @property
    def ratio(self) -> float | None:
        return self.good / self.counted if self.counted else None


def count_slots(
    good_beats: Iterable[datetime],
    window_start: datetime,
    window_end: datetime,
    interval_s: int,
    created_at: datetime | None = None,
) -> SlotCount:
    """Count good slots, and slots that are fair to judge, within the window.

    The window is clipped to the service's creation time, so a service registered ten
    minutes ago is judged on ten minutes, not on a day it did not exist for.

    Only complete slots are counted, plus the in-progress slot if it already has a good
    beat. Without that rule every service would look slightly down between beats.
    """
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")

    start = as_utc(window_start)
    end = as_utc(window_end)
    if created_at is not None:
        start = max(start, as_utc(created_at))
    if end <= start:
        return SlotCount(0, 0)

    complete_slots = int((end - start).total_seconds() // interval_s)
    good_slots = {
        int((as_utc(beat) - start).total_seconds() // interval_s)
        for beat in good_beats
        if start <= as_utc(beat) < end
    }
    counted = complete_slots + (1 if complete_slots in good_slots else 0)
    return SlotCount(len(good_slots), counted)


def slot_uptime(
    good_beats: Iterable[datetime],
    window_start: datetime,
    window_end: datetime,
    interval_s: int,
    created_at: datetime | None = None,
) -> float | None:
    """Fraction of judged slots that saw a good beat, or None if nothing can be judged yet."""
    return count_slots(good_beats, window_start, window_end, interval_s, created_at).ratio


def allowed_error_ratio(slo_target_pct: float) -> float:
    if not 0 < slo_target_pct < 100:
        raise ValueError("slo_target must be between 0 and 100, exclusive")
    return 1 - slo_target_pct / 100


def allowed_downtime_s(slo_target_pct: float, window: timedelta) -> float:
    """The error budget in seconds: (1 - target) x window length."""
    return allowed_error_ratio(slo_target_pct) * window.total_seconds()


def burn_rate(uptime: float, slo_target_pct: float) -> float:
    """Observed error ratio divided by the allowed error ratio."""
    return (1 - uptime) / allowed_error_ratio(slo_target_pct)


@dataclass(frozen=True)
class ErrorBudget:
    allowed_downtime_s: float
    consumed_ratio: float
    remaining_ratio: float

    @property
    def exhausted(self) -> bool:
        return self.consumed_ratio >= 1


def error_budget(slo_target_pct: float, bad_seconds: float, window: timedelta) -> ErrorBudget:
    """Downtime spent against downtime allowed over one window.

    This is deliberately measured in seconds rather than derived from the uptime ratio. A
    service that has existed for three minutes and missed one 10-second slot has spent
    10 s of an 86 s daily budget at 99.9%, which is 12%, not 58 times the budget. The *rate* of
    spending is what `burn_rate` reports. `remaining_ratio` goes negative once the budget
    for the window is gone.
    """
    allowed_s = allowed_downtime_s(slo_target_pct, window)
    consumed = bad_seconds / allowed_s
    return ErrorBudget(
        allowed_downtime_s=allowed_s,
        consumed_ratio=consumed,
        remaining_ratio=1 - consumed,
    )


def sparkline(
    good_beats: list[datetime],
    window_start: datetime,
    window_end: datetime,
    interval_s: int,
    created_at: datetime | None = None,
    buckets: int = 30,
) -> list[float | None]:
    """Uptime per bucket across the window, oldest first, for the UI's mini chart."""
    start = as_utc(window_start)
    step = (as_utc(window_end) - start) / buckets
    beats = sorted(as_utc(b) for b in good_beats)
    points: list[float | None] = []
    for i in range(buckets):
        lo, hi = start + step * i, start + step * (i + 1)
        in_bucket = beats[bisect_left(beats, lo) : bisect_left(beats, hi)]
        points.append(slot_uptime(in_bucket, lo, hi, interval_s, created_at))
    return points
