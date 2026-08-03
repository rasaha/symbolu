"""Mode A — structural, structurally-lossless minimization.

Removes exact-duplicate text and collapses declared redundancy sets, keeping one
representative. Losslessness holds *by the declared structural contract*: every
removed unit is a duplicate of a retained unit carrying the same information. This
mode needs NO invariance oracle.

Protected-span invariant (v1 contract):
    A unit marked protected is NEVER removed by structural minimization.
    Deduplication applies only to UNPROTECTED units. A protected unit may act as
    the retained representative that makes an unprotected duplicate removable, but
    two protected duplicates are BOTH retained.

This is intentionally NARROWER than full Context Minimization — do not describe it
as authorization-preserving. It preserves information structurally, not against any
oracle.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .fingerprint import result_fingerprint, run_fingerprint
from .models import (
    Context,
    EquivalenceStatus,
    MinimizationMode,
    MinimizationResult,
    ProtectionResult,
)
from .policy import DEFAULT_POLICY, MinimizationPolicy
from .protocols import TokenCounter
from . import reasons


def _norm(text: Optional[str]) -> str:
    """Whitespace/case-normalized text used for exact-duplicate detection."""
    return " ".join((text or "").lower().split())


def deduplicate_context(
    context: Context,
    protected_ids: Iterable[str] = (),
) -> tuple[list[str], list[str]]:
    """Low-level primitive: return ``(kept_ids, removed_ids)`` in source order.

    Protected units are always kept and act as representatives; only unprotected
    exact-duplicate / redundancy-set-collapsed units are removed.
    """
    protected = frozenset(protected_ids)
    seen_text: dict[str, str] = {}
    seen_redundancy: set[str] = set()

    # Pass 1: protected units are representatives and are always retained.
    for u in context.units:
        if u.id in protected:
            seen_text.setdefault(_norm(u.text), u.id)
            if u.redundancy_set is not None:
                seen_redundancy.add(u.redundancy_set)

    # Pass 2: walk in order. Keep every protected unit; dedup only unprotected ones.
    kept: list[str] = []
    removed: list[str] = []
    for u in context.units:
        if u.id in protected:
            kept.append(u.id)
            continue
        norm = _norm(u.text)
        drop = False
        if u.redundancy_set is not None and u.redundancy_set in seen_redundancy:
            drop = True                       # a copy of this declared fact is retained
        elif norm in seen_text:
            drop = True                       # exact-duplicate text of a retained span
        if drop:
            removed.append(u.id)
        else:
            seen_text.setdefault(norm, u.id)
            if u.redundancy_set is not None:
                seen_redundancy.add(u.redundancy_set)
            kept.append(u.id)
    return kept, removed


def _resolve_protection(
    context: Context,
    protection: Optional[ProtectionResult],
    protected_ids: Iterable[str],
) -> frozenset[str]:
    ids: set[str] = set(protected_ids)
    ids.update(u.id for u in context.units if u.protected)
    if protection is not None:
        ids.update(protection.effective_protected)
    return frozenset(ids)


def structural_minimize(
    context: Context,
    *,
    protected_ids: Iterable[str] = (),
    protection: Optional[ProtectionResult] = None,
    policy: MinimizationPolicy = DEFAULT_POLICY,
    token_counter: Optional[TokenCounter] = None,
) -> MinimizationResult:
    """Mode A entry point. Structurally minimize ``context`` and return a result.

    Protection is the union of: ``protected_ids``, units flagged ``protected=True``,
    and any ``protection`` result's effective-protected set. No oracle is consulted.
    """
    protected = _resolve_protection(context, protection, protected_ids)
    kept, removed = deduplicate_context(context, protected)

    original_ids = context.unit_ids
    original_tokens = context.total_tokens(token_counter)
    resulting_tokens = sum(context.unit(i).counted_tokens(token_counter) for i in kept)

    codes: tuple[str, ...] = (
        reasons.STRUCTURAL_DEDUP_APPLIED if removed else reasons.NO_REDUCTION_POSSIBLE,
    )

    outcome_fp = result_fingerprint(
        context_id=context.id,
        mode=MinimizationMode.STRUCTURAL.value,
        surviving_ids=kept,
        removed_structural=removed,
        removed_extractive=[],
        restored_ids=[],
        protected_ids=protected,
        equivalence_status=EquivalenceStatus.NOT_EVALUATED.value,
        fell_back=False,
        policy_version=policy.version,
        oracle_id=None,
        oracle_contract_version=None,
    )
    # Structural mode consults no oracle: requested_reduction is 0.0 (its request
    # semantics are "remove provable duplicates"), the oracle block is null, and
    # evaluation_time is not part of its identity.
    run_fp = run_fingerprint(
        context,
        mode=MinimizationMode.STRUCTURAL.value,
        requested_reduction=0.0,
        requested_token_budget=None,
        evaluation_time=None,
        policy=policy,
        token_counter=token_counter,
        base_eval=None,
        surviving_ids=kept,
        removed_structural=removed,
        removed_extractive=[],
        restored_ids=[],
        protected_ids=protected,
        original_tokens=original_tokens,
        resulting_tokens=resulting_tokens,
        equivalence_status=EquivalenceStatus.NOT_EVALUATED.value,
        fell_back=False,
        reason_codes=codes,
    )

    return MinimizationResult(
        context_id=context.id,
        mode=MinimizationMode.STRUCTURAL,
        original_ids=original_ids,
        surviving_ids=tuple(kept),
        removed_ids=tuple(removed),
        removed_structural=tuple(removed),
        removed_extractive=(),
        restored_ids=(),
        protected_ids=tuple(sorted(protected)),
        original_tokens=original_tokens,
        resulting_tokens=resulting_tokens,
        requested_reduction=0.0,
        equivalence_status=EquivalenceStatus.NOT_EVALUATED,
        reduced=bool(removed),
        fell_back=False,
        reason_codes=codes,
        policy_version=policy.version,
        oracle_id=None,
        oracle_contract_version=None,
        requested_token_budget=None,
        outcome_fingerprint=outcome_fp,
        run_fingerprint=run_fp,
        fingerprint=outcome_fp,  # DEPRECATED alias
    )
