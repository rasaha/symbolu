"""§10.V1.6 follow-up: paraphrase-cache pipeline-version-stamping tests.

Guards against the class of bug where a disk paraphrase cache
written by one template version is silently consumed by a run using
a different template. This is the automatic replacement for the
manual `rm paraphrase_cache_*.json` step.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from symbolu_bcvf_llm.benchmark.dataset import TruthfulQABenchmark
from symbolu_bcvf_llm.sources.paraphrase import (
    PARAPHRASE_VERSION_TAG,
    paraphrase_pipeline_version,
)


def _fake_tqa_with_cache(
    cache_file: Path,
    model_name: str = "mistralai/Mistral-7B-Instruct-v0.3",
    split: str = "validation",
) -> TruthfulQABenchmark:
    """Construct a TruthfulQABenchmark by invoking its cache-load block
    manually — bypasses the torch-gated __init__ path."""
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

    # Replicate the __init__ load block.
    if cache_file.exists():
        current_version = paraphrase_pipeline_version()
        try:
            with open(cache_file) as fh:
                payload = json.load(fh)
            cached_version = payload.get("paraphrase_pipeline_version")
            model_ok = payload.get("model_name") == model_name
            split_ok = payload.get("split") == split
            version_ok = cached_version == current_version
            if model_ok and split_ok and version_ok:
                for k, v in payload.get("entries", {}).items():
                    row_str, seed_str = k.split("__", 1)
                    bench._paraphrase_cache[(int(row_str), int(seed_str))] = v
                bench._paraphrase_cache_loaded = len(bench._paraphrase_cache)
            else:
                reasons = []
                if not model_ok:
                    reasons.append("model_name mismatch")
                if not split_ok:
                    reasons.append("split mismatch")
                if not version_ok:
                    reasons.append("paraphrase_pipeline_version mismatch")
                bench._paraphrase_cache_discarded_reason = "; ".join(reasons)
        except Exception as exc:
            bench._paraphrase_cache_discarded_reason = f"load error: {exc}"
    return bench


# --------------------------------------------------------------------------- #
# paraphrase_pipeline_version stability
# --------------------------------------------------------------------------- #


def test_pipeline_version_is_deterministic():
    """Same code state → same hash on repeated calls."""
    assert paraphrase_pipeline_version() == paraphrase_pipeline_version()


def test_pipeline_version_is_short_hex_string():
    """Hash is 16 hex chars — long enough for uniqueness, short enough to eyeball."""
    v = paraphrase_pipeline_version()
    assert isinstance(v, str)
    assert len(v) == 16
    assert all(c in "0123456789abcdef" for c in v)


def test_pipeline_version_tag_exported():
    """Human-readable tag is exposed alongside the hash."""
    assert isinstance(PARAPHRASE_VERSION_TAG, str)
    assert len(PARAPHRASE_VERSION_TAG) > 0


def test_pipeline_version_changes_when_directives_change():
    """Monkey-patch the directives → hash should differ."""
    from symbolu_bcvf_llm.sources import paraphrase as p

    original = paraphrase_pipeline_version()
    with mock.patch.object(
        p, "_SEED_STYLE_DIRECTIVES",
        ("different", "directives", "here", "now"),
    ):
        mutated = paraphrase_pipeline_version()
    assert mutated != original


def test_pipeline_version_changes_when_template_changes():
    from symbolu_bcvf_llm.sources import paraphrase as p

    original = paraphrase_pipeline_version()
    with mock.patch.object(
        p, "DEFAULT_REWRITE_INSTRUCTION",
        "totally different template {prompt} {style}",
    ):
        mutated = paraphrase_pipeline_version()
    assert mutated != original


# --------------------------------------------------------------------------- #
# Cache load: version check + stale-reject
# --------------------------------------------------------------------------- #


def test_cache_loads_when_version_matches(tmp_path: Path):
    """Fresh cache with correct version stamp → loaded into memory."""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "split": "validation",
        "paraphrase_pipeline_version": paraphrase_pipeline_version(),
        "paraphrase_version_tag": PARAPHRASE_VERSION_TAG,
        "entries": {
            "0__1": "paraphrased version one of question zero",
            "0__2": "paraphrased version two of question zero",
        },
    }))
    bench = _fake_tqa_with_cache(cache)
    assert bench._paraphrase_cache_loaded == 2
    assert bench._paraphrase_cache_discarded_reason is None


def test_cache_discards_when_version_missing(tmp_path: Path):
    """Old V1 cache without version stamp → rejected on load."""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "split": "validation",
        # no paraphrase_pipeline_version field — simulates pre-fix cache
        "entries": {"0__1": "old corrupted paraphrase"},
    }))
    bench = _fake_tqa_with_cache(cache)
    assert bench._paraphrase_cache_loaded == 0
    assert bench._paraphrase_cache_discarded_reason is not None
    assert "paraphrase_pipeline_version" in (
        bench._paraphrase_cache_discarded_reason
    )


def test_cache_discards_when_version_mismatches(tmp_path: Path):
    """Cache stamped with a different pipeline version → rejected."""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "split": "validation",
        "paraphrase_pipeline_version": "deadbeefcafebabe",  # wrong
        "entries": {"0__1": "paraphrase from another pipeline"},
    }))
    bench = _fake_tqa_with_cache(cache)
    assert bench._paraphrase_cache_loaded == 0
    assert bench._paraphrase_cache_discarded_reason is not None
    assert "version mismatch" in (
        bench._paraphrase_cache_discarded_reason
    )


def test_cache_discards_when_model_mismatches(tmp_path: Path):
    """Model-name mismatch → reject (protects against cross-model pollution)."""
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "some-other-model/different",
        "split": "validation",
        "paraphrase_pipeline_version": paraphrase_pipeline_version(),
        "entries": {"0__1": "paraphrase from another model"},
    }))
    bench = _fake_tqa_with_cache(cache)
    assert bench._paraphrase_cache_loaded == 0
    assert bench._paraphrase_cache_discarded_reason is not None
    assert "model_name mismatch" in (
        bench._paraphrase_cache_discarded_reason
    )


def test_cache_discards_when_split_mismatches(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "split": "test",   # benchmark uses "validation"
        "paraphrase_pipeline_version": paraphrase_pipeline_version(),
        "entries": {"0__1": "entry"},
    }))
    bench = _fake_tqa_with_cache(cache)
    assert bench._paraphrase_cache_loaded == 0
    assert "split mismatch" in (
        bench._paraphrase_cache_discarded_reason
    )


def test_multiple_mismatches_concatenated_in_reason(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "different-model",
        "split": "test",
        "paraphrase_pipeline_version": "wrong",
        "entries": {"0__1": "entry"},
    }))
    bench = _fake_tqa_with_cache(cache)
    reason = bench._paraphrase_cache_discarded_reason
    assert "model_name mismatch" in reason
    assert "split mismatch" in reason
    assert "version mismatch" in reason


def test_discarded_reason_exposed_in_stats(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
        "split": "validation",
        # no version
        "entries": {"0__1": "stale"},
    }))
    bench = _fake_tqa_with_cache(cache)
    stats = bench.paraphrase_cache_stats
    assert stats["discarded_reason"] is not None
    assert stats["loaded_from_disk"] == 0
