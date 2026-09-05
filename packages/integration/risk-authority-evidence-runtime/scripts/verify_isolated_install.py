#!/usr/bin/env python3
"""Reproducible proof that ``ugence-risk-authority-evidence-runtime`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no
monorepo path.

Like the RA-4.5 runtime verifier, this is an *integration* package: it legitimately
depends on first-party wheels (risk-authority, tap-provider) plus their transitive
first-party leaves (governance-provider-framework, governance-contracts). This
verifier builds a local wheelhouse of those FIRST-PARTY wheels and installs the
package from it (no third-party runtime dependency is required at all).

It then proves, inside that clean env:

  * ``ugence_risk_authority_evidence_runtime`` imports from site-packages;
  * the PRODUCTION path GRANTs only on an EXPLICIT full-support determination over
    an authenticated producer channel, and DENYs: a forged PASS (no evidence),
    presumptive support from a rule-less evaluator (audit H-1), and evidence from
    an untrusted channel (audit H-2); production also refuses to construct with a
    permissive evaluator or a missing trusted-ingress seam;
  * ``risk_authority`` remains a stdlib-only leaf (importable, no provider dep);
  * NO out-of-scope monorepo package is importable — including the RA-4.5 runtime
    and the two governance kernels (RA-5 is upstream of the envelope).

Run:  python packages/integration/risk-authority-evidence-runtime/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/risk-authority-evidence-runtime -> repo

FIRST_PARTY = [
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "governance-provider-framework",
    REPO / "packages" / "providers" / "tap",
    REPO / "packages" / "risk_authority",
    PKG,
]

_PROBE = r'''
import importlib, pathlib
from datetime import datetime, timedelta, timezone

# 1. Import from site-packages, not the repo checkout.
import ugence_risk_authority_evidence_runtime as rt
loc = pathlib.Path(rt.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_risk_authority_evidence_runtime import (
    ProductionEvidenceAdmission, StaticTrustedIngress, TapControlAssurance,
    RiskAuthorityEvidenceRuntime, stamp_admitted_evidence,
)
from ugence_tap_provider.api import TapEngine, TapOutcome, TapRule, build_tap_provider
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.api.schemas import CreateCaseRequest
from risk_authority.domain import (
    AuthorityGrant, AuthorityType, Predicate, PredicateOp, RiskClass, RuleEffect,
    Scope, WorkflowIR, WorkflowRule, WorkflowStatus,
)
from risk_authority.domain.enums import RiskRecommendation
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.services.decision_authority import ReferenceDecisionAuthority


class _ProdDecisionAuthority:
    """Conformance double for a production Decision Authority adapter (defect (h)):
    production mode now requires an explicit production-authoritative ruler."""
    is_production_authoritative = True

    def __init__(self):
        self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw):
        return self._inner.issue_decision(**kw)


NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
TENANT, ACTOR, MODEL, PRINCIPAL = "t1", "a1", "m1", "p1"

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

import os, tempfile
from risk_authority.persistence import SqliteRiskAuthorityStore

def build_runtime(control_assurance, ingress):
    r = RiskAuthorityEvidenceRuntime(
        workflow_source=source, key_record=key, clock=lambda: NOW,
        evidence_admission=ProductionEvidenceAdmission(),
        control_assurance=control_assurance, evidence_ingress=ingress,
        decision_authority=_ProdDecisionAuthority(),
        persistence=SqliteRiskAuthorityStore(os.path.join(tempfile.mkdtemp(), "ra.sqlite")))
    r.application.authority.add_grant(AuthorityGrant(
        principal_id=PRINCIPAL, tenant_id=TENANT, authority_type=AuthorityType.RISK_APPROVAL,
        domains=("FINANCE",), allowed_risk_classes=(RiskClass.HIGH,), max_autonomy=2,
        delegated_by="x", grantable_scope=scope))
    return r

def new_case(runtime, cid):
    runtime.create_case(CreateCaseRequest(
        tenant_id=TENANT, case_id=cid, subject_id=ACTOR, model_id=MODEL, purpose="P",
        domain="FINANCE", jurisdictions=("US",), tools=("crm.read",), autonomy_level=2,
        data_classes=(), workflow_ir_id="wf", inherent_risk=RiskClass.HIGH,
        residual_risk=RiskClass.MEDIUM))

def evidence(eid="ev1"):
    return stamp_admitted_evidence(
        evidence_id=eid, tenant_id=TENANT, source_type="attestation",
        source_identity="prov", subject=ACTOR, workflow_ir_digest=wf.digest,
        policy_digest=wf.digest, observed_at=NOW, valid_until=NOW + timedelta(hours=1),
        admitted_at=NOW, producer="prod", producer_version="1")

# A deployment's REAL authenticated-channel verifier — no is_reference_ingress
# marker, so production accepts it (unlike the conformance StaticTrustedIngress,
# which F-1 refuses). Models mTLS / workload-identity ingress.
class ChannelIngress:
    def __init__(self, *, trusted): self._t = bool(trusted)
    def is_trusted(self, evidence, *, now): return self._t

# An EXPLICIT full-support determination (rule) + authenticated producer channel.
supported = {"C1": TapRule(outcome=TapOutcome.SUPPORTED, evidence_coverage=1.0)}
prod_assurance = TapControlAssurance(build_tap_provider(TapEngine(rules=supported)))
trusted_ingress = ChannelIngress(trusted=True)

# 2. GRANT path — explicit full support + trusted channel.
runtime = build_runtime(prod_assurance, trusted_ingress)
new_case(runtime, "grant")
g = runtime.submit_evidence_and_evaluate(TENANT, "grant", (evidence(),), control_evidence={"C1": ("ev1",)})
assert g.recommendation in (RiskRecommendation.ALLOW, RiskRecommendation.ALLOW_WITH_CONDITIONS), g.recommendation

# 3. DENY — forged PASS, no admitted evidence.
new_case(runtime, "forged")
d = runtime.submit_evidence_and_evaluate(TENANT, "forged", ())
assert d.recommendation is RiskRecommendation.DENY, d.recommendation

# 3b. H-1 DENY — a rule-less (presumptive) evaluator cannot mint PASS from mere
# evidence presence, even over a trusted channel with full evidence.
presumptive_runtime = build_runtime(
    TapControlAssurance(build_tap_provider(TapEngine())), ChannelIngress(trusted=True))
new_case(presumptive_runtime, "presumptive")
p = presumptive_runtime.submit_evidence_and_evaluate(
    TENANT, "presumptive", (evidence(),), control_evidence={"C1": ("ev1",)})
assert p.recommendation is RiskRecommendation.DENY, p.recommendation

# 3c. H-2 DENY — evidence from an UNTRUSTED producer channel never admits, even
# with an explicit full-support determination and a valid self-computed digest.
untrusted_runtime = build_runtime(
    TapControlAssurance(build_tap_provider(TapEngine(rules=supported))),
    ChannelIngress(trusted=False))
new_case(untrusted_runtime, "untrusted")
u = untrusted_runtime.submit_evidence_and_evaluate(
    TENANT, "untrusted", (evidence(),), control_evidence={"C1": ("ev1",)})
assert u.recommendation is RiskRecommendation.DENY, u.recommendation

# 3d. F-1 fail-closed — production REFUSES the conformance StaticTrustedIngress
# stand-in (is_reference_ingress=True); it is not a real authenticated-channel
# verifier and must never be wired into production.
from risk_authority.domain.errors import RiskAuthorityError
try:
    build_runtime(prod_assurance, StaticTrustedIngress(trusted=True))
    raise AssertionError("production accepted a reference/conformance ingress (F-1)")
except RiskAuthorityError:
    pass

# 3e. H-1/H-2 fail-closed construction — production refuses a permissive evaluator
# and refuses a missing trusted-ingress seam.
for bad in ("permissive", "no_ingress"):
    try:
        if bad == "permissive":
            build_runtime(TapControlAssurance(build_tap_provider(TapEngine()),
                          require_explicit_determination=False), trusted_ingress)
        else:
            RiskAuthorityEvidenceRuntime(
                workflow_source=source, key_record=key, clock=lambda: NOW,
                evidence_admission=ProductionEvidenceAdmission(),
                control_assurance=prod_assurance, evidence_ingress=None)
    except RiskAuthorityError:
        continue
    raise SystemExit(f"FAIL: production did not fail closed for {bad}")

# 4. risk_authority stays a stdlib-only leaf (imports fine, no provider dep pulled).
import risk_authority  # noqa: F401

# 5. No out-of-scope monorepo package importable — including RA-4.5 + kernels.
for forbidden in ("symbolu", "agentic", "ai_hiring", "applications", "domains",
                  "tap_provider", "cloud_controller",
                  "ugence_risk_authority_runtime", "ugence_decision_authority",
                  "ugence_actiongate_provider"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"FAIL: out-of-scope package importable: {forbidden}")

print("OK: evidence-runtime installed from declared deps; GRANT+DENY verified; boundaries clean")
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
              "--find-links", str(wheelhouse), "ugence-risk-authority-evidence-runtime"])

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
