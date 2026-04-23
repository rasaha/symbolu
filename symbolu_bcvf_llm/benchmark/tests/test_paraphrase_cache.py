"""§6.2 paraphrase-cache behaviour test.

Exercises `TruthfulQABenchmark._get_or_create_paraphrase` + the
`paraphrase_cache_stats` diagnostic without loading a real model
or the `datasets` library.

Strategy: monkey-patch `make_paraphrased_prompt` and bypass the
torch-gated constructor by instantiating via `__new__`. The cache
logic is pure-Python and testable independent of the ML stack.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from unittest import mock

import pytest


def _make_fake_benchmark(row_id: int = 0):
    """Minimal TruthfulQABenchmark-like object exercising the cache path.

    Uses `__new__` to bypass the real __init__ (which wants torch +
    transformers + datasets). Only the attributes + methods the
    cache test touches are populated; anything else raises AttributeError
    if accidentally used (which would be a test-design bug, not a code
    bug).
    """
    from symbolu_bcvf_llm.benchmark.dataset import (
        Question,
        TruthfulQABenchmark,
    )

    bench = TruthfulQABenchmark.__new__(TruthfulQABenchmark)
    bench._paraphrase_cache = {}
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._paraphrase_max_new_tokens = 32
    bench._use_paraphrase = True
    bench._model = object()      # placeholder; make_paraphrased_prompt is mocked
    bench._tokenizer = object()  # same
    # Same-model paraphraser (V1 default) — the cross-model path sets
    # these to a distinct pair.
    bench._paraphraser_model = bench._model
    bench._paraphraser_tokenizer = bench._tokenizer
    bench._paraphraser_model_name = "test-model"
    # Disk-cache fields (disabled for this test helper).
    bench._paraphrase_cache_file = None
    bench._paraphrase_cache_loaded = 0
    bench._paraphrase_cache_discarded_reason = None
    bench._model_name = "test-model"
    bench._split = "test"
    # Rewrite-seed plumbing (§1.10 replication).
    bench._rewrite_seed_pair = (1, 2)
    bench._evaluation_seed = 1
    return bench


def test_paraphrase_cache_hits_after_first_miss():
    bench = _make_fake_benchmark()
    call_log: List[Tuple[str, int]] = []

    def fake_paraphrase(model, tokenizer, prompt, rewrite_seed,
                        max_new_tokens, instruction_template=None):
        call_log.append((prompt, rewrite_seed))
        return f"PARAPHRASE(prompt={prompt!r}, seed={rewrite_seed})"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        # First call — miss.
        out_1 = bench._get_or_create_paraphrase(row_id=7, base_prompt="Q?",
                                                rewrite_seed=1)
        # Second call — same key — hit.
        out_2 = bench._get_or_create_paraphrase(row_id=7, base_prompt="Q?",
                                                rewrite_seed=1)

    assert out_1 == out_2
    assert len(call_log) == 1, (
        f"expected 1 paraphrase call, got {len(call_log)}: {call_log}"
    )
    assert bench._paraphrase_hits == 1
    assert bench._paraphrase_misses == 1


def test_paraphrase_cache_separates_by_seed():
    bench = _make_fake_benchmark()
    call_log = []

    def fake_paraphrase(model, tokenizer, prompt, rewrite_seed,
                        max_new_tokens, instruction_template=None):
        call_log.append(rewrite_seed)
        return f"PARA_{rewrite_seed}"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        a = bench._get_or_create_paraphrase(row_id=0, base_prompt="P",
                                            rewrite_seed=1)
        b = bench._get_or_create_paraphrase(row_id=0, base_prompt="P",
                                            rewrite_seed=2)
        a2 = bench._get_or_create_paraphrase(row_id=0, base_prompt="P",
                                             rewrite_seed=1)
        b2 = bench._get_or_create_paraphrase(row_id=0, base_prompt="P",
                                             rewrite_seed=2)

    assert a == a2 == "PARA_1"
    assert b == b2 == "PARA_2"
    # Seeds 1 and 2 should produce two distinct misses, then two hits.
    assert sorted(call_log) == [1, 2]
    assert bench._paraphrase_misses == 2
    assert bench._paraphrase_hits == 2


def test_paraphrase_cache_separates_by_row():
    bench = _make_fake_benchmark()

    def fake_paraphrase(model, tokenizer, prompt, rewrite_seed, **kwargs):
        return f"{prompt}__seed={rewrite_seed}"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        bench._get_or_create_paraphrase(row_id=0, base_prompt="A", rewrite_seed=1)
        bench._get_or_create_paraphrase(row_id=1, base_prompt="B", rewrite_seed=1)
        # Re-query row 0, seed 1 — should hit.
        bench._get_or_create_paraphrase(row_id=0, base_prompt="A", rewrite_seed=1)

    assert bench._paraphrase_misses == 2
    assert bench._paraphrase_hits == 1
    stats = bench.paraphrase_cache_stats
    assert stats["hits"] == 1
    assert stats["misses"] == 2
    assert stats["entries"] == 2
    assert stats["loaded_from_disk"] == 0
    assert stats["persisted_to"] is None


def test_paraphrase_cache_expected_count_for_simulated_run():
    """End-to-end cache arithmetic.

    Simulate a 5-question benchmark where each question gets 5 choices ×
    3 decoders = 15 make_sources calls and each make_sources asks for
    two paraphrases. Expected:
      raw calls would be 5 × 15 × 2 = 150
      cached calls:     5 × 2       = 10 (one per (question, seed))
      hits:             140
    """
    bench = _make_fake_benchmark()
    calls = {"n": 0}

    def fake_paraphrase(*args, **kwargs):
        calls["n"] += 1
        return "x"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        for question_id in range(5):
            for _ in range(15):  # 3 decoders × 5 choices
                for seed in (1, 2):
                    bench._get_or_create_paraphrase(
                        row_id=question_id,
                        base_prompt=f"Q{question_id}",
                        rewrite_seed=seed,
                    )

    assert calls["n"] == 10, f"expected 10 real paraphrase calls, got {calls['n']}"
    assert bench._paraphrase_misses == 10
    assert bench._paraphrase_hits == 140
    assert len(bench._paraphrase_cache) == 10
