"""Runner behaviour, C1/Phase-6A equivalence, invariants, failover, reproducibility, CLI."""
from __future__ import annotations

import pytest

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy
from provider_heterogeneity_validation import run as run_module
from provider_heterogeneity_validation.evaluators.invariants import check_invariants, invariants_passed
from provider_heterogeneity_validation.failure_injection.profiles import FailureProfile
from provider_heterogeneity_validation.runners.workflow import run
from provider_heterogeneity_validation.schemas.config import CONFIGURATIONS
from provider_heterogeneity_validation.validation import run_validation

_DS = load_frozen_dataset()
# reduced-scope validation shared across tests (keeps the suite fast)
_RES = run_validation(profiles=(FailureProfile.NORMAL, FailureProfile.TAP_UNAVAILABLE,
                                FailureProfile.ACTIONGATE_UNAVAILABLE,
                                FailureProfile.NO_COMPATIBLE_PROVIDER,
                                FailureProfile.NO_CAPABILITY_MATCH,
                                FailureProfile.REGISTRY_DUPLICATE_ID,
                                FailureProfile.TAP_INCOMPATIBLE))


def test_c1_reproduces_phase6a_full_governance():
    full = build_strategy("full_governance")
    for s in _DS.ordered():
        hr = run(s, CONFIGURATIONS["C1"])
        fr = full.run(s)
        assert hr.dispatched == fr.dispatched, s.scenario_id
        assert hr.assertion_outcome == fr.assertion_outcome, s.scenario_id
        assert hr.authorization_outcome == fr.authorization_outcome, s.scenario_id


def test_no_config_has_unsafe_outcomes():
    for cid, c in _RES.configuration_comparison.items():
        assert c["unsafe_outcomes"] == 0, (cid, c)


@pytest.mark.parametrize("inv", _RES.invariants, ids=[i.id for i in _RES.invariants])
def test_invariant(inv):
    assert inv.passed, f"{inv.id} {inv.description}: {inv.detail}"


def test_all_invariants_pass():
    assert invariants_passed(_RES.invariants)


def test_capability_limited_never_promotes():
    # baseline assertion on a qualifier scenario → INDETERMINATE (never SUPPORTED)
    r = run(_DS.by_id("procurement-006"), CONFIGURATIONS["C4"])
    assert r.assertion_outcome == "INDETERMINATE"
    assert not r.dispatched


def test_governance_shopping_prevented_on_unsupported():
    # C5 bounded fallback, both healthy: TAP returns UNSUPPORTED → no fallback, no dispatch
    r = run(_DS.by_id("procurement-003"), CONFIGURATIONS["C5"])
    assert r.assertion_outcome == "UNSUPPORTED"
    assert not r.assertion_fallback_used and not r.dispatched


def test_governance_shopping_prevented_on_denied():
    # C5: ActionGate DENIED → never falls back to baseline to authorize
    r = run(_DS.by_id("procurement-013"), CONFIGURATIONS["C5"])
    assert r.authorization_outcome == "DENIED"
    assert not r.action_fallback_used and not r.dispatched


def test_safe_fallback_under_unavailability():
    r = run(_DS.by_id("procurement-001"), CONFIGURATIONS["C5"], FailureProfile.TAP_UNAVAILABLE)
    assert r.assertion_provider_id == "baseline-assertion"
    assert r.assertion_fallback_used and r.assertion_outcome == "SUPPORTED"


def test_fallback_to_less_capable_stays_fail_safe():
    # qualifier scenario + TAP unavailable → fallback to baseline → INDETERMINATE, no dispatch
    r = run(_DS.by_id("procurement-006"), CONFIGURATIONS["C5"], FailureProfile.TAP_UNAVAILABLE)
    assert r.assertion_fallback_used and r.assertion_outcome == "INDETERMINATE"
    assert not r.dispatched


def test_no_valid_provider_fail_safe():
    r = run(_DS.by_id("procurement-001"), CONFIGURATIONS["C5"], FailureProfile.NO_COMPATIBLE_PROVIDER)
    assert r.no_valid_assertion_provider and r.assertion_outcome == "INDETERMINATE"
    assert not r.dispatched


def test_reproducible_digest():
    a = run_validation(profiles=(FailureProfile.NORMAL,))
    b = run_validation(profiles=(FailureProfile.NORMAL,))
    assert a.substantive_digest == b.substantive_digest


def test_cli_writes_reports(tmp_path):
    code = run_module.main(["--output", str(tmp_path / "p6b"),
                            "--failure-profile", "TAP_UNAVAILABLE"])
    assert code == 0
    for name in ("PHASE_6B_HETEROGENEITY_REPORT.md", "PHASE_6B_RESOLUTION_METRICS.json",
                 "PHASE_6B_INVARIANTS.json", "PHASE_6B_SELECTION_RECORDS.json",
                 "PHASE_6B_COST_BENEFIT_FRONTIER.json", "PHASE_6B_CONFIGURATION_COMPARISON.json",
                 "PHASE_6B_FAILURE_MATRIX.json", "PHASE_6B_PROVIDER_RESULTS.json"):
        assert (tmp_path / "p6b" / name).exists(), name
