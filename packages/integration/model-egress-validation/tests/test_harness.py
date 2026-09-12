"""The eighteen rows: conformant offline where executable, named where not, never passed."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest

from ugence_model_egress_unit import COMMISSIONING_STATUS
from ugence_model_egress_validation import (
    OFFLINE_ROWS,
    ROWS,
    STATUS_VOCABULARY,
    SYNTHETIC_PROMPT,
    OfflineRun,
    run_offline,
)
from ugence_model_egress_validation.harness import SCENARIOS

NOW = datetime(2026, 9, 11, 18, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def run() -> OfflineRun:
    return run_offline(now=NOW)


def test_the_row_table_is_the_matrix_and_has_no_pass_status():
    assert [r.row for r in ROWS] == list(range(1, 19))
    assert "PASS" not in STATUS_VOCABULARY and "MET" not in STATUS_VOCABULARY
    assert OFFLINE_ROWS == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 17)
    assert {r.row for r in ROWS if r.infrastructure_dependent} == {12, 18}
    for r in ROWS:
        assert r.offline or r.reason_if_not_offline, r.row


def test_every_offline_row_is_conformant_and_every_other_row_is_named(run):
    assert [o.row for o in run.outcomes] == list(range(1, 19))
    for o in run.outcomes:
        assert o.status in STATUS_VOCABULARY
        if o.row in OFFLINE_ROWS:
            assert o.status == "OFFLINE_CONFORMANT", (o.row, o.observed)
        else:
            assert o.status == "NOT_EXECUTABLE_OFFLINE" and o.reason and o.observed == "not executed"
    assert run.outcome(12).infrastructure_dependent and run.outcome(18).infrastructure_dependent
    assert run.commissioning_status == COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"


@pytest.mark.parametrize("row", sorted(SCENARIOS))
def test_each_scenario_is_deterministic_and_observes_only_names_counts_and_digests(row):
    ok1, observed1, digests1 = SCENARIOS[row](NOW, "MARKER-A-" + "0" * 32)
    ok2, observed2, digests2 = SCENARIOS[row](NOW, "MARKER-B-" + "1" * 32)
    assert ok1 and ok2
    assert observed1 == observed2  # the marker never reaches an observation
    assert "MARKER-" not in observed1 and SYNTHETIC_PROMPT not in observed1
    assert all(len(d) == 64 and all(c in "0123456789abcdef" for c in d) for d in digests1)


def test_the_observations_name_the_required_refusals(run):
    assert "credential_not_commissioned" in run.outcome(1).observed
    assert "refused=8 accepted=0" in run.outcome(3).observed
    assert "content_digest_mismatch" in run.outcome(4).observed
    assert "model_not_pinned" in run.outcome(5).observed
    for row in (6, 7):
        assert "request_limit_exceeded" in run.outcome(row).observed and "dispatches=0" in run.outcome(row).observed
    assert run.outcome(8).observed.count("request_limit_exceeded") == 5
    assert "answered=10 eleventh=commissioning_budget_exhausted dispatches=10 cents_reserved=2500" in run.outcome(9).observed
    assert run.outcome(10).observed == "latest:ValueError service_account_key:ValueError"
    assert "credential_not_commissioned" in run.outcome(11).observed and "reserved=0" in run.outcome(11).observed
    assert run.outcome(16).observed == "proven_then_ok=ANSWERED/2 proven_x3=FAILED/2 unproven=OUTCOME_UNKNOWN/1"
    assert run.outcome(17).observed == "vendor_error_429=FAILED timeout_after_dispatch=OUTCOME_UNKNOWN malformed_answer=FAILED"
    assert run.outcome(2).observed.endswith("leaks=0")


def test_the_run_holds_the_marker_only_in_memory_and_row_2_would_notice_a_leak(run):
    assert len(run.known_markers) == 2 and run.known_markers[0].startswith("MARKER-HARNESS-LEASE-")
    dumped = json.dumps([dataclasses.asdict(o) for o in run.outcomes])
    for marker in run.known_markers:
        assert marker not in dumped
    # a leaked observation flips row 2, by construction of the scan
    leaked = dataclasses.replace(run.outcome(9), observed=run.outcome(9).observed + " " + run.known_markers[0])
    corpus = " ".join(o.observed for o in run.outcomes if o.row != 9) + " " + leaked.observed
    assert run.known_markers[0] in corpus


def test_a_naive_instant_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        run_offline(now=NOW.replace(tzinfo=None))
