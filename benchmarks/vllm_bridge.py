"""
vLLM real-runtime bridge for PCAM (Phase 4).

This module provides a narrow, lazy-import path for running a real
``vllm`` inference and deriving a ``TraceEvent`` stream that can then
be replayed through PCAM. It is NOT imported at package load, and it
does NOT take a runtime dependency on ``vllm``. The heavy import
happens inside ``generate_with_derived_trace`` the first time a real
run is requested.

Scope — "shadow mode", not "active eviction control"
----------------------------------------------------
Phase 4 runs vLLM with its default eviction policy and derives a
PCAM-compatible trace from the observable sequence structure
(prompt lengths, generated token counts, sequence ids). That trace
is then replayed through ``simulator.pcam.kv_policy.KVCachePolicy``
so PCAM can report what it *would* have done on the same workload.

This is deliberately "shadow mode":

- It exercises a real model on real inputs.
- It produces policy-decision numbers that are honest — PCAM really
  did run against a real-vLLM-shaped workload.
- It does NOT patch vLLM's internal evictor. Patching vLLM's
  ``BlockSpaceManager`` is fragile across vLLM releases and was
  explicitly scoped out of Phase 4.

A future "active mode" phase will add a ``vllm.core.evictor`` ABC
subclass and a small monkey-patch that installs PCAM as vLLM's real
eviction policy. That phase is not this one.

Honesty notes
-------------
- The derived trace is a structural reconstruction, not a per-layer
  attention capture. Block admissions come from the observed
  (prompt_length + completion_length) // block_size. Attention
  events are synthesized as uniform-weight touches per generated
  token — this is a correct "the block was touched at decode step N"
  signal, but it is NOT the per-block attention mass a model hook
  would give you. For that, see ``pcam_trace_extract.py``, which
  uses HuggingFace forward hooks on a separate model run.
- Sink tokens are derived from the PCAM default (positions < 4);
  this matches the Phase 1 convention.
- No model weights ship with this file. The caller must provide a
  model name that vLLM can download or load from disk, and a GPU
  with enough VRAM to host it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Ensure simulator.pcam is importable when this file is used from either
# the repo root or from inside benchmarks/.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam.trace import EventKind, TraceEvent  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from simulator.pcam.kv_policy import InferencePhase  # noqa: F401


__all__ = [
    "VLLMBridgeUnavailable",
    "ensure_vllm_available",
    "DerivedRunResult",
    "generate_with_derived_trace",
]


# ---------------------------------------------------------------------------
# Error surface
# ---------------------------------------------------------------------------


class VLLMBridgeUnavailable(RuntimeError):
    """
    Raised when a real-vLLM code path is requested but cannot be run.

    Three distinct reasons can trigger this:

    1. ``vllm`` is not installed.
    2. ``vllm`` is installed but the import itself fails (e.g. CUDA
       mismatch, missing shared libraries, unsupported Python version).
    3. The requested model cannot be loaded on the current hardware.

    The exception message always includes an actionable hint so a
    demo user is never left guessing.
    """


def ensure_vllm_available() -> None:
    """
    Importability probe with an actionable error. Callers run this at
    the start of a real-vLLM code path so the failure mode is a
    clear exception rather than a confusing ImportError from deep in
    downstream code.
    """
    try:
        import vllm  # noqa: F401  # pragma: no cover  (env-dependent)
    except ImportError as exc:
        raise VLLMBridgeUnavailable(
            "vllm is not installed. Install with `pip install vllm` "
            "(requires a CUDA-capable GPU and a supported CUDA runtime). "
            "The PCAM synthetic demo path does not require vllm — run "
            "`python benchmarks/pcam_vllm_demo.py` without --real-vllm "
            "to exercise the adapter without a real model."
        ) from exc
    except Exception as exc:  # pragma: no cover  (env-dependent)
        # vllm is importable but blew up on load — usually a CUDA or
        # shared-library mismatch. Surface the root cause cleanly.
        raise VLLMBridgeUnavailable(
            f"vllm is installed but failed to import: {type(exc).__name__}: "
            f"{exc}. This is usually a CUDA version mismatch or a missing "
            "shared library. Check `python -c 'import vllm'` interactively "
            "for the full traceback."
        ) from exc


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class DerivedRunResult:
    """
    Structured result of a ``generate_with_derived_trace`` call.

    - ``trace``: the derived ``TraceEvent`` list, ready to feed into
      ``simulator.pcam.trace.replay``
    - ``prompts``: the prompts as given
    - ``completions``: the text vLLM produced for each prompt
    - ``prompt_token_counts``: per-prompt input token counts
    - ``completion_token_counts``: per-prompt output token counts
    - ``model``: the model name that was loaded
    - ``block_size``: the block granularity used to derive admissions
    """

    trace: List[TraceEvent]
    prompts: List[str]
    completions: List[str]
    prompt_token_counts: List[int]
    completion_token_counts: List[int]
    model: str
    block_size: int

    def summary(self) -> Dict[str, Any]:
        """Flat metric dict suitable for the Phase 3 reporting helper."""
        return {
            "model": self.model,
            "block_size": self.block_size,
            "num_prompts": len(self.prompts),
            "total_prompt_tokens": sum(self.prompt_token_counts),
            "total_completion_tokens": sum(self.completion_token_counts),
            "derived_events": len(self.trace),
        }


# ---------------------------------------------------------------------------
# Trace derivation
# ---------------------------------------------------------------------------


def _derive_trace_from_vllm_run(
    prompt_token_counts: List[int],
    completion_token_counts: List[int],
    block_size: int,
    sink_tokens: int = 4,
) -> List[TraceEvent]:
    """
    Build a ``TraceEvent`` list from observed vLLM sequence shapes.

    Structural reconstruction only — this does not capture per-layer
    attention. One sequence per prompt; each sequence's blocks are
    derived from ``ceil((prompt_tokens + completion_tokens) / block_size)``.
    The first block of each sequence is treated as the sink block
    (positions ``0..sink_tokens-1``); subsequent blocks are
    non-sink. Each generated token contributes one uniform-weight
    attention event against the block it falls into.
    """
    events: List[TraceEvent] = []
    next_block_id = 0

    for seq_idx, (p_tokens, c_tokens) in enumerate(
        zip(prompt_token_counts, completion_token_counts)
    ):
        seq_id = seq_idx + 1
        total_tokens = p_tokens + c_tokens
        if total_tokens <= 0:
            continue
        num_blocks = (total_tokens + block_size - 1) // block_size

        events.append(
            TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": seq_id})
        )
        events.append(
            TraceEvent(
                EventKind.SET_PHASE,
                {"seq_id": seq_id, "phase": "PREFILL"},
            )
        )

        sequence_block_ids: List[int] = []
        for b in range(num_blocks):
            block_id = next_block_id
            next_block_id += 1
            sequence_block_ids.append(block_id)

            # Positions for this block — 0..sink_tokens-1 for the
            # first block in the sequence triggers PCAM's sink path.
            if b == 0:
                positions = list(range(min(sink_tokens, block_size)))
            else:
                positions = [b * block_size]

            events.append(
                TraceEvent(
                    EventKind.ENSURE_BLOCK,
                    {
                        "block_id": block_id,
                        "sequence_id": seq_id,
                        "positions": positions,
                    },
                )
            )

        # Transition to decode after prefill is accounted for.
        events.append(
            TraceEvent(
                EventKind.SET_PHASE,
                {"seq_id": seq_id, "phase": "DECODE"},
            )
        )

        # Each generated token contributes one uniform attention
        # event on the block it landed in. The attention weight is
        # intentionally low (0.05) because this is a structural
        # proxy, not a measured attention mass.
        for t in range(c_tokens):
            absolute_pos = p_tokens + t
            block_index = absolute_pos // block_size
            if block_index >= len(sequence_block_ids):
                break
            events.append(
                TraceEvent(
                    EventKind.ON_BLOCK_ATTENTION,
                    {
                        "block_id": sequence_block_ids[block_index],
                        "attention_sum": 0.05,
                        "sequence_id": seq_id,
                    },
                )
            )

        events.append(
            TraceEvent(
                EventKind.COMPLETE_SEQUENCE, {"seq_id": seq_id}
            )
        )

    return events


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_with_derived_trace(
    model: str,
    prompts: List[str],
    *,
    max_tokens: int = 64,
    block_size: int = 16,
    sink_tokens: int = 4,
    dtype: Optional[str] = None,
    trust_remote_code: bool = False,
) -> DerivedRunResult:
    """
    Run a real ``vllm.LLM.generate`` call against ``model`` on
    ``prompts`` and derive a ``TraceEvent`` list from the observed
    sequence shapes.

    Raises ``VLLMBridgeUnavailable`` if vLLM is not importable or the
    model cannot be loaded. Callers should treat this as a clean
    failure path — do NOT fall back to a synthetic trace and silently
    label it as real.

    The returned ``DerivedRunResult.trace`` is a structural
    reconstruction: admissions from block layout, attention events
    from token counts. For richer per-block attention mass, use
    ``pcam_trace_extract.py`` (HuggingFace hook-based) instead.
    """
    ensure_vllm_available()
    try:  # pragma: no cover  (env-dependent)
        from vllm import LLM, SamplingParams
    except Exception as exc:  # pragma: no cover
        raise VLLMBridgeUnavailable(
            f"vllm import failed after ensure_vllm_available succeeded: {exc}"
        ) from exc

    llm_kwargs: Dict[str, Any] = {"model": model}
    if dtype is not None:
        llm_kwargs["dtype"] = dtype
    if trust_remote_code:
        llm_kwargs["trust_remote_code"] = True

    try:  # pragma: no cover  (env-dependent)
        llm = LLM(**llm_kwargs)
    except Exception as exc:  # pragma: no cover
        raise VLLMBridgeUnavailable(
            f"vllm.LLM({model!r}) failed to load: {type(exc).__name__}: {exc}. "
            "Common causes: insufficient GPU memory, model name not found, "
            "or missing --trust-remote-code for custom architectures."
        ) from exc

    sampling_params = SamplingParams(max_tokens=max_tokens)
    outputs = llm.generate(prompts, sampling_params)

    prompt_token_counts: List[int] = []
    completion_token_counts: List[int] = []
    completions: List[str] = []
    for output in outputs:  # pragma: no cover  (env-dependent)
        prompt_token_counts.append(len(output.prompt_token_ids))
        first = output.outputs[0]
        completion_token_counts.append(len(first.token_ids))
        completions.append(first.text)

    trace = _derive_trace_from_vllm_run(
        prompt_token_counts=prompt_token_counts,
        completion_token_counts=completion_token_counts,
        block_size=block_size,
        sink_tokens=sink_tokens,
    )

    return DerivedRunResult(
        trace=trace,
        prompts=list(prompts),
        completions=completions,
        prompt_token_counts=prompt_token_counts,
        completion_token_counts=completion_token_counts,
        model=model,
        block_size=block_size,
    )
