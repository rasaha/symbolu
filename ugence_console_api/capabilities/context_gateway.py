"""Agent Gateway adapter — Context Minimization ("what may enter").

Wraps the module's deterministic, lossless ``structural_compress`` (drops exact
duplicate spans / redundant facts, keeps one representative) — a real path in the
Context Minimization codebase that needs no trained detector. The full
authorization-preserving compressor (with a fitted protection detector) is the
productization upgrade.
"""

from __future__ import annotations

import os
import sys

from ..models import ContextUnit, MinimizeResult

# The module lives under experiments/ as a nested package; expose it on sys.path.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PKG_PATH = os.path.join(_ROOT, "experiments", "actiongate_context_ablation")

_available = True
_reason = ""
try:  # fail-safe import — a missing module degrades, never crashes the app.
    if _PKG_PATH not in sys.path:
        sys.path.insert(0, _PKG_PATH)
    from actiongate_context_ablation import compressor as _cm  # type: ignore
    from actiongate_context_ablation.units import SemanticUnit  # type: ignore
except Exception as exc:  # noqa: BLE001
    _available = False
    _reason = f"{type(exc).__name__}: {exc}"


def available() -> tuple[bool, str]:
    return _available, _reason


def minimize(units: list[ContextUnit]) -> MinimizeResult:
    """Structurally compress the admitted context, protecting flagged units."""
    if not _available:
        raise RuntimeError(f"context_minimization unavailable: {_reason}")

    ctx_units = tuple(
        SemanticUnit(
            id=u.id, source_type="state_fact", text=u.text,
            redundancy_set=u.redundancy_set,
        )
        for u in units
    )
    ctx = _cm.Context(
        id="console-ctx", base={"tool": "console", "verb": "admit", "target": []},
        units=ctx_units, data_origin="authored-fixture",
    )
    protected_ids = frozenset(u.id for u in units if u.protected)
    kept, removed = _cm.structural_compress(ctx, protected_ids)
    kept_set = set(kept)
    # Losslessness: every removed unit is a duplicate of a fact still represented.
    lossless = all(u.id in kept_set or u.redundancy_set is not None
                   for u in units if u.id in set(removed))
    return MinimizeResult(
        kept_ids=list(kept), removed_ids=list(removed),
        total_units=len(units), removed_units=len(removed),
        protected_ids=sorted(protected_ids), lossless=lossless,
    )
