#!/usr/bin/env python3
"""Reproducible proof that Risk Authority installs and operates as a single,
self-contained leaf wheel with NO other Ugence package (and no third-party
dependency) on the path.

Builds ``ugence-risk-authority`` only, installs it into a fresh virtualenv with
no system site packages and no monorepo path (``--no-index`` — the package
declares zero third-party runtime dependencies), then proves inside that env:

  * ``risk_authority`` imports from site-packages and ships ``py.typed``;
  * pure-Python Ed25519 matches an RFC 8032 vector (no crypto dependency);
  * the RA-1..RA-4 authority spine runs end-to-end (issue -> verify -> ALLOW);
  * an off-scope action is denied;
  * NO capability / framework / product / crypto package is importable.

Run:  python packages/risk_authority/verify_risk_authority_distribution.py
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

_CHECK = r'''
import importlib.util, sys
from datetime import datetime, timezone

import risk_authority as ra
assert ra.__version__ == "0.6.0", ra.__version__
assert "site-packages" in ra.__file__, ra.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(ra.__file__).resolve().parent / "py.typed").is_file(), "py.typed missing"

# Pure-Python Ed25519 correctness (RFC 8032 TEST 2) — no third-party crypto.
from risk_authority.crypto.signing import SigningKey
seed = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
assert SigningKey.from_seed(seed).sign(bytes.fromhex("72")).hex().startswith("92a009a9")

# No third-party / unrelated Ugence package in this clean env.
for mod in ("pydantic", "cryptography", "nacl", "fastapi", "governance_providers",
            "ugence_actiongate_provider", "ugence_decision_authority", "platform_freeze"):
    assert importlib.util.find_spec(mod) is None, ("unexpected package present: " + mod)

# RA-1..RA-4 authority spine, end to end.
from risk_authority.api import (RiskAuthorityApplication, CreateCaseRequest, EvaluateRequest,
    ControlResultInput, DecisionRequest, IssueEnvelopeRequest, AuthorizeActionRequest)
from risk_authority.crypto import SigningKeyRecord
from risk_authority.domain import (AuthorityGrant, AuthorityType, RiskClass, RuleEffect,
    Scope, WorkflowIR, WorkflowRule, WorkflowStatus, Predicate, PredicateOp, ActionGateDecision)
from risk_authority.integrations import InMemoryWorkflowIRSource

now = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
scope = Scope(purposes=("CUSTOMER_REFUND_REVIEW",), tools_allow=("crm.read", "refund.prepare"),
    tools_deny=("refund.execute", "email.external"), data_allow=("CUSTOMER_PII",),
    destinations=("internal://finance",), models=("model_xyz",), actors=("agent_finance_07",),
    max_autonomy_level=2, max_transaction_minor_units=500000)
wf = WorkflowIR(workflow_ir_id="finance-ai-risk", version="4.1.0", status=WorkflowStatus.ACTIVE,
    rules=(WorkflowRule(rule_id="FIN-12",
        conditions=(Predicate("risk_class", PredicateOp.IN, ["HIGH", "CRITICAL"]),),
        required_controls=("MODEL_PROVENANCE_VALID",), effect=RuleEffect.DENY_UNLESS_ALL),),
    source_refs=("CORP-AI-04",), effective_at=now).with_digest()
src = InMemoryWorkflowIRSource(); src.register(wf)
key = SigningKeyRecord("risk-key-2026-08", SigningKey.from_seed(bytes(range(32))))
app = RiskAuthorityApplication(workflow_source=src, key_record=key, clock=lambda: now)
app.authority.add_grant(AuthorityGrant(principal_id="risk-office-prod", tenant_id="t",
    authority_type=AuthorityType.RISK_APPROVAL, domains=("FINANCE",),
    allowed_risk_classes=(RiskClass.HIGH,), max_autonomy=2, delegated_by="ero", grantable_scope=scope))
app.create_case(CreateCaseRequest(tenant_id="t", case_id="rdc_1", subject_id="agent_finance_07",
    model_id="model_xyz", purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
    tools=("crm.read", "refund.prepare"), autonomy_level=2, data_classes=("CUSTOMER_PII",),
    workflow_ir_id="finance-ai-risk", inherent_risk=RiskClass.HIGH, residual_risk=RiskClass.MEDIUM))
ev = app.evaluate("t", "rdc_1", EvaluateRequest(
    control_results=(ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),)))
dec = app.issue_decision("t", "rdc_1", ev, DecisionRequest(principal_id="risk-office-prod", requested_scope=scope))
env = app.issue_envelope("t", "rdc_1", IssueEnvelopeRequest(decision_id=dec.decision_id,
    audience="rt", session_id="s", nonce="n"))
assert app.verify_envelope("t", env.envelope_id).valid

def go(**kw):
    base = dict(envelope_id=env.envelope_id, tenant_id="t", actor_id="agent_finance_07",
        model_id="model_xyz", session_id="s", target_id="txn", purpose="CUSTOMER_REFUND_REVIEW",
        destination="internal://finance")
    base.update(kw)
    return app.authorize_action(AuthorizeActionRequest(**base)).decision

assert go(action_type="crm.read") is ActionGateDecision.AUTHORIZED
assert go(action_type="refund.execute") is ActionGateDecision.DENIED

# --- PR-1: stop-at-decision evaluation seam, from the installed wheel ----------------
from risk_authority.api import RiskEvaluationSeam, SeamConfigurationError
from risk_authority.integrations import (SubjectRiskEvaluationRequest, SubjectRiskDecision,
    SubjectRiskDisposition, SubjectRiskNonDecisionReason, ReferencePolicyResolver,
    ReferenceControlEvidenceResolver)
from risk_authority.services.decision_authority import ReferenceDecisionAuthority

sscope = Scope(purposes=("SCALE",), max_autonomy_level=1)
swf = WorkflowIR(workflow_ir_id="scaling-pol", version="1.0.0", status=WorkflowStatus.ACTIVE,
    rules=(), source_refs=(), effective_at=now).with_digest()
ssrc = InMemoryWorkflowIRSource(); ssrc.register(swf)
seam = RiskEvaluationSeam.reference(workflow_source=ssrc, key_record=key, clock=lambda: now,
    policy_resolver=ReferencePolicyResolver(by_purpose_domain={("SCALE", "SCALING"): swf}))
sreq = SubjectRiskEvaluationRequest(subject_type="cloud_scaling_recommendation", subject_id="rec-1",
    subject_digest="sha256:abc", tenant_id="t", requested_purpose="SCALE", requested_domain="SCALING",
    requested_scope=sscope, requested_risk_class=RiskClass.HIGH, requested_autonomy_level=1,
    evaluation_time=now)
sres = seam.evaluate(sreq)
# successful evaluation returns a NON-EXECUTABLE decision
assert sres.disposition is SubjectRiskDisposition.RISK_PASSED, sres.disposition
assert (sres.executable, sres.authorization_performed, sres.envelope_issued,
        sres.actiongate_invoked, sres.actuation_performed, sres.effect_verified) == (False,)*6
# serialization + digest round-trip is stable
assert SubjectRiskDecision.from_dict(sres.to_canonical_dict()).digest() == sres.digest()
# no envelope / ActionGate path was reachable (sentinels)
seam._app.issue_envelope = lambda *a, **k: (_ for _ in ()).throw(AssertionError("envelope reached"))
seam._app.authorize_action = lambda *a, **k: (_ for _ in ()).throw(AssertionError("actiongate reached"))
assert seam.evaluate(sreq).disposition is SubjectRiskDisposition.RISK_PASSED
# missing trusted policy fails closed to a typed non-decision
sres_np = seam.evaluate(SubjectRiskEvaluationRequest(subject_type="x", subject_id="s",
    subject_digest="d", tenant_id="t", requested_purpose="SCALE", requested_domain="OTHER",
    requested_scope=sscope, evaluation_time=now))
assert sres_np.disposition is SubjectRiskDisposition.NOT_EVALUATED
assert sres_np.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY
# production construction rejects reference dependencies (the caller cannot supply authority)
try:
    RiskEvaluationSeam.production(workflow_source=ssrc,
        policy_resolver=ReferencePolicyResolver(by_purpose_domain={}),
        evidence_resolver=ReferenceControlEvidenceResolver(), evidence_admission=None,
        control_assurance=None, evidence_ingress=None,
        decision_authority=ReferenceDecisionAuthority(), evaluator_grant=None,
        key_record=key, clock=lambda: now)
    raise AssertionError("production accepted reference config")
except SeamConfigurationError:
    pass

# --- Facade containment (audit corrections), from the installed wheel ----------------
from risk_authority.domain.errors import ProductionContainmentError, RiskAuthorityError
from risk_authority.api.schemas import IssueEnvelopeRequest, AuthorizeActionRequest
from risk_authority.services.decision_authority import ReferenceDecisionAuthority

class _PA:
    is_production_authoritative = True
    def is_trusted(self, evidence, *, now): return True
    def is_admissible(self, record, *, now): return True
    def evaluate(self, request): raise AssertionError
class _PDA:
    is_production_authoritative = True
    def __init__(self): self._i = ReferenceDecisionAuthority()
    def issue_decision(self, **k): return self._i.issue_decision(**k)

psrc = InMemoryWorkflowIRSource(); psrc.register(swf)
pkw = dict(workflow_source=psrc, key_record=key, clock=lambda: now,
           evidence_admission=_PA(), control_assurance=_PA(), evidence_ingress=_PA(),
           production_mode=True)
# production_mode=True with no Decision Authority fails closed
try:
    RiskAuthorityApplication(decision_authority=None, **pkw)
    raise AssertionError("production accepted a missing decision authority")
except RiskAuthorityError:
    pass
# production_mode=True with the reference ruler fails closed
try:
    RiskAuthorityApplication(decision_authority=ReferenceDecisionAuthority(), **pkw)
    raise AssertionError("production accepted the reference ruler")
except RiskAuthorityError:
    pass
# an approved production app constructs, but cannot issue an envelope or authorize
papp = RiskAuthorityApplication(decision_authority=_PDA(), **pkw)
try:
    papp.issue_envelope("t", "c", IssueEnvelopeRequest(decision_id="d", audience="a",
        session_id="s", nonce="n"))
    raise AssertionError("production issued an envelope")
except ProductionContainmentError:
    pass
try:
    papp.authorize_action(AuthorizeActionRequest(envelope_id="e", tenant_id="t",
        actor_id="a", model_id="m", session_id="s", action_type="x", target_id="y", purpose="p"))
    raise AssertionError("production authorized an action")
except ProductionContainmentError:
    pass
# reference mode remains available only outside production (no injection needed)
refapp = RiskAuthorityApplication(workflow_source=psrc, key_record=key, clock=lambda: now)
assert isinstance(refapp._authority_service, ReferenceDecisionAuthority)
print("ISOLATED SINGLE-WHEEL RISK-AUTHORITY FACADE CONTAINMENT VERIFICATION OK")
print("ISOLATED SINGLE-WHEEL RISK-AUTHORITY SEAM (PR-1) VERIFICATION OK")

# --- Phase 4A: v2 subject-context contracts + pure binding validation, installed ------
from datetime import timedelta
from risk_authority.integrations import (SubjectContext, SubjectBinding,
    SubjectRiskEvaluationRequestV2, SubjectBindingValidation, SubjectBindingError,
    validate_subject_binding, SUBJECT_CONTEXT_SCHEMA_VERSION, SUBJECT_BINDING_SCHEMA_VERSION,
    EVALUATION_REQUEST_SCHEMA_VERSION, EVALUATION_REQUEST_SCHEMA_VERSION_V2,
    SUPPORTED_REQUEST_SCHEMA_VERSIONS)

assert SUBJECT_CONTEXT_SCHEMA_VERSION == "risk-subject-context-1"
assert SUBJECT_BINDING_SCHEMA_VERSION == "risk-subject-binding-1"
assert EVALUATION_REQUEST_SCHEMA_VERSION_V2 == "risk-subject-evaluation-request-2"
# Phase 4B: the accepted set now admits BOTH canonical schemas, because the validator is
# wired ahead of policy resolution (asserted behaviorally in the Phase 4B block below).
assert SUPPORTED_REQUEST_SCHEMA_VERSIONS == frozenset({
    EVALUATION_REQUEST_SCHEMA_VERSION, EVALUATION_REQUEST_SCHEMA_VERSION_V2})

vt0 = datetime(2026, 8, 13, 4, 0, 0, tzinfo=timezone.utc)
vctx = SubjectContext(action_type="scale_up", subject_asserted_at=vt0, subject_valid_from=vt0,
    subject_valid_until=vt0 + timedelta(minutes=15), environment="prod", region="eu-west-1",
    zone=None, compute_group="cluster-7", resource_class="web",
    magnitude_before=6, magnitude_after=9)
# The ADR §5.3 worked example reproduces byte-for-byte from the installed wheel.
assert vctx.digest() == "sha256:9af3f626a08e888a2916215a59c965e221179388ba3987cbbc6b2e0e64cfdbb0", vctx.digest()
vbind = SubjectBinding(tenant_id="tnt-acme", subject_id="wl-checkout-api",
    subject_type="cloud_scaling.capacity_action",
    recommendation_digest="sha256:" + "1" * 64, context_digest=vctx.digest())
assert vbind.digest() == "sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38", vbind.digest()
# strict round trips
assert SubjectContext.from_dict(vctx.to_canonical_dict()) == vctx
assert SubjectBinding.from_dict(vbind.to_canonical_dict()) == vbind

vreq = SubjectRiskEvaluationRequestV2(subject_type="cloud_scaling.capacity_action",
    subject_id="wl-checkout-api", subject_digest=vbind.digest(), tenant_id="tnt-acme",
    requested_purpose="cloud_scaling.capacity_action", requested_domain="cloud_scaling",
    requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
    evidence_references=("sha256:aaa", "sha256:bbb"), correlation_id="corr-42",
    subject_context=vctx, recommendation_digest="sha256:" + "1" * 64)
assert SubjectRiskEvaluationRequestV2.from_dict(vreq.to_canonical_dict()).digest() == vreq.digest()

# Frozen canonical identity of risk-subject-evaluation-request-2 (audit F-3), asserted
# from the INSTALLED wheel so a packaging or serialization drift is caught here too.
# This is also the corrected ADR 5.3 worked request digest.
assert vreq.digest() == "sha256:cd6dc88a3123959da32df7e03e936867416120099bdd303ebc954c6f04bdbcfb", vreq.digest()
assert SubjectRiskEvaluationRequestV2.from_dict(vreq.to_canonical_dict()).digest() == vreq.digest()

vres = validate_subject_binding(vreq)
assert isinstance(vres, SubjectBindingValidation)
assert vres.subject_digest == vbind.digest() and vres.context_digest == vctx.digest()
# validating a binding grants NOTHING
assert (vres.policy_resolved, vres.risk_evaluated, vres.authority_granted, vres.envelope_issued,
        vres.actiongate_invoked, vres.actuation_performed, vres.effect_verified,
        vres.executable) == (False,) * 8

# altered raw context + stale subject_digest fails closed
vtampered = SubjectContext(action_type="scale_up", subject_asserted_at=vt0, subject_valid_from=vt0,
    subject_valid_until=vt0 + timedelta(minutes=15), environment="staging", region="eu-west-1",
    zone=None, compute_group="cluster-7", resource_class="web",
    magnitude_before=6, magnitude_after=9)
try:
    validate_subject_binding(SubjectRiskEvaluationRequestV2(
        subject_type="cloud_scaling.capacity_action", subject_id="wl-checkout-api",
        subject_digest=vbind.digest(), tenant_id="tnt-acme",
        requested_purpose="cloud_scaling.capacity_action", requested_domain="cloud_scaling",
        requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
        subject_context=vtampered, recommendation_digest="sha256:" + "1" * 64))
    raise AssertionError("stale subject_digest over an altered context was accepted")
except SubjectBindingError:
    pass
# a v1 request is never auto-converted into the v2 validator
try:
    validate_subject_binding(sreq)
    raise AssertionError("a v1 request was accepted by the v2 binding validator")
except SubjectBindingError:
    pass

# Integrity, NOT authenticity (audit F-2): a FULLY self-consistent fabricated request is
# accepted by the pure structural validator -- every digest recomputed by the caller, a
# foreign tenant, and a recommendation_digest corresponding to no recommendation. This is
# expected: Phase 4A proves canonical consistency; source authenticity is the future
# adapter's job (reconstruct the recommendation, recompute rec.digest(), require equality).
vforged_ctx = SubjectContext(action_type="scale_up", subject_asserted_at=vt0,
    subject_valid_from=vt0, subject_valid_until=vt0 + timedelta(minutes=15),
    environment="staging", magnitude_before=1, magnitude_after=99999)
vforged_bind = SubjectBinding(tenant_id="tnt-victim", subject_id="wl-someone-else",
    subject_type="cloud_scaling.capacity_action", recommendation_digest="sha256:" + "f" * 64,
    context_digest=vforged_ctx.digest())
vforged = SubjectRiskEvaluationRequestV2(subject_type="cloud_scaling.capacity_action",
    subject_id="wl-someone-else", subject_digest=vforged_bind.digest(),
    tenant_id="tnt-victim", requested_purpose="cloud_scaling.capacity_action",
    requested_domain="cloud_scaling",
    requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
    subject_context=vforged_ctx, recommendation_digest="sha256:" + "f" * 64)
assert validate_subject_binding(vforged).tenant_id == "tnt-victim"
# Phase 4B admits v2, so the consistency-only guarantee now has consequences: this
# forgery IS admitted by binding validation. That is the documented boundary, not a
# defect -- source authenticity remains the future Cloud Scaling adapter's job. What
# still holds is containment, asserted in the Phase 4B block below.

# A v1-CLASS object carrying the v2 tag must NOT masquerade as v2 now that the v2 tag is
# a supported value: admission gates on the (class, tag) pair, not on set membership.
_stale = SubjectRiskEvaluationRequest(subject_type="x", subject_id="s", subject_digest="d",
    tenant_id="t", requested_purpose="SCALE", requested_domain="SCALING",
    requested_scope=sscope, evaluation_time=now,
    schema_version=EVALUATION_REQUEST_SCHEMA_VERSION_V2)
_r = seam.evaluate(_stale)
assert _r.disposition is SubjectRiskDisposition.NOT_EVALUATED, _r.disposition
assert _r.non_decision_reason is SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION
# v1 remains byte-for-byte intact alongside the new layer
assert SubjectRiskEvaluationRequest.from_dict(sreq.to_canonical_dict()).digest() == sreq.digest()
assert "subject_context" not in sreq.to_canonical_dict()
assert "recommendation_digest" not in sreq.to_canonical_dict()
print("ISOLATED SINGLE-WHEEL RISK-AUTHORITY v2 SUBJECT-CONTEXT (PHASE 4A) VERIFICATION OK")

# --- Phase 4B: validated v2 seam admission + subject-aware policy resolution ----------
from risk_authority.integrations import (SubjectAwarePolicyResolverPort,
    ReferenceSubjectAwarePolicyResolver, is_subject_aware_policy_resolver)

# The new public surface is present in the INSTALLED wheel.
assert hasattr(SubjectRiskNonDecisionReason, "CALLER_SUPPLIED_EVALUATION_TIME")
assert SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME.value == "caller_supplied_evaluation_time"
# Capability is DECLARED, never inferred: neither half alone confers v2 capability.
assert is_subject_aware_policy_resolver(ReferencePolicyResolver(by_purpose_domain={})) is False
assert is_subject_aware_policy_resolver(ReferenceSubjectAwarePolicyResolver(by_purpose_domain={})) is True
class _KwargsSniffer:
    is_production_authoritative = True
    is_subject_context_aware = True
    def resolve(self, **kw): raise AssertionError("must never be reached")
assert is_subject_aware_policy_resolver(_KwargsSniffer()) is False

# A trusted clock INSIDE the fixture's validity window [vt0, vt0+15m].
vnow = vt0 + timedelta(minutes=5)
vsrc = InMemoryWorkflowIRSource()
vwf = vsrc.register(WorkflowIR(workflow_ir_id="scaling-pol", version="1.0.0",
    status=WorkflowStatus.ACTIVE, rules=(), source_refs=(), effective_at=vt0).with_digest())

# (a) a genuine v2 request IS admitted through an explicitly subject-aware resolver, and
#     terminates at a NON-EXECUTABLE decision.
vres_seam = RiskEvaluationSeam.reference(workflow_source=vsrc, key_record=key,
    clock=lambda: vnow,
    policy_resolver=ReferenceSubjectAwarePolicyResolver(by_purpose_domain={
        ("cloud_scaling.capacity_action", "cloud_scaling"): vwf}))
_ok = vres_seam.evaluate(vreq)
assert _ok.non_decision_reason is not SubjectRiskNonDecisionReason.INVALID_SUBJECT, _ok
assert (_ok.authorization_performed, _ok.envelope_issued, _ok.actiongate_invoked,
        _ok.actuation_performed, _ok.effect_verified, _ok.executable) == (False,) * 6

# (b) the SAME request against a v1-only resolver fails closed -- no fallback.
vlegacy_seam = RiskEvaluationSeam.reference(workflow_source=vsrc, key_record=key,
    clock=lambda: vnow,
    policy_resolver=ReferencePolicyResolver(by_purpose_domain={
        ("cloud_scaling.capacity_action", "cloud_scaling"): vwf}))
_nf = vlegacy_seam.evaluate(vreq)
assert _nf.disposition is SubjectRiskDisposition.NOT_EVALUATED, _nf
assert _nf.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY
assert "resolver:not_subject_context_aware" in _nf.reason_codes

# (c) binding mismatches fail closed at the seam, from the wheel.
_bad = SubjectRiskEvaluationRequestV2(subject_type="cloud_scaling.capacity_action",
    subject_id="wl-checkout-api", subject_digest="sha256:" + "b" * 64, tenant_id="tnt-acme",
    requested_purpose="cloud_scaling.capacity_action", requested_domain="cloud_scaling",
    requested_scope=Scope(purposes=("cloud_scaling.capacity_action",)),
    subject_context=vctx, recommendation_digest="sha256:" + "1" * 64)
_br = vres_seam.evaluate(_bad)
assert _br.disposition is SubjectRiskDisposition.NOT_EVALUATED
assert _br.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT

# (d) a caller-supplied evaluation_time is REJECTED fail-closed on the trusted PRODUCTION
#     path, and the caller value never becomes the clock.
class _PEv:
    is_production_authoritative = True
    def resolve(self, **kw): return ()
class _PSAR:
    is_production_authoritative = True
    is_subject_context_aware = True
    def resolve_with_subject_context(self, **kw): return vwf
    def resolve(self, **kw): return vwf
from risk_authority.domain import AuthorityGrant, AuthorityType, RiskClass
vgrant = AuthorityGrant(principal_id="prod-evaluator", tenant_id="tnt-acme",
    authority_type=AuthorityType.RISK_APPROVAL, domains=("cloud_scaling",),
    allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH), max_autonomy=5,
    delegated_by="root", grantable_scope=Scope(purposes=("cloud_scaling.capacity_action",)))
vprod = RiskEvaluationSeam.production(workflow_source=vsrc, policy_resolver=_PSAR(),
    evidence_resolver=_PEv(), evidence_admission=_PA(), control_assurance=_PA(),
    evidence_ingress=_PA(), decision_authority=_PDA(), evaluator_grant=vgrant,
    key_record=key, clock=lambda: vnow)
_caller_time = vt0 + timedelta(minutes=1)
_tr = vprod.evaluate(SubjectRiskEvaluationRequestV2.from_dict(
    {**vreq.to_canonical_dict(), "evaluation_time": "2026-08-13T04:01:00.000000Z"}))
assert _tr.disposition is SubjectRiskDisposition.NOT_EVALUATED, _tr
assert _tr.non_decision_reason is SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME
assert _tr.evaluated_at == vnow and _tr.evaluated_at != _caller_time

# (e) a reference resolver can never enter the production composition root.
try:
    RiskEvaluationSeam.production(workflow_source=vsrc,
        policy_resolver=ReferenceSubjectAwarePolicyResolver(by_purpose_domain={}),
        evidence_resolver=_PEv(), evidence_admission=_PA(), control_assurance=_PA(),
        evidence_ingress=_PA(), decision_authority=_PDA(), evaluator_grant=vgrant,
        key_record=key, clock=lambda: vnow)
    raise AssertionError("production accepted a reference subject-aware resolver")
except SeamConfigurationError:
    pass

# (f) v1 remains byte-for-byte intact after the widening.
assert sreq.digest() == SubjectRiskEvaluationRequest.from_dict(sreq.to_canonical_dict()).digest()
print("ISOLATED SINGLE-WHEEL RISK-AUTHORITY v2 SEAM ADMISSION (PHASE 4B) VERIFICATION OK")

print("ISOLATED SINGLE-WHEEL RISK-AUTHORITY VERIFICATION OK")
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
    return {t for t in tops if not (t == "risk_authority" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the single risk-authority wheel")
    _run([sys.executable, "-m", "build", "--wheel", str(PKG), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_risk_authority-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "risk_authority/py.typed" in names, "wheel is missing py.typed"
    print("      wheel contains only risk_authority/ (+ py.typed) + dist-info")

    print("[3/4] create an isolated venv and install ONLY this wheel (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-risk-authority"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED SINGLE-WHEEL RISK-AUTHORITY DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
