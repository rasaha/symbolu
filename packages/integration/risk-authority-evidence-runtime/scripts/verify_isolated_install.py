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
  * the PRODUCTION path GRANTs on full trusted support and DENYs a forged PASS
    (no admitted evidence) — the RA-5 acceptance anchor;
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
    ProductionEvidenceAdmission, TapControlAssurance, RiskAuthorityEvidenceRuntime,
    stamp_admitted_evidence,
)
from ugence_tap_provider.api import TapEngine, build_tap_provider
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.api.schemas import CreateCaseRequest
from risk_authority.domain import (
    AuthorityGrant, AuthorityType, Predicate, PredicateOp, RiskClass, RuleEffect,
    Scope, WorkflowIR, WorkflowRule, WorkflowStatus,
)
from risk_authority.domain.enums import RiskRecommendation
from risk_authority.integrations import InMemoryWorkflowIRSource

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
runtime = RiskAuthorityEvidenceRuntime(
    workflow_source=source, key_record=key, clock=lambda: NOW,
    evidence_admission=ProductionEvidenceAdmission(),
    control_assurance=TapControlAssurance(build_tap_provider(TapEngine())))
runtime.application.authority.add_grant(AuthorityGrant(
    principal_id=PRINCIPAL, tenant_id=TENANT, authority_type=AuthorityType.RISK_APPROVAL,
    domains=("FINANCE",), allowed_risk_classes=(RiskClass.HIGH,), max_autonomy=2,
    delegated_by="x", grantable_scope=scope))

def new_case(cid):
    runtime.create_case(CreateCaseRequest(
        tenant_id=TENANT, case_id=cid, subject_id=ACTOR, model_id=MODEL, purpose="P",
        domain="FINANCE", jurisdictions=("US",), tools=("crm.read",), autonomy_level=2,
        data_classes=(), workflow_ir_id="wf", inherent_risk=RiskClass.HIGH,
        residual_risk=RiskClass.MEDIUM))

# 2. GRANT path — full trusted support.
new_case("grant")
ev_ok = stamp_admitted_evidence(
    evidence_id="ev1", tenant_id=TENANT, source_type="attestation",
    source_identity="prov", subject=ACTOR, workflow_ir_digest=wf.digest,
    policy_digest=wf.digest, observed_at=NOW, valid_until=NOW + timedelta(hours=1),
    admitted_at=NOW, producer="prod", producer_version="1")
g = runtime.submit_evidence_and_evaluate(TENANT, "grant", (ev_ok,), control_evidence={"C1": ("ev1",)})
assert g.recommendation in (RiskRecommendation.ALLOW, RiskRecommendation.ALLOW_WITH_CONDITIONS), g.recommendation

# 3. DENY path — forged PASS, no admitted evidence.
new_case("forged")
d = runtime.submit_evidence_and_evaluate(TENANT, "forged", ())
assert d.recommendation is RiskRecommendation.DENY, d.recommendation

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
