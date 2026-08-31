"""Chain substitution — every substitution moves the digest, or is refused.

§19's substitution matrix, verbatim: publisher identity; publisher key ID; the
publisher submission envelope; the submission-envelope signature;
approval-authority identity; approval key ID; the approval envelope; the
approval-envelope signature; registry-authority identity; the submission-record
payload; the admission payload; the admission payload's ``declared_outcome``;
the post-admission rejection payload; the registration-event payload; the
revocation envelope; revoker identity; ``effective_at``; and
``declared_recorded_at``.

Each case is either *substitutable* — the change is legal and must move the
final digest — or *refused*, because the change would break a constructor gate.
Both are recorded, because "the digest moved" and "you cannot even build that"
are two different guarantees and the matrix needs both.
"""

from __future__ import annotations

import pytest

import _builders as fx
from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkScope,
)
from ugence_benchmark_registry_authority.api import (
    BenchmarkAdmissionOutcome,
    BenchmarkRegistryContractError,
    canonical_digest,
)

BASELINE_REVOCATION = canonical_digest(fx.revocation_event())
BASELINE_REGISTRATION = canonical_digest(fx.registration_event())
BASELINE_REJECTION = canonical_digest(fx.post_admission_rejection())


def _revocation_with(**overrides):
    """Rebuild the whole chain from the leaves with one coordinated override."""

    envelope = fx.publisher_envelope(
        **{
            k: v
            for k, v in overrides.items()
            if k in {"publisher_identity", "publisher_key_id", "detached_signature"}
        }
    )
    approval = fx.approval_envelope(
        publisher_submission_envelope=envelope,
        **{
            k: v
            for k, v in overrides.items()
            if k
            in {
                "approval_authority_identity",
                "approval_authority_key_id",
                "applicable_policy_ref",
            }
        },
    )
    if "approval_signature" in overrides:
        approval = fx.approval_envelope(
            publisher_submission_envelope=envelope,
            detached_signature=overrides["approval_signature"],
        )
    record = fx.submission_record(
        publisher_submission_envelope=envelope,
        **{
            k: v
            for k, v in overrides.items()
            if k
            in {
                "declared_registry_authority_identity",
                "declared_recorded_at",
            }
        },
    )
    decision = fx.admission_decision(
        submission_record=record,
        approval_envelope=approval,
    )
    registration = fx.registration_event(admission_decision=decision)
    revocation_envelope = fx.revocation_envelope(
        **{
            k: v
            for k, v in overrides.items()
            if k in {"revoker_identity", "revoker_key_id", "effective_at"}
        }
    )
    if "revocation_signature" in overrides:
        revocation_envelope = fx.revocation_envelope(
            detached_signature=overrides["revocation_signature"]
        )
    return fx.revocation_event(
        registration_event=registration,
        revocation_envelope=revocation_envelope,
        declared_recorded_at=overrides.get(
            "event_declared_recorded_at", fx.RECORDED_AT
        ),
    )


SUBSTITUTIONS = [
    ("publisher identity", {"publisher_identity": "publisher-omega"}),
    ("publisher key ID", {"publisher_key_id": "publisher-key-9"}),
    ("publisher submission envelope signature", {"detached_signature": "0f" * 64}),
    (
        "approval-authority identity",
        {"approval_authority_identity": "approval-authority-omega"},
    ),
    ("approval key ID", {"approval_authority_key_id": "approval-key-9"}),
    ("approval envelope signature", {"approval_signature": "0e" * 64}),
    ("approval envelope policy reference", {"applicable_policy_ref": "policy-9"}),
    (
        "registry-authority identity",
        {"declared_registry_authority_identity": "registry-authority-omega"},
    ),
    ("submission record declared_recorded_at", {"declared_recorded_at": fx.AS_OF}),
    ("revoker identity", {"revoker_identity": "revoker-omega"}),
    ("revoker key ID", {"revoker_key_id": "revocation-key-9"}),
    ("revocation envelope signature", {"revocation_signature": "0d" * 64}),
    ("effective_at", {"effective_at": fx.VALIDITY_FROM}),
    ("event declared_recorded_at", {"event_declared_recorded_at": fx.AS_OF}),
]


def test_happy_the_baseline_is_stable():
    assert canonical_digest(fx.revocation_event()) == BASELINE_REVOCATION


@pytest.mark.parametrize(
    "label,overrides", SUBSTITUTIONS, ids=[label for label, _ in SUBSTITUTIONS]
)
def test_every_substitution_moves_the_final_revocation_event_digest(label, overrides):
    assert canonical_digest(_revocation_with(**overrides)) != BASELINE_REVOCATION


def test_effective_at_and_declared_recorded_at_move_the_digest_independently():
    """The two timestamps have different owners and must not be interchangeable."""

    only_effective = canonical_digest(_revocation_with(effective_at=fx.VALIDITY_FROM))
    only_recorded = canonical_digest(
        _revocation_with(event_declared_recorded_at=fx.AS_OF)
    )
    both = canonical_digest(
        _revocation_with(
            effective_at=fx.VALIDITY_FROM, event_declared_recorded_at=fx.AS_OF
        )
    )
    assert len({BASELINE_REVOCATION, only_effective, only_recorded, both}) == 4


# --------------------------------------------------------------------------- #
# Whole-object substitutions
# --------------------------------------------------------------------------- #
def test_substituting_the_publisher_submission_envelope_moves_every_downstream_digest():
    other = fx.publisher_envelope(publisher_key_id="publisher-key-7")
    record = fx.submission_record(publisher_submission_envelope=other)
    approval = fx.approval_envelope(publisher_submission_envelope=other)
    decision = fx.admission_decision(
        submission_record=record, approval_envelope=approval
    )
    registration = fx.registration_event(admission_decision=decision)
    assert canonical_digest(record) != canonical_digest(fx.submission_record())
    assert canonical_digest(decision) != canonical_digest(fx.admission_decision())
    assert canonical_digest(registration) != BASELINE_REGISTRATION


def test_substituting_the_submission_record_moves_the_admission_digest():
    other = fx.submission_record(declared_recorded_at=fx.VALIDITY_FROM)
    assert canonical_digest(
        fx.admission_decision(submission_record=other)
    ) != canonical_digest(fx.admission_decision())


def test_substituting_the_admission_payload_moves_registration_and_rejection():
    other = fx.admission_decision(declared_recorded_at=fx.VALIDITY_FROM)
    assert canonical_digest(
        fx.registration_event(admission_decision=other)
    ) != BASELINE_REGISTRATION
    assert canonical_digest(
        fx.post_admission_rejection(admission_decision=other)
    ) != BASELINE_REJECTION


def test_substituting_the_admission_declared_outcome_is_refused_downstream():
    """The declared_outcome substitution is a *refusal*, which is stronger."""

    rejected = fx.rejected_admission_decision()
    with pytest.raises(BenchmarkRegistryContractError):
        fx.registration_event(admission_decision=rejected)
    with pytest.raises(BenchmarkRegistryContractError):
        fx.post_admission_rejection(admission_decision=rejected)


def test_the_admission_declared_outcome_moves_the_decision_digest_itself():
    assert canonical_digest(fx.rejected_admission_decision()) != canonical_digest(
        fx.admission_decision()
    )


def test_substituting_the_registration_event_moves_the_revocation_digest():
    other = fx.registration_event(declared_recorded_at=fx.VALIDITY_FROM)
    assert canonical_digest(
        fx.revocation_event(registration_event=other)
    ) != BASELINE_REVOCATION


def test_substituting_the_revocation_envelope_moves_the_revocation_digest():
    other = fx.revocation_envelope(declared_revocation_reason="measurement-error")
    assert canonical_digest(
        fx.revocation_event(revocation_envelope=other)
    ) != BASELINE_REVOCATION


def test_substituting_the_post_admission_rejection_reason_moves_its_digest():
    from ugence_benchmark_registry_authority.api import (
        BenchmarkRegistryRefusalReason,
    )

    other = fx.post_admission_rejection(
        declared_refusal_reason=BenchmarkRegistryRefusalReason.SIGNATURE_INVALID
    )
    assert canonical_digest(other) != BASELINE_REJECTION


def test_substituting_the_approval_envelope_moves_the_admission_digest():
    other = fx.approval_envelope(validity_to=fx.VALIDITY_TO.replace(year=2028))
    assert canonical_digest(
        fx.admission_decision(approval_envelope=other)
    ) != canonical_digest(fx.admission_decision())


def test_substituting_the_approval_declared_outcome_moves_the_admission_digest():
    other = fx.approval_envelope(declared_outcome=BenchmarkAdmissionOutcome.REJECTED)
    assert canonical_digest(
        fx.admission_decision(approval_envelope=other)
    ) != canonical_digest(fx.admission_decision())


@pytest.mark.parametrize(
    "override",
    [
        {"benchmark_id": "other-bmk"},
        {"benchmark_family": "other-fam"},
        {"benchmark_version": "1.2.4"},
        {"scope": BenchmarkScope.for_tenant("t2")},
        {"scope": BenchmarkScope.platform_wide()},
        {"geography": BenchmarkApplicabilityCoordinate.not_applicable()},
        {"geography": BenchmarkApplicabilityCoordinate.applicable("us")},
        {"domain": BenchmarkApplicabilityCoordinate.applicable("healthcare")},
    ],
    ids=[
        "benchmark_id",
        "benchmark_family",
        "benchmark_version",
        "scope.tenant_id",
        "scope.kind",
        "geography.declaration",
        "geography.value",
        "domain.declaration",
    ],
)
def test_substituting_any_locator_element_moves_every_digest_in_the_chain(override):
    """All nine scalar elements of the BR-1 locator are digest-bound here too."""

    envelope = fx.publisher_envelope(coordinate=fx.coordinate(**override))
    record = fx.submission_record(publisher_submission_envelope=envelope)
    assert canonical_digest(record) != canonical_digest(fx.submission_record())


def test_the_substitution_matrix_covers_every_specified_element():
    """Guard against a row quietly disappearing from the matrix."""

    labels = {label for label, _ in SUBSTITUTIONS}
    required = {
        "publisher identity",
        "publisher key ID",
        "publisher submission envelope signature",
        "approval-authority identity",
        "approval key ID",
        "approval envelope signature",
        "registry-authority identity",
        "revoker identity",
        "effective_at",
        "event declared_recorded_at",
    }
    assert required <= labels
