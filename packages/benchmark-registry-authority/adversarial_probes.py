#!/usr/bin/env python3
"""Independent adversarial probes for the Benchmark Registry Authority (BR-2A).

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
    BenchmarkPlanningOutcome,
    BENCHMARK_REGISTRATION_TRANSITIONS,
    is_byte_identical_resubmission,
    plan_submission_outcome,
    plan_transition,
    BenchmarkRegistrationState,
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryConsistencyClaim,
    BenchmarkRegistryContractError,
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
)


# --------------------------------------------------------------------------- #
# Probes
# --------------------------------------------------------------------------- #
@probe("Q-00 the whole administrative chain constructs and digests")
def _q00():
    event = revocation()
    assert len(canonical_digest(event)) == 64
    assert event.declared_state is BenchmarkRegistrationState.REVOKED


@probe("Q-01 all eighteen shipped artifacts canonicalize into eighteen byte spaces")
def _q01():
    domains = set()
    for builder in ALL_BUILDERS:
        framed = json.loads(canonical_bytes(builder()).decode("utf-8"))
        domains.add(framed["domain"])
    assert len(domains) == 18, len(domains)
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
    allowed = {
        "benchmark_identity_digest",
        "benchmark_content_digest",
        "admitted_digest",
        "declared_admitted_digest",
    }
    for builder in ALL_BUILDERS:
        for f in dataclasses.fields(builder()):
            if f.name.endswith("_digest"):
                assert f.name in allowed, f.name


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
    assert len(BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS) == 34


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


@probe("Q-62 no callable in contracts/ accepts a plan, by resolved type identity")
def _q62():
    """Resolved, not matched. This harness derives it independently.

    A substring rule reading the annotation text is walked past by an alias, by
    a Union member, or by omitting the annotation entirely — which is how the
    suite's version of this check came to pass a plan-consuming callable. Here
    the hints are resolved through typing.get_type_hints, every Union and
    generic is walked to its leaves, and membership is decided by ``is``.
    """

    import importlib
    import inspect
    import pathlib as _pl
    import typing

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

    root = _pl.Path(
        importlib.import_module(
            "ugence_benchmark_registry_authority.contracts"
        ).__file__
    ).parent
    ns = "ugence_benchmark_registry_authority"
    offenders, unannotated, checked = [], [], 0

    for path in sorted(root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = importlib.import_module(f"{ns}.contracts.{path.stem}")
        functions = []
        for value in vars(module).values():
            if inspect.isfunction(value):
                functions.append(value)
            elif inspect.isclass(value) and str(
                getattr(value, "__module__", "")
            ).startswith(ns):
                for member in vars(value).values():
                    if inspect.isfunction(member):
                        functions.append(member)
                    elif isinstance(member, property) and member.fget:
                        functions.append(member.fget)
        for func in functions:
            code = getattr(func, "__code__", None)
            if code is None or not str(code.co_filename).startswith(str(root)):
                continue  # imported or compiler-generated, not written here
            checked += 1
            try:
                hints = typing.get_type_hints(func)
            except Exception:
                unannotated.append(func.__qualname__)
                continue
            for name in inspect.signature(func).parameters:
                if name in ("self", "cls"):
                    continue
                if name not in hints:
                    unannotated.append(f"{func.__qualname__}({name})")
                elif plan in leaves(hints[name]):
                    offenders.append(f"{func.__qualname__}({name})")

    assert checked > 50, checked
    assert offenders == [], offenders
    assert unannotated == [], unannotated

    # The check must be able to fail. Plant the three shapes that walked past
    # the substring rule and require the leaf-walker to see each one. The
    # annotation object is attached directly rather than written as a local
    # alias in a source annotation, because get_type_hints resolves a PEP 563
    # string against the function's globals and would never see a local name.
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
