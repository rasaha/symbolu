"""The typed refusal vocabulary (ADR §11, E-9, DD-1).

Every member is pinned by name and value, the set is proved to contain no
success state, and the ordering is proved deterministic.
"""

from __future__ import annotations

import pytest
from ugence_trusted_evidence_authority.api import (
    TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TRUSTED_EVIDENCE_REFUSAL_REASONS,
    TrustedEvidenceRefusalReason,
)

R = TrustedEvidenceRefusalReason

#: The complete ratified TEV-1 vocabulary, in declaration order. Pinned so an
#: addition, removal, rename or reorder is a deliberate, reviewed change.
#:
#: TEV-2 **appended** to this enum and changed nothing in this list. These
#: nineteen must remain the first nineteen members, in exactly this order,
#: forever: ADR §22.13's deterministic reason ordering sorts by declaration
#: index, so re-ordering them would silently re-order a refusal sequence a
#: merged receipt was issued under.
TEV1_EXPECTED_ORDER = [
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


#: The TEV-2 additive block, in declaration order. Every member discharges a
#: ratified ADR §11 row or §13.3 property that TEV-1 named as TEV-2's own.
TEV2_EXPECTED_ORDER = [
    "TRUSTED_EVIDENCE_ENVELOPE_MALFORMED",
    "TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH",
    "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED",
    "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID",
    "TRUSTED_EVIDENCE_AUTHORITY_MISMATCH",
    "TRUSTED_EVIDENCE_KEY_ID_MISMATCH",
    "TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING",
    "TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS",
    "TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED",
    "TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH",
    "TRUSTED_EVIDENCE_KEY_NOT_YET_VALID",
    "TRUSTED_EVIDENCE_KEY_EXPIRED",
    "TRUSTED_EVIDENCE_KEY_DISABLED",
    "TRUSTED_EVIDENCE_KEY_REVOKED",
    "TRUSTED_EVIDENCE_SIGNATURE_INVALID",
    "TRUSTED_EVIDENCE_PRODUCER_UNKNOWN",
    "TRUSTED_EVIDENCE_PRODUCER_UNAUTHORIZED",
    "TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED",
    "TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH",
    "TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID",
    "TRUSTED_EVIDENCE_RECEIPT_EXPIRED",
]

EXPECTED_ORDER = TEV1_EXPECTED_ORDER + TEV2_EXPECTED_ORDER


def test_the_vocabulary_is_exactly_the_ratified_set_in_order():
    assert [m.name for m in R] == EXPECTED_ORDER
    assert len(TEV1_EXPECTED_ORDER) == 19
    assert len(TEV2_EXPECTED_ORDER) == 21
    assert len(EXPECTED_ORDER) == 40


def test_the_tev1_nineteen_are_still_the_first_nineteen_in_order():
    """Backward compatibility, asserted positionally rather than as a set.

    A set comparison would pass even if TEV-2 had interleaved its members among
    TEV-1's. Ordinal position is what ADR §22.13's ordering actually depends on,
    so that is what is pinned.
    """

    assert [m.name for m in R][:19] == TEV1_EXPECTED_ORDER
    assert [m.value for m in R][:19] == TEV1_EXPECTED_ORDER
    assert set(list(R)[:19]) == TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS


def test_the_tev2_block_is_appended_and_disjoint_from_tev1():
    assert [m.name for m in R][19:] == TEV2_EXPECTED_ORDER
    assert TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS.isdisjoint(
        TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS
    )
    assert (
        TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS | TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS
        == TRUSTED_EVIDENCE_REFUSAL_REASONS
    )


def test_only_one_refusal_namespace_exists():
    """DD-1 delegates *the* vocabulary, singular; §22.11 forbids a second.

    A parallel TEV-2 enum would be the duplicate, conflicting reason namespace
    the ADR prohibits, so the package must define exactly one refusal
    vocabulary.
    """

    import enum
    import pathlib

    import ugence_trusted_evidence_authority as pkg

    root = pathlib.Path(pkg.__file__).resolve().parent
    import ast

    refusal_enums = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and (
                "refusal" in node.name.lower() or "reason" in node.name.lower()
            ):
                refusal_enums.append(node.name)
    assert refusal_enums == ["TrustedEvidenceRefusalReason"], refusal_enums

    from ugence_trusted_evidence_authority import api

    enums = [
        n
        for n in api.__all__
        if isinstance(getattr(api, n), type) and issubclass(getattr(api, n), enum.Enum)
    ]
    reason_like = [n for n in enums if "reason" in n.lower() or "refusal" in n.lower()]
    assert reason_like == ["TrustedEvidenceRefusalReason"]


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
    #
    # A ``NOT_`` anywhere in the code negates everything after it —
    # ``KEY_NOT_YET_VALID`` and ``RECEIPT_NOT_YET_VALID`` are refusals despite
    # containing "VALID". Only the segment *before* the first ``NOT_`` is
    # scanned, which recognizes the negated forms precisely rather than either
    # blanket-banning the word or exempting the whole code.
    forbidden = {"OK", "PASS", "PASSED", "ACCEPT", "ACCEPTED", "ADMITTED",
                 "SUCCESS", "SUFFICIENT", "VERIFIED", "VALID", "AUTHENTIC",
                 "TRUSTED", "GRANTED", "ALLOWED", "APPROVED"}
    for member in R:
        suffix = member.value.removeprefix("TRUSTED_EVIDENCE_")
        unnegated = suffix.split("NOT_", 1)[0]
        words = set(w for w in unnegated.split("_") if w)
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
        # §11 row 13 — requirement-relative, owned by the consuming evaluation
        # engine under a Policy Authority requirement (§12 stage 6, §18). Not
        # TEV-2's, and still not shipped.
        "TRUSTED_EVIDENCE_UNIT_MISMATCH",
        "TRUSTED_EVIDENCE_METRIC_MISMATCH",
        # §28's ratified evidence lifecycle has no supersession arrow;
        # supersession is the *benchmark* lifecycle's (§29) and is DD-4.
        "TRUSTED_EVIDENCE_SUPERSEDED",
        # Benchmark refusals belong to BR-1/BR-2 (§16.3).
        "TRUSTED_EVIDENCE_BENCHMARK_UNKNOWN",
        "TRUSTED_EVIDENCE_BENCHMARK_REVOKED",
        # Readiness, policy sufficiency and authorization are other owners'.
        "TRUSTED_EVIDENCE_POLICY_INSUFFICIENT",
        "TRUSTED_EVIDENCE_NOT_AUTHORIZED",
        "TRUSTED_EVIDENCE_DEPLOYMENT_DENIED",
    ],
)
def test_codes_for_checks_this_package_cannot_perform_are_absent(absent):
    """A code advertises a check; this package ships none it cannot reach."""

    assert absent not in R.__members__
    assert absent not in {m.value for m in R}


@pytest.mark.parametrize(
    "code",
    [
        "TRUSTED_EVIDENCE_SIGNATURE_INVALID",
        "TRUSTED_EVIDENCE_KEY_REVOKED",
        "TRUSTED_EVIDENCE_KEY_EXPIRED",
        "TRUSTED_EVIDENCE_KEY_NOT_YET_VALID",
        "TRUSTED_EVIDENCE_PRODUCER_UNKNOWN",
        "TRUSTED_EVIDENCE_PRODUCER_UNAUTHORIZED",
        "TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING",
        "TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED",
    ],
)
def test_the_adr_11_conditions_tev1_deferred_now_exist(code):
    """TEV-1 named these "**TEV-2.**"; TEV-2 exists, so they do (§11 rows 4-6)."""

    assert code in R.__members__
    assert R[code] in TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS


def test_a_refusal_reason_is_a_plain_string_enum_with_no_authority_semantics():
    member = R.TRUSTED_EVIDENCE_TENANT_MISMATCH
    assert isinstance(member, str)
    assert member == "TRUSTED_EVIDENCE_TENANT_MISMATCH"
    # It carries no verdict object, no signature, no authority handle.
    assert not hasattr(member, "authority")
    assert not hasattr(member, "signature")
