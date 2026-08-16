#!/usr/bin/env python3
"""Independent adversarial probes against the UVI Policy Authority (GV-2C-b).

Deliberately *separate* from the pytest suite and sharing none of its fixtures:
these probes rebuild every artifact from scratch and attack the package through
its public API only, so a mistake in the test fixtures cannot mask a real hole.

Each probe states an attack an untrusted caller might attempt and asserts the
authority refuses it. Run:

    python packages/uvi-policy-authority/adversarial_probes.py

Exit code 0 when every probe held; non-zero on the first breach.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import sys
from datetime import datetime, timedelta, timezone

_HERE = pathlib.Path(__file__).resolve().parent
for _path in (
    _HERE / "src",
    _HERE.parent / "governance-contracts" / "src",
    _HERE.parent / "uvi-policy-contracts" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from ugence_uvi_policy_authority.api import (  # noqa: E402
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    HistoricalResolutionRule,
    InMemoryPolicyRegistry,
    IssuedPolicyRecord,
    PolicyApprovalError,
    PolicyAuthorityError,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    SigningKey,
    SupersessionRule,
    canonical_policy_body_digest,
    issue_policy,
    resolve_policy,
    revoke_policy,
)
from ugence_uvi_policy_contracts.api import (  # noqa: E402
    ComponentEvidenceRequirement,
    DomainPolicy,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessPolicy,
    ValuationPolicy,
    ValueComponent,
)

T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
SEC = timedelta(seconds=1)

ISSUER = "ugence.uvi.policy-authority"
APPROVER = "ugence.governance.policy-approval-board"

_BODIES = {
    PolicyFamily.GEOGRAPHY: (
        GeographyPolicy,
        dict(jurisdiction="US-CA", reporting_currency="USD", functional_currency="USD"),
    ),
    PolicyFamily.DOMAIN: (DomainPolicy, dict(governed_outcome_unit="resolved_ticket")),
    PolicyFamily.INTENDED_OUTCOME: (
        IntendedOutcomePolicy,
        dict(target_outcome="o", task_definition="t"),
    ),
    PolicyFamily.VALUATION: (
        ValuationPolicy,
        dict(
            required_components=(
                ComponentEvidenceRequirement(component=ValueComponent.GROSS_BENEFIT),
            )
        ),
    ),
    PolicyFamily.READINESS: (ReadinessPolicy, dict()),
}

_RESULTS: list[tuple[str, str]] = []
_FAILURES: list[str] = []


def probe(description: str):
    def wrap(fn):
        try:
            fn()
        except AssertionError as exc:
            _FAILURES.append(f"{description}: {exc}")
            _RESULTS.append(("BREACH", description))
        except Exception as exc:  # pragma: no cover - probe harness fault
            _FAILURES.append(f"{description}: unexpected {type(exc).__name__}: {exc}")
            _RESULTS.append(("ERROR", description))
        else:
            _RESULTS.append(("held", description))
        return fn

    return wrap


def build(family=PolicyFamily.DOMAIN, *, body_overrides=None, **meta_kwargs):
    cls, body = _BODIES[family]
    body = dict(body)
    if body_overrides:
        body.update(body_overrides)

    def meta(digest):
        base = dict(
            policy_id="pol-1",
            policy_family=family,
            version="1.0.0",
            content_digest=digest,
            lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE,
            effective_from=T_FROM,
            effective_to=T_TO,
        )
        base.update(meta_kwargs)
        return PolicyArtifactMetadata(**base)

    draft = cls(metadata=meta("0" * 64), **body)
    return cls(metadata=meta(canonical_policy_body_digest(draft)), **body)


class Verifier:
    def __init__(self, status=ApprovalVerificationStatus.APPROVED, approver=APPROVER):
        self.status, self.approver, self.calls = status, approver, 0

    def verify_approval(self, *, policy_reference, policy_body_digest, approval, as_of):
        self.calls += 1
        return ApprovalVerification(
            verified=self.status is ApprovalVerificationStatus.APPROVED,
            status=self.status,
            policy_reference=policy_reference,
            policy_body_digest=policy_body_digest,
            approving_authority_id=self.approver,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
        )


class CountingSigner:
    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    @property
    def authority_id(self):
        return self.inner.authority_id

    @property
    def key_id(self):
        return self.inner.key_id

    @property
    def signature_alg(self):
        return self.inner.signature_alg

    def sign(self, payload):
        self.calls += 1
        return self.inner.sign(payload)


def evidence(approver=APPROVER, ref="APPROVAL-1"):
    return ApprovalEvidenceRef(
        approval_ref=ref,
        approval_digest=hashlib.sha256(b"approval").hexdigest(),
        approving_authority_id=approver,
    )


def wiring(seed=1, key_id="k1", authority_id=ISSUER):
    signer = Ed25519PolicySigner(
        authority_id=authority_id, key_id=key_id, signing_key=SigningKey.from_seed(bytes([seed]) * 32)
    )
    return signer, PolicyKeyRing().with_key(signer.verification_key()), InMemoryPolicyRegistry()


def issue(policy, signer, registry, verifier=None, **kwargs):
    return issue_policy(
        policy=policy,
        record_id=kwargs.pop("record_id", "rec-1"),
        approval=kwargs.pop("approval", evidence()),
        approval_verifier=verifier or Verifier(),
        signer=signer,
        registry=registry,
        issued_at=kwargs.pop("issued_at", T_MID),
        **kwargs,
    )


def resolve(reference, registry, ring, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_tenant_id=tenant,
        as_of=as_of,
        registry=registry,
        signature_verifier=ring,
        **kwargs,
    )


def refuses(fn, *, expected=PolicyAuthorityError):
    try:
        fn()
    except expected:
        return True
    except Exception as exc:
        raise AssertionError(f"raised {type(exc).__name__} instead of {expected.__name__}: {exc}")
    raise AssertionError("the operation was permitted")


# --------------------------------------------------------------------------- #
# Probes
# --------------------------------------------------------------------------- #
@probe("a caller cannot self-approve with a boolean, a name, or a lifecycle label")
def _():
    signer, ring, registry = wiring()
    policy = build()
    counting = CountingSigner(signer)

    # No `approved` parameter exists.
    try:
        issue_policy(
            policy=policy, record_id="r", approved=True, approval_verifier=Verifier(),
            signer=counting, registry=registry, issued_at=T_MID,
        )
        raise AssertionError("an `approved=True` keyword was accepted")
    except TypeError:
        pass

    # A bare authority name is not evidence.
    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=APPROVER, approval_verifier=Verifier(),
        signer=counting, registry=registry, issued_at=T_MID,
    ))

    # The artifact's own APPROVED_ACTIVE label, with no approval authority wired up.
    assert policy.metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=evidence(),
        approval_verifier=DenyAllApprovalVerifier(), signer=counting,
        registry=registry, issued_at=T_MID,
    ), expected=PolicyApprovalError)

    assert counting.calls == 0, "the signer ran during a failed approval"
    assert registry.get_issued(policy.reference) is None


@probe("the issuing authority cannot name itself the approver")
def _():
    signer, _, registry = wiring()
    refuses(lambda: issue(build(), signer, registry,
                          verifier=Verifier(approver=ISSUER),
                          approval=evidence(approver=ISSUER)),
            expected=PolicyApprovalError)
    assert len(registry._issued) == 0


@probe("a hand-forged issuance record does not resolve")
def _():
    signer, ring, registry = wiring()
    policy = build()
    forged = IssuedPolicyRecord(
        record_id="forged",
        policy_reference=policy.reference,
        policy_family=policy.metadata.policy_family,
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id=ISSUER,
        key_id="k1",
        signature_alg="ed25519",
        signature=b"\x99" * 64,
        approving_authority_id=APPROVER,
        approval_ref="APPROVAL-FORGED",
        approval_digest=hashlib.sha256(b"x").hexdigest(),
        issued_at=T_MID,
    )
    registry.append_issuance(forged)
    assert registry.get_issued(policy.reference) is forged, "the probe failed to plant the record"
    assert resolve(policy.reference, registry, ring).reason is (
        PolicyResolutionReason.SIGNATURE_INVALID
    )


@probe("a stored version cannot be replaced")
def _():
    signer, ring, registry = wiring()
    policy = build()
    good = issue(policy, signer, registry)
    evil = dataclasses.replace(good, record_id="evil", approval_ref="APPROVAL-EVIL")
    refuses(lambda: registry.append_issuance(evil))
    assert registry.get_issued(policy.reference) == good
    assert resolve(policy.reference, registry, ring).status is PolicyResolutionStatus.RESOLVED


@probe("policy content cannot change while the reference stays valid")
def _():
    signer, ring, registry = wiring()
    policy = build(PolicyFamily.GEOGRAPHY)
    record = issue(policy, signer, registry)
    object.__setattr__(record, "policy", dataclasses.replace(record.policy, jurisdiction="XX"))
    assert resolve(policy.reference, registry, ring).reason is (
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH
    )


@probe("an arbitrary well-formed 64-hex digest is not proof the body matches")
def _():
    signer, _, registry = wiring()
    policy = build()
    arbitrary = hashlib.sha256(b"unrelated").hexdigest()
    assert len(arbitrary) == 64
    forged = dataclasses.replace(
        policy, metadata=dataclasses.replace(policy.metadata, content_digest=arbitrary)
    )
    refuses(lambda: issue(forged, signer, registry))
    assert len(registry._issued) == 0


@probe("tenant and scope cannot be altered")
def _():
    signer, ring, registry = wiring()
    policy = build(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    issue(policy, signer, registry, expected_tenant_id="tenant-a")

    hijacked = dataclasses.replace(policy.reference, tenant_id="tenant-b")
    assert resolve(hijacked, registry, ring, tenant="tenant-b").reason is (
        PolicyResolutionReason.NOT_FOUND
    )
    cross = resolve(policy.reference, registry, ring, tenant="tenant-b")
    assert cross.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    assert cross.policy is None and "tenant-a" not in cross.detail


@probe("another family cannot be substituted for a stored one")
def _():
    signer, ring, registry = wiring()
    policy = build(PolicyFamily.READINESS)
    issue(policy, signer, registry)
    probe_ref = dataclasses.replace(policy.reference, policy_family=PolicyFamily.VALUATION)
    assert resolve(probe_ref, registry, ring).reason is PolicyResolutionReason.NOT_FOUND


@probe("an unsupported dataclass and a subclass cannot be issued")
def _():
    signer, _, registry = wiring()
    policy = build()

    @dataclasses.dataclass(frozen=True)
    class RogueMultiplierPolicy:
        metadata: PolicyArtifactMetadata
        roi_multiplier: int = 10

    refuses(lambda: issue(RogueMultiplierPolicy(metadata=policy.metadata), signer, registry))

    class ExtendedDomainPolicy(DomainPolicy):
        pass

    refuses(lambda: issue(
        ExtendedDomainPolicy(metadata=policy.metadata, governed_outcome_unit="x"),
        signer, registry,
    ))
    assert len(registry._issued) == 0


@probe("no floating reference exists in the trusted path")
def _():
    registry = InMemoryPolicyRegistry()
    for forbidden in ("latest", "current", "newest", "find_by_id", "head", "resolve_by_id"):
        assert not hasattr(registry, forbidden), forbidden

    from ugence_uvi_policy_contracts.api import PolicyContractError, PolicyReference

    try:
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1.0.0", content_digest=""
        )
        raise AssertionError("a digest-free reference was constructible")
    except PolicyContractError:
        pass


@probe("a caller cannot supply its own signature as authority-produced")
def _():
    import inspect

    assert "signature" not in inspect.signature(issue_policy).parameters
    assert "signature" not in inspect.signature(revoke_policy).parameters

    signer, ring, registry = wiring()
    policy = build()
    record = issue(policy, signer, registry)
    attacker, _, _ = wiring(seed=42, key_id="k1")
    object.__setattr__(record, "signature", attacker.sign(record.signing_payload()))
    assert resolve(policy.reference, registry, ring).reason is (
        PolicyResolutionReason.SIGNATURE_INVALID
    )


@probe("every signed field is tamper-evident")
def _():
    signer, ring, registry = wiring()
    record = issue(build(), signer, registry)
    substitutes = {
        "record_id": "tampered",
        "policy_body_digest": "d" * 64,
        "issuing_authority_id": "attacker",
        "key_id": "k2",
        "signature_alg": "none",
        "approving_authority_id": "attacker",
        "approval_ref": "APPROVAL-EVIL",
        "approval_digest": "e" * 64,
        "issued_at": T_MID + SEC,
    }
    for field, value in substitutes.items():
        tampered = dataclasses.replace(record, **{field: value})
        assert not ring.verify(
            key_id=tampered.key_id,
            payload=tampered.signing_payload(),
            signature=tampered.signature,
            expected_authority_id=tampered.issuing_authority_id,
            expected_tenant_id="",
            as_of=T_MID,
        ).valid, field


@probe("revocation cannot be bypassed")
def _():
    signer, ring, registry = wiring()
    policy = build(effective_to=None)
    record = issue(policy, signer, registry)
    revoke_policy(
        reference=policy.reference,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=registry,
        revoked_at=T_MID,
        signer=signer,
    )
    # Re-appending the original issuance does not clear it.
    registry.append_issuance(record)
    assert resolve(policy.reference, registry, ring).reason is PolicyResolutionReason.REVOKED
    # Nor does the default historical rule allow a look-back.
    assert resolve(policy.reference, registry, ring, as_of=T_MID - SEC).reason is (
        PolicyResolutionReason.REVOKED
    )
    # The opt-in rule permits only a strictly earlier as_of.
    assert resolve(
        policy.reference, registry, ring, as_of=T_MID - SEC,
        historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
    ).status is PolicyResolutionStatus.RESOLVED
    assert resolve(
        policy.reference, registry, ring, as_of=T_MID,
        historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
    ).reason is PolicyResolutionReason.REVOKED


@probe("revoking one version leaves another valid, across tenants too")
def _():
    signer, ring, registry = wiring()
    v1 = build(policy_id="p", version="1.0.0", effective_to=None)
    v2 = build(policy_id="p", version="2.0.0", effective_to=None)
    issue(v1, signer, registry, record_id="r1")
    issue(v2, signer, registry, record_id="r2")
    revoke_policy(
        reference=v1.reference, revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.REPLACED, registry=registry,
        revoked_at=T_MID, replacement_reference=v2.reference,
    )
    assert resolve(v1.reference, registry, ring).reason is PolicyResolutionReason.REVOKED
    assert resolve(v2.reference, registry, ring).status is PolicyResolutionStatus.RESOLVED

    tenant_policy = build(scope=PolicyScope.TENANT, tenant_id="t-a", effective_to=None)
    issue(tenant_policy, signer, registry, record_id="rt", expected_tenant_id="t-a")
    refuses(lambda: revoke_policy(
        reference=tenant_policy.reference, revocation_id="rv-x",
        reason_code=PolicyRevocationReasonCode.OTHER, registry=registry,
        revoked_at=T_MID, expected_tenant_id="t-b",
    ))


@probe("an expired policy cannot be marked active")
def _():
    signer, ring, registry = wiring()
    policy = build()
    issue(policy, signer, registry)
    assert resolve(policy.reference, registry, ring, as_of=T_TO).reason is (
        PolicyResolutionReason.EXPIRED
    )
    assert resolve(policy.reference, registry, ring, as_of=T_TO - SEC).status is (
        PolicyResolutionStatus.RESOLVED
    )
    assert resolve(policy.reference, registry, ring, as_of=T_FROM).status is (
        PolicyResolutionStatus.RESOLVED
    )
    assert resolve(policy.reference, registry, ring, as_of=T_FROM - SEC).reason is (
        PolicyResolutionReason.NOT_YET_EFFECTIVE
    )


@probe("no non-active lifecycle state can be issued as active")
def _():
    signer, _, registry = wiring()
    for state in (
        PolicyLifecycleState.DRAFT,
        PolicyLifecycleState.EXPIRED,
        PolicyLifecycleState.REVOKED,
        PolicyLifecycleState.SUPERSEDED,
    ):
        refuses(lambda s=state: issue(build(lifecycle_state=s), signer, registry))
    assert len(registry._issued) == 0


@probe("supersession is never inferred from an unstructured reference")
def _():
    signer, ring, registry = wiring()
    v1 = build(policy_id="p", version="1.0.0", effective_to=None)
    v2 = build(policy_id="p", version="2.0.0", effective_to=None, supersedes_ref="p@1.0.0")
    issue(v1, signer, registry, record_id="r1")
    issue(v2, signer, registry, record_id="r2")

    assert resolve(v1.reference, registry, ring).status is PolicyResolutionStatus.RESOLVED
    strict = resolve(
        v1.reference, registry, ring,
        supersession=SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR,
    )
    assert strict.reason is PolicyResolutionReason.SUPERSESSION_UNDETERMINED
    assert strict.policy is None
    # The older record is neither mutated nor deleted.
    assert registry.get_issued(v1.reference) is not None


@probe("a caller-owned collection cannot reach a stored record")
def _():
    from ugence_uvi_policy_contracts.api import (
        GateCategory,
        PolicyGate,
        ReadinessTarget,
        RequirementClass,
    )

    gates = [
        PolicyGate(
            gate_id="g1", category=GateCategory.SAFETY,
            requirement_class=RequirementClass.MANDATORY,
            applicability=(ReadinessTarget.PILOT,),
        )
    ]
    signer, ring, registry = wiring()
    policy = build(PolicyFamily.READINESS, body_overrides={"gates": gates})
    issue(policy, signer, registry)
    gates.clear()
    stored = registry.get_issued(policy.reference)
    assert len(stored.policy.gates) == 1
    assert resolve(policy.reference, registry, ring).status is PolicyResolutionStatus.RESOLVED


@probe("stored records are immutable")
def _():
    signer, _, registry = wiring()
    policy = build()
    record = issue(policy, signer, registry)
    for target, field in (
        (record, "record_id"),
        (record.policy_reference, "content_digest"),
        (record.policy.metadata, "lifecycle_state"),
    ):
        try:
            setattr(target, field, "hijacked")
            raise AssertionError(f"{type(target).__name__}.{field} was mutable")
        except dataclasses.FrozenInstanceError:
            pass


@probe("the authority evaluates no readiness and calculates no value")
def _():
    from ugence_uvi_policy_authority import api

    for banned in (
        "evaluate_readiness", "calculate_value", "FinancialValuation",
        "ReadinessDetermination", "forecast", "resolve_benchmark",
        "SourceBasis", "VerificationStatus", "MetricClaim",
    ):
        assert banned not in api.__all__, banned
        assert not hasattr(api, banned), banned

    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                lowered = f.name.lower()
                for banned in ("multiplier", "roi", "uplift", "score", "weight"):
                    assert banned not in lowered, (name, f.name)


@probe("no readiness, governed-value or foreign package is imported")
def _():
    import ast

    import ugence_uvi_policy_authority

    root = pathlib.Path(ugence_uvi_policy_authority.__file__).resolve().parent
    forbidden = {
        "ugence_agent_value_readiness", "governed_value", "ugence_governed_value",
        "risk_authority", "ugence_decision_authority", "agent_runtime",
        "runtime_assurance", "forecasting", "benchmark_registry",
        "governance_providers", "pydantic", "numpy", "fastapi", "cryptography", "nacl",
    }
    seen: set[str] = set()
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                seen.add(node.module.split(".")[0])
    assert not seen & forbidden, seen & forbidden


@probe("no system clock is reachable")
def _():
    import ugence_uvi_policy_authority

    root = pathlib.Path(ugence_uvi_policy_authority.__file__).resolve().parent
    for path in root.rglob("*.py"):
        source = path.read_text()
        for token in ("datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()"):
            assert token not in source, (path.name, token)


@probe("issuance and resolution are byte-deterministic")
def _():
    from ugence_uvi_policy_authority.canonical import canonical_bytes

    policy = build(PolicyFamily.VALUATION)
    records = []
    for _ in range(3):
        signer, ring, registry = wiring()
        records.append(canonical_bytes(issue(policy, signer, registry)))
    assert len(set(records)) == 1

    signer, ring, registry = wiring()
    issue(policy, signer, registry)
    outcomes = {
        (resolve(policy.reference, registry, ring).status,
         resolve(policy.reference, registry, ring).reason)
        for _ in range(5)
    }
    assert len(outcomes) == 1


@probe("all five merged families round-trip, and only those five exist")
def _():
    from ugence_uvi_policy_authority.api import SUPPORTED_POLICY_FAMILIES

    assert set(SUPPORTED_POLICY_FAMILIES) == set(PolicyFamily)
    assert len(SUPPORTED_POLICY_FAMILIES) == 5
    for family in PolicyFamily:
        signer, ring, registry = wiring()
        policy = build(family)
        issue(policy, signer, registry)
        assert resolve(policy.reference, registry, ring).status is (
            PolicyResolutionStatus.RESOLVED
        ), family


@probe("an unconfigured deployment issues nothing and resolves nothing")
def _():
    signer, ring, registry = wiring()
    policy = build()
    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=evidence(),
        approval_verifier=DenyAllApprovalVerifier(), signer=signer,
        registry=registry, issued_at=T_MID,
    ), expected=PolicyApprovalError)
    issue(policy, signer, registry)
    assert resolve_policy(
        reference=policy.reference, expected_tenant_id="", as_of=T_MID,
        registry=registry, signature_verifier=DenyAllSignatureVerifier(),
    ).reason is PolicyResolutionReason.KEY_UNKNOWN


def main() -> int:
    print("UVI Policy Authority — independent adversarial probes\n")
    for outcome, description in _RESULTS:
        marker = "  [ok]  " if outcome == "held" else f"  [{outcome}] "
        print(f"{marker}{description}")
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} PROBE(S) BREACHED:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"ALL {len(_RESULTS)} PROBES HELD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
