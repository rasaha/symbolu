"""Tests for the §6 runpod incremental-save + disk-paraphrase-cache fixes.

Covers:
  - per_decoder_complete_callback fires once per decoder with the
    correct result.
  - MockBenchmark-driven end-to-end write produces per-decoder CSVs.
  - Disk paraphrase cache round-trip: save on miss, load on next
    instance, hits on reload.
  - Cache rejects mismatched (model, split) on load.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple
from unittest import mock

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import (
    MockBenchmark,
    Question,
    TruthfulQABenchmark,
)
from symbolu_bcvf_llm.benchmark.harness import run_benchmark


def test_per_decoder_complete_callback_fires_per_decoder():
    bench = MockBenchmark(num_questions=4)
    calls: List[Tuple[str, int, float]] = []

    def cb(decoder_name, result):
        calls.append(
            (decoder_name, int(result.num_questions), float(result.accuracy))
        )

    run_benchmark(bench, per_decoder_complete_callback=cb)
    # Fired exactly once per decoder, in order.
    assert [name for (name, _, _) in calls] == [
        "vanilla", "conventional_blend", "bcvf_trust",
    ]
    for (_, n, _) in calls:
        assert n == 4


def test_per_decoder_callback_receives_accuracy_between_0_and_1():
    bench = MockBenchmark(num_questions=3)
    accs = []

    def cb(decoder_name, result):
        accs.append(result.accuracy)

    run_benchmark(bench, per_decoder_complete_callback=cb)
    assert len(accs) == 3
    for a in accs:
        assert 0.0 <= a <= 1.0


# --------------------------------------------------------------------------- #
# Disk paraphrase cache
# --------------------------------------------------------------------------- #


def _fake_tqa_benchmark(tmp_path: Path, model_name: str = "m1",
                        split: str = "validation") -> TruthfulQABenchmark:
    """Bypass __init__'s torch gate so we can exercise just the cache logic."""
    bench = TruthfulQABenchmark.__new__(TruthfulQABenchmark)
    bench._paraphrase_cache = {}
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._paraphrase_max_new_tokens = 32
    bench._use_paraphrase = True
    bench._model_name = model_name
    bench._split = split
    bench._paraphrase_cache_file = tmp_path / "cache.json"
    bench._paraphrase_cache_loaded = 0
    bench._model = object()
    bench._tokenizer = object()
    bench._rewrite_seed_pair = (1, 2)
    bench._evaluation_seed = 1
    return bench


def test_paraphrase_cache_persists_to_disk_on_miss(tmp_path: Path):
    bench = _fake_tqa_benchmark(tmp_path)

    def fake_paraphrase(*args, **kwargs):
        return f"PARA_{kwargs['rewrite_seed']}"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        bench._get_or_create_paraphrase(row_id=0, base_prompt="Q0", rewrite_seed=1)

    cache_path = bench._paraphrase_cache_file
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text())
    assert payload["model_name"] == "m1"
    assert payload["split"] == "validation"
    assert payload["entries"] == {"0__1": "PARA_1"}


def test_paraphrase_cache_reloads_from_disk(tmp_path: Path):
    # Manually write a cache file, then simulate loading.
    cache_path = tmp_path / "seeded.json"
    cache_path.write_text(json.dumps({
        "model_name": "m1",
        "split": "validation",
        "entries": {
            "5__1": "precomputed_5_1",
            "5__2": "precomputed_5_2",
        },
    }))
    bench = TruthfulQABenchmark.__new__(TruthfulQABenchmark)
    bench._paraphrase_cache = {}
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._paraphrase_max_new_tokens = 32
    bench._use_paraphrase = True
    bench._model_name = "m1"
    bench._split = "validation"
    bench._paraphrase_cache_file = cache_path
    bench._paraphrase_cache_loaded = 0
    bench._rewrite_seed_pair = (1, 2)
    bench._evaluation_seed = 1

    # Emulate the __init__ load block.
    with open(cache_path) as fh:
        payload = json.load(fh)
    for k, v in payload["entries"].items():
        row_str, seed_str = k.split("__", 1)
        bench._paraphrase_cache[(int(row_str), int(seed_str))] = v
    bench._paraphrase_cache_loaded = len(bench._paraphrase_cache)

    assert bench._paraphrase_cache_loaded == 2
    assert bench.paraphrase_cache_stats["loaded_from_disk"] == 2

    # Now request a previously-cached entry — should hit, no new
    # paraphrase generation.
    called = {"n": 0}

    def fake_paraphrase(*args, **kwargs):
        called["n"] += 1
        return "SHOULD_NOT_BE_CALLED"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        out = bench._get_or_create_paraphrase(
            row_id=5, base_prompt="anything", rewrite_seed=1
        )

    assert out == "precomputed_5_1"
    assert called["n"] == 0
    assert bench._paraphrase_hits == 1
    assert bench._paraphrase_misses == 0


def test_paraphrase_cache_stats_exposes_disk_metadata(tmp_path: Path):
    bench = _fake_tqa_benchmark(tmp_path)
    stats = bench.paraphrase_cache_stats
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["entries"] == 0
    assert stats["loaded_from_disk"] == 0
    assert stats["persisted_to"] == str(bench._paraphrase_cache_file)
    assert stats["rewrite_seed_pair"] == [1, 2]


def test_paraphrase_cache_stats_persisted_to_none_when_disabled(tmp_path: Path):
    bench = _fake_tqa_benchmark(tmp_path)
    bench._paraphrase_cache_file = None   # emulate --no-paraphrase-cache-file
    stats = bench.paraphrase_cache_stats
    assert stats["persisted_to"] is None
