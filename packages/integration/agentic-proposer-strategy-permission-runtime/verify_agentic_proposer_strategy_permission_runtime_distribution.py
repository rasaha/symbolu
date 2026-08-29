#!/usr/bin/env python3
"""Reproducible proof that the strategy-permission runtime installs and operates
from a built wheel, against installed distributions and no monorepo path.

Builds this distribution and its first-party dependencies into a local
find-links directory, installs it into a fresh virtualenv with no system site
packages, and then proves *inside that environment*:

  * ``ugence_agentic_proposer_strategy_permission_runtime`` imports from
    site-packages, at 0.1.0, with no repository source on ``sys.path``;
  * the curated public API resolves and ``py.typed`` ships;
  * a policy issued and signed through the **real** shared authority resolves
    through the concrete resolver and yields the four ratified response fields,
    with the version a string and no ``verified`` boolean anywhere;
  * an unknown reference, a near-miss reference and a cross-tenant reference all
    fail closed, and the injected mapping is defensively copied;
  * an approval verifier is required at construction;
  * a body swap under the same coordinate fails closed, and the authority's cause
    reaches the caller **only** on the ``reason`` attribute — never in the message;
  * no execution authority, console, product or unrelated package is importable.

The permissive approval verifier below exists only inside this script, for the
same reason the authority's own permissive verifiers exist only under ``tests/``:
issuance must be exercised, and the shipped default is deny-by-default. Neither
distribution ships anything like it, and a package test asserts that.

Run:  python packages/integration/agentic-proposer-strategy-permission-runtime/verify_agentic_proposer_strategy_permission_runtime_distribution.py
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
REPO = PKG.parents[2]

DISTRIBUTION = "ugence-agentic-proposer-strategy-permission-runtime"
NAMESPACE = "ugence_agentic_proposer_strategy_permission_runtime"

SOURCES = {
    NAMESPACE: PKG,
    "ugence_agentic_proposer_strategy_permission_policy": (
        REPO / "packages" / "integration" / "agentic-proposer-strategy-permission-policy"
    ),
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_agentic_proposer": REPO / "packages" / "capabilities" / "agentic-proposer",
    "ugence_jcs": REPO / "packages" / "jcs",
}

_CHECK = r'''
import dataclasses
import importlib.util
import sys
from datetime import datetime, timezone

import ugence_agentic_proposer_strategy_permission_runtime as runtime

assert runtime.__version__ == "0.1.0", runtime.__version__
assert "site-packages" in runtime.__file__, runtime.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(runtime.__file__).resolve().parent / "py.typed").is_file(), "no py.typed"

import ugence_agentic_proposer_strategy_permission_policy as family
from ugence_agentic_proposer import (
    ReasoningStrategy, StrategyPolicyRequest, StrategyPolicyResponse,
)
from ugence_policy_authority.api import (
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, Ed25519PolicySigner, InMemoryPolicyRegistry,
    KeyEntitlement, PolicyKeyRing, PolicyResolutionReason, SigningKey, issue_policy,
)

SINGLE = ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
MULTI = ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value
REF = "policy-authority/strategy-permission/reconciliation"
TENANT = "tenant-1"
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

ADAPTER = family.StrategyPermissionPolicyFamilyAdapter()


def metadata(digest):
    return family.StrategyPermissionPolicyMetadata(
        policy_id="strategy-permission", version="1.0.0", content_digest=digest,
        scope=family.POLICY_SCOPE_TENANT,
        lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE, tenant_id=TENANT,
        effective_from=T_FROM, effective_to=T_TO)


permitted = tuple(sorted((MULTI, SINGLE)))
draft = family.StrategyPermissionPolicy(
    metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
    strategy_policy_ref=REF, permitted_strategies=permitted)
policy = family.StrategyPermissionPolicy(
    metadata=metadata(ADAPTER.describe(draft).body_digest()),
    strategy_policy_ref=REF, permitted_strategies=permitted)


class _ScriptApprovalVerifier:
    """Verification-script only. Neither distribution ships anything like it."""

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        return ApprovalVerification(
            verified=True, status=ApprovalVerificationStatus.APPROVED,
            coordinate=coordinate, policy_body_digest=policy_body_digest,
            approving_authority_id=approval.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest, verified_at=as_of)


signer = Ed25519PolicySigner(
    authority_id="ugence.policy-authority", key_id="key-1",
    signing_key=SigningKey.from_seed(bytes([1]) * 32))
key_ring = PolicyKeyRing(
    [signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))])
registry = InMemoryPolicyRegistry()
adapters = runtime.with_strategy_permission_adapter(None)
assert family.STRATEGY_PERMISSION_ADAPTER_ID in {a.adapter_id for a in adapters.adapters}

issue_policy(
    policy=policy, record_id="rec-1",
    approval=ApprovalEvidenceRef(
        approval_ref="APPROVAL-1", approval_digest="a" * 64,
        approving_authority_id="ugence.governance.policy-approval-board"),
    approval_verifier=_ScriptApprovalVerifier(), signer=signer, registry=registry,
    adapters=adapters, issued_at=T_MID)

coordinate = family.strategy_permission_coordinate(policy.metadata)
supplied = {(TENANT, REF): coordinate}
resolver = runtime.build_strategy_policy_resolver(
    reference_map=supplied, registry=registry, signature_verifier=key_ring,
    approval_verifier=_ScriptApprovalVerifier(), adapters=adapters)


def request(*, ref=REF, tenant=TENANT, case_ref="case-1", as_of=T_MID):
    return StrategyPolicyRequest(
        strategy_policy_ref=ref, tenant_id=tenant, case_ref=case_ref, as_of=as_of)


# -- the four ratified response fields --------------------------------------
response = resolver.resolve(request=request())
assert type(response) is StrategyPolicyResponse
assert response.strategy_policy_id == "strategy-permission"
assert response.strategy_policy_version == "1.0.0"
assert type(response.strategy_policy_version) is str
assert response.strategy_policy_ref == REF
assert [m.value for m in response.permitted_strategies] == list(permitted)
assert not hasattr(response, "verified")
assert "verified" not in type(response).model_fields

# -- case_ref selects nothing ------------------------------------------------
assert resolver.resolve(request=request(case_ref="case-99")) == response

def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a fail-closed rule did not fire: " + expected.__name__)


# -- the mapping was defensively copied --------------------------------------
# Adding a key to the mapping handed in must not widen what the resolver can
# reach, and removing the real one must not narrow it.
supplied[("tenant-attacker", "any")] = coordinate
supplied.pop((TENANT, REF))
assert resolver.resolve(request=request()).strategy_policy_id == "strategy-permission"
refuses(lambda: resolver.resolve(request=request(tenant="tenant-attacker", ref="any")),
        runtime.UnknownStrategyPolicyReferenceError)

refuses(lambda: resolver.resolve(request=request(ref=REF + "x")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: resolver.resolve(request=request(ref="policy-authority")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: resolver.resolve(request=request(tenant="tenant-elsewhere")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: runtime.build_strategy_policy_resolver(
            reference_map={(TENANT, REF): coordinate}, registry=registry,
            signature_verifier=key_ring, approval_verifier=None), TypeError)

# -- a mis-wired deployment: the key names one tenant, the coordinate another --
mis_wired = runtime.build_strategy_policy_resolver(
    reference_map={("tenant-other", REF): coordinate}, registry=registry,
    signature_verifier=key_ring, approval_verifier=_ScriptApprovalVerifier(),
    adapters=adapters)
refuses(lambda: mis_wired.resolve(request=request(tenant="tenant-other")),
        runtime.StrategyPolicyTenantScopeError)

# -- the effective window, and the reason discipline -------------------------
try:
    resolver.resolve(request=request(as_of=T_AFTER))
    raise SystemExit("an out-of-window resolution did not fail closed")
except runtime.StrategyPolicyUnresolvedError as exc:
    assert exc.reason is PolicyResolutionReason.EXPIRED
    message = str(exc).upper()
    for reason in PolicyResolutionReason:
        assert reason.value not in message, ("the cause leaked into the message: "
                                             + reason.value)

# -- a body swap under the same coordinate fails closed ----------------------
tampered = family.StrategyPermissionPolicy(
    metadata=policy.metadata, strategy_policy_ref=policy.strategy_policy_ref,
    permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)))
registry._issued[coordinate] = dataclasses.replace(
    registry._issued[coordinate], policy=tampered)
refuses(lambda: resolver.resolve(request=request()),
        runtime.StrategyPolicyUnresolvedError)

# -- nothing that authorizes execution came along ----------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance", "requests",
            "httpx", "boto3"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED STRATEGY-PERMISSION-RUNTIME VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == NAMESPACE or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print(f"[1/4] build {DISTRIBUTION} and its first-party dependencies")
    for src in SOURCES.values():
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_agentic_proposer_strategy_permission_runtime-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert f"{NAMESPACE}/py.typed" in names, "wheel is missing py.typed"
    print(f"      wheel contains only {NAMESPACE}/ (+ py.typed) + dist-info")

    print("[3/4] create an isolated venv and install from the local wheelhouse")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks), DISTRIBUTION])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print(f"\nISOLATED {DISTRIBUTION.upper()} DISTRIBUTION VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
