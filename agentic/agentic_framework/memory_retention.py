"""
Memory Retention Policy (v2.5)

Optional time- and size-based eviction limits for ``AgentMemory``,
peer to ``BudgetPolicy`` and ``DurationPolicy``.  Where ``BudgetPolicy``
governs resource consumption and ``DurationPolicy`` governs temporal
persistence of *runs*, ``MemoryRetentionPolicy`` governs temporal
persistence of *memory items*.

Three independent caps:

- ``item_ttl_s``  — drop turns older than this (created_at).
- ``idle_ttl_s``  — drop turns not accessed in this long
  (last_accessed_at).
- ``max_items``   — hard cap on history length, applied AFTER TTL
  cleanup.

All three default to ``None``; the all-``None`` policy reproduces
today's positional sliding-window behaviour exactly.

This module defines the policy object only.  Cleanup logic lives in
``memory_store.py`` and is wired in a separate batch.

See ``docs/MEMORY_TTL_V2_5_DESIGN.md`` for the full design contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class MemoryRetentionPolicy:
    """Optional time- and size-based eviction limits for ``AgentMemory``.

    Set any field to ``None`` (the default) to leave it unconstrained.
    The all-``None`` policy is a no-op: behaviour with this policy is
    byte-identical to having no policy at all.

    Args:
        item_ttl_s: Maximum wall-clock seconds since a turn's
            ``created_at``.  Turns older than this are evicted on the
            next memory read or write.  ``None`` (default) disables
            item-age expiry.
        idle_ttl_s: Maximum wall-clock seconds since a turn's
            ``last_accessed_at``.  Turns not accessed in this long are
            evicted on the next memory read or write.  ``last_accessed``
            is updated to *now* whenever a turn is returned by any read
            path.  ``None`` (default) disables idle expiry.
        max_items: Hard cap on history length, applied AFTER TTL
            cleanup.  When set, drops the oldest items by position until
            the history fits.  When set, this overrides
            ``AgentMemory.window_size`` for retention purposes; when
            ``None`` (default), the existing ``window_size`` continues
            to apply.

    Wall-clock time is used for gating.  Replay-deterministic operators
    should leave all fields ``None`` (see design doc §10).
    """

    item_ttl_s: Optional[float] = None
    idle_ttl_s: Optional[float] = None
    max_items: Optional[int] = None

    def is_active(self) -> bool:
        """Return ``True`` if any field is set; the policy will evict
        at least sometimes.

        A policy with all fields ``None`` is observably indistinguishable
        from no policy at all and the runtime can short-circuit cleanup.
        """
        return (
            self.item_ttl_s is not None
            or self.idle_ttl_s is not None
            or self.max_items is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return asdict(self)
