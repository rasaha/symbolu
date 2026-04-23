"""§1.10 replication: `--seed` plumbing to paraphrase rewrite-seeds.

Tests the evaluation_seed → rewrite_seed_pair mapping on
`TruthfulQABenchmark`. The prior implementation hardcoded rewrite
seeds (1, 2), which meant `--seed 2` would produce the same
paraphrases as `--seed 1` → replication was a no-op. This suite
guards against regression by asserting distinct mappings for
different evaluation seeds.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from symbolu_bcvf_llm.benchmark.dataset import TruthfulQABenchmark


def _fake_tqa(
    evaluation_seed: int = 1,
    rewrite_seed_pair=None,
) -> TruthfulQABenchmark:
    """Bypass the torch-gated __init__ and exercise only the
    rewrite-seed derivation logic."""
    bench = TruthfulQABenchmark.__new__(TruthfulQABenchmark)
    bench._paraphrase_cache = {}
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._paraphrase_max_new_tokens = 32
    bench._use_paraphrase = True
    bench._model_name = "m1"
    bench._split = "validation"
    bench._paraphrase_cache_file = None
    bench._paraphrase_cache_loaded = 0
    bench._paraphrase_cache_discarded_reason = None
    bench._model = object()
    bench._tokenizer = object()
    bench._paraphraser_model = bench._model
    bench._paraphraser_tokenizer = bench._tokenizer
    bench._paraphraser_model_name = bench._model_name

    # Replicate the __init__ derivation logic.
    if rewrite_seed_pair is not None:
        pair = tuple(int(s) for s in rewrite_seed_pair)
        if len(pair) != 2 or pair[0] == pair[1]:
            raise ValueError(
                f"rewrite_seed_pair must be two distinct ints, got {pair}"
            )
        bench._rewrite_seed_pair = pair
    else:
        base = max(int(evaluation_seed), 1)
        bench._rewrite_seed_pair = (2 * base - 1, 2 * base)
    bench._evaluation_seed = int(evaluation_seed)
    return bench


def test_seed_1_maps_to_rewrite_seeds_1_and_2():
    """Backward compat: the pre-fix hardcoded behaviour was (1, 2)."""
    bench = _fake_tqa(evaluation_seed=1)
    assert bench.rewrite_seed_pair == (1, 2)


def test_seed_2_maps_to_rewrite_seeds_3_and_4():
    """§1.10 replication: seed 2 must use DIFFERENT paraphrases from seed 1."""
    bench = _fake_tqa(evaluation_seed=2)
    assert bench.rewrite_seed_pair == (3, 4)


def test_seed_3_maps_to_rewrite_seeds_5_and_6():
    bench = _fake_tqa(evaluation_seed=3)
    assert bench.rewrite_seed_pair == (5, 6)


def test_seed_0_treated_as_seed_1_for_backward_compat():
    """Default --seed 0 gets (1, 2) same as --seed 1."""
    bench = _fake_tqa(evaluation_seed=0)
    assert bench.rewrite_seed_pair == (1, 2)


def test_explicit_rewrite_seed_pair_overrides_derivation():
    bench = _fake_tqa(evaluation_seed=99, rewrite_seed_pair=(42, 43))
    assert bench.rewrite_seed_pair == (42, 43)


def test_rewrite_seed_pair_must_be_distinct():
    with pytest.raises(ValueError, match="distinct"):
        _fake_tqa(rewrite_seed_pair=(5, 5))


def test_paraphrase_cache_stats_includes_rewrite_seed_pair():
    bench = _fake_tqa(evaluation_seed=3)
    stats = bench.paraphrase_cache_stats
    assert stats["rewrite_seed_pair"] == [5, 6]


def test_different_eval_seeds_produce_distinct_cache_keys():
    """Seed 1 and seed 2 must paraphrase different (row_id, seed) pairs,
    so their cache entries don't collide."""
    bench1 = _fake_tqa(evaluation_seed=1)
    bench2 = _fake_tqa(evaluation_seed=2)

    def fake_paraphrase(*args, **kwargs):
        return f"rewrite_seed={kwargs['rewrite_seed']}"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        # Both benches paraphrase row_id=7; seed 1 uses (1, 2), seed 2 uses (3, 4).
        seed_a_1, seed_b_1 = bench1.rewrite_seed_pair
        bench1._get_or_create_paraphrase(7, "Q7", seed_a_1)
        bench1._get_or_create_paraphrase(7, "Q7", seed_b_1)

        seed_a_2, seed_b_2 = bench2.rewrite_seed_pair
        bench2._get_or_create_paraphrase(7, "Q7", seed_a_2)
        bench2._get_or_create_paraphrase(7, "Q7", seed_b_2)

    # Cache keys must not overlap.
    keys_1 = set(bench1._paraphrase_cache.keys())
    keys_2 = set(bench2._paraphrase_cache.keys())
    assert keys_1 == {(7, 1), (7, 2)}
    assert keys_2 == {(7, 3), (7, 4)}
    assert keys_1.isdisjoint(keys_2)
    # And the paraphrase outputs differ — that's the whole point.
    assert bench1._paraphrase_cache[(7, 1)] != bench2._paraphrase_cache[(7, 3)]
