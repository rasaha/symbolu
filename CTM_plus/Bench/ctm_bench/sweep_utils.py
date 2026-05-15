"""Shared utilities for the §20 sweep harnesses.

Three concerns, one home:

1. **Atomic partial JSON writes** — `save_partial_json(summary, path)`.
   The three sweep scripts each collect many trial rows in memory and
   write the JSON once at end. A crash mid-sweep (OOM at long context,
   tokenizer hitting an unsupported model variant, a flaky GPU node)
   would otherwise lose all accumulated data. The atomic-rename pattern
   writes the current state to `<path>.partial` then `os.replace`s it
   onto `<path>` so the operator always sees a valid JSON reflecting
   completed work.

2. **`max_position_embeddings` guards** — `check_context_window(...)`.
   Long-context sweeps + throughput sweeps both accept user-supplied
   token-count lengths. A request beyond the model's positional
   encoding window crashes mid-prefill with an opaque CUDA error. The
   helper splits the requested lengths into (allowed, skipped) and
   logs the boundary so the operator sees the issue before paying for
   the crash.

3. **CUDA memory cleanup** — `cleanup_cuda_after_trial(*tensors)`.
   The KV cache in the long-context harness can hold 16+ GB at 32k.
   PyTorch's caching allocator may hold fragmented buffers across
   trials; explicit `del`+`empty_cache()` after each trial returns
   them to the OS. No-op on CPU dry-runs.

Used by:
  * `ctm_bench/scripts/track_e_throughput.py`
  * `ctm_bench/scripts/sink_fp16_sweep.py`
  * `ctm_bench/scripts/track_e_long_context.py`
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

LOG = logging.getLogger("sweep_utils")


def save_partial_json(summary: Any, path: Path) -> None:
    """Atomically write `summary` (a dataclass or dict) to `path`.

    Writes to `<path>.partial` first, then `os.replace`s it onto
    `<path>`. The replace is atomic on POSIX (same filesystem); a
    reader observing `path` always sees either the previous valid
    contents or the new valid contents, never a half-written file.

    Idempotent: calling this every loop iteration is fine. The
    operator's last successful write IS the final artefact if the
    script crashes; no separate finalization needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(summary) if is_dataclass(summary) else summary
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def check_context_window(
    *,
    model: Any,
    requested_tokens: Sequence[int],
) -> tuple[list[int], list[int], Optional[int]]:
    """Filter `requested_tokens` against `model.config.max_position_embeddings`.

    Returns ``(allowed, skipped, max_pos)``:
      * `allowed`: lengths the model can handle. Use these for the sweep.
      * `skipped`: lengths that exceed max_pos (would crash mid-prefill).
      * `max_pos`: the model's window, or None if the config doesn't
        expose it (in which case all requested lengths pass through
        and the caller continues at their own risk).

    Logs a WARNING for each skipped length so the operator sees it
    in stdout before the sweep starts.

    Does NOT raise. The caller decides whether to abort or proceed
    with the filtered set — for a multi-axis sweep, dropping the
    over-window lengths and continuing is usually better than aborting
    the whole run.
    """
    max_pos = None
    cfg = getattr(model, "config", None)
    if cfg is not None:
        max_pos = getattr(cfg, "max_position_embeddings", None)
    if max_pos is None:
        return list(requested_tokens), [], None
    allowed = [n for n in requested_tokens if n <= int(max_pos)]
    skipped = [n for n in requested_tokens if n > int(max_pos)]
    if skipped:
        LOG.warning(
            "Requested context lengths %s exceed model.config."
            "max_position_embeddings=%d; skipping these cells. "
            "Use rope_scaling-extended models for longer contexts.",
            skipped, int(max_pos),
        )
    return allowed, skipped, int(max_pos)


def cleanup_cuda_after_trial(*tensors_to_drop: Any) -> None:
    """Explicit cleanup after a single trial. Helps long-context loops
    where the cumulative KV-cache + activations can fragment the
    caching allocator across trials.

    Args:
        *tensors_to_drop: optional handles to derefence explicitly
            before calling `empty_cache()`. Most call sites have a
            `cache` and an `out` to drop; pass them so the GC sees
            the dereference before the cleanup runs.

    No-op on CPU (and when torch isn't installed). Safe to call from
    dry-run paths.
    """
    try:
        import torch  # type: ignore
    except ImportError:
        return
    # Drop references explicitly so the next `empty_cache` returns
    # the underlying buffers.
    for t in tensors_to_drop:
        del t  # noqa: F841 — explicit derefence for the caller
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
