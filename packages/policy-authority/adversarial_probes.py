#!/usr/bin/env python3
"""Independent adversarial probes against the shared Ugence Policy Authority.

Deliberately *separate* from the pytest suite and sharing none of its fixtures:
these probes rebuild every artifact from scratch and attack the package through
its **public API only**, so a mistake in the test fixtures cannot mask a real
hole.

Each probe states an attack an untrusted caller might attempt and asserts the
authority refuses it. Run:

    python packages/policy-authority/adversarial_probes.py

Exit code 0 when every probe held; non-zero on the first breach.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import pathlib
import sys
import threading
import unicodedata
from datetime import datetime, timedelta, timezone

_HERE = pathlib.Path(__file__).resolve().parent
for _path in (
    _HERE / "src",
    _HERE.parent / "governance-contracts" / "src",
    _HERE.parent / "uvi-policy-contracts" / "src",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from ugence_policy_authority.api import (  # noqa: E402
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_ID,
    AUTHORITY_PROTOCOL_VERSION,
    CANONICALIZATION_VERSION,
    SUPERSESSION_REFERENCE_UNSUPPORTED,
    AdapterRegistry,
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerificationStatus,
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    HistoricalResolutionRule,
    InMemoryPolicyRegistry,
    IssuedPolicyRecord,
    KeyEntitlement,
    PolicyApprovalError,
    PolicyAuthorityError,
    PolicyCanonicalizationError,
    PolicyCoordinate,
    PolicyKeyRing,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    SigningKey,
    UnsupportedSupersessionError,
    canonical_bytes,
    default_uvi_adapters,
    issue_policy,
    resolve_policy,
    revoke_policy,
    uvi_coordinate,
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

ISSUER = "ugence.policy-authority"
REVOKER = "ugence.policy-authority.revocation"
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

_ADAPTERS = default_uvi_adapters()
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
    return cls(metadata=meta(_ADAPTERS.describe(draft).body_digest()), **body)


class Verifier:
    def __init__(self, status=ApprovalVerificationStatus.APPROVED, approver=APPROVER):
        self.status, self.approver, self.calls = status, approver, 0

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        self.calls += 1
        return ApprovalVerification(
            verified=self.status is ApprovalVerificationStatus.APPROVED,
            status=self.status,
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approving_authority_id=self.approver,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
        )


class CountingSigner:
    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    authority_id = property(lambda s: s.inner.authority_id)
    key_id = property(lambda s: s.inner.key_id)
    signature_alg = property(lambda s: s.inner.signature_alg)

    def sign(self, payload):
        self.calls += 1
        return self.inner.sign(payload)


EV = ApprovalEvidenceRef(
    approval_ref="APPROVAL-1",
    approval_digest=hashlib.sha256(b"approval").hexdigest(),
    approving_authority_id=APPROVER,
)


def wiring(seed=1):
    signer = Ed25519PolicySigner(
        authority_id=ISSUER, key_id="k-issue", signing_key=SigningKey.from_seed(bytes([seed]) * 32)
    )
    revoker = Ed25519PolicySigner(
        authority_id=REVOKER, key_id="k-rev", signing_key=SigningKey.from_seed(bytes([seed + 90]) * 32)
    )
    ring = PolicyKeyRing(
        [
            signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
            revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
        ]
    )
    return signer, revoker, ring, InMemoryPolicyRegistry()


def issue(policy, signer, registry, verifier=None, **kwargs):
    return issue_policy(
        policy=policy,
        record_id=kwargs.pop("record_id", "rec-1"),
        approval=kwargs.pop("approval", EV),
        approval_verifier=verifier or Verifier(),
        signer=signer,
        registry=registry,
        adapters=kwargs.pop("adapters", _ADAPTERS),
        issued_at=kwargs.pop("issued_at", T_MID),
        **kwargs,
    )


def resolve(reference, registry, ring, *, as_of=T_MID, tenant="", **kwargs):
    return resolve_policy(
        reference=reference,
        expected_reference_tenant_id=tenant,
        as_of=as_of,
        registry=registry,
        signature_verifier=ring,
        adapters=kwargs.pop("adapters", _ADAPTERS),
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
# Naming and ownership
# --------------------------------------------------------------------------- #
@probe("the retired UVI-owned namespace and distribution are absent")
def _():
    assert importlib.util.find_spec("ugence_uvi_policy_authority") is None
    root = pathlib.Path(
        importlib.util.find_spec("ugence_policy_authority").origin
    ).resolve().parent
    for path in root.rglob("*.py"):
        source = path.read_text()
        assert "ugence_uvi_policy_authority" not in source, path
        assert "ugence-uvi-policy-authority" not in source, path
    assert root.name == "ugence_policy_authority"
    assert root.parents[1].name == "policy-authority"


@probe("the authority protocol identity is platform-neutral and versioned")
def _():
    assert AUTHORITY_PROTOCOL == "ugence.policy-authority"
    assert AUTHORITY_PROTOCOL_VERSION == "v0.1"
    assert AUTHORITY_PROTOCOL_ID == "ugence.policy-authority/v0.1"
    assert CANONICALIZATION_VERSION == "ugence.policy-authority/canonicalization/v1"
    for identifier in (AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_ID, CANONICALIZATION_VERSION):
        assert "uvi" not in identifier.lower()
        assert "gv-2c" not in identifier.lower() and "gv2c" not in identifier.lower()


@probe("the generic core imports no policy family and branches on none")
def _():
    root = pathlib.Path(
        importlib.util.find_spec("ugence_policy_authority").origin
    ).resolve().parent
    banned_types = {
        "GeographyPolicy", "DomainPolicy", "IntendedOutcomePolicy",
        "ValuationPolicy", "ReadinessPolicy", "PolicyFamily", "PolicyReference",
    }
    for path in (root / "core").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "uvi_policy_contracts" not in node.module, path
            if isinstance(node, ast.Name):
                assert node.id not in banned_types, (path, node.id)
            if isinstance(node, ast.Attribute):
                assert node.attr not in banned_types, (path, node.attr)
    uvi_importers = {
        p.name
        for p in root.rglob("*.py")
        if "ugence_uvi_policy_contracts" in p.read_text()
    }
    assert uvi_importers == {"uvi.py"}, uvi_importers


# --------------------------------------------------------------------------- #
# Approval
# --------------------------------------------------------------------------- #
@probe("a caller cannot self-approve with a boolean, a name, or a lifecycle label")
def _():
    signer, _, ring, registry = wiring()
    counting = CountingSigner(signer)
    policy = build()

    try:
        issue_policy(
            policy=policy, record_id="r", approved=True, approval_verifier=Verifier(),
            signer=counting, registry=registry, adapters=_ADAPTERS, issued_at=T_MID,
        )
        raise AssertionError("an `approved=True` keyword was accepted")
    except TypeError:
        pass

    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=APPROVER, approval_verifier=Verifier(),
        signer=counting, registry=registry, adapters=_ADAPTERS, issued_at=T_MID,
    ))

    assert policy.metadata.lifecycle_state is PolicyLifecycleState.APPROVED_ACTIVE
    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=EV,
        approval_verifier=DenyAllApprovalVerifier(), signer=counting,
        registry=registry, adapters=_ADAPTERS, issued_at=T_MID,
    ), expected=PolicyApprovalError)

    assert counting.calls == 0, "the signer ran during a failed approval"
    assert len(registry._issued) == 0


@probe("a fabricated duck-typed approval verification is rejected")
def _():
    class DuckVerifier:
        def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
            fake = type("V", (), {})()
            fake.verified = True
            fake.status = ApprovalVerificationStatus.APPROVED
            fake.coordinate = coordinate
            fake.policy_body_digest = policy_body_digest
            fake.approving_authority_id = APPROVER
            fake.approval_ref = approval.approval_ref
            fake.approval_digest = approval.approval_digest
            fake.verified_at = as_of
            fake.approved_from = fake.approved_to = None
            fake.detail = ""
            return fake

    signer, _, _, registry = wiring()
    refuses(lambda: issue(build(), signer, registry, verifier=DuckVerifier()),
            expected=PolicyApprovalError)
    assert len(registry._issued) == 0


@probe("the issuing authority cannot name itself the approver")
def _():
    signer, _, _, registry = wiring()
    refuses(lambda: issue(
        build(), signer, registry, verifier=Verifier(approver=ISSUER),
        approval=ApprovalEvidenceRef(
            approval_ref="A", approval_digest=hashlib.sha256(b"a").hexdigest(),
            approving_authority_id=ISSUER,
        ),
    ), expected=PolicyApprovalError)
    assert len(registry._issued) == 0


# --------------------------------------------------------------------------- #
# Digest and canonicalization
# --------------------------------------------------------------------------- #
@probe("an arbitrary well-formed digest is not proof the body matches")
def _():
    signer, _, _, registry = wiring()
    policy = build()
    arbitrary = hashlib.sha256(b"unrelated").hexdigest()
    forged = dataclasses.replace(
        policy, metadata=dataclasses.replace(policy.metadata, content_digest=arbitrary)
    )
    refuses(lambda: issue(forged, signer, registry))
    assert len(registry._issued) == 0


@probe("policy content cannot change while the reference stays valid")
def _():
    signer, _, ring, registry = wiring()
    policy = build(PolicyFamily.GEOGRAPHY)
    record = issue(policy, signer, registry)
    object.__setattr__(record, "policy", dataclasses.replace(record.policy, jurisdiction="XX"))
    assert resolve(policy.reference, registry, ring).reason is (
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH
    )


@probe("only the declared metadata.content_digest path is excluded from the digest")
def _():
    from ugence_governance_contracts.api import BenchmarkReference

    a = build(body_overrides={"domain_benchmark_refs": (
        BenchmarkReference(benchmark_id="b", version="1", content_digest="a" * 64),)})
    b = build(body_overrides={"domain_benchmark_refs": (
        BenchmarkReference(benchmark_id="b", version="1", content_digest="b" * 64),)})
    assert a.metadata.content_digest != b.metadata.content_digest, (
        "a nested content_digest must stay bound"
    )
    projection = _ADAPTERS.describe(a).canonical_projection
    assert "content_digest" not in projection["metadata"]
    assert projection["domain_benchmark_refs"][0]["content_digest"] == "a" * 64


@probe("NFC is accepted and NFD is rejected recursively, never silently folded")
def _():
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd

    assert canonical_bytes({"j": nfc})
    for payload in ({"j": nfd}, {"a": [nfd]}, {"a": {"b": {"c": nfd}}}, {nfd: "v"}):
        try:
            canonical_bytes(payload)
            raise AssertionError(f"NFD accepted in {payload!r}")
        except PolicyCanonicalizationError as exc:
            assert "NFC" in str(exc)

    nfc_policy = build(body_overrides={"governed_outcome_unit": nfc})
    nfd_policy = dataclasses.replace(nfc_policy, governed_outcome_unit=nfd)
    try:
        _ADAPTERS.describe(nfd_policy).body_digest()
        raise AssertionError("an NFD policy field was digested")
    except PolicyCanonicalizationError:
        pass


@probe("a naive datetime is rejected by the canonicalization helper directly")
def _():
    naive = datetime(2026, 6, 1)
    for call in (
        lambda: canonical_bytes(naive),
        lambda: canonical_bytes({"when": naive}),
        lambda: canonical_bytes({"a": [{"b": naive}]}),
    ):
        refuses(call, expected=PolicyCanonicalizationError)

    signer, _, ring, registry = wiring()
    policy = build()
    refuses(lambda: issue(policy, signer, registry, issued_at=naive))
    issue(policy, signer, registry)
    refuses(lambda: resolve(policy.reference, registry, ring, as_of=naive))


# --------------------------------------------------------------------------- #
# Supersession
# --------------------------------------------------------------------------- #
@probe("unstructured supersession is rejected before any collaborator is called")
def _():
    signer, _, _, registry = wiring()
    verifier = Verifier()
    counting = CountingSigner(signer)

    for ref in ("p@1.0.0", "prior", "  padded  ", "latest", "*", "../../etc/passwd"):
        try:
            issue_policy(
                policy=build(supersedes_ref=ref), record_id="r", approval=EV,
                approval_verifier=verifier, signer=counting, registry=registry,
                adapters=_ADAPTERS, issued_at=T_MID,
            )
            raise AssertionError(f"a non-empty supersedes_ref {ref!r} was accepted")
        except UnsupportedSupersessionError as exc:
            assert SUPERSESSION_REFERENCE_UNSUPPORTED in str(exc)

    assert verifier.calls == 0, "the approval verifier ran on a rejected artifact"
    assert counting.calls == 0, "the signer ran on a rejected artifact"
    assert len(registry._issued) == 0, "a rejected artifact reached the registry"


@probe("empty and whitespace-only supersession references issue normally")
def _():
    for ref in ("", "   ", "\t\n  \r"):
        signer, _, ring, registry = wiring()
        policy = build(supersedes_ref=ref)
        issue(policy, signer, registry)
        assert resolve(policy.reference, registry, ring).resolved, repr(ref)


@probe("supersession rejection does not poison other versions of the identity")
def _():
    signer, _, ring, registry = wiring()
    v1 = build(policy_id="p", version="1.0.0")
    issue(v1, signer, registry, record_id="r1")
    refuses(lambda: issue(
        build(policy_id="p", version="2.0.0", supersedes_ref="p@1.0.0"),
        signer, registry, record_id="r2",
    ))
    assert resolve(v1.reference, registry, ring).resolved
    v2 = build(policy_id="p", version="2.0.0")
    issue(v2, signer, registry, record_id="r2")
    assert resolve(v2.reference, registry, ring).resolved


@probe("a directly injected legacy record with supersession fails closed")
def _():
    signer, _, ring, registry = wiring()
    clean = build()
    record = issue(clean, signer, registry)
    legacy = build(supersedes_ref="p@1.0.0")
    object.__setattr__(record, "policy", legacy)
    object.__setattr__(record, "coordinate", uvi_coordinate(legacy.reference))
    object.__setattr__(record, "policy_body_digest", legacy.metadata.content_digest)
    registry._issued = {uvi_coordinate(legacy.reference): record}

    class AlwaysValid:
        def verify(self, **kwargs):
            from ugence_policy_authority.api import KeyVerification, KeyVerificationStatus

            return KeyVerification(status=KeyVerificationStatus.VALID, key_id="k")

    result = resolve(legacy.reference, registry, AlwaysValid())
    assert result.reason is PolicyResolutionReason.SUPERSESSION_REFERENCE_UNSUPPORTED
    assert result.policy is None


@probe("no permissive supersession posture survives in the public API")
def _():
    from ugence_policy_authority import api

    for banned in ("SupersessionRule", "SELF_DECLARED_ONLY", "SUPERSESSION_UNDETERMINED"):
        assert banned not in api.__all__, banned
        assert not hasattr(api, banned), banned


# --------------------------------------------------------------------------- #
# Signing and revocation
# --------------------------------------------------------------------------- #
@probe("a hand-forged issuance record does not resolve")
def _():
    signer, _, ring, registry = wiring()
    policy = build()
    forged = IssuedPolicyRecord(
        record_id="forged",
        coordinate=uvi_coordinate(policy.reference),
        adapter_id="ugence.uvi.policy-family/v1",
        policy_type="DomainPolicy",
        policy=policy,
        policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id=ISSUER,
        key_id="k-issue",
        signature_alg="ed25519",
        signature=b"\x99" * 64,
        approving_authority_id=APPROVER,
        approval_ref="APPROVAL-FORGED",
        approval_digest=hashlib.sha256(b"x").hexdigest(),
        issued_at=T_MID,
    )
    registry.append_issuance(forged)
    assert registry.get_issued(uvi_coordinate(policy.reference)) is forged
    assert resolve(policy.reference, registry, ring).reason is (
        PolicyResolutionReason.SIGNATURE_INVALID
    )


@probe("every signed issuance field is tamper-evident")
def _():
    signer, _, ring, registry = wiring()
    record = issue(build(), signer, registry)
    substitutes = {
        "record_id": "tampered",
        "adapter_id": "attacker.adapter",
        "policy_body_digest": "d" * 64,
        "issuing_authority_id": "attacker",
        "key_id": "k-other",
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
            required_entitlement=KeyEntitlement.ISSUE_POLICY,
            as_of=T_MID,
        ).valid, field


@probe("an unsigned or unauthorized revocation cannot be created")
def _():
    signer, revoker, ring, registry = wiring()
    policy = build(effective_to=None)
    issue(policy, signer, registry)

    def revoke(**kwargs):
        params = dict(
            reference=policy.reference, revocation_id="rv-1",
            reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
            registry=registry, adapters=_ADAPTERS, signer=revoker,
            signature_verifier=ring, revoked_at=T_MID,
        )
        params.update(kwargs)
        return revoke_policy(**params)

    refuses(lambda: revoke(signer=None))
    refuses(lambda: revoke(signature_verifier=None))
    refuses(lambda: revoke(reason_code=True))
    # The issue-only key is not entitled to revoke.
    refuses(lambda: revoke(signer=signer))
    # A foreign signer with a structurally valid signature is not authorized.
    foreign = Ed25519PolicySigner(
        authority_id="attacker", key_id="attacker-key",
        signing_key=SigningKey.from_seed(b"\x31" * 32),
    )
    refuses(lambda: revoke(signer=foreign))

    assert registry.revocations_for(uvi_coordinate(policy.reference)) == ()
    assert resolve(policy.reference, registry, ring).resolved


@probe("resolution verifies the revocation signature before applying it")
def _():
    signer, revoker, ring, registry = wiring()
    policy = build(effective_to=None)
    issue(policy, signer, registry)
    revocation = revoke_policy(
        reference=policy.reference, revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=registry, adapters=_ADAPTERS, signer=revoker,
        signature_verifier=ring, revoked_at=T_MID,
    )
    assert resolve(policy.reference, registry, ring).reason is PolicyResolutionReason.REVOKED

    coordinate = uvi_coordinate(policy.reference)
    for field, value in (
        ("signature", b"\x00" * 64),
        ("revoking_authority_id", "attacker"),
        ("revoked_at", T_MID + SEC),
        ("reason_code", PolicyRevocationReasonCode.OTHER),
    ):
        registry._revocations[coordinate] = dataclasses.replace(revocation, **{field: value})
        result = resolve(policy.reference, registry, ring, as_of=T_FROM)
        assert result.reason is PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID, field
        assert result.policy is None, field


@probe("revocation cannot be bypassed, and history is explicitly labelled")
def _():
    signer, revoker, ring, registry = wiring()
    policy = build(effective_to=None)
    record = issue(policy, signer, registry)
    revoke_policy(
        reference=policy.reference, revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        registry=registry, adapters=_ADAPTERS, signer=revoker,
        signature_verifier=ring, revoked_at=T_MID,
    )
    registry.append_issuance(record)
    assert resolve(policy.reference, registry, ring).reason is PolicyResolutionReason.REVOKED
    assert resolve(policy.reference, registry, ring, as_of=T_MID - SEC).reason is (
        PolicyResolutionReason.REVOKED
    )

    historical = resolve(
        policy.reference, registry, ring, as_of=T_MID - SEC,
        historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
    )
    assert historical.status is PolicyResolutionStatus.RESOLVED
    assert historical.historical is True
    assert historical.implies_current_validity is False
    assert historical.as_of == T_MID - SEC


# --------------------------------------------------------------------------- #
# Trust anchors, registry, tenancy
# --------------------------------------------------------------------------- #
@probe("mutating a caller-owned key map after construction cannot inject a key")
def _():
    signer, _, _, _ = wiring()
    caller_map = {"k-issue": signer.verification_key()}
    ring = PolicyKeyRing(caller_map)

    attacker = Ed25519PolicySigner(
        authority_id="attacker", key_id="attacker-key",
        signing_key=SigningKey.from_seed(b"\x41" * 32),
    )
    caller_map["attacker-key"] = attacker.verification_key()
    caller_map.clear()
    assert ring.resolve("attacker-key") is None
    assert ring.resolve("k-issue") is not None

    for attempt in (
        lambda: ring.keys.__setitem__("attacker-key", attacker.verification_key()),
        lambda: ring.keys.update({"attacker-key": attacker.verification_key()}),
        lambda: setattr(ring, "_keys", {}),
        lambda: delattr(ring, "_keys"),
    ):
        try:
            attempt()
            raise AssertionError("a trust-anchor mutation succeeded")
        except (TypeError, AttributeError):
            pass
    assert ring.resolve("attacker-key") is None


@probe("concurrent conflicting issuance yields one winner and typed conflicts")
def _():
    from ugence_policy_authority.api import PolicyRegistryConflictError

    registry = InMemoryPolicyRegistry()
    records = []
    for i in range(12):
        signer, _, _, scratch = wiring()
        records.append(
            issue(
                build(policy_id="p", version="1.0.0",
                      body_overrides={"governed_outcome_unit": f"unit-{i}"}),
                signer, scratch, record_id=f"rec-{i}",
            )
        )

    barrier = threading.Barrier(len(records))
    ok, errors = [], []

    def run(i):
        barrier.wait()
        try:
            ok.append(registry.append_issuance(records[i]))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(records))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ok) == 1, f"{len(ok)} writers won the same slot"
    assert len(errors) == len(records) - 1
    assert all(isinstance(e, PolicyRegistryConflictError) for e in errors)
    assert len(registry._issued) == 1


@probe("cross-tenant access discloses nothing and never resolves")
def _():
    signer, _, ring, registry = wiring()
    policy = build(scope=PolicyScope.TENANT, tenant_id="tenant-a")
    issue(policy, signer, registry, expected_reference_tenant_id="tenant-a")

    cross = resolve(policy.reference, registry, ring, tenant="tenant-b")
    assert cross.reason is PolicyResolutionReason.TENANT_SCOPE_MISMATCH
    assert cross.policy is None and "tenant-a" not in cross.detail

    hijacked = dataclasses.replace(policy.reference, tenant_id="tenant-b")
    missing = resolve(hijacked, registry, ring, tenant="tenant-b")
    assert missing.reason is PolicyResolutionReason.NOT_FOUND
    # A real-but-other-tenant probe is indistinguishable from a nonexistent one.
    ghost = dataclasses.replace(policy.reference, policy_id="never-existed", tenant_id="tenant-b")
    assert resolve(ghost, registry, ring, tenant="tenant-b").reason is missing.reason


@probe("raw registry retrieval cannot substitute for trusted resolution")
def _():
    signer, _, ring, registry = wiring()
    policy = build()
    forged = IssuedPolicyRecord(
        record_id="forged", coordinate=uvi_coordinate(policy.reference),
        adapter_id="ugence.uvi.policy-family/v1", policy_type="DomainPolicy",
        policy=policy, policy_body_digest=policy.metadata.content_digest,
        issuing_authority_id="attacker", key_id="attacker-key", signature_alg="ed25519",
        signature=b"\xbb" * 64, approving_authority_id=APPROVER, approval_ref="A",
        approval_digest=hashlib.sha256(b"a").hexdigest(), issued_at=T_MID,
    )
    registry.append_issuance(forged)
    assert registry.get_issued(uvi_coordinate(policy.reference)) is forged
    assert not resolve(policy.reference, registry, ring).resolved


@probe("a caller-owned collection cannot reach a stored record or its digest")
def _():
    from ugence_uvi_policy_contracts.api import (
        GateCategory, PolicyGate, ReadinessTarget, RequirementClass,
    )

    gates = [PolicyGate(
        gate_id="g1", category=GateCategory.SAFETY,
        requirement_class=RequirementClass.MANDATORY,
        applicability=(ReadinessTarget.PILOT,),
    )]
    signer, _, ring, registry = wiring()
    policy = build(PolicyFamily.READINESS, body_overrides={"gates": gates})
    before = policy.metadata.content_digest
    issue(policy, signer, registry)
    gates.clear()
    gates.append("garbage")
    stored = registry.get_issued(uvi_coordinate(policy.reference))
    assert len(stored.policy.gates) == 1
    assert _ADAPTERS.describe(stored.policy).body_digest() == before
    assert resolve(policy.reference, registry, ring).resolved


@probe("stored records are immutable")
def _():
    signer, _, _, registry = wiring()
    policy = build()
    record = issue(policy, signer, registry)
    for target, field in (
        (record, "record_id"),
        (record.coordinate, "content_digest"),
        (record.policy.metadata, "lifecycle_state"),
    ):
        try:
            setattr(target, field, "hijacked")
            raise AssertionError(f"{type(target).__name__}.{field} was mutable")
        except dataclasses.FrozenInstanceError:
            pass


@probe("no floating reference is representable")
def _():
    registry = InMemoryPolicyRegistry()
    for forbidden in ("latest", "current", "newest", "find_by_id", "head", "search"):
        assert not hasattr(registry, forbidden), forbidden
    from ugence_uvi_policy_contracts.api import PolicyContractError, PolicyReference

    try:
        PolicyReference(
            policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1.0.0", content_digest=""
        )
        raise AssertionError("a digest-free reference was constructible")
    except PolicyContractError:
        pass
    try:
        PolicyCoordinate(
            policy_family="DOMAIN", policy_id="p", version="1", content_digest="", scope="GLOBAL"
        )
        raise AssertionError("a digest-free coordinate was constructible")
    except PolicyAuthorityError:
        pass


# --------------------------------------------------------------------------- #
# Scope of the capability
# --------------------------------------------------------------------------- #
@probe("the authority authorizes nothing and computes no money, readiness or forecast")
def _():
    from ugence_policy_authority import api

    for banned in (
        "evaluate_readiness", "calculate_value", "FinancialValuation",
        "ReadinessDetermination", "forecast", "resolve_benchmark", "authorize",
        "authorize_action", "RiskAuthorizationEnvelope", "SourceBasis",
        "VerificationStatus", "MetricClaim",
    ):
        assert banned not in api.__all__, banned
        assert not hasattr(api, banned), banned

    for name in api.__all__:
        obj = getattr(api, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                lowered = f.name.lower()
                for banned in (
                    "multiplier", "roi", "uplift", "score", "weight", "money",
                    "amount", "currency", "authorized", "authorization", "permit",
                ):
                    assert banned not in lowered, (name, f.name)


@probe("no readiness, governed-value or foreign package is imported")
def _():
    root = pathlib.Path(
        importlib.util.find_spec("ugence_policy_authority").origin
    ).resolve().parent
    forbidden = {
        "ugence_agent_value_readiness", "governed_value", "ugence_governed_value",
        "risk_authority", "ugence_decision_authority", "agent_runtime",
        "runtime_assurance", "forecasting", "benchmark_registry",
        "governance_providers", "pydantic", "numpy", "fastapi", "cryptography", "nacl",
        "ugence_governance_contracts",
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


@probe("no wall clock is reachable")
def _():
    root = pathlib.Path(
        importlib.util.find_spec("ugence_policy_authority").origin
    ).resolve().parent
    for path in root.rglob("*.py"):
        source = path.read_text()
        for token in (
            "datetime.now(", "datetime.utcnow(", "time.time(", ".utcnow()",
            "uuid4(", "os.environ", "getenv(",
        ):
            assert token not in source, (path.name, token)


@probe("issuance is byte-deterministic and reads one injected instant")
def _():
    policy = build(PolicyFamily.VALUATION)
    payloads = set()
    for _ in range(3):
        signer, _, _, registry = wiring()
        payloads.add(issue(policy, signer, registry).signing_payload())
    assert len(payloads) == 1

    signer, _, ring, registry = wiring()
    verifier = Verifier()
    record = issue(policy, signer, registry, verifier=verifier)
    assert record.issued_at == T_MID and verifier.calls == 1


@probe("all five UVI families round-trip through the shared authority")
def _():
    for family in PolicyFamily:
        signer, _, ring, registry = wiring()
        policy = build(family)
        issue(policy, signer, registry)
        assert resolve(policy.reference, registry, ring).status is (
            PolicyResolutionStatus.RESOLVED
        ), family


@probe("an unconfigured deployment issues nothing and resolves nothing")
def _():
    signer, _, _, registry = wiring()
    policy = build()
    refuses(lambda: issue_policy(
        policy=policy, record_id="r", approval=EV,
        approval_verifier=DenyAllApprovalVerifier(), signer=signer,
        registry=registry, adapters=_ADAPTERS, issued_at=T_MID,
    ), expected=PolicyApprovalError)
    issue(policy, signer, registry)
    assert resolve(policy.reference, registry, DenyAllSignatureVerifier()).reason is (
        PolicyResolutionReason.KEY_UNKNOWN
    )


def main() -> int:
    print("Shared Ugence Policy Authority — independent adversarial probes\n")
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
