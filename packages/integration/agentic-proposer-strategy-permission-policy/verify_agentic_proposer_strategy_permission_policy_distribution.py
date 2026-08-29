#!/usr/bin/env python3
"""Reproducible proof that the strategy-permission policy family installs and
operates from a built wheel, against installed distributions and no monorepo path.

Builds this distribution and its two first-party dependencies into a local
find-links directory, installs it into a fresh virtualenv with no system site
packages, and then proves *inside that environment*:

  * ``ugence_agentic_proposer_strategy_permission_policy`` imports from
    site-packages, at 0.1.0, with no repository source on ``sys.path``;
  * the curated public API resolves and ``py.typed`` ships;
  * a policy constructs, its declared digest binds its own body, and the
    canonical projection omits exactly ``metadata.content_digest``;
  * the construction rules fire — empty, duplicated, unsorted, alien token,
    wrong vocabulary version, and a non-Token ``policy_id``;
  * the accepted token set equals ``set(ReasoningStrategy)`` from the installed
    proposer distribution, so no fork survives packaging;
  * the family issues and resolves through the **real** shared authority, and a
    body swap under the same coordinate fails closed;
  * no execution authority, console, product or unrelated package is importable.

The permissive approval verifier below exists only inside this script, for the
same reason the authority's own permissive verifiers exist only under ``tests/``:
issuance must be exercised, and the shipped default is deny-by-default. Neither
distribution ships anything like it, and a package test asserts that.

Run:  python packages/integration/agentic-proposer-strategy-permission-policy/verify_agentic_proposer_strategy_permission_policy_distribution.py
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
REPO = PKG.parents[2]  # packages/integration/<pkg> -> packages/integration -> packages -> repo

DISTRIBUTION = "ugence-agentic-proposer-strategy-permission-policy"
NAMESPACE = "ugence_agentic_proposer_strategy_permission_policy"

SOURCES = {
    NAMESPACE: PKG,
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_agentic_proposer": REPO / "packages" / "capabilities" / "agentic-proposer",
    "ugence_jcs": REPO / "packages" / "jcs",
}

_CHECK = r'''
import importlib.util
import sys
from datetime import datetime, timezone

import ugence_agentic_proposer_strategy_permission_policy as family

assert family.__version__ == "0.1.0", family.__version__
assert "site-packages" in family.__file__, family.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(family.__file__).resolve().parent / "py.typed").is_file(), "no py.typed"

# -- identity constants are what the snapshot pinned ------------------------
assert family.STRATEGY_PERMISSION_ADAPTER_ID == "ugence.agentic-proposer.strategy-permission/v1"
assert family.STRATEGY_PERMISSION_POLICY_FAMILY == "agentic_proposer.strategy_permission"
assert family.STRATEGY_PERMISSION_POLICY_TYPE == "StrategyPermissionPolicy"
assert family.STRATEGY_VOCABULARY_VERSION == "ugence.agentic-proposer.reasoning-strategy/v1"

# -- one vocabulary, across a packaging boundary ----------------------------
from ugence_agentic_proposer import ReasoningStrategy
assert family.ADMITTED_STRATEGY_TOKENS == {m.value for m in ReasoningStrategy}, (
    "the installed family and the installed proposer disagree on the vocabulary")

SINGLE = ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
MULTI = ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value
REF = "policy-authority/strategy-permission/reconciliation"
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)

ADAPTER = family.StrategyPermissionPolicyFamilyAdapter()


def metadata(digest, **overrides):
    fields = dict(policy_id="strategy-permission", version="1.0.0",
                  content_digest=digest, scope=family.POLICY_SCOPE_TENANT,
                  lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE,
                  tenant_id="tenant-1", effective_from=T_FROM, effective_to=T_TO)
    fields.update(overrides)
    return family.StrategyPermissionPolicyMetadata(**fields)


def build(permitted=(MULTI, SINGLE), **overrides):
    permitted = tuple(sorted(permitted))
    draft = family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST, **overrides),
        strategy_policy_ref=REF, permitted_strategies=permitted)
    digest = ADAPTER.describe(draft).body_digest()
    return family.StrategyPermissionPolicy(
        metadata=metadata(digest, **overrides),
        strategy_policy_ref=REF, permitted_strategies=permitted)


policy = build()
descriptor = ADAPTER.describe(policy)
assert descriptor.body_digest() == descriptor.declared_content_digest
assert descriptor.policy_type == family.STRATEGY_PERMISSION_POLICY_TYPE

projection = descriptor.canonical_projection
assert "content_digest" not in projection["metadata"], "the digest was not removed"
assert projection["strategy_policy_ref"] == REF
assert projection["vocabulary_version"] == family.STRATEGY_VOCABULARY_VERSION
assert projection["permitted_strategies"] == sorted((MULTI, SINGLE))

# -- the construction rules fire -------------------------------------------
def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a construction rule did not fire: " + expected.__name__)


refuses(lambda: build(permitted=()), family.StrategyPermissionFieldError)
refuses(lambda: build(permitted=("STAGED_DECOMPOSITION",)), family.StrategyPermissionFieldError)
refuses(lambda: build(policy_id="tenant/strategy"), family.StrategyPermissionFieldError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE, SINGLE)),
    family.StrategyPermissionDuplicateError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE, MULTI)),
    family.StrategyPermissionOrderingError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE,),
        vocabulary_version="ugence.agentic-proposer.reasoning-strategy/v2"),
    family.StrategyPermissionFieldError)

# -- the real authority issues and resolves this family ---------------------
from ugence_policy_authority.api import (
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, Ed25519PolicySigner, InMemoryPolicyRegistry,
    KeyEntitlement, PolicyKeyRing, PolicyResolutionReason, PolicyResolutionStatus,
    SigningKey, framed_body_digest, issue_policy, resolve_policy,
)


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
adapters = AdapterRegistry([ADAPTER])
approval = ApprovalEvidenceRef(
    approval_ref="APPROVAL-1", approval_digest="a" * 64,
    approving_authority_id="ugence.governance.policy-approval-board")

record = issue_policy(
    policy=policy, record_id="rec-1", approval=approval,
    approval_verifier=_ScriptApprovalVerifier(), signer=signer, registry=registry,
    adapters=adapters, issued_at=T_MID)

resolution = resolve_policy(
    reference=family.strategy_permission_coordinate(policy.metadata),
    expected_reference_tenant_id="tenant-1", as_of=T_MID, registry=registry,
    signature_verifier=key_ring, adapters=adapters)
assert resolution.status is PolicyResolutionStatus.RESOLVED, resolution.reason
assert resolution.reason is PolicyResolutionReason.RESOLVED
assert resolution.policy is policy

recomputed = framed_body_digest(
    adapter_id=resolution.descriptor_adapter_id,
    policy_type=resolution.descriptor_policy_type,
    projection=resolution.descriptor_canonical_projection)
assert recomputed == record.policy_body_digest, "the published projection does not rebuild"

# a body swap under the same coordinate fails closed
import dataclasses
coordinate = family.strategy_permission_coordinate(policy.metadata)
tampered = family.StrategyPermissionPolicy(
    metadata=policy.metadata, strategy_policy_ref=policy.strategy_policy_ref,
    permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)))
registry._issued[coordinate] = dataclasses.replace(
    registry._issued[coordinate], policy=tampered)
after = resolve_policy(
    reference=coordinate, expected_reference_tenant_id="tenant-1", as_of=T_MID,
    registry=registry, signature_verifier=key_ring, adapters=adapters)
assert after.status is PolicyResolutionStatus.UNRESOLVED, after.status
assert after.policy is None

# -- nothing that authorizes execution came along --------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance",
            "ugence_agentic_proposer_strategy_permission_runtime"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED STRATEGY-PERMISSION-POLICY VERIFICATION OK")
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
    wheel = _latest(findlinks, "ugence_agentic_proposer_strategy_permission_policy-*.whl")
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
