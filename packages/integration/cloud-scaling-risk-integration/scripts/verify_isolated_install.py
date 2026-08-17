#!/usr/bin/env python3
"""Reproducible proof that ``ugence-cloud-scaling-risk-integration`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no monorepo
path.

This is an *integration* package, so — unlike the zero-dependency Risk Authority leaf —
it legitimately depends on two first-party wheels (cloud-scaling-controller,
risk-authority). The verifier therefore builds a local wheelhouse of those FIRST-PARTY
wheels and installs the adapter from it, allowing only third-party wheels (numpy, a
controller dependency) from the index.

It then proves, inside that clean environment:

  * ``ugence_cloud_scaling_risk_integration`` imports from site-packages, not the repo;
  * the D-4 ratified identifiers are exactly the owner-ratified strings;
  * the D-6 idempotency key reproduces the ADR §5.3 worked-example digest;
  * a genuine recommendation authenticates, projects, and reconciles — and the
    installed code produces the SAME context / subject / request digests as the source
    tree (the digests are passed in as expected values, so a divergence fails here);
  * content tampering with a stale carried digest is REJECTED;
  * an in-process object with no independent digest expectation is REJECTED;
  * an expired recommendation never reaches the seam;
  * an abstention never reaches the seam and manufactures no subject digest;
  * every execution/authorization flag is False, and a forged True is rejected;
  * NO envelope issuer, ActionGate, credential or execution symbol is reachable;
  * NO out-of-scope monorepo package (symbolu/agentic/apps/…) is importable.

Run:  python packages/integration/cloud-scaling-risk-integration/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/cloud-scaling-risk-integration -> repo

# First-party wheels the adapter needs, built locally into the wheelhouse.
FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller",
    PKG,
]

# The controller's Phase-3 test builders, copied into the clean environment so the probe
# can construct a GENUINE recommendation there. Only the builders travel — the adapter
# itself comes exclusively from the installed wheel.
CONTROLLER_HELPERS = (
    REPO / "packages" / "capabilities" / "cloud-scaling-controller"
    / "tests" / "planning" / "ph_helpers.py"
)

_PROBE = r'''
import importlib, json, pathlib, sys
from datetime import timedelta

EXPECTED = json.loads(sys.argv[1])

# 1. The adapter must come from site-packages, not the repository checkout.
import ugence_cloud_scaling_risk_integration as adapter_pkg
loc = pathlib.Path(adapter_pkg.__file__).resolve()
assert "site-packages" in loc.parts, f"not installed from site-packages: {loc}"
assert adapter_pkg.__version__ == EXPECTED["version"], adapter_pkg.__version__

from ugence_cloud_scaling_risk_integration import (
    AdapterOutcomeStatus, AdapterRejectionReason, CloudScalingRiskAdapter,
    CANONICAL_ACTION_TYPES, DOMAIN_CLOUD_SCALING, PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT, authenticate_controller_output,
    build_idempotency_key, project_recommendation,
)

# 2. D-4 ratified identifiers, exact.
assert PURPOSE_CAPACITY_ACTION == "cloud_scaling.capacity_action"
assert DOMAIN_CLOUD_SCALING == "cloud_scaling"
assert SUBJECT_TYPE_CAPACITY_SUBJECT == "cloud_scaling.capacity_subject"
assert CANONICAL_ACTION_TYPES == frozenset(
    {"no_change", "scale_up", "scale_down", "coordinated"})

# 3. D-6 idempotency reproduces the ADR §5.3 worked example.
assert build_idempotency_key(
    tenant_id="tnt-acme",
    subject_id="wl-checkout-api",
    recommendation_digest="sha256:" + "1" * 64,
) == "sha256:42aaa799941a6661c39c3dbe45ea7e7b2ecfcc5d617a9fc09ee32cbbe8959dd0"

# 4. Build a GENUINE recommendation with the controller's own pipeline.
import ph_helpers as H
from ugence_cloud_scaling_controller.planning import recommend_capacity_action
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
)

subject = H.subject()
rec = recommend_capacity_action(
    H.build_forecast_evidence(9, subj=subject),
    H.replicas_state(H.at(180.0), 6, subj=subject),
    H.cost_book(subj=subject),
    H.constraints(),
    H.policy(),
    recommendation_time=H.at(190.0),
    validity_seconds=300.0,
    recommendation_id="rec-phase4c-1",
)
assert isinstance(rec, CapacityActionRecommendation), type(rec).__name__

document = rec.to_canonical_dict()
projection = project_recommendation(authenticate_controller_output(document))

# 5. INSTALLED behavior must equal SOURCE behavior, digest for digest.
assert projection.recommendation_digest == EXPECTED["recommendation_digest"], (
    "installed recommendation digest diverges from source")
assert projection.context_digest == EXPECTED["context_digest"], (
    "installed context digest diverges from source")
assert projection.subject_digest == EXPECTED["subject_digest"], (
    "installed subject digest diverges from source")
assert projection.request_digest == EXPECTED["request_digest"], (
    "installed request digest diverges from source")
assert projection.idempotency_key == EXPECTED["idempotency_key"], (
    "installed idempotency key diverges from source")
assert list(projection.evidence_references) == EXPECTED["evidence_references"]
assert projection.request.evaluation_time is None

# 6. Risk Authority's own Phase 4B validation reconciles what the adapter produced.
from risk_authority.integrations import validate_subject_binding
validation = validate_subject_binding(projection.request)
assert validation.subject_digest == projection.subject_digest
assert validation.authority_granted is False and validation.executable is False

# --- fail-closed behavior, from the installed wheel ---------------------------------

class ForbiddenSeam:
    reached = False
    def evaluate(self, request):
        ForbiddenSeam.reached = True
        raise AssertionError("the seam was reached despite a failed adapter gate")

FIXED_NOW = H.at(300.0)
adapter = CloudScalingRiskAdapter(seam=ForbiddenSeam(), clock=lambda: FIXED_NOW)

# 7. Content tampering with a stale carried digest is rejected.
tampered = dict(document)
tampered["recommendation_id"] = "rec-TAMPERED"
outcome = adapter.evaluate(tampered)
assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
assert outcome.rejection_reason is AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH

# 8. A live object with no independent expectation is rejected (no self-referential check).
outcome = adapter.evaluate(rec)
assert outcome.rejection_reason is (
    AdapterRejectionReason.MISSING_INDEPENDENT_RECOMMENDATION_DIGEST)

# 9. An expired recommendation never reaches the seam.
expired = CloudScalingRiskAdapter(
    seam=ForbiddenSeam(), clock=lambda: H.at(190.0) + timedelta(days=1))
outcome = expired.evaluate(document)
assert outcome.rejection_reason is AdapterRejectionReason.RECOMMENDATION_EXPIRED

# 10. An abstention never reaches the seam and manufactures no subject digest.
abstained = recommend_capacity_action(
    H.build_abstained_forecast(subj=subject),
    H.replicas_state(H.at(180.0), 6, subj=subject),
    H.cost_book(subj=subject), H.constraints(), H.policy(),
    recommendation_time=H.at(190.0), validity_seconds=300.0)
outcome = adapter.evaluate(abstained.to_canonical_dict())
assert outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM
assert outcome.projection is None and outcome.recommendation_digest is None
assert outcome.abstention_reason == abstained.reason.value

assert ForbiddenSeam.reached is False, "a failed gate still reached the seam"

# 11. Every execution/authorization flag is False, and a forged True is rejected.
from ugence_cloud_scaling_risk_integration import (
    CloudScalingRiskOutcome, NonExecutableInvariantError,
)
for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
             "credential_issued", "actuation_performed", "effect_verified", "executable"):
    assert getattr(outcome, flag) is False
    try:
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_REJECTED,
            rejection_reason=AdapterRejectionReason.PROJECTION_FAILED,
            **{flag: True},
        )
    except NonExecutableInvariantError:
        pass
    else:
        raise AssertionError(f"a forged {flag}=True was accepted")
assert outcome.grants_authority is False

# 12. No Phase 5/6 capability is reachable from the public surface.
for name in adapter_pkg.__all__:
    lowered = name.lower()
    for forbidden in ("envelope", "authorize", "actiongate", "credential", "execute",
                      "actuate", "broker"):
        assert forbidden not in lowered, name

# 13. No out-of-scope monorepo package is importable.
for module in ("symbolu", "agentic", "cloud_scaling_operations",
               "ugence_risk_authority_runtime", "ugence_decision_authority",
               "ugence_actiongate_provider", "ugence_agent_runtime"):
    try:
        importlib.import_module(module)
    except ImportError:
        pass
    else:
        raise AssertionError(f"out-of-scope package is importable: {module}")

print("INSTALLED-WHEEL PHASE 4C ADAPTER VERIFICATION OK")
'''


def run(cmd, **kwargs):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def source_expectations() -> dict:
    """Compute the expected values from the SOURCE tree.

    They are passed into the clean environment so the probe compares installed behavior
    against source behavior rather than merely against itself.
    """

    for path in (
        PKG / "src",
        REPO / "packages" / "risk_authority" / "src",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
        CONTROLLER_HELPERS.parent,
    ):
        sys.path.insert(0, str(path))

    import ph_helpers as H  # type: ignore[import-not-found]
    from ugence_cloud_scaling_controller.planning import recommend_capacity_action

    from ugence_cloud_scaling_risk_integration import (  # noqa: E402
        __version__,
        authenticate_controller_output,
        project_recommendation,
    )

    subject = H.subject()
    rec = recommend_capacity_action(
        H.build_forecast_evidence(9, subj=subject),
        H.replicas_state(H.at(180.0), 6, subj=subject),
        H.cost_book(subj=subject),
        H.constraints(),
        H.policy(),
        recommendation_time=H.at(190.0),
        validity_seconds=300.0,
        recommendation_id="rec-phase4c-1",
    )
    projection = project_recommendation(
        authenticate_controller_output(rec.to_canonical_dict())
    )
    return {
        "version": __version__,
        "recommendation_digest": projection.recommendation_digest,
        "context_digest": projection.context_digest,
        "subject_digest": projection.subject_digest,
        "request_digest": projection.request_digest,
        "idempotency_key": projection.idempotency_key,
        "evidence_references": list(projection.evidence_references),
    }


def main() -> int:
    expected = source_expectations()
    print("source expectations:")
    for key, value in expected.items():
        print(f"  {key} = {value}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()
        env_dir = tmp_path / "env"

        print("\n--- building first-party wheels ---", flush=True)
        for project in FIRST_PARTY:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse),
                 str(project)])

        print("\n--- creating a clean virtualenv ---", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / "bin" / "python"
        if not python.exists():  # pragma: no cover - Windows layout
            python = env_dir / "Scripts" / "python.exe"

        print("\n--- installing the adapter from the wheelhouse ---", flush=True)
        run([str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        run([str(python), "-m", "pip", "install", "--quiet",
             "--find-links", str(wheelhouse),
             "ugence-cloud-scaling-risk-integration"])

        # The controller's Phase-3 builders are test-only and are not shipped in any
        # wheel; copy just that module so the probe can build a genuine recommendation.
        probe_dir = tmp_path / "probe"
        probe_dir.mkdir()
        (probe_dir / "ph_helpers.py").write_text(
            CONTROLLER_HELPERS.read_text(encoding="utf-8"), encoding="utf-8"
        )
        probe_file = probe_dir / "probe.py"
        probe_file.write_text(_PROBE, encoding="utf-8")

        print("\n--- running the isolated behavior probe ---", flush=True)
        # cwd is the probe directory and NOT the repository, so nothing can be imported
        # from the monorepo checkout.
        run([str(python), str(probe_file), json.dumps(expected)], cwd=str(probe_dir))

    print("\nISOLATED PHASE 4C ADAPTER DISTRIBUTION VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
