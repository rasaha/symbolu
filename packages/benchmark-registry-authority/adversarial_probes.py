#!/usr/bin/env python3
"""Independent adversarial probes for the Benchmark Registry Authority (BR-2B).

Deliberately **independent** of the package's own test suite: this file imports
no test module, no ``_builders`` helper, no ``conftest`` and no private
submodule. It uses the two packages' curated public APIs and the standard
library only, so it exercises exactly what a consumer can reach — and it runs
unchanged against the source tree or against an installed wheel.

Every probe attempts something an attacker or a careless consumer would try, and
asserts the package refuses it, or that the refusal is detectable. Each is
attempted against a **working** happy path first, so a probe that passed because
its fixture was already broken shows up as the happy-path probe failing.

Run:
    PYTHONPATH=packages/benchmark-registry-authority/src:packages/benchmark-registry/src \\
        python packages/benchmark-registry-authority/adversarial_probes.py
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pickle
import sys
from datetime import datetime, timedelta, timezone

from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkLifecycleState,
    BenchmarkRefusalReason,
    BenchmarkScope,
)
from ugence_benchmark_registry_authority.api import (
    BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    BENCHMARK_BANNED_REGISTRATION_STATE_NAMES,
    BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT,
    BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_REGISTRATION_TRANSITIONS,
    BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
    BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS,
    BENCHMARK_REGISTRY_DECLARED_CONSISTENCY,
    BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES,
    BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES,
    BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_SIGNING_FRAME_VERSION,
    BENCHMARK_TRANSITION_PAYLOAD_BINDING,
    BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES,
    BenchmarkAdmissionDecisionPayload,
    BenchmarkAdmissionOutcome,
    BenchmarkApprovalEnvelope,
    BenchmarkConflictRecordPayload,
    BenchmarkExactResolutionRequest,
    BenchmarkHistoricalInspectionRequest,
    BenchmarkHistoricalRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkRegistrationEventPayload,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
    BenchmarkPlanningOutcome,
    is_byte_identical_resubmission,
    plan_submission_outcome,
    plan_transition,
    BenchmarkRegistrationState,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryConsistencyClaim,
    BenchmarkRegistryContractError,
    BenchmarkRegistryFaultClass,
    BenchmarkRegistryLifecycleError,
    BenchmarkRegistryRefusalReason,
    BenchmarkRegistryStoreConsistencyDescriptor,
    BenchmarkResolutionRecordPayload,
    BenchmarkRevocationEnvelope,
    BenchmarkRevocationEventPayload,
    BenchmarkSignatureProfile,
    BenchmarkSubmissionRecordPayload,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
    canonical_bytes,
    canonical_digest,
    fault_class_for,
    is_valid_registration_transition,
    require_bound_payload_for_transition,
    require_exact_historical_record_payload,
    require_exact_resolution_record_payload,
    require_valid_registration_transition,
)

# --------------------------------------------------------------------------- #
# Probe harness
# --------------------------------------------------------------------------- #
_PROBES = []
_FAILURES = []


def probe(name):
    def register(fn):
        _PROBES.append((name, fn))
        return fn

    return register


def refuses(fn, *types):
    """Assert ``fn()`` raises one of ``types``, and return the exception."""

    try:
        fn()
    except types as exc:
        return exc
    except BaseException as exc:  # noqa: BLE001 - wrong exception is a failure
        raise AssertionError(
            f"raised {type(exc).__name__} rather than one of "
            f"{[t.__name__ for t in types]}: {exc}"
        ) from exc
    raise AssertionError("did not refuse")


# --------------------------------------------------------------------------- #
# Fixtures — re-declared here, never imported from the test suite
# --------------------------------------------------------------------------- #
IDENTITY_DIGEST = "a1" * 32
CONTENT_DIGEST = "b2" * 32
OTHER_DIGEST = "c3" * 32
PUB_SIG = "01" * 64
APP_SIG = "02" * 64
REV_SIG = "03" * 64
T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
PROFILE = BenchmarkSignatureProfile.ED25519_SHA512_V1
# BR-2C fixtures. Re-declared here with the same literals the suite uses, and
# arrived at independently: the pinned vectors only agree if both harnesses
# encode the same values the same way.
PUB_KEY = "d4" * 32
APP_KEY = "e5" * 32
REV_KEY = "f6" * 32
ANCHOR_FROM = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
TRUSTED_INSTANT = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
ANCHOR_REVOKED_AT = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def coordinate(**kw):
    base = dict(
        benchmark_id="bmk",
        benchmark_family="fam",
        benchmark_version="1.2.3",
        scope=BenchmarkScope.for_tenant("t1"),
        geography=BenchmarkApplicabilityCoordinate.applicable("eu"),
        domain=BenchmarkApplicabilityCoordinate.not_applicable(),
    )
    base.update(kw)
    return BenchmarkCoordinate(**base)


def publisher(**kw):
    base = dict(
        coordinate=coordinate(),
        benchmark_identity_digest=IDENTITY_DIGEST,
        benchmark_content_digest=CONTENT_DIGEST,
        publisher_identity="publisher-alpha",
        publisher_key_id="publisher-key-1",
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        detached_signature=PUB_SIG,
    )
    base.update(kw)
    return BenchmarkPublisherSubmissionEnvelope(**base)


def approval(**kw):
    base = dict(
        publisher_submission_envelope=publisher(),
        approval_authority_identity="approval-authority-beta",
        approval_authority_key_id="approval-key-1",
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
        applicable_policy_ref="benchmark-approval-policy/v1",
        validity_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        validity_to=T2,
        detached_signature=APP_SIG,
    )
    base.update(kw)
    return BenchmarkApprovalEnvelope(**base)


def revocation_envelope(**kw):
    base = dict(
        coordinate=coordinate(),
        admitted_digest=IDENTITY_DIGEST,
        revoker_identity="revoker-delta",
        revoker_key_id="revocation-key-1",
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        declared_revocation_reason="content-defect-identified",
        effective_at=T1,
        detached_signature=REV_SIG,
    )
    base.update(kw)
    return BenchmarkRevocationEnvelope(**base)


def record(**kw):
    base = dict(
        publisher_submission_envelope=publisher(),
        declared_registry_authority_identity="registry-authority-gamma",
        declared_recorded_at=T0,
    )
    base.update(kw)
    return BenchmarkSubmissionRecordPayload(**base)


def decision(**kw):
    base = dict(
        submission_record=record(),
        approval_envelope=approval(),
        declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
        declared_recorded_at=T0,
    )
    base.update(kw)
    return BenchmarkAdmissionDecisionPayload(**base)


def rejected_decision(**kw):
    base = dict(
        submission_record=record(),
        approval_envelope=approval(
            declared_outcome=BenchmarkAdmissionOutcome.REJECTED
        ),
        declared_outcome=BenchmarkAdmissionOutcome.REJECTED,
        declared_recorded_at=T0,
        declared_refusal_reason=BenchmarkRegistryRefusalReason.PUBLISHER_UNTRUSTED,
    )
    base.update(kw)
    return BenchmarkAdmissionDecisionPayload(**base)


def registration(**kw):
    base = dict(admission_decision=decision(), declared_recorded_at=T0)
    base.update(kw)
    return BenchmarkRegistrationEventPayload(**base)


def revocation(**kw):
    base = dict(
        registration_event=registration(),
        revocation_envelope=revocation_envelope(),
        declared_recorded_at=T0,
    )
    base.update(kw)
    return BenchmarkRevocationEventPayload(**base)


def post_admission_rejection(**kw):
    base = dict(
        admission_decision=decision(),
        declared_refusal_reason=BenchmarkRegistryRefusalReason.APPROVAL_UNVERIFIED,
        declared_recorded_at=T0,
    )
    base.update(kw)
    return BenchmarkPostAdmissionRejectionEventPayload(**base)


def snapshot_assertion(**overrides):
    """Independently built here, not shared with the suite's fixtures."""

    base = dict(
        coordinate=coordinate(),
        asserted_current_state=BenchmarkRegistrationState.ADMITTED,
        asserted_registration_record_presence=(
            BenchmarkRegistrationRecordPresence.NO_RECORD_APPENDED
        ),
    )
    base.update(overrides)
    return BenchmarkRegistrySnapshotAssertion(**base)


def anchor(**overrides):
    kwargs = dict(
        role=BenchmarkTrustRole.PUBLISHER,
        identity="publisher-alpha",
        key_id="publisher-key-1",
        signature_profile=PROFILE,
        public_key_material=PUB_KEY,
        validity_from=ANCHOR_FROM,
        validity_to=T2,
        status=BenchmarkTrustAnchorStatus.ENABLED,
        revoked_at=None,
        revocation_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkTrustAnchorRecord(**kwargs)


def publisher_verified(**overrides):
    kwargs = dict(
        verified_digest=IDENTITY_DIGEST,
        signer_role=BenchmarkTrustRole.PUBLISHER,
        signer_identity="publisher-alpha",
        signer_key_id="publisher-key-1",
        signature_profile=PROFILE,
        anchor_record_digest=OTHER_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkPublisherVerifiedResult(**kwargs)


def approval_verified(**overrides):
    kwargs = dict(
        verified_digest=CONTENT_DIGEST,
        signer_role=BenchmarkTrustRole.APPROVER,
        signer_identity="approval-authority-beta",
        signer_key_id="approval-key-1",
        signature_profile=PROFILE,
        anchor_record_digest=OTHER_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkApprovalVerifiedResult(**kwargs)


def revocation_verified(**overrides):
    kwargs = dict(
        verified_digest=OTHER_DIGEST,
        signer_role=BenchmarkTrustRole.REVOKER,
        signer_identity="revoker-delta",
        signer_key_id="revocation-key-1",
        signature_profile=PROFILE,
        anchor_record_digest=IDENTITY_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkRevocationVerifiedResult(**kwargs)


ALL_BUILDERS = (
    publisher,
    approval,
    revocation_envelope,
    record,
    decision,
    post_admission_rejection,
    registration,
    revocation,
    snapshot_assertion,
    lambda: BenchmarkTransitionPlan(
        snapshot=snapshot_assertion(),
        planned_to_state=BenchmarkRegistrationState.REGISTERED,
    ),
    lambda: BenchmarkTransitionRefusal(
        snapshot=snapshot_assertion(),
        refused_to_state=BenchmarkRegistrationState.REVOKED,
        declared_refusal_reason=(
            BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
        ),
    ),
    lambda: BenchmarkConflictRecordPayload(
        submission_record=record(),
        declared_refusal_reason=(
            BenchmarkRegistryRefusalReason.COORDINATE_SLOT_CONFLICT
        ),
        declared_recorded_at=T0,
    ),
    lambda: BenchmarkResolutionRecordPayload(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity="registry-authority-gamma",
    ),
    lambda: BenchmarkHistoricalRecordPayload(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity="registry-authority-gamma",
        as_of=T1,
    ),
    lambda: BenchmarkExactResolutionRequest(coordinate=coordinate()),
    lambda: BenchmarkHistoricalInspectionRequest(coordinate=coordinate(), as_of=T1),
    lambda: PlatformRegistryScopeExpectation(scope=BenchmarkScope.platform_wide()),
    lambda: TenantRegistryScopeExpectation(scope=BenchmarkScope.for_tenant("t1")),
    lambda: anchor(),
    lambda: publisher_verified(),
    lambda: approval_verified(),
    lambda: revocation_verified(),
)


# --------------------------------------------------------------------------- #
# Probes
# --------------------------------------------------------------------------- #
@probe("Q-00 the whole administrative chain constructs and digests")
def _q00():
    event = revocation()
    assert len(canonical_digest(event)) == 64
    assert event.declared_state is BenchmarkRegistrationState.REVOKED


@probe("Q-01 all twenty-two shipped artifacts canonicalize into twenty-two byte spaces")
def _q01():
    domains = set()
    for builder in ALL_BUILDERS:
        framed = json.loads(canonical_bytes(builder()).decode("utf-8"))
        domains.add(framed["domain"])
    assert len(domains) == 22, len(domains)
    assert domains == set(BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS)


@probe("Q-02 every digest is independently recomputable with hashlib alone")
def _q02():
    for builder in ALL_BUILDERS:
        obj = builder()
        assert (
            hashlib.sha256(canonical_bytes(obj)).hexdigest()
            == canonical_digest(obj)
        )


@probe("Q-03 every frame binds the canonicalization version, domain and type")
def _q03():
    for builder in ALL_BUILDERS:
        framed = json.loads(canonical_bytes(builder()).decode("utf-8"))
        assert framed["canonicalization"] == (
            BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION
        )
        assert set(framed) == {"body", "canonicalization", "domain", "type"}


@probe("Q-04 the chain links by independently recomputed predecessor digests")
def _q04():
    event = revocation()
    assert event.prev_event_digest == canonical_digest(event.registration_event)
    assert event.registration_event.prev_event_digest == canonical_digest(
        event.registration_event.admission_decision
    )
    assert (
        event.registration_event.admission_decision.prev_event_digest
        == canonical_digest(
            event.registration_event.admission_decision.submission_record
        )
    )


@probe("Q-05 only the initial submission record derives prev_event_digest as None")
def _q05():
    assert record().prev_event_digest is None
    for builder in (decision, post_admission_rejection, registration, revocation):
        assert builder().prev_event_digest is not None


@probe("Q-06 no caller-supplied upstream digest field exists anywhere")
def _q06():
    """Digest fields name only artifacts this package cannot recompute.

    Two ratified exceptions, and they are exceptions to the *derived-property*
    rule rather than holes in it. D-24 rules that each verified result binds
    "the envelope or artifact digest" and "the anchor-record digest" among
    exactly nine bound facts, and D-25 makes the second of those the anchor
    revision. Both are digests by ratification, named as digests.

    The rule they are excused from exists because a chain payload **chains**: a
    caller-supplied ``prev_event_digest`` would let an artifact attest to a
    predecessor nobody could reproduce. A verified result chains nothing, and it
    is permanently ``authority_verified is False`` — a caller who wanted to forge
    one could already write ``outcome=VERIFIED`` into it, so a settable digest
    field admits no forgery the type did not already admit. Q-24 and Q-46 keep
    the derivations in place; this probe keeps the exception at exactly two
    fields on exactly three classes.
    """

    allowed = {
        "benchmark_identity_digest",
        "benchmark_content_digest",
        "admitted_digest",
        "declared_admitted_digest",
    }
    verified_results = {
        "BenchmarkPublisherVerifiedResult",
        "BenchmarkApprovalVerifiedResult",
        "BenchmarkRevocationVerifiedResult",
    }
    ratified = {"verified_digest", "anchor_record_digest"}
    seen_exceptions = set()
    for builder in ALL_BUILDERS:
        instance = builder()
        name = type(instance).__name__
        for f in dataclasses.fields(instance):
            if not f.name.endswith("_digest"):
                continue
            if name in verified_results and f.name in ratified:
                seen_exceptions.add((name, f.name))
                continue
            assert f.name in allowed, f"{name}.{f.name}"
    # Both directions: the exception is used exactly where it was ratified, so a
    # verified-result type that quietly lost a bound digest fails here too.
    assert seen_exceptions == {
        (cls, field) for cls in verified_results for field in ratified
    }, seen_exceptions


@probe("Q-07 prev_event_digest cannot be supplied, assigned or overwritten")
def _q07():
    event = registration()
    refuses(
        lambda: object.__setattr__(event, "prev_event_digest", "0" * 64),
        AttributeError,
    )
    refuses(
        lambda: BenchmarkRegistrationEventPayload(
            admission_decision=decision(),
            declared_recorded_at=T0,
            prev_event_digest="0" * 64,
        ),
        TypeError,
    )


@probe("Q-08 every payload derives all five no-authority properties as False")
def _q08():
    for builder in ALL_BUILDERS:
        obj = builder()
        for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
            assert getattr(obj, prop) is False, (type(obj).__name__, prop)


@probe("Q-09 no no-authority property survives copy, deepcopy or pickle as True")
def _q09():
    for builder in ALL_BUILDERS:
        obj = builder()
        for clone in (copy.copy(obj), copy.deepcopy(obj),
                      pickle.loads(pickle.dumps(obj))):
            for prop in BENCHMARK_UNVERIFIED_AUTHORITY_PROPERTIES:
                assert getattr(clone, prop) is False


@probe("Q-10 object.__setattr__ cannot reach a no-authority property")
def _q10():
    obj = record()
    refuses(
        lambda: object.__setattr__(obj, "authority_verified", True),
        AttributeError,
    )
    assert obj.authority_verified is False


@probe("Q-11 a subclass can lie about authority but can never produce bytes")
def _q11():
    genuine = record()
    liar = dataclasses.dataclass(frozen=True)(
        type(
            "LiarRecord",
            (type(genuine),),
            {"authority_verified": property(lambda self: True)},
        )
    )
    forged = liar(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    assert forged.authority_verified is True
    refuses(lambda: canonical_bytes(forged), BenchmarkRegistryCanonicalizationError)


@probe("Q-12 the three reserved authority-issued type names are undefined")
def _q12():
    import ugence_benchmark_registry_authority as pkg

    for reserved in BENCHMARK_RESERVED_AUTHORITY_ISSUED_TYPE_NAMES:
        assert not hasattr(pkg, reserved), reserved


@probe("Q-13 a same-named foreign dataclass cannot borrow the genuine bytes")
def _q13():
    genuine = record()
    forged_cls = dataclasses.make_dataclass(
        "BenchmarkSubmissionRecordPayload",
        [(f.name, object, dataclasses.field(default=None))
         for f in dataclasses.fields(genuine)],
        frozen=True,
    )
    forged_cls.__module__ = type(genuine).__module__
    forged = forged_cls(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    assert type(forged).__name__ == type(genuine).__name__
    assert type(forged).__module__ == type(genuine).__module__
    refuses(lambda: canonical_bytes(forged), BenchmarkRegistryCanonicalizationError)


@probe("Q-14 a metaclass forging class equality and hash cannot borrow the bytes")
def _q14():
    genuine = record()
    target = type(genuine)

    class ForgingMeta(type):
        def __eq__(cls, other):
            return True

        def __hash__(cls):
            return hash(target)

    namespace = {
        "__annotations__": {f.name: object for f in dataclasses.fields(genuine)},
        "__module__": target.__module__,
        # Supplied so @dataclass does not synthesize one. On CPython 3.10
        # dataclasses builds a missing __doc__ from str(inspect.signature(cls)),
        # and inspect takes a wrong branch on a class whose metaclass forges
        # __eq__ — raising before the forgery reaches the code under test.
        "__doc__": f"Metaclass-forged stand-in for {target.__name__}.",
    }
    forged_cls = dataclasses.dataclass(frozen=True)(
        ForgingMeta(target.__name__, (), namespace)
    )
    forged = forged_cls(
        **{f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    )
    assert type(forged) == target and type(forged) is not target  # noqa: E721
    refuses(lambda: canonical_bytes(forged), BenchmarkRegistryCanonicalizationError)


@probe("Q-15 a hostile nested object never has its own validator invoked")
def _q15():
    invoked = []
    genuine = record()
    envelope = genuine.publisher_submission_envelope

    def __post_init__(self):
        invoked.append("hostile")

    hostile_cls = dataclasses.make_dataclass(
        "HostileEnvelope",
        [(f.name, object, dataclasses.field(default=None))
         for f in dataclasses.fields(envelope)],
        frozen=True,
        namespace={"__post_init__": __post_init__},
    )
    hostile = hostile_cls(
        **{f.name: getattr(envelope, f.name) for f in dataclasses.fields(envelope)}
    )
    invoked.clear()
    object.__setattr__(genuine, "publisher_submission_envelope", hostile)
    refuses(lambda: canonical_bytes(genuine), BenchmarkRegistryCanonicalizationError)
    assert invoked == [], "the hostile validator was invoked"


@probe("Q-16 a frozen node corrupted via object.__setattr__ is refused")
def _q16():
    event = revocation()
    object.__setattr__(
        event.registration_event.admission_decision.submission_record,
        "declared_registry_authority_identity",
        "",
    )
    refuses(lambda: canonical_bytes(event), BenchmarkRegistryCanonicalizationError)


@probe("Q-17 a corrupted predecessor declared_outcome is caught before any byte")
def _q17():
    event = registration()
    object.__setattr__(
        event.admission_decision,
        "declared_outcome",
        BenchmarkAdmissionOutcome.REJECTED,
    )
    refuses(lambda: canonical_bytes(event), BenchmarkRegistryCanonicalizationError)


@probe("Q-18 registration refuses a REJECTED admission decision")
def _q18():
    refuses(
        lambda: BenchmarkRegistrationEventPayload(
            admission_decision=rejected_decision(), declared_recorded_at=T0
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-19 post-admission rejection refuses a REJECTED admission decision")
def _q19():
    refuses(
        lambda: BenchmarkPostAdmissionRejectionEventPayload(
            admission_decision=rejected_decision(),
            declared_refusal_reason=BenchmarkRegistryRefusalReason.NOT_ADMITTED,
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-20 a post-admission rejection event is unnestable by every later payload")
def _q20():
    rejection = post_admission_rejection()
    for builder in ALL_BUILDERS:
        obj = builder()
        for f in dataclasses.fields(obj):
            assert type(getattr(obj, f.name)) is not type(rejection)
    refuses(
        lambda: BenchmarkRegistrationEventPayload(
            admission_decision=rejection, declared_recorded_at=T0
        ),
        BenchmarkRegistryContractError,
    )


@probe("Q-21 no alternative shortened chain is constructible")
def _q21():
    for wrong in (decision(), record(), post_admission_rejection()):
        refuses(
            lambda w=wrong: BenchmarkRevocationEventPayload(
                registration_event=w,
                revocation_envelope=revocation_envelope(),
                declared_recorded_at=T0,
            ),
            BenchmarkRegistryContractError,
        )


@probe("Q-22 admission refuses mismatched publisher submissions across its paths")
def _q22():
    refuses(
        lambda: BenchmarkAdmissionDecisionPayload(
            submission_record=record(),
            approval_envelope=approval(
                publisher_submission_envelope=publisher(
                    publisher_key_id="publisher-key-9"
                )
            ),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-23 a publisher cannot approve its own artifact")
def _q23():
    refuses(
        lambda: approval(approval_authority_identity="publisher-alpha"),
        BenchmarkRegistryContractError,
    )


@probe("Q-24 the registry cannot be its own publisher")
def _q24():
    refuses(
        lambda: record(declared_registry_authority_identity="publisher-alpha"),
        BenchmarkRegistryContractError,
    )


@probe("Q-25 the registry cannot be the approving authority")
def _q25():
    refuses(
        lambda: BenchmarkAdmissionDecisionPayload(
            submission_record=record(),
            approval_envelope=approval(
                approval_authority_identity="registry-authority-gamma"
            ),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryContractError,
    )


@probe("Q-26 a revoker cannot impersonate the registry authority")
def _q26():
    refuses(
        lambda: BenchmarkRevocationEventPayload(
            registration_event=registration(),
            revocation_envelope=revocation_envelope(
                revoker_identity="registry-authority-gamma"
            ),
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryContractError,
    )


@probe("Q-27 a revocation of one benchmark cannot be attached to another")
def _q27():
    refuses(
        lambda: BenchmarkRevocationEventPayload(
            registration_event=registration(),
            revocation_envelope=revocation_envelope(
                coordinate=coordinate(benchmark_id="other")
            ),
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryLifecycleError,
    )
    refuses(
        lambda: BenchmarkRevocationEventPayload(
            registration_event=registration(),
            revocation_envelope=revocation_envelope(admitted_digest=OTHER_DIGEST),
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-28 registry-authority identity has one source of truth in the chain")
def _q28():
    """One declaration inside the administrative chain; derived everywhere after.

    The two read payloads legitimately declare it: they are standalone answers
    with no nested chain to derive it from, and they say so — each carries the
    ``declared_`` prefix and the permanent ``authority_verified is False``. What
    the rule forbids is a *downstream chain payload* accepting a second
    spelling, because there the value is already fixed by the nested predecessor.
    """

    chain = (record, decision, post_admission_rejection, registration, revocation)
    declarations = [
        type(builder()).__name__
        for builder in chain
        for f in dataclasses.fields(builder())
        if f.name == "declared_registry_authority_identity"
    ]
    assert declarations == ["BenchmarkSubmissionRecordPayload"], declarations
    for builder in (decision, post_admission_rejection, registration, revocation):
        obj = builder()
        assert isinstance(
            type(obj).registry_authority_identity, property
        ), type(obj).__name__
        assert obj.registry_authority_identity == "registry-authority-gamma"


@probe("Q-29 publisher identity is declared on exactly one contract")
def _q29():
    declarations = [
        type(builder()).__name__
        for builder in ALL_BUILDERS
        for f in dataclasses.fields(builder())
        if f.name == "publisher_identity"
    ]
    assert declarations == ["BenchmarkPublisherSubmissionEnvelope"], declarations


@probe("Q-30 every substitution in the chain moves the final digest")
def _q30():
    baseline = canonical_digest(revocation())
    variants = [
        canonical_digest(
            revocation(
                registration_event=registration(
                    admission_decision=decision(
                        submission_record=record(
                            publisher_submission_envelope=publisher(
                                publisher_identity="publisher-omega"
                            )
                        ),
                        approval_envelope=approval(
                            publisher_submission_envelope=publisher(
                                publisher_identity="publisher-omega"
                            )
                        ),
                    )
                )
            )
        ),
        canonical_digest(
            revocation(
                revocation_envelope=revocation_envelope(
                    revoker_identity="revoker-omega"
                )
            )
        ),
        canonical_digest(
            revocation(revocation_envelope=revocation_envelope(effective_at=T2))
        ),
        canonical_digest(revocation(declared_recorded_at=T2)),
    ]
    assert len(set(variants) | {baseline}) == len(variants) + 1


@probe("Q-31 effective_at and declared_recorded_at move the digest independently")
def _q31():
    baseline = canonical_digest(revocation())
    a = canonical_digest(
        revocation(revocation_envelope=revocation_envelope(effective_at=T2))
    )
    b = canonical_digest(revocation(declared_recorded_at=T2))
    assert len({baseline, a, b}) == 3


@probe("Q-32 no floating token is constructible on any locator")
def _q32():
    for token in ("latest", "LATEST", "current", "active", "stable", "*", "-", "?"):
        refuses(
            lambda t=token: coordinate(benchmark_version=t), BenchmarkContractError
        )
        refuses(lambda t=token: coordinate(benchmark_id=t), BenchmarkContractError)


@probe("Q-33 no range, wildcard, partial version or build metadata is constructible")
def _q33():
    for version in (">=1.2.3", "~1.2.3", "1.2", "1.2.x", "1.2.3+build", "1.02.0"):
        refuses(
            lambda v=version: coordinate(benchmark_version=v),
            BenchmarkContractError,
        )


@probe("Q-34 the trusted resolution request has no as_of at all")
def _q34():
    request = BenchmarkExactResolutionRequest(coordinate=coordinate())
    assert not hasattr(request, "as_of")
    refuses(
        lambda: BenchmarkExactResolutionRequest(
            coordinate=coordinate(), as_of=T1
        ),
        TypeError,
    )


@probe("Q-35 the two read payloads cannot substitute for one another")
def _q35():
    resolution = BenchmarkResolutionRecordPayload(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity="registry-authority-gamma",
    )
    historical = BenchmarkHistoricalRecordPayload(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity="registry-authority-gamma",
        as_of=T1,
    )
    refuses(
        lambda: require_exact_resolution_record_payload(historical),
        BenchmarkRegistryContractError,
    )
    refuses(
        lambda: require_exact_historical_record_payload(resolution),
        BenchmarkRegistryContractError,
    )
    assert historical.is_historical_disclosure is True
    assert resolution.is_historical_disclosure is False
    assert canonical_digest(resolution) != canonical_digest(historical)


@probe("Q-36 every supersession path fails closed with the typed refusal")
def _q36():
    import ugence_benchmark_registry_authority as pkg

    assert BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION.value == (
        "UNSUPPORTED_SUPERSESSION"
    )
    for symbol in pkg.__all__:
        assert "successor" not in symbol.lower()
    for builder in ALL_BUILDERS:
        obj = builder()
        assert not hasattr(obj, "supersession")
        assert not hasattr(obj, "superseded_by")
    assert "SUPERSEDED" not in {s.name for s in BenchmarkRegistrationState}


@probe("Q-37 the closed relation admits exactly five arrows and no reverse")
def _q37():
    admitted = [
        (a, b)
        for a in BenchmarkRegistrationState
        for b in BenchmarkRegistrationState
        if is_valid_registration_transition(a, b)
    ]
    assert len(admitted) == 5
    for a, b in admitted:
        assert not is_valid_registration_transition(b, a)
        assert a is not b
    refuses(
        lambda: require_valid_registration_transition(
            BenchmarkRegistrationState.REVOKED,
            BenchmarkRegistrationState.REGISTERED,
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-38 terminal states answer with an empty set rather than raising")
def _q38():
    for state in (
        BenchmarkRegistrationState.REVOKED,
        BenchmarkRegistrationState.REJECTED,
    ):
        assert BENCHMARK_REGISTRATION_TRANSITIONS[state] == frozenset()


@probe("Q-39 each transition accepts exactly one bound payload type")
def _q39():
    assert len(BENCHMARK_TRANSITION_PAYLOAD_BINDING) == 6
    require_bound_payload_for_transition(
        None, BenchmarkRegistrationState.SUBMITTED, record()
    )
    refuses(
        lambda: require_bound_payload_for_transition(
            BenchmarkRegistrationState.ADMITTED,
            BenchmarkRegistrationState.REGISTERED,
            revocation(),
        ),
        BenchmarkRegistryLifecycleError,
    )
    refuses(
        lambda: require_bound_payload_for_transition(
            BenchmarkRegistrationState.SUBMITTED,
            BenchmarkRegistrationState.ADMITTED,
            rejected_decision(),
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-40 no banned state name exists in the vocabulary or the surface")
def _q40():
    import ugence_benchmark_registry_authority as pkg

    for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
        assert banned not in {s.name for s in BenchmarkRegistrationState}
        for symbol in pkg.__all__:
            assert banned not in symbol.upper(), symbol


@probe("Q-41 the two refusal vocabularies are disjoint with no alias either way")
def _q41():
    br1 = {r.value for r in BenchmarkRefusalReason}
    br2 = {r.value for r in BenchmarkRegistryRefusalReason}
    assert not (br1 & br2)
    for member in BenchmarkRefusalReason:
        refuses(lambda m=member: fault_class_for(m), BenchmarkRegistryContractError)


@probe("Q-42 the composite preserves BR-1 declaration order as its prefix")
def _q42():
    prefix = BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[: len(BenchmarkRefusalReason)]
    assert prefix == tuple(BenchmarkRefusalReason)
    assert len(BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS) == 41


@probe("Q-43 a BR-1 lifecycle state can never establish a BR-2 registration state")
def _q43():
    refuses(
        lambda: BenchmarkResolutionRecordPayload(
            coordinate=coordinate(),
            declared_registration_state=BenchmarkLifecycleState.REGISTERED,
            declared_admitted_digest=IDENTITY_DIGEST,
            declared_registry_authority_identity="registry-authority-gamma",
        ),
        BenchmarkRegistryContractError,
    )
    assert (
        BenchmarkLifecycleState.REGISTERED
        is not BenchmarkRegistrationState.REGISTERED
    )


@probe("Q-44 a BR-1 APPROVED artifact never substitutes for an approval envelope")
def _q44():
    refuses(
        lambda: BenchmarkAdmissionDecisionPayload(
            submission_record=record(),
            approval_envelope=BenchmarkLifecycleState.APPROVED,
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryContractError,
    )
    assert approval().approval_authenticity_established is False


@probe("Q-45 no malformed signature encoding is accepted by any envelope")
def _q45():
    for builder in (publisher, approval, revocation_envelope):
        for bad in ("", "00" * 63, "AB" * 64, "zz" * 64, "0x" + "0" * 126):
            refuses(
                lambda b=builder, v=bad: b(detached_signature=v),
                BenchmarkRegistryContractError,
            )


@probe("Q-46 an unconstrained algorithm string is unrepresentable")
def _q46():
    for builder in (publisher, approval, revocation_envelope):
        for algorithm in ("none", "NONE", "HS256", "ED25519_SHA512_V1"):
            refuses(
                lambda b=builder, a=algorithm: b(signature_profile=a),
                BenchmarkRegistryContractError,
            )


@probe("Q-47 each envelope admits only its own signing frame")
def _q47():
    frames = (
        BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
        BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
        BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    )
    assert len(set(frames)) == 3
    for builder, own in zip((publisher, approval, revocation_envelope), frames):
        for other in frames:
            if other == own:
                continue
            refuses(
                lambda b=builder, o=other: b(signing_frame_domain=o),
                BenchmarkRegistryContractError,
            )


@probe("Q-48 a validated signature encoding still establishes nothing")
def _q48():
    for builder in (publisher, approval, revocation_envelope):
        envelope = builder()
        assert len(envelope.detached_signature) == 128
        assert envelope.signature_verified is False
        assert envelope.admission_established is False
        assert envelope.publisher_authenticity_established is False


@probe("Q-49 a BR-1 contract is refused as a BR-2 canonicalization root")
def _q49():
    refuses(
        lambda: canonical_bytes(coordinate()),
        BenchmarkRegistryCanonicalizationError,
    )
    refuses(
        lambda: canonical_bytes(BenchmarkScope.platform_wide()),
        BenchmarkRegistryCanonicalizationError,
    )


@probe("Q-50 float, bytes and mappings are all refused by the encoder")
def _q50():
    for value in (1.5, b"\x01" * 8, {"a": 1}):
        obj = record()
        object.__setattr__(obj, "declared_registry_authority_identity", value)
        refuses(
            lambda o=obj: canonical_bytes(o),
            BenchmarkRegistryCanonicalizationError,
        )


@probe("Q-51 a naive datetime is refused at construction and at the encoder")
def _q51():
    refuses(
        lambda: record(declared_recorded_at=datetime(2026, 3, 1)),
        BenchmarkRegistryContractError,
    )
    obj = record()
    object.__setattr__(obj, "declared_recorded_at", datetime(2026, 3, 1))
    refuses(
        lambda: canonical_bytes(obj), BenchmarkRegistryCanonicalizationError
    )


@probe("Q-52 a non-NFC string is refused, never normalized")
def _q52():
    refuses(
        lambda: record(declared_registry_authority_identity="éx"),
        BenchmarkRegistryContractError,
    )


@probe("Q-53 two spellings of one instant produce one byte sequence")
def _q53():
    shifted = T0.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert canonical_bytes(record(declared_recorded_at=shifted)) == canonical_bytes(
        record()
    )


@probe("Q-54 the consistency descriptor disclaims five guarantees and has no flag")
def _q54():
    descriptor = BENCHMARK_REGISTRY_DECLARED_CONSISTENCY
    assert len(BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES) == 5
    for name in BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES:
        assert getattr(descriptor, name) is (
            BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED
        )
        refuses(
            lambda n=name: object.__setattr__(descriptor, n, "CLAIMED"),
            AttributeError,
        )
    for f in dataclasses.fields(BenchmarkRegistryStoreConsistencyDescriptor):
        assert f.type is not bool


@probe("Q-55 the confusable contract claims no algorithm and permits no rewrite")
def _q55():
    contract = BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT
    assert contract["algorithm_identifier"] is None
    assert contract["unicode_version"] is None
    assert contract["rewrite_permitted"] is False
    assert contract["completeness_claim"].startswith("NONE")
    assert len(contract["compared_elements"]) == 9


@probe("Q-56 no concrete exported class satisfies any inert port")
def _q56():
    import inspect

    import ugence_benchmark_registry_authority as pkg
    from ugence_benchmark_registry_authority.api import (
        BenchmarkApprovalVerifierPort,
        BenchmarkClockPort,
        BenchmarkPublisherTrustDirectoryPort,
        BenchmarkRegistryStorePort,
    )

    ports = (
        BenchmarkRegistryStorePort,
        BenchmarkPublisherTrustDirectoryPort,
        BenchmarkApprovalVerifierPort,
        BenchmarkClockPort,
    )
    concrete = [
        getattr(pkg, name)
        for name in pkg.__all__
        if inspect.isclass(getattr(pkg, name))
        and not getattr(getattr(pkg, name), "_is_protocol", False)
    ]
    for port in ports:
        refuses(lambda p=port: p(), TypeError)
        required = {
            n for n in dir(port)
            if not n.startswith("_") and callable(getattr(port, n, None))
        }
        for cls in concrete:
            assert not required <= {n for n in dir(cls) if not n.startswith("_")}


@probe("Q-57 nothing in the package reads a clock")
def _q57():
    import ugence_benchmark_registry_authority as pkg

    for symbol in pkg.__all__:
        assert symbol != "now"
        assert not symbol.startswith("utc")


@probe("Q-58 no tenant is inferred and cross-tenant reads share one refusal code")
def _q58():
    refuses(lambda: BenchmarkScope.for_tenant(""), BenchmarkContractError)
    assert BenchmarkRegistryRefusalReason.NOT_FOUND.value == "NOT_FOUND"
    names = {r.name for r in BenchmarkRegistryRefusalReason}
    for leaky in ("NOT_PERMITTED", "FORBIDDEN", "DENIED"):
        assert leaky not in names


@probe("Q-59 an admission with a refusal reason, or a rejection without one, is refused")
def _q59():
    refuses(
        lambda: BenchmarkAdmissionDecisionPayload(
            submission_record=record(),
            approval_envelope=approval(),
            declared_outcome=BenchmarkAdmissionOutcome.REJECTED,
            declared_recorded_at=T0,
        ),
        BenchmarkRegistryLifecycleError,
    )
    refuses(
        lambda: BenchmarkAdmissionDecisionPayload(
            submission_record=record(),
            approval_envelope=approval(),
            declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
            declared_recorded_at=T0,
            declared_refusal_reason=(
                BenchmarkRegistryRefusalReason.PUBLISHER_UNTRUSTED
            ),
        ),
        BenchmarkRegistryLifecycleError,
    )


@probe("Q-60 planning is total: every state pair yields a plan or a refusal")
def _q60():
    for a in BenchmarkRegistrationState:
        for b in BenchmarkRegistrationState:
            outcome = plan_transition(snapshot_assertion(asserted_current_state=a), b)
            assert isinstance(
                outcome, (BenchmarkTransitionPlan, BenchmarkTransitionRefusal)
            ), (a, b)
            if b not in BENCHMARK_REGISTRATION_TRANSITIONS[a]:
                assert isinstance(outcome, BenchmarkTransitionRefusal), (a, b)


@probe("Q-61 idempotence is decided on canonical bytes, recomputed from records")
def _q61():
    assert is_byte_identical_resubmission(record(), record())
    assert not is_byte_identical_resubmission(
        record(), record(declared_registry_authority_identity="someone-else")
    )
    # A caller may not substitute bytes or a digest for either record.
    for impostor in (canonical_bytes(record()), canonical_digest(record()), None):
        refuses(
            lambda i=impostor: is_byte_identical_resubmission(record(), i),
            BenchmarkRegistryContractError,
        )


def _is_declared_port(value) -> bool:
    """A declared ``typing.Protocol`` port, decided structurally.

    ``_is_protocol`` is set by ``typing.Protocol`` itself on the class object.
    A concrete class cannot acquire it by naming itself ``...Port``.
    """

    return bool(getattr(value, "_is_protocol", False))


@probe("Q-62 no exported callable or port method accepts a plan, by resolved identity")
def _q62():
    """Resolved, not matched — and scoped to the claim BR-2B actually makes.

    An earlier version of this probe asserted that *no callable anywhere under
    src/* consumes a plan. That claim was withdrawn by owner ruling (ADR §35
    D-20): Python permits closures, containers, dynamic attributes, exec and
    runtime rebinding, so no walk can enumerate every callable, and this probe's
    own ownership test — a function's ``__module__`` — is writable by whoever
    plants the function. It was asserting something it could not decide.

    What it checks now is decidable and is the property that holds: no callable
    a caller can reach, and no port method BR-2D would be obliged to implement,
    accepts a transition plan. Hints are resolved through get_type_hints, every
    Union and generic is walked to its leaves, and membership is decided by
    ``is`` — so an alias, an Optional or a container-nested plan is visible.

    A private helper taking a plan is *not* covered, deliberately. It is
    governed by review, and it is inert: there is no store, clock, authority
    result or effectful operation in this package for it to spend a plan on.
    Q-24, Q-25 and Q-46 are the probes that keep that true.
    """

    import inspect
    import typing

    import ugence_benchmark_registry_authority as pkg

    plan = BenchmarkTransitionPlan

    def leaves(annotation):
        found, pending, seen = set(), [annotation], []
        while pending:
            current = pending.pop()
            if any(current is s for s in seen):
                continue
            seen.append(current)
            if isinstance(current, type):
                found.add(current)
            origin = typing.get_origin(current)
            if isinstance(origin, type):
                found.add(origin)
            pending.extend(typing.get_args(current))
        return found

    # Both curated surfaces, unioned. A separate gate pins them equal, but this
    # harness must not depend on that gate holding: walking only the root
    # re-export would miss a callable added to ``api.__all__`` alone, and
    # walking only ``api`` would miss the reverse. Neither may host a plan
    # consumer, so both are walked here.
    surface = {}
    for module in (pkg, pkg.api):
        for symbol in module.__all__:
            value = getattr(module, symbol)
            if inspect.isfunction(value):
                surface[symbol] = value
            elif inspect.isclass(value) and _is_declared_port(value):
                for attribute, member in vars(value).items():
                    if inspect.isfunction(member) and not attribute.startswith("_"):
                        surface[f"{symbol}.{attribute}"] = member

    offenders, unannotated = [], []
    for label, func in surface.items():
        try:
            hints = typing.get_type_hints(func)
        except Exception:
            unannotated.append(label)
            continue
        for name in inspect.signature(func).parameters:
            if name in ("self", "cls"):
                continue
            if name not in hints:
                unannotated.append(f"{label}({name})")
            elif plan in leaves(hints[name]):
                offenders.append(f"{label}({name})")

    # Offenders first. The size assertion below exists so a *shrunken* surface
    # cannot make this probe vacuous, but it must never be what reports a plan
    # consumer: a plant that replaced an existing callable would leave the size
    # unchanged, and a size failure says nothing about what was found.
    assert offenders == [], offenders
    assert unannotated == [], unannotated
    # Twenty-three, not twenty-two: D-26 adds ``verify_revocation`` to the
    # approval-verifier port. The count is a floor against a vacuous probe, not
    # a claim about behaviour, and it moves whenever a seam is declared.
    assert len(surface) == 23, sorted(surface)

    # The check must be able to fail. Plant the shapes that walked past the
    # substring rule and require the leaf-walker to see each one. The annotation
    # object is attached directly rather than written as a source annotation,
    # because get_type_hints resolves a PEP 563 string against the function's
    # globals and would never see a local name.
    aliased = plan
    optional_alias = typing.Optional[aliased]
    nested = typing.Dict[str, typing.List[aliased]]

    def _commit(candidate):
        return None

    _commit.__annotations__ = {"candidate": optional_alias}

    assert plan in leaves(aliased), "a bare alias is invisible"
    assert plan in leaves(optional_alias), "an Optional alias is invisible"
    assert plan in leaves(nested), "a nested alias is invisible"
    assert plan in leaves(_commit.__annotations__["candidate"])
    assert "BenchmarkTransitionPlan" not in "optional_alias"


@probe("Q-64 no planner returns a lifecycle payload, through a resolved Union")
def _q64():
    import typing

    forbidden = {
        BenchmarkSubmissionRecordPayload,
        BenchmarkAdmissionDecisionPayload,
        BenchmarkPostAdmissionRejectionEventPayload,
        BenchmarkRegistrationEventPayload,
        BenchmarkRevocationEventPayload,
        BenchmarkConflictRecordPayload,
    }
    for func in (plan_transition, plan_submission_outcome):
        returned = set(typing.get_args(typing.get_type_hints(func)["return"]))
        assert returned == {
            BenchmarkTransitionPlan,
            BenchmarkTransitionRefusal,
        }, (func.__name__, returned)
        assert not (returned & forbidden), func.__name__

    # And the alias itself is exactly two members, so widening it is visible.
    members = set(typing.get_args(BenchmarkPlanningOutcome))
    assert members == {BenchmarkTransitionPlan, BenchmarkTransitionRefusal}, members


@probe("Q-63 a self-inconsistent snapshot fails closed rather than being repaired")
def _q63():
    stale = plan_submission_outcome(snapshot_assertion(), record())
    assert isinstance(stale, BenchmarkTransitionRefusal)
    assert stale.declared_refusal_reason is (
        BenchmarkRegistryRefusalReason.STALE_REGISTRY_SNAPSHOT
    )


# --------------------------------------------------------------------------- #
# BR-2C trust and verification contracts (D-24 – D-29).
#
# Reconstructed through the curated public API alone, with this harness's own
# literals. Every probe here asserts a refusal or an absence: no verifier ships,
# and none has been audited (D-32).
# --------------------------------------------------------------------------- #
@probe("Q-65 the three verified-result types are distinct and role-pinned")
def _q65():
    types = {type(publisher_verified()), type(approval_verified()),
             type(revocation_verified())}
    assert len(types) == 3
    for build, pinned in (
        (publisher_verified, BenchmarkTrustRole.PUBLISHER),
        (approval_verified, BenchmarkTrustRole.APPROVER),
        (revocation_verified, BenchmarkTrustRole.REVOKER),
    ):
        assert build().signer_role is pinned
        for role in BenchmarkTrustRole:
            if role is not pinned:
                refuses(
                    lambda b=build, r=role: b(signer_role=r),
                    BenchmarkRegistryContractError,
                )
        # A bare string spelling the member's value is not the member.
        refuses(
            lambda b=build, v=pinned.value: b(signer_role=v),
            BenchmarkRegistryContractError,
        )


@probe("Q-66 a verified result establishes nothing, including when it says VERIFIED")
def _q66():
    for build in (publisher_verified, approval_verified, revocation_verified):
        result = build()
        assert result.outcome is BenchmarkVerificationOutcome.VERIFIED
        for prop in (
            "authority_verified",
            "publisher_authenticity_established",
            "approval_authenticity_established",
            "registry_admission_established",
            "trusted_resolution_established",
        ):
            assert getattr(result, prop) is False, prop
            refuses(
                lambda r=result, p=prop: object.__setattr__(r, p, True),
                AttributeError,
            )


@probe("Q-67 the outcome/reason biconditional holds in both directions")
def _q67():
    for build in (publisher_verified, approval_verified, revocation_verified):
        refuses(
            lambda b=build: b(
                outcome=BenchmarkVerificationOutcome.VERIFIED,
                refusal_reason=BenchmarkRegistryRefusalReason.SIGNATURE_INVALID,
            ),
            BenchmarkRegistryContractError,
        )
        refuses(
            lambda b=build: b(
                outcome=BenchmarkVerificationOutcome.REFUSED,
                refusal_reason=None,
            ),
            BenchmarkRegistryContractError,
        )
        # A VERIFIED result cannot omit the revision it verified against.
        refuses(
            lambda b=build: b(anchor_record_digest=None),
            BenchmarkRegistryContractError,
        )


@probe("Q-68 the anchor revision is the record digest and no counter exists")
def _q68():
    record = anchor()
    assert record.anchor_record_digest == canonical_digest(record)
    names = {f.name for f in dataclasses.fields(record)}
    assert "anchor_record_digest" not in names
    for banned in ("revision", "version", "generation", "sequence", "serial"):
        assert not any(banned in n for n in names), names
    refuses(
        lambda: object.__setattr__(record, "anchor_record_digest", "0" * 64),
        AttributeError,
    )
    # Any bound field moves the revision.
    base = record.anchor_record_digest
    for override in (
        {"identity": "publisher-omega"},
        {"key_id": "publisher-key-2"},
        {"public_key_material": APP_KEY},
        {"role": BenchmarkTrustRole.APPROVER},
    ):
        assert anchor(**override).anchor_record_digest != base


@probe("Q-69 the anchor's revocation facts and status can never disagree")
def _q69():
    refuses(
        lambda: anchor(status=BenchmarkTrustAnchorStatus.REVOKED, revoked_at=None),
        BenchmarkRegistryContractError,
    )
    for status in (
        BenchmarkTrustAnchorStatus.ENABLED,
        BenchmarkTrustAnchorStatus.DISABLED,
    ):
        refuses(
            lambda s=status: anchor(status=s, revoked_at=ANCHOR_REVOKED_AT),
            BenchmarkRegistryContractError,
        )
        refuses(
            lambda s=status: anchor(status=s, revocation_reason="anything"),
            BenchmarkRegistryContractError,
        )
    # An interval containing no instant is refused, never reordered.
    refuses(
        lambda: anchor(validity_from=T2, validity_to=ANCHOR_FROM),
        BenchmarkRegistryContractError,
    )


@probe("Q-70 key material is an encoding that is checked and never decoded")
def _q70():
    record = anchor()
    assert len(record.public_key_material) == 64
    for bad in ("A" * 64, "d4" * 31, "", "0x" + "d4" * 32, "zz" * 32, " " + "d4" * 32):
        refuses(
            lambda b=bad: anchor(public_key_material=b),
            BenchmarkRegistryContractError,
        )
    # No cryptographic library was imported to check any of that.
    for module in ("cryptography", "nacl", "ed25519", "Crypto", "OpenSSL"):
        assert module not in sys.modules, module


@probe("Q-71 the seven trust refusals are appended, role-neutral and classified")
def _q71():
    members = list(BenchmarkRegistryRefusalReason)
    assert len(members) == 24
    tail = [m.name for m in members[-7:]]
    assert tail == [
        "TRUST_ANCHOR_NOT_FOUND",
        "TRUST_ANCHOR_REVOKED",
        "TRUST_ANCHOR_DISABLED",
        "TRUST_ANCHOR_NOT_YET_VALID",
        "TRUST_ANCHOR_EXPIRED",
        "TRUST_DIRECTORY_UNAVAILABLE",
        "STALE_TRUST_SNAPSHOT",
    ], tail
    for name in tail:
        member = BenchmarkRegistryRefusalReason[name]
        assert (
            fault_class_for(member)
            is BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        )
        for role in BenchmarkTrustRole:
            assert role.value not in name, name
    # BR-1's frozen prefix is untouched and still occupies indices 0..16.
    assert BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS[17:][:7] != tuple(tail)


@probe("Q-72 the verification vocabulary is not the admission vocabulary")
def _q72():
    values = {m.value for m in BenchmarkVerificationOutcome}
    assert values == {"VERIFIED", "REFUSED"}
    assert not (values & {m.value for m in BenchmarkAdmissionOutcome})
    # And no banned floating lifecycle word entered through the anchor status.
    for member in BenchmarkTrustAnchorStatus:
        for banned in BENCHMARK_BANNED_REGISTRATION_STATE_NAMES:
            assert banned not in member.name.upper(), member.name


@probe("Q-73 nothing in the package satisfies the reshaped ports")
def _q73():
    import ugence_benchmark_registry_authority as pkg

    for port_name in (
        "BenchmarkApprovalVerifierPort",
        "BenchmarkPublisherTrustDirectoryPort",
    ):
        port = getattr(pkg, port_name)
        assert getattr(port, "_is_protocol", False), port_name
        refuses(lambda p=port: p(), TypeError)
    seams = {
        name
        for name in vars(pkg.BenchmarkApprovalVerifierPort)
        if not name.startswith("_")
    }
    assert seams == {
        "verify_publisher_submission",
        "verify_approval",
        "verify_revocation",
    }, seams
    assert "is_entitled" not in vars(pkg.BenchmarkPublisherTrustDirectoryPort)
    assert "resolve_anchor" in vars(pkg.BenchmarkPublisherTrustDirectoryPort)


def main() -> int:
    for name, fn in _PROBES:
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001 - a probe failure is a result
            _FAILURES.append((name, exc))
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print("=" * 70)
    if _FAILURES:
        print(f"{len(_FAILURES)} of {len(_PROBES)} probes FAILED")
        return 1
    print(f"{len(_PROBES)} probes passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
