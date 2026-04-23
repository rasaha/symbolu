"""Cross-model paraphrase cache invalidation tests.

Exercises the §10.V1.3 Experiment A cross-model paraphraser path:
- Cache written by paraphraser M is rejected when the current run
  uses paraphraser M' (M ≠ M').
- Cache payload carries the paraphraser model name so the check
  can be made.
- Older caches that predate the flag (no `paraphraser_model_name`
  key) are treated as same-model — backward compatible.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from symbolu_bcvf_llm.benchmark.dataset import TruthfulQABenchmark
from symbolu_bcvf_llm.sources.paraphrase import paraphrase_pipeline_version


def _fake_bench(
    *,
    cache_file: Path,
    model_name: str,
    paraphraser_model_name: str,
    split: str = "validation",
) -> TruthfulQABenchmark:
    """Instantiate TruthfulQABenchmark via __new__ and run only the
    cache-load block (a faithful copy of the real __init__ slice)."""
    bench = TruthfulQABenchmark.__new__(TruthfulQABenchmark)
    bench._paraphrase_cache = {}
    bench._paraphrase_hits = 0
    bench._paraphrase_misses = 0
    bench._paraphrase_max_new_tokens = 32
    bench._use_paraphrase = True
    bench._model_name = model_name
    bench._split = split
    bench._paraphrase_cache_file = cache_file
    bench._paraphrase_cache_loaded = 0
    bench._paraphrase_cache_discarded_reason = None
    bench._rewrite_seed_pair = (1, 2)
    bench._evaluation_seed = 1
    bench._model = object()
    bench._tokenizer = object()
    bench._paraphraser_model = bench._model
    bench._paraphraser_tokenizer = bench._tokenizer
    bench._paraphraser_model_name = paraphraser_model_name

    if not cache_file.exists():
        return bench

    current_version = paraphrase_pipeline_version()
    with open(cache_file) as fh:
        payload = json.load(fh)
    cached_version = payload.get("paraphrase_pipeline_version")
    model_ok = payload.get("model_name") == model_name
    cached_paraphraser = payload.get(
        "paraphraser_model_name", payload.get("model_name")
    )
    paraphraser_ok = cached_paraphraser == paraphraser_model_name
    split_ok = payload.get("split") == split
    version_ok = cached_version == current_version

    if model_ok and paraphraser_ok and split_ok and version_ok:
        for k, v in payload.get("entries", {}).items():
            row_str, seed_str = k.split("__", 1)
            bench._paraphrase_cache[(int(row_str), int(seed_str))] = v
        bench._paraphrase_cache_loaded = len(bench._paraphrase_cache)
    else:
        reasons = []
        if not paraphraser_ok:
            reasons.append(
                f"paraphraser_model_name mismatch "
                f"(cache={cached_paraphraser}, "
                f"current={paraphraser_model_name})"
            )
        bench._paraphrase_cache_discarded_reason = "; ".join(reasons)
    return bench


def _write_cache(
    path: Path, *, model_name: str, paraphraser_model_name: str,
    split: str = "validation", entries: dict = None,
    include_paraphraser_key: bool = True,
) -> None:
    payload = {
        "model_name": model_name,
        "split": split,
        "paraphrase_pipeline_version": paraphrase_pipeline_version(),
        "entries": entries or {"0__1": "precomputed"},
    }
    if include_paraphraser_key:
        payload["paraphraser_model_name"] = paraphraser_model_name
    path.write_text(json.dumps(payload))


def test_cache_accepts_matching_paraphraser(tmp_path: Path):
    cache = tmp_path / "c.json"
    _write_cache(
        cache, model_name="base", paraphraser_model_name="para",
    )
    bench = _fake_bench(
        cache_file=cache, model_name="base", paraphraser_model_name="para",
    )
    assert bench._paraphrase_cache_loaded == 1
    assert bench._paraphrase_cache_discarded_reason is None


def test_cache_rejects_different_paraphraser(tmp_path: Path):
    cache = tmp_path / "c.json"
    _write_cache(
        cache, model_name="base", paraphraser_model_name="paraphraser_A",
    )
    bench = _fake_bench(
        cache_file=cache,
        model_name="base",
        paraphraser_model_name="paraphraser_B",
    )
    assert bench._paraphrase_cache_loaded == 0
    assert "paraphraser_model_name mismatch" in (
        bench._paraphrase_cache_discarded_reason or ""
    )


def test_cache_backward_compat_missing_paraphraser_key(tmp_path: Path):
    """Old caches (pre-cross-model flag) don't carry
    `paraphraser_model_name`. They're treated as same-model — the
    paraphraser is assumed to equal the base model."""
    cache = tmp_path / "c.json"
    _write_cache(
        cache, model_name="legacy-base", paraphraser_model_name="ignored",
        include_paraphraser_key=False,
    )
    # Current run: same-model configuration (paraphraser == base).
    bench = _fake_bench(
        cache_file=cache,
        model_name="legacy-base",
        paraphraser_model_name="legacy-base",
    )
    assert bench._paraphrase_cache_loaded == 1


def test_cache_backward_compat_old_cache_rejected_if_paraphraser_differs(
    tmp_path: Path,
):
    """Old cache, new run uses cross-model paraphraser — reject because
    the implicit same-model paraphraser of the old cache doesn't match
    the current run's explicit different paraphraser."""
    cache = tmp_path / "c.json"
    _write_cache(
        cache, model_name="m1", paraphraser_model_name="ignored",
        include_paraphraser_key=False,
    )
    bench = _fake_bench(
        cache_file=cache,
        model_name="m1",
        paraphraser_model_name="m2",  # different paraphraser now
    )
    assert bench._paraphrase_cache_loaded == 0
    assert "paraphraser_model_name mismatch" in (
        bench._paraphrase_cache_discarded_reason or ""
    )


def test_persist_paraphrase_cache_includes_paraphraser_name(tmp_path: Path):
    """The persisted cache payload must record which paraphraser model
    wrote it, so later runs can reject on mismatch."""
    cache_path = tmp_path / "c.json"
    bench = _fake_bench(
        cache_file=cache_path, model_name="mistral",
        paraphraser_model_name="qwen",
    )

    def fake_paraphrase(*args, **kwargs):
        return f"PARA_seed={kwargs['rewrite_seed']}"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        bench._get_or_create_paraphrase(
            row_id=3, base_prompt="Q?", rewrite_seed=1,
        )

    payload = json.loads(cache_path.read_text())
    assert payload["model_name"] == "mistral"
    assert payload["paraphraser_model_name"] == "qwen"
    assert payload["entries"] == {"3__1": "PARA_seed=1"}


def test_get_or_create_paraphrase_uses_paraphraser_model(tmp_path: Path):
    """When paraphraser != base, make_paraphrased_prompt must be called
    with the paraphraser's model and tokenizer, not the base model."""
    bench = _fake_bench(
        cache_file=tmp_path / "c.json", model_name="base",
        paraphraser_model_name="paraphraser",
    )
    paraphraser_model = object()
    paraphraser_tokenizer = object()
    bench._paraphraser_model = paraphraser_model
    bench._paraphraser_tokenizer = paraphraser_tokenizer

    received = {}

    def fake_paraphrase(model, tokenizer, prompt, **kwargs):
        received["model"] = model
        received["tokenizer"] = tokenizer
        return "paraphrased"

    with mock.patch(
        "symbolu_bcvf_llm.sources.paraphrase.make_paraphrased_prompt",
        side_effect=fake_paraphrase,
    ):
        bench._get_or_create_paraphrase(row_id=0, base_prompt="Q", rewrite_seed=1)

    assert received["model"] is paraphraser_model
    assert received["tokenizer"] is paraphraser_tokenizer
    # And explicitly NOT the base model
    assert received["model"] is not bench._model
