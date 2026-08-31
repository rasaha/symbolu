"""Relay heartbeat, relay health probe, and preflight (round PR-C).

The relay serves no HTTP surface, so its liveness signal is heartbeat freshness.
These pin that the signal is content-free, atomic, fails closed when unusable,
and that a healthy idle relay can never look stale by configuration.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.relay.__main__ import write_heartbeat
from ugence_dilchat.scripts_relay_health import check

_NOW = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)


def _settings(**kw) -> Settings:
    return Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://", **kw)


# --- heartbeat writing ------------------------------------------------------ #


def test_heartbeat_contains_only_a_timestamp(tmp_path):
    path = tmp_path / "relay.heartbeat"
    write_heartbeat(str(path))
    raw = path.read_text()
    # Parses as a timestamp and carries nothing else.
    assert dt.datetime.fromisoformat(raw)
    assert len(raw.splitlines()) == 1


def test_heartbeat_creates_missing_parent_directory(tmp_path):
    path = tmp_path / "nested" / "dir" / "relay.heartbeat"
    write_heartbeat(str(path))
    assert path.exists()


def test_heartbeat_write_failure_never_raises(tmp_path):
    # A path whose parent cannot be created: the relay must keep running.
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    write_heartbeat(str(blocker / "sub" / "relay.heartbeat"))  # must not raise


def test_heartbeat_leaves_no_temp_files_behind(tmp_path):
    path = tmp_path / "relay.heartbeat"
    for _ in range(3):
        write_heartbeat(str(path))
    assert [p.name for p in tmp_path.iterdir()] == ["relay.heartbeat"]


# --- health probe ------------------------------------------------------------ #


def test_probe_reports_ok_for_a_fresh_heartbeat(tmp_path):
    path = tmp_path / "relay.heartbeat"
    path.write_text((_NOW - dt.timedelta(seconds=5)).isoformat())
    code, message = check(_settings(relay_heartbeat_path=str(path)), now=_NOW)
    assert code == 0
    assert message.startswith("RELAY_HEARTBEAT_OK")


def test_probe_reports_stale_past_the_bound(tmp_path):
    path = tmp_path / "relay.heartbeat"
    path.write_text((_NOW - dt.timedelta(seconds=121)).isoformat())
    code, message = check(_settings(relay_heartbeat_path=str(path)), now=_NOW)
    assert code == 1
    assert message.startswith("RELAY_HEARTBEAT_STALE")


def test_probe_fails_closed_on_missing_and_unreadable(tmp_path):
    missing = _settings(relay_heartbeat_path=str(tmp_path / "absent"))
    assert check(missing, now=_NOW) == (1, "RELAY_HEARTBEAT_MISSING")

    garbled = tmp_path / "relay.heartbeat"
    garbled.write_text("not-a-timestamp")
    code, message = check(_settings(relay_heartbeat_path=str(garbled)), now=_NOW)
    assert (code, message) == (1, "RELAY_HEARTBEAT_UNREADABLE")


def test_probe_fails_closed_when_no_heartbeat_is_configured():
    code, message = check(_settings(), now=_NOW)
    assert (code, message) == (2, "RELAY_HEARTBEAT_NOT_CONFIGURED")


def test_a_naive_timestamp_is_treated_as_utc(tmp_path):
    path = tmp_path / "relay.heartbeat"
    path.write_text((_NOW - dt.timedelta(seconds=5)).replace(tzinfo=None).isoformat())
    assert check(_settings(relay_heartbeat_path=str(path)), now=_NOW)[0] == 0


def test_round_trip_write_then_probe(tmp_path):
    path = tmp_path / "relay.heartbeat"
    write_heartbeat(str(path))
    assert check(_settings(relay_heartbeat_path=str(path)))[0] == 0


# --- configuration sanity ---------------------------------------------------- #


def test_heartbeat_bound_must_exceed_the_idle_poll_interval():
    """Otherwise a healthy, idle relay would report itself unhealthy."""
    with pytest.raises(ValueError, match="relay_heartbeat_max_age_seconds"):
        _settings(relay_heartbeat_max_age_seconds=2, relay_poll_interval_seconds=2.0)
    with pytest.raises(ValueError, match="relay_heartbeat_max_age_seconds"):
        _settings(relay_heartbeat_max_age_seconds=1, relay_poll_interval_seconds=5.0)
    assert _settings(relay_heartbeat_max_age_seconds=120).relay_heartbeat_max_age_seconds == 120


def test_ratified_deployment_defaults():
    s = _settings()
    assert s.relay_heartbeat_path is None  # opt-in; absent = no heartbeat
    assert s.relay_heartbeat_max_age_seconds == 120
