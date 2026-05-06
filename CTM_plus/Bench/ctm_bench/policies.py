"""Policy implementations + a registry.

Three concrete policies:

* :class:`LRUPolicy` — recency-only, the production-default
  baseline.
* :class:`FIFOPolicy` — insertion-order, the minimal baseline.
* :class:`CTMPlusPolicyAdapter` — wraps the existing
  ``kv_policy.KVCachePolicy`` so the benchmark always tests the
  current production-target scoring math; no fork.

All three conform to the :class:`Policy` protocol so the runner
stays policy-agnostic. To add a new policy (ARC, S3FIFO,
LFU-DA, ...), implement the protocol and register it in
:data:`POLICIES`.
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol


@dataclass(frozen=True)
class BenchConfig:
    """Per-run policy configuration. Held by the runner.

    The ``attention_ema_alpha`` field is the experimental knob
    used by the Round 3 ema-alpha sweep. It is forwarded only
    to :class:`CTMPlusPolicyAdapter`; LRU + FIFO ignore it. When
    ``None`` (the default), the underlying ``KVCachePolicy``
    uses its own default (currently 0.1) — the production
    behaviour is preserved unless the caller opts in.
    """

    max_blocks: int                 # tier 0 capacity in blocks
    block_size: int = 16            # tokens per block
    sink_tokens: int = 4
    seed: int = 42
    attention_ema_alpha: Optional[float] = None  # None = use policy default

    def __post_init__(self) -> None:
        if self.max_blocks <= 0:
            raise ValueError(
                f"max_blocks must be positive; got {self.max_blocks}"
            )
        if self.block_size <= 0:
            raise ValueError(
                f"block_size must be positive; got {self.block_size}"
            )
        if self.sink_tokens < 0:
            raise ValueError(
                f"sink_tokens must be non-negative; got {self.sink_tokens}"
            )
        if self.attention_ema_alpha is not None:
            if not (0.0 < self.attention_ema_alpha <= 1.0):
                raise ValueError(
                    f"attention_ema_alpha must be in (0, 1]; "
                    f"got {self.attention_ema_alpha}"
                )


@dataclass(frozen=True)
class AccessContext:
    """Context the runner passes to the policy on each access."""

    seq_id: int
    position: int                   # token position within sequence
    seq_len: int                    # current sequence length
    attention_weight: float         # per-block attention this access
    is_prefill: bool                # phase signal


class Policy(Protocol):
    """Eviction-policy protocol the runner expects."""

    def register_sequence(self, seq_id: int) -> None: ...

    def on_access(self, block_id: int, ctx: AccessContext) -> None: ...

    def select_victims(self, n: int) -> List[int]: ...

    def on_evict(self, block_id: int) -> None: ...


# ---------------------------------------------------------------- #
# LRU
# ---------------------------------------------------------------- #


class LRUPolicy:
    """Vanilla LRU. Block recency is the only signal."""

    def __init__(self, cfg: BenchConfig) -> None:
        self.cfg = cfg
        # OrderedDict preserves insertion order; move_to_end on
        # access updates recency in O(1).
        self._order: "OrderedDict[int, None]" = OrderedDict()

    def register_sequence(self, seq_id: int) -> None:
        # LRU has no per-sequence state.
        return None

    def on_access(self, block_id: int, ctx: AccessContext) -> None:
        if block_id in self._order:
            self._order.move_to_end(block_id)
        else:
            self._order[block_id] = None

    def select_victims(self, n: int) -> List[int]:
        if n <= 0:
            return []
        # Oldest first.
        victims = list(self._order.keys())[:n]
        return victims

    def on_evict(self, block_id: int) -> None:
        self._order.pop(block_id, None)


# ---------------------------------------------------------------- #
# FIFO
# ---------------------------------------------------------------- #


class FIFOPolicy:
    """Vanilla FIFO. Insertion order is the only signal — does
    not update on re-access. Useful as a sanity-floor baseline."""

    def __init__(self, cfg: BenchConfig) -> None:
        self.cfg = cfg
        self._order: "OrderedDict[int, None]" = OrderedDict()

    def register_sequence(self, seq_id: int) -> None:
        return None

    def on_access(self, block_id: int, ctx: AccessContext) -> None:
        if block_id not in self._order:
            self._order[block_id] = None

    def select_victims(self, n: int) -> List[int]:
        if n <= 0:
            return []
        return list(self._order.keys())[:n]

    def on_evict(self, block_id: int) -> None:
        self._order.pop(block_id, None)


# ---------------------------------------------------------------- #
# CTM+ adapter
# ---------------------------------------------------------------- #


def _add_kv_policy_to_path() -> None:
    """Make ``kv_policy`` importable when running from inside
    ``CTM_plus/Bench/``. The KVPolicy package lives in a sibling
    directory (``CTM_plus/KVPolicy/``); we add that to sys.path
    on first import. Reversible: we only add, never remove."""
    here = Path(__file__).resolve().parent.parent.parent
    kv_policy_root = here / "KVPolicy"
    candidate = str(kv_policy_root)
    if candidate not in sys.path and kv_policy_root.is_dir():
        sys.path.insert(0, candidate)


class CTMPlusPolicyAdapter:
    """Adapter wrapping :class:`kv_policy.KVCachePolicy`.

    The benchmark uses the *real* CTM+ policy code so a future
    bug fix in scoring is reflected in the next benchmark run
    automatically. If the KVPolicy package is not on sys.path,
    instantiation raises a clear ImportError pointing at the
    expected path.
    """

    def __init__(self, cfg: BenchConfig) -> None:
        self.cfg = cfg
        _add_kv_policy_to_path()
        try:
            from kv_policy import KVCachePolicy  # type: ignore
            from kv_policy.attention_evictor import InferencePhase  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "CTM+ adapter requires the kv_policy package. Install "
                "it via `pip install -e CTM_plus/KVPolicy/` from the "
                "repository root, or run the benchmark with `python -m` "
                "from a directory where kv_policy is importable."
            ) from exc
        self._InferencePhase = InferencePhase
        # Forward the optional ema-alpha knob only when the caller
        # opted in. Passing it unconditionally would lock us to
        # whatever value KVCachePolicy currently defaults to and
        # mask future production-default changes.
        kvcache_kwargs = dict(
            max_blocks=cfg.max_blocks,
            block_size=cfg.block_size,
            sink_tokens=cfg.sink_tokens,
        )
        if cfg.attention_ema_alpha is not None:
            kvcache_kwargs["attention_ema_alpha"] = cfg.attention_ema_alpha
        self._policy = KVCachePolicy(**kvcache_kwargs)
        self._registered: set = set()

    def register_sequence(self, seq_id: int) -> None:
        if seq_id in self._registered:
            return
        self._policy.register_sequence(seq_id)
        self._registered.add(seq_id)

    def on_access(self, block_id: int, ctx: AccessContext) -> None:
        if ctx.seq_id not in self._registered:
            self.register_sequence(ctx.seq_id)
        phase = (
            self._InferencePhase.PREFILL
            if ctx.is_prefill
            else self._InferencePhase.DECODE
        )
        self._policy.set_phase(ctx.seq_id, phase)
        # token_id is unused by the policy beyond tracking; we
        # synthesise one from position so the policy sees a stable
        # identifier within the sequence.
        token_id = ctx.position
        self._policy.on_token_access(
            token_id=token_id,
            position=ctx.position,
            sequence_id=ctx.seq_id,
            block_id=block_id,
            attention_weight=ctx.attention_weight,
            seq_len=ctx.seq_len,
        )

    def select_victims(self, n: int) -> List[int]:
        if n <= 0:
            return []
        return self._policy.select_victims(n)

    def on_evict(self, block_id: int) -> None:
        self._policy.evict_block(block_id)


# ---------------------------------------------------------------- #
# Registry
# ---------------------------------------------------------------- #


POLICIES: Dict[str, Callable[[BenchConfig], Policy]] = {
    "lru": LRUPolicy,
    "fifo": FIFOPolicy,
    "ctm_plus": CTMPlusPolicyAdapter,
}


def get_policy(name: str, cfg: BenchConfig) -> Policy:
    """Construct a policy by name. Raises KeyError with a helpful
    message if the name is unknown."""
    if name not in POLICIES:
        raise KeyError(
            f"unknown policy {name!r}; known policies are "
            f"{sorted(POLICIES.keys())!r}"
        )
    return POLICIES[name](cfg)
