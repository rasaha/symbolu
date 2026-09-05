"""Phase 4C slice 1: the deterministic sample selector, the output-format wrapper and the
``bbh-ld7.v3`` scorer.

Every expected digest here is a **literal from the commissioning note**, never a value
recomputed by the code under test, so a change in the implementation cannot quietly move
the target with it. No benchmark case or expected answer appears anywhere: the selector
works on index ranges, and the scorer tests use synthetic digests and synthetic letters.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from experiments.workflow_fit_study.bbh_ld7_scorer import (
    SCORING_PROCEDURE_DIGEST,
    SCORING_PROCEDURE_TEXT,
    BbhLd7Scorer,
    ScorerConstructionError,
    ScorerCustodyError,
    extract_answer,
    normalize_payload,
)
from experiments.workflow_fit_study.bbh_sample import (
    SampleSelectionError,
    index_list_digest,
    select_indexes,
)
from experiments.workflow_fit_study.bbh_wrapper import (
    ANSWER_INSTRUCTION,
    PromptWrapError,
    is_wrapped,
    wrap_query,
)
from ugence_jcs import canonical_sha256_hex
from ugence_jcs.errors import BareNumberError

# Literals transcribed from WORKFLOW_FIT_PILOT_4C_COMMISSIONING_NOTE.md (revisions 12-14).
RATIFIED_SEED = 2924744787006253617
POPULATION = 250
SAMPLE = 50
RATIFIED_INDEX_DIGEST = "c521cdd75dc3b8c9e589835ade4b780ef26ba955d4077f5c7ad74e803be60682"
RATIFIED_PROCEDURE_DIGEST = "9cc587889c5b43dbc1f6ae796840d6af90cfe95c0e6e49cbe245f2ca5dfc1813"
RATIFIED_PROCEDURE_BYTES = 1704

CASE_A = "a" * 64
CASE_B = "b" * 64


# --------------------------------------------------------------------------- selector


def test_selector_reproduces_the_ratified_sample_and_digest():
    indexes = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    assert len(indexes) == SAMPLE
    assert len(set(indexes)) == SAMPLE
    assert all(0 <= i < POPULATION for i in indexes)
    assert list(indexes) == sorted(indexes)
    assert index_list_digest(indexes) == RATIFIED_INDEX_DIGEST


def test_selection_is_stable_across_repeated_execution():
    first = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    second = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    assert first == second


def test_a_different_seed_selects_a_different_sample():
    other = select_indexes(seed=RATIFIED_SEED + 1, population_size=POPULATION, sample_size=SAMPLE)
    assert other != select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)


def test_tie_breaking_is_total_so_the_whole_population_orders_deterministically():
    # Selecting the entire population exercises the (hash, index) total order rather than
    # only its prefix; the result must be the identity ordering, with no index lost.
    everything = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=POPULATION)
    assert everything == tuple(range(POPULATION))


def test_digest_input_is_the_decimal_string_form():
    indexes = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    assert index_list_digest(indexes) == canonical_sha256_hex([str(i) for i in indexes])


def test_bare_numeric_indexes_are_refused_by_the_canonicalizer():
    indexes = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    with pytest.raises(BareNumberError):
        canonical_sha256_hex(list(indexes))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"seed": -1, "population_size": 250, "sample_size": 50},
        {"seed": 2**64, "population_size": 250, "sample_size": 50},
        {"seed": True, "population_size": 250, "sample_size": 50},
        {"seed": "2924744787006253617", "population_size": 250, "sample_size": 50},
        {"seed": RATIFIED_SEED, "population_size": 0, "sample_size": 50},
        {"seed": RATIFIED_SEED, "population_size": -250, "sample_size": 50},
        {"seed": RATIFIED_SEED, "population_size": 250, "sample_size": 0},
        {"seed": RATIFIED_SEED, "population_size": 250, "sample_size": 251},
    ],
)
def test_invalid_selector_inputs_fail_closed(kwargs):
    with pytest.raises(SampleSelectionError):
        select_indexes(**kwargs)


@pytest.mark.parametrize("indexes", [(), (1, 0), (0, 0, 1), (0, "1")])
def test_invalid_digest_inputs_fail_closed(indexes):
    with pytest.raises(SampleSelectionError):
        index_list_digest(indexes)


# --------------------------------------------------------------------------- wrapper

SYNTHETIC_ITEM = "Synthetic ordering puzzle.\nOptions:\n(A) first\n(B) second\n(G) seventh"


def test_wrapper_preserves_the_upstream_item_byte_for_byte_as_the_prefix():
    wrapped = wrap_query(SYNTHETIC_ITEM)
    assert wrapped.startswith(SYNTHETIC_ITEM)
    assert wrapped.endswith(ANSWER_INSTRUCTION)


def test_wrapping_is_deterministic():
    assert wrap_query(SYNTHETIC_ITEM) == wrap_query(SYNTHETIC_ITEM)


def test_wrapper_exposes_no_expected_answer_and_requests_no_chain_of_thought():
    wrapped = wrap_query(SYNTHETIC_ITEM)
    assert "expected" not in wrapped.lower()
    for phrase in ("step by step", "step-by-step", "chain of thought", "reasoning trace", "show your work"):
        assert phrase not in wrapped.lower()


def test_wrapper_requires_the_answer_line():
    assert "ANSWER:" in wrap_query(SYNTHETIC_ITEM)


def test_double_wrapping_is_refused():
    wrapped = wrap_query(SYNTHETIC_ITEM)
    assert is_wrapped(wrapped)
    with pytest.raises(PromptWrapError):
        wrap_query(wrapped)


@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_blank_items_are_refused(bad):
    with pytest.raises(PromptWrapError):
        wrap_query(bad)


def test_unicode_and_newlines_survive_wrapping_unchanged():
    item = "Ünïcode ítem\r\nwith CRLF and a line separator"
    wrapped = wrap_query(item)
    assert wrapped[: len(item)] == item


# --------------------------------------------------------------------------- scorer


def test_shipped_procedure_text_matches_the_recorded_length_and_digest():
    assert len(SCORING_PROCEDURE_TEXT.encode("utf-8")) == RATIFIED_PROCEDURE_BYTES
    assert canonical_sha256_hex(SCORING_PROCEDURE_TEXT) == RATIFIED_PROCEDURE_DIGEST
    assert SCORING_PROCEDURE_DIGEST == RATIFIED_PROCEDURE_DIGEST


@pytest.fixture()
def scorer() -> BbhLd7Scorer:
    return BbhLd7Scorer({CASE_A: "(B)", CASE_B: "(G)"})


@pytest.mark.parametrize("response", ["ANSWER: B", "answer: b", "ANSWER: (B)", "  ANSWER:   b  ", "ANSWER:B"])
def test_conforming_answers_score_one(scorer, response):
    assert scorer.score(CASE_A, response) == Decimal("1")


@pytest.mark.parametrize("response", ["B", "(B)", "b", "The answer is B"])
def test_a_bare_letter_without_the_prefix_scores_zero(scorer, response):
    assert scorer.score(CASE_A, response) == Decimal("0")


def test_the_last_prefix_bearing_line_wins(scorer):
    assert scorer.score(CASE_A, "ANSWER: G\nANSWER: B") == Decimal("1")
    assert scorer.score(CASE_A, "ANSWER: B\nANSWER: G") == Decimal("0")


def test_a_malformed_last_line_scores_zero_with_no_fallback(scorer):
    assert scorer.score(CASE_A, "ANSWER: B\nANSWER: BC") == Decimal("0")
    assert scorer.score(CASE_A, "ANSWER: B\nANSWER:") == Decimal("0")


@pytest.mark.parametrize(
    "response",
    ["ANSWER: B.", "ANSWER: BC", "ANSWER: (B", "ANSWER: ((B))", "ANSWER: H", "ANSWER: 1", "ANSWER: В"],
)
def test_malformed_payloads_score_zero(scorer, response):
    assert scorer.score(CASE_A, response) == Decimal("0")


def test_a_missing_answer_line_scores_zero(scorer):
    assert scorer.score(CASE_A, "There is no answer line here.") == Decimal("0")


@pytest.mark.parametrize("letter", list("ABCDEFG"))
def test_every_upstream_target_normalizes_and_scores(letter):
    scorer = BbhLd7Scorer({CASE_A: f"({letter})"})
    assert normalize_payload(f"({letter})") == letter
    assert scorer.score(CASE_A, f"ANSWER: {letter}") == Decimal("1")


def test_identical_inputs_score_identically_across_fresh_instances():
    first = BbhLd7Scorer({CASE_A: "(B)"}).score(CASE_A, "ANSWER: (b)")
    second = BbhLd7Scorer({CASE_A: "(B)"}).score(CASE_A, "ANSWER: (b)")
    assert first == second == Decimal("1")


def test_the_scorer_signature_never_takes_a_query():
    import inspect

    parameters = list(inspect.signature(BbhLd7Scorer.score).parameters)
    assert parameters == ["self", "case_digest", "response"]


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"short": "(B)"},
        {CASE_A.upper(): "(B)"},
        {CASE_A: "(H)"},
        {CASE_A: "BC"},
        {CASE_A: ""},
        {CASE_A: 2},
    ],
)
def test_malformed_custody_mappings_are_refused(mapping):
    with pytest.raises(ScorerConstructionError):
        BbhLd7Scorer(mapping)


def test_a_case_digest_outside_custody_fails_closed(scorer):
    with pytest.raises(ScorerCustodyError):
        scorer.score("c" * 64, "ANSWER: B")


def test_extract_answer_returns_the_empty_string_when_no_prefix_line_exists():
    assert extract_answer("no answer here") == ""


def test_runtime_constant_is_byte_identical_to_the_documented_preimage():
    """The runtime constant and the commissioning note must be the same bytes, not merely
    the same digest: a second source of truth is how errata like the v2 character count
    survive."""
    import pathlib
    import re

    note = pathlib.Path("docs/architecture/WORKFLOW_FIT_PILOT_4C_COMMISSIONING_NOTE.md")
    if not note.is_file():  # the implementation branch may be reviewed without the note
        pytest.skip("commissioning note is not present in this checkout")
    documented = re.search(r"```\n(bbh-ld7\.v3: LINES\..*?)\n```", note.read_text(), re.S)
    assert documented is not None, "the note carries no bbh-ld7.v3 preimage"
    assert documented.group(1) == SCORING_PROCEDURE_TEXT


def test_procedure_text_states_the_prefix_length_correctly():
    """The v2 erratum, guarded against regression: the quoted prefix has seven characters."""
    assert "the seven characters 'ANSWER:'" in SCORING_PROCEDURE_TEXT
    assert "the four characters" not in SCORING_PROCEDURE_TEXT
    assert len("ANSWER:") == 7


def test_scorer_matches_the_quality_scorer_port_signature():
    import inspect

    from ugence_workflow_fit_pilot.runner import QualityScorerPort

    assert inspect.signature(BbhLd7Scorer.score) == inspect.signature(QualityScorerPort.score)


def test_custody_mapping_is_defensively_copied():
    supplied = {CASE_A: "(B)"}
    instance = BbhLd7Scorer(supplied)
    supplied[CASE_A] = "(G)"
    supplied[CASE_B] = "(A)"
    assert instance.score(CASE_A, "ANSWER: B") == Decimal("1")
    with pytest.raises(ScorerCustodyError):
        instance.score(CASE_B, "ANSWER: A")


def test_a_non_string_response_is_a_type_error():
    with pytest.raises(TypeError):
        BbhLd7Scorer({CASE_A: "(B)"}).score(CASE_A, 3)
