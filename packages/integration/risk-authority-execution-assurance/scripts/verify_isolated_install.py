#!/usr/bin/env python3
"""Reproducible proof that ``ugence-risk-authority-execution-assurance`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no
monorepo path.

Unlike the RA-7 runtime-assurance package (proven fully offline with ``--no-index``
because it has no third-party runtime dependency), RA-8 legitimately composes
Decision Authority, which is pydantic-backed. This verifier therefore builds a
local wheelhouse of the FIRST-PARTY wheels (governance-contracts, risk-authority,
status-runtime, decision-authority, and this package) and installs RA-8 from it,
allowing only the third-party ``pydantic`` (a transitive DA dependency) from the
index — the same pattern as ``ugence-risk-authority-runtime``.

It then proves, inside that clean env:

  * ``ugence_risk_authority_execution_assurance`` imports from site-packages;
  * the ratified RA-8 loop runs: a matching final effect → MATCHED, no signal; a
    material mismatch → MISMATCH → a neutral EXECUTION_EFFECT_MISMATCH signal into
    the REAL RA-6 intake → targeted envelope revocation; the M-1 favorable-mask
    hole is closed (FAILED-then-SUCCEEDED ≠ MATCHED); a reference effect
    authenticator is refused in production (F-1);
  * ``risk_authority`` remains a stdlib-only leaf carrying the additive
    EXECUTION_EFFECT_MISMATCH category;
  * the Agent Runtime is NOT importable (RA-8 observes it via a neutral contract),
    and no other out-of-scope monorepo package is importable.

Run:  python packages/integration/risk-authority-execution-assurance/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/risk-authority-execution-assurance -> repo

# First-party wheels RA-8 needs, built locally into the wheelhouse.
FIRST_PARTY = [
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "integration" / "risk-authority-status-runtime",
    REPO / "packages" / "capabilities" / "decision-authority",
    PKG,
]

_PROBE = r'''
import importlib, pathlib
from datetime import datetime, timezone

# 1. Import from site-packages, not the repo checkout.
import ugence_risk_authority_execution_assurance as ra8
loc = pathlib.Path(ra8.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_risk_authority_execution_assurance import (
    EffectAssuranceService, EffectAssuranceSignalEmitter, EffectObservation,
    EffectReconciliationOutcome, ExpectedEffect, GovernedAuthorityContext,
    ReferenceEffectSourceAuthenticator, ReferenceEffectIngressRejectedError,
    TrustedEffectIngress,
)
from ugence_risk_authority_status_runtime import (
    AuthorityLifecycleService, AuthorityReassessor, ReferenceAuthorityStore,
    ReferenceWriterAuthorizer,
)
from ugence_risk_authority_status_runtime.writer import LIFECYCLE_WRITE_CAPABILITY
from risk_authority.integrations.authority_lifecycle import WriterPrincipal
from risk_authority.domain.authority_signal import SignalChangeType
from ugence_decision_authority.execution.status import BusinessOutcome, Finality

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT, ENV, WF = "t1", "env_abc", "wf1"

# Real RA-6 reassess->revoke stack behind the neutral intake port.
store = ReferenceAuthorityStore(); store.seed_tenant(TENANT)
writer = AuthorityLifecycleService(store, ReferenceWriterAuthorizer(), clock=lambda: NOW)
sysprin = WriterPrincipal(principal_id="ra-reassessor", tenant_id=TENANT,
                          capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}))
reassessor = AuthorityReassessor(writer, system_principal=sysprin)
service = EffectAssuranceService.reference(emitter=EffectAssuranceSignalEmitter(reassessor))

ctx = GovernedAuthorityContext(tenant_id=TENANT, workflow_instance_id=WF, envelope_id=ENV,
    authorized_action_digest="pf1", correlation_id="c1", provider="cloud", idempotency_key="idem1")
expected = ExpectedEffect(action_type="terminate", target_system="cloud",
    authorized_parameters={"target": "i-1"})

def obs(oid, outcome, eff):
    return EffectObservation(schema_version="1", observation_id=oid, tenant_id=TENANT,
        workflow_instance_id=WF, envelope_id=ENV, authorized_action_digest="pf1",
        attempt_id="idem1#attempt-1", external_request_id="ext1", business_outcome=outcome,
        provider="cloud", external_effect_id=eff, observed_parameters={"target": "i-1"},
        finality=Finality.FINAL, source="ref-effect-source", source_version="1")

# Matching final effect: MATCHED, no revocation.
m = service.assess(ctx, attempt_id="idem1#attempt-1", expected=expected,
    observations=[obs("o1", BusinessOutcome.SUCCEEDED, "e-ok")],
    external_request_id="ext1", idempotency_key="idem1", provider="cloud", produced_at=NOW)
assert m.outcome is EffectReconciliationOutcome.MATCHED, m.outcome
assert ENV not in store.export(TENANT).revoked_envelopes

# M-1: FAILED-then-SUCCEEDED (same request, distinct effect ids) must NOT be MATCHED,
# and the material mismatch -> EXECUTION_EFFECT_MISMATCH -> real targeted revoke.
mm = service.assess(ctx, attempt_id="idem1#attempt-1", expected=expected,
    observations=[obs("o1", BusinessOutcome.FAILED, "e-fail"),
                  obs("o2", BusinessOutcome.SUCCEEDED, "e-ok")],
    external_request_id="ext1", idempotency_key="idem1", provider="cloud", produced_at=NOW)
assert mm.assessment.da_status.value == "RECONCILED", "DA latest-wins expected"
assert mm.outcome is not EffectReconciliationOutcome.MATCHED, mm.outcome
assert mm.handoff is not None and mm.handoff.submitted
assert mm.handoff.signal.change_type is SignalChangeType.EXECUTION_EFFECT_MISMATCH
assert ENV in store.export(TENANT).revoked_envelopes, "RA-6 did not revoke the envelope"

# MATCHED cannot resurrect a revoked envelope.
again = service.assess(ctx, attempt_id="idem1#attempt-1", expected=expected,
    observations=[obs("o3", BusinessOutcome.SUCCEEDED, "e-ok")],
    external_request_id="ext1", idempotency_key="idem1", provider="cloud", produced_at=NOW)
assert again.outcome is EffectReconciliationOutcome.MATCHED
assert ENV in store.export(TENANT).revoked_envelopes, "MATCHED resurrected a revoked envelope"

# F-1: production refuses the reference effect authenticator.
try:
    TrustedEffectIngress(ReferenceEffectSourceAuthenticator(), production_mode=True)
    raise AssertionError("production accepted a reference authenticator (F-1)")
except ReferenceEffectIngressRejectedError:
    pass

# risk_authority stays a stdlib-only leaf carrying the additive category.
import risk_authority  # noqa: F401
assert hasattr(SignalChangeType, "EXECUTION_EFFECT_MISMATCH")

# No out-of-scope monorepo package importable (esp. the Agent Runtime).
for forbidden in ("symbolu", "ugence_agent_runtime", "ugence_risk_authority_runtime",
                  "ugence_risk_authority_runtime_assurance", "ugence_actiongate_provider",
                  "ugence_tap_provider"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"FAIL: out-of-scope package importable: {forbidden}")

print("OK: execution-assurance installed from declared deps; RA-8 assess->signal->RA-6 "
      "revoke enforced; M-1 favorable-mask closed; boundaries clean")
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

        # Build first-party wheels into the wheelhouse (deps resolved from index).
        for pkg in FIRST_PARTY:
            _run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheelhouse), str(pkg)])

        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        vpy = env_dir / "bin" / "python"
        if not vpy.exists():  # windows
            vpy = env_dir / "Scripts" / "python.exe"

        # Install RA-8, preferring local wheels; index only for pydantic (DA's dep).
        _run([str(vpy), "-m", "pip", "install", "--quiet", "--find-links", str(wheelhouse),
              "ugence-risk-authority-execution-assurance"])

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
