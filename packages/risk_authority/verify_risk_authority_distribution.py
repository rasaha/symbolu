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
assert ra.__version__ == "0.2.0", ra.__version__
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
