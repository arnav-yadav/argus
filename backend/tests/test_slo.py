"""Unit tests for the SLO maths. No database, no HTTP, no clock: time is passed in."""

from datetime import UTC, datetime, timedelta

import pytest

from app import slo

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


def beats_every(seconds: int, start: datetime, end: datetime) -> list[datetime]:
    out, t = [], start
    while t < end:
        out.append(t)
        t += timedelta(seconds=seconds)
    return out


class TestCurrentStatus:
    def test_no_heartbeat_yet_is_unknown(self):
        assert slo.current_status(None, None, 30, NOW) == slo.UNKNOWN

    def test_recent_ok_beat_is_up(self):
        assert slo.current_status(NOW - timedelta(seconds=20), "ok", 30, NOW) == slo.UP

    def test_silence_beyond_two_intervals_is_down(self):
        assert slo.current_status(NOW - timedelta(seconds=61), "ok", 30, NOW) == slo.DOWN

    def test_silence_threshold_is_configurable(self):
        last = NOW - timedelta(seconds=61)
        assert slo.current_status(last, "ok", 30, NOW, missed_beats_before_down=3) == slo.UP

    @pytest.mark.parametrize(
        ("beat_status", "expected"), [("degraded", "degraded"), ("fail", "down")]
    )
    def test_service_reported_state_is_respected(self, beat_status, expected):
        assert slo.current_status(NOW - timedelta(seconds=5), beat_status, 30, NOW) == expected

    def test_naive_timestamps_from_sqlite_are_treated_as_utc(self):
        naive = (NOW - timedelta(seconds=5)).replace(tzinfo=None)
        assert slo.current_status(naive, "ok", 30, NOW) == slo.UP


class TestSlotUptime:
    def test_a_beat_in_every_slot_is_full_uptime(self):
        start = NOW - timedelta(hours=1)
        assert slo.slot_uptime(beats_every(30, start, NOW), start, NOW, 30) == 1.0

    def test_silent_second_half_is_half_uptime(self):
        start = NOW - timedelta(hours=1)
        beats = beats_every(30, start, start + timedelta(minutes=30))
        assert slo.slot_uptime(beats, start, NOW, 30) == pytest.approx(0.5)

    def test_extra_beats_in_one_slot_do_not_inflate_uptime(self):
        start = NOW - timedelta(minutes=10)
        beats = beats_every(1, start, start + timedelta(minutes=5))  # 300 beats, 10 slots
        assert slo.slot_uptime(beats, start, NOW, 30) == pytest.approx(0.5)

    def test_window_is_clipped_to_service_creation(self):
        created = NOW - timedelta(minutes=10)
        beats = beats_every(30, created, NOW)
        # A 24h window, but the service only existed for 10 minutes, all of them healthy.
        assert slo.slot_uptime(beats, NOW - timedelta(hours=24), NOW, 30, created) == 1.0

    def test_unfinished_slot_without_a_beat_yet_is_not_counted(self):
        start = NOW - timedelta(seconds=75)  # two complete 30s slots + 15s in progress
        beats = [start + timedelta(seconds=1), start + timedelta(seconds=31)]
        assert slo.slot_uptime(beats, start, NOW, 30) == 1.0

    def test_slot_count_reports_bad_slots(self):
        start = NOW - timedelta(minutes=10)
        count = slo.count_slots(
            beats_every(30, start, start + timedelta(minutes=5)), start, NOW, 30
        )
        assert (count.good, count.counted, count.bad) == (10, 20, 10)

    def test_nothing_to_judge_returns_none(self):
        assert slo.slot_uptime([], NOW, NOW, 30) is None
        assert slo.slot_uptime([], NOW - timedelta(seconds=5), NOW, 30) is None

    def test_rejects_non_positive_interval(self):
        with pytest.raises(ValueError):
            slo.slot_uptime([], NOW - timedelta(hours=1), NOW, 0)


class TestErrorBudget:
    def test_burn_rate_of_one_means_exactly_on_budget(self):
        assert slo.burn_rate(0.995, 99.5) == pytest.approx(1.0)

    def test_burn_rate_scales_with_errors(self):
        assert slo.burn_rate(0.99, 99.5) == pytest.approx(2.0)
        assert slo.burn_rate(1.0, 99.5) == 0

    def test_budget_for_99_5_over_a_day_is_432_seconds(self):
        budget = slo.error_budget(99.5, 0, timedelta(hours=24))
        assert budget.allowed_downtime_s == pytest.approx(432)
        assert budget.remaining_ratio == pytest.approx(1.0)
        assert not budget.exhausted

    def test_budget_counts_downtime_spent_not_the_error_rate(self):
        # A new service missed one 10s slot. At 99.9% it may lose 86.4s a day, so 10s of
        # downtime is about 12% of the budget, even though its short-term rate is far worse.
        budget = slo.error_budget(99.9, 10, timedelta(hours=24))
        assert budget.consumed_ratio == pytest.approx(10 / 86.4)
        assert not budget.exhausted

    def test_breached_slo_has_negative_remaining_budget(self):
        budget = slo.error_budget(99.9, 864, timedelta(hours=24))  # 1% of a day down
        assert budget.consumed_ratio == pytest.approx(10)
        assert budget.remaining_ratio == pytest.approx(-9)
        assert budget.exhausted

    @pytest.mark.parametrize("target", [0, 100, 101, -5])
    def test_impossible_targets_are_rejected(self, target):
        with pytest.raises(ValueError):
            slo.allowed_error_ratio(target)


def test_sparkline_shows_where_the_outage_was():
    start = NOW - timedelta(hours=1)
    beats = beats_every(30, start, start + timedelta(minutes=30))
    points = slo.sparkline(beats, start, NOW, 30, buckets=4)
    assert points == [1.0, 1.0, 0.0, 0.0]
