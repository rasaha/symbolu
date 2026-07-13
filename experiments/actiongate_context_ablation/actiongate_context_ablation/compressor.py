"""ActionGate Context Minimization — extractive compressor prototype.

Purely EXTRACTIVE: it removes whole spans; it never rewrites, paraphrases, or
summarizes. Objective: maximize token reduction subject to (a) 100% protected-span
recall and (b) ActionGate decision invariance. Fail-closed: if the compressed
context would change the gate's envelope/outcome/dispositive-rules/constraints/
evidence/approvals, restore the necessary spans, or fall back to the original.

Reuses the frozen protected-span detector and the frozen oracle extractor + gate;
it does not modify ActionGate, the corpus, or the extractor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import adapter, extractor
from .units import Context

# span importance for extractive ordering (lower = removed first). No query is
# available, so this is a structural prior: pure filler goes first.
_LOW_VALUE_SRC = {"log_event": 0, "chat_turn": 1, "sentence": 2, "clause": 3,
                  "retrieved_passage": 3, "list_item": 3, "state_fact": 4}
_FILLER_HINT = ("weekly", "sprint", "historical", "log:", "previously", "earlier",
                "planning", "on-call", "coffee", "maintenance window")


def _importance(unit) -> tuple:
    base = _LOW_VALUE_SRC.get(unit.source_type, 5)
    hint = -1 if any(w in (unit.text or "").lower() for w in _FILLER_HINT) else 0
    # tuple sort key: (filler-hint first, source-value, then longer spans removed
    # earlier to reach budget faster, then id for determinism)
    return (hint, base, -unit.token_count, unit.id)


def _eval(ctx: Context, ids, sp) -> dict:
    return extractor.extract_and_eval(ctx, ids, sp, mode=extractor.ORACLE)


def signature(res: dict) -> tuple:
    """Decision-invariance signature: the canonical envelope plus the gate's decision
    outputs (outcome, dispositive rules, applied constraints). Two contexts are
    decision-equivalent iff these are equal.

    Note we intentionally do NOT include the *count* of provided evidence/approvals:
    that is an input quantity, not a decision output. Removing a REDUNDANT evidence
    leaves the outcome/dispositive-rules unchanged (correctly invariant); removing a
    REQUIRED evidence changes the outcome (e.g. ALLOW -> SIMULATE_AND_RETRY), which
    IS in the signature — so 'evidence/approval requirements' are enforced via the
    decision outputs, not by counting inputs."""
    d = res["decision"]
    env = res["envelope"]
    return (
        tuple(sorted((k, repr(v)) for k, v in env.items())),
        d.get("outcome"),
        tuple(d.get("dispositive_rules") or ()),
        repr(d.get("applied_constraints")),
    )


@dataclass
class CompressResult:
    surviving_ids: list
    removed_structural: list
    removed_extractive: list
    restored: list
    fell_back: bool
    total_tokens: int
    removed_tokens: int
    protected_ids: frozenset
    invariant: bool

    @property
    def token_reduction(self) -> float:
        return self.removed_tokens / self.total_tokens if self.total_tokens else 0.0


def structural_compress(ctx: Context, protected_ids) -> tuple:
    """Lossless dedup: keep one representative per redundancy-set and drop
    exact-duplicate span texts. Losslessness holds because a retained copy carries
    the same information. Returns (kept_ids, removed_ids)."""
    kept, removed = [], []
    seen_text = {}
    seen_redundancy = set()
    for u in ctx.units:
        norm = " ".join((u.text or "").lower().split())
        drop = False
        if u.redundancy_set is not None:
            if u.redundancy_set in seen_redundancy:
                drop = True                    # a copy of this fact is already kept
            else:
                seen_redundancy.add(u.redundancy_set)
        if not drop and norm in seen_text:
            drop = True                        # exact-duplicate text
        if not drop:
            seen_text[norm] = u.id
            kept.append(u.id)
        else:
            removed.append(u.id)
    return kept, removed


def extractive_select(ctx: Context, candidate_ids, protected_ids, target_reduction) -> list:
    """Remove only NON-protected candidate spans, lowest-importance first, until the
    target token reduction is reached (or nothing non-protected remains)."""
    total = ctx.total_tokens or 1
    removable = [ctx.unit(i) for i in candidate_ids if i not in protected_ids]
    removable.sort(key=_importance)
    removed, removed_tok = [], 0
    for u in removable:
        if removed_tok / total >= target_reduction:
            break
        removed.append(u.id)
        removed_tok += u.token_count
    return removed


def _necessary(ctx, sp, removed_ids, sig_orig) -> set:
    """Removed spans whose individual removal from the FULL context changes the
    signature — i.e. genuinely decision-relevant spans the detector missed."""
    all_ids = [u.id for u in ctx.units]
    nec = set()
    for rid in removed_ids:
        if signature(_eval(ctx, [i for i in all_ids if i != rid], sp)) != sig_orig:
            nec.add(rid)
    return nec


def compress(ctx: Context, protect_fn, sp, target_reduction: float,
             *, structural: bool = True, fail_closed: bool = True) -> CompressResult:
    all_ids = [u.id for u in ctx.units]
    total = ctx.total_tokens
    sig_orig = signature(_eval(ctx, all_ids, sp))
    protected = frozenset(protect_fn(ctx))

    removed_struct = []
    kept = all_ids
    if structural:
        kept, removed_struct = structural_compress(ctx, protected)

    removed_ext = extractive_select(ctx, kept, protected, target_reduction)
    removed = set(removed_struct) | set(removed_ext)
    surviving = [i for i in all_ids if i not in removed]

    restored, fell_back = [], False
    invariant = signature(_eval(ctx, surviving, sp)) == sig_orig
    if not invariant and fail_closed:
        nec = _necessary(ctx, sp, removed, sig_orig)
        if nec:
            removed -= nec
            restored = sorted(nec)
            surviving = [i for i in all_ids if i not in removed]
            invariant = signature(_eval(ctx, surviving, sp)) == sig_orig
        if not invariant:                      # joint effects etc. -> full fallback
            fell_back = True
            removed = set()
            surviving = list(all_ids)
            invariant = True

    removed_tok = sum(ctx.unit(i).token_count for i in removed)
    return CompressResult(
        surviving_ids=surviving,
        removed_structural=[i for i in removed_struct if i in removed],
        removed_extractive=[i for i in removed_ext if i in removed],
        restored=restored, fell_back=fell_back, total_tokens=total,
        removed_tokens=removed_tok, protected_ids=protected, invariant=invariant)
