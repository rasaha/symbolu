"""``AssessedSystemBinding`` canonicalization — equal bindings, equal bytes.

The correction these tests pin: two timezone-aware datetimes naming the **same
instant** are equal in Python and hash alike, so two bindings differing only in
the offset their instants were written with are the *same* binding. Before the
fix they nonetheless produced three different canonical byte sequences and three
different digests, silently forking the identity fingerprint the whole platform
compares on.

The invariant asserted throughout::

    if binding_a == binding_b:
        assert binding_a.canonical_bytes() == binding_b.canonical_bytes()
        assert binding_a.canonical_digest() == binding_b.canonical_digest()

Nothing here relaxes a rule. Naive datetimes stay rejected — a value with no
offset names no instant and UTC is never assumed for it — genuinely different
instants stay distinct, and no legacy-digest fallback, dual acceptance rule or
alias exists. This is one deterministic canonicalization, not a second protocol.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from ugence_governance_contracts import api
from ugence_governance_contracts.contracts import system_identity
from ugence_governance_contracts.contracts.system_identity import (
    AssessedSystemBinding,
    SystemIdentityContractError,
)

CTX_DIGEST = "baba834176cee0f39f8dc6e4a29d7c5afe1861e6b410c3ed9acb538a795d2fdf"
CFG_DIGEST = "b8d582270bcab6ca49bc8ef3b9916fa6f77fd84a35be1c1d884eec31746a29a6"
MANIFEST_DIGEST = "c" * 64

#: The three representations named in the finding. One instant, three offsets.
UTC = datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone.utc)
PLUS_0530 = datetime(2026, 8, 17, 15, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
MINUS_0400 = datetime(2026, 8, 17, 6, 0, 0, tzinfo=timezone(timedelta(hours=-4)))

#: A second instant, for the effective_to bound. 2026-08-18T00:00:00Z.
END_UTC = datetime(2026, 8, 18, 0, 0, 0, tzinfo=timezone.utc)
END_PLUS_0930 = datetime(
    2026, 8, 18, 9, 30, 0, tzinfo=timezone(timedelta(hours=9, minutes=30))
)
END_MINUS_1100 = datetime(2026, 8, 17, 13, 0, 0, tzinfo=timezone(timedelta(hours=-11)))


def binding(**overrides) -> AssessedSystemBinding:
    base = dict(
        binding_id="bind-1",
        tenant_id="t1",
        subject_id="a1",
        context_id="ctx1",
        context_digest=CTX_DIGEST,
        system_id="agent-sys-1",
        system_version="1.4.2",
        configuration_id="cfg-prod-a",
        configuration_digest=CFG_DIGEST,
    )
    base.update(overrides)
    return AssessedSystemBinding(**base)


def assert_indistinguishable(*bindings: AssessedSystemBinding) -> None:
    """Equality, hash, canonical bytes and digest all agree across the group."""

    first = bindings[0]
    for other in bindings[1:]:
        assert first == other
        assert hash(first) == hash(other)
        assert first.canonical_bytes() == other.canonical_bytes()
        assert first.canonical_digest() == other.canonical_digest()


# --------------------------------------------------------------------------- #
# 1. The previously observed failing example
# --------------------------------------------------------------------------- #
def test_the_previously_observed_failing_example_now_canonicalizes_identically():
    """The exact finding: equal bindings, three digests. Now one digest."""

    a, b, c = binding(effective_from=UTC), binding(effective_from=PLUS_0530), binding(
        effective_from=MINUS_0400
    )
    # The premise of the defect — these really are the same instant and compare
    # equal — is asserted, not assumed.
    assert UTC == PLUS_0530 == MINUS_0400
    assert a == b == c
    assert_indistinguishable(a, b, c)
    assert len({x.canonical_digest() for x in (a, b, c)}) == 1


def test_equal_bindings_have_equal_canonical_bytes_and_digests():
    for kwargs in (
        {"effective_from": UTC},
        {"effective_to": END_UTC},
        {"effective_from": UTC, "effective_to": END_UTC},
    ):
        left = binding(**kwargs)
        right = binding(**kwargs)
        assert_indistinguishable(left, right)


# --------------------------------------------------------------------------- #
# 2. Positive, negative and non-hour offsets, per datetime field
# --------------------------------------------------------------------------- #
def test_utc_versus_positive_offset_on_effective_from():
    assert_indistinguishable(
        binding(effective_from=UTC),
        binding(effective_from=datetime(2026, 8, 17, 19, 0, tzinfo=timezone(timedelta(hours=9)))),
    )


def test_utc_versus_negative_offset_on_effective_from():
    assert_indistinguishable(binding(effective_from=UTC), binding(effective_from=MINUS_0400))


def test_non_hour_offset_plus_0530_on_effective_from():
    assert_indistinguishable(binding(effective_from=UTC), binding(effective_from=PLUS_0530))


def test_non_hour_offsets_of_every_shape():
    """Half-hour, three-quarter-hour and second-level offsets all normalize."""

    equivalents = [
        UTC,
        PLUS_0530,
        datetime(2026, 8, 17, 15, 45, tzinfo=timezone(timedelta(hours=5, minutes=45))),
        datetime(2026, 8, 17, 22, 0, tzinfo=timezone(timedelta(hours=12))),
        datetime(2026, 8, 16, 22, 0, tzinfo=timezone(timedelta(hours=-12))),
        datetime(2026, 8, 17, 10, 0, 42, tzinfo=timezone(timedelta(seconds=42))),
    ]
    assert_indistinguishable(*[binding(effective_from=e) for e in equivalents])


def test_utc_versus_offsets_on_effective_to():
    assert_indistinguishable(
        binding(effective_to=END_UTC),
        binding(effective_to=END_PLUS_0930),
        binding(effective_to=END_MINUS_1100),
    )


def test_both_bounds_together_normalize_independently():
    assert_indistinguishable(
        binding(effective_from=UTC, effective_to=END_UTC),
        binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100),
        binding(effective_from=MINUS_0400, effective_to=END_PLUS_0930),
    )


def test_every_datetime_field_of_the_binding_is_covered_by_these_tests():
    """A datetime field added later fails here until it is covered above.

    ``effective_from`` and ``effective_to`` are the complete set today; the guard
    exists so the normalization proof cannot silently fall behind the contract.
    """

    import typing

    hints = typing.get_type_hints(AssessedSystemBinding)
    datetime_fields = {
        f.name
        for f in dataclasses.fields(AssessedSystemBinding)
        if datetime in typing.get_args(hints[f.name]) or hints[f.name] is datetime
    }
    assert datetime_fields == {"effective_from", "effective_to"}


def test_normalization_reaches_every_datetime_in_the_payload():
    """Structural, not field-by-field: nothing datetime-shaped survives un-normalized."""

    payload = system_identity._canonical_payload(
        binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100)
    )
    instants = [v for v in payload.values() if isinstance(v, datetime)]
    assert len(instants) == 2
    for value in instants:
        assert value.utcoffset() == timedelta(0)
        assert value.tzinfo is timezone.utc


# --------------------------------------------------------------------------- #
# 3. Open-start / open-end cases
# --------------------------------------------------------------------------- #
def test_open_start_and_open_end_cases_normalize():
    # Open start (effective_from absent), offset-written end.
    assert_indistinguishable(
        binding(effective_to=END_UTC), binding(effective_to=END_PLUS_0930)
    )
    # Open end (effective_to absent), offset-written start.
    assert_indistinguishable(
        binding(effective_from=UTC), binding(effective_from=PLUS_0530)
    )


def test_a_fully_open_binding_carries_no_instant_and_is_stable():
    left, right = binding(), binding()
    assert_indistinguishable(left, right)
    payload = json.loads(left.canonical_bytes())
    assert payload["effective_from"] is None and payload["effective_to"] is None


def test_an_open_bound_is_not_the_same_binding_as_a_closed_one():
    """Absence must never collapse into a normalized instant."""

    assert binding().canonical_digest() != binding(effective_from=UTC).canonical_digest()
    assert (
        binding(effective_from=UTC).canonical_digest()
        != binding(effective_from=UTC, effective_to=END_UTC).canonical_digest()
    )


# --------------------------------------------------------------------------- #
# 4. Microsecond precision
# --------------------------------------------------------------------------- #
def test_microsecond_precision_survives_normalization():
    micro_utc = datetime(2026, 8, 17, 10, 0, 0, 123456, tzinfo=timezone.utc)
    micro_ist = datetime(
        2026, 8, 17, 15, 30, 0, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    assert micro_utc == micro_ist
    assert_indistinguishable(
        binding(effective_from=micro_utc), binding(effective_from=micro_ist)
    )
    assert "10:00:00.123456+00:00" in binding(effective_from=micro_ist).canonical_bytes().decode()


def test_a_one_microsecond_difference_still_changes_the_digest():
    a = binding(effective_from=datetime(2026, 8, 17, 10, 0, 0, 123456, tzinfo=timezone.utc))
    b = binding(effective_from=datetime(2026, 8, 17, 10, 0, 0, 123457, tzinfo=timezone.utc))
    assert a != b
    assert a.canonical_bytes() != b.canonical_bytes()
    assert a.canonical_digest() != b.canonical_digest()


def test_a_microsecond_difference_hidden_behind_an_offset_is_still_detected():
    a = binding(effective_from=datetime(2026, 8, 17, 10, 0, 0, 1, tzinfo=timezone.utc))
    b = binding(
        effective_from=datetime(
            2026, 8, 17, 15, 30, 0, 2, tzinfo=timezone(timedelta(hours=5, minutes=30))
        )
    )
    assert a.canonical_digest() != b.canonical_digest()


# --------------------------------------------------------------------------- #
# 5. Different instants stay different
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "other",
    [
        datetime(2026, 8, 17, 10, 0, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 17, 11, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 17, 10, 0, 0, tzinfo=timezone(timedelta(hours=1))),
        datetime(2026, 8, 18, 10, 0, 0, tzinfo=timezone.utc),
    ],
)
def test_a_genuinely_different_instant_changes_bytes_and_digest(other):
    a, b = binding(effective_from=UTC), binding(effective_from=other)
    assert a != b
    assert a.canonical_bytes() != b.canonical_bytes()
    assert a.canonical_digest() != b.canonical_digest()


def test_non_datetime_coordinates_still_dominate_the_digest():
    """Normalization changed nothing about replay detection on other fields."""

    reference = binding(effective_from=UTC).canonical_digest()
    for kwargs in (
        {"tenant_id": "other"},
        {"subject_id": "other"},
        {"context_id": "other"},
        {"system_id": "other"},
        {"system_version": "2"},
        {"configuration_id": "other"},
        {"configuration_digest": "d" * 64},
        {"deployment_environment_ref": "env-b"},
        {"canonical_subject_context_ref": "subj-token"},
        {"system_manifest_ref": "m", "system_manifest_digest": MANIFEST_DIGEST},
    ):
        assert binding(effective_from=UTC, **kwargs).canonical_digest() != reference


# --------------------------------------------------------------------------- #
# 6. Naive and non-datetime rejection — no silent UTC assignment
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field", ["effective_from", "effective_to"])
def test_a_naive_datetime_is_rejected_at_construction(field):
    with pytest.raises(SystemIdentityContractError, match="timezone-aware"):
        binding(**{field: datetime(2026, 8, 17, 10, 0, 0)})


@pytest.mark.parametrize("field", ["effective_from", "effective_to"])
def test_a_non_datetime_is_rejected_at_construction(field):
    for value in ("2026-08-17T10:00:00+00:00", 1755424800, 1755424800.0, object()):
        with pytest.raises(SystemIdentityContractError, match="must be a datetime"):
            binding(**{field: value})


@pytest.mark.parametrize("field", ["effective_from", "effective_to"])
def test_canonicalization_itself_rejects_a_naive_datetime(field):
    """Defense in depth: the frozen guard can be bypassed; the serializer cannot.

    A naive value forced past ``__post_init__`` must still be refused rather than
    silently read as UTC — otherwise a smuggled value would mint a digest for an
    instant nobody named.
    """

    smuggled = binding(effective_from=UTC)
    object.__setattr__(smuggled, field, datetime(2026, 8, 17, 10, 0, 0))
    with pytest.raises(SystemIdentityContractError, match="timezone-aware"):
        smuggled.canonical_bytes()
    with pytest.raises(SystemIdentityContractError, match="timezone-aware"):
        smuggled.canonical_digest()


def test_canonicalization_itself_rejects_a_non_datetime_instant():
    smuggled = binding(effective_from=UTC)
    object.__setattr__(smuggled, "effective_from", "2026-08-17T10:00:00+00:00")
    # A string is serialized as a string, never coerced into an instant: the
    # smuggled value cannot impersonate the datetime it spells.
    assert smuggled.canonical_digest() != binding(effective_from=UTC).canonical_digest()
    with pytest.raises(SystemIdentityContractError, match="must be a datetime"):
        system_identity._to_utc("2026-08-17T10:00:00+00:00", "x")


def test_a_naive_value_is_never_assigned_utc():
    """The stored field is left exactly as the caller gave it — or refused."""

    naive = datetime(2026, 8, 17, 10, 0, 0)
    with pytest.raises(SystemIdentityContractError):
        binding(effective_from=naive)
    assert naive.tzinfo is None  # untouched; no in-place UTC stamping


# --------------------------------------------------------------------------- #
# 7. Determinism — repeated calls, field order, no hidden input
# --------------------------------------------------------------------------- #
def test_repeated_calls_are_identical():
    b = binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100)
    assert len({b.canonical_bytes() for _ in range(25)}) == 1
    assert len({b.canonical_digest() for _ in range(25)}) == 1


def test_canonicalization_does_not_mutate_the_binding():
    b = binding(effective_from=PLUS_0530)
    before = dataclasses.asdict(b)
    b.canonical_bytes()
    b.canonical_digest()
    assert dataclasses.asdict(b) == before
    # The stored instant keeps its original offset; only the serialization is UTC.
    assert b.effective_from.utcoffset() == timedelta(hours=5, minutes=30)


def test_field_order_is_deterministic_and_keyword_order_independent():
    """Sorted keys, so constructor keyword order cannot move a byte."""

    forwards = AssessedSystemBinding(
        binding_id="bind-1",
        tenant_id="t1",
        subject_id="a1",
        context_id="ctx1",
        context_digest=CTX_DIGEST,
        system_id="agent-sys-1",
        system_version="1.4.2",
        configuration_id="cfg-prod-a",
        configuration_digest=CFG_DIGEST,
        effective_from=PLUS_0530,
    )
    backwards = AssessedSystemBinding(
        effective_from=UTC,
        configuration_digest=CFG_DIGEST,
        configuration_id="cfg-prod-a",
        system_version="1.4.2",
        system_id="agent-sys-1",
        context_digest=CTX_DIGEST,
        context_id="ctx1",
        subject_id="a1",
        tenant_id="t1",
        binding_id="bind-1",
    )
    assert_indistinguishable(forwards, backwards)
    keys = list(json.loads(forwards.canonical_bytes()))
    assert keys == sorted(keys)
    assert set(keys) == {f.name for f in dataclasses.fields(AssessedSystemBinding)}


def test_canonicalization_reads_no_system_clock_locale_or_environment():
    """AST guard over the module: normalization is pure arithmetic.

    ``astimezone`` is only safe with an **explicit** target — the zero-argument
    form infers the machine's local timezone. That distinction is asserted
    structurally so it cannot regress into an environment-dependent digest.
    """

    source = pathlib.Path(system_identity.__file__).read_text()
    tree = ast.parse(source)
    banned = {"now", "utcnow", "today", "time", "monotonic", "localtime", "getenv"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert name not in banned, f"canonicalization calls {name}()"
            if name == "astimezone":
                assert node.args, "astimezone() with no argument infers the local timezone"
        if isinstance(node, ast.Import):
            roots = {a.name.split(".")[0] for a in node.names}
            assert not roots & {"os", "time", "random", "locale", "zoneinfo"}, roots
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            root = node.module.split(".")[0]
            assert root not in {"os", "time", "random", "locale", "zoneinfo"}, root


# --------------------------------------------------------------------------- #
# 8. Independent digest computation — not the helper under test
# --------------------------------------------------------------------------- #
def test_digest_recomputed_from_hand_built_canonical_bytes():
    """The expected value is built by hand, from a literal payload.

    Neither :func:`_canonical_bytes` nor :func:`_canonical_payload` participates:
    the JSON below is written out explicitly, hashed with ``hashlib`` directly,
    and only then compared against what the contract produces. So this test
    fails if the helper is wrong, rather than agreeing with it by construction.
    """

    expected_json = (
        "{"
        '"binding_id":"bind-1",'
        '"canonical_subject_context_ref":"",'
        f'"configuration_digest":"{CFG_DIGEST}",'
        '"configuration_id":"cfg-prod-a",'
        f'"context_digest":"{CTX_DIGEST}",'
        '"context_id":"ctx1",'
        '"deployment_environment_ref":"",'
        '"effective_from":"2026-08-17 10:00:00+00:00",'
        '"effective_to":"2026-08-18 00:00:00+00:00",'
        '"subject_id":"a1",'
        '"system_id":"agent-sys-1",'
        '"system_manifest_digest":"",'
        '"system_manifest_ref":"",'
        '"system_version":"1.4.2",'
        '"tenant_id":"t1"'
        "}"
    )
    expected_bytes = expected_json.encode("utf-8")
    expected_digest = hashlib.sha256(expected_bytes).hexdigest()

    # Written with non-UTC offsets on both bounds: the contract must land on the
    # hand-built UTC bytes above.
    produced = binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100)
    assert produced.canonical_bytes() == expected_bytes
    assert produced.canonical_digest() == expected_digest
    # And the all-UTC spelling of the same instants is byte-identical to it.
    assert binding(effective_from=UTC, effective_to=END_UTC).canonical_bytes() == expected_bytes


def test_the_digest_is_sha256_of_the_canonical_bytes():
    for b in (binding(), binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100)):
        assert b.canonical_digest() == hashlib.sha256(b.canonical_bytes()).hexdigest()
        assert len(b.canonical_digest()) == 64


# --------------------------------------------------------------------------- #
# 9. Ordinary all-UTC behaviour did not drift
# --------------------------------------------------------------------------- #
#: Captured from merged default (`930e73ed`, PR #1439) *before* this correction.
#: Normalizing a UTC instant to UTC is the identity, so every all-UTC binding
#: keeps the exact bytes and digest it already had. These literals are the proof.
MERGED_DEFAULT_NO_PERIOD_DIGEST = (
    "cdbafaaba667b4496f309d01ba7c75788033f68f93d8042ab311f39ddc50b43d"
)
MERGED_DEFAULT_UTC_PERIOD_DIGEST = (
    "df8abb566278f6bbf6fb942bd0429aa0a37f4fc638d0280274a02ddeb63ec438"
)
MERGED_DEFAULT_NO_PERIOD_BYTES = (
    '{"binding_id":"bind-1","canonical_subject_context_ref":"",'
    '"configuration_digest":"b8d582270bcab6ca49bc8ef3b9916fa6f77fd84a35be1c1d884eec31746a29a6",'
    '"configuration_id":"cfg-prod-a",'
    '"context_digest":"baba834176cee0f39f8dc6e4a29d7c5afe1861e6b410c3ed9acb538a795d2fdf",'
    '"context_id":"ctx1","deployment_environment_ref":"","effective_from":null,'
    '"effective_to":null,"subject_id":"a1","system_id":"agent-sys-1",'
    '"system_manifest_digest":"","system_manifest_ref":"","system_version":"1.4.2",'
    '"tenant_id":"t1"}'
).encode("utf-8")


def test_an_all_utc_binding_keeps_its_merged_default_canonical_bytes():
    assert binding().canonical_bytes() == MERGED_DEFAULT_NO_PERIOD_BYTES


def test_an_all_utc_binding_keeps_its_merged_default_digest():
    assert binding().canonical_digest() == MERGED_DEFAULT_NO_PERIOD_DIGEST
    assert binding(effective_from=UTC).canonical_digest() == MERGED_DEFAULT_UTC_PERIOD_DIGEST


def test_the_pre_correction_serializer_still_produces_the_same_bytes_for_utc():
    """The serialization step itself was not replaced — only fed normalized values.

    Reproduces the merged-default expression verbatim and asserts the corrected
    contract still agrees with it for every all-UTC binding.
    """

    for b in (binding(), binding(effective_from=UTC), binding(effective_from=UTC, effective_to=END_UTC)):
        pre_correction = json.dumps(
            dataclasses.asdict(b), sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        assert b.canonical_bytes() == pre_correction


# --------------------------------------------------------------------------- #
# 10. The rest of the contract is untouched
# --------------------------------------------------------------------------- #
def test_no_new_public_symbol_was_added():
    assert set(system_identity.__all__) == {
        "SystemIdentityContractError",
        "SystemBindingAuthenticityStatus",
        "AssessedSystemBinding",
    }
    for name in system_identity.__all__:
        assert getattr(api, name) is getattr(system_identity, name)


def test_no_legacy_or_dual_acceptance_surface_exists():
    """One canonicalization, not two. No fallback, alias or translation layer."""

    names = dir(AssessedSystemBinding)
    for banned in ("legacy", "fallback", "v1", "compat", "alias", "translate", "naive"):
        assert not [n for n in names if banned in n.lower()], banned
    methods = {n for n in names if not n.startswith("__") and callable(getattr(AssessedSystemBinding, n, None))}
    assert {n for n in methods if "canonical" in n} == {"canonical_bytes", "canonical_digest"}


def test_authenticity_and_structural_invariants_are_unchanged():
    b = binding(effective_from=PLUS_0530)
    assert b.authenticity_status is api.SystemBindingAuthenticityStatus.STRUCTURAL_UNVERIFIED
    assert b.authenticity_verified is False
    assert AssessedSystemBinding.__subclasses__() == []
    assert b.system_configuration_identity == (
        "agent-sys-1",
        "1.4.2",
        "cfg-prod-a",
        CFG_DIGEST,
    )


def test_is_effective_at_is_offset_agnostic_and_unchanged():
    """The membership test already compared instants; normalization changed nothing."""

    window = binding(effective_from=UTC, effective_to=END_UTC)
    equivalent = binding(effective_from=PLUS_0530, effective_to=END_MINUS_1100)
    probes = [
        (datetime(2026, 8, 17, 9, 59, 59, tzinfo=timezone.utc), False),
        (UTC, True),  # inclusive start
        (PLUS_0530, True),  # the same instant, other offset
        # 2026-08-17T16:00:00Z written at -04:00 — inside the window.
        (datetime(2026, 8, 17, 12, 0, tzinfo=timezone(timedelta(hours=-4))), True),
        (END_UTC, False),  # exclusive end
        (END_MINUS_1100, False),
    ]
    for instant, expected in probes:
        assert window.is_effective_at(instant) is expected
        assert equivalent.is_effective_at(instant) is expected


def test_the_half_open_period_guard_still_fires_across_offsets():
    with pytest.raises(SystemIdentityContractError, match="half-open"):
        binding(effective_from=UTC, effective_to=MINUS_0400)  # same instant, not before
