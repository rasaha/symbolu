"""Regression tests for the shared `ctm_bench.sweep_utils` helpers.

Pins:

* `save_partial_json` does an ATOMIC write (no half-written file ever
  visible at the target path).
* `save_partial_json` accepts both dataclasses and dicts.
* `check_context_window` filters lengths against
  `model.config.max_position_embeddings` and logs a warning for
  skipped ones.
* `check_context_window` returns (all, [], None) when the model has
  no `config.max_position_embeddings` (e.g., the fake tiny model);
  dry-run paths must still work.
* `cleanup_cuda_after_trial` is a no-op on CPU and safe to call
  without arguments.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest


def test_save_partial_json_writes_dict(tmp_path: Path):
    """`save_partial_json` accepts a plain dict."""
    from ctm_bench.sweep_utils import save_partial_json
    path = tmp_path / "out.json"
    save_partial_json({"a": 1, "b": [2, 3]}, path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data == {"a": 1, "b": [2, 3]}


def test_save_partial_json_writes_dataclass(tmp_path: Path):
    """`save_partial_json` accepts a dataclass via `asdict`."""
    from ctm_bench.sweep_utils import save_partial_json

    @dataclass
    class _Summary:
        schema_version: str = "test.v1"
        rows: List[int] = field(default_factory=list)

    s = _Summary(rows=[1, 2, 3])
    path = tmp_path / "out.json"
    save_partial_json(s, path)
    data = json.loads(path.read_text())
    assert data["schema_version"] == "test.v1"
    assert data["rows"] == [1, 2, 3]


def test_save_partial_json_cleans_up_partial_file(tmp_path: Path):
    """After a successful write, no `<path>.partial` should remain.
    The atomic-rename moves it onto the target."""
    from ctm_bench.sweep_utils import save_partial_json
    path = tmp_path / "out.json"
    save_partial_json({"a": 1}, path)
    assert path.exists()
    assert not (tmp_path / "out.json.partial").exists()


def test_save_partial_json_idempotent_for_loop_callers(tmp_path: Path):
    """Calling repeatedly with growing data is the expected sweep
    pattern — each call should overwrite cleanly."""
    from ctm_bench.sweep_utils import save_partial_json
    path = tmp_path / "out.json"
    for i in range(5):
        save_partial_json({"step": i, "cells": list(range(i))}, path)
    data = json.loads(path.read_text())
    assert data["step"] == 4
    assert data["cells"] == [0, 1, 2, 3]


def test_save_partial_json_creates_parent_dirs(tmp_path: Path):
    """Output parent doesn't need to exist; the helper creates it."""
    from ctm_bench.sweep_utils import save_partial_json
    path = tmp_path / "deep" / "nested" / "out.json"
    save_partial_json({"a": 1}, path)
    assert path.exists()


def test_check_context_window_filters_over_max_pos(caplog):
    """Lengths beyond `max_position_embeddings` are returned in the
    skipped list and a warning is logged."""
    from ctm_bench.sweep_utils import check_context_window

    class _Cfg:
        max_position_embeddings = 8192

    class _Model:
        config = _Cfg()

    import logging
    with caplog.at_level(logging.WARNING, logger="sweep_utils"):
        allowed, skipped, max_pos = check_context_window(
            model=_Model(), requested_tokens=[4096, 8192, 16384, 32768],
        )
    assert allowed == [4096, 8192]
    assert skipped == [16384, 32768]
    assert max_pos == 8192
    # Warning was emitted naming the skipped values.
    assert any(
        "16384" in record.message and "exceed" in record.message
        for record in caplog.records
    )


def test_check_context_window_passes_through_when_no_config():
    """A model without `config.max_position_embeddings` (e.g., the
    fake tiny model used in dry-runs) gets all lengths passed through
    unchanged — the caller continues at their own risk."""
    from ctm_bench.sweep_utils import check_context_window

    class _ModelNoConfig:
        pass

    allowed, skipped, max_pos = check_context_window(
        model=_ModelNoConfig(), requested_tokens=[1024, 8192, 32768],
    )
    assert allowed == [1024, 8192, 32768]
    assert skipped == []
    assert max_pos is None


def test_check_context_window_returns_empty_when_all_over_limit():
    """Pathological case: every requested length exceeds the window.
    Returns ([], all, max_pos); the caller decides whether to abort."""
    from ctm_bench.sweep_utils import check_context_window

    class _Cfg:
        max_position_embeddings = 2048

    class _Model:
        config = _Cfg()

    allowed, skipped, max_pos = check_context_window(
        model=_Model(), requested_tokens=[4096, 8192],
    )
    assert allowed == []
    assert skipped == [4096, 8192]
    assert max_pos == 2048


def test_cleanup_cuda_after_trial_no_args_safe():
    """Helper must be callable without args."""
    from ctm_bench.sweep_utils import cleanup_cuda_after_trial
    cleanup_cuda_after_trial()  # no-op on CPU; must not raise


def test_cleanup_cuda_after_trial_with_tensor_args_safe():
    """Helper accepts arbitrary objects to be dereferenced."""
    from ctm_bench.sweep_utils import cleanup_cuda_after_trial
    obj1, obj2 = object(), object()
    cleanup_cuda_after_trial(obj1, obj2)  # no-op + deref; must not raise
