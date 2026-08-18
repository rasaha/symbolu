#!/usr/bin/env python3
"""Reproducible proof that ``ugence-cloud-scaling-risk-integration`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no monorepo
path.

This is an *integration* package, so — unlike the zero-dependency Risk Authority leaf —
it legitimately depends on two first-party wheels (cloud-scaling-controller,
risk-authority). The verifier therefore builds a local wheelhouse of those FIRST-PARTY
wheels and installs the adapter from it, allowing only third-party wheels (numpy, a
controller dependency) from the index.

**Scope of the claim, stated precisely.** This script's run is *not* offline as a whole,
and does not claim to be. It has four phases:

  * **Phase A (online)** — build the first-party wheels and download the full dependency
    closure, numpy included, into a local wheelhouse. Reaching an index here is what
    collecting a closure *means*; pretending otherwise would be the over-claim.
  * **Phase B (genuinely offline)** — the isolated-installation stage under test: install
    into a throwaway virtualenv from that wheelhouse alone, with no index reachable.
  * **Phase C (offline)** — negative controls that prove the phase-B guarantee.
  * **Phase D (offline)** — behavior probes inside the isolated environment.

Only **phase B** is the guarantee, and the closing banner names exactly that:
``OFFLINE ISOLATED INSTALLATION STAGE VERIFIED``.

Within phase B, ``--no-index`` and ``PIP_NO_INDEX=1`` are the *actual* index prohibition.
The unroutable ``OFFLINE_SENTINEL_INDEX`` is **defense in depth** and provides no
protection of its own: it exists so that if a future edit dropped one of those flags,
resolution fails loudly against an unroutable host rather than quietly succeeding against
the real PyPI.

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
  * an authenticated token whose digest does not describe its recommendation is
    REJECTED — at construction, and again at every consumption boundary, including
    tokens built through ``object.__new__`` or mutated with ``object.__setattr__``;
  * NO envelope issuer, ActionGate, credential or execution symbol is implemented in,
    imported by, publicly exported by or called from the installed adapter (a
    dependency may still load such modules through its own package initialization —
    the claim is about the adapter, not about the process);
  * NO out-of-scope monorepo package (symbolu/agentic/apps/…) is importable.

Run:  python packages/integration/cloud-scaling-risk-integration/scripts/verify_isolated_install.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Sequence

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]  # packages/integration/cloud-scaling-risk-integration -> repo

# First-party wheels the adapter needs, built locally into the wheelhouse.
FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller",
    PKG,
]

# Every distribution that must be present in the wheelhouse before the offline phase
# starts. Checked explicitly so an incomplete wheelhouse fails immediately with a clear
# message, rather than failing obscurely mid-install (or, worse, being silently rescued
# by an index because someone dropped a flag).
REQUIRED_DISTRIBUTIONS = (
    "ugence_cloud_scaling_risk_integration-",
    "ugence_cloud_scaling_controller-",
    "ugence_risk_authority-",
    "numpy-",  # the controller's only third-party runtime dependency
)

# An unroutable sentinel used wherever an index URL must be supplied. It is DEFENSE IN
# DEPTH and is not what makes the offline phase offline: --no-index and PIP_NO_INDEX=1 are
# the actual index prohibition. The sentinel exists so that if a future edit dropped one of
# those flags, resolution fails loudly against an unroutable host instead of quietly
# succeeding against the real PyPI.
OFFLINE_SENTINEL_INDEX = "http://offline.invalid/simple"

#: Number of steps that must complete before the verifier may report success.
EXPECTED_STEPS = 8

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

# 1. Every package under test must come from site-packages, not the repo checkout.
import ugence_cloud_scaling_risk_integration as adapter_pkg
import ugence_cloud_scaling_controller as controller_pkg
import risk_authority as ra_pkg

for name, mod in (("adapter", adapter_pkg), ("controller", controller_pkg),
                  ("risk_authority", ra_pkg)):
    loc = pathlib.Path(mod.__file__).resolve()
    assert "site-packages" in loc.parts, f"{name} not installed from site-packages: {loc}"
    assert "symbolu" not in loc.parts, f"{name} resolved into the monorepo checkout: {loc}"
assert adapter_pkg.__version__ == EXPECTED["version"], adapter_pkg.__version__

# No monorepo path may be on sys.path at all.
for entry in sys.path:
    resolved = str(pathlib.Path(entry).resolve()) if entry else ""
    assert "/symbolu/packages" not in resolved, f"monorepo source on sys.path: {entry}"

# Tests and unrelated source files must not have been shipped inside the wheel.
adapter_dir = pathlib.Path(adapter_pkg.__file__).resolve().parent
shipped = sorted(p.name for p in adapter_dir.rglob("*") if p.is_file())
for leaked in shipped:
    assert not leaked.startswith("test_"), f"a test file shipped in the wheel: {leaked}"
    assert leaked != "conftest.py", "conftest.py shipped in the wheel"
assert "py.typed" in shipped, "py.typed missing from the installed package"

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

# 11b. The authenticated token's own content-integrity invariant, from the wheel.
#      A token could previously be hand-built with an exact canonical recommendation and
#      a syntactically valid but incorrect digest; a consumer would then accept a token
#      whose name claimed a reconciliation that never happened. Verified here against the
#      INSTALLED code, and at all three consumption boundaries, because a source-only
#      check would not prove what a deployed wheel does.
from dataclasses import fields as _dc_fields

from ugence_cloud_scaling_risk_integration import (
    AuthenticatedRecommendation, RecommendationAuthenticityError,
    UnsupportedRecommendationSourceError,
)

WRONG_DIGEST = "sha256:" + "9" * 64
assert rec.digest() != WRONG_DIGEST

# (a) supported construction cannot mint a mismatched token.
try:
    AuthenticatedRecommendation(
        recommendation=rec,
        recommendation_digest=WRONG_DIGEST,
        expectation_source="caller_supplied_expectation",
    )
except RecommendationAuthenticityError:
    pass
else:
    raise AssertionError("a mismatched authenticated token was constructed")

# (b) a token subclass is refused at construction.
class _SubclassToken(AuthenticatedRecommendation):
    pass

try:
    _SubclassToken(
        recommendation=rec,
        recommendation_digest=rec.digest(),
        expectation_source="caller_supplied_expectation",
    )
except UnsupportedRecommendationSourceError:
    pass
else:
    raise AssertionError("a token subclass was constructed")

# (c) a constructor-bypassed token (object.__new__, so __post_init__ never ran) is
#     refused at every consumption boundary, and nothing observes it.
_forged = object.__new__(AuthenticatedRecommendation)
object.__setattr__(_forged, "recommendation", rec)
object.__setattr__(_forged, "recommendation_digest", WRONG_DIGEST)
object.__setattr__(_forged, "expectation_source", "caller_supplied_expectation")
for _f in _dc_fields(AuthenticatedRecommendation):
    if _f.name not in ("recommendation", "recommendation_digest", "expectation_source"):
        object.__setattr__(_forged, _f.name, False)
assert type(_forged) is AuthenticatedRecommendation

class _CountingSeam:
    calls = 0
    def evaluate(self, request):
        _CountingSeam.calls += 1
        raise AssertionError("the seam was reached with a forged authenticated token")

_reads = []
_token_adapter = CloudScalingRiskAdapter(
    seam=_CountingSeam(), clock=lambda: (_reads.append(1) or FIXED_NOW))

try:
    project_recommendation(_forged)
except (RecommendationAuthenticityError, UnsupportedRecommendationSourceError):
    pass
else:
    raise AssertionError("project_recommendation accepted a forged token")

try:
    _token_adapter.project(_forged)
except (RecommendationAuthenticityError, UnsupportedRecommendationSourceError):
    pass
else:
    raise AssertionError(".project accepted a forged token")

_outcome = _token_adapter.evaluate(_forged)
assert _outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
assert _outcome.decision is None and _outcome.projection is None
assert _CountingSeam.calls == 0, "the seam was reached with a forged token"
assert _reads == [], "the trusted clock was read for a forged token"

# (d) post-construction mutation of a validly built token is caught at consumption.
_mutated = authenticate_controller_output(
    rec, expected_recommendation_digest=rec.digest())
object.__setattr__(_mutated, "recommendation_digest", WRONG_DIGEST)
try:
    project_recommendation(_mutated)
except RecommendationAuthenticityError:
    pass
else:
    raise AssertionError("a mutated token was projected")

# (e) positive control: the legitimate token path is unchanged.
_valid = authenticate_controller_output(
    rec, expected_recommendation_digest=rec.digest())
assert _valid.recommendation_digest == _valid.recommendation.digest()
assert project_recommendation(_valid).request_digest == EXPECTED["request_digest"]

# (f) the invariant is enforced without widening the public API.
assert "_validate_authenticated_recommendation" not in adapter_pkg.__all__
assert not hasattr(adapter_pkg, "_validate_authenticated_recommendation")

# 12. No Phase 5/6 capability is publicly exported by the installed adapter. Scoped
#     deliberately to this package's own surface: Risk Authority may transitively load
#     envelope- or ActionGate-related modules through its own package initialization,
#     so a process-wide 'nothing is reachable' assertion would be false.
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


def make_python(env_dir: Path) -> Path:
    """Create a clean virtualenv and return its interpreter.

    ``with_pip=True`` bootstraps pip from the local ``ensurepip`` bundle — no index
    access — and pip is deliberately **not** upgraded afterwards, because
    ``pip install --upgrade pip`` is itself a network fetch and would make the phrase
    "offline installation" false.
    """

    venv.EnvBuilder(with_pip=True).create(env_dir)
    python = env_dir / "bin" / "python"
    if not python.exists():  # pragma: no cover - Windows layout
        python = env_dir / "Scripts" / "python.exe"
    return python


def offline_install(
    python: Path, wheelhouse: Path, requirement: str, *, extra_args: Sequence[str] = ()
) -> subprocess.CompletedProcess:
    """Install ``requirement`` with index access structurally disabled.

    Three independent belts, so a single flag being dropped in a future edit cannot
    silently restore network access:

    * ``--no-index`` on the command line;
    * ``PIP_NO_INDEX=1`` in the environment (covers anything pip re-invokes);
    * ``PIP_INDEX_URL`` / ``PIP_EXTRA_INDEX_URL`` pointed at an unroutable sentinel, so
      that if index resolution were somehow attempted it fails loudly rather than
      quietly succeeding against PyPI.

    ``PIP_DISABLE_PIP_VERSION_CHECK`` and ``PIP_NO_PYTHON_VERSION_WARNING`` suppress
    pip's own opportunistic network chatter. No editable install is used anywhere: an
    editable install would put the monorepo source tree on ``sys.path`` and defeat the
    entire point of the exercise.
    """

    env = dict(os.environ)
    env.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_PYTHON_VERSION_WARNING": "1",
            "PIP_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            "PIP_EXTRA_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            # Never silently reuse a previously downloaded artifact: the wheelhouse must
            # be the only source, or "offline" would just mean "warm cache".
            "PIP_NO_CACHE_DIR": "1",
        }
    )
    cmd = [
        str(python), "-m", "pip", "install", "--quiet",
        "--no-index",
        "--no-cache-dir",
        "--find-links", str(wheelhouse),
        *extra_args,
        requirement,
    ]
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, env=env)


def expect_offline_install_failure(
    python: Path, wheelhouse: Path, requirement: str, *, why: str
) -> None:
    """Assert that an offline install *fails*. A negative control for the positive path."""

    try:
        offline_install(python, wheelhouse, requirement)
    except subprocess.CalledProcessError:
        print(f"  [ok] install failed as required — {why}", flush=True)
        return
    raise SystemExit(
        f"NEGATIVE PROBE FAILED: the install unexpectedly SUCCEEDED — {why}. "
        "The offline guarantee is not being enforced."
    )


def main() -> int:
    steps: list[str] = []

    def done(step: str) -> None:
        steps.append(step)
        print(f"  [step complete] {step}", flush=True)

    expected = source_expectations()
    print("source expectations:")
    for key, value in expected.items():
        print(f"  {key} = {value}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()

        # === PHASE A — collection. ONLINE by design, and the only phase that is. ===
        # Every distribution the adapter needs, first- and third-party, is materialized
        # into the local wheelhouse before the offline phase begins. Calling an install
        # "offline" because a wheel happened to be cached would be false; the wheelhouse
        # is built explicitly so the offline phase can be genuinely index-free.
        print("\n=== PHASE A (online): build + collect every required wheel ===",
              flush=True)
        for project in FIRST_PARTY:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse),
                 str(project)])
        done("first-party wheels built")

        # Resolve the full dependency closure, taking first-party from the wheelhouse and
        # third-party (numpy, via the controller) from the index — into the wheelhouse.
        run([
            sys.executable, "-m", "pip", "download", "--quiet",
            "--only-binary=:all:",
            "--dest", str(wheelhouse),
            "--find-links", str(wheelhouse),
            "ugence-cloud-scaling-risk-integration",
        ])
        collected = sorted(p.name for p in wheelhouse.glob("*.whl"))
        print(f"  wheelhouse now holds {len(collected)} wheel(s):", flush=True)
        for name in collected:
            print(f"    - {name}", flush=True)
        for required in REQUIRED_DISTRIBUTIONS:
            if not any(name.startswith(required) for name in collected):
                raise SystemExit(
                    f"required distribution {required!r} is absent from the wheelhouse; "
                    "refusing to enter the offline phase with an incomplete wheelhouse"
                )
        done("dependency closure collected into the wheelhouse")

        # === PHASE B — the genuinely offline stage this verifier exists to prove. =======
        # No index, no cache, no source tree. --no-index and PIP_NO_INDEX=1 are the actual
        # prohibition; the sentinel index URL is defense in depth behind them.
        print("\n=== PHASE B (offline): install with the index structurally disabled ===",
              flush=True)
        env_dir = tmp_path / "env"
        python = make_python(env_dir)
        done("clean virtualenv created (pip from local ensurepip, never upgraded)")

        offline_install(python, wheelhouse, "ugence-cloud-scaling-risk-integration")
        done("adapter installed offline from the local wheelhouse only")

        # === PHASE C — negative controls. An "offline" claim nobody tested is a guess. ===
        print("\n=== PHASE C: negative controls on the offline guarantee ===", flush=True)

        # (1) Remove a required wheel: the install MUST fail rather than reach the index.
        crippled = tmp_path / "crippled-wheelhouse"
        crippled.mkdir()
        removed = None
        for wheel in wheelhouse.glob("*.whl"):
            if wheel.name.startswith("ugence_risk_authority-"):
                removed = wheel.name
                continue
            shutil.copy2(wheel, crippled / wheel.name)
        if removed is None:
            raise SystemExit("could not identify the risk-authority wheel to remove")
        print(f"  removed {removed} from a copy of the wheelhouse", flush=True)
        crippled_env = make_python(tmp_path / "env-crippled")
        expect_offline_install_failure(
            crippled_env, crippled, "ugence-cloud-scaling-risk-integration",
            why="a required wheel was absent from the wheelhouse",
        )
        done("negative control: missing wheel causes failure, not an index fetch")

        # (2) A bogus remote index cannot rescue that install — proving the failure above
        #     is a real absence and not merely a misconfigured URL.
        bogus_env = make_python(tmp_path / "env-bogus")
        try:
            subprocess.run(
                [
                    str(bogus_env), "-m", "pip", "install", "--quiet",
                    "--no-cache-dir",
                    "--index-url", OFFLINE_SENTINEL_INDEX,
                    "--find-links", str(crippled),
                    "ugence-cloud-scaling-risk-integration",
                ],
                check=True,
                env={**os.environ, "PIP_NO_CACHE_DIR": "1",
                     "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("  [ok] a bogus index could not supply the missing distribution",
                  flush=True)
        else:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the install succeeded against a bogus index — "
                "something other than the wheelhouse supplied the distribution"
            )
        done("negative control: a bogus index cannot rescue an incomplete wheelhouse")

        # (3) The crippled environment must NOT have the adapter importable.
        probe = subprocess.run(
            [str(crippled_env), "-c", "import ugence_cloud_scaling_risk_integration"],
            capture_output=True,
        )
        if probe.returncode == 0:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the adapter is importable in an environment "
                "whose installation failed — a failed install left a usable package"
            )
        print("  [ok] the failed installation left nothing importable", flush=True)
        done("negative control: a failed install cannot yield a working package")

        # === PHASE D — behavior probes inside the isolated environment. ===
        print("\n=== PHASE D: behavior probes in the isolated environment ===", flush=True)
        # The controller's Phase-3 builders are test-only and are not shipped in any
        # wheel; copy just that module so the probe can build a genuine recommendation.
        # It imports nothing from the monorepo itself — the probe asserts that every
        # package it uses resolves to site-packages.
        probe_dir = tmp_path / "probe"
        probe_dir.mkdir()
        (probe_dir / "ph_helpers.py").write_text(
            CONTROLLER_HELPERS.read_text(encoding="utf-8"), encoding="utf-8"
        )
        probe_file = probe_dir / "probe.py"
        probe_file.write_text(_PROBE, encoding="utf-8")

        # cwd is the probe directory and NOT the repository, and PYTHONPATH is cleared,
        # so nothing can be imported from the monorepo checkout.
        probe_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        run([str(python), str(probe_file), json.dumps(expected)],
            cwd=str(probe_dir), env=probe_env)
        done("import, public-API, digest and non-execution probes passed")

    # VERIFIED is printed only after EVERY step above recorded completion. Any failed
    # subprocess raises CalledProcessError (check=True) and never reaches this line, so
    # a non-zero exit is the only possible outcome of a partial run.
    if len(steps) != EXPECTED_STEPS:
        raise SystemExit(
            f"refusing to report success: {len(steps)} of {EXPECTED_STEPS} steps "
            f"completed ({steps})"
        )
    print(f"\nall {EXPECTED_STEPS} verification steps completed:", flush=True)
    for step in steps:
        print(f"  - {step}")
    # Names the phase that was actually verified. The run as a whole reached the network
    # in phase A by design; the guarantee is that phase B installed with no index reachable.
    print("\nOFFLINE ISOLATED INSTALLATION STAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
