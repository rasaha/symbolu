"""Pin the ratified Phase 3B safety-limit defaults (DILCHAT-D3B-4).

These are enforceable safety limits, not documentation: enforcement is proven
by tests/integration/test_safety_flows.py (which trips the limiter by seeding
counters to the CONFIGURED value), and this test pins the shipped defaults so a
silent change to the ratified numbers fails loudly. The test environment may
override them (env-prefixed settings), which is exactly why the defaults need
their own pin.
"""

from __future__ import annotations

from ugence_dilchat.config import Environment, Settings


def _settings() -> Settings:
    return Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://")


def test_ratified_rate_limit_defaults():
    s = _settings()
    assert s.ratelimit_send_per_minute == 30
    assert s.ratelimit_send_per_hour == 300
    assert s.ratelimit_report_per_day == 10
    assert s.ratelimit_block_mutations_per_hour == 60


def test_report_policy_defaults():
    s = _settings()
    assert s.safety_report_description_max_code_points == 1000
    assert s.safety_evidence_window_default == 50
    assert s.safety_evidence_window_max == 50
    assert s.chat_report_after_revocation_days == 30
    # Destructive scheduled purging is NOT run in Phase 3B.
    assert s.retention_purge_enabled is False
