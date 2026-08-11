"""Package + authority boundaries (spec §8, §28, §31, §32, §33; matrix 30/31/40/41).

Proves the one-way dependency direction, no second machine-authority artifact, no
third canonical execution ledger, no Agent Runtime import, and that the leaf/RA-6/
RA-7/DA surfaces are not reached backwards from RA-8.
"""

from __future__ import annotations

import sys
from pathlib import Path

import ugence_risk_authority_execution_assurance as ra8

REPO = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parents[1] / "src" / "ugence_risk_authority_execution_assurance"


# ---------------------------------------------------- no second authority ----
def test_no_second_authority_artifact_export():
    forbidden_suffixes = (
        "Authorization",
        "AuthorityGrant",
        "AuthorityEnvelope",
        "AuthorityToken",
        "Grant",
        "Credential",
        "Envelope",
        "Token",
        "Permit",
        "Capability",
    )
    offenders = [
        name for name in ra8.__all__ if any(name.endswith(sfx) for sfx in forbidden_suffixes)
    ]
    assert offenders == [], f"unexpected authority-artifact exports: {offenders}"


def test_service_and_outcome_have_no_lifecycle_mutation():
    for obj in (ra8.EffectAssuranceService, ra8.EffectAssuranceOutcome, ra8.EffectAssuranceAssessment):
        for attr in ("revoke_envelope", "revoke_subject", "revoke_model", "advance_epoch",
                     "emergency_stop", "mint", "grant", "issue"):
            assert not hasattr(obj, attr), f"{obj} exposes {attr}"


def test_ra8_reuses_leaf_signal_not_a_new_signal_type():
    for banned in ("EffectAuthorization", "ReconciliationAuthorization", "EffectGrant",
                   "ReceiptToken", "CompensationAuthority", "ExecutionToken"):
        assert banned not in ra8.__all__
        assert not hasattr(ra8, banned)


def test_handoff_imports_leaf_signal():
    from ugence_risk_authority_execution_assurance.handoff import AuthorityReassessmentSignal
    from risk_authority.domain.authority_signal import (
        AuthorityReassessmentSignal as LeafSignal,
    )

    assert AuthorityReassessmentSignal is LeafSignal


# ------------------------------------------------------- no third ledger ----
def test_ra8_defines_no_execution_ledger():
    # RA-8 owns only correlation/dedupe/observation metadata; the authoritative
    # execution/reconciliation ledger is Decision Authority's (spec §25/§28 I18).
    joined = " ".join(ra8.__all__).lower()
    for banned in ("repository", "ledger", "executionstore", "attemptstore"):
        assert banned not in joined


def test_reference_reconciler_delegates_persistence_to_da():
    # The reference reconciler builds a *fresh* DA in-memory repo per reconcile and
    # holds no long-lived authoritative ledger of its own (bounded, not canonical).
    recon = ra8.ReferenceDecisionAuthorityReconciler()
    assert not any(
        attr for attr in vars(recon) if "repo" in attr.lower() or "ledger" in attr.lower()
    )


# --------------------------------------------------- Agent Runtime decoupled ----
def test_importing_ra8_does_not_pull_in_agent_runtime():
    import ugence_risk_authority_execution_assurance  # noqa: F401

    assert "ugence_agent_runtime" not in sys.modules


def test_source_tree_does_not_import_agent_runtime():
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "ugence_agent_runtime" not in text, f"{py} references the Agent Runtime"
        assert "import agent_runtime" not in text, f"{py} imports agent runtime"


# ------------------------------------------------ one-way dependency direction ----
def _scan_no_backref(package_src: Path) -> None:
    token = "ugence_risk_authority_execution_assurance"
    for py in package_src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert token not in text, f"{py} imports RA-8 (reverse dependency)"


def test_leaf_does_not_import_ra8():
    _scan_no_backref(REPO / "packages" / "risk_authority" / "src")


def test_ra6_status_runtime_does_not_import_ra8():
    _scan_no_backref(
        REPO / "packages" / "integration" / "risk-authority-status-runtime" / "src"
    )


def test_ra7_runtime_assurance_does_not_import_ra8():
    _scan_no_backref(
        REPO / "packages" / "integration" / "risk-authority-runtime-assurance" / "src"
    )


def test_decision_authority_does_not_import_ra8_or_risk_authority():
    da_src = REPO / "packages" / "capabilities" / "decision-authority" / "src"
    _scan_no_backref(da_src)
    for py in da_src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "import risk_authority" not in text, f"{py} imports the RA leaf"
        assert "ugence_risk_authority_status_runtime" not in text


def test_agent_runtime_does_not_import_da_or_ra8():
    ar_src = REPO / "packages" / "runtime" / "agent-runtime" / "src"
    if not ar_src.is_dir():
        return
    for py in ar_src.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "ugence_decision_authority" not in text, f"{py} imports Decision Authority"
        assert "ugence_risk_authority_execution_assurance" not in text


# ------------------------------------------- the single ratified leaf change ----
def test_leaf_signal_enum_has_execution_effect_mismatch():
    from risk_authority.domain.authority_signal import SignalChangeType

    assert hasattr(SignalChangeType, "EXECUTION_EFFECT_MISMATCH")
    assert SignalChangeType.EXECUTION_EFFECT_MISMATCH.value == "EXECUTION_EFFECT_MISMATCH"


def test_no_acp_symbols():
    joined = " ".join(ra8.__all__).lower()
    for banned in ("actuator", "clearance", "actiongate", "thirdpartygateway", "grc"):
        assert banned not in joined
