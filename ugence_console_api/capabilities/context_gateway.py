"""Agent Gateway adapter — Context Minimization ("what may enter").

Wraps the canonical, independently-packaged Context Minimization capability
(``ugence-context-minimization``) — specifically its deterministic, structurally
lossless ``structural_minimize`` (drops exact-duplicate spans / declared redundancy
sets, keeps one representative). This is the STRUCTURAL mode: it needs no invariance
oracle. The full oracle-verified, authorization-preserving path (``minimize_context``
with a concrete ActionGate-derived oracle) is the productization upgrade and lives
outside this console adapter.

Migration note: this adapter previously imported the experimental
``actiongate_context_ablation`` package via a ``sys.path`` hack. It now imports the
canonical distribution directly. A behavioural hardening comes with that move — a
PROTECTED unit is never removed, even when a duplicate copy would otherwise make it
droppable (the old experimental ``structural_compress`` ignored the protected set).
"""

from __future__ import annotations

from ..models import ContextUnit, MinimizeResult

_available = True
_reason = ""
try:  # fail-safe import — a missing module degrades, never crashes the app.
    from ugence_context_minimization.api import (
        Context as _Context,
        ContextUnit as _CanonUnit,
        structural_minimize as _structural_minimize,
    )
except Exception as exc:  # noqa: BLE001
    _available = False
    _reason = f"{type(exc).__name__}: {exc}"


def available() -> tuple[bool, str]:
    return _available, _reason


def minimize(units: list[ContextUnit]) -> MinimizeResult:
    """Structurally minimize the admitted context, protecting flagged units."""
    if not _available:
        raise RuntimeError(f"context_minimization unavailable: {_reason}")

    ctx = _Context(
        id="console-ctx",
        units=tuple(
            _CanonUnit(
                id=u.id, text=u.text, source_type="state_fact",
                redundancy_set=u.redundancy_set, protected=u.protected,
            )
            for u in units
        ),
    )
    protected_ids = [u.id for u in units if u.protected]
    result = _structural_minimize(ctx, protected_ids=protected_ids)
    removed = set(result.removed_ids)
    kept = set(result.surviving_ids)
    # Losslessness: every removed unit is a duplicate of a fact still represented —
    # either an exact-text duplicate of a surviving span or a surviving redundancy set.
    surviving_texts = {" ".join(u.text.lower().split()) for u in units if u.id in kept}
    surviving_rsets = {u.redundancy_set for u in units if u.id in kept and u.redundancy_set}
    lossless = all(
        " ".join(u.text.lower().split()) in surviving_texts
        or u.redundancy_set in surviving_rsets
        for u in units if u.id in removed
    )
    return MinimizeResult(
        kept_ids=list(result.surviving_ids),
        removed_ids=list(result.removed_ids),
        total_units=len(units),
        removed_units=len(result.removed_ids),
        protected_ids=sorted(result.protected_ids),
        lossless=lossless,
    )
