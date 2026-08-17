#!/usr/bin/env python3
"""Reproducible proof that Agent Value Readiness installs and operates from a
built wheel, with ONLY the two neutral contract leaves and the shared Ugence
Policy Authority as cross-package dependencies, and NO ``governed-value`` or
other foreign package on the path.

Builds ``ugence-agent-value-readiness`` and its three dependencies
(``ugence-uvi-policy-contracts``, ``ugence-governance-contracts``,
``ugence-policy-authority``) into a local find-links directory, installs the
first (pip resolves the rest) into a fresh venv with no system site packages and
no monorepo path (``--no-index`` — all wheels are local, zero third-party deps),
then proves inside that env:

  * ``ugence_agent_value_readiness`` imports from site-packages, ships py.typed;
  * the curated API resolves;
  * representative readiness contracts construct, digest, and enforce structure
    (distinct indicator types; non-waivable mandatory condition; advisory-composite
    Decimal + float rejection; target/classification consistency; immutability);
  * the GV-3R-b evaluator selects the tier itself from a complete applicable gate
    set — mandatory FAIL dominates, an omitted gate is never PASS, the composite
    cannot move the tier, a naive evaluation time is rejected, evidence axes are
    preserved, and the result authorizes nothing;
  * the trusted orchestration boundary fails closed from the wheel — a policy
    issued and signed through the shared authority resolves and evaluates, while
    an unconfigured resolver or verifier denies, an unverified PASS cannot unlock
    readiness, an unverified condition cannot compensate, and no permissive
    verifier is present in the installed distribution;
  * M-3R.3 holds from the wheel — ``assess_readiness`` REQUIRES an exact
    ``AssessedSystemBinding`` (a missing one is ``NOT_EVALUATED``, never a
    headline), a cross-tenant binding fails closed, two configurations of one
    system cannot share a binding digest, binding a catalog creates NO
    requirement for any indicator family, catalog entry order is not
    digest-significant, the binding's authenticity is permanently
    ``STRUCTURAL_UNVERIFIED``, and policy-resolution failure still dominates
    every binding and catalog code;
  * the evaluator remains usable with NO orchestration configuration at all;
  * NO ``governed_value`` / capability / product / framework / third-party package
    is importable.

Run:  python packages/capabilities/agent-value-readiness/verify_agent_value_readiness_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[2]  # packages/capabilities/agent-value-readiness -> capabilities -> packages -> repo

SOURCES = {
    "ugence_agent_value_readiness": PKG,
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
}

_CHECK = r'''
import dataclasses, hashlib, importlib.util, sys
from datetime import datetime, timezone
from decimal import Decimal

import ugence_agent_value_readiness as r
assert r.__version__ == "0.4.1", r.__version__
assert "site-packages" in r.__file__, r.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
import pathlib as _pl
assert (_pl.Path(r.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"

from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod, AssessmentWindow
from ugence_uvi_policy_contracts.api import (
    PolicyArtifactMetadata, PolicyReference, PolicyFamily, PolicyLifecycleState,
    AssessmentContext, GeographyPolicy, DomainPolicy, IntendedOutcomePolicy,
    ReadinessPolicy, ReadinessTarget, RequirementClass, PolicyGate, GateCategory)
from ugence_agent_value_readiness.api import (
    IntelligenceFitnessResult, CapabilityReadinessResult, AdoptionReadinessResult,
    GateResult, GateStatus, ConditionSet, ConditionStatus, AdvisoryComposite,
    AgentValueReadinessDetermination, ReadinessClassification, ReadinessIndicatorClass,
    IntelligenceDimension, CapabilityDimension, AdoptionDimension, CapabilityDemonstration,
    ReadinessContractError,
    ReadinessEvaluationCase, ReadinessEvaluationError, ReadinessEvaluationResult,
    ReadinessRuleId, ReadinessReasonCode, ReadinessAdvisoryCode, evaluate_readiness)

D = hashlib.sha256(b"c").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc); T1 = datetime(2027, 1, 1, tzinfo=timezone.utc); MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
WIN = AssessmentWindow(start=T0, end=MID)
def meta(f, p): return PolicyArtifactMetadata(policy_id=p, policy_family=f, version="1", content_digest=D, lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1)
geo = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
dom = DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="ticket")
io = IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "i"), target_outcome="o", task_definition="t")
ctx = AssessmentContext.bind_policies(context_id="ctx1", tenant_id="t1", subject_id="a1", geography=geo, domain=dom, intended_outcome=io, as_of=MID)
rdy = PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D)
claim = MetricClaim(claim_id="c1", tenant_id="t1", subject_id="a1", metric_id="accuracy", value="0.95", governed_unit="ratio", source_basis=SourceBasis.OBSERVED, transformation_method=TransformationMethod.DIRECT, assessment_window=WIN)
intel = IntelligenceFitnessResult(result_id="ir1", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i", dimension=IntelligenceDimension.ACCURACY, claim=claim, requirement_class=RequirementClass.MANDATORY, applicable_targets=[ReadinessTarget.PILOT], status=GateStatus.PASS)
assert intel.indicator_class is ReadinessIndicatorClass.INTELLIGENCE
pgate = PolicyGate(gate_id="g1", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=(ReadinessTarget.PILOT,))
gate = GateResult(policy_gate=pgate, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PILOT, status=GateStatus.PASS)
assert gate.gate_id == "g1" and gate.gate_kind is RequirementClass.MANDATORY and gate.applicable is True
det = AgentValueReadinessDetermination(assessment_id="a1", tenant_id="t1", subject_id="a1", context=ctx, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY, created_at=MID, intelligence_results=[intel], gate_results=[gate])
assert len(det.canonical_digest()) == 64
assert det.is_advisory is True
assert det.blocking_gate_ids == ()  # derived from gate_results

# GV3R-F1: a ready classification cannot hide an applicable mandatory FAIL
_pg_fail = PolicyGate(gate_id="mf", category=GateCategory.SAFETY, requirement_class=RequirementClass.MANDATORY, applicability=(ReadinessTarget.PILOT,))
_gr_fail = GateResult(policy_gate=_pg_fail, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PILOT, status=GateStatus.FAIL)
try:
    AgentValueReadinessDetermination(assessment_id="a2", tenant_id="t1", subject_id="a1", context=ctx, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY, created_at=MID, gate_results=[_gr_fail])
    raise SystemExit("GV3R-F1 hidden-mandatory-FAIL guard did not fire")
except ReadinessContractError:
    pass

# non-waivable mandatory condition
try:
    ConditionSet(condition_id="c", source_gate_or_finding_ref="g", concern_requirement_class=RequirementClass.MANDATORY, current_status=ConditionStatus.PROPOSED)
    raise SystemExit("mandatory-condition guard did not fire")
except ReadinessContractError:
    pass
# composite rejects float
try:
    AdvisoryComposite(method_id="m", method_version="1", score=0.8, scale_min=Decimal("0"), scale_max=Decimal("1"), component_result_refs=["r1"])
    raise SystemExit("composite float guard did not fire")
except ReadinessContractError:
    pass
# target/classification consistency
try:
    AgentValueReadinessDetermination(assessment_id="a", tenant_id="t1", subject_id="a1", context=ctx, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PRODUCTION, classification=ReadinessClassification.PILOT_READY, created_at=MID)
    raise SystemExit("target/classification guard did not fire")
except ReadinessContractError:
    pass
# immutability: list coerced, mutation-proof
evid = ["e1"]
im = IntelligenceFitnessResult(result_id="ir2", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i", dimension=IntelligenceDimension.RELIABILITY, claim=claim, requirement_class=RequirementClass.ADVISORY, applicable_targets=[ReadinessTarget.PILOT], status=GateStatus.PASS, evidence_refs=evid)
d0 = im.canonical_digest(); evid.append("x")
assert im.evidence_refs == ("e1",) and im.canonical_digest() == d0
# no financial fields
for shape in (IntelligenceFitnessResult, CapabilityReadinessResult, AdoptionReadinessResult, GateResult, ConditionSet, AdvisoryComposite, AgentValueReadinessDetermination, ReadinessEvaluationCase, ReadinessEvaluationResult):
    for f in dataclasses.fields(shape):
        low = f.name.lower()
        assert not any(t in low for t in ("money", "currency", "roi", "benefit", "cost", "multiplier", "revenue")), (shape.__name__, f.name)

# ---- GV-3R-b: the deterministic determination evaluator ------------------- #
PROD = ReadinessTarget.PRODUCTION
def _rg(gid, kind, appl=(PROD,), comp=False):
    return PolicyGate(gate_id=gid, category=GateCategory.SAFETY, requirement_class=kind, applicability=appl, conditionally_compensable=comp)
rpol = ReadinessPolicy(metadata=meta(PolicyFamily.READINESS, "rp"), gates=(_rg("m1", RequirementClass.MANDATORY), _rg("m2", RequirementClass.MANDATORY)))
ctx2 = AssessmentContext.bind_policies(context_id="ctx2", tenant_id="t1", subject_id="a1", geography=geo, domain=dom, intended_outcome=io, readiness=rpol, as_of=MID)
_ind = dict(tenant_id="t1", subject_id="a1", context_id="ctx2", task_or_outcome_ref="task", requirement_class=RequirementClass.MANDATORY, applicable_targets=(PROD,), status=GateStatus.PASS)
i2 = IntelligenceFitnessResult(result_id="i2", dimension=IntelligenceDimension.ACCURACY, claim=claim, **_ind)
c2 = CapabilityReadinessResult(result_id="c2", dimension=CapabilityDimension.TOOL_READINESS, claim=claim, demonstration=CapabilityDemonstration.MET_THRESHOLD, evidence_sufficient=True, **_ind)
a2 = AdoptionReadinessResult(result_id="a2", dimension=AdoptionDimension.EXPECTED_UTILIZATION, claim=claim, **_ind)

def _case(statuses, composite=None):
    grs = tuple(GateResult(policy_gate={g.gate_id: g for g in rpol.gates}[gid], readiness_policy_ref=rpol.reference, requested_target=PROD, status=st) for gid, st in statuses)
    return ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=ctx2, readiness_policy=rpol, readiness_policy_ref=rpol.reference, requested_target=PROD, intelligence_results=(i2,), capability_results=(c2,), adoption_results=(a2,), gate_results=grs, advisory_composite=composite)

ALL_PASS = (("m1", GateStatus.PASS), ("m2", GateStatus.PASS))
ready = evaluate_readiness(_case(ALL_PASS), evaluation_time=MID)
assert ready.classification is ReadinessClassification.DEPLOYMENT_READY, ready.classification
assert ready.rule_id == ReadinessRuleId.DEPLOYMENT_READY.value
# the evaluator SELECTS the tier: the case has no classification field to supply
assert not any("classification" in f.name for f in dataclasses.fields(ReadinessEvaluationCase))
# mandatory FAIL dominates an unrelated INDETERMINATE
mixed = evaluate_readiness(_case((("m1", GateStatus.FAIL), ("m2", GateStatus.INDETERMINATE))), evaluation_time=MID)
assert mixed.classification is ReadinessClassification.NOT_READY and mixed.rule_id == ReadinessRuleId.MANDATORY_FAIL.value
# INDETERMINATE without FAIL is NOT_ASSESSABLE
ind = evaluate_readiness(_case((("m1", GateStatus.INDETERMINATE), ("m2", GateStatus.PASS))), evaluation_time=MID)
assert ind.classification is ReadinessClassification.NOT_ASSESSABLE
# an omitted applicable mandatory gate is NEVER treated as PASS
omitted = evaluate_readiness(_case((("m1", GateStatus.PASS),)), evaluation_time=MID)
assert omitted.classification is ReadinessClassification.NOT_ASSESSABLE, omitted.classification
assert omitted.trace.missing_required_gate_ids == ("m2",)
# the advisory composite cannot move the tier (min vs max, same gates)
def _comp(v): return AdvisoryComposite(method_id="m", method_version="1", score=Decimal(v), scale_min=Decimal("0"), scale_max=Decimal("100"), component_result_refs=("i2",))
lo = evaluate_readiness(_case((("m1", GateStatus.FAIL), ("m2", GateStatus.PASS)), _comp("0")), evaluation_time=MID)
hi = evaluate_readiness(_case((("m1", GateStatus.FAIL), ("m2", GateStatus.PASS)), _comp("100")), evaluation_time=MID)
assert lo.classification is hi.classification is ReadinessClassification.NOT_READY
assert lo.rule_id == hi.rule_id and lo.reason_codes == hi.reason_codes
# no system clock: a naive evaluation_time is refused
try:
    evaluate_readiness(_case(ALL_PASS), evaluation_time=datetime(2026, 6, 1))
    raise SystemExit("naive evaluation_time guard did not fire")
except ReadinessEvaluationError:
    pass
# determinism: input order never changes the outcome
rev = evaluate_readiness(_case(tuple(reversed(ALL_PASS))), evaluation_time=MID)
assert rev.canonical_digest() == ready.canonical_digest()
# evidence axes preserved; the result authorizes nothing
assert ready.determination.intelligence_results[0].claim is claim
assert ready.is_advisory is True and ready.authorizes_deployment is False
assert ReadinessAdvisoryCode.ADVISORY_ONLY_NOT_DEPLOYMENT_AUTHORIZATION.value in ready.advisory_codes
assert ReadinessAdvisoryCode.GATE_STATUS_STRUCTURALLY_SUPPLIED.value in ready.advisory_codes
# a gate borrowed from another ReadinessPolicy is rejected outright
try:
    ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=ctx2, readiness_policy=rpol, readiness_policy_ref=rpol.reference, requested_target=PROD, gate_results=(GateResult(policy_gate=rpol.gates[0], readiness_policy_ref=rdy, requested_target=PROD, status=GateStatus.PASS),))
    raise SystemExit("wrong-policy gate guard did not fire")
except ReadinessEvaluationError:
    pass

# ---- RA-01: readiness requirements are policy/gate-driven ----------------- #
# No indicator record of any family, complete + passing gate inventory: the tier
# is decided by the gates, not by bare indicator presence.
bare = ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=ctx2, readiness_policy=rpol, readiness_policy_ref=rpol.reference, requested_target=PROD, gate_results=tuple(GateResult(policy_gate={g.gate_id: g for g in rpol.gates}[gid], readiness_policy_ref=rpol.reference, requested_target=PROD, status=st) for gid, st in ALL_PASS))
bare_r = evaluate_readiness(bare, evaluation_time=MID)
assert bare_r.classification is ReadinessClassification.DEPLOYMENT_READY, bare_r.classification
assert not bare.intelligence_results and not bare.capability_results and not bare.adoption_results
# and no presence-based reason code survives anywhere in the vocabulary
assert not any(c.name.endswith("_RESULT_MISSING") and c.name != "APPLICABLE_GATE_RESULT_MISSING" for c in ReadinessReasonCode), [c.name for c in ReadinessReasonCode]
# omission of a *gate* still fails closed even with no indicators
bare_missing = ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=ctx2, readiness_policy=rpol, readiness_policy_ref=rpol.reference, requested_target=PROD, gate_results=(GateResult(policy_gate=rpol.gates[0], readiness_policy_ref=rpol.reference, requested_target=PROD, status=GateStatus.PASS),))
assert evaluate_readiness(bare_missing, evaluation_time=MID).classification is ReadinessClassification.NOT_ASSESSABLE

# ---- AUD-01: policy lifecycle + effective period are precondition row 0 --- #
def _policy(state=PolicyLifecycleState.APPROVED_ACTIVE, ef=T0, et=T1):
    m = PolicyArtifactMetadata(policy_id="rp2", policy_family=PolicyFamily.READINESS, version="1", content_digest=D, lifecycle_state=state, effective_from=ef, effective_to=et)
    return ReadinessPolicy(metadata=m, gates=(_rg("m1", RequirementClass.MANDATORY),))

def _eval_policy(pol, when):
    # direct context construction: the fail-closed binder refuses a non-active
    # policy outright, so this is the only way to represent the case at all.
    c = AssessmentContext(context_id="ctx3", tenant_id="t1", subject_id="a1", geography_ref=geo.reference, domain_ref=dom.reference, intended_outcome_ref=io.reference, readiness_ref=pol.reference)
    case_ = ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=c, readiness_policy=pol, readiness_policy_ref=pol.reference, requested_target=PROD, gate_results=(GateResult(policy_gate=pol.gates[0], readiness_policy_ref=pol.reference, requested_target=PROD, status=GateStatus.PASS),))
    return evaluate_readiness(case_, evaluation_time=when)

assert _eval_policy(_policy(), MID).classification is ReadinessClassification.DEPLOYMENT_READY
for _state in PolicyLifecycleState:
    if _state is PolicyLifecycleState.APPROVED_ACTIVE:
        continue
    _r = _eval_policy(_policy(state=_state), MID)
    assert _r.classification is ReadinessClassification.NOT_ASSESSABLE, (_state, _r.classification)
    assert _r.rule_id == ReadinessRuleId.POLICY_PRECONDITION.value
    assert ReadinessReasonCode.READINESS_POLICY_NOT_APPROVED_ACTIVE.value in _r.reason_codes
# half-open effective period: [effective_from, effective_to)
assert _eval_policy(_policy(), T0).classification is ReadinessClassification.DEPLOYMENT_READY
assert _eval_policy(_policy(), T1).classification is ReadinessClassification.NOT_ASSESSABLE
# an invalid governing policy dominates a mandatory FAIL and asserts no headline
_pol = _policy(state=PolicyLifecycleState.REVOKED)
_c3 = AssessmentContext(context_id="ctx3", tenant_id="t1", subject_id="a1", geography_ref=geo.reference, domain_ref=dom.reference, intended_outcome_ref=io.reference, readiness_ref=_pol.reference)
_fail_case = ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=_c3, readiness_policy=_pol, readiness_policy_ref=_pol.reference, requested_target=PROD, gate_results=(GateResult(policy_gate=_pol.gates[0], readiness_policy_ref=_pol.reference, requested_target=PROD, status=GateStatus.FAIL),))
_fr = evaluate_readiness(_fail_case, evaluation_time=MID)
assert _fr.classification is ReadinessClassification.NOT_ASSESSABLE, _fr.classification
assert _fr.determination.gate_results == () and _fr.determination.blocking_gate_ids == ()
assert _fr.trace.mandatory_failure_gate_ids == ("m1",)   # still reported diagnostically
assert _fr.trace.formula_version == "GV-3R-b.3", _fr.trace.formula_version

# context-to-policy BINDING is part of the same R0 precondition
def _eval_binding(readiness_ref, when=MID, status=GateStatus.PASS):
    _pol2 = _policy()
    _c = AssessmentContext(context_id="ctx4", tenant_id="t1", subject_id="a1", geography_ref=geo.reference, domain_ref=dom.reference, intended_outcome_ref=io.reference, readiness_ref=readiness_ref)
    _case = ReadinessEvaluationCase(case_id="cv", tenant_id="t1", subject_id="a1", context=_c, readiness_policy=_pol2, readiness_policy_ref=_pol2.reference, requested_target=PROD, gate_results=(GateResult(policy_gate=_pol2.gates[0], readiness_policy_ref=_pol2.reference, requested_target=PROD, status=status),))
    return evaluate_readiness(_case, evaluation_time=when)

# (a) no binding at all — even with every gate passing
_nb = _eval_binding(None)
assert _nb.classification is ReadinessClassification.NOT_ASSESSABLE, _nb.classification
assert _nb.rule_id == ReadinessRuleId.POLICY_PRECONDITION.value, _nb.rule_id
assert ReadinessReasonCode.READINESS_POLICY_NOT_BOUND_TO_CONTEXT.value in _nb.reason_codes
# (b) bound to a DIFFERENT policy — and a mandatory FAIL cannot override it
_mm = _eval_binding(PolicyReference(policy_id="other-rp", policy_family=PolicyFamily.READINESS, version="1", content_digest=D), status=GateStatus.FAIL)
assert _mm.classification is ReadinessClassification.NOT_ASSESSABLE, _mm.classification
assert _mm.rule_id == ReadinessRuleId.POLICY_PRECONDITION.value
assert ReadinessReasonCode.READINESS_POLICY_REF_CONTEXT_MISMATCH.value in _mm.reason_codes
assert _mm.determination.gate_results == () and _mm.determination.blocking_gate_ids == ()
assert _mm.trace.mandatory_failure_gate_ids == ("m1",)   # diagnostic only
# (c) correctly bound — normal gate precedence resumes
_ok = _eval_binding(_policy().reference, status=GateStatus.FAIL)
assert _ok.classification is ReadinessClassification.NOT_READY, _ok.classification
assert _ok.rule_id == ReadinessRuleId.MANDATORY_FAIL.value

# ---- Trusted Readiness Orchestration, from the wheel --------------------- #
from ugence_policy_authority.api import (
    ApprovalEvidenceRef, ApprovalVerification, ApprovalVerificationStatus, Ed25519PolicySigner,
    InMemoryPolicyRegistry, KeyEntitlement, PolicyKeyRing, PolicyResolutionStatus, SigningKey,
    UviPolicyFamilyAdapter, default_uvi_adapters, issue_policy)
from ugence_agent_value_readiness.api import (
    READINESS_ORCHESTRATOR_VERSION, ConditionSetVerification, DenyAllConditionSetVerifier,
    DenyAllGateResultVerifier, DenyAllReadinessPolicyResolver, GateResultVerification,
    PolicyAuthorityReadinessPolicyResolver, ReadinessAssessmentRequest, ReadinessAssessmentStatus,
    ReadinessInputVerificationStatus, ReadinessTrustAdvisoryState, ReadinessTrustGapCode,
    AdoptionReadinessCatalog, AdoptionReadinessIndicatorDefinition, AssessedSystemBinding,
    CapabilityReadinessCatalog, CapabilityReadinessIndicatorDefinition,
    IntelligenceFitnessCatalog, IntelligenceFitnessIndicatorDefinition,
    ReadinessIndicatorAdmissionStatus, ReadinessIndicatorCatalogSet,
    SYSTEM_BINDING_AUTHENTICITY_ADVISORY, SystemBindingAuthenticityStatus,
    assess_readiness)

assert READINESS_ORCHESTRATOR_VERSION == "ugence.readiness-orchestration/v0.2", READINESS_ORCHESTRATOR_VERSION
# Platform-neutral identity: the shipped wheel claims no ADR milestone.
for _tok in ("gv-3r", "gv3r", "m-3r", "m3r", "milestone"):
    assert _tok not in READINESS_ORCHESTRATOR_VERSION.lower(), _tok

_ADAPTER = UviPolicyFamilyAdapter()
def _digest_bound(gates, comp_gate=True):
    def _m(dig):
        return PolicyArtifactMetadata(policy_id="orch-rp", policy_family=PolicyFamily.READINESS, version="1", content_digest=dig, lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1)
    draft = ReadinessPolicy(metadata=_m("0" * 64), gates=gates)
    return ReadinessPolicy(metadata=_m(_ADAPTER.describe(draft).body_digest()), gates=gates)

_ogates = (_rg("m1", RequirementClass.MANDATORY), _rg("c1", RequirementClass.CONDITIONAL, comp=True))
opol = _digest_bound(_ogates)
octx = AssessmentContext(context_id="octx", tenant_id="t1", subject_id="a1", geography_ref=geo.reference, domain_ref=dom.reference, intended_outcome_ref=io.reference, readiness_ref=opol.reference)

class _Approval:
    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        return ApprovalVerification(verified=True, status=ApprovalVerificationStatus.APPROVED, coordinate=coordinate, policy_body_digest=policy_body_digest, approving_authority_id="board", approval_ref=approval.approval_ref, approval_digest=approval.approval_digest, verified_at=as_of)

_signer = Ed25519PolicySigner(authority_id="auth", key_id="k1", signing_key=SigningKey.from_seed(bytes([5]) * 32))
_registry = InMemoryPolicyRegistry(); _adapters = default_uvi_adapters()
issue_policy(policy=opol, record_id="orch-rec", approval=ApprovalEvidenceRef(approval_ref="A", approval_digest=hashlib.sha256(b"a").hexdigest(), approving_authority_id="board"), approval_verifier=_Approval(), signer=_signer, registry=_registry, adapters=_adapters, issued_at=T0)
_resolver = PolicyAuthorityReadinessPolicyResolver(registry=_registry, signature_verifier=PolicyKeyRing([_signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))]), adapters=_adapters)

class _V:
    def __init__(self, ok=True): self.ok = ok
    def _s(self): return ReadinessInputVerificationStatus.VERIFIED if self.ok else ReadinessInputVerificationStatus.EVIDENCE_NOT_VERIFIED
    def verify_gate_result(self, q):
        return GateResultVerification(status=self._s(), verifier_id="v", gate_id=q.gate_id, gate_digest=q.gate_digest, readiness_policy_ref=q.readiness_policy_ref, tenant_id=q.tenant_id, subject_id=q.subject_id, context_digest=q.context_digest, requested_target=q.requested_target, verified_at=q.evaluation_time, verified_status=q.claimed_status if self.ok else None, evidence_verified=self.ok, benchmark_resolved=self.ok, threshold_evaluation_verified=self.ok)
    def verify_condition(self, q):
        return ConditionSetVerification(status=self._s(), verifier_id="v", condition_id=q.condition_id, condition_digest=q.condition_digest, source_gate_or_finding_ref=q.source_gate_or_finding_ref, covered_gate_id=q.covered_gate_id, gate_digest=q.gate_digest, readiness_policy_ref=q.readiness_policy_ref, tenant_id=q.tenant_id, subject_id=q.subject_id, context_digest=q.context_digest, requested_target=q.requested_target, verified_at=q.evaluation_time, verified_status=q.claimed_status if self.ok else None, approval_authority_verified=self.ok, approval_evidence_verified=self.ok, owner_and_monitoring_verified=self.ok, effective_from=q.effective_from, effective_to=q.effective_to, expiry=q.expiry)

def _gr(gid, st):
    return GateResult(policy_gate={g.gate_id: g for g in opol.gates}[gid], readiness_policy_ref=opol.reference, requested_target=PROD, status=st)
# ---- M-3R.3: the assessed-system binding and the indicator catalogs ------- #
# There is exactly one orchestration path and it REQUIRES a binding, so every
# request below carries one. The binding is structural: it proves identity and
# digest consistency, never that the described system was really deployed.
_obinding = AssessedSystemBinding(
    binding_id="orch-binding", tenant_id="t1", subject_id="a1",
    context_id=octx.context_id, context_digest=octx.canonical_digest(),
    system_id="orch-system", system_version="1.0.0", configuration_id="orch-config",
    configuration_digest=hashlib.sha256(b"orch-configuration").hexdigest())
assert _obinding.authenticity_status is SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
assert _obinding.authenticity_verified is False
assert [m.value for m in SystemBindingAuthenticityStatus] == ["STRUCTURAL_UNVERIFIED"]

_ocatalogs = ReadinessIndicatorCatalogSet(
    intelligence=IntelligenceFitnessCatalog(
        catalog_id="wheel-int", catalog_version="1.0.0",
        entries=(IntelligenceFitnessIndicatorDefinition(
            indicator_id="ind-accuracy", dimension=IntelligenceDimension.ACCURACY,
            metric_id="accuracy"),)),
    capability=CapabilityReadinessCatalog(catalog_id="wheel-cap", catalog_version="1.0.0"),
    adoption=AdoptionReadinessCatalog(catalog_id="wheel-ado", catalog_version="1.0.0"))
# Catalog entry order is canonicalized, so it is not digest-significant.
assert IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1", entries=(
    IntelligenceFitnessIndicatorDefinition(indicator_id="b", dimension=IntelligenceDimension.ACCURACY, metric_id="m"),
    IntelligenceFitnessIndicatorDefinition(indicator_id="a", dimension=IntelligenceDimension.RELIABILITY, metric_id="m"),
)).indicator_ids == ("a", "b")

def _req(grs, conds=(), system_binding=_obinding, indicator_catalogs=None):
    return ReadinessAssessmentRequest(assessment_id="orch-1", tenant_id="t1", subject_id="a1", context=octx, readiness_policy_ref=opol.reference, requested_target=PROD, evaluation_time=MID, gate_results=tuple(grs), conditions=tuple(conds), system_binding=system_binding, indicator_catalogs=indicator_catalogs)

_all_pass = (_gr("m1", GateStatus.PASS), _gr("c1", GateStatus.PASS))
_ok = assess_readiness(_req(_all_pass), policy_resolver=_resolver, gate_verifier=_V(), condition_verifier=_V())
assert _ok.status is ReadinessAssessmentStatus.EVALUATED, _ok.status
assert _ok.classification is ReadinessClassification.DEPLOYMENT_READY, _ok.classification
assert _ok.trust_gap_codes == (), _ok.trust_gap_codes
assert _ok.is_advisory is True and _ok.authorizes_deployment is False
assert _ok.trace.evaluator_formula_version == "GV-3R-b.3"
assert _ok.trace.orchestrator_version == "ugence.readiness-orchestration/v0.2"
assert _ok.trace.issuance_record_ref == "orch-rec"
assert _ok.system_binding_accepted is True
assert _ok.system_binding_authenticity_verified is False
assert _ok.trace.system_binding_ref == "orch-binding"
assert _ok.trace.system_binding_digest == _obinding.canonical_digest()

# A missing binding is NOT_EVALUATED — never a headline readiness result.
_unbound = assess_readiness(_req(_all_pass, system_binding=None), policy_resolver=_resolver, gate_verifier=_V(), condition_verifier=_V())
assert _unbound.status is ReadinessAssessmentStatus.NOT_EVALUATED, _unbound.status
assert _unbound.classification is None and _unbound.evaluation is None
assert ReadinessTrustGapCode.SYSTEM_BINDING_REQUIRED.value in _unbound.trust_gap_codes
assert _unbound.trace.system_binding_ref == "" and _unbound.trace.system_binding_digest == ""

# Structural acceptance and authenticity stay separate on every outcome.
for _outcome in (_ok, _unbound):
    _auth = [d for d in _outcome.dispositions if d.advisory_code == SYSTEM_BINDING_AUTHENTICITY_ADVISORY]
    assert len(_auth) == 1, _auth
    assert _auth[0].state is ReadinessTrustAdvisoryState.OUT_OF_SCOPE

# Binding a catalog creates NO requirement: zero indicators still evaluates.
_catalogued = assess_readiness(_req(_all_pass, indicator_catalogs=_ocatalogs), policy_resolver=_resolver, gate_verifier=_V(), condition_verifier=_V())
assert _catalogued.classification is ReadinessClassification.DEPLOYMENT_READY, _catalogued.classification
assert _catalogued.trace.catalog_families_bound == ("INTELLIGENCE", "CAPABILITY", "ADOPTION")
assert _catalogued.indicator_admissions == ()
assert _catalogued.trust_gap_codes == (), _catalogued.trust_gap_codes

# A cross-tenant binding fails closed.
_cross = AssessedSystemBinding(binding_id="orch-binding", tenant_id="another-tenant", subject_id="a1", context_id=octx.context_id, context_digest=octx.canonical_digest(), system_id="orch-system", system_version="1.0.0", configuration_id="orch-config", configuration_digest=hashlib.sha256(b"orch-configuration").hexdigest())
_cross_out = assess_readiness(_req(_all_pass, system_binding=_cross), policy_resolver=_resolver, gate_verifier=_V(), condition_verifier=_V())
assert _cross_out.status is ReadinessAssessmentStatus.NOT_EVALUATED
assert ReadinessTrustGapCode.SYSTEM_BINDING_TENANT_MISMATCH.value in _cross_out.trust_gap_codes

# Two configurations of one system can never share a binding digest.
_cfg_b = AssessedSystemBinding(binding_id="orch-binding", tenant_id="t1", subject_id="a1", context_id=octx.context_id, context_digest=octx.canonical_digest(), system_id="orch-system", system_version="1.0.0", configuration_id="orch-config-b", configuration_digest=hashlib.sha256(b"orch-configuration-b").hexdigest())
assert _obinding.system_id == _cfg_b.system_id
assert _obinding.canonical_digest() != _cfg_b.canonical_digest()

# Policy-resolution failure dominates: no binding or catalog code appears.
_dominated = assess_readiness(_req(_all_pass, system_binding=None, indicator_catalogs=_ocatalogs))
assert _dominated.status is ReadinessAssessmentStatus.NOT_EVALUATED
assert ReadinessTrustGapCode.POLICY_RESOLVER_NOT_CONFIGURED.value in _dominated.trust_gap_codes
assert not any("SYSTEM_BINDING" in _c or "INDICATOR" in _c for _c in _dominated.trust_gap_codes)

# production defaults deny, and a denial asserts no headline at all
_denied = assess_readiness(_req(_all_pass))
assert _denied.status is ReadinessAssessmentStatus.NOT_EVALUATED
assert _denied.classification is None and _denied.evaluation is None
assert _denied.trace.issuance_record_ref == "" and _denied.trace.resolved_policy_digest == ""
assert ReadinessTrustGapCode.POLICY_RESOLVER_NOT_CONFIGURED.value in _denied.trust_gap_codes

# an unverified PASS cannot unlock readiness; an unverified FAIL cannot force NOT_READY
_unverified = assess_readiness(_req(_all_pass), policy_resolver=_resolver, gate_verifier=_V(ok=False))
assert _unverified.classification is ReadinessClassification.NOT_ASSESSABLE, _unverified.classification
_unverified_fail = assess_readiness(_req((_gr("m1", GateStatus.FAIL), _gr("c1", GateStatus.PASS))), policy_resolver=_resolver, gate_verifier=_V(ok=False))
assert _unverified_fail.classification is ReadinessClassification.NOT_ASSESSABLE

# a verified mandatory FAIL still dominates
_fail = assess_readiness(_req((_gr("m1", GateStatus.FAIL), _gr("c1", GateStatus.PASS))), policy_resolver=_resolver, gate_verifier=_V())
assert _fail.classification is ReadinessClassification.NOT_READY, _fail.classification

# an unverified condition cannot compensate; a verified one compensates its exact concern
_cond = ConditionSet(condition_id="cd1", source_gate_or_finding_ref="c1", concern_requirement_class=RequirementClass.CONDITIONAL, current_status=ConditionStatus.APPROVED_ACTIVE, approved_mitigation_ref="m", approving_authority_ref="a", accountable_owner="o", scope_exposure_limit="10%", monitoring_requirement="weekly", evidence_refs=("ev",), revocation_trigger="breach", effective_from=T0)
_unresolved = (_gr("m1", GateStatus.PASS), _gr("c1", GateStatus.FAIL))
_no_cover = assess_readiness(_req(_unresolved, (_cond,)), policy_resolver=_resolver, gate_verifier=_V())
assert _no_cover.classification is ReadinessClassification.NOT_READY, _no_cover.classification
_covered = assess_readiness(_req(_unresolved, (_cond,)), policy_resolver=_resolver, gate_verifier=_V(), condition_verifier=_V())
assert _covered.classification is ReadinessClassification.READY_WITH_CONDITIONS, _covered.classification

# trust advisories are reconciled, never deleted
_states = {d.advisory_code: d.state for d in _covered.dispositions}
assert set(_covered.evaluation.advisory_codes) <= set(_states)
assert ReadinessTrustAdvisoryState.RESOLVED_BY_POLICY_RESOLUTION in _states.values()
assert ReadinessTrustAdvisoryState.RESOLVED_BY_CONDITION_VERIFICATION in _states.values()

# the deny-all defaults really deny, and carry no permissive switch
assert DenyAllReadinessPolicyResolver().resolve_readiness_policy(reference=opol.reference, expected_tenant_id="", as_of=MID).status is PolicyResolutionStatus.UNRESOLVED
import inspect as _inspect
for _cls in (DenyAllGateResultVerifier, DenyAllConditionSetVerifier):
    assert list(_inspect.signature(_cls).parameters) == [], _cls

# no permissive verifier ships in the INSTALLED distribution
import ast as _ast, pathlib as _pathlib
_root = _pathlib.Path(r.__file__).resolve().parent
_tokens = ("allowall", "allow_all", "acceptall", "accept_all", "trustall", "trust_all", "alwaysvalid", "always_valid", "fakeverifier", "testverifier", "stubverifier", "insecure", "bypass")
for _p in _root.rglob("*.py"):
    for _n in _ast.walk(_ast.parse(_p.read_text())):
        if isinstance(_n, (_ast.ClassDef, _ast.FunctionDef)):
            assert not any(t in _n.name.lower() for t in _tokens), (_p.name, _n.name)

# the evaluator remains usable with NO orchestration configuration whatsoever
assert evaluate_readiness(_case(ALL_PASS), evaluation_time=MID).classification is ReadinessClassification.DEPLOYMENT_READY

for mod in ("governed_value", "ugence_governed_value", "governance_providers", "decision_governance", "ai_hiring", "pydantic"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED AGENT-VALUE-READINESS VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_agent_value_readiness" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the readiness wheel + its contract leaves and the shared authority")
    for name, src in SOURCES.items():
        # A stale ``build/lib`` tree from an earlier build silently resurrects
        # deleted modules into the wheel — which is exactly how a duplicate
        # ``AssessedSystemBinding`` implementation could ship after the ADR §20
        # move. Remove it so every wheel is built from the source tree alone.
        shutil.rmtree(src / "build", ignore_errors=True)
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_agent_value_readiness-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_agent_value_readiness/py.typed" in names, "wheel is missing py.typed"
    for banned in ("test", "fixture", "conftest", "probe", "adversarial"):
        offenders = [n for n in names if banned in n.lower()]
        assert not offenders, f"wheel ships {banned} artifacts: {sorted(offenders)[:5]}"

    # ADR §20: the assessed-system binding is owned by governance-contracts.
    # The readiness wheel must contain NO definition of it — not a module, not a
    # copy, not a subclass. A stale build tree is the realistic way this
    # regresses, so it is asserted against the built artifact itself.
    assert "ugence_agent_value_readiness/contracts/binding.py" not in names, (
        "the readiness wheel still ships the pre-move binding module"
    )
    for member in names:
        if not member.endswith(".py"):
            continue
        with zipfile.ZipFile(wheel) as z:
            source = z.read(member).decode("utf-8")
        assert "class AssessedSystemBinding" not in source, (
            f"the readiness wheel defines AssessedSystemBinding in {member}"
        )
        assert "class SystemBindingAuthenticityStatus" not in source, (
            f"the readiness wheel defines SystemBindingAuthenticityStatus in {member}"
        )

    governance_wheel = _latest(findlinks, "ugence_governance_contracts-*.whl")
    with zipfile.ZipFile(governance_wheel) as z:
        governance_names = set(z.namelist())
    assert "ugence_governance_contracts/contracts/system_identity.py" in governance_names, (
        "the governance wheel does not ship the assessed-system identity contract"
    )
    print("      wheel contains only ugence_agent_value_readiness/ (+ py.typed) + dist-info")
    print("      and defines NO AssessedSystemBinding — it lives in the governance wheel")

    print("[3/4] create an isolated venv and install ONLY these local wheels (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-agent-value-readiness"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED AGENT-VALUE-READINESS DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
