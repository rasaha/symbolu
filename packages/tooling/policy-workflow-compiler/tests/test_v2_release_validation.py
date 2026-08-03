"""Strict, deterministic release validation."""

from __future__ import annotations

from ugence_policy_workflow_compiler.semantics import enrich_workflow
from ugence_policy_workflow_compiler.validation.release_validator import (
    CompiledReleaseValidator,
    ReleaseValidationCode,
    ReleaseValidationState,
    validate_compiled_release,
)
import _v2_helpers as H


def _v2(ir=None):
    return enrich_workflow(ir or H.procurement_ir(), compiler_version="test")


def test_valid_release():
    res = validate_compiled_release(_v2())
    assert res.state is ReleaseValidationState.VALID
    assert res.ok
    assert res.structural_ok and res.semantic_ok and res.authority_ok
    assert res.contract_ok and res.dependency_ok and res.provenance_ok and res.digest_ok


def test_unsupported_version_fails_closed():
    v2 = _v2().model_copy(update={"ir_version": "workflow_ir.v9"})
    res = validate_compiled_release(v2)
    assert res.state is ReleaseValidationState.UNSUPPORTED_VERSION
    assert not res.ok


def test_base_digest_mismatch_is_integrity_failure():
    v2 = _v2().model_copy(update={"base_ir_digest": "sha256:" + "0" * 64})
    res = validate_compiled_release(v2)
    assert res.state is ReleaseValidationState.INTEGRITY_FAILURE
    assert not res.digest_ok


def test_workflow_fingerprint_mismatch_is_integrity_failure():
    v2 = _v2().model_copy(update={"workflow_fingerprint": "sha256:" + "1" * 64})
    res = validate_compiled_release(v2)
    assert res.state is ReleaseValidationState.INTEGRITY_FAILURE


def test_missing_node_semantics_is_invalid():
    v2 = _v2()
    v2 = v2.model_copy(update={"node_semantics": v2.node_semantics[:-1]})
    # recompute fingerprint so the failure is semantic, not a digest mismatch
    v2 = v2.model_copy(update={"workflow_fingerprint": v2.logical_digest()})
    res = validate_compiled_release(v2)
    assert res.state is ReleaseValidationState.INVALID
    assert not res.semantic_ok
    assert any(d.code == ReleaseValidationCode.MISSING_NODE_SEMANTICS.value
               for d in res.diagnostics)


def test_authoritative_node_marked_agent_eligible_is_invalid_never_warning():
    from ugence_policy_workflow_compiler.semantics import RoleRelevance
    v2 = _v2()
    # tamper one authoritative node's semantics to claim agent-eligibility
    tampered = []
    changed = False
    by_id = {n.node_id: n for n in v2.base_ir.nodes}
    for s in v2.node_semantics:
        if not changed and by_id[s.node_id].disposition.value == "AUTHORITATIVE":
            s = s.model_copy(update={"role_relevance": RoleRelevance.ADVISORY_AGENT_ELIGIBLE})
            changed = True
        tampered.append(s)
    assert changed
    v2 = v2.model_copy(update={"node_semantics": tuple(tampered)})
    v2 = v2.model_copy(update={"workflow_fingerprint": v2.logical_digest()})
    res = validate_compiled_release(v2)
    assert res.state is ReleaseValidationState.INVALID  # authority failure => never a warning
    assert not res.authority_ok
    assert any(d.code == ReleaseValidationCode.AI_ELIGIBLE_ON_AUTHORITATIVE_NODE.value
               for d in res.diagnostics)


def test_validation_is_deterministic():
    a = validate_compiled_release(_v2())
    b = validate_compiled_release(_v2())
    assert a.state == b.state
    assert [d.code for d in a.diagnostics] == [d.code for d in b.diagnostics]


def test_upgrade_roundtrip_validates():
    v2 = _v2()
    from ugence_policy_workflow_compiler.semantics import upgrade_workflow_ir
    up = upgrade_workflow_ir(v2.base_ir, compiler_version="test")
    assert up.workflow_fingerprint == v2.workflow_fingerprint  # lossless
    assert validate_compiled_release(up).state is ReleaseValidationState.VALID
