"""Tests for the Hiring Policy Compiler (PWC) → HiringWorkflowIR → Decision Contract.

Covers spec §21 step 1: declarative policy authoring, deterministic signed
compilation, the six compile-time rejection checks, contract projection with
provenance + tamper detection, role weighting divergence, and the structural
guarantee that the Overall Fit Index never appears on the IR or contract.
"""

from __future__ import annotations

import pytest

from ugence_ai_hiring.hiring_policy import (
    ActionConstraints,
    ApproverAuthority,
    CompiledFrom,
    DeterministicHMACSigner,
    DimensionEmphasis,
    HiringDecisionContract,
    HiringPolicy,
    HiringPolicyCompiler,
    HiringWorkflowIR,
    MandatoryGateType,
    PolicyCompilationError,
    Requirements,
    RoleRef,
    project_contract,
)
from ugence_ai_hiring.hiring_policy.contract import ContractProjectionError
from ugence_ai_hiring.hiring_policy.enums import GateStatus


def make_policy(**overrides) -> HiringPolicy:
    base = dict(
        policy_id="pol-arch",
        role=RoleRef(job_definition_id="jd-arch", title="Senior Architect", seniority_level="L5"),
        requirements=Requirements(
            required_skills=("AWS", "Kubernetes", "Leadership"),
            mandatory=(MandatoryGateType.REQUIRED_SKILLS, MandatoryGateType.INTERVIEW_COMPLETED),
            operating_environment="HEALTHCARE",
            emphasis=(
                ("TECHNICAL", DimensionEmphasis.PRIMARY),
                ("LEADERSHIP", DimensionEmphasis.SECONDARY),
                ("DOMAIN", DimensionEmphasis.SUPPORTING),
            ),
        ),
        action_constraints=ActionConstraints(
            salary_ceiling=220000, approved_level="L5",
            approved_roles=("Senior Architect",), allowed_locations=("US-REMOTE", "NYC"),
        ),
        approval_chain=("Hiring Manager", "Director", "VP Eng"),
        authored_by="hr-jane",
    )
    base.update(overrides)
    return HiringPolicy(**base)


# --- happy path -----------------------------------------------------------
def test_compile_produces_signed_content_addressed_ir():
    ir = HiringPolicyCompiler().compile(make_policy())
    assert isinstance(ir, HiringWorkflowIR)
    assert ir.ir_version == "hiring_workflow_ir.v1"
    assert ir.content_digest and len(ir.content_digest) == 64  # sha-256 hex
    assert ir.signature.alg == "hmac-sha256"
    assert DeterministicHMACSigner().verify(ir.content_digest, ir.signature)
    assert ir.compiler.all_passed()


def test_dimension_weights_sum_to_one_and_exclude_role_sustainability():
    ir = HiringPolicyCompiler().compile(make_policy())
    assert abs(sum(ir.dimension_weights.values()) - 1.0) < 1e-9
    # ROLE_SUSTAINABILITY is a tracked dimension but carries no pre-hire weight
    assert "ROLE_SUSTAINABILITY_AND_ADAPTATION" in ir.dimensions
    assert "ROLE_SUSTAINABILITY_AND_ADAPTATION" not in ir.dimension_weights
    # PRIMARY outweighs SECONDARY outweighs SUPPORTING
    assert ir.dimension_weights["TECHNICAL"] > ir.dimension_weights["LEADERSHIP"]
    assert ir.dimension_weights["LEADERSHIP"] > ir.dimension_weights["DOMAIN"]


def test_operating_environment_dimension_auto_added():
    ir = HiringPolicyCompiler().compile(make_policy())
    assert "OPERATING_ENVIRONMENT_COMPATIBILITY" in ir.dimensions
    assert "OPERATING_ENVIRONMENT_COMPATIBILITY" in ir.dimension_weights


def test_mandatory_gates_are_definitions_defaulting_indeterminate():
    ir = HiringPolicyCompiler().compile(make_policy())
    types = {g.gate_type for g in ir.mandatory_gates}
    assert MandatoryGateType.REQUIRED_SKILLS in types
    assert all(g.status is GateStatus.INDETERMINATE for g in ir.mandatory_gates)
    # deterministic, policy-scoped gate ids (no random uuids)
    assert all(g.gate_id.startswith("gate-pol-arch-") for g in ir.mandatory_gates)


# --- reproducibility ------------------------------------------------------
def test_same_policy_yields_same_digest_and_signature():
    pwc = HiringPolicyCompiler()
    a = pwc.compile(make_policy())
    b = pwc.compile(make_policy())
    assert a.content_digest == b.content_digest
    assert a.signature.value == b.signature.value


def test_different_roles_diverge_in_weights_and_digest():
    arch = HiringPolicyCompiler().compile(make_policy())
    sales = HiringPolicyCompiler().compile(
        make_policy(
            policy_id="pol-sales",
            role=RoleRef(job_definition_id="jd-sales", title="Sales Exec", seniority_level="L4"),
            requirements=Requirements(
                mandatory=(MandatoryGateType.INTERVIEW_COMPLETED,),
                operating_environment="STARTUP",
                emphasis=(
                    ("BEHAVIOR", DimensionEmphasis.PRIMARY),
                    ("DOMAIN", DimensionEmphasis.SECONDARY),
                ),
            ),
            action_constraints=ActionConstraints(salary_ceiling=160000, approved_level="L4"),
            approval_chain=("Hiring Manager", "Director"),
        )
    )
    assert arch.content_digest != sales.content_digest
    assert arch.dimension_weights != sales.dimension_weights


# --- (a) OFI / forbidden dimensions --------------------------------------
@pytest.mark.parametrize("bad", ["CULTURE_FIT", "RESILIENCE"])
def test_forbidden_legacy_dimension_rejected(bad):
    policy = make_policy(
        requirements=Requirements(
            required_skills=("AWS",),
            mandatory=(MandatoryGateType.INTERVIEW_COMPLETED,),
            emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY), (bad, DimensionEmphasis.SECONDARY)),
        )
    )
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    assert any("(a)" in r and bad in r for r in ei.value.reasons)


def test_ofi_reference_in_dimension_rejected():
    policy = make_policy(
        requirements=Requirements(
            required_skills=("AWS",),
            mandatory=(MandatoryGateType.INTERVIEW_COMPLETED,),
            emphasis=(("OVERALL_FIT_INDEX", DimensionEmphasis.PRIMARY),),
        )
    )
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    assert any("Overall Fit Index" in r for r in ei.value.reasons)


# --- (b) non-compensatory gates ------------------------------------------
def test_mandatory_requirement_as_weighted_dimension_rejected():
    policy = make_policy(
        requirements=Requirements(
            required_skills=("AWS",),
            mandatory=(MandatoryGateType.REQUIRED_EXPERIENCE,),
            emphasis=(
                ("TECHNICAL", DimensionEmphasis.PRIMARY),
                ("REQUIRED_EXPERIENCE", DimensionEmphasis.SECONDARY),  # gate as a weighted dim
            ),
        )
    )
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    assert any("(b)" in r for r in ei.value.reasons)


# --- (d) human-only approval chain ---------------------------------------
@pytest.mark.parametrize("bad_approver", ["AI Review Bot", "svc-recruiter", "hiring-agent"])
def test_non_human_approver_rejected(bad_approver):
    policy = make_policy(approval_chain=("Hiring Manager", bad_approver))
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    assert any("(d)" in r for r in ei.value.reasons)


# --- (e) approver authority ----------------------------------------------
def test_action_constraints_beyond_approver_authority_rejected():
    # Hiring Manager alone cannot grant 900k / L9.
    policy = make_policy(
        action_constraints=ActionConstraints(salary_ceiling=900000, approved_level="L9"),
        approval_chain=("Hiring Manager",),
    )
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    assert any("(e)" in r for r in ei.value.reasons)


def test_authority_satisfied_by_senior_approver_in_chain():
    # VP Eng in the chain authorizes a high offer.
    policy = make_policy(
        action_constraints=ActionConstraints(salary_ceiling=380000, approved_level="L8"),
        approval_chain=("Hiring Manager", "VP Eng"),
    )
    ir = HiringPolicyCompiler().compile(policy)
    assert ir.compiler.action_constraints_within_approver_authority


def test_custom_authority_table():
    authority = ApproverAuthority({"Panel Lead": (500000.0, "L9")})
    policy = make_policy(
        action_constraints=ActionConstraints(salary_ceiling=450000, approved_level="L8"),
        approval_chain=("Panel Lead",),
    )
    ir = HiringPolicyCompiler(approver_authority=authority).compile(policy)
    assert ir.compiler.all_passed()


# --- aggregated reasons ---------------------------------------------------
def test_multiple_violations_reported_together():
    policy = make_policy(
        requirements=Requirements(
            required_skills=("AWS",),
            mandatory=(MandatoryGateType.INTERVIEW_COMPLETED,),
            emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY), ("CULTURE_FIT", DimensionEmphasis.SECONDARY)),
        ),
        action_constraints=ActionConstraints(salary_ceiling=900000, approved_level="L9"),
        approval_chain=("AI Bot",),
    )
    with pytest.raises(PolicyCompilationError) as ei:
        HiringPolicyCompiler().compile(policy)
    reasons = " ".join(ei.value.reasons)
    assert "(a)" in reasons and "(d)" in reasons and "(e)" in reasons


# --- runtime assurance derivation ----------------------------------------
def test_security_clearance_adds_background_check_assurance():
    policy = make_policy(
        requirements=Requirements(
            required_skills=("AWS",),
            mandatory=(MandatoryGateType.SECURITY_CLEARANCE, MandatoryGateType.INTERVIEW_COMPLETED),
            emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY),),
        )
    )
    ir = HiringPolicyCompiler().compile(policy)
    checks = {c.value for c in ir.runtime_assurance_checks}
    assert {"APPROVALS_VALID", "SALARY_POLICY_SATISFIED", "BACKGROUND_CHECK_CURRENT"} <= checks


# --- contract projection --------------------------------------------------
def test_project_contract_carries_provenance():
    ir = HiringPolicyCompiler().compile(make_policy())
    hdc = project_contract(ir, job_definition_id="jd-arch", signer=DeterministicHMACSigner())
    assert isinstance(hdc, HiringDecisionContract)
    assert isinstance(hdc.compiled_from, CompiledFrom)
    assert hdc.compiled_from.ir_digest == ir.content_digest
    assert hdc.compiled_from.ir_version == ir.ir_version
    assert hdc.action_constraints.salary_ceiling == 220000
    assert hdc.dimension_weights_ref.endswith("#dimension_weights")
    assert hdc.compiled is True


def test_project_contract_refuses_tampered_ir():
    ir = HiringPolicyCompiler().compile(make_policy())
    tampered = ir.model_copy(update={"content_digest": "0" * 64})
    with pytest.raises(ContractProjectionError):
        project_contract(tampered, job_definition_id="jd-arch")


def test_project_contract_refuses_bad_signature():
    ir = HiringPolicyCompiler().compile(make_policy())
    # a signer with a different key cannot verify the signature
    other = DeterministicHMACSigner(key_id="other", secret=b"different")
    with pytest.raises(ContractProjectionError):
        project_contract(ir, job_definition_id="jd-arch", signer=other)


# --- structural guarantee: OFI never on IR or contract -------------------
def test_overall_fit_index_absent_from_ir_and_contract():
    ir = HiringPolicyCompiler().compile(make_policy())
    hdc = project_contract(ir, job_definition_id="jd-arch")
    for field in ("overall_fit", "overall_fit_index", "ofi", "fit_score"):
        assert field not in ir.model_fields
        assert field not in hdc.model_fields
