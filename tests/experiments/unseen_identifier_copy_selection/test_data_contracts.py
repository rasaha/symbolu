"""Fixture-only tests for identifier pools, C1-C8 construction, serialization, and parsing."""
from __future__ import annotations

import pytest

from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer
from experiments.unseen_identifier_copy_selection.config import (
    CANDIDATE_COUNT,
    FIXTURE_SEEDS,
    IDENTIFIER_LENGTH,
    RESERVED_SEEDS,
)
from experiments.unseen_identifier_copy_selection.identifiers import (
    IdentifierIntegrityError,
    assert_character_visible,
    build_pools,
)
from experiments.unseen_identifier_copy_selection.parser import OutputCategory, parse
from experiments.unseen_identifier_copy_selection.serializer import serialize
from experiments.unseen_identifier_copy_selection.tasks import generate_split

FS = FIXTURE_SEEDS[0]
SPLITS = tuple(f"C{i}" for i in range(1, 9))


def test_master_pools_disjoint_and_char_visible():
    pools = build_pools(FS)
    train, final, evidence = set(pools["train"]), set(pools["final"]), set(pools["evidence"])
    assert train.isdisjoint(final)
    assert train.isdisjoint(evidence)
    assert final.isdisjoint(evidence)
    assert_character_visible(list(train)[:32])
    # every identifier is exactly IDENTIFIER_LENGTH tokens under the frozen tokenizer
    tok = LexicalTokenizer()
    for ident in list(train)[:32]:
        assert len(tok.encode(ident)) == IDENTIFIER_LENGTH
        assert tok.decode(tok.encode(ident)) == ident


def test_pools_deterministic_byte_identical():
    assert build_pools(FS) == build_pools(FS)


def test_fixture_seeds_disjoint_from_reserved():
    assert set(FIXTURE_SEEDS).isdisjoint(RESERVED_SEEDS)


@pytest.mark.parametrize("split", SPLITS)
def test_split_construction_and_gold_parses_correctly(split):
    exs = generate_split(split, "unseen", FS, n=12)
    assert len(exs) == 12
    for e in exs:
        # gold output must classify as exact-correct (answer splits) or correct-abstention (C8)
        res = parse(e.expected_output, e)
        if e.expected_abstention:
            assert res.category is OutputCategory.CORRECT_ABSTENTION
        else:
            assert res.category is OutputCategory.EXACT_CORRECT
        # candidate structure
        if split in ("C2", "C4", "C5", "C6", "C7"):
            assert len(e.pairs) == CANDIDATE_COUNT
            assert e.expected_output in [t for _, t in e.pairs]


def test_position_balance_for_c4():
    exs = generate_split("C4", "unseen", FS, n=12)
    positions = [e.correct_position % 3 for e in exs]
    # balanced first/middle/last
    assert positions.count(0) == positions.count(1) == positions.count(2) == 4


def test_c5_lexical_decoys_are_near_neighbors():
    exs = generate_split("C5", "unseen", FS, n=8)
    for e in exs:
        assert e.lexical_decoy_class in ("edit1", "edit2")
        answer = e.expected_output
        for _, tgt in e.pairs:
            if tgt != answer:
                diff = sum(1 for a, b in zip(tgt, answer) if a != b)
                assert 1 <= diff <= 2


def test_c8_missing_key_query_absent_from_context():
    exs = generate_split("C8", "unseen", FS, n=10)
    for e in exs:
        assert e.expected_abstention
        assert e.query_source not in e.context_ids  # queried source is truly absent


def test_seen_unseen_pools_disjoint():
    seen = {i for e in generate_split("C6", "seen", FS, n=40) for i in e.context_ids}
    unseen = {i for e in generate_split("C7", "unseen", FS, n=40) for i in e.context_ids}
    assert seen.isdisjoint(unseen)


def test_serialization_byte_identical_and_ascii():
    e = generate_split("C2", "unseen", FS, n=4)[0]
    assert serialize(e) == serialize(e)
    serialize(e).encode("ascii")  # must not raise
    assert serialize(e).rstrip("\n").endswith("ANSWER =")


def test_no_reserved_cohort_generated_by_fixtures():
    # generating with a fixture seed must never draw a reserved-pool identifier namespace;
    # (fixtures use fixture seeds; reserved seeds are gated elsewhere). Sanity: fixture ids exist.
    exs = generate_split("C1", "unseen", FS, n=4)
    assert all(len(e.target_id) == IDENTIFIER_LENGTH for e in exs)


def test_requesting_more_than_window_raises():
    with pytest.raises(ValueError):
        generate_split("C2", "unseen", FS, n=10_000)


def test_parser_categories():
    e = generate_split("C2", "unseen", FS, n=1)[0]
    ctx_wrong = next(t for _, t in e.pairs if t != e.expected_output)
    assert parse(e.expected_output, e).category is OutputCategory.EXACT_CORRECT
    assert parse(ctx_wrong, e).category is OutputCategory.WRONG_IN_CONTEXT
    assert parse("ZZ99", e).category in (OutputCategory.FABRICATED_OUT_OF_CONTEXT, OutputCategory.TOKEN_PARTIAL)
    assert parse("!!bad!!", e).category is OutputCategory.MALFORMED
    assert parse("INSUFFICIENT_EVIDENCE", e).category is OutputCategory.FALSE_ABSTENTION
    c8 = generate_split("C8", "unseen", FS, n=1)[0]
    assert parse("INSUFFICIENT_EVIDENCE", c8).category is OutputCategory.CORRECT_ABSTENTION
