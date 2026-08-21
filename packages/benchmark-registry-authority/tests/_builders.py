"""Pinned fixture builders for the BR-2 suite.

Every value here is a **fixed literal**. Nothing reads a clock, an environment
variable, a random source or the filesystem, so the canonical bytes these
fixtures produce are reproducible on any machine, in any order, in any process —
which is what makes the pinned vectors in ``pinned_canonical_vectors.json``
meaningful rather than decorative.

The independent probe harness (``adversarial_probes.py``) and the distribution
verifier (``verify_benchmark_registry_authority_distribution.py``) deliberately
**do not import this module**. They re-declare the same constants themselves and
reconstruct the same objects through the curated public API alone, so a bug in a
shared helper cannot make a probe and a test agree with each other while both
disagree with reality.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkCoordinate,
    BenchmarkScope,
)

from ugence_benchmark_registry_authority.api import (
    BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    BENCHMARK_SIGNING_FRAME_VERSION,
    BenchmarkAdmissionDecisionPayload,
    BenchmarkAdmissionOutcome,
    BenchmarkApprovalEnvelope,
    BenchmarkConflictRecordPayload,
    BenchmarkExactResolutionRequest,
    BenchmarkHistoricalInspectionRequest,
    BenchmarkHistoricalRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
    BenchmarkPublisherSubmissionEnvelope,
    BenchmarkRegistrationEventPayload,
    BenchmarkRegistrationState,
    BenchmarkRegistryRefusalReason,
    BenchmarkResolutionRecordPayload,
    BenchmarkRevocationEnvelope,
    BenchmarkRevocationEventPayload,
    BenchmarkSignatureProfile,
    BenchmarkSubmissionRecordPayload,
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BenchmarkTrustAnchorRecord,
    BenchmarkTrustAnchorStatus,
    BenchmarkTrustRole,
    BenchmarkVerificationOutcome,
    PlatformRegistryScopeExpectation,
    TenantRegistryScopeExpectation,
)

# --------------------------------------------------------------------------- #
# Pinned literals. Changing any of these changes the pinned vectors, which is
# exactly the point: the vectors are what prove the encoding did not move.
# --------------------------------------------------------------------------- #
BENCHMARK_ID = "bmk"
BENCHMARK_FAMILY = "fam"
BENCHMARK_VERSION = "1.2.3"
TENANT_ID = "t1"
GEOGRAPHY_VALUE = "eu"

# Hex letters as well as digits, so the pinned vectors exercise the whole
# lowercase alphabet a digest is allowed to use — and so an uppercase
# spelling is a genuinely different string the validators must refuse.
IDENTITY_DIGEST = "a1" * 32
CONTENT_DIGEST = "b2" * 32
OTHER_DIGEST = "c3" * 32

PUBLISHER_IDENTITY = "publisher-alpha"
PUBLISHER_KEY_ID = "publisher-key-1"
APPROVAL_AUTHORITY_IDENTITY = "approval-authority-beta"
APPROVAL_AUTHORITY_KEY_ID = "approval-key-1"
REGISTRY_AUTHORITY_IDENTITY = "registry-authority-gamma"
REVOKER_IDENTITY = "revoker-delta"
REVOKER_KEY_ID = "revocation-key-1"

PUBLISHER_SIGNATURE = "01" * 64
APPROVAL_SIGNATURE = "02" * 64
REVOCATION_SIGNATURE = "03" * 64

APPLICABLE_POLICY_REF = "benchmark-approval-policy/v1"
REVOCATION_REASON = "content-defect-identified"

RECORDED_AT = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
VALIDITY_FROM = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
VALIDITY_TO = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
EFFECTIVE_AT = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)

PROFILE = BenchmarkSignatureProfile.ED25519_SHA512_V1

# BR-2C contract fixtures. Public-key material is 64 lowercase hex characters
# (32 bytes) and, like every other literal here, is a fixed string that is never
# decoded: this package parses no key material and links no cryptographic
# library, so these are encodings that look like keys and are not keys.
PUBLISHER_PUBLIC_KEY = "d4" * 32
APPROVER_PUBLIC_KEY = "e5" * 32
REVOKER_PUBLIC_KEY = "f6" * 32

# The explicit trusted instant D-28 makes an input to verification. Deliberately
# inside [VALIDITY_FROM, VALIDITY_TO) so the pinned anchor fixture is one a
# verifier would find valid — and deliberately a literal, because BR-2C ships no
# clock and the authoritative clock arrives at BR-2D (D-11, unamended).
TRUSTED_INSTANT = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
ANCHOR_REVOKED_AT = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
ANCHOR_REVOCATION_REASON = "key-compromise-reported"


def tenant_scope(tenant_id: str = TENANT_ID) -> BenchmarkScope:
    return BenchmarkScope.for_tenant(tenant_id)


def platform_scope() -> BenchmarkScope:
    return BenchmarkScope.platform_wide()


def coordinate(**overrides) -> BenchmarkCoordinate:
    kwargs = dict(
        benchmark_id=BENCHMARK_ID,
        benchmark_family=BENCHMARK_FAMILY,
        benchmark_version=BENCHMARK_VERSION,
        scope=tenant_scope(),
        geography=BenchmarkApplicabilityCoordinate.applicable(GEOGRAPHY_VALUE),
        domain=BenchmarkApplicabilityCoordinate.not_applicable(),
    )
    kwargs.update(overrides)
    return BenchmarkCoordinate(**kwargs)


def publisher_envelope(**overrides) -> BenchmarkPublisherSubmissionEnvelope:
    kwargs = dict(
        coordinate=coordinate(),
        benchmark_identity_digest=IDENTITY_DIGEST,
        benchmark_content_digest=CONTENT_DIGEST,
        publisher_identity=PUBLISHER_IDENTITY,
        publisher_key_id=PUBLISHER_KEY_ID,
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        detached_signature=PUBLISHER_SIGNATURE,
    )
    kwargs.update(overrides)
    return BenchmarkPublisherSubmissionEnvelope(**kwargs)


def approval_envelope(**overrides) -> BenchmarkApprovalEnvelope:
    kwargs = dict(
        publisher_submission_envelope=publisher_envelope(),
        approval_authority_identity=APPROVAL_AUTHORITY_IDENTITY,
        approval_authority_key_id=APPROVAL_AUTHORITY_KEY_ID,
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
        applicable_policy_ref=APPLICABLE_POLICY_REF,
        validity_from=VALIDITY_FROM,
        validity_to=VALIDITY_TO,
        detached_signature=APPROVAL_SIGNATURE,
    )
    kwargs.update(overrides)
    return BenchmarkApprovalEnvelope(**kwargs)


def revocation_envelope(**overrides) -> BenchmarkRevocationEnvelope:
    kwargs = dict(
        coordinate=coordinate(),
        admitted_digest=IDENTITY_DIGEST,
        revoker_identity=REVOKER_IDENTITY,
        revoker_key_id=REVOKER_KEY_ID,
        signature_profile=PROFILE,
        signing_frame_domain=BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
        signing_frame_version=BENCHMARK_SIGNING_FRAME_VERSION,
        declared_revocation_reason=REVOCATION_REASON,
        effective_at=EFFECTIVE_AT,
        detached_signature=REVOCATION_SIGNATURE,
    )
    kwargs.update(overrides)
    return BenchmarkRevocationEnvelope(**kwargs)


def submission_record(**overrides) -> BenchmarkSubmissionRecordPayload:
    kwargs = dict(
        publisher_submission_envelope=publisher_envelope(),
        declared_registry_authority_identity=REGISTRY_AUTHORITY_IDENTITY,
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkSubmissionRecordPayload(**kwargs)


def admission_decision(**overrides) -> BenchmarkAdmissionDecisionPayload:
    kwargs = dict(
        submission_record=submission_record(),
        approval_envelope=approval_envelope(),
        declared_outcome=BenchmarkAdmissionOutcome.ADMITTED,
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkAdmissionDecisionPayload(**kwargs)


def rejected_admission_decision(**overrides) -> BenchmarkAdmissionDecisionPayload:
    kwargs = dict(
        submission_record=submission_record(),
        approval_envelope=approval_envelope(
            declared_outcome=BenchmarkAdmissionOutcome.REJECTED
        ),
        declared_outcome=BenchmarkAdmissionOutcome.REJECTED,
        declared_recorded_at=RECORDED_AT,
        declared_refusal_reason=BenchmarkRegistryRefusalReason.PUBLISHER_UNTRUSTED,
    )
    kwargs.update(overrides)
    return BenchmarkAdmissionDecisionPayload(**kwargs)


def post_admission_rejection(
    **overrides,
) -> BenchmarkPostAdmissionRejectionEventPayload:
    kwargs = dict(
        admission_decision=admission_decision(),
        declared_refusal_reason=(
            BenchmarkRegistryRefusalReason.APPROVAL_UNVERIFIED
        ),
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkPostAdmissionRejectionEventPayload(**kwargs)


def registration_event(**overrides) -> BenchmarkRegistrationEventPayload:
    kwargs = dict(
        admission_decision=admission_decision(),
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkRegistrationEventPayload(**kwargs)


def revocation_event(**overrides) -> BenchmarkRevocationEventPayload:
    kwargs = dict(
        registration_event=registration_event(),
        revocation_envelope=revocation_envelope(),
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkRevocationEventPayload(**kwargs)


def conflict_record(**overrides) -> BenchmarkConflictRecordPayload:
    kwargs = dict(
        submission_record=submission_record(),
        declared_refusal_reason=(
            BenchmarkRegistryRefusalReason.COORDINATE_SLOT_CONFLICT
        ),
        declared_recorded_at=RECORDED_AT,
    )
    kwargs.update(overrides)
    return BenchmarkConflictRecordPayload(**kwargs)


def resolution_record(**overrides) -> BenchmarkResolutionRecordPayload:
    kwargs = dict(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity=REGISTRY_AUTHORITY_IDENTITY,
    )
    kwargs.update(overrides)
    return BenchmarkResolutionRecordPayload(**kwargs)


def historical_record(**overrides) -> BenchmarkHistoricalRecordPayload:
    kwargs = dict(
        coordinate=coordinate(),
        declared_registration_state=BenchmarkRegistrationState.REGISTERED,
        declared_admitted_digest=IDENTITY_DIGEST,
        declared_registry_authority_identity=REGISTRY_AUTHORITY_IDENTITY,
        as_of=AS_OF,
    )
    kwargs.update(overrides)
    return BenchmarkHistoricalRecordPayload(**kwargs)


def exact_resolution_request(**overrides) -> BenchmarkExactResolutionRequest:
    kwargs = dict(coordinate=coordinate())
    kwargs.update(overrides)
    return BenchmarkExactResolutionRequest(**kwargs)


def historical_inspection_request(
    **overrides,
) -> BenchmarkHistoricalInspectionRequest:
    kwargs = dict(coordinate=coordinate(), as_of=AS_OF)
    kwargs.update(overrides)
    return BenchmarkHistoricalInspectionRequest(**kwargs)


def platform_expectation(**overrides) -> PlatformRegistryScopeExpectation:
    kwargs = dict(scope=platform_scope())
    kwargs.update(overrides)
    return PlatformRegistryScopeExpectation(**kwargs)


def tenant_expectation(**overrides) -> TenantRegistryScopeExpectation:
    kwargs = dict(scope=tenant_scope())
    kwargs.update(overrides)
    return TenantRegistryScopeExpectation(**kwargs)


# --------------------------------------------------------------------------- #
# BR-2C trust and verification contracts (D-24, D-25, D-26).
#
# Fixtures for shapes, not for capability. Constructing a verified result here
# verifies nothing: the objects carry §09's five permanently-False authority
# derivations exactly as every other contract in this package does, and no
# verifier exists to produce one.
# --------------------------------------------------------------------------- #
def trust_anchor_record(**overrides) -> BenchmarkTrustAnchorRecord:
    """An ENABLED publisher anchor. The pinned fixture."""

    kwargs = dict(
        role=BenchmarkTrustRole.PUBLISHER,
        identity=PUBLISHER_IDENTITY,
        key_id=PUBLISHER_KEY_ID,
        signature_profile=PROFILE,
        public_key_material=PUBLISHER_PUBLIC_KEY,
        validity_from=VALIDITY_FROM,
        validity_to=VALIDITY_TO,
        status=BenchmarkTrustAnchorStatus.ENABLED,
        revoked_at=None,
        revocation_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkTrustAnchorRecord(**kwargs)


def revoked_trust_anchor_record(**overrides) -> BenchmarkTrustAnchorRecord:
    """A REVOKED anchor, carrying the revocation facts a REVOKED status requires.

    A second fixture for the same class, like ``rejected_admission_decision``
    and ``unoccupied_assertion``: the revoked branch of the constructor's
    biconditional is unreachable from the ENABLED fixture.
    """

    kwargs = dict(
        status=BenchmarkTrustAnchorStatus.REVOKED,
        revoked_at=ANCHOR_REVOKED_AT,
        revocation_reason=ANCHOR_REVOCATION_REASON,
    )
    kwargs.update(overrides)
    return trust_anchor_record(**kwargs)


def approver_trust_anchor_record(**overrides) -> BenchmarkTrustAnchorRecord:
    """An anchor in the **approver** namespace. D-26 keeps the three separate."""

    kwargs = dict(
        role=BenchmarkTrustRole.APPROVER,
        identity=APPROVAL_AUTHORITY_IDENTITY,
        key_id=APPROVAL_AUTHORITY_KEY_ID,
        public_key_material=APPROVER_PUBLIC_KEY,
    )
    kwargs.update(overrides)
    return trust_anchor_record(**kwargs)


def revoker_trust_anchor_record(**overrides) -> BenchmarkTrustAnchorRecord:
    """An anchor in the **revoker** namespace."""

    kwargs = dict(
        role=BenchmarkTrustRole.REVOKER,
        identity=REVOKER_IDENTITY,
        key_id=REVOKER_KEY_ID,
        public_key_material=REVOKER_PUBLIC_KEY,
    )
    kwargs.update(overrides)
    return trust_anchor_record(**kwargs)


def publisher_verified_result(**overrides) -> BenchmarkPublisherVerifiedResult:
    kwargs = dict(
        verified_digest=IDENTITY_DIGEST,
        signer_role=BenchmarkTrustRole.PUBLISHER,
        signer_identity=PUBLISHER_IDENTITY,
        signer_key_id=PUBLISHER_KEY_ID,
        signature_profile=PROFILE,
        anchor_record_digest=OTHER_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkPublisherVerifiedResult(**kwargs)


def refused_publisher_verified_result(
    **overrides,
) -> BenchmarkPublisherVerifiedResult:
    """A refusal naming an anchor that was never found — so it binds no revision."""

    kwargs = dict(
        anchor_record_digest=None,
        outcome=BenchmarkVerificationOutcome.REFUSED,
        refusal_reason=BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND,
    )
    kwargs.update(overrides)
    return publisher_verified_result(**kwargs)


def approval_verified_result(**overrides) -> BenchmarkApprovalVerifiedResult:
    kwargs = dict(
        verified_digest=CONTENT_DIGEST,
        signer_role=BenchmarkTrustRole.APPROVER,
        signer_identity=APPROVAL_AUTHORITY_IDENTITY,
        signer_key_id=APPROVAL_AUTHORITY_KEY_ID,
        signature_profile=PROFILE,
        anchor_record_digest=OTHER_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkApprovalVerifiedResult(**kwargs)


def revocation_verified_result(**overrides) -> BenchmarkRevocationVerifiedResult:
    kwargs = dict(
        verified_digest=OTHER_DIGEST,
        signer_role=BenchmarkTrustRole.REVOKER,
        signer_identity=REVOKER_IDENTITY,
        signer_key_id=REVOKER_KEY_ID,
        signature_profile=PROFILE,
        anchor_record_digest=IDENTITY_DIGEST,
        evaluated_at=TRUSTED_INSTANT,
        outcome=BenchmarkVerificationOutcome.VERIFIED,
        refusal_reason=None,
    )
    kwargs.update(overrides)
    return BenchmarkRevocationVerifiedResult(**kwargs)


#: Pinned fixtures for the shipped root-canonicalizable artifact classes, in
#: the ratified domain order. **Twenty-two classes** — BR-2A's fifteen, BR-2B's
#: three and BR-2C's four. The builder count is deliberately **not** one-to-one
#: with them: ``rejected_admission_decision`` is a second fixture for
#: ``BenchmarkAdmissionDecisionPayload``, ``unoccupied_assertion`` a second for
#: ``BenchmarkRegistrySnapshotAssertion``, ``refused_publisher_verified_result``
#: a second for ``BenchmarkPublisherVerifiedResult``, and
#: ``revoked_trust_anchor_record``, ``approver_trust_anchor_record`` and
#: ``revoker_trust_anchor_record`` three more for ``BenchmarkTrustAnchorRecord``
#: — so the builders outnumber the classes and the count is not restated as a
#: pair. Every one of the twenty-two appears in
#: ``pinned_canonical_vectors.json``, in the canonical-domain inventory, in the
#: public-contract inventory, and in the source/wheel/sdist parity checks.
def snapshot_assertion(**overrides) -> BenchmarkRegistrySnapshotAssertion:
    kwargs = dict(
        coordinate=coordinate(),
        asserted_current_state=BenchmarkRegistrationState.ADMITTED,
        asserted_registration_record_presence=(
            BenchmarkRegistrationRecordPresence.NO_RECORD_APPENDED
        ),
    )
    kwargs.update(overrides)
    return BenchmarkRegistrySnapshotAssertion(**kwargs)


def unoccupied_assertion(**overrides) -> BenchmarkRegistrySnapshotAssertion:
    """The only assertion from which the initial move is admissible."""

    kwargs = dict(
        coordinate=coordinate(),
        asserted_current_state=None,
        asserted_registration_record_presence=(
            BenchmarkRegistrationRecordPresence.NO_RECORD_APPENDED
        ),
    )
    kwargs.update(overrides)
    return BenchmarkRegistrySnapshotAssertion(**kwargs)


def transition_plan(**overrides) -> BenchmarkTransitionPlan:
    kwargs = dict(
        snapshot=snapshot_assertion(),
        planned_to_state=BenchmarkRegistrationState.REGISTERED,
    )
    kwargs.update(overrides)
    return BenchmarkTransitionPlan(**kwargs)


def transition_refusal(**overrides) -> BenchmarkTransitionRefusal:
    kwargs = dict(
        snapshot=snapshot_assertion(),
        refused_to_state=BenchmarkRegistrationState.REVOKED,
        declared_refusal_reason=(
            BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
        ),
    )
    kwargs.update(overrides)
    return BenchmarkTransitionRefusal(**kwargs)


PINNED_VECTOR_BUILDERS = (
    ("BenchmarkPublisherSubmissionEnvelope", publisher_envelope),
    ("BenchmarkApprovalEnvelope", approval_envelope),
    ("BenchmarkRevocationEnvelope", revocation_envelope),
    ("BenchmarkSubmissionRecordPayload", submission_record),
    ("BenchmarkAdmissionDecisionPayload", admission_decision),
    ("BenchmarkPostAdmissionRejectionEventPayload", post_admission_rejection),
    ("BenchmarkRegistrationEventPayload", registration_event),
    ("BenchmarkRevocationEventPayload", revocation_event),
    ("BenchmarkConflictRecordPayload", conflict_record),
    ("BenchmarkResolutionRecordPayload", resolution_record),
    ("BenchmarkHistoricalRecordPayload", historical_record),
    ("BenchmarkExactResolutionRequest", exact_resolution_request),
    ("BenchmarkHistoricalInspectionRequest", historical_inspection_request),
    ("PlatformRegistryScopeExpectation", platform_expectation),
    ("TenantRegistryScopeExpectation", tenant_expectation),
    ("BenchmarkRegistrySnapshotAssertion", snapshot_assertion),
    ("BenchmarkTransitionPlan", transition_plan),
    ("BenchmarkTransitionRefusal", transition_refusal),
    ("BenchmarkTrustAnchorRecord", trust_anchor_record),
    ("BenchmarkPublisherVerifiedResult", publisher_verified_result),
    ("BenchmarkApprovalVerifiedResult", approval_verified_result),
    ("BenchmarkRevocationVerifiedResult", revocation_verified_result),
)
