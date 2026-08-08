"""The Hiring Policy Compiler (PWC).

Compiles a declarative :class:`~ugence_ai_hiring.hiring_policy.policy.HiringPolicy`
into a signed, content-addressed :class:`HiringWorkflowIR`. Derivation is
deterministic: the same policy always yields the same content digest (the
digest excludes the volatile ``compiled_at`` timestamp).

Compile-time rejections (the invariants; a policy failing any is rejected with
all reasons at once):

  (a) no OFI reference in policy / no forbidden legacy dimension
  (b) mandatory requirements are gates, never weighted (compensable) dimensions
  (c) every weighted dimension declares required evidence
  (d) the approval chain is human-only
  (e) declared action constraints are within some approver's authority
  (f) constrained actions carry the required runtime-assurance checks
"""

from __future__ import annotations

from typing import Optional

from .authority import ApproverAuthority
from .enums import (
    DIM_ROLE_SUSTAINABILITY,
    DIM_TECHNICAL,
    DIM_OPERATING_ENVIRONMENT,
    DimensionEmphasis,
    FORBIDDEN_DIMENSIONS,
    HiringEvidenceClass,
    MandatoryGateType,
    NON_HUMAN_APPROVER_TOKENS,
    RuntimeAssuranceCheck,
)
from .errors import PolicyCompilationError
from .policy import HiringPolicy
from .signing import DeterministicHMACSigner, Signer
from .workflow_ir import (
    Approver,
    CompilerProvenance,
    GatePredicate,
    HiringWorkflowIR,
    IRActionConstraints,
    MandatoryGate,
    compute_content_digest_from_parts,
)

PWC_VERSION = "pwc-hiring-1.0.0"

_OFI_TOKENS = ("OFI", "OVERALL_FIT", "OVERALLFIT", "FIT_INDEX")

# Default per-dimension admissible evidence (kept non-empty so every weighted
# dimension satisfies check (c)).
_EVIDENCE_BY_DIMENSION: dict[str, tuple[HiringEvidenceClass, ...]] = {
    DIM_TECHNICAL: (HiringEvidenceClass.CODING_ASSESSMENT, HiringEvidenceClass.PORTFOLIO),
    "LEADERSHIP": (HiringEvidenceClass.REFERENCE_CHECK, HiringEvidenceClass.INTERVIEW),
    "DOMAIN": (HiringEvidenceClass.EMPLOYMENT_HISTORY, HiringEvidenceClass.CERTIFICATION),
    "BEHAVIOR": (HiringEvidenceClass.INTERVIEW,),
    "LEARNING": (HiringEvidenceClass.INTERVIEW,),
    DIM_OPERATING_ENVIRONMENT: (HiringEvidenceClass.INTERVIEW, HiringEvidenceClass.REFERENCE_CHECK),
}
_EVIDENCE_DEFAULT: tuple[HiringEvidenceClass, ...] = (HiringEvidenceClass.INTERVIEW,)

_GATE_SPEC: dict[MandatoryGateType, tuple[str, tuple[HiringEvidenceClass, ...]]] = {
    MandatoryGateType.REQUIRED_SKILLS: (
        "has_all(required_skills)",
        (HiringEvidenceClass.RESUME, HiringEvidenceClass.CODING_ASSESSMENT, HiringEvidenceClass.PORTFOLIO),
    ),
    MandatoryGateType.REQUIRED_CERTIFICATIONS: (
        "has_all(required_certifications)",
        (HiringEvidenceClass.CERTIFICATION,),
    ),
    MandatoryGateType.WORK_AUTHORIZATION: (
        "authorized_to_work == true",
        (HiringEvidenceClass.BACKGROUND_CHECK,),
    ),
    MandatoryGateType.SECURITY_CLEARANCE: (
        "clearance_active == true",
        (HiringEvidenceClass.BACKGROUND_CHECK,),
    ),
    MandatoryGateType.INTERVIEW_COMPLETED: (
        "interview.completed == true",
        (HiringEvidenceClass.INTERVIEW,),
    ),
    MandatoryGateType.ASSESSMENT_COMPLETED: (
        "assessment.completed == true",
        (HiringEvidenceClass.CODING_ASSESSMENT,),
    ),
    MandatoryGateType.REQUIRED_EXPERIENCE: (
        "years_experience >= required_experience",
        (HiringEvidenceClass.EMPLOYMENT_HISTORY, HiringEvidenceClass.RESUME),
    ),
}

_DEFAULT_CONFIDENCE_FLOOR = 0.6


class HiringPolicyCompiler:
    """Compiles a Hiring Policy into a signed HiringWorkflowIR."""

    def __init__(
        self,
        *,
        signer: Optional[Signer] = None,
        approver_authority: Optional[ApproverAuthority] = None,
        pwc_version: str = PWC_VERSION,
    ) -> None:
        self._signer: Signer = signer or DeterministicHMACSigner()
        self._authority = approver_authority or ApproverAuthority()
        self._pwc_version = pwc_version

    # -- public API --------------------------------------------------------
    def compile(self, policy: HiringPolicy) -> HiringWorkflowIR:
        """Compile ``policy`` or raise :class:`PolicyCompilationError` with every reason."""
        reasons: list[str] = []
        emphasis = policy.requirements.emphasis_map()

        # (a) no OFI reference / no forbidden legacy dimension
        ofi_ok = self._check_no_ofi(policy, emphasis, reasons)

        # derive dimensions + weights (needed by later checks)
        dimensions, weights = self._derive_dimensions(policy, emphasis, reasons)

        # (b) mandatory requirements are gates, not weighted dimensions
        gates_ok = self._check_gates_non_compensatory(policy, weights, reasons)
        gates = self._build_gates(policy)

        # (c) every weighted dimension declares required evidence
        evidence_requirements = self._build_evidence_requirements(weights)
        evidence_ok = self._check_weighted_have_evidence(weights, evidence_requirements, reasons)

        confidence_thresholds = {dim: _DEFAULT_CONFIDENCE_FLOOR for dim in weights}

        # (d) approval chain is human-only
        approvers, human_ok = self._build_approval_chain(policy, reasons)

        action = IRActionConstraints(
            salary_ceiling=policy.action_constraints.salary_ceiling,
            salary_currency=policy.action_constraints.salary_currency,
            approved_level=policy.action_constraints.approved_level,
            approved_roles=policy.action_constraints.approved_roles,
            allowed_locations=policy.action_constraints.allowed_locations,
        )

        # (e) action constraints within some approver's authority
        authority_ok = self._check_authority(policy, reasons)

        # (f) constrained actions carry the required assurance checks
        assurance = self._derive_assurance_checks(gates, evidence_requirements)
        assurance_ok = self._check_assurance(action, assurance, reasons)

        if reasons:
            raise PolicyCompilationError(reasons)

        provenance = CompilerProvenance(
            pwc_version=self._pwc_version,
            no_ofi_in_policy=ofi_ok,
            gates_non_compensatory=gates_ok,
            weighted_dimensions_have_required_evidence=evidence_ok,
            approval_chain_human_only=human_ok,
            action_constraints_within_approver_authority=authority_ok,
            constrained_actions_have_assurance_checks=assurance_ok,
        )

        digest = compute_content_digest_from_parts(
            source_policy_id=policy.policy_id,
            dimensions=dimensions,
            dimension_weights=weights,
            mandatory_gates=gates,
            evidence_requirements=evidence_requirements,
            confidence_thresholds=confidence_thresholds,
            action_constraints=action,
            runtime_assurance_checks=assurance,
            approval_chain=approvers,
            review_schedule_months=policy.review_schedule_months,
        )
        signature = self._signer.sign(digest)

        return HiringWorkflowIR(
            source_policy_id=policy.policy_id,
            content_digest=digest,
            signature=signature,
            dimensions=dimensions,
            dimension_weights=weights,
            mandatory_gates=gates,
            evidence_requirements=evidence_requirements,
            confidence_thresholds=confidence_thresholds,
            action_constraints=action,
            runtime_assurance_checks=assurance,
            approval_chain=approvers,
            review_schedule_months=policy.review_schedule_months,
            compiler=provenance,
        )

    # -- checks & derivation ----------------------------------------------
    def _check_no_ofi(
        self, policy: HiringPolicy, emphasis: dict[str, DimensionEmphasis], reasons: list[str]
    ) -> bool:
        ok = True
        for dim in emphasis:
            if dim in FORBIDDEN_DIMENSIONS:
                replacement = (
                    DIM_OPERATING_ENVIRONMENT if dim == "CULTURE_FIT" else DIM_ROLE_SUSTAINABILITY
                )
                reasons.append(
                    f"(a) forbidden legacy dimension {dim!r}; use {replacement!r} instead"
                )
                ok = False
            if any(tok in dim for tok in _OFI_TOKENS):
                reasons.append(
                    f"(a) dimension {dim!r} references the Overall Fit Index, which is "
                    f"analytics-only and must never enter policy"
                )
                ok = False
        return ok

    def _derive_dimensions(
        self,
        policy: HiringPolicy,
        emphasis: dict[str, DimensionEmphasis],
        reasons: list[str],
    ) -> tuple[tuple[str, ...], dict[str, float]]:
        emphasis = dict(emphasis)  # copy; may augment
        # auto-add operating-environment dimension when the environment is declared
        if policy.requirements.operating_environment and DIM_OPERATING_ENVIRONMENT not in emphasis:
            emphasis[DIM_OPERATING_ENVIRONMENT] = DimensionEmphasis.SUPPORTING
        # fall back to a TECHNICAL primary when nothing else is declared but skills are
        if not emphasis and policy.requirements.required_skills:
            emphasis[DIM_TECHNICAL] = DimensionEmphasis.PRIMARY

        # weighted dimensions exclude ROLE_SUSTAINABILITY (post-hire, 0 pre-hire weight)
        weighted = {d: e for d, e in emphasis.items() if d != DIM_ROLE_SUSTAINABILITY}
        if not weighted:
            reasons.append(
                "(a) cannot derive any weighted dimension; declare emphasis or required_skills"
            )
            # ROLE_SUSTAINABILITY is always tracked as a dimension
            dims = (DIM_ROLE_SUSTAINABILITY,) if DIM_ROLE_SUSTAINABILITY in emphasis else ()
            return dims, {}

        total_points = sum(e.weight_points for e in weighted.values())
        raw = {d: e.weight_points / total_points for d, e in weighted.items()}
        weights = _normalize_to_one(raw)

        # dimensions = weighted dims (sorted) + ROLE_SUSTAINABILITY tracked last
        dims_list = sorted(weights.keys())
        dims_list.append(DIM_ROLE_SUSTAINABILITY)
        return tuple(dims_list), weights

    def _check_gates_non_compensatory(
        self, policy: HiringPolicy, weights: dict[str, float], reasons: list[str]
    ) -> bool:
        # A mandatory requirement must be a gate, never a weighted (compensable)
        # dimension. Reject if a gate type also appears as a weighted dimension name.
        ok = True
        gate_names = {g.value for g in policy.requirements.mandatory}
        for dim in weights:
            if dim in gate_names:
                reasons.append(
                    f"(b) {dim!r} is a mandatory requirement and cannot also be a weighted "
                    f"(compensable) dimension"
                )
                ok = False
        return ok

    def _build_gates(self, policy: HiringPolicy) -> tuple[MandatoryGate, ...]:
        gates: list[MandatoryGate] = []
        seen: set[MandatoryGateType] = set()
        for gate_type in policy.requirements.mandatory:
            if gate_type in seen:
                continue
            seen.add(gate_type)
            expression, evidence = _GATE_SPEC[gate_type]
            gates.append(
                MandatoryGate(
                    gate_id=f"gate-{policy.policy_id}-{gate_type.value}",
                    gate_type=gate_type,
                    predicate=GatePredicate(expression=expression, evidence_types=evidence),
                )
            )
        return tuple(gates)

    def _build_evidence_requirements(
        self, weights: dict[str, float]
    ) -> dict[str, tuple[HiringEvidenceClass, ...]]:
        return {
            dim: _EVIDENCE_BY_DIMENSION.get(dim, _EVIDENCE_DEFAULT) for dim in weights
        }

    def _check_weighted_have_evidence(
        self,
        weights: dict[str, float],
        evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]],
        reasons: list[str],
    ) -> bool:
        ok = True
        for dim in weights:
            if not evidence_requirements.get(dim):
                reasons.append(f"(c) weighted dimension {dim!r} has no required evidence")
                ok = False
        return ok

    def _build_approval_chain(
        self, policy: HiringPolicy, reasons: list[str]
    ) -> tuple[tuple[Approver, ...], bool]:
        approvers: list[Approver] = []
        ok = True
        for role in policy.approval_chain:
            lowered = role.lower()
            if any(tok in lowered.split() or tok in lowered.replace("-", " ").split() for tok in NON_HUMAN_APPROVER_TOKENS):
                reasons.append(
                    f"(d) approval-chain entry {role!r} appears to be a non-human principal; "
                    f"only humans may bind"
                )
                ok = False
                continue
            approvers.append(Approver(approver_role=role))
        return tuple(approvers), ok

    def _check_authority(self, policy: HiringPolicy, reasons: list[str]) -> bool:
        salary = policy.action_constraints.salary_ceiling
        level = policy.action_constraints.approved_level
        if not self._authority.chain_authorizes(policy.approval_chain, salary=salary, level=level):
            reasons.append(
                f"(e) no approver in {list(policy.approval_chain)} is authorized to grant "
                f"salary {salary:g} at level {level!r}"
            )
            return False
        return True

    def _derive_assurance_checks(
        self,
        gates: tuple[MandatoryGate, ...],
        evidence_requirements: dict[str, tuple[HiringEvidenceClass, ...]],
    ) -> tuple[RuntimeAssuranceCheck, ...]:
        selected: set[RuntimeAssuranceCheck] = {
            RuntimeAssuranceCheck.APPROVALS_VALID,
            RuntimeAssuranceCheck.REQUISITION_OPEN,
            RuntimeAssuranceCheck.OFFER_NOT_EXPIRED,
            RuntimeAssuranceCheck.SALARY_POLICY_SATISFIED,
        }
        gate_types = {g.gate_type for g in gates}
        if gate_types & {MandatoryGateType.SECURITY_CLEARANCE, MandatoryGateType.WORK_AUTHORIZATION}:
            selected.add(RuntimeAssuranceCheck.BACKGROUND_CHECK_CURRENT)
        if any(
            HiringEvidenceClass.REFERENCE_CHECK in types for types in evidence_requirements.values()
        ):
            selected.add(RuntimeAssuranceCheck.REFERENCES_COMPLETE)
        # stable order = enum declaration order
        return tuple(c for c in RuntimeAssuranceCheck if c in selected)

    def _check_assurance(
        self,
        action: IRActionConstraints,
        assurance: tuple[RuntimeAssuranceCheck, ...],
        reasons: list[str],
    ) -> bool:
        # salary is always constrained (salary_ceiling is required), so both
        # APPROVALS_VALID and SALARY_POLICY_SATISFIED must be present.
        ok = True
        required = {RuntimeAssuranceCheck.APPROVALS_VALID, RuntimeAssuranceCheck.SALARY_POLICY_SATISFIED}
        missing = required - set(assurance)
        if missing:
            names = ", ".join(sorted(m.value for m in missing))
            reasons.append(f"(f) constrained action is missing runtime-assurance checks: {names}")
            ok = False
        return ok


def _normalize_to_one(raw: dict[str, float]) -> dict[str, float]:
    """Round weights to 9 dp and absorb rounding drift into the largest weight so
    the total is exactly 1.0."""
    rounded = {k: round(v, 9) for k, v in raw.items()}
    drift = round(1.0 - sum(rounded.values()), 9)
    if drift and rounded:
        top = max(rounded, key=lambda k: (rounded[k], k))
        rounded[top] = round(rounded[top] + drift, 9)
    return rounded
