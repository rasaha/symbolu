"""Long-context workload generators.

Three patterns relevant to the NAND-tier story:

* :func:`generate_agentic` — tool-use re-read pattern. The
  scratchpad blocks (early system prompt + recent tool outputs)
  are re-read on every step. Stresses recency + sink protection.

* :func:`generate_rag` — one-shot retrieval pattern. Each
  retrieved chunk is prefilled and read once. Stresses
  scan-resistance: the policy must not let one-hit-wonders
  evict useful blocks.

* :func:`generate_chat` — multi-turn conversational pattern.
  Early system prompt is re-read every turn; recent turns are
  re-read with high attention; mid-context is read with low
  attention. Stresses attention-sink + entity classification.

Each generator yields :class:`TraceEvent` instances ordered by
logical timestamp. The generator is deterministic for a given
seed so a benchmark report is exactly reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Tuple


class AccessPattern(Enum):
    AGENTIC = "agentic"
    RAG = "rag"
    CHAT = "chat"


@dataclass(frozen=True)
class WorkloadSpec:
    """Pinned spec for one workload run. The full bench config
    stays in :mod:`policies`; this just describes the trace."""

    name: str
    pattern: AccessPattern
    n_concurrent_seqs: int
    context_length_tokens: int
    duration_decode_tokens: int
    block_size_tokens: int = 16
    seed: int = 42

    def __post_init__(self) -> None:
        for field_name, value in (
            ("n_concurrent_seqs", self.n_concurrent_seqs),
            ("context_length_tokens", self.context_length_tokens),
            ("duration_decode_tokens", self.duration_decode_tokens),
            ("block_size_tokens", self.block_size_tokens),
        ):
            if value <= 0:
                raise ValueError(
                    f"WorkloadSpec.{field_name} must be positive; got {value}"
                )

    def n_blocks_per_sequence(self) -> int:
        return (
            self.context_length_tokens + self.block_size_tokens - 1
        ) // self.block_size_tokens

    def total_unique_blocks(self) -> int:
        return self.n_concurrent_seqs * (
            self.n_blocks_per_sequence()
            + self.duration_decode_tokens // self.block_size_tokens
        )


@dataclass(frozen=True)
class TraceEvent:
    """One access event in the trace."""

    seq_id: int
    block_id: int
    position: int
    seq_len: int
    attention_weight: float
    is_prefill: bool


# Standard pinned workloads — used by the runner CLI by default.

AGENTIC_64K: WorkloadSpec = WorkloadSpec(
    name="agentic_64k",
    pattern=AccessPattern.AGENTIC,
    n_concurrent_seqs=4,
    context_length_tokens=64 * 1024,
    duration_decode_tokens=2048,
)

RAG_128K: WorkloadSpec = WorkloadSpec(
    name="rag_128k",
    pattern=AccessPattern.RAG,
    n_concurrent_seqs=2,
    context_length_tokens=128 * 1024,
    duration_decode_tokens=1024,
)

CHAT_32K: WorkloadSpec = WorkloadSpec(
    name="chat_32k",
    pattern=AccessPattern.CHAT,
    n_concurrent_seqs=8,
    context_length_tokens=32 * 1024,
    duration_decode_tokens=512,
)


# ---------------------------------------------------------------- #
# Generator helpers
# ---------------------------------------------------------------- #


def _block_id_for(seq_id: int, position: int, block_size: int, max_blocks_per_seq: int) -> int:
    """Stable block_id encoding: combine seq_id + block index so
    blocks across sequences never collide. Reserves 1024 sequence
    slots × max_blocks_per_seq."""
    block_index = position // block_size
    if block_index >= max_blocks_per_seq:
        # Decode-extension blocks live in a higher range.
        return seq_id * 100_000 + max_blocks_per_seq + (block_index - max_blocks_per_seq)
    return seq_id * 100_000 + block_index


def _prefill_events(
    spec: WorkloadSpec, seq_id: int
) -> Iterator[TraceEvent]:
    """Walk every token of the initial context once. Attention
    weight here is dominated by the future decode; we model
    prefill attention as low and approximately uniform."""
    bs = spec.block_size_tokens
    n_blocks_per_seq = spec.n_blocks_per_sequence()
    for pos in range(spec.context_length_tokens):
        block_id = _block_id_for(seq_id, pos, bs, n_blocks_per_seq)
        yield TraceEvent(
            seq_id=seq_id,
            block_id=block_id,
            position=pos,
            seq_len=spec.context_length_tokens,
            attention_weight=0.001,
            is_prefill=True,
        )


def generate_agentic(spec: WorkloadSpec) -> Iterator[TraceEvent]:
    """Tool-use pattern. After prefill, decode steps re-read:

    * Sink (positions 0 .. sink_tokens) every step.
    * The most recent ~10 blocks every step (current scratchpad).
    * One randomly-chosen earlier "tool output" block every
      ~5 steps (re-reads of relevant context).
    """
    if spec.pattern is not AccessPattern.AGENTIC:
        raise ValueError(
            f"generate_agentic given non-agentic spec: {spec.pattern}"
        )
    rng = random.Random(spec.seed)
    bs = spec.block_size_tokens
    n_blocks_per_seq = spec.n_blocks_per_sequence()

    for seq_id in range(spec.n_concurrent_seqs):
        yield from _prefill_events(spec, seq_id)

        # Decode steps: re-read sink + recent + occasional tool block.
        for step in range(spec.duration_decode_tokens):
            current_pos = spec.context_length_tokens + step
            current_seq_len = current_pos + 1
            current_block = _block_id_for(seq_id, current_pos, bs, n_blocks_per_seq)
            # Sink re-reads (high attention).
            for sink_pos in range(0, min(4, spec.context_length_tokens)):
                block_id = _block_id_for(
                    seq_id, sink_pos, bs, n_blocks_per_seq
                )
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=sink_pos,
                    seq_len=current_seq_len,
                    attention_weight=0.4,
                    is_prefill=False,
                )
            # Recent ~10 blocks (medium attention).
            recent_start = max(0, current_pos - 10 * bs)
            for pos in range(recent_start, current_pos + 1, bs):
                block_id = _block_id_for(seq_id, pos, bs, n_blocks_per_seq)
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=pos,
                    seq_len=current_seq_len,
                    attention_weight=0.15,
                    is_prefill=False,
                )
            # Occasional re-read of an earlier "tool output" block.
            if step % 5 == 0 and spec.context_length_tokens > 256:
                tool_pos = rng.randrange(
                    256, spec.context_length_tokens - 256
                )
                block_id = _block_id_for(seq_id, tool_pos, bs, n_blocks_per_seq)
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=tool_pos,
                    seq_len=current_seq_len,
                    attention_weight=0.25,
                    is_prefill=False,
                )
            # The newly-generated decode token itself.
            yield TraceEvent(
                seq_id=seq_id,
                block_id=current_block,
                position=current_pos,
                seq_len=current_seq_len,
                attention_weight=0.05,
                is_prefill=False,
            )


def generate_rag(spec: WorkloadSpec) -> Iterator[TraceEvent]:
    """RAG pattern. Long prefill (the retrieved chunks) followed
    by decode that re-reads only sinks + recent. Mid-context
    chunks are touched once during prefill and never again — the
    classic scan-resistance test case."""
    if spec.pattern is not AccessPattern.RAG:
        raise ValueError(
            f"generate_rag given non-RAG spec: {spec.pattern}"
        )
    bs = spec.block_size_tokens
    n_blocks_per_seq = spec.n_blocks_per_sequence()

    for seq_id in range(spec.n_concurrent_seqs):
        yield from _prefill_events(spec, seq_id)

        for step in range(spec.duration_decode_tokens):
            current_pos = spec.context_length_tokens + step
            current_seq_len = current_pos + 1
            current_block = _block_id_for(seq_id, current_pos, bs, n_blocks_per_seq)
            # Sink re-reads.
            for sink_pos in range(0, min(4, spec.context_length_tokens)):
                block_id = _block_id_for(
                    seq_id, sink_pos, bs, n_blocks_per_seq
                )
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=sink_pos,
                    seq_len=current_seq_len,
                    attention_weight=0.3,
                    is_prefill=False,
                )
            # Recent ~5 blocks.
            recent_start = max(0, current_pos - 5 * bs)
            for pos in range(recent_start, current_pos + 1, bs):
                block_id = _block_id_for(seq_id, pos, bs, n_blocks_per_seq)
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=pos,
                    seq_len=current_seq_len,
                    attention_weight=0.2,
                    is_prefill=False,
                )
            # The newly-generated token.
            yield TraceEvent(
                seq_id=seq_id,
                block_id=current_block,
                position=current_pos,
                seq_len=current_seq_len,
                attention_weight=0.05,
                is_prefill=False,
            )


def generate_chat(spec: WorkloadSpec) -> Iterator[TraceEvent]:
    """Chat pattern. Multi-turn — system prompt + each turn's
    user / assistant blocks. We model 4 logical "turns" inside
    the duration_decode_tokens and emit re-reads of:

    * System prompt block (every step, high attention).
    * Current turn's user message (high attention).
    * Previous turn's assistant message (medium attention).
    * Older turns (low attention, rare access)."""
    if spec.pattern is not AccessPattern.CHAT:
        raise ValueError(
            f"generate_chat given non-CHAT spec: {spec.pattern}"
        )
    bs = spec.block_size_tokens
    n_blocks_per_seq = spec.n_blocks_per_sequence()

    for seq_id in range(spec.n_concurrent_seqs):
        yield from _prefill_events(spec, seq_id)

        # Approximate turn boundaries: divide context into 4 turns.
        turn_size = max(bs, spec.context_length_tokens // 4)
        for step in range(spec.duration_decode_tokens):
            current_pos = spec.context_length_tokens + step
            current_seq_len = current_pos + 1
            current_block = _block_id_for(seq_id, current_pos, bs, n_blocks_per_seq)
            # System prompt re-read (positions 0 .. turn_size/4).
            for sys_pos in range(0, min(turn_size // 4, 64), bs):
                block_id = _block_id_for(seq_id, sys_pos, bs, n_blocks_per_seq)
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=sys_pos,
                    seq_len=current_seq_len,
                    attention_weight=0.35,
                    is_prefill=False,
                )
            # Current (last) turn — high attention.
            last_turn_start = max(0, spec.context_length_tokens - turn_size)
            for pos in range(last_turn_start, spec.context_length_tokens, bs):
                block_id = _block_id_for(seq_id, pos, bs, n_blocks_per_seq)
                yield TraceEvent(
                    seq_id=seq_id,
                    block_id=block_id,
                    position=pos,
                    seq_len=current_seq_len,
                    attention_weight=0.2,
                    is_prefill=False,
                )
            # Newly-generated token.
            yield TraceEvent(
                seq_id=seq_id,
                block_id=current_block,
                position=current_pos,
                seq_len=current_seq_len,
                attention_weight=0.05,
                is_prefill=False,
            )


_DISPATCH = {
    AccessPattern.AGENTIC: generate_agentic,
    AccessPattern.RAG: generate_rag,
    AccessPattern.CHAT: generate_chat,
}


def generate(spec: WorkloadSpec) -> Iterator[TraceEvent]:
    """Dispatch to the right generator for the spec's pattern."""
    return _DISPATCH[spec.pattern](spec)
