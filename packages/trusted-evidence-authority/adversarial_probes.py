#!/usr/bin/env python3
"""Independent adversarial probes for the Ugence Trusted Evidence Authority.

**Independent** in the load-bearing sense: this file imports **only** the
curated public API — ``ugence_trusted_evidence_authority.api`` — plus the Python
standard library. It imports no package test module, no ``_builders`` helper, no
``conftest``, and no private submodule. It builds every fixture from scratch and
recomputes every expected digest with ``hashlib`` alone.

That matters because a probe that reuses the suite's own helpers can only
re-confirm the suite's own assumptions. If the package's internal validators
were removed wholesale, these probes would still fail.

Runs standalone (``python packages/trusted-evidence-authority/adversarial_probes.py``)
and is also executed inside the isolated wheel install by
``verify_trusted_evidence_authority_distribution.py``. Exit code 0 on success;
non-zero with a report on the first failure.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pickle
import sys
from datetime import datetime, timedelta, timezone

from ugence_trusted_evidence_authority.api import (  # noqa: F401
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
    SIGNED_INPUT_LENGTH_PREFIX_BYTES,
    SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
    TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
    TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    ApplicabilityCoordinate,
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    DeclaredVerificationOutcome,
    EvidenceClaimBinding,
    EvidenceLifecycleState,
    EvidenceObservation,
    EvidenceProvenanceChain,
    EvidenceSchemaRef,
    EvidenceScopeBinding,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
    EvidenceVerificationReceiptPayload,
    EvidenceVerificationRequest,
    TrustedEvidenceCanonicalizationError,
    TrustedEvidenceContractError,
    TrustedEvidenceLifecycleError,
    TrustedEvidenceRefusalReason,
    DenyAllTrustAnchorDirectory,
    Ed25519EvidenceAuthenticityProtocol,
    Ed25519ReceiptSigner,
    EvidenceAdmissionOutcome,
    EvidenceVerificationAuthority,
    EvidenceVerificationDetermination,
    KeyRevocation,
    ProtocolExecutionResult,
    ReceiptIssuer,
    ReceiptSigningInput,
    ReceiptScopeExpectation,
    ReceiptVerificationKind,
    ReceiptVerificationOutcome,
    ScopeBoundVerificationResult,
    SignatureOnlyVerificationResult,
    SignedEvidenceSubmission,
    SignedEvidenceVerificationReceipt,
    SignedReceiptVerifier,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustedEvidenceSigningKey,
    TrustedEvidenceVerificationKey,
    audit_record_for_determination,
    audit_record_for_receipt_verification,
    canonical_bytes,
    canonical_digest,
    decode_public_key,
    derive_receipt_id,
    encode_public_key,
    encode_signature,
    framed_signed_input,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
    signed_evidence_input_bytes,
    signed_receipt_input_bytes,
)

UTC = timezone.utc
R = TrustedEvidenceRefusalReason

_FAILURES: list = []
_RUN = 0


def probe(fn):
    """Register and immediately run a probe, recording rather than raising."""

    global _RUN
    _RUN += 1
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — a probe harness reports, not crashes
        _FAILURES.append(f"{fn.__name__}: {type(exc).__name__}: {exc}")
    return fn


def expect_refusal(callable_, *exc_types):
    """Assert ``callable_`` refuses; a silent acceptance is the failure mode."""

    types = exc_types or (TrustedEvidenceContractError,)
    try:
        result = callable_()
    except types:
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"refused with an unexpected error: {exc!r}") from None
    raise AssertionError(f"expected a refusal, got {result!r}")


# --------------------------------------------------------------------------- #
# Fixtures — built here, from the public API only
# --------------------------------------------------------------------------- #
CONTENT = hashlib.sha256(b"probe-evidence-content").hexdigest()
CONTEXT = hashlib.sha256(b"probe-assessment-context").hexdigest()
BINDING = hashlib.sha256(b"probe-system-binding").hexdigest()
OTHER = hashlib.sha256(b"probe-something-else").hexdigest()

T_OBS = datetime(2026, 4, 1, 9, 30, 0, 125000, tzinfo=UTC)
T_COL = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
T_FROM = datetime(2026, 4, 1, tzinfo=UTC)
T_TO = datetime(2026, 10, 1, tzinfo=UTC)
T_MID = datetime(2026, 7, 1, tzinfo=UTC)


def build_identity(**overrides) -> CanonicalEvidenceIdentity:
    base = dict(
        evidence_id="probe-ev",
        evidence_type="PROBE_EVIDENCE",
        schema=EvidenceSchemaRef(schema_id="probe.schema", schema_version="1"),
        content_digest=CONTENT,
        observation=EvidenceObservation(
            producer_id="probe-producer",
            collected_at=T_COL,
            observed_from=T_OBS,
            observed_to=None,
            issuer_id="",
        ),
        scope=EvidenceScopeBinding(
            tenant_id="probe-tenant",
            assessment_context_ref="probe-ctx",
            assessment_context_digest=CONTEXT,
            subject_ref="probe-subject",
            assessment_purpose_ref="probe-purpose",
            usage_scope_ref="probe-scope",
            assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
            assessed_system_binding_ref="probe-binding",
            assessed_system_binding_digest=BINDING,
        ),
        claim=EvidenceClaimBinding.applicable(
            claim_ref="probe-claim",
            metric_ref="probe-metric",
            unit="probe-unit",
            measurement_semantics_ref="probe-semantics",
        ),
        provenance=EvidenceProvenanceChain(
            chain_ref="probe-chain", custody_refs=("link-a", "link-b")
        ),
        lifecycle_state=EvidenceLifecycleState.SUBMITTED,
        geography=ApplicabilityCoordinate.applicable("US"),
        domain=ApplicabilityCoordinate.not_applicable(),
        intended_outcome=ApplicabilityCoordinate.applicable("probe-outcome"),
        valid_from=T_FROM,
        valid_to=T_TO,
    )
    base.update(overrides)
    return CanonicalEvidenceIdentity(**base)


def build_request(**overrides) -> EvidenceVerificationRequest:
    base = dict(
        evidence=build_identity(),
        expected_content_digest=CONTENT,
        expected_tenant_id="probe-tenant",
        expected_assessment_context_ref="probe-ctx",
        expected_assessment_context_digest=CONTEXT,
        expected_subject_ref="probe-subject",
        expected_assessment_purpose_ref="probe-purpose",
        expected_usage_scope_ref="probe-scope",
        expected_assessed_system_binding_ref="probe-binding",
        expected_assessed_system_binding_digest=BINDING,
        as_of=T_MID,
        requested_trust_stages=(EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,),
    )
    base.update(overrides)
    return EvidenceVerificationRequest(**base)


# --------------------------------------------------------------------------- #
# A. Nothing in this API can report a verified state
# --------------------------------------------------------------------------- #
@probe
def probe_no_verified_state_exists():
    assert list(EvidenceStructuralStatus) == [
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    ]
    ident = build_identity()
    assert ident.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert ident.authenticity_verified is False
    assert len(ident.unestablished_trust_stages) == 5
    assert ident.established_trust_stages == (
        EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    )


@probe
def probe_every_refusal_reason_is_a_refusal():
    assert set(R) == set(TRUSTED_EVIDENCE_REFUSAL_REASONS)
    assert R.TRUSTED_EVIDENCE_INDETERMINATE in TRUSTED_EVIDENCE_REFUSAL_REASONS
    assert len(list(R)) == 40
    # TEV-1's nineteen keep their exact ordinal positions; TEV-2 appended 21.
    assert [m.name for m in R][:19] == sorted(
        [m.name for m in R][:19], key=[m.name for m in R].index
    )
    assert list(R)[18] is R.TRUSTED_EVIDENCE_INDETERMINATE
    assert list(R)[19] is R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED
    # Still no success state anywhere in the vocabulary.
    for member in R:
        head = member.value.removeprefix("TRUSTED_EVIDENCE_").split("NOT_", 1)[0]
        words = {w for w in head.split("_") if w}
        assert not (words & {"OK", "PASS", "ADMITTED", "SUCCESS", "VERIFIED",
                             "VALID", "AUTHENTIC", "TRUSTED", "APPROVED"}), member


@probe
def probe_a_request_reports_that_no_verification_happened():
    req = build_request()
    assert req.structural_scope_mismatches() == ()
    assert (
        req.unperformed_verification_reason
        is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


# --------------------------------------------------------------------------- #
# B. Forgery routes (ADR §10, task §11)
# --------------------------------------------------------------------------- #
@probe
def probe_verified_true_and_truthy_values_are_unaccepted():
    for truthy in (True, 1, "true", "VERIFIED", [1], {"a": 1}):
        expect_refusal(lambda t=truthy: build_identity(verified=t), TypeError)
        expect_refusal(lambda t=truthy: build_request(verified=t), TypeError)


@probe
def probe_frozen_contracts_reject_assignment():
    ident = build_identity()
    for attribute, value in (
        ("authenticity_verified", True),
        ("structural_status", "VERIFIED"),
        ("evidence_id", "other"),
        ("content_digest", OTHER),
    ):
        expect_refusal(
            lambda a=attribute, v=value: setattr(ident, a, v),
            dataclasses.FrozenInstanceError,
        )
    assert ident.authenticity_verified is False


@probe
def probe_direct_enum_construction_cannot_reach_a_verified_member():
    for attempt in ("VERIFIED", "AUTHENTIC", "TRUSTED", "APPROVED", "OK"):
        expect_refusal(lambda a=attempt: EvidenceStructuralStatus(a), ValueError)
        expect_refusal(lambda a=attempt: R(a), ValueError)


@probe
def probe_a_subclass_cannot_enter_a_contract_graph():
    class Forged(CanonicalEvidenceIdentity):
        @property
        def authenticity_verified(self):
            return True

    base = build_identity()
    forged = Forged(
        **{f.name: getattr(base, f.name) for f in dataclasses.fields(base)}
    )
    assert forged.authenticity_verified is True  # it can lie about itself...
    expect_refusal(lambda: build_request(evidence=forged))  # ...and go no further
    # Its digest is separated by the type name bound into the frame.
    assert canonical_digest(forged) != base.canonical_digest()
    assert b'"type":"Forged"' in canonical_bytes(forged)


@probe
def probe_a_property_override_never_reaches_the_digest():
    base = build_identity()
    before = base.canonical_digest()
    original = CanonicalEvidenceIdentity.authenticity_verified
    try:
        CanonicalEvidenceIdentity.authenticity_verified = property(lambda self: True)
        assert base.canonical_digest() == before
        assert b"authenticity_verified" not in base.canonical_bytes()
    finally:
        CanonicalEvidenceIdentity.authenticity_verified = original
    assert build_identity().authenticity_verified is False


@probe
def probe_an_authority_looking_name_confers_nothing():
    for name in ("Ugence Trusted Evidence Authority", "TAP", "ROOT-TRUST-ANCHOR"):
        ident = build_identity(
            observation=EvidenceObservation(
                producer_id=name,
                collected_at=T_COL,
                observed_from=T_OBS,
                observed_to=None,
                issuer_id="",
            )
        )
        assert ident.authenticity_verified is False
        assert (
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC
            in ident.unestablished_trust_stages
        )


@probe
def probe_a_matching_digest_is_not_verification():
    req = build_request(expected_content_digest=CONTENT)
    assert req.structural_scope_mismatches() == ()
    assert req.evidence.authenticity_verified is False
    # Recomputing the digest independently changes nothing about trust.
    assert (
        hashlib.sha256(req.evidence.canonical_bytes()).hexdigest()
        == req.evidence.canonical_digest()
    )
    assert req.evidence.unestablished_trust_stages


@probe
def probe_a_duck_typed_lookalike_is_refused():
    base = build_identity()

    class Lookalike:
        pass

    fake = Lookalike()
    for field in dataclasses.fields(base):
        setattr(fake, field.name, getattr(base, field.name))
    fake.authenticity_verified = True
    expect_refusal(lambda: build_request(evidence=fake))

    @dataclasses.dataclass(frozen=True)
    class LookalikeSchema:
        schema_id: str = "probe.schema"
        schema_version: str = "1"

    expect_refusal(lambda: build_identity(schema=LookalikeSchema()))


@probe
def probe_cross_scope_replay_is_detectable_on_every_axis():
    base = build_identity()
    axes = {
        "tenant_id": ("probe-tenant-2", R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        "assessment_context_ref": ("probe-ctx-2", R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        "subject_ref": ("probe-subject-2", R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        "assessed_system_binding_ref": (
            "probe-binding-2",
            R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH,
        ),
        "assessment_purpose_ref": (
            "probe-purpose-2",
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
        "usage_scope_ref": (
            "probe-scope-2",
            R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        ),
    }
    for field, (replacement, expected) in axes.items():
        original_scope = base.scope
        replayed_scope = EvidenceScopeBinding(
            **{
                **{
                    f.name: getattr(original_scope, f.name)
                    for f in dataclasses.fields(original_scope)
                },
                field: replacement,
            }
        )
        replayed = build_identity(scope=replayed_scope)
        assert replayed.canonical_digest() != base.canonical_digest(), field
        assert expected in build_request(evidence=replayed).structural_scope_mismatches()


# --------------------------------------------------------------------------- #
# C. Canonicalization and digests, recomputed independently
# --------------------------------------------------------------------------- #
@probe
def probe_digest_is_sha256_over_exactly_the_canonical_bytes():
    for contract in (
        build_identity(),
        build_request(),
        EvidenceSchemaRef(schema_id="probe.schema", schema_version="1"),
    ):
        raw = canonical_bytes(contract)
        assert hashlib.sha256(raw).hexdigest() == canonical_digest(contract)


@probe
def probe_the_canonical_frame_is_versioned_and_domain_separated():
    framed = json.loads(canonical_bytes(build_identity()).decode("utf-8"))
    assert framed["canonicalization"] == TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
    assert framed["domain"] == EVIDENCE_IDENTITY_DIGEST_DOMAIN
    assert framed["type"] == "CanonicalEvidenceIdentity"
    assert (
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION
        == "ugence.trusted-evidence-authority/canonicalization/v1"
    )
    assert (
        EVIDENCE_IDENTITY_DIGEST_DOMAIN
        == "ugence.trusted-evidence-authority/evidence-identity/v1"
    )


@probe
def probe_a_hand_written_byte_string_reproduces_the_digest():
    """Reconstructed from the documented rules, not from a program run."""

    literal = (
        b'{"body":{"schema_id":"probe.schema","schema_version":"1"},'
        b'"canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",'
        b'"domain":"ugence.trusted-evidence-authority/evidence-identity/v1",'
        b'"type":"EvidenceSchemaRef"}'
    )
    schema = EvidenceSchemaRef(schema_id="probe.schema", schema_version="1")
    assert canonical_bytes(schema) == literal
    assert canonical_digest(schema) == hashlib.sha256(literal).hexdigest()


@probe
def probe_utc_offset_equivalence_and_microsecond_preservation():
    utc = datetime(2026, 4, 1, 9, 30, 0, 125000, tzinfo=UTC)
    ist = utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    nyc = utc.astimezone(timezone(timedelta(hours=-4)))
    built = [
        build_identity(
            observation=EvidenceObservation(
                producer_id="probe-producer",
                collected_at=T_COL,
                observed_from=t,
                observed_to=None,
                issuer_id="",
            )
        )
        for t in (utc, ist, nyc)
    ]
    assert len({b.canonical_bytes() for b in built}) == 1
    assert b"09:30:00.125000Z" in built[0].canonical_bytes()
    shifted = build_identity(
        observation=EvidenceObservation(
            producer_id="probe-producer",
            collected_at=T_COL,
            observed_from=utc.replace(microsecond=125001),
            observed_to=None,
            issuer_id="",
        )
    )
    assert shifted.canonical_digest() != built[0].canonical_digest()


@probe
def probe_naive_datetimes_are_refused_everywhere():
    naive = datetime(2026, 4, 1, 9, 30)
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p", collected_at=naive, observed_from=T_OBS
        )
    )
    expect_refusal(lambda: build_identity(valid_from=naive))
    expect_refusal(lambda: build_request(as_of=naive))
    expect_refusal(lambda: build_identity().is_valid_at(naive))


@probe
def probe_reordered_stage_input_is_equivalent_and_custody_order_is_not():
    a = build_request(
        requested_trust_stages=(
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
            EvidenceTrustStage.CURRENTLY_VALID,
        )
    )
    b = build_request(
        requested_trust_stages=(
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        )
    )
    assert a.canonical_digest() == b.canonical_digest()

    forward = build_identity(
        provenance=EvidenceProvenanceChain(chain_ref="c", custody_refs=("x", "y"))
    )
    backward = build_identity(
        provenance=EvidenceProvenanceChain(chain_ref="c", custody_refs=("y", "x"))
    )
    assert forward.canonical_digest() != backward.canonical_digest()


@probe
def probe_the_encoder_has_no_permissive_fallback():
    @dataclasses.dataclass(frozen=True)
    class Holder:
        payload: object

    class Opaque:
        pass

    for bad in (
        Opaque(),
        1.5,
        float("nan"),
        float("inf"),
        b"bytes",
        {"k": "v"},
        {1, 2},
        datetime(2026, 4, 1),
        "é",  # NFD, not NFC
    ):
        expect_refusal(
            lambda b=bad: canonical_bytes(Holder(payload=b)),
            TrustedEvidenceCanonicalizationError,
        )


@probe
def probe_none_is_explicit_and_distinct_from_empty():
    with_bound = build_identity(valid_to=T_TO)
    without = build_identity(valid_to=None)
    assert json.loads(canonical_bytes(without))["body"]["valid_to"] is None
    assert with_bound.canonical_digest() != without.canonical_digest()


# --------------------------------------------------------------------------- #
# D. Constructor invariants
# --------------------------------------------------------------------------- #
@probe
def probe_blank_padded_and_mistyped_identifiers_are_refused():
    for bad in ("", " ", "\t", " probe-ev", "probe-ev ", None, 1, True, b"x", ["x"]):
        expect_refusal(lambda b=bad: build_identity(evidence_id=b))


@probe
def probe_malformed_digests_are_refused():
    for bad in ("", "nope", CONTENT.upper(), CONTENT[:-1], CONTENT + "0",
                "sha256:" + CONTENT, " " + CONTENT):
        expect_refusal(lambda b=bad: build_identity(content_digest=b))


@probe
def probe_temporal_orderings_are_enforced():
    # reversed observation window
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p",
            collected_at=T_COL,
            observed_from=datetime(2026, 4, 1, 11, tzinfo=UTC),
            observed_to=datetime(2026, 4, 1, 10, tzinfo=UTC),
        )
    )
    # zero-length window (half-open)
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p", collected_at=T_COL, observed_from=T_OBS, observed_to=T_OBS
        )
    )
    # collection before observation
    expect_refusal(
        lambda: EvidenceObservation(
            producer_id="p",
            collected_at=T_OBS - timedelta(seconds=1),
            observed_from=T_OBS,
        )
    )
    # reversed and zero-length validity interval
    expect_refusal(lambda: build_identity(valid_from=T_TO, valid_to=T_FROM))
    expect_refusal(lambda: build_identity(valid_from=T_FROM, valid_to=T_FROM))


@probe
def probe_half_open_validity_boundaries():
    ident = build_identity()
    tick = timedelta(microseconds=1)
    assert ident.is_valid_at(T_FROM) is True
    assert ident.temporal_refusal_at(T_FROM) is None
    assert ident.temporal_refusal_at(T_FROM - tick) is R.TRUSTED_EVIDENCE_NOT_YET_VALID
    assert ident.is_valid_at(T_TO - tick) is True
    assert ident.is_valid_at(T_TO) is False
    assert ident.temporal_refusal_at(T_TO) is R.TRUSTED_EVIDENCE_STALE


@probe
def probe_applicability_must_be_declared_not_omitted():
    expect_refusal(
        lambda: ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.APPLICABLE, value=""
        )
    )
    expect_refusal(
        lambda: ApplicabilityCoordinate(
            declaration=ApplicabilityDeclaration.NOT_APPLICABLE, value="US"
        )
    )
    assert (
        build_identity(geography=ApplicabilityCoordinate.not_applicable()).canonical_digest()
        != build_identity(geography=ApplicabilityCoordinate.applicable("US")).canonical_digest()
    )


@probe
def probe_the_system_binding_pair_is_co_required_or_co_absent():
    def scope(**kw):
        base = dict(
            tenant_id="t",
            assessment_context_ref="c",
            assessment_context_digest=CONTEXT,
            subject_ref="s",
            assessment_purpose_ref="p",
            usage_scope_ref="u",
            assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
            assessed_system_binding_ref="b",
            assessed_system_binding_digest=BINDING,
        )
        base.update(kw)
        return EvidenceScopeBinding(**base)

    expect_refusal(lambda: scope(assessed_system_binding_digest=""))
    expect_refusal(lambda: scope(assessed_system_binding_ref=""))
    expect_refusal(
        lambda: scope(
            assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE
        )
    )
    ok = scope(
        assessed_system_applicability=ApplicabilityDeclaration.NOT_APPLICABLE,
        assessed_system_binding_ref="",
        assessed_system_binding_digest="",
    )
    assert ok.assessed_system_binding_ref == ""


@probe
def probe_custody_chains_reject_scalars_duplicates_and_blanks():
    for bad in ("abc", b"abc", {"a": 1}, 42, None):
        expect_refusal(
            lambda b=bad: EvidenceProvenanceChain(chain_ref="c", custody_refs=b)
        )
    expect_refusal(
        lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("a", "a"))
    )
    expect_refusal(
        lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("a", " "))
    )
    caller = ["a", "b"]
    chain = EvidenceProvenanceChain(chain_ref="c", custody_refs=caller)
    caller.append("c")
    assert chain.custody_refs == ("a", "b")


# --------------------------------------------------------------------------- #
# E. Lifecycle relation
# --------------------------------------------------------------------------- #
@probe
def probe_the_lifecycle_relation_is_closed_and_terminal_states_are_terminal():
    S = EvidenceLifecycleState
    admissible = {
        (S.PRODUCED, S.SUBMITTED), (S.PRODUCED, S.EXPIRED), (S.PRODUCED, S.REVOKED),
        (S.SUBMITTED, S.RETAINED), (S.SUBMITTED, S.EXPIRED), (S.SUBMITTED, S.REVOKED),
        (S.RETAINED, S.EXPIRED), (S.RETAINED, S.REVOKED),
    }
    for current in S:
        for proposed in S:
            expected = (current, proposed) in admissible
            assert is_valid_lifecycle_transition(current, proposed) is expected
            if not expected:
                try:
                    require_valid_lifecycle_transition(current, proposed)
                except TrustedEvidenceLifecycleError as exc:
                    assert (
                        exc.reason
                        is R.TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION
                    )
                else:
                    raise AssertionError(f"{current} -> {proposed} was not refused")
    assert EVIDENCE_LIFECYCLE_TRANSITIONS[S.REVOKED] == frozenset()
    assert EVIDENCE_LIFECYCLE_TRANSITIONS[S.EXPIRED] == frozenset()


@probe
def probe_no_verified_or_superseded_lifecycle_state_exists():
    values = {s.value for s in EvidenceLifecycleState}
    assert values == {"PRODUCED", "SUBMITTED", "RETAINED", "EXPIRED", "REVOKED"}
    assert not any("VERIF" in v or "SUPERSED" in v for v in values)
    assert not any("SUPERSED" in r.value for r in R)


# --------------------------------------------------------------------------- #
# F. Milestone boundary, from the public surface alone
# --------------------------------------------------------------------------- #
@probe
def probe_stage_six_cannot_be_requested_from_tap():
    expect_refusal(
        lambda: build_request(
            requested_trust_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,)
        )
    )
    expect_refusal(lambda: build_request(requested_trust_stages=()))


@probe
def probe_only_a_signed_artifact_is_named_a_receipt():
    """§13.3 — an unsigned artifact is not a receipt, and is not named as one."""

    import ugence_trusted_evidence_authority.api as api_module

    assert "EvidenceVerificationReceiptPayload" in api_module.__all__
    assert "EvidenceVerificationReceipt" not in api_module.__all__
    assert not hasattr(api_module, "EvidenceVerificationReceipt")
    for name in api_module.__all__:
        if name.endswith("Receipt") and "_" not in name and not name.isupper():
            assert name.startswith("Signed"), name


@probe
def probe_no_later_milestone_capability_is_exported():
    """TEV-2's ceiling: Benchmark Registry, Readiness and ROI stay absent."""

    import ugence_trusted_evidence_authority.api as api_module

    for name in api_module.__all__:
        flattened = name.lower().replace("_", "")
        for forbidden in ("benchmark", "readiness", "roi", "forecast",
                          "attribution", "valuation", "actiongate",
                          "deployment", "credential", "kms", "hsm",
                          "certificate", "riskauthority", "cloudscaling",
                          "governedvalue", "policyapplicability"):
            assert forbidden not in flattened, (name, forbidden)


@probe
def probe_no_public_object_exposes_an_authorization_surface():
    import ugence_trusted_evidence_authority.api as api_module

    # TEV-2 verifies, signs, issues and resolves — those are its ratified verbs
    # (ADR §30). What must stay absent everywhere is the *authorization*
    # vocabulary: E-14 keeps TAP off the runtime path and §13.2 / E-12 keep a
    # receipt from authorizing anything.
    forbidden = {"authorize", "authorizes_deployment", "authorize_deployment",
                 "authorize_action", "approve", "grant", "allow", "permit",
                 "deploy", "enact", "execute", "authorization",
                 "evaluate_policy", "compute_readiness", "compute_roi"}
    for name in api_module.__all__:
        obj = getattr(api_module, name)
        if isinstance(obj, type):
            assert not (set(dir(obj)) & forbidden), name


@probe
def probe_the_package_version_and_typing_marker():
    import pathlib

    import ugence_trusted_evidence_authority as pkg

    assert pkg.__version__ == "0.3.0"
    assert not hasattr(pkg, "CONTRACT_VERSION")
    assert (pathlib.Path(pkg.__file__).resolve().parent / "py.typed").is_file()


@probe
def probe_this_harness_imports_only_the_curated_api_and_the_stdlib():
    """This harness's own independence, asserted from inside it.

    Checks what *this file* imports, not what the package loads internally: the
    package is naturally free to import its own private modules, but a probe
    harness that reached into them — or into a test helper, fixture or conftest
    — would only re-confirm the suite's own assumptions.
    """

    import ast
    import pathlib

    for forbidden in ("_builders", "conftest"):
        assert forbidden not in sys.modules, forbidden

    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    imported: set = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.level, "this harness uses no relative import"
            imported.add(node.module)

    for module in imported:
        root = module.split(".")[0]
        if root in stdlib or root == "__future__":
            continue
        assert module in (
            "ugence_trusted_evidence_authority",
            "ugence_trusted_evidence_authority.api",
        ), f"probe harness imports a non-curated module: {module}"



# --------------------------------------------------------------------------- #
# G. Claim / metric / units (ADR §9 rows 11-12) — audit finding A-02
# --------------------------------------------------------------------------- #
@probe
def probe_claim_applicability_must_be_declared_not_inferred():
    expect_refusal(lambda: EvidenceClaimBinding(), TypeError)
    declared = EvidenceClaimBinding.not_applicable()
    assert declared.applicability is ApplicabilityDeclaration.NOT_APPLICABLE
    assert declared.claim_identity == ("NOT_APPLICABLE", "", "", "", "")


@probe
def probe_the_claim_units_co_requirement_holds():
    for kw in (
        dict(claim_ref="c", unit="u", measurement_semantics_ref="s"),
        dict(metric_ref="m", unit="u", measurement_semantics_ref="s"),
        dict(claim_ref="c", metric_ref="m", unit="u", measurement_semantics_ref="s"),
    ):
        EvidenceClaimBinding(applicability=ApplicabilityDeclaration.APPLICABLE, **kw)
    for kw in (
        dict(unit="u", measurement_semantics_ref="s"),
        dict(claim_ref="c", measurement_semantics_ref="s"),
        dict(claim_ref="c", unit="u"),
        dict(claim_ref="c"),
        {},
    ):
        expect_refusal(
            lambda k=kw: EvidenceClaimBinding(
                applicability=ApplicabilityDeclaration.APPLICABLE, **k
            )
        )
    for field in ("claim_ref", "metric_ref", "unit", "measurement_semantics_ref"):
        expect_refusal(
            lambda f=field: EvidenceClaimBinding(
                applicability=ApplicabilityDeclaration.NOT_APPLICABLE, **{f: "x"}
            )
        )


@probe
def probe_empty_string_and_none_are_not_not_applicable():
    expect_refusal(
        lambda: EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE,
            claim_ref="", metric_ref="", unit="", measurement_semantics_ref="",
        )
    )
    expect_refusal(
        lambda: EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE,
            claim_ref=None, unit="u", measurement_semantics_ref="s",
        )
    )


@probe
def probe_every_claim_coordinate_moves_the_evidence_digest():
    base = build_identity()
    variants = [
        EvidenceClaimBinding.applicable(
            claim_ref="other", metric_ref="probe-metric",
            unit="probe-unit", measurement_semantics_ref="probe-semantics"),
        EvidenceClaimBinding.applicable(
            claim_ref="probe-claim", metric_ref="other",
            unit="probe-unit", measurement_semantics_ref="probe-semantics"),
        EvidenceClaimBinding.applicable(
            claim_ref="probe-claim", metric_ref="probe-metric",
            unit="other", measurement_semantics_ref="probe-semantics"),
        EvidenceClaimBinding.applicable(
            claim_ref="probe-claim", metric_ref="probe-metric",
            unit="probe-unit", measurement_semantics_ref="other"),
        EvidenceClaimBinding.not_applicable(),
    ]
    digests = {base.canonical_digest()}
    for variant in variants:
        mutated = build_identity(claim=variant)
        assert mutated.canonical_digest() != base.canonical_digest()
        assert mutated.coordinate_identity != base.coordinate_identity
        digests.add(mutated.canonical_digest())
    assert len(digests) == len(variants) + 1


@probe
def probe_the_claim_contract_computes_nothing():
    forbidden = {"convert", "normalize", "compare", "evaluate", "calculate", "result"}
    assert not (set(dir(EvidenceClaimBinding)) & forbidden)


# --------------------------------------------------------------------------- #
# H. Receipt payload (ADR §13) — audit finding A-01
# --------------------------------------------------------------------------- #
RECEIPT_T = datetime(2026, 7, 1, 6, 0, 0, 500000, tzinfo=UTC)
RCPT_FROM = datetime(2026, 7, 1, tzinfo=UTC)
RCPT_TO = datetime(2026, 11, 1, tzinfo=UTC)


def build_receipt(**overrides) -> EvidenceVerificationReceiptPayload:
    """The most favourable-looking payload a caller can build."""

    base = dict(
        receipt_id="probe-receipt",
        schema=EvidenceSchemaRef(schema_id="probe.receipt", schema_version="1"),
        source_evidence_identity_digest=build_identity().canonical_digest(),
        evidence_content_digest=CONTENT,
        verification_request_digest=build_request().canonical_digest(),
        scope=build_identity().scope,
        verified_at=RECEIPT_T,
        verifier_authority_id="Ugence Root Trust Authority",
        verifier_key_id="root-signing-key",
        verification_protocol_id="probe.protocol",
        verification_protocol_version="1",
        declared_outcome=DeclaredVerificationOutcome.DECLARED_ADMITTED,
        declared_cleared_stages=tuple(RECEIPT_REPORTABLE_TRUST_STAGES),
        declared_unattempted_stages=(),
        declared_refusal_reasons=(),
        evidence_valid_from=T_FROM,
        evidence_valid_to=T_TO,
        receipt_valid_from=RCPT_FROM,
        receipt_valid_to=RCPT_TO,
    )
    base.update(overrides)
    return EvidenceVerificationReceiptPayload(**base)


@probe
def probe_a_maximally_favourable_payload_is_still_structurally_unverified():
    payload = build_receipt()
    assert payload.declares_admission is True
    assert set(payload.declared_cleared_stages) == set(RECEIPT_REPORTABLE_TRUST_STAGES)
    assert payload.structural_status is EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
    assert payload.authenticity_verified is False
    assert payload.established_trust_stages == (
        EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
    )
    assert (
        EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC
        in payload.unestablished_trust_stages
    )
    assert EvidenceTrustStage.POLICY_SUFFICIENT in payload.unestablished_trust_stages
    assert (
        payload.envelope_verification_reason
        is R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
    )


@probe
def probe_the_payload_carries_no_signature_of_any_kind():
    names = {f.name for f in dataclasses.fields(EvidenceVerificationReceiptPayload)}
    # Unchanged by TEV-2: the envelope **wraps** this payload, and retrofitted
    # no field into it. Every digest TEV-1 pinned is therefore still exact.
    for forbidden in ("signature", "signed", "signer", "envelope", "trust_anchor",
                      "public_key", "algorithm", "certificate", "key_material"):
        assert forbidden not in names, forbidden
    for forbidden in ("signature", "signed", "trust_anchor"):
        expect_refusal(lambda f=forbidden: build_receipt(**{f: b"x"}), TypeError)
    body = json.loads(canonical_bytes(build_receipt()))["body"]
    assert not any("sign" in k.lower() for k in body)


@probe
def probe_receipt_forgery_routes_are_all_closed():
    payload = build_receipt()
    for truthy in (True, 1, "true", [1], {"a": 1}):
        expect_refusal(lambda t=truthy: build_receipt(verified=t), TypeError)
        expect_refusal(
            lambda t=truthy: build_receipt(authenticity_verified=t), TypeError
        )
    expect_refusal(
        lambda: setattr(payload, "authenticity_verified", True),
        dataclasses.FrozenInstanceError,
    )
    expect_refusal(
        lambda: object.__setattr__(payload, "authenticity_verified", True),
        AttributeError,
    )
    payload.__dict__["authenticity_verified"] = True
    assert payload.authenticity_verified is False
    for attempt in ("DECLARED_VERIFIED", "AUTHORITY_VERIFIED", "ADMITTED", "OK"):
        expect_refusal(lambda a=attempt: DeclaredVerificationOutcome(a), ValueError)

    class ForgedReceipt(EvidenceVerificationReceiptPayload):
        @property
        def authenticity_verified(self):
            return True

    forged = ForgedReceipt(
        **{f.name: getattr(payload, f.name) for f in dataclasses.fields(payload)}
    )
    assert canonical_digest(forged) != payload.canonical_digest()
    assert b'"type":"ForgedReceipt"' in canonical_bytes(forged)

    class Lookalike:
        pass

    fake = Lookalike()
    for field in dataclasses.fields(payload):
        setattr(fake, field.name, getattr(payload, field.name))
    fake.authenticity_verified = True
    expect_refusal(lambda: canonical_bytes(fake), TrustedEvidenceCanonicalizationError)


@probe
def probe_a_monkeypatched_property_never_reaches_the_receipt_digest():
    payload = build_receipt()
    before = payload.canonical_digest()
    original = EvidenceVerificationReceiptPayload.authenticity_verified
    try:
        EvidenceVerificationReceiptPayload.authenticity_verified = property(
            lambda self: True
        )
        assert payload.canonical_digest() == before
        assert b"authenticity_verified" not in payload.canonical_bytes()
    finally:
        EvidenceVerificationReceiptPayload.authenticity_verified = original
    assert build_receipt().authenticity_verified is False


@probe
def probe_receipt_stage_and_outcome_coherence():
    for field in ("declared_cleared_stages", "declared_unattempted_stages"):
        expect_refusal(
            lambda f=field: build_receipt(
                **{f: (EvidenceTrustStage.POLICY_SUFFICIENT,)}
            )
        )
    expect_refusal(
        lambda: build_receipt(
            declared_cleared_stages=(EvidenceTrustStage.CURRENTLY_VALID,),
            declared_unattempted_stages=(EvidenceTrustStage.CURRENTLY_VALID,),
        )
    )
    expect_refusal(
        lambda: build_receipt(declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,))
    )
    expect_refusal(lambda: build_receipt(declared_cleared_stages=()))
    expect_refusal(
        lambda: build_receipt(
            declared_outcome=DeclaredVerificationOutcome.DECLARED_REFUSED,
            declared_refusal_reasons=(),
        )
    )
    expect_refusal(
        lambda: build_receipt(
            declared_outcome=DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
            declared_cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,),
            declared_refusal_reasons=(R.TRUSTED_EVIDENCE_STALE,),
        )
    )
    ok = build_receipt(
        declared_outcome=DeclaredVerificationOutcome.DECLARED_INDETERMINATE,
        declared_cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,),
        declared_refusal_reasons=(R.TRUSTED_EVIDENCE_INDETERMINATE,),
    )
    assert ok.declares_admission is False
    assert ok.authenticity_verified is False


@probe
def probe_receipt_and_evidence_validity_are_never_conflated():
    payload = build_receipt(
        evidence_valid_from=datetime(2026, 1, 1, tzinfo=UTC),
        evidence_valid_to=datetime(2026, 2, 1, tzinfo=UTC),
        receipt_valid_from=datetime(2026, 7, 1, tzinfo=UTC),
        receipt_valid_to=datetime(2026, 12, 1, tzinfo=UTC),
    )
    instant = datetime(2026, 8, 1, tzinfo=UTC)
    assert payload.receipt_is_valid_at(instant) is True
    assert payload.evidence_is_valid_at(instant) is False
    tick = timedelta(microseconds=1)
    assert payload.receipt_is_valid_at(datetime(2026, 7, 1, tzinfo=UTC)) is True
    assert payload.receipt_is_valid_at(datetime(2026, 12, 1, tzinfo=UTC)) is False
    assert payload.receipt_is_valid_at(datetime(2026, 12, 1, tzinfo=UTC) - tick) is True
    expect_refusal(lambda: payload.receipt_is_valid_at(datetime(2026, 8, 1)))
    expect_refusal(
        lambda: build_receipt(receipt_valid_from=RCPT_TO, receipt_valid_to=RCPT_FROM)
    )
    expect_refusal(
        lambda: build_receipt(evidence_valid_from=T_TO, evidence_valid_to=T_FROM)
    )


@probe
def probe_receipt_domain_separation_and_independent_digest():
    payload = build_receipt()
    frame = json.loads(canonical_bytes(payload))
    assert frame["domain"] == EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
    assert frame["type"] == "EvidenceVerificationReceiptPayload"
    assert (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
        == "ugence.trusted-evidence-authority/"
        "evidence-verification-receipt-payload/v1"
    )
    assert (
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN
        != EVIDENCE_IDENTITY_DIGEST_DOMAIN
    )
    assert (
        hashlib.sha256(canonical_bytes(payload)).hexdigest()
        == canonical_digest(payload)
    )
    ident = build_identity()
    for other in (
        ident, ident.schema, ident.scope, ident.observation, ident.provenance,
        ident.claim, build_request(),
    ):
        assert canonical_bytes(other) != canonical_bytes(payload)
        assert canonical_digest(other) != canonical_digest(payload)
        assert json.loads(canonical_bytes(other))["domain"] != frame["domain"]


@probe
def probe_receipt_reordered_sets_are_equivalent_and_every_field_is_load_bearing():
    a = build_receipt(
        declared_cleared_stages=(
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            EvidenceTrustStage.CURRENTLY_VALID,
        )
    )
    b = build_receipt(
        declared_cleared_stages=(
            EvidenceTrustStage.CURRENTLY_VALID,
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
        )
    )
    assert a.canonical_bytes() == b.canonical_bytes()

    base = build_receipt()
    mutations = {
        "receipt_id": dict(receipt_id="probe-receipt-2"),
        "source_evidence_identity_digest": dict(source_evidence_identity_digest=OTHER),
        "evidence_content_digest": dict(evidence_content_digest=OTHER),
        "verification_request_digest": dict(verification_request_digest=OTHER),
        "verified_at": dict(verified_at=RECEIPT_T + timedelta(microseconds=1)),
        "verifier_authority_id": dict(verifier_authority_id="other-authority"),
        "verifier_key_id": dict(verifier_key_id="other-key"),
        "verification_protocol_id": dict(verification_protocol_id="other.protocol"),
        "verification_protocol_version": dict(verification_protocol_version="2"),
        "declared_cleared_stages": dict(
            declared_cleared_stages=(EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,)
        ),
        "evidence_valid_to": dict(evidence_valid_to=T_TO + timedelta(seconds=1)),
        "receipt_valid_to": dict(receipt_valid_to=RCPT_TO + timedelta(seconds=1)),
    }
    digests = {base.canonical_digest()}
    for name, kw in mutations.items():
        mutated = build_receipt(**kw)
        assert mutated.canonical_digest() != base.canonical_digest(), name
        digests.add(mutated.canonical_digest())
    assert len(digests) == len(mutations) + 1


@probe
def probe_receipt_required_coordinates_cannot_be_blank():
    for name in ("receipt_id", "verifier_authority_id", "verifier_key_id",
                 "verification_protocol_id", "verification_protocol_version"):
        for bad in ("", "  ", " padded", None, 1, True):
            expect_refusal(lambda n=name, b=bad: build_receipt(**{n: b}))
    for name in ("source_evidence_identity_digest", "evidence_content_digest",
                 "verification_request_digest"):
        for bad in ("", "nope", CONTENT.upper()):
            expect_refusal(lambda n=name, b=bad: build_receipt(**{n: b}))
    expect_refusal(lambda: build_receipt(verified_at=datetime(2026, 7, 1)))


# --------------------------------------------------------------------------- #
# I. NFC at construction (audit finding A-03)
# --------------------------------------------------------------------------- #
@probe
def probe_non_nfc_strings_are_refused_at_construction():
    import unicodedata

    nfd = "caf\u0065\u0301-id"
    nfc = "caf\u00e9-id"
    assert unicodedata.normalize("NFC", nfd) == nfc != nfd, "fixture is already NFC"

    expect_refusal(lambda: EvidenceSchemaRef(schema_id=nfd, schema_version="1"))
    expect_refusal(lambda: build_identity(evidence_id=nfd))
    expect_refusal(lambda: build_identity(evidence_type=nfd))
    expect_refusal(
        lambda: EvidenceProvenanceChain(chain_ref="c", custody_refs=("ok", nfd))
    )
    expect_refusal(lambda: ApplicabilityCoordinate.applicable(nfd))
    expect_refusal(
        lambda: EvidenceClaimBinding.applicable(
            claim_ref=nfd, unit="u", measurement_semantics_ref="s"
        )
    )
    expect_refusal(lambda: build_request(expected_tenant_id=nfd))
    expect_refusal(lambda: build_receipt(verifier_authority_id=nfd))

    accepted = EvidenceSchemaRef(schema_id=nfc, schema_version="1")
    assert accepted.schema_id == nfc != nfd

    built = EvidenceSchemaRef(schema_id="ok", schema_version="1")
    object.__setattr__(built, "schema_id", nfd)
    expect_refusal(
        lambda: canonical_bytes(built), TrustedEvidenceCanonicalizationError
    )




# =========================================================================== #
# TEV-2 — the verification-authority layer
#
# Built from the curated public API alone, exactly like everything above. The
# signed bytes are reconstructed here **by hand** — from the documented framing
# rules, with ``int.to_bytes`` and ``b"".join`` — and compared against what the
# package produces, so a probe failure means the package changed its signing
# input rather than that this file merely agrees with itself.
# =========================================================================== #

# --------------------------------------------------------------------------- #
# NON-PRODUCTION probe keys. Fixed, public, hard-coded byte patterns committed
# to a public source tree. NEVER usable as production key material.
# --------------------------------------------------------------------------- #
NON_PRODUCTION_PROBE_PRODUCER_SEED = bytes(range(96, 128))
NON_PRODUCTION_PROBE_AUTHORITY_SEED = bytes(range(128, 160))
NON_PRODUCTION_PROBE_ATTACKER_SEED = bytes(range(160, 192))

PROBE_PRODUCER_AUTHORITY = "probe-producer-authority-nonprod"
PROBE_PRODUCER_KEY = "probe-producer-key-nonprod"
PROBE_VERIFIER_AUTHORITY = "probe-verifier-authority-nonprod"
PROBE_VERIFIER_KEY = "probe-verifier-key-nonprod"
PROBE_ANCHOR_SET = "probe-anchor-set-nonprod"

T_KEY_FROM = datetime(2026, 1, 1, tzinfo=UTC)
T_KEY_TO = datetime(2027, 1, 1, tzinfo=UTC)
T_VERIFIED = datetime(2026, 7, 1, 12, 0, 0, 500000, tzinfo=UTC)


def probe_producer_key():
    return TrustedEvidenceSigningKey(NON_PRODUCTION_PROBE_PRODUCER_SEED)


def probe_authority_key():
    return TrustedEvidenceSigningKey(NON_PRODUCTION_PROBE_AUTHORITY_SEED)


def probe_attacker_key():
    return TrustedEvidenceSigningKey(NON_PRODUCTION_PROBE_ATTACKER_SEED)


def probe_producer_anchor(**kw):
    return TrustAnchorRecord(**{
        "authority_id": PROBE_PRODUCER_AUTHORITY,
        "key_id": PROBE_PRODUCER_KEY,
        "capability": TrustAnchorCapability.EVIDENCE_PRODUCTION,
        "public_key": encode_public_key(
            probe_producer_key().verification_key.public_key_bytes),
        "trust_anchor_set_id": PROBE_ANCHOR_SET,
        "trust_anchor_set_version": "1",
        "effective_from": T_KEY_FROM,
        "effective_to": T_KEY_TO,
        **kw,
    })


def probe_authority_anchor(**kw):
    return TrustAnchorRecord(**{
        "authority_id": PROBE_VERIFIER_AUTHORITY,
        "key_id": PROBE_VERIFIER_KEY,
        "capability": TrustAnchorCapability.RECEIPT_ISSUANCE,
        "public_key": encode_public_key(
            probe_authority_key().verification_key.public_key_bytes),
        "trust_anchor_set_id": PROBE_ANCHOR_SET,
        "trust_anchor_set_version": "1",
        "effective_from": T_KEY_FROM,
        "effective_to": T_KEY_TO,
        **kw,
    })


def probe_directory(*anchors):
    return StaticTrustAnchorDirectory(
        anchors or (probe_producer_anchor(), probe_authority_anchor()),
        trust_anchor_set_id=PROBE_ANCHOR_SET,
        trust_anchor_set_version="1",
    )


def probe_submission(evidence=None, *, key=None, **kw):
    evidence = build_identity() if evidence is None else evidence
    key = probe_producer_key() if key is None else key
    authority_id = kw.pop("producer_authority_id", PROBE_PRODUCER_AUTHORITY)
    key_id = kw.pop("producer_key_id", PROBE_PRODUCER_KEY)
    signature = kw.pop("signature", encode_signature(key.sign(
        signed_evidence_input_bytes(
            evidence=evidence,
            producer_authority_id=authority_id,
            producer_key_id=key_id))))
    return SignedEvidenceSubmission(**{
        "envelope_schema": SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1,
        "evidence": evidence,
        "evidence_identity_digest": canonical_digest(evidence),
        "producer_authority_id": authority_id,
        "producer_key_id": key_id,
        "signature_profile": TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        "signed_input_domain": TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
        "signature": signature,
        **kw,
    })


def probe_signer(**kw):
    return Ed25519ReceiptSigner(**{
        "signer_authority_id": PROBE_VERIFIER_AUTHORITY,
        "signing_key_id": PROBE_VERIFIER_KEY,
        "signing_key": probe_authority_key(),
        **kw,
    })


def probe_authority(anchors=None, **kw):
    return EvidenceVerificationAuthority(**{
        "authority_id": PROBE_VERIFIER_AUTHORITY,
        "trust_anchors": probe_directory() if anchors is None else anchors,
        "protocol": Ed25519EvidenceAuthenticityProtocol(),
        "receipt_schema": EvidenceSchemaRef(
            schema_id="ugence.receipt.evidence-verification", schema_version="1"),
        **kw,
    })


def probe_determination(**kw):
    authority = probe_authority(kw.pop("anchors", None), **kw.pop("authority_kw", {}))
    return authority.verify(
        kw.pop("submission", probe_submission()),
        kw.pop("request", build_request()),
        verified_at=kw.pop("verified_at", T_VERIFIED),
        verifier_key_id=kw.pop("verifier_key_id", PROBE_VERIFIER_KEY),
        **kw,
    )


def probe_envelope(**kw):
    return ReceiptIssuer(signer=probe_signer()).issue(probe_determination(**kw))


def probe_reverifier(anchors=None):
    return SignedReceiptVerifier(
        trust_anchors=probe_directory() if anchors is None else anchors)


def _refusal_of(envelope=None, *, anchors=None, at=None):
    result = probe_reverifier(anchors).verify_signature(
        probe_envelope() if envelope is None else envelope,
        evaluated_at=T_MID if at is None else at,
    )
    assert result.outcome is ReceiptVerificationOutcome.REFUSED, result
    assert not result.verified
    return result.refusal_reason


def probe_expectation(envelope=None, **overrides):
    """The exact expectation an honest consumer of ``envelope`` would state."""

    payload = (probe_envelope() if envelope is None else envelope).payload
    return dataclasses.replace(
        ReceiptScopeExpectation.from_scope(
            payload.scope,
            evidence_content_digest=payload.evidence_content_digest,
            verification_protocol_id=payload.verification_protocol_id,
            verification_protocol_version=payload.verification_protocol_version),
        **overrides)


def _bound_refusal_of(envelope, field, value, *, anchors=None, at=None):
    expectation = probe_expectation(envelope, **{field: value})
    result = probe_reverifier(anchors).verify_bound(
        envelope, expectation, evaluated_at=T_MID if at is None else at)
    assert result.outcome is ReceiptVerificationOutcome.REFUSED, result
    assert not result.verified
    assert result.scope_expectation_digest == expectation.expectation_digest()
    return result.refusal_reason


# --------------------------------------------------------------------------- #
# Pinned TEV-2 vectors — every one reproducible from the fixtures above with no
# clock, no randomness and no ambient state. Recomputed on every probe run.
# --------------------------------------------------------------------------- #
PINNED_AUTHORITY_PUBLIC_KEY = "cd14b37f956e953194ff7fb73b3d81dcc561d61a7538094b7c3e1a643ee5f3aa"
PINNED_RECEIPT_ID = "receipt-87b7f25038c7aebdd5bdc798873d7aa434c7cd83c1e791ac49a734f23e754a4f"
PINNED_RECEIPT_PAYLOAD_DIGEST = "176f98a11d187f371d5e4a1df6f01d2f2078b4977e12113abfa11430a3933db3"
PINNED_RECEIPT_SIGNED_INPUT_DIGEST = "47720f148e3722b92e45c4c2fbddab0eeaeb39b05b05c1c50a7f9056a731dba2"
PINNED_RECEIPT_SIGNATURE = (
    "c3603daa2bfdc06d1a4f810c9690c9f18981f1e2cfb52ed7f656d0ee25e3564a"
    "459e96ad84b3539b1b2a7b3fb2aa729d6b39c83a3ea4eaa9f0f50ff1156c990e"
)
PINNED_ENVELOPE_DIGEST = "ea82f19fe1ffcb03394b166af926a14e45bb1e5d8e78265a5774ff5f046ab263"
PINNED_EVIDENCE_SIGNATURE = (
    "9d8e3f0834293dcd2810aadd8289cefc55451c2ecc78fa087bc01c32b29aa634"
    "f31e2ccff814b0e06ce13440a996e8b8f43eb9170c1a50dd93fc474203a15109"
)
PINNED_SUBMISSION_DIGEST = "e9ee5dd99072028c13b28ffa6ac8f529c9b4d1695cf7ac2705a578bf1a33d046"


# --------------------------------------------------------------------------- #
# Signed-byte reconstruction, done independently
# --------------------------------------------------------------------------- #

@probe
def probe_the_signed_input_frame_is_reconstructible_from_documented_rules():
    """Rebuild both frames by hand and compare. No package internals used."""

    def frame(elements):
        width = SIGNED_INPUT_LENGTH_PREFIX_BYTES
        out = [len(elements).to_bytes(width, "big")]
        for element in elements:
            out.append(len(element).to_bytes(width, "big"))
            out.append(element)
        return b"".join(out)

    assert SIGNED_INPUT_LENGTH_PREFIX_BYTES == 8
    evidence = build_identity()
    payload = build_receipt()

    expected_evidence = frame((
        TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN.encode("utf-8"),
        SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode("utf-8"),
        EVIDENCE_IDENTITY_DIGEST_DOMAIN.encode("utf-8"),
        PROBE_PRODUCER_AUTHORITY.encode("utf-8"),
        PROBE_PRODUCER_KEY.encode("utf-8"),
        canonical_bytes(evidence),
    ))
    assert signed_evidence_input_bytes(
        evidence=evidence,
        producer_authority_id=PROBE_PRODUCER_AUTHORITY,
        producer_key_id=PROBE_PRODUCER_KEY,
    ) == expected_evidence

    expected_receipt = frame((
        TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN.encode("utf-8"),
        SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.encode("utf-8"),
        TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode("utf-8"),
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN.encode("utf-8"),
        PROBE_VERIFIER_AUTHORITY.encode("utf-8"),
        PROBE_VERIFIER_KEY.encode("utf-8"),
        payload.verification_protocol_id.encode("utf-8"),
        payload.verification_protocol_version.encode("utf-8"),
        canonical_digest(payload).encode("utf-8"),
        canonical_bytes(payload),
    ))
    assert signed_receipt_input_bytes(
        payload=payload,
        signer_authority_id=PROBE_VERIFIER_AUTHORITY,
        signing_key_id=PROBE_VERIFIER_KEY,
    ) == expected_receipt

    assert expected_evidence != expected_receipt


@probe
def probe_the_frame_is_length_unambiguous():
    """Moving an element boundary must change the bytes (no concatenation bug)."""

    assert framed_signed_input((b"ab", b"c")) != framed_signed_input((b"a", b"bc"))
    assert framed_signed_input((b"a",)) != framed_signed_input((b"a", b""))
    assert framed_signed_input((b"",)) != framed_signed_input((b"", b""))
    expect_refusal(lambda: framed_signed_input(()))
    expect_refusal(lambda: framed_signed_input((b"ok", "not-bytes")))
    expect_refusal(lambda: framed_signed_input([b"a"]))


@probe
def probe_a_fixed_signature_vector_verifies_and_is_pinned():
    """One end-to-end vector, pinned byte-for-byte and reproduced here.

    Every value below derives from fixed inputs with no clock and no randomness,
    so it is stable across machines and runs. If the signing input, the
    canonicalization, the profile, the framing or the key derivation changes,
    this probe fails.
    """

    envelope = probe_envelope()

    assert envelope.payload_canonical_digest == PINNED_RECEIPT_PAYLOAD_DIGEST
    assert envelope.envelope_digest() == PINNED_ENVELOPE_DIGEST
    assert envelope.signature == PINNED_RECEIPT_SIGNATURE
    assert envelope.payload.receipt_id == PINNED_RECEIPT_ID
    assert hashlib.sha256(envelope.signed_input_bytes()).hexdigest() == (
        PINNED_RECEIPT_SIGNED_INPUT_DIGEST)

    public = encode_public_key(probe_authority_key().verification_key.public_key_bytes)
    assert public == PINNED_AUTHORITY_PUBLIC_KEY

    # It verifies against a key rebuilt from the pinned hex, not from the signer
    # object, so the check does not route through the thing it is testing.
    rebuilt = TrustedEvidenceVerificationKey(decode_public_key(public))
    assert rebuilt.verify(envelope.signed_input_bytes(), envelope.signature_bytes())

    verification = probe_reverifier().verify_signature(envelope, evaluated_at=T_MID)
    assert verification.outcome is ReceiptVerificationOutcome.VERIFIED
    assert verification.verified is True

    submission = probe_submission()
    assert submission.signature == PINNED_EVIDENCE_SIGNATURE
    assert canonical_digest(submission) == PINNED_SUBMISSION_DIGEST


@probe
def probe_rfc8032_test_vectors_reproduce_exactly():
    """Conformance to the standard, not to this implementation.

    RFC 8032 §7.1 TEST 1 and TEST 2, verbatim from the RFC. These are published
    **non-production** keys — among the best-known Ed25519 private keys in
    existence — and reproducing them proves the module implements the standard
    algorithm rather than a bespoke look-alike.
    """

    vectors = [
        (
            "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
            b"",
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        ),
        (
            "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
            "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
            bytes([0x72]),
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        ),
    ]
    for seed_hex, public_hex, message, signature_hex in vectors:
        key = TrustedEvidenceSigningKey(bytes.fromhex(seed_hex))
        assert encode_public_key(key.verification_key.public_key_bytes) == public_hex
        assert encode_signature(key.sign(message)) == signature_hex
        verifier = TrustedEvidenceVerificationKey(bytes.fromhex(public_hex))
        assert verifier.verify(message, bytes.fromhex(signature_hex))
        tampered = bytearray(bytes.fromhex(signature_hex))
        tampered[0] ^= 0x01
        assert not verifier.verify(message, bytes(tampered))


# --------------------------------------------------------------------------- #
# Every principal refusal class, demonstrated
# --------------------------------------------------------------------------- #

@probe
def probe_every_principal_refusal_class_is_demonstrable():
    """One live refusal per class. A class that cannot be reached is not a gate."""

    envelope = probe_envelope()
    demonstrated = {}

    demonstrated["anchor_not_configured"] = _refusal_of(
        envelope, anchors=DenyAllTrustAnchorDirectory())
    assert demonstrated["anchor_not_configured"] is (
        R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED)

    demonstrated["anchor_missing"] = _refusal_of(
        envelope, anchors=probe_directory(probe_producer_anchor()))
    assert demonstrated["anchor_missing"] is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING

    class AmbiguousResolver:
        def resolve(self, coordinate):
            return TrustAnchorResolution.refused(
                coordinate, R.TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS)

    demonstrated["anchor_ambiguous"] = _refusal_of(
        envelope, anchors=AmbiguousResolver())
    assert demonstrated["anchor_ambiguous"] is (
        R.TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS)

    demonstrated["key_not_yet_valid"] = _refusal_of(
        envelope, anchors=probe_directory(probe_authority_anchor(
            effective_from=datetime(2026, 12, 1, tzinfo=UTC))))
    assert demonstrated["key_not_yet_valid"] is R.TRUSTED_EVIDENCE_KEY_NOT_YET_VALID

    demonstrated["key_expired"] = _refusal_of(
        envelope, anchors=probe_directory(probe_authority_anchor(
            effective_to=datetime(2026, 2, 1, tzinfo=UTC))))
    assert demonstrated["key_expired"] is R.TRUSTED_EVIDENCE_KEY_EXPIRED

    demonstrated["key_disabled"] = _refusal_of(
        envelope, anchors=probe_directory(probe_authority_anchor(disabled=True)))
    assert demonstrated["key_disabled"] is R.TRUSTED_EVIDENCE_KEY_DISABLED

    demonstrated["key_revoked"] = _refusal_of(
        envelope, anchors=probe_directory(probe_authority_anchor(
            revocation=KeyRevocation(effective_at=T_KEY_FROM))))
    assert demonstrated["key_revoked"] is R.TRUSTED_EVIDENCE_KEY_REVOKED

    wrong_key_anchor = probe_authority_anchor(
        public_key=encode_public_key(
            probe_attacker_key().verification_key.public_key_bytes))
    demonstrated["signature_invalid"] = _refusal_of(
        envelope, anchors=probe_directory(wrong_key_anchor))
    assert demonstrated["signature_invalid"] is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID

    early = probe_envelope(
        receipt_valid_from=datetime(2026, 8, 1, tzinfo=UTC),
        receipt_valid_to=datetime(2026, 9, 1, tzinfo=UTC))
    demonstrated["receipt_not_yet_valid"] = _refusal_of(early, at=T_MID)
    assert demonstrated["receipt_not_yet_valid"] is (
        R.TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID)
    demonstrated["receipt_expired"] = _refusal_of(
        early, at=datetime(2026, 9, 1, tzinfo=UTC))
    assert demonstrated["receipt_expired"] is R.TRUSTED_EVIDENCE_RECEIPT_EXPIRED

    # Scope mismatches are reachable only through verify_bound, and every one
    # of the nine declared coordinates is exercised independently.
    for field, value, reason in (
        ("tenant_id", "a-different-value", R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
        ("assessment_context_ref", "a-different-value",
         R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH),
        ("subject_ref", "a-different-value", R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH),
        ("assessment_purpose_ref", "a-different-value",
         R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
        ("usage_scope_ref", "a-different-value",
         R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH),
        ("verification_protocol_id", "a-different-value",
         R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED),
        ("verification_protocol_version", "a-different-value",
         R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH),
        ("assessed_system_binding_digest", OTHER,
         R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH),
        ("evidence_content_digest", OTHER,
         R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH),
    ):
        got = _bound_refusal_of(envelope, field, value)
        assert got is reason, (field, got)
        demonstrated[field] = got
    assert set(ReceiptScopeExpectation.REQUIRED_COORDINATES) <= set(demonstrated)

    # E-3: a producing key can never satisfy a receipt-issuance coordinate.
    producer_shaped = TrustAnchorRecord(
        authority_id=PROBE_VERIFIER_AUTHORITY,
        key_id=PROBE_VERIFIER_KEY,
        capability=TrustAnchorCapability.EVIDENCE_PRODUCTION,
        public_key=encode_public_key(
            probe_authority_key().verification_key.public_key_bytes),
        trust_anchor_set_id=PROBE_ANCHOR_SET,
        trust_anchor_set_version="1")
    demonstrated["capability"] = _refusal_of(
        envelope, anchors=probe_directory(producer_shaped))
    assert demonstrated["capability"] is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING

    assert len(demonstrated) >= 18


@probe
def probe_the_verification_side_refusals_are_all_reachable():
    """The authority's own fail-closed surface, not the re-verifier's."""

    determination = probe_determination(
        anchors=probe_directory(probe_authority_anchor()))
    assert determination.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING in determination.refusal_reasons

    forged = probe_submission(key=probe_attacker_key())
    determination = probe_determination(submission=forged)
    assert determination.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_SIGNATURE_INVALID in determination.refusal_reasons

    revoked = build_identity(lifecycle_state=EvidenceLifecycleState.REVOKED)
    determination = probe_determination(
        submission=probe_submission(revoked),
        request=build_request(evidence=revoked))
    assert R.TRUSTED_EVIDENCE_REVOKED in determination.refusal_reasons

    determination = probe_determination(
        request=build_request(expected_tenant_id="a-different-tenant"))
    assert R.TRUSTED_EVIDENCE_TENANT_MISMATCH in determination.refusal_reasons

    determination = probe_determination(
        request=build_request(as_of=datetime(2026, 12, 1, tzinfo=UTC)))
    assert R.TRUSTED_EVIDENCE_STALE in determination.refusal_reasons

    class RefusingProtocol:
        protocol_id = TRUSTED_EVIDENCE_PROTOCOL_V1_ID
        protocol_version = TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

        def run_protocol(self, **kw):
            return ProtocolExecutionResult(
                protocol_id=self.protocol_id,
                protocol_version=self.protocol_version,
                refusal_reasons=(R.TRUSTED_EVIDENCE_INDETERMINATE,))

    authority = probe_authority(protocol=RefusingProtocol())
    determination = authority.verify(
        probe_submission(), build_request(),
        verified_at=T_VERIFIED, verifier_key_id=PROBE_VERIFIER_KEY)
    assert determination.outcome is EvidenceAdmissionOutcome.REFUSED
    assert R.TRUSTED_EVIDENCE_INDETERMINATE in determination.refusal_reasons
    assert determination.receipt_payload is None


@probe
def probe_indeterminate_is_never_a_pass_and_no_third_outcome_exists():
    assert [m.name for m in EvidenceAdmissionOutcome] == ["ADMITTED", "REFUSED"]
    assert [m.name for m in ReceiptVerificationOutcome] == ["VERIFIED", "REFUSED"]
    for banned in ("UNKNOWN", "PARTIAL", "PENDING", "BEST_EFFORT", "DEGRADED",
                   "INDETERMINATE", "WARNING", "ADVISORY"):
        assert banned not in EvidenceAdmissionOutcome.__members__
        assert banned not in ReceiptVerificationOutcome.__members__


# --------------------------------------------------------------------------- #
# Forgery, replay and substitution
# --------------------------------------------------------------------------- #

@probe
def probe_a_determination_cannot_be_manufactured():
    """§8.1.5 — no consumer may manufacture verification."""

    for token in (True, 1, "token", [], {}, object(), None, EvidenceAdmissionOutcome):
        expect_refusal(lambda t=token: EvidenceVerificationDetermination(
            outcome=EvidenceAdmissionOutcome.ADMITTED,
            verification_request_digest=CONTENT,
            verifier_authority_id=PROBE_VERIFIER_AUTHORITY,
            verifier_key_id=PROBE_VERIFIER_KEY,
            verification_protocol_id=TRUSTED_EVIDENCE_PROTOCOL_V1_ID,
            verification_protocol_version=TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION,
            verified_at=T_VERIFIED, evaluated_at=T_MID,
            cleared_stages=tuple(RECEIPT_REPORTABLE_TRUST_STAGES),
            receipt_payload=build_receipt(), issuance_token=t))


@probe
def probe_neither_receipt_verification_result_can_be_manufactured():
    coordinate = TrustAnchorCoordinate(
        authority_id=PROBE_VERIFIER_AUTHORITY, key_id=PROBE_VERIFIER_KEY,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE)
    for result_type in (SignatureOnlyVerificationResult,
                        ScopeBoundVerificationResult):
        for token in (None, True, 1, "verified", object()):
            expect_refusal(lambda r=result_type, t=token: r(
                outcome=ReceiptVerificationOutcome.VERIFIED,
                evaluated_at=T_MID, coordinate=coordinate,
                envelope_digest=CONTENT, payload_canonical_digest=CONTENT,
                verification_token=t))


@probe
def probe_there_is_no_public_route_to_signing_arbitrary_bytes():
    """The signer takes a package-minted instruction, never free bytes."""

    for token in (None, True, 1, "token", object(), []):
        expect_refusal(lambda t=token: ReceiptSigningInput(
            signed_input=b"attacker-chosen bytes",
            signer_authority_id=PROBE_VERIFIER_AUTHORITY,
            signing_key_id=PROBE_VERIFIER_KEY,
            signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
            issuance_token=t))
    signer = probe_signer()
    for bad in (b"raw bytes", "a string", None, 42, build_receipt()):
        expect_refusal(lambda b=bad: signer.sign_receipt(b))
    import ugence_trusted_evidence_authority.api as api_module
    for name in api_module.__all__:
        assert name not in ("sign", "sign_bytes", "sign_payload"), name


@probe
def probe_a_refused_determination_is_never_signed():
    determination = probe_determination(
        request=build_request(expected_tenant_id="a-different-tenant"))
    assert determination.outcome is EvidenceAdmissionOutcome.REFUSED
    assert determination.receipt_payload is None
    expect_refusal(lambda: ReceiptIssuer(signer=probe_signer()).issue(determination))


@probe
def probe_swapping_the_payload_after_signing_is_caught():
    envelope = probe_envelope()
    other = build_receipt(receipt_id="a-different-receipt")

    expect_refusal(lambda: dataclasses.replace(envelope, payload=other))
    swapped = dataclasses.replace(
        envelope, payload=other, payload_canonical_digest=canonical_digest(other))
    assert _refusal_of(swapped) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID
    expect_refusal(lambda: dataclasses.replace(
        envelope, payload_canonical_digest=OTHER))


@probe
def probe_authority_and_key_substitution_are_caught():
    envelope = probe_envelope()
    for field, value in (("signer_authority_id", "another-authority"),
                         ("signing_key_id", "another-key")):
        relabelled = dataclasses.replace(envelope, **{field: value})
        assert _refusal_of(relabelled) is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING

    relabelled = dataclasses.replace(envelope, signing_key_id="another-key")
    forged_anchor = probe_authority_anchor(key_id="another-key")
    assert _refusal_of(
        relabelled, anchors=probe_directory(forged_anchor)
    ) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


@probe
def probe_cross_domain_substitution_is_impossible():
    """An evidence signature can never verify as a receipt signature."""

    evidence = build_identity()
    payload = build_receipt()
    key = probe_authority_key()

    evidence_frame = signed_evidence_input_bytes(
        evidence=evidence,
        producer_authority_id=PROBE_VERIFIER_AUTHORITY,
        producer_key_id=PROBE_VERIFIER_KEY)
    receipt_frame = signed_receipt_input_bytes(
        payload=payload,
        signer_authority_id=PROBE_VERIFIER_AUTHORITY,
        signing_key_id=PROBE_VERIFIER_KEY)
    assert evidence_frame != receipt_frame

    public = key.verification_key
    assert public.verify(evidence_frame, key.sign(evidence_frame))
    assert not public.verify(receipt_frame, key.sign(evidence_frame))
    assert not public.verify(evidence_frame, key.sign(receipt_frame))

    domains = {
        EVIDENCE_IDENTITY_DIGEST_DOMAIN,
        EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
        TRUST_ANCHOR_RECORD_DIGEST_DOMAIN,
        SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
        SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
        TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
        TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        TRUSTED_EVIDENCE_RECEIPT_ID_DOMAIN,
    }
    assert len(domains) == 8


@probe
def probe_signature_truncation_extension_and_noncanonical_encoding_are_refused():
    envelope = probe_envelope()
    good = envelope.signature
    for bad in (good[:-2], good + "00", good.upper(), "0x" + good[2:],
                " " + good[1:], good[:-1] + "g", ""):
        expect_refusal(lambda b=bad: dataclasses.replace(envelope, signature=b))
    for bad in (None, 42, b"\x00" * 64, ["hex"], {"sig": good}):
        expect_refusal(lambda b=bad: dataclasses.replace(envelope, signature=b))

    flipped = bytearray(envelope.signature_bytes())
    flipped[0] ^= 0x01
    tampered = dataclasses.replace(envelope, signature=encode_signature(bytes(flipped)))
    assert _refusal_of(tampered) is R.TRUSTED_EVIDENCE_SIGNATURE_INVALID


@probe
def probe_algorithm_confusion_and_profile_downgrade_are_refused():
    envelope = probe_envelope()
    for bad in ("none", "None", "NONE", "hmac-sha256", "ed25519", "rsa-pss",
                TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.replace("/v1", "/v2"),
                TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.upper(), ""):
        expect_refusal(lambda b=bad: dataclasses.replace(envelope, signature_profile=b))
        expect_refusal(lambda b=bad: probe_authority_anchor(signature_profile=b))
    assert TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1.endswith("/v1")
    assert "ed25519" in TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
    assert TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1.endswith("base16-lower/v1")


@probe
def probe_a_previously_valid_receipt_stops_verifying_after_revocation():
    """§13.3 — "not silently honoured". A signature is never grandfathered."""

    envelope = probe_envelope()
    assert probe_reverifier().verify_signature(envelope, evaluated_at=T_MID).verified

    revoke_at = datetime(2026, 8, 1, tzinfo=UTC)
    revoked_directory = probe_directory(
        probe_producer_anchor(),
        probe_authority_anchor(revocation=KeyRevocation(effective_at=revoke_at)))

    still_good = probe_reverifier(revoked_directory).verify_signature(
        envelope, evaluated_at=datetime(2026, 7, 31, tzinfo=UTC))
    assert still_good.verified
    at_instant = probe_reverifier(revoked_directory).verify_signature(
        envelope, evaluated_at=revoke_at)
    assert at_instant.refusal_reason is R.TRUSTED_EVIDENCE_KEY_REVOKED
    after = probe_reverifier(revoked_directory).verify_signature(
        envelope, evaluated_at=datetime(2026, 9, 1, tzinfo=UTC))
    assert after.refusal_reason is R.TRUSTED_EVIDENCE_KEY_REVOKED

    # The refusal keeps enough typed evidence to explain itself.
    assert envelope.payload.verified_at < revoke_at
    assert after.evaluated_at >= revoke_at
    assert after.coordinate.key_id == PROBE_VERIFIER_KEY


@probe
def probe_duplicate_and_partial_trust_anchor_lookups_are_refused():
    anchor = probe_authority_anchor()
    expect_refusal(lambda: StaticTrustAnchorDirectory((anchor, anchor)))
    expect_refusal(lambda: probe_directory().with_anchor(probe_authority_anchor()))

    directory = probe_directory()
    for absent in ("latest", "default", "any", "first", "find", "search",
                   "resolve_by_authority", "get"):
        assert not hasattr(directory, absent), absent
    for coordinate in (
        TrustAnchorCoordinate(authority_id=PROBE_VERIFIER_AUTHORITY,
                              key_id="not-the-key",
                              capability=TrustAnchorCapability.RECEIPT_ISSUANCE),
        TrustAnchorCoordinate(authority_id="not-the-authority",
                              key_id=PROBE_VERIFIER_KEY,
                              capability=TrustAnchorCapability.RECEIPT_ISSUANCE),
        TrustAnchorCoordinate(authority_id=PROBE_VERIFIER_AUTHORITY,
                              key_id=PROBE_VERIFIER_KEY,
                              capability=TrustAnchorCapability.EVIDENCE_PRODUCTION),
    ):
        resolution = directory.resolve(coordinate)
        assert resolution.anchor is None
        assert resolution.refusal_reason is R.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING


@probe
def probe_the_trust_directory_is_immutable_after_construction():
    directory = probe_directory()
    for attempt in (
        lambda: setattr(directory, "_anchors", {}),
        lambda: setattr(directory, "anchors", {}),
        lambda: delattr(directory, "_anchors"),
    ):
        expect_refusal(attempt, AttributeError)
    expect_refusal(lambda: directory.anchors.clear(), AttributeError, TypeError)
    anchors = [probe_authority_anchor()]
    built = StaticTrustAnchorDirectory(anchors)
    anchors.append(probe_producer_anchor())
    assert len(built.anchors) == 1


@probe
def probe_reconstruction_routes_cannot_forge_a_verified_envelope():
    import copy
    import pickle

    envelope = probe_envelope()
    for clone in (copy.copy(envelope), copy.deepcopy(envelope),
                  pickle.loads(pickle.dumps(envelope))):
        assert clone == envelope
        assert clone.envelope_digest() == envelope.envelope_digest()
        assert probe_reverifier().verify_signature(clone, evaluated_at=T_MID).verified
        # And with no trust configured, a round-tripped envelope still refuses.
        assert not probe_reverifier(DenyAllTrustAnchorDirectory()).verify_signature(
            clone, evaluated_at=T_MID).verified

    # Doctoring a refused result in place does not change what re-verifying the
    # *envelope* says, which is the only thing a consumer may rely on.
    refused = probe_reverifier(DenyAllTrustAnchorDirectory()).verify_signature(
        envelope, evaluated_at=T_MID)
    assert not refused.verified
    try:
        object.__setattr__(refused, "outcome", ReceiptVerificationOutcome.VERIFIED)
    except Exception:
        pass
    assert not probe_reverifier(DenyAllTrustAnchorDirectory()).verify_signature(
        envelope, evaluated_at=T_MID).verified


@probe
def probe_a_duck_typed_envelope_lookalike_is_refused():
    envelope = probe_envelope()

    class Lookalike:
        envelope_schema = SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1
        payload = envelope.payload
        payload_canonical_digest = envelope.payload_canonical_digest
        signature_profile = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
        signed_input_domain = TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN
        signer_authority_id = PROBE_VERIFIER_AUTHORITY
        signing_key_id = PROBE_VERIFIER_KEY
        signature = envelope.signature
        verified = True

        def envelope_digest(self):
            return envelope.envelope_digest()

        def signed_input_bytes(self):
            return envelope.signed_input_bytes()

        def signature_bytes(self):
            return envelope.signature_bytes()

    expect_refusal(lambda: probe_reverifier().verify_signature(Lookalike(), evaluated_at=T_MID))

    class Subclass(SignedEvidenceVerificationReceipt):
        pass

    forged = Subclass(
        envelope_schema=envelope.envelope_schema,
        payload=envelope.payload,
        payload_canonical_digest=envelope.payload_canonical_digest,
        signature_profile=envelope.signature_profile,
        signed_input_domain=envelope.signed_input_domain,
        signer_authority_id=envelope.signer_authority_id,
        signing_key_id=envelope.signing_key_id,
        signature=envelope.signature)
    expect_refusal(lambda: probe_reverifier().verify_signature(forged, evaluated_at=T_MID))


@probe
def probe_naive_datetimes_are_refused_at_every_tev2_boundary():
    envelope = probe_envelope()
    naive = datetime(2026, 7, 1, 12, 0, 0)
    expect_refusal(lambda: probe_reverifier().verify_signature(envelope, evaluated_at=naive))
    expect_refusal(lambda: KeyRevocation(effective_at=naive))
    expect_refusal(lambda: probe_authority_anchor(effective_from=naive))
    expect_refusal(lambda: probe_authority_anchor(effective_to=naive))
    expect_refusal(lambda: probe_authority_anchor().lifecycle_refusal_at(naive))
    expect_refusal(lambda: probe_determination(verified_at=naive))
    expect_refusal(lambda: derive_receipt_id(
        verification_request_digest=CONTENT,
        verifier_authority_id="a", verifier_key_id="b",
        verification_protocol_id="c", verification_protocol_version="1",
        verified_at=naive))


@probe
def probe_no_tev2_entry_point_defaults_its_instant():
    """§22.10 — the evaluation instant is a parameter, never an ambient read."""

    import inspect

    for owner, method, parameter in (
        (SignedReceiptVerifier, "verify_signature", "evaluated_at"),
        (SignedReceiptVerifier, "verify_bound", "evaluated_at"),
        (EvidenceVerificationAuthority, "verify", "verified_at"),
        (TrustAnchorRecord, "lifecycle_refusal_at", "instant"),
        (KeyRevocation, "is_revoked_at", "instant"),
    ):
        signature = inspect.signature(getattr(owner, method))
        assert signature.parameters[parameter].default is inspect.Parameter.empty


@probe
def probe_private_key_material_never_escapes():
    seed = NON_PRODUCTION_PROBE_AUTHORITY_SEED
    key = TrustedEvidenceSigningKey(seed)
    envelope = probe_envelope()
    verification = probe_reverifier().verify_signature(envelope, evaluated_at=T_MID)
    record = audit_record_for_receipt_verification(
        verification, envelope, tenant_id="tenant-1")

    hexed = seed.hex()
    for rendering in (
        "%r" % (key,), "%s" % (key,),
        "%r" % (probe_signer(),),
        "%r" % (ReceiptIssuer(signer=probe_signer()),),
        canonical_bytes(envelope).decode("utf-8"),
        canonical_bytes(record).decode("utf-8"),
        canonical_bytes(probe_authority_anchor()).decode("utf-8"),
        json.dumps(dataclasses.asdict(envelope), default=str),
        "%r" % (verification,),
    ):
        assert hexed not in rendering

    assert not hasattr(envelope, "seed")
    assert not hasattr(verification, "seed")
    assert not hasattr(probe_authority_anchor(), "seed")
    assert probe_authority_anchor().public_key != hexed
    try:
        probe_signer().sign_receipt(b"not a signing input")
    except Exception as exc:
        assert hexed not in str(exc)
        assert hexed not in repr(exc)


@probe
def probe_the_envelope_authorizes_nothing():
    envelope = probe_envelope()
    verification = probe_reverifier().verify_signature(envelope, evaluated_at=T_MID)
    assert verification.verified

    for obj in (envelope, verification, envelope.payload):
        for forbidden in ("authorize", "authorizes_deployment", "allow", "permit",
                          "approve", "grant", "deploy", "execute",
                          "policy_sufficient", "is_authorized"):
            assert not hasattr(obj, forbidden), (type(obj).__name__, forbidden)

    assert EvidenceTrustStage.POLICY_SUFFICIENT not in (
        verification.established_trust_stages)
    assert EvidenceTrustStage.POLICY_SUFFICIENT not in (
        envelope.payload.declared_cleared_stages)
    assert envelope.payload.structural_status is (
        EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED)
    assert envelope.payload.authenticity_verified is False


@probe
def probe_audit_records_are_deterministic_and_carry_no_payload():
    determination = probe_determination()
    envelope = ReceiptIssuer(signer=probe_signer()).issue(determination)
    a = audit_record_for_determination(determination, tenant_id="tenant-1",
                                       envelope=envelope)
    b = audit_record_for_determination(determination, tenant_id="tenant-1",
                                       envelope=envelope)
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_digest(a) == canonical_digest(b)

    body = json.loads(canonical_bytes(a))["body"]
    for key in body:
        assert "payload" not in key or key.endswith("_digest"), key
    assert "scope" not in body
    assert "evidence" not in body

    refused = probe_determination(
        request=build_request(expected_tenant_id="another-tenant"))
    record = audit_record_for_determination(refused, tenant_id="tenant-1")
    assert record.outcome == "REFUSED"
    assert R.TRUSTED_EVIDENCE_TENANT_MISMATCH in record.refusal_reasons
    assert record.receipt_payload_digest == ""

    expect_refusal(lambda: audit_record_for_determination(
        refused, tenant_id="tenant-1", envelope=envelope))


@probe
def probe_receipt_ids_are_deterministic_and_re_verification_mints_a_new_one():
    first = probe_determination()
    again = probe_determination()
    assert first.receipt_payload.receipt_id == again.receipt_payload.receipt_id

    later = probe_determination(verified_at=T_VERIFIED + timedelta(seconds=1))
    assert later.receipt_payload.receipt_id != first.receipt_payload.receipt_id
    assert first.receipt_payload.verified_at == T_VERIFIED
    assert first.receipt_payload.receipt_id.startswith("receipt-")
    assert len(first.receipt_payload.receipt_id) == len("receipt-") + 64


# --------------------------------------------------------------------------- #
# The closure-audit corrections, probed from outside the package
# --------------------------------------------------------------------------- #

#: Points that must never become a verification key or a trust anchor. Every
#: one is either small-order — carrying no discrete-logarithm security at all —
#: or a spelling RFC 8032 §5.1.3 says must not decode.
UNTRUSTWORTHY_POINTS = (
    "01" + "00" * 31,                     # identity, canonical
    "01" + "00" * 30 + "80",              # identity, non-canonical (x=0, x_0=1)
    "ec" + "ff" * 30 + "7f",              # order 2
    "ec" + "ff" * 31,                     # order 2, non-canonical sign bit
    "00" * 32,                            # order 4
    "00" * 31 + "80",                     # order 4, sign bit set
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
    "ed" + "ff" * 30 + "7f",              # y = p
    "ee" + "ff" * 30 + "7f",              # y = p + 1
    "ff" * 32,
)


@probe
def probe_no_untrustworthy_point_can_become_a_key_or_an_anchor():
    """Closure-audit F-01/F-03, from the curated API only.

    An identity-point anchor admits a universal forgery: with A = identity the
    verification equation holds for R = [S]B and any S at all. The correction
    refuses the point where it would enter the system, so the forgery has no
    key to be mounted against.
    """

    for hexed in UNTRUSTWORTHY_POINTS:
        raw = bytes.fromhex(hexed)
        try:
            TrustedEvidenceVerificationKey(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted an untrustworthy point: {hexed}")
        expect_refusal(lambda h=hexed: TrustAnchorRecord(
            authority_id=PROBE_VERIFIER_AUTHORITY,
            key_id=PROBE_VERIFIER_KEY,
            capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
            public_key=h,
            trust_anchor_set_id=PROBE_ANCHOR_SET,
            trust_anchor_set_version="1"))

    # And a genuine key still works, so the refusals above are not vacuous.
    genuine = probe_authority_key().verification_key.public_key_bytes
    assert TrustedEvidenceVerificationKey(genuine).public_key_bytes == genuine


@probe
def probe_no_in_package_curve_arithmetic_remains():
    """The handwritten implementation is gone, checked from the outside.

    Only the module names and the absence of an ``ed25519`` submodule are
    checked here — the probe harness imports the curated API and the stdlib
    only, and asserts that of itself, so it deliberately does not reach into
    package internals to look.
    """

    import importlib

    for absent in ("ugence_trusted_evidence_authority.authority.ed25519",
                   "ugence_trusted_evidence_authority.ed25519"):
        try:
            importlib.import_module(absent)
        except ImportError:
            continue
        raise AssertionError(f"{absent} still exists")

    for banned in ("scalarmult", "point_add", "recover_x", "decode_point"):
        assert not hasattr(TrustedEvidenceVerificationKey, banned), banned
        assert not hasattr(TrustedEvidenceSigningKey, banned), banned


@probe
def probe_a_signature_only_answer_never_reports_a_scope():
    """Closure-audit F-04 — the weakening is typed, not documented in prose."""

    envelope = probe_envelope()
    unbound = probe_reverifier().verify_signature(envelope, evaluated_at=T_MID)
    bound = probe_reverifier().verify_bound(
        envelope, probe_expectation(envelope), evaluated_at=T_MID)

    assert unbound.verified and bound.verified
    assert type(unbound) is SignatureOnlyVerificationResult
    assert type(bound) is ScopeBoundVerificationResult
    assert unbound.verification_kind is ReceiptVerificationKind.SIGNATURE_ONLY
    assert bound.verification_kind is ReceiptVerificationKind.SCOPE_BOUND
    assert unbound.scope_bound is False and bound.scope_bound is True
    # Two verified answers about one envelope at one instant, never equal in
    # either direction, and only one of them claims the binding stage.
    assert unbound != bound and bound != unbound
    assert EvidenceTrustStage.CONTEXT_SYSTEM_BOUND in bound.established_trust_stages
    assert EvidenceTrustStage.CONTEXT_SYSTEM_BOUND not in (
        unbound.established_trust_stages)
    assert not hasattr(unbound, "scope_expectation_digest")
    assert bound.scope_expectation_digest == (
        probe_expectation(envelope).expectation_digest())


@probe
def probe_nothing_falsy_can_stand_in_for_a_scope_expectation():
    """Closure-audit F-05 — every value that used to skip its own check."""

    envelope = probe_envelope()

    class Lookalike:
        REQUIRED_COORDINATES = ReceiptScopeExpectation.REQUIRED_COORDINATES
        tenant_id = assessment_context_ref = subject_ref = "x"
        assessed_system_binding_digest = ""
        assessment_purpose_ref = usage_scope_ref = "x"
        evidence_content_digest = CONTENT
        verification_protocol_id = TRUSTED_EVIDENCE_PROTOCOL_V1_ID
        verification_protocol_version = TRUSTED_EVIDENCE_PROTOCOL_V1_VERSION

        def expectation_digest(self):
            return CONTENT

    for bad in (None, "", " ", False, True, 0, 1, (), [], {}, set(),
                envelope.payload.scope, Lookalike(), Lookalike,
                ReceiptScopeExpectation, object()):
        expect_refusal(lambda b=bad: probe_reverifier().verify_bound(
            envelope, b, evaluated_at=T_MID))

    # And the expectation itself admits no blank coordinate to skip.
    honest = probe_expectation(envelope)
    fields = {name: getattr(honest, name)
              for name in ReceiptScopeExpectation.REQUIRED_COORDINATES}
    for name in ReceiptScopeExpectation.REQUIRED_COORDINATES:
        for falsy in (None, "", False, 0, [], (), {}):
            if name == "assessed_system_binding_digest" and falsy == "":
                continue  # the one ratified empty spelling (§9 row 10)
            expect_refusal(lambda n=name, f=falsy: ReceiptScopeExpectation(
                **{**fields, n: f}))


@probe
def probe_a_signing_key_exposes_no_seed_by_any_route():
    """Closure-audit F-08 — the public accessor is gone, not merely undocumented."""

    seed = NON_PRODUCTION_PROBE_AUTHORITY_SEED
    key = TrustedEvidenceSigningKey(seed)
    hexed = seed.hex()

    assert not dataclasses.is_dataclass(key)
    assert not hasattr(key, "__dict__")
    for absent in ("seed", "seed_bytes", "private_bytes", "private_key",
                   "to_bytes", "export", "raw", "_seed"):
        assert not hasattr(key, absent), absent
    for rendering in ("%r" % (key,), "%s" % (key,), format(key)):
        assert hexed not in rendering
        assert rendering == "TrustedEvidenceSigningKey(<redacted>)"

    # Neither serialization nor duplication can lift it out.
    for attempt in (lambda: pickle.dumps(key),
                    lambda: copy.copy(key),
                    lambda: copy.deepcopy(key),
                    lambda: key.__reduce__()):
        try:
            attempt()
        except (TypeError, AttributeError, Exception):
            continue
        raise AssertionError("key material escaped through serialization")

    # And the key still signs, so the protection is not achieved by breaking it.
    assert len(key.sign(b"a message")) == 64


@probe
def probe_the_reverifier_recomputes_the_payload_digest_it_is_handed():
    """Closure-audit F-09 — the gate is load-bearing, shown by what it alone catches.

    An envelope whose ``__post_init__`` never ran — an unpickled one, or one a
    deserializer rebuilt field by field — carries a valid signature and a lying
    declared digest. The signing frame binds the *recomputed* digest, so the
    signature check passes and this is the only gate that refuses.
    """

    envelope = probe_envelope()
    rebuilt = object.__new__(type(envelope))
    for field in dataclasses.fields(envelope):
        object.__setattr__(rebuilt, field.name, getattr(envelope, field.name))
    object.__setattr__(rebuilt, "payload_canonical_digest", OTHER)

    assert type(rebuilt) is type(envelope)
    assert rebuilt.signed_input_bytes() == envelope.signed_input_bytes()
    anchor_key = TrustedEvidenceVerificationKey(
        bytes.fromhex(probe_authority_anchor().public_key))
    assert anchor_key.verify(
        rebuilt.signed_input_bytes(), rebuilt.signature_bytes()) is True

    result = probe_reverifier().verify_signature(rebuilt, evaluated_at=T_MID)
    assert result.outcome is ReceiptVerificationOutcome.REFUSED
    assert result.refusal_reason is R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH


def main() -> int:
    print(f"trusted-evidence adversarial probes: {_RUN} probes run")
    if _FAILURES:
        print(f"\n{len(_FAILURES)} FAILED:")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("ALL TRUSTED-EVIDENCE ADVERSARIAL PROBES PASSED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
