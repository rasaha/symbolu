#!/usr/bin/env python3
"""
HuggingFace-based real attention-trace extractor for PCAM (Phase 4).

Loads a small causal-LM via ``transformers.AutoModelForCausalLM``,
runs a prompt through it with ``output_attentions=True``, and emits a
``TraceEvent`` JSON list that can be replayed through
``simulator.pcam.trace.replay`` and the Phase 3 benchmark scripts.

Scope
-----
This extractor ships real per-block attention mass — not a
structural reconstruction. It runs in CPU mode by default so it can
execute on developer laptops without a GPU, and it targets small
models (GPT-2, tiny-LLaMA, etc.) by default so the whole run takes
seconds rather than minutes.

The output format is the same JSON schema the rest of the Phase 3
tooling already consumes:

    [
      {"kind": "register_sequence", "args": {"seq_id": 1}},
      {"kind": "set_phase", "args": {"seq_id": 1, "phase": "DECODE"}},
      {"kind": "ensure_block", "args": {...}},
      {"kind": "on_block_attention", "args": {"block_id": B, "attention_sum": X, "sequence_id": 1}},
      ...
    ]

Honesty notes
-------------
- Attention is aggregated across the last layer's heads by default.
  Multi-layer aggregation is a known follow-up (Phase 5+) and would
  change the attention-mass distribution.
- Block size defaults to 16 tokens (matches vllm_bridge and the
  Phase 1 default); override with ``--block-size``.
- The extractor runs on CPU by default. ``--device cuda`` uses
  GPU if available, but no GPU dependency is required.
- The model must fit in available memory. A 125M parameter model
  (``gpt2`` or ``facebook/opt-125m``) fits comfortably on CPU;
  larger models may OOM.

Dependency surface
------------------
- ``torch``
- ``transformers``

Neither is a PCAM runtime dependency. This script is the only place
in the benchmark tree that touches either. If either is absent,
the script fails clean via ``TraceExtractorUnavailable`` with an
install hint.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam.trace import EventKind, TraceEvent  # noqa: E402


__all__ = [
    "TraceExtractorUnavailable",
    "ensure_transformers_available",
    "ExtractedTrace",
    "extract_trace_from_prompt",
    "run",
    "main",
]


# ---------------------------------------------------------------------------
# Error surface
# ---------------------------------------------------------------------------


class TraceExtractorUnavailable(RuntimeError):
    """Raised when the HuggingFace extractor dependencies are missing."""


def ensure_transformers_available() -> None:
    """
    Importability probe for ``torch`` + ``transformers``. Runs at the
    start of every extraction call so the failure mode is a clear
    exception with an actionable hint.
    """
    missing: List[str] = []
    try:
        import torch  # noqa: F401
    except ImportError:
        missing.append("torch")
    try:
        import transformers  # noqa: F401
    except ImportError:
        missing.append("transformers")
    if missing:
        raise TraceExtractorUnavailable(
            f"HuggingFace trace extraction requires {', '.join(missing)}. "
            f"Install with `pip install {' '.join(missing)}`. The rest of "
            "the PCAM benchmark tree does not require torch or "
            "transformers — only this script does."
        )


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ExtractedTrace:
    trace: List[TraceEvent]
    model: str
    prompt: str
    num_tokens: int
    num_blocks: int
    block_size: int
    per_block_attention: Dict[int, float]

    def to_json(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.trace]


# ---------------------------------------------------------------------------
# Attention → TraceEvent conversion
# ---------------------------------------------------------------------------


def _attention_to_block_mass(
    attention_matrix_last_layer: Any,  # torch.Tensor shape [batch, heads, seq, seq]
    block_size: int,
) -> Dict[int, float]:
    """
    Reduce a last-layer attention tensor to per-block attention mass.

    Strategy: average across heads, sum attention RECEIVED by each
    key position, then bucket positions into blocks of ``block_size``
    and sum the per-position mass per block. The result is a dict
    ``{block_id: attention_sum}`` for every block that appears in
    the input sequence.

    Kept in a separate function so it can be unit-tested with a
    mock tensor (see ``test_phase4_realtime.py``).
    """
    # Work with a list-of-lists float view so this function doesn't
    # need torch imported at module load. Callers convert their
    # torch tensor via ``.detach().cpu().tolist()`` before calling.
    try:
        import torch  # noqa: F401
        if hasattr(attention_matrix_last_layer, "detach"):
            attention_matrix_last_layer = (
                attention_matrix_last_layer.detach().cpu().tolist()
            )
    except ImportError:  # pragma: no cover — covered by ensure_transformers_available
        pass

    # Shape: [batch, heads, seq, seq]. We take batch 0.
    head_matrices = attention_matrix_last_layer[0]
    num_heads = len(head_matrices)
    seq_len = len(head_matrices[0]) if num_heads > 0 else 0

    # Average across heads, sum attention RECEIVED per key position.
    per_key_mass = [0.0] * seq_len
    for h in range(num_heads):
        head = head_matrices[h]
        for q in range(seq_len):
            row = head[q]
            for k in range(seq_len):
                per_key_mass[k] += float(row[k])
    if num_heads > 0:
        per_key_mass = [m / num_heads for m in per_key_mass]

    # Bucket into blocks.
    per_block: Dict[int, float] = {}
    for pos, mass in enumerate(per_key_mass):
        block_id = pos // block_size
        per_block[block_id] = per_block.get(block_id, 0.0) + mass
    return per_block


def _events_from_block_attention(
    per_block_attention: Dict[int, float],
    block_size: int,
    sink_tokens: int,
    seq_id: int = 1,
) -> List[TraceEvent]:
    """
    Build a ``TraceEvent`` list from a per-block attention-mass
    dict. One ``ensure_block`` per block, one ``on_block_attention``
    per block, plus the sequence lifecycle events.
    """
    events: List[TraceEvent] = [
        TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": seq_id}),
        TraceEvent(
            EventKind.SET_PHASE,
            {"seq_id": seq_id, "phase": "DECODE"},
        ),
    ]
    for block_id in sorted(per_block_attention.keys()):
        if block_id == 0:
            positions = list(range(min(sink_tokens, block_size)))
        else:
            positions = [block_id * block_size]
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
    for block_id in sorted(per_block_attention.keys()):
        events.append(
            TraceEvent(
                EventKind.ON_BLOCK_ATTENTION,
                {
                    "block_id": block_id,
                    "attention_sum": float(per_block_attention[block_id]),
                    "sequence_id": seq_id,
                },
            )
        )
    events.append(
        TraceEvent(EventKind.COMPLETE_SEQUENCE, {"seq_id": seq_id})
    )
    return events


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_trace_from_prompt(
    model: str,
    prompt: str,
    *,
    block_size: int = 16,
    sink_tokens: int = 4,
    device: str = "cpu",
) -> ExtractedTrace:
    """
    Load a HuggingFace causal LM, run ``prompt`` through it with
    ``output_attentions=True``, and emit an ``ExtractedTrace``.

    Raises ``TraceExtractorUnavailable`` if ``torch`` or
    ``transformers`` is missing. Any other failure (OOM, model not
    found, unsupported architecture) propagates as whatever the
    underlying library raised — the extractor does not swallow
    unrelated errors.
    """
    ensure_transformers_available()
    import torch  # pragma: no cover  (env-dependent)
    from transformers import AutoModelForCausalLM, AutoTokenizer  # pragma: no cover

    tokenizer = AutoTokenizer.from_pretrained(model)  # pragma: no cover
    # attn_implementation="eager" is required for output_attentions=True
    # to work on transformers >= 4.36 where SDPA is the default attention
    # kernel. SDPA intentionally does not return attention weights. The
    # eager attention path is slower but is the only implementation that
    # exposes per-layer attention tensors, which the extractor needs.
    hf_model = AutoModelForCausalLM.from_pretrained(  # pragma: no cover
        model, output_attentions=True, attn_implementation="eager"
    )
    hf_model.to(device)  # pragma: no cover
    hf_model.eval()  # pragma: no cover

    inputs = tokenizer(prompt, return_tensors="pt").to(device)  # pragma: no cover
    with torch.no_grad():  # pragma: no cover
        outputs = hf_model(**inputs, output_attentions=True)

    attentions = outputs.attentions  # pragma: no cover  (tuple of per-layer tensors)
    if not attentions:  # pragma: no cover
        raise RuntimeError(
            f"Model {model!r} did not return attention outputs. "
            "Ensure the architecture supports output_attentions=True."
        )
    last_layer = attentions[-1]  # pragma: no cover
    per_block = _attention_to_block_mass(last_layer, block_size)  # pragma: no cover
    num_tokens = int(inputs["input_ids"].shape[1])  # pragma: no cover
    events = _events_from_block_attention(  # pragma: no cover
        per_block, block_size=block_size, sink_tokens=sink_tokens
    )
    return ExtractedTrace(  # pragma: no cover
        trace=events,
        model=model,
        prompt=prompt,
        num_tokens=num_tokens,
        num_blocks=len(per_block),
        block_size=block_size,
        per_block_attention=per_block,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract a real attention trace from a HuggingFace "
                    "causal LM and emit a PCAM-compatible TraceEvent JSON.",
    )
    p.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name or local path (default: gpt2).",
    )
    p.add_argument(
        "--prompt", type=str,
        default="The quick brown fox jumps over the lazy dog.",
        help="Prompt to run through the model.",
    )
    p.add_argument(
        "--block-size", type=int, default=16,
        help="Tokens per block (default: 16, matches PCAM default).",
    )
    p.add_argument(
        "--sink-tokens", type=int, default=4,
        help="Sink token count for the first block (default: 4).",
    )
    p.add_argument(
        "--device", type=str, default="cpu",
        help="Device for the forward pass (default: cpu).",
    )
    p.add_argument(
        "--out", type=Path, required=True,
        help="Output path for the TraceEvent JSON list.",
    )
    return p


def run(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)
    try:
        extracted = extract_trace_from_prompt(
            model=args.model,
            prompt=args.prompt,
            block_size=args.block_size,
            sink_tokens=args.sink_tokens,
            device=args.device,
        )
    except TraceExtractorUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(extracted.to_json(), indent=2))  # pragma: no cover
    print(  # pragma: no cover
        f"wrote {len(extracted.trace)} events ({extracted.num_blocks} blocks, "
        f"{extracted.num_tokens} tokens) from {args.model!r} to {args.out}"
    )
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
