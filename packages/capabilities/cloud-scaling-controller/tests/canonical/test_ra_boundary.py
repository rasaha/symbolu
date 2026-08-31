"""Risk Authority / authority boundary tests for the canonical layer (section 19.5).

The canonical capacity-intelligence layer produces upstream RECOMMENDATION EVIDENCE only.
It must not import or construct any Risk Authority / Decision Authority / ActionGate
artifact, evaluate risk, or issue any authority/authorization. Its evidence digest is a
content identity, never a signature.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

import pytest

import ugence_cloud_scaling_controller
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacitySubject, CapacityState, InfrastructureState,
    Measurement, NormalizationMethod, NormalizationPolicy, Unit, recommend_with_evidence,
)

PKG_DIR = pathlib.Path(ugence_cloud_scaling_controller.__file__).parent
CANON_DIR = PKG_DIR / "canonical"
CANON_FILES = sorted(CANON_DIR.rglob("*.py"))

# Authority/enforcement implementation namespaces that must never be imported here.
FORBIDDEN_AUTHORITY_IMPORTS = {
    "risk_authority", "ugence_risk_authority", "ugence_risk_authority_execution_assurance",
    "decision_authority", "ugence_decision_authority", "actiongate", "actiongate_provider",
    "agent_runtime", "ugence_agent_runtime", "runtime_assurance", "control_plane",
    "cloud_scaling_operations", "ugence_cloud_scaling_operations",
}

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _imports(path):
    names = set()
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_canonical_layer_imports_no_authority_implementation():
    offenders = {}
    for p in CANON_FILES:
        bad = _imports(p) & FORBIDDEN_AUTHORITY_IMPORTS
        if bad:
            offenders[p.name] = sorted(bad)
    assert not offenders, f"canonical layer imports authority implementations: {offenders}"


def test_canonical_layer_uses_only_stdlib_and_own_package():
    # Every top-level import must be stdlib or a relative import of this package.
    import sys
    allowed_third_party = set()  # canonical layer adds no third-party dependency
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    offenders = {}
    for p in CANON_FILES:
        for name in _imports(p):
            if name in stdlib or name in allowed_third_party:
                continue
            if name == "ugence_cloud_scaling_controller":
                continue
            offenders.setdefault(p.name, set()).add(name)
    assert not offenders, f"unexpected imports in canonical layer: {offenders}"


def test_no_risk_authority_symbols_referenced():
    forbidden_tokens = (
        "RiskAuthorization", "RiskDecision", "RiskAuthorizationEnvelope", "AuthorityGrant",
        "ActionGate", "ControlEvidenceRecord", "EffectAssuranceAssessment", "RiskVerdict",
    )
    hits = {}
    for p in CANON_FILES:
        text = p.read_text()
        for tok in forbidden_tokens:
            if tok in text:
                hits.setdefault(tok, []).append(p.name)
    assert not hits, f"canonical layer references RA domain symbols: {hits}"


def test_evidence_digest_is_not_a_signature():
    p = NormalizationPolicy(policy_id="p", method_by_signal={"cpu": NormalizationMethod.PERCENT_TO_RATIO})
    s = CanonicalCapacityState(subject=CapacitySubject(workload_id="w"), observed_at=NOW,
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
                               capacity=CapacityState(running_replicas=3))
    _, ev = recommend_with_evidence(s, p)
    d = ev.to_canonical_dict()
    # A content identity, not a signature/authorization.
    assert "signature" not in d and "signed_by" not in d and "authority_epoch" not in d
    assert ev.digest().startswith("sha256:")  # plain content digest


def test_no_authority_lifecycle_or_evaluation_api():
    # The canonical package exposes no risk-evaluation / authorization entrypoint.
    import ugence_cloud_scaling_controller.canonical as canon
    exported = set(canon.__all__)
    for banned in ("evaluate_risk", "authorize", "issue_authorization", "revoke",
                   "match_envelope", "grant", "deny"):
        assert banned not in exported
