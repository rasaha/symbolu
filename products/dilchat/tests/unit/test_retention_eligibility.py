"""Ratified purge-eligibility rule (DEC-PR-3), round PR-B.

Eligibility is NOT deletion: it is the state a later, separately-ratified purge
would consider. Every condition is pinned here, including the reporting-window
boundary and the unconditional dominance of PRESERVED_FOR_REPORT.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.domain.enums import RetentionState
from ugence_dilchat.services.retention import PurgeBlocker, purge_eligibility

_NOW = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)
_DAYS = 30


def _eligibility(**kw):
    base = dict(
        purge_enabled=True,
        state=RetentionState.REVOKED_PENDING_POLICY.value,
        revoked_at=_NOW - dt.timedelta(days=31),
        hold_reason=None,
        retention_days=_DAYS,
        now=_NOW,
    )
    base.update(kw)
    return purge_eligibility(**base)


def test_all_conditions_met_is_eligible():
    assert _eligibility() is None


# --- the reporting/retention window boundary ------------------------------- #


@pytest.mark.parametrize(
    "age_days, expected",
    [
        (0, PurgeBlocker.WITHIN_RETENTION_WINDOW),
        (29, PurgeBlocker.WITHIN_RETENTION_WINDOW),  # day 29: still reportable
        (30, None),  # exactly the window: eligible
        (31, None),  # past the window
        (365, None),
    ],
)
def test_retention_window_boundary(age_days, expected):
    assert _eligibility(revoked_at=_NOW - dt.timedelta(days=age_days)) is expected


def test_boundary_is_exact_to_the_second():
    """One second short of 30 days is NOT eligible; exactly 30 days is."""
    just_short = _NOW - dt.timedelta(days=30) + dt.timedelta(seconds=1)
    assert _eligibility(revoked_at=just_short) is PurgeBlocker.WITHIN_RETENTION_WINDOW
    assert _eligibility(revoked_at=_NOW - dt.timedelta(days=30)) is None


# --- preservation dominance ------------------------------------------------ #


@pytest.mark.parametrize("age_days", [0, 29, 30, 31, 3650])
def test_preserved_for_report_is_never_eligible_at_any_age(age_days):
    assert (
        _eligibility(
            state=RetentionState.PRESERVED_FOR_REPORT.value,
            revoked_at=_NOW - dt.timedelta(days=age_days),
        )
        is PurgeBlocker.PRESERVED_FOR_REPORT
    )


def test_preservation_dominates_even_with_purge_enabled_and_no_hold():
    assert (
        _eligibility(state=RetentionState.PRESERVED_FOR_REPORT.value, purge_enabled=True)
        is PurgeBlocker.PRESERVED_FOR_REPORT
    )


# --- the remaining ratified conditions ------------------------------------- #


def test_disabled_flag_blocks_everything():
    assert _eligibility(purge_enabled=False) is PurgeBlocker.PURGE_DISABLED


@pytest.mark.parametrize("age_days", [0, 30, 3650])
def test_legal_hold_is_never_eligible_at_any_age(age_days):
    assert (
        _eligibility(hold_reason="LEGAL_HOLD", revoked_at=_NOW - dt.timedelta(days=age_days))
        is PurgeBlocker.LEGAL_HOLD
    )


def test_policy_exception_hold_uses_the_same_path():
    assert _eligibility(hold_reason="POLICY_EXCEPTION") is PurgeBlocker.LEGAL_HOLD


def test_active_conversation_is_never_eligible():
    assert _eligibility(state=RetentionState.ACTIVE.value) is PurgeBlocker.NOT_REVOKED_STATE


def test_already_purged_is_not_re_eligible():
    assert _eligibility(state=RetentionState.PURGED.value) is PurgeBlocker.ALREADY_PURGED


def test_missing_revocation_timestamp_fails_closed():
    assert _eligibility(revoked_at=None) is PurgeBlocker.MISSING_REVOCATION_TIMESTAMP


def test_every_state_value_yields_a_decision():
    """Total function: no state can slip through undecided."""
    for state in RetentionState:
        result = _eligibility(state=state.value, revoked_at=_NOW - dt.timedelta(days=99))
        assert result is None or isinstance(result, PurgeBlocker)
    # Only the two revoked-side states can ever be eligible.
    eligible_states = {
        s.value
        for s in RetentionState
        if _eligibility(state=s.value, revoked_at=_NOW - dt.timedelta(days=99)) is None
    }
    assert eligible_states == {
        RetentionState.REVOKED_PENDING_POLICY.value,
        RetentionState.ELIGIBLE_FOR_PURGE.value,
    }


# --- settings guards -------------------------------------------------------- #


def _settings(**kw) -> Settings:
    return Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://", **kw)


def test_ratified_retention_defaults():
    s = _settings()
    assert s.chat_retention_revoked_days == 30
    assert s.chat_report_after_revocation_days == 30
    # The ratified amendment: destructive purging stays OFF.
    assert s.retention_purge_enabled is False


def test_retention_may_never_undercut_the_reporting_window():
    with pytest.raises(ValueError, match="reporting window"):
        _settings(chat_retention_revoked_days=15)
    # Equal is permitted; longer is permitted.
    assert _settings(chat_retention_revoked_days=30).chat_retention_revoked_days == 30
    assert _settings(chat_retention_revoked_days=90).chat_retention_revoked_days == 90


def test_a_longer_reporting_window_also_forces_longer_retention():
    with pytest.raises(ValueError, match="reporting window"):
        _settings(chat_report_after_revocation_days=60)
    assert (
        _settings(
            chat_report_after_revocation_days=60, chat_retention_revoked_days=60
        ).chat_retention_revoked_days
        == 60
    )
