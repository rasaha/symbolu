"""The canonical-bytes profile of rule section 6a, enforced rather than described.

The envelope is the sibling packages' own; these tests cover what the *profile* adds,
because a specification an implementation does not enforce is a specification two
implementations will disagree about.
"""

from __future__ import annotations

import json

import pytest

from ugence_change_effect_records import (
    CanonicalFormRefused,
    ContractViolation,
    canonical_json,
    domain_digest,
    iso,
    normalize_tenant,
    require_digest,
    require_ordinal,
    require_tzaware,
)


def test_the_envelope_matches_the_sibling_convention():
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert canonical_json({"k": "é"}) == '{"k":"\\u00e9"}', "ensure_ascii, deterministically"


def test_a_null_anywhere_is_refused():
    with pytest.raises(CanonicalFormRefused) as e:
        domain_digest("x", {"k": None})
    assert e.value.code == "CANONICAL_NULL_FORBIDDEN"


def test_a_nested_null_is_refused_too():
    """Recursive, so "absent" and "present and empty" cannot collide at any depth."""

    with pytest.raises(CanonicalFormRefused) as e:
        domain_digest("x", {"a": [{"b": None}]})
    assert e.value.code == "CANONICAL_NULL_FORBIDDEN"


def test_a_json_boolean_is_refused_outright():
    """Stricter than refusing booleans where an integer is expected, and deliberate.

    A language that treats ``True`` as ``1`` would otherwise admit a flag wherever a
    count was meant. Writing the flag out as an enumerated string removes the question.
    """

    with pytest.raises(CanonicalFormRefused) as e:
        domain_digest("x", {"k": True})
    assert e.value.code == "CANONICAL_BOOLEAN_REFUSED"


@pytest.mark.parametrize("value", [1.5, 2**63, -(2**63) - 1])
def test_floats_and_out_of_range_integers_are_refused(value):
    with pytest.raises(CanonicalFormRefused) as e:
        domain_digest("x", {"k": value})
    assert e.value.code == "CANONICAL_NUMBER_REFUSED"


def test_int64_boundaries_are_admissible():
    assert domain_digest("x", {"k": 2**63 - 1})
    assert domain_digest("x", {"k": -(2**63)})


def test_an_unencodable_type_is_refused():
    with pytest.raises(CanonicalFormRefused) as e:
        domain_digest("x", {"k": {1, 2}})
    assert e.value.code == "CANONICAL_TYPE_REFUSED"


def test_nfc_is_applied_recursively():
    decomposed, composed = "é", "é"
    assert domain_digest("x", {"a": [{"b": decomposed}]}) == (
        domain_digest("x", {"a": [{"b": composed}]}))


def test_a_unit_separator_inside_a_string_cannot_forge_the_framing():
    """The encoder escapes U+001F, which is the framing bare concatenation lacks."""

    assert "\\u001f" in canonical_json({"k": "a\x1fb"})
    assert domain_digest("d", {"k": "a\x1fb"}) != domain_digest("d", {"k": "ab"})


def test_the_domain_separates():
    assert domain_digest("chain_id", {"k": 1}) != domain_digest("obligation_id", {"k": 1})


def test_a_digest_must_be_full_and_lowercase():
    full = "a" * 64
    assert require_digest(full, "d") == full
    for bad in ("a" * 63, "A" * 64, "g" * 64, ""):
        with pytest.raises(ContractViolation):
            require_digest(bad, "d")


def test_truncation_is_refused_rather_than_tolerated():
    with pytest.raises(ContractViolation):
        require_digest(domain_digest("x", {"k": 1})[:16], "d")


def test_an_ordinal_refuses_a_boolean():
    assert require_ordinal(0, "o") == 0
    for bad in (True, -1, "0", 1.0):
        with pytest.raises(ContractViolation):
            require_ordinal(bad, "o")


def test_no_clock_is_read_and_naive_instants_are_refused():
    import datetime as dt

    with pytest.raises(ContractViolation):
        require_tzaware(dt.datetime(2026, 1, 1), "t")
    aware = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert iso(aware) == "2026-01-01T00:00:00.000000+00:00"


def test_tenant_normalisation_is_trim_lower_nfc():
    assert normalize_tenant("  TENANT-1  ") == "tenant-1"
    with pytest.raises(ContractViolation):
        normalize_tenant("   ")


def test_profiling_does_not_mutate_the_caller_s_payload():
    payload = {"k": "é", "n": [1, 2]}
    before = json.dumps(payload, sort_keys=True)
    domain_digest("x", payload)
    assert json.dumps(payload, sort_keys=True) == before
