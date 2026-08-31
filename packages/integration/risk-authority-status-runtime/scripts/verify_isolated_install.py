#!/usr/bin/env python3
"""Reproducible proof that ``ugence-risk-authority-status-runtime`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no
monorepo path.

It is an *integration* package: it legitimately depends on exactly one first-party
wheel (``ugence-risk-authority``, the machine-authority owner) and no third-party
runtime dependency at all. This verifier builds a local wheelhouse of those wheels
and installs the package from it (``--no-index``).

It then proves, inside that clean env:

  * ``ugence_risk_authority_status_runtime`` imports from site-packages;
  * the ratified RA-6 lifecycle enforces: valid+fresh ALLOW; revoke → DENY; epoch
    advance → DENY; uninitialized cache → DENY; unauthorized/cross-tenant writer →
    rejected (no state change); reference authorizer refused in production (F-1);
  * ``risk_authority`` remains a stdlib-only leaf (importable, no third-party dep);
  * NO out-of-scope monorepo package is importable — including the RA-4.5 runtime,
    the RA-5 evidence runtime, the Agent Runtime, and the governance kernels.

Run:  python packages/integration/risk-authority-status-runtime/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/risk-authority-status-runtime -> repo

FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    PKG,
]

_PROBE = r'''
import importlib, pathlib
from datetime import datetime, timedelta, timezone

# 1. Import from site-packages, not the repo checkout.
import ugence_risk_authority_status_runtime as srt
loc = pathlib.Path(srt.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_risk_authority_status_runtime import (
    ReferenceAuthorityStore, AuthorityStatusCache, AuthorityLifecycleService,
    ReferenceWriterAuthorizer, ReferenceWriterRejectedError, StatusAwareActionGate,
    LIFECYCLE_WRITE_CAPABILITY,
)
from risk_authority.api import (
    ControlResultInput, CreateCaseRequest, DecisionRequest, EvaluateRequest,
    IssueEnvelopeRequest, RiskAuthorityApplication,
)
from risk_authority.crypto import KeyRing, SigningKey, SigningKeyRecord
from risk_authority.domain import (
    AuthorityGrant, AuthorityType, CanonicalAction, Predicate, PredicateOp, RiskClass,
    RuleEffect, Scope, WorkflowIR, WorkflowRule, WorkflowStatus,
)
from risk_authority.domain.enums import ActionGateDecision
from risk_authority.integrations import InMemoryWorkflowIRSource, RuntimeIdentity
from risk_authority.integrations.authority_lifecycle import WriterPrincipal
from risk_authority.services.authority_status import StalenessPolicy, ALLOW

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT, ACTOR, MODEL, PRINCIPAL, SESSION = "t1", "a1", "m1", "p1", "s1"

wf = WorkflowIR(
    workflow_ir_id="wf", version="1", status=WorkflowStatus.ACTIVE,
    rules=(WorkflowRule(rule_id="R1",
        conditions=(Predicate("domain", PredicateOp.EQ, "FINANCE"),),
        required_controls=("C1",), effect=RuleEffect.DENY_UNLESS_ALL),),
    source_refs=("REF-1",), effective_at=NOW).with_digest()
scope = Scope(purposes=("P",), tools_allow=("crm.read",), models=(MODEL,), actors=(ACTOR,),
              max_autonomy_level=2, max_transaction_minor_units=1000)
source = InMemoryWorkflowIRSource(); source.register(wf)
key = SigningKeyRecord("k", SigningKey.from_seed(bytes(range(32))))
app = RiskAuthorityApplication(workflow_source=source, key_record=key, clock=lambda: NOW)
app.authority.add_grant(AuthorityGrant(
    principal_id=PRINCIPAL, tenant_id=TENANT, authority_type=AuthorityType.RISK_APPROVAL,
    domains=("FINANCE",), allowed_risk_classes=(RiskClass.LOW, RiskClass.HIGH), max_autonomy=2,
    delegated_by="x", grantable_scope=scope))
key_ring = KeyRing.from_records([key])
app.create_case(CreateCaseRequest(
    tenant_id=TENANT, case_id="c", subject_id=ACTOR, model_id=MODEL, purpose="P",
    domain="FINANCE", jurisdictions=("US",), tools=("crm.read",), autonomy_level=2,
    data_classes=(), workflow_ir_id="wf", inherent_risk=RiskClass.HIGH,
    residual_risk=RiskClass.LOW))
ev = app.evaluate(TENANT, "c", EvaluateRequest(control_results=(ControlResultInput("C1", "PASS"),)))
dec = app.issue_decision(TENANT, "c", ev, DecisionRequest(principal_id=PRINCIPAL, requested_scope=scope))
assert dec.grants_authority
envelope = app.issue_envelope(TENANT, "c", IssueEnvelopeRequest(
    decision_id=dec.decision_id, audience="aud", session_id=SESSION, nonce="n1"))

store = ReferenceAuthorityStore(); store.seed_tenant(TENANT)
writer = AuthorityLifecycleService(store, ReferenceWriterAuthorizer(), clock=lambda: NOW)
cache = AuthorityStatusCache(store, clock=lambda: NOW); cache.sync()
gate = StatusAwareActionGate(cache, policy=StalenessPolicy.fail_closed_defaults())
admin = WriterPrincipal(principal_id="adm", tenant_id=TENANT,
                        capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}))

def act(): return CanonicalAction(tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL,
    action_type="crm.read", target_id="x", purpose="P", data_classes=(),
    destination=None, amount_minor_units=None, currency="USD")
def ident(): return RuntimeIdentity(tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL, session_id=SESSION)
def authorize():
    return gate.authorize(authorization_id="a", envelope=envelope, action=act(),
        identity=ident(), key_ring=key_ring, tier=RiskClass.LOW, now=NOW)

# valid + fresh -> ALLOW
r = authorize()
assert r.decision is ActionGateDecision.AUTHORIZED and r.status.outcome == ALLOW, r

# targeted revoke -> DENY
writer.revoke_envelope(principal=admin, tenant_id=TENANT, envelope_id=envelope.envelope_id,
                       reason="r", correlation_id="x")
cache.sync()
assert authorize().decision is ActionGateDecision.DENIED

# fresh slice: epoch advance -> DENY (stale epoch)
store2 = ReferenceAuthorityStore(); store2.seed_tenant(TENANT)
writer2 = AuthorityLifecycleService(store2, ReferenceWriterAuthorizer(), clock=lambda: NOW)
cache2 = AuthorityStatusCache(store2, clock=lambda: NOW); cache2.sync()
writer2.advance_epoch(principal=admin, tenant_id=TENANT, change_id="c1", reason="r", correlation_id="x")
cache2.sync()
gate2 = StatusAwareActionGate(cache2, policy=StalenessPolicy.fail_closed_defaults())
r2 = gate2.authorize(authorization_id="a", envelope=envelope, action=act(), identity=ident(),
                     key_ring=key_ring, tier=RiskClass.LOW, now=NOW)
assert r2.decision is ActionGateDecision.DENIED

# uninitialized cache -> DENY (all tiers)
cache3 = AuthorityStatusCache(ReferenceAuthorityStore(), clock=lambda: NOW)  # never synced
gate3 = StatusAwareActionGate(cache3, policy=StalenessPolicy.fail_closed_defaults())
r3 = gate3.authorize(authorization_id="a", envelope=envelope, action=act(), identity=ident(),
                     key_ring=key_ring, tier=RiskClass.LOW, now=NOW)
assert r3.decision is ActionGateDecision.DENIED and any("uninitialized" in c for c in r3.reason_codes)

# unauthorized + cross-tenant writer -> rejected, no state change
powerless = WriterPrincipal(principal_id="nobody", tenant_id=TENANT, capabilities=frozenset())
assert writer2.advance_epoch(principal=powerless, tenant_id=TENANT, change_id="z", reason="r",
                             correlation_id="x").outcome.value == "ERROR_NON_EXECUTABLE"
foreign = WriterPrincipal(principal_id="att", tenant_id="other",
                          capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}))
assert writer2.revoke_envelope(principal=foreign, tenant_id=TENANT, envelope_id="e", reason="r",
                               correlation_id="x").outcome.value == "ERROR_NON_EXECUTABLE"

# F-1: production refuses the reference authorizer.
try:
    AuthorityLifecycleService(ReferenceAuthorityStore(), ReferenceWriterAuthorizer(),
                              clock=lambda: NOW, production_mode=True)
    raise AssertionError("production accepted a reference authorizer (F-1)")
except ReferenceWriterRejectedError:
    pass

# risk_authority stays a stdlib-only leaf.
import risk_authority  # noqa: F401

# No out-of-scope monorepo package importable.
for forbidden in ("symbolu", "ugence_risk_authority_runtime",
                  "ugence_risk_authority_evidence_runtime", "ugence_agent_runtime",
                  "ugence_decision_authority", "ugence_actiongate_provider",
                  "ugence_tap_provider"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"FAIL: out-of-scope package importable: {forbidden}")

print("OK: status-runtime installed from declared deps; RA-6 lifecycle enforced; boundaries clean")
'''


def _run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        wheelhouse = tmpdir / "wheelhouse"
        wheelhouse.mkdir()
        env_dir = tmpdir / "venv"

        for pkg in FIRST_PARTY:
            _run([sys.executable, "-m", "pip", "wheel", "--no-deps",
                  "-w", str(wheelhouse), str(pkg)])

        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        vpy = env_dir / "bin" / "python"
        if not vpy.exists():  # windows
            vpy = env_dir / "Scripts" / "python.exe"

        _run([str(vpy), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(wheelhouse), "ugence-risk-authority-status-runtime"])

        probe = tmpdir / "probe.py"
        probe.write_text(_PROBE)
        _run([str(vpy), str(probe)])
    print("verify_isolated_install: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"verify_isolated_install: FAIL ({exc})", file=sys.stderr)
        sys.exit(1)
