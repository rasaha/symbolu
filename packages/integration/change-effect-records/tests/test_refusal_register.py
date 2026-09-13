"""The refusal register: complete, consistent, and honest about what this package raises."""

from __future__ import annotations

from ugence_change_effect_records import CODES_RAISED_HERE, REFUSAL_CODES


def test_every_code_has_an_effect_and_a_condition():
    for code, (effect, condition) in REFUSAL_CODES.items():
        assert code.isupper() and code.replace("_", "").isalnum(), code
        assert effect in ("terminating", "blocking", "refusing", "fails_closed"), code
        assert condition.endswith("."), code


def test_the_blocking_codes_are_the_ones_that_must_not_end_a_candidate():
    """Three codes block. Each is a case where ending the candidate would be the bug."""

    blocking = {c for c, (e, _) in REFUSAL_CODES.items() if e == "blocking"}
    assert blocking == {
        "EVALUATION_RESULT_INCOMPLETE", "SAMPLE_EXHAUSTED", "COMPLETION_PENDING"}


def test_the_codes_this_package_raises_are_all_in_the_register():
    assert CODES_RAISED_HERE <= set(REFUSAL_CODES)


def test_the_codes_this_package_raises_are_only_the_canonical_form_ones():
    """Everything else belongs to a Stage 2 or Stage 3 boundary that does not exist."""

    assert all(c.startswith("CANONICAL_") for c in CODES_RAISED_HERE)


def test_each_code_this_package_raises_is_reachable():
    import pytest

    from ugence_change_effect_records import CanonicalFormRefused, domain_digest

    payloads = {
        "CANONICAL_NULL_FORBIDDEN": None,
        "CANONICAL_BOOLEAN_REFUSED": True,
        "CANONICAL_NUMBER_REFUSED": 1.5,
        "CANONICAL_TYPE_REFUSED": {1, 2},
    }
    assert set(payloads) == CODES_RAISED_HERE
    for code, value in payloads.items():
        with pytest.raises(CanonicalFormRefused) as raised:
            domain_digest("x", {"k": value})
        assert raised.value.code == code
