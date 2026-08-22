#!/usr/bin/env python3
"""Reproducible proof that ``ugence-cloud-scaling-authorization-contracts`` installs and
operates from its DECLARED dependencies alone, in a fresh virtualenv with no monorepo path.

Follows the proven Phase 4C pattern exactly, including its honesty about what is offline.

**Scope of the claim, stated precisely.** This script's run is *not* offline as a whole,
and does not claim to be. It has four phases:

  * **Phase A (online)** — build the first-party wheels and download the full dependency
    closure, numpy included, into a local wheelhouse. Reaching an index here is what
    collecting a closure *means*; pretending otherwise would be the over-claim.
  * **Phase B (genuinely offline)** — the isolated-installation stage under test: install
    into a throwaway virtualenv from that wheelhouse alone, with no index reachable.
  * **Phase C (offline)** — negative controls that prove the phase-B guarantee.
  * **Phase D (offline)** — behavior probes inside the isolated environment.

Only **phase B** is the guarantee, and the closing banner names exactly that.

Within phase B, ``--no-index`` and ``PIP_NO_INDEX=1`` are the *actual* index prohibition.
The unroutable ``OFFLINE_SENTINEL_INDEX`` is **defense in depth** and provides no
protection of its own: it exists so that if a future edit dropped one of those flags,
resolution fails loudly against an unroutable host rather than quietly succeeding against
the real PyPI. No editable install is used anywhere.

It then proves, inside that clean environment:

  * the package imports from site-packages, not the repo checkout;
  * the exact public API matches the source tree, symbol for symbol;
  * the D-4 identifiers are exactly the ratified strings;
  * a genuine chain produces the SAME frozen digests as the source tree — the source
    digests are passed in as expected values, so any divergence fails here;
  * every rejection behaviour still rejects inside the wheel (cross-tenant, non-ALLOW,
    forged decision digest, foreign attestation, magnitude and delta escalation,
    forged trust state, subclass and ``object.__new__`` fabrication);
  * the candidate carries NO authority field and reports ``grants_authority`` False;
  * NO envelope, ActionGate, credential, executor, Decision Authority or clock symbol is
    implemented in, imported by, exported from or callable in the installed package;
  * NO test, fixture or ``conftest.py`` leaked into the wheel;
  * NO out-of-scope monorepo package is importable.

Run:  python packages/integration/cloud-scaling-authorization-contracts/scripts/verify_isolated_install.py
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
REPO = PKG.parents[2]

FIRST_PARTY = [
    REPO / "packages" / "risk_authority",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration",
    PKG,
]

REQUIRED_DISTRIBUTIONS = (
    "ugence_cloud_scaling_authorization_contracts-",
    "ugence_cloud_scaling_risk_integration-",
    "ugence_cloud_scaling_controller-",
    "ugence_risk_authority-",
    "numpy-",
)

OFFLINE_SENTINEL_INDEX = "http://offline.invalid/simple"

EXPECTED_STEPS = 8

CONTROLLER_HELPERS = (
    REPO / "packages" / "capabilities" / "cloud-scaling-controller"
    / "tests" / "planning" / "ph_helpers.py"
)

_PROBE = r'''
import dataclasses, hashlib, importlib, json, pathlib, sys
from datetime import datetime, timezone

EXPECTED = json.loads(sys.argv[1])

# --- 1. every package under test resolves to site-packages, not the repo checkout -------
import ugence_cloud_scaling_authorization_contracts as p5a
import ugence_cloud_scaling_risk_integration as p4c
import ugence_cloud_scaling_controller as controller
import risk_authority as ra

for name, mod in (("phase5a", p5a), ("phase4c", p4c), ("controller", controller), ("ra", ra)):
    location = pathlib.Path(mod.__file__).resolve()
    if "site-packages" not in location.parts:
        raise AssertionError(f"{name} did not come from site-packages: {location}")

if p5a.__version__ != EXPECTED["version"]:
    raise AssertionError(f"version {p5a.__version__} != {EXPECTED['version']}")

# --- 2. exact public API parity with the source tree ------------------------------------
installed_api = sorted(p5a.__all__)
if installed_api != sorted(EXPECTED["public_api"]):
    missing = set(EXPECTED["public_api"]) - set(installed_api)
    extra = set(installed_api) - set(EXPECTED["public_api"])
    raise AssertionError(f"public API drift: missing={sorted(missing)} extra={sorted(extra)}")
for symbol in installed_api:
    if not hasattr(p5a, symbol):
        raise AssertionError(f"{symbol} is exported but absent")

# --- 3. D-4 identifiers are the ratified strings -----------------------------------------
assert p5a.PURPOSE_CAPACITY_ACTION == "cloud_scaling.capacity_action"
assert p5a.DOMAIN_CLOUD_SCALING == "cloud_scaling"
assert p5a.SUBJECT_TYPE_CAPACITY_SUBJECT == "cloud_scaling.capacity_subject"
assert p5a.CANONICAL_ACTION_TYPES == frozenset(
    {"no_change", "scale_up", "scale_down", "coordinated"}
)

# --- 4. exactly one trust state, and it is the unverified one ---------------------------
states = list(p5a.EvidenceTrustState)
if len(states) != 1 or states[0].value != "PRESENT_BUT_NOT_TRUST_VERIFIED":
    raise AssertionError(f"trust vocabulary drift: {states}")

# --- 5. build the genuine chain inside the wheel and match the SOURCE digests ------------
import ph_helpers as H
from risk_authority.crypto import SigningKey, canonical_bytes
from ugence_cloud_scaling_controller.canonical.identity import CapacitySubject
from ugence_cloud_scaling_controller.planning import recommend_capacity_action

subject = CapacitySubject(
    workload_id="checkout-api", tenant_id="tenant-1", resource_id="deploy/checkout-api",
    environment="prod", cluster="prod-us-east-1-blue", region="us-east-1", zone="us-east-1a",
)
rec = recommend_capacity_action(
    H.build_forecast_evidence(9, subj=subject),
    H.replicas_state(H.at(180.0), 6, subj=subject),
    H.cost_book(subj=subject), H.constraints(), H.policy(),
    recommendation_time=H.at(190.0), validity_seconds=300.0,
    recommendation_id="rec-phase5a-1",
)
projection = p4c.project_recommendation(
    p4c.authenticate_controller_output(
        rec, expected_recommendation_digest=rec.to_canonical_dict()["evidence_digest"]
    )
)
for key in ("recommendation_digest", "context_digest", "subject_digest", "request_digest",
            "idempotency_key"):
    actual = getattr(projection, key)
    if actual != EXPECTED[key]:
        raise AssertionError(f"{key}: installed {actual} != source {EXPECTED[key]}")

# A genuine decision through the real reference seam.
from risk_authority.api.evaluation_seam import RiskEvaluationSeam
from risk_authority.crypto import SigningKeyRecord
from risk_authority.domain import (
    Predicate, PredicateOp, RuleEffect, WorkflowIR, WorkflowRule, WorkflowStatus,
)
from risk_authority.integrations import (
    InMemoryWorkflowIRSource, ReferenceSubjectAwarePolicyResolver, SubjectRiskDecision,
    SubjectRiskDisposition,
)

workflow = WorkflowIR(
    workflow_ir_id="cloud-scaling-risk", version="1.0.0", status=WorkflowStatus.ACTIVE,
    rules=(WorkflowRule(rule_id="CS-1",
                        conditions=(Predicate("domain", PredicateOp.EQ, "cloud_scaling"),),
                        required_controls=(), effect=RuleEffect.ALLOW_IF_ALL),),
    source_refs=("ADR-CLOUD-SCALING-P5",),
    effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
).with_digest()
source = InMemoryWorkflowIRSource()
source.register(workflow)
seam = RiskEvaluationSeam.reference(
    workflow_source=source,
    key_record=SigningKeyRecord("cs-key", SigningKey.from_seed(bytes(range(32)))),
    clock=lambda: H.at(300.0),
    policy_resolver=ReferenceSubjectAwarePolicyResolver(
        by_purpose_domain={("cloud_scaling.capacity_action", "cloud_scaling"): workflow}
    ),
)
decision = seam.evaluate(projection.request)
if decision.decision_digest != EXPECTED["decision_digest"]:
    raise AssertionError("decision_digest diverged inside the wheel")


def make_attestation(recommendation_digest, **over):
    payload = {
        "schema_version": "cloud-scaling-producer-attestation-evidence-1",
        "producer_id": over.get("producer_id", "ugence.cloud-scaling-controller"),
        "producer_key_id": "producer-attestation-key-1",
        "signature_algorithm": "ed25519",
        "signing_purpose": over.get("signing_purpose", p5a.PRODUCER_SIGNING_PURPOSE),
        "recommendation_id": "rec-phase5a-1",
        "recommendation_digest": recommendation_digest,
        "issued_at": H.at(190.0),
    }
    sig = SigningKey.from_seed(bytes(range(32, 64))).sign(canonical_bytes(payload))
    return p5a.ProducerAttestationEvidence(
        producer_id=payload["producer_id"], producer_key_id=payload["producer_key_id"],
        signature_algorithm="ed25519", signature=sig.hex(),
        recommendation_id="rec-phase5a-1", recommendation_digest=recommendation_digest,
        signing_purpose=payload["signing_purpose"],
        signing_payload_digest=p5a.canonical_digest(payload), issued_at=payload["issued_at"],
    )


def make_scope(**over):
    kw = dict(
        tenant_id=projection.tenant_id, account_id="acct-000123456789",
        environment=projection.context.environment, region=projection.context.region,
        zone=projection.context.zone, namespace=None,
        compute_group=projection.context.compute_group,
        resource_class=projection.context.resource_class,
        action_type=projection.context.action_type,
        magnitude_before=projection.context.magnitude_before,
        requested_magnitude=projection.context.magnitude_after,
        max_permitted_magnitude=20, max_permitted_delta=5,
    )
    kw.update(over)
    return p5a.ExecutionTargetScope(**kw)


def make_policy(scope, **over):
    body = dict(
        policy_id="cloud-scaling.capacity-bounds", policy_version="3.1.0",
        policy_artifact_digest=p5a.canonical_digest(
            {"policy": "cloud-scaling.capacity-bounds", "v": "3.1.0"}
        ),
        policy_issuer="ugence.policy-authority", policy_key_id="policy-signing-key-7",
        target_scope_digest=scope.digest(),
        max_permitted_magnitude=scope.max_permitted_magnitude,
        max_permitted_delta=scope.max_permitted_delta,
        policy_signature_algorithm="ed25519",
    )
    body.update(over)
    payload = {"schema_version": "cloud-scaling-policy-target-binding-1", **body}
    sig = SigningKey.from_seed(bytes(range(64, 96))).sign(canonical_bytes(payload))
    return p5a.PolicyTargetBindingReference(
        policy_signature=sig.hex(), binding_digest=p5a.canonical_digest(payload), **body
    )


def make_coordinate(scope, **over):
    """The complete Policy Authority coordinate the candidate carries (5B-1).

    The body digest is well-shaped rather than genuine, for the same reason the source
    fixture's is: this distribution depends on neither the Policy Authority nor the UVI
    contracts, so there is no real policy here to derive one from.
    """

    digest = hashlib.sha256(
        canonical_bytes(
            {"policy": "cloud-scaling.capacity-bounds", "v": "3.1.0", "body": "fixture"}
        )
    ).hexdigest()
    body = dict(
        policy_family="capacity-bounds",
        policy_id="cloud-scaling.capacity-bounds",
        policy_version="3.1.0",
        policy_content_digest=digest,
        policy_scope="TENANT",
        policy_tenant_id=scope.tenant_id,
        policy_body_digest=digest,
        issuing_authority_id="ugence.policy-authority",
        key_id="policy-signing-key-7",
        signature_alg="ed25519",
        target_scope_digest=scope.digest(),
    )
    body.update(over)
    payload = {"schema_version": "cloud-scaling-policy-target-binding-2", **body}
    return p5a.PolicyTargetBindingReferenceV2(
        binding_digest=p5a.canonical_digest(payload), **body
    )


attestation = make_attestation(projection.recommendation_digest)
scope = make_scope()
policy = make_policy(scope)
coordinate = make_coordinate(scope)
candidate = p5a.build_capacity_authorization_candidate(
    projection=projection, decision=decision, producer_attestation=attestation,
    policy_binding=policy, policy_coordinate_binding=coordinate, target_scope=scope,
)
for key, actual in (
    ("producer_signing_payload_digest", attestation.signing_payload_digest),
    ("target_scope_digest", scope.digest()),
    ("policy_binding_digest", policy.digest()),
    ("policy_coordinate_binding_digest", coordinate.digest()),
    ("candidate_digest", candidate.candidate_digest),
):
    if actual != EXPECTED[key]:
        raise AssertionError(f"{key}: installed {actual} != source {EXPECTED[key]}")

# --- 6. the candidate grants nothing, structurally ---------------------------------------
for forbidden in ("authorized", "authority_granted", "envelope_issued", "actiongate_invoked",
                  "credential_issued", "actuation_performed", "effect_verified", "executable"):
    if forbidden in type(candidate).__dataclass_fields__:
        raise AssertionError(f"the installed candidate carries an authority field: {forbidden}")
    if forbidden in candidate.to_canonical_dict():
        raise AssertionError(f"the installed candidate canonicalizes {forbidden}")
if candidate.grants_authority is not False:
    raise AssertionError("grants_authority is not False")
if candidate.trust_state.value != "PRESENT_BUT_NOT_TRUST_VERIFIED":
    raise AssertionError("trust state drift inside the wheel")

# --- 7. every rejection still rejects inside the wheel -----------------------------------
def rejects(label, fn):
    try:
        fn()
    except p5a.CloudScalingAuthorizationContractError:
        return
    except (TypeError, AttributeError):
        return
    raise AssertionError(f"the installed wheel FAILED to reject: {label}")


def forged_decision(**over):
    f = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for k, v in vars(decision).items():
        object.__setattr__(f, k, v)
    for k, v in over.items():
        object.__setattr__(f, k, v)
    return f


def build(**over):
    kw = dict(projection=projection, decision=decision, producer_attestation=attestation,
              policy_binding=policy, policy_coordinate_binding=coordinate,
              target_scope=scope)
    kw.update(over)
    return p5a.build_capacity_authorization_candidate(**kw)


other_scope = make_scope(account_id="acct-999999999999")
rejects("denied decision",
        lambda: build(decision=forged_decision(disposition=SubjectRiskDisposition.RISK_DENIED)))
rejects("forged decision digest",
        lambda: build(decision=forged_decision(decision_digest="sha256:" + "a" * 64)))
rejects("missing decision snapshot",
        lambda: build(decision=forged_decision(decision_snapshot=None)))
rejects("missing expires_at", lambda: build(decision=forged_decision(expires_at=None)))
rejects("stale request digest",
        lambda: build(decision=forged_decision(request_digest="sha256:" + "0" * 64)))
rejects("missing attestation", lambda: build(producer_attestation=None))
rejects("foreign attestation",
        lambda: build(producer_attestation=make_attestation("sha256:" + "b" * 64)))
rejects("policy-signing purpose reuse",
        lambda: make_attestation(projection.recommendation_digest,
                                 signing_purpose="ugence.policy_authority.policy_signing"))
rejects("missing policy binding", lambda: build(policy_binding=None))
rejects("policy bound to another account's scope",
        lambda: build(policy_binding=make_policy(other_scope)))
rejects("missing account binding", lambda: make_scope(account_id=""))
rejects("magnitude escalation", lambda: make_scope(max_permitted_magnitude=1))
rejects("delta escalation", lambda: make_scope(max_permitted_delta=0))
rejects("action substitution", lambda: build(target_scope=make_scope(action_type="scale_down")))
rejects("target relocation", lambda: build(target_scope=make_scope(region="eu-west-1")))
rejects("duck-typed attestation", lambda: build(producer_attestation=object()))
rejects("forged trust state on attestation", lambda: p5a.ProducerAttestationEvidence.from_dict(
    {**{k: v for k, v in attestation.to_canonical_dict().items() if k != "trust_state"},
     "trust_state": "TRUST_VERIFIED"}))
rejects("wrong candidate digest", lambda: type(candidate)(
    **{**{f: getattr(candidate, f) for f in type(candidate).__dataclass_fields__},
       "candidate_digest": "sha256:" + "e" * 64}))

Sub = type("SubProjection", (type(projection),), {})
rejects("subclass projection", lambda: p5a.reconcile_phase4(
    Sub(**{f: getattr(projection, f) for f in type(projection).__dataclass_fields__}),
    decision))
Fake = type("FakeProjection", (), {})
fake = Fake.__new__(Fake)
for f in type(projection).__dataclass_fields__:
    object.__setattr__(fake, f, getattr(projection, f))
rejects("object.__new__ fabrication", lambda: p5a.reconcile_phase4(fake, decision))

# --- 7b. AUDIT REMEDIATION (F-2/F-4) verified from inside the installed wheel ------------
import dataclasses as _dc

# F-4: annotated class constants must not be dataclass fields or constructor keywords.
for cls in (p5a.ProducerAttestationEvidence, p5a.ExecutionTargetScope,
            p5a.PolicyTargetBindingReference, p5a.CapacityAuthorizationCandidate):
    leaked = [f.name for f in _dc.fields(cls) if f.name.startswith("_")]
    if leaked:
        raise AssertionError(f"{cls.__name__} exposes class constants as fields: {leaked}")
    import inspect as _insp
    sig_leak = [k for k in _insp.signature(cls).parameters if k.startswith("_")]
    if sig_leak:
        raise AssertionError(f"{cls.__name__} accepts class constants as keywords: {sig_leak}")
rejects("class constant as a constructor keyword",
        lambda: make_scope(_ALLOWED_KEYS=frozenset({"anything"})))

# F-2: the candidate digest must cover the COMPLETE carried artifacts.
_payload = candidate.digest_payload()
for _key, _obj in (("target_scope", candidate.target_scope),
                   ("policy_binding", candidate.policy_binding),
                   ("producer_attestation", candidate.producer_attestation)):
    if _key not in _payload or _payload[_key] != _obj.to_canonical_dict():
        raise AssertionError(f"{_key} is not bound in full inside the installed wheel")
if _payload["producer_attestation"]["signature"] != candidate.producer_attestation.signature:
    raise AssertionError("producer signature bytes are not digest-bound in the wheel")
if _payload["policy_binding"]["policy_signature"] != candidate.policy_binding.policy_signature:
    raise AssertionError("policy signature is not digest-bound in the wheel")
_unbound = (set(type(candidate).__dataclass_fields__) - set(_payload) - {"candidate_digest"})
if _unbound:
    raise AssertionError(f"candidate fields carried but not digest-bound: {sorted(_unbound)}")

# F-2: the rogue-policy-issuer attack must be closed inside the wheel too.
import copy as _copy
_rogue = make_policy(scope, policy_issuer="attacker.rogue-authority",
                     policy_key_id="rogue-key-1")
_t = _copy.copy(candidate)
object.__setattr__(_t, "policy_binding", _rogue)
if _t.digest() == _t.candidate_digest:
    raise AssertionError("rogue policy issuer rides along under an unchanged digest")
rejects("rogue policy issuer with a preserved candidate digest", lambda: type(candidate)(
    **{**{f: getattr(candidate, f) for f in type(candidate).__dataclass_fields__},
       "policy_binding": _rogue}))

# ...and forged producer signature bytes.
_forged = make_attestation(projection.recommendation_digest)
object.__setattr__(_forged, "signature", "de" * 32)
_t2 = _copy.copy(candidate)
object.__setattr__(_t2, "producer_attestation", _forged)
if _t2.digest() == _t2.candidate_digest:
    raise AssertionError("forged producer signature rides along under an unchanged digest")

# Both trust states remain the single unverified value.
for _o in (candidate.producer_attestation, candidate.policy_binding, candidate):
    if _o.trust_state.value != "PRESENT_BUT_NOT_TRUST_VERIFIED":
        raise AssertionError("trust state drift inside the wheel")

# --- 8. no authority/execution/clock symbol exists in the installed package --------------
import ast, pkgutil

pkg_dir = pathlib.Path(p5a.__file__).resolve().parent
for source_file in sorted(pkg_dir.rglob("*.py")):
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in {"boto3", "kubernetes", "azure", "requests", "socket",
                            "subprocess", "time"}:
                    raise AssertionError(f"{source_file.name} imports {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in {"ugence_decision_authority",
                                             "ugence_actiongate_provider",
                                             "ugence_cloud_scaling_operations",
                                             "ugence_policy_authority"}:
                raise AssertionError(f"{source_file.name} imports {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"now", "utcnow", "monotonic", "issue_envelope",
                                  "authorize_action", "issue_credential"}:
                raise AssertionError(f"{source_file.name} calls .{node.func.attr}()")

for symbol in p5a.__all__:
    lowered = symbol.lower()
    for fragment in ("envelope", "actiongate", "credential", "executor", "clock"):
        if fragment in lowered:
            raise AssertionError(f"public export {symbol} names {fragment}")

# --- 9. no test, fixture or conftest leaked into the wheel -------------------------------
for leaked in pkg_dir.rglob("*"):
    name = leaked.name
    if name in {"conftest.py", "ph_helpers.py"} or name.startswith("test_"):
        raise AssertionError(f"test material leaked into the wheel: {leaked}")
    if leaked.is_dir() and name in {"tests", "fixtures"}:
        raise AssertionError(f"test directory leaked into the wheel: {leaked}")
if not (pkg_dir / "py.typed").exists():
    raise AssertionError("py.typed is missing from the installed package")

# --- 10. no out-of-scope monorepo package is importable ----------------------------------
for module in ("symbolu", "agentic", "cloud_scaling_operations",
               "ugence_decision_authority", "ugence_actiongate_provider",
               "ugence_policy_authority", "ugence_trusted_evidence_authority"):
    try:
        importlib.import_module(module)
    except ImportError:
        pass
    else:
        raise AssertionError(f"out-of-scope package is importable: {module}")

print("INSTALLED-WHEEL PHASE 5A AUTHORIZATION-CONTRACTS VERIFICATION OK")
'''


def run(cmd, **kwargs):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def source_expectations() -> dict:
    """Compute the expected values from the SOURCE tree.

    Passed into the clean environment so the probe compares installed behavior against
    source behavior rather than merely against itself.
    """

    for path in (
        PKG / "src",
        REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
        REPO / "packages" / "risk_authority" / "src",
        REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
        CONTROLLER_HELPERS.parent,
        PKG / "tests",
    ):
        sys.path.insert(0, str(path))

    import conftest as fixtures  # type: ignore[import-not-found]

    import ugence_cloud_scaling_authorization_contracts as p5a

    projection = fixtures.build_projection()
    decision = fixtures.build_decision(projection)
    attestation = fixtures.build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    scope = fixtures.build_target_scope(projection)
    policy = fixtures.build_policy_binding(scope)
    coordinate = fixtures.build_policy_coordinate_binding(
        scope, policy_id=policy.policy_id, policy_version=policy.policy_version
    )
    candidate = p5a.build_capacity_authorization_candidate(
        projection=projection, decision=decision, producer_attestation=attestation,
        policy_binding=policy, policy_coordinate_binding=coordinate, target_scope=scope,
    )
    return {
        "version": p5a.__version__,
        "public_api": list(p5a.__all__),
        "recommendation_digest": projection.recommendation_digest,
        "context_digest": projection.context_digest,
        "subject_digest": projection.subject_digest,
        "request_digest": projection.request_digest,
        "idempotency_key": projection.idempotency_key,
        "decision_digest": decision.decision_digest,
        "producer_signing_payload_digest": attestation.signing_payload_digest,
        "target_scope_digest": scope.digest(),
        "policy_binding_digest": policy.digest(),
        "policy_coordinate_binding_digest": coordinate.digest(),
        "candidate_digest": candidate.candidate_digest,
    }


def make_python(env_dir: Path) -> Path:
    """Create a clean virtualenv and return its interpreter.

    ``with_pip=True`` bootstraps pip from the local ``ensurepip`` bundle — no index access
    — and pip is deliberately **not** upgraded afterwards, because ``pip install --upgrade
    pip`` is itself a network fetch and would make the phrase "offline installation" false.
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
    silently restore network access: ``--no-index``, ``PIP_NO_INDEX=1``, and an unroutable
    sentinel index URL behind them. The cache is disabled so the wheelhouse is the only
    possible source — otherwise "offline" would just mean "warm cache". No editable
    install is used: an editable install would put the monorepo source tree on
    ``sys.path`` and defeat the entire exercise.
    """

    env = dict(os.environ)
    env.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_PYTHON_VERSION_WARNING": "1",
            "PIP_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            "PIP_EXTRA_INDEX_URL": OFFLINE_SENTINEL_INDEX,
            "PIP_NO_CACHE_DIR": "1",
        }
    )
    cmd = [
        str(python), "-m", "pip", "install", "--quiet",
        "--no-index", "--no-cache-dir",
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
        if key != "public_api":
            print(f"  {key} = {value}")
    print(f"  public_api = {len(expected['public_api'])} symbols")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()

        # === PHASE A — collection. ONLINE by design, and the only phase that is. ========
        print("\n=== PHASE A (online): build + collect every required wheel ===", flush=True)
        for project in FIRST_PARTY:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse),
                 str(project)])
        done("first-party wheels built")

        run([
            sys.executable, "-m", "pip", "download", "--quiet",
            "--only-binary=:all:",
            "--dest", str(wheelhouse),
            "--find-links", str(wheelhouse),
            "ugence-cloud-scaling-authorization-contracts",
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
        print("\n=== PHASE B (offline): install with the index structurally disabled ===",
              flush=True)
        env_dir = tmp_path / "env"
        python = make_python(env_dir)
        done("clean virtualenv created (pip from local ensurepip, never upgraded)")

        offline_install(python, wheelhouse, "ugence-cloud-scaling-authorization-contracts")
        done("package installed offline from the local wheelhouse only")

        # === PHASE C — negative controls. An "offline" claim nobody tested is a guess. ==
        print("\n=== PHASE C: negative controls on the offline guarantee ===", flush=True)

        crippled = tmp_path / "crippled-wheelhouse"
        crippled.mkdir()
        removed = None
        for wheel in wheelhouse.glob("*.whl"):
            if wheel.name.startswith("ugence_cloud_scaling_risk_integration-"):
                removed = wheel.name
                continue
            shutil.copy2(wheel, crippled / wheel.name)
        if removed is None:
            raise SystemExit("could not identify the Phase 4C wheel to remove")
        print(f"  removed {removed} from a copy of the wheelhouse", flush=True)
        crippled_env = make_python(tmp_path / "env-crippled")
        expect_offline_install_failure(
            crippled_env, crippled, "ugence-cloud-scaling-authorization-contracts",
            why="a required wheel was absent from the wheelhouse",
        )
        done("negative control: missing wheel causes failure, not an index fetch")

        bogus_env = make_python(tmp_path / "env-bogus")
        try:
            subprocess.run(
                [
                    str(bogus_env), "-m", "pip", "install", "--quiet", "--no-cache-dir",
                    "--index-url", OFFLINE_SENTINEL_INDEX,
                    "--find-links", str(crippled),
                    "ugence-cloud-scaling-authorization-contracts",
                ],
                check=True,
                env={**os.environ, "PIP_NO_CACHE_DIR": "1",
                     "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print("  [ok] a bogus index could not supply the missing distribution", flush=True)
        else:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the install succeeded against a bogus index — "
                "something other than the wheelhouse supplied the distribution"
            )
        done("negative control: a bogus index cannot rescue an incomplete wheelhouse")

        probe = subprocess.run(
            [str(crippled_env), "-c", "import ugence_cloud_scaling_authorization_contracts"],
            capture_output=True,
        )
        if probe.returncode == 0:
            raise SystemExit(
                "NEGATIVE PROBE FAILED: the package is importable in an environment whose "
                "installation failed — a failed install left a usable package"
            )
        print("  [ok] the failed installation left nothing importable", flush=True)
        done("negative control: a failed install cannot yield a working package")

        # === PHASE D — behavior probes inside the isolated environment. =================
        print("\n=== PHASE D: behavior probes in the isolated environment ===", flush=True)
        probe_dir = tmp_path / "probe"
        probe_dir.mkdir()
        (probe_dir / "ph_helpers.py").write_text(
            CONTROLLER_HELPERS.read_text(encoding="utf-8"), encoding="utf-8"
        )
        probe_file = probe_dir / "probe.py"
        probe_file.write_text(_PROBE, encoding="utf-8")

        probe_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        run([str(python), str(probe_file), json.dumps(expected)],
            cwd=str(probe_dir), env=probe_env)
        done("import, API-parity, digest-parity, rejection and non-authority probes passed")

    if len(steps) != EXPECTED_STEPS:
        raise SystemExit(
            f"refusing to report success: {len(steps)} of {EXPECTED_STEPS} steps "
            f"completed ({steps})"
        )
    print(f"\nall {EXPECTED_STEPS} verification steps completed:", flush=True)
    for step in steps:
        print(f"  - {step}")
    print("\nOFFLINE ISOLATED INSTALLATION STAGE VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
