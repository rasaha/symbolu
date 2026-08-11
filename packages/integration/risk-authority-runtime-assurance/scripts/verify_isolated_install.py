#!/usr/bin/env python3
"""Reproducible proof that ``ugence-risk-authority-runtime-assurance`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no
monorepo path.

It is an *integration* package: it legitimately depends on exactly two first-party
wheels (``ugence-risk-authority`` — the machine-authority owner — and
``ugence-risk-authority-status-runtime`` — the RA-6 intake) and no third-party
runtime dependency at all. This verifier builds a local wheelhouse of those wheels
and installs the package from it (``--no-index``).

It then proves, inside that clean env:

  * ``ugence_risk_authority_runtime_assurance`` imports from site-packages;
  * the ratified RA-7 loop runs: a normal trajectory → NORMAL, no signal; a
    cumulative-exposure breach → ESCALATED → a neutral RUNTIME_RISK_ESCALATED
    signal into the REAL RA-6 intake → targeted envelope revocation; a duplicate
    observation is idempotent; a reference telemetry authenticator is refused in
    production (F-1);
  * ``risk_authority`` remains a stdlib-only leaf;
  * the Agent Runtime is NOT importable (RA-7 observes it via a neutral contract),
    and no other out-of-scope monorepo package is importable.

Run:  python packages/integration/risk-authority-runtime-assurance/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/risk-authority-runtime-assurance -> repo

FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "integration" / "risk-authority-status-runtime",
    PKG,
]

_PROBE = r'''
import importlib, pathlib
from datetime import datetime, timezone

# 1. Import from site-packages, not the repo checkout.
import ugence_risk_authority_runtime_assurance as ra7
loc = pathlib.Path(ra7.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"

from ugence_risk_authority_runtime_assurance import (
    AuthorityReassessmentSignalEmitter, AssessmentOutcome, RuntimeRiskLevel,
    RuntimeAssuranceService, ReferenceTelemetryAuthenticator, ReferenceIngressRejectedError,
    ReferenceTrajectoryPolicyReader, TrajectoryObservation, TrajectoryPolicy,
    TrajectoryPolicyRef, TrustedTelemetryIngress,
)
from ugence_risk_authority_status_runtime import (
    AuthorityLifecycleService, AuthorityReassessor, ReferenceAuthorityStore,
    ReferenceWriterAuthorizer,
)
from ugence_risk_authority_status_runtime.writer import LIFECYCLE_WRITE_CAPABILITY
from risk_authority.integrations.authority_lifecycle import WriterPrincipal

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT, ENV, WF = "t1", "env_abc", "wf1"

# Real RA-6 reassess->revoke stack behind the neutral intake port.
store = ReferenceAuthorityStore(); store.seed_tenant(TENANT)
writer = AuthorityLifecycleService(store, ReferenceWriterAuthorizer(), clock=lambda: NOW)
sysprin = WriterPrincipal(principal_id="ra-reassessor", tenant_id=TENANT,
                          capabilities=frozenset({LIFECYCLE_WRITE_CAPABILITY}))
reassessor = AuthorityReassessor(writer, system_principal=sysprin)

reader = ReferenceTrajectoryPolicyReader()
reader.register(TrajectoryPolicy(policy_id="p1", version="1",
                                 cumulative_exposure_limits={"model_cost": 50000.0}))
service = RuntimeAssuranceService.reference(
    policy_reader=reader, emitter=AuthorityReassessmentSignalEmitter(reassessor))
ref = TrajectoryPolicyRef("p1", "1")

def obs(seq, amount):
    return TrajectoryObservation(
        schema_version="1", event_id=f"{WF}:{seq}", tenant_id=TENANT,
        workflow_instance_id=WF, envelope_id=ENV, runtime_event_type="PROVIDER_COMPLETED",
        observed_at=NOW, source="telemetry", source_version="1", action_id=f"a{seq}",
        sequence_number=seq, policy_ref=ref, detail={"exposure": {"model_cost": amount}})

# Normal: no signal, no revocation.
r = service.observe(obs(1, 100.0), produced_at=NOW)
assert r.assessment.risk_level is RuntimeRiskLevel.NORMAL, r.assessment.risk_level
assert ENV not in store.export(TENANT).revoked_envelopes

# Cumulative breach: 6x9000 = 54000 > 50000 -> ESCALATED -> real targeted revoke.
last = None
for i in range(2, 8):
    last = service.observe(obs(i, 9000.0), produced_at=NOW)
assert last.outcome is AssessmentOutcome.SIGNAL_REASSESS, last.outcome
assert last.handoff is not None and last.handoff.submitted
assert ENV in store.export(TENANT).revoked_envelopes, "RA-6 did not revoke the envelope"

# Duplicate observation is idempotent.
dup = service.observe(obs(2, 9000.0), produced_at=NOW)
assert dup.outcome is AssessmentOutcome.IGNORE_EVENT

# F-1: production refuses the reference telemetry authenticator.
try:
    TrustedTelemetryIngress(ReferenceTelemetryAuthenticator(), production_mode=True)
    raise AssertionError("production accepted a reference authenticator (F-1)")
except ReferenceIngressRejectedError:
    pass

# risk_authority stays a stdlib-only leaf.
import risk_authority  # noqa: F401

# No out-of-scope monorepo package importable (esp. the Agent Runtime).
for forbidden in ("symbolu", "ugence_agent_runtime", "ugence_risk_authority_runtime",
                  "ugence_risk_authority_evidence_runtime", "ugence_decision_authority",
                  "ugence_actiongate_provider", "ugence_tap_provider"):
    try:
        importlib.import_module(forbidden)
    except ImportError:
        continue
    raise SystemExit(f"FAIL: out-of-scope package importable: {forbidden}")

print("OK: runtime-assurance installed from declared deps; RA-7 observe->signal->RA-6 "
      "revoke enforced; boundaries clean")
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
              "--find-links", str(wheelhouse), "ugence-risk-authority-runtime-assurance"])

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
