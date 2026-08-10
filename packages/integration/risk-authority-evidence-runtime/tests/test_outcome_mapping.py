"""Unit coverage for the ratified TAP-outcome → ControlStatus mapping (§9)."""

from __future__ import annotations

import pytest

from ugence_governance_contracts.contracts.assertion import AssertionCoverage

from risk_authority.domain.enums import ControlStatus
from ugence_risk_authority_evidence_runtime import map_assertion_outcome


def test_supported_full_coverage_is_pass():
    assert map_assertion_outcome(AssertionCoverage.SUPPORTED, 1.0) is ControlStatus.PASS


@pytest.mark.parametrize("coverage", [0.0, 0.5, 0.999, None])
def test_supported_partial_or_unquantified_is_not_pass(coverage):
    assert map_assertion_outcome(AssertionCoverage.SUPPORTED, coverage) is ControlStatus.UNKNOWN


def test_unsupported_is_fail():
    assert map_assertion_outcome(AssertionCoverage.UNSUPPORTED, 1.0) is ControlStatus.FAIL


def test_constrained_is_not_pass():
    assert map_assertion_outcome(AssertionCoverage.CONSTRAINED, 1.0) is ControlStatus.UNKNOWN


def test_indeterminate_is_not_pass():
    assert map_assertion_outcome(AssertionCoverage.INDETERMINATE, 1.0) is ControlStatus.UNKNOWN


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "1.0", True])
def test_malformed_coverage_never_passes(bad):
    # Only a real numeric coverage >= 1.0 clears the gate; NaN/inf/str/bool do not.
    assert map_assertion_outcome(AssertionCoverage.SUPPORTED, bad) is ControlStatus.UNKNOWN


def test_coverage_above_one_is_clamped_and_passes():
    # A provider over-reporting coverage still only means "full" — never a weight.
    assert map_assertion_outcome(AssertionCoverage.SUPPORTED, 1.5) is ControlStatus.PASS
