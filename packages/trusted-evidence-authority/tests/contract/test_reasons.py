"""The typed refusal vocabulary (ADR §11, E-9, DD-1).

Every member is pinned by name and value, the set is proved to contain no
success state, and the ordering is proved deterministic.
"""

from __future__ import annotations

import pytest
from ugence_trusted_evidence_authority.api import (
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TrustedEvidenceRefusalReason,
)

R = TrustedEvidenceRefusalReason

#: The complete ratified TEV-1 vocabulary, in declaration order. Pinned so an
#: addition, removal, rename or reorder is a deliberate, reviewed change.
EXPECTED_ORDER = [
    "TRUSTED_EVIDENCE_MISSING",
    "TRUSTED_EVIDENCE_MALFORMED_CONTRACT",
    "TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED",
    "TRUSTED_EVIDENCE_TYPE_UNSUPPORTED",
    "TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING",
    "TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH",
    "TRUSTED_EVIDENCE_TENANT_MISMATCH",
    "TRUSTED_EVIDENCE_CONTEXT_MISMATCH",
    "TRUSTED_EVIDENCE_SUBJECT_MISMATCH",
    "TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH",
    "TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH",
    "TRUSTED_EVIDENCE_PROVENANCE_MISMATCH",
    "TRUSTED_EVIDENCE_NOT_YET_VALID",
    "TRUSTED_EVIDENCE_STALE",
    "TRUSTED_EVIDENCE_REVOKED",
    "TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION",
    "TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED",
    "TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE",
    "TRUSTED_EVIDENCE_INDETERMINATE",
]


def test_the_vocabulary_is_exactly_the_ratified_set_in_order():
    assert [m.name for m in R] == EXPECTED_ORDER
    assert len(EXPECTED_ORDER) == 19


def test_every_member_name_equals_its_value():
    for member in R:
        assert member.name == member.value


def test_every_name_and_value_is_unique():
    names = [m.name for m in R]
    values = [m.value for m in R]
    assert len(set(names)) == len(names)
    assert len(set(values)) == len(values)


def test_every_member_carries_the_neutral_namespace_prefix():
    for member in R:
        assert member.value.startswith("TRUSTED_EVIDENCE_")


def test_no_member_is_milestone_branded():
    """No ``TEV1_``/``TEV_1_``/``V1_`` opaque code (task §10)."""

    for member in R:
        assert "TEV" not in member.value
        assert "_V1" not in member.value


def test_there_are_no_aliases_or_deprecated_spellings():
    """Two names mapping to one value would break §22.11's stability rule."""

    assert len(set(R.__members__)) == len({m.value for m in R})
    assert len(R.__members__) == len(list(R))


def test_the_declared_frozenset_is_the_whole_enum():
    assert TRUSTED_EVIDENCE_REFUSAL_REASONS == frozenset(R)
    assert isinstance(TRUSTED_EVIDENCE_REFUSAL_REASONS, frozenset)


def test_every_member_is_a_refusal_there_is_no_success_state():
    """Structurally: the vocabulary *is* the refusal set."""

    assert set(R) == set(TRUSTED_EVIDENCE_REFUSAL_REASONS)
    # Compared per underscore-delimited word, so "REVOKED" is not read as "OK".
    # ``NOT_YET_VALID`` is a refusal despite containing "VALID", so the negated
    # forms are recognized rather than blanket-banning the word.
    forbidden = {"OK", "PASS", "PASSED", "ACCEPT", "ACCEPTED", "ADMITTED",
                 "SUCCESS", "SUFFICIENT", "VERIFIED", "VALID", "AUTHENTIC"}
    for member in R:
        suffix = member.value.removeprefix("TRUSTED_EVIDENCE_")
        if suffix.startswith("NOT_"):
            continue  # an explicitly negated condition is a refusal by construction
        words = set(suffix.split("_"))
        assert not (words & forbidden), (member.value, sorted(words & forbidden))


def test_indeterminate_is_a_refusal_never_a_pass():
    assert R.TRUSTED_EVIDENCE_INDETERMINATE in TRUSTED_EVIDENCE_REFUSAL_REASONS
    assert "INDETERMINATE" in [m.value.rsplit("_", 1)[-1] for m in R]
    doc = R.__doc__ or ""
    assert "refusal" in doc.lower()


def test_verification_unavailability_is_a_refusal_not_a_neutral_outcome():
    for member in (
        R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED,
        R.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE,
        R.TRUSTED_EVIDENCE_INDETERMINATE,
    ):
        assert member in TRUSTED_EVIDENCE_REFUSAL_REASONS


def test_the_ordering_is_deterministic_and_usable_as_a_sort_key():
    order = list(R)
    shuffled = [
        R.TRUSTED_EVIDENCE_INDETERMINATE,
        R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
        R.TRUSTED_EVIDENCE_MISSING,
    ]
    assert sorted(shuffled, key=order.index) == [
        R.TRUSTED_EVIDENCE_MISSING,
        R.TRUSTED_EVIDENCE_TENANT_MISMATCH,
        R.TRUSTED_EVIDENCE_INDETERMINATE,
    ]
    # Stable across repeated evaluation.
    assert [m.name for m in R] == [m.name for m in R]


@pytest.mark.parametrize(
    "absent",
    [
        "TRUSTED_EVIDENCE_KEY_UNKNOWN",
        "TRUSTED_EVIDENCE_KEY_REVOKED",
        "TRUSTED_EVIDENCE_KEY_EXPIRED",
        "TRUSTED_EVIDENCE_SIGNATURE_INVALID",
        "TRUSTED_EVIDENCE_PRODUCER_UNKNOWN",
        "TRUSTED_EVIDENCE_PRODUCER_UNAUTHORIZED",
        "TRUSTED_EVIDENCE_UNIT_MISMATCH",
        "TRUSTED_EVIDENCE_METRIC_MISMATCH",
        "TRUSTED_EVIDENCE_SUPERSEDED",
    ],
)
def test_codes_for_checks_tev1_cannot_perform_are_absent(absent):
    """A code advertises a check; TEV-1 ships none it cannot reach."""

    assert absent not in R.__members__
    assert absent not in {m.value for m in R}


def test_a_refusal_reason_is_a_plain_string_enum_with_no_authority_semantics():
    member = R.TRUSTED_EVIDENCE_TENANT_MISMATCH
    assert isinstance(member, str)
    assert member == "TRUSTED_EVIDENCE_TENANT_MISMATCH"
    # It carries no verdict object, no signature, no authority handle.
    assert not hasattr(member, "authority")
    assert not hasattr(member, "signature")
