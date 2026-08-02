"""Mode B — oracle-verified extractive minimization.

Reduces an already-assembled context by extractive omission and proves the reduced
context equivalent to the full context via a neutral :class:`InvarianceOracle`,
comparing the oracle's OPAQUE ``equivalence_key`` values. It FAILS CLOSED: any
uncertainty — a missing/raising/malformed/expired oracle result, a correlation
mismatch, a contract mismatch, or an unresolved joint effect — increases retained
context (restore or full fallback), NEVER removal.

The core creates no authority and never interprets the equivalence key's contents.
The oracle owns all authorization / equivalence semantics.
"""

from __future__ import annotations

from typing import Iterable, Optional, Union

from .errors import InvalidRequestError, OracleRequiredError
from .fingerprint import result_fingerprint
from .models import (
    Context,
    EquivalenceStatus,
    MinimizationMode,
    MinimizationRequest,
    MinimizationResult,
    OracleEvaluation,
    ProtectionResult,
)
from .policy import DEFAULT_POLICY, MinimizationPolicy
from .protocols import InvarianceOracle, ProtectionProvider, TokenCounter
from .structural import deduplicate_context
from . import reasons


# --------------------------------------------------------------------------- #
# Oracle evaluation, defensively validated.
# --------------------------------------------------------------------------- #
def _validate_eval(
    ev: object, context: Context, evaluation_time: Optional[float]
) -> tuple[Optional[OracleEvaluation], Optional[str]]:
    if not isinstance(ev, OracleEvaluation):
        return None, reasons.ORACLE_RESULT_MALFORMED
    # The key is OPAQUE, but it must be a string. An empty string is a legitimate
    # (degenerate) equivalence class; a non-string (e.g. None) is malformed.
    if not isinstance(ev.equivalence_key, str):
        return None, reasons.ORACLE_RESULT_MALFORMED
    if (
        ev.correlation_id is not None
        and context.correlation_id is not None
        and ev.correlation_id != context.correlation_id
    ):
        return None, reasons.CORRELATION_MISMATCH
    if (
        ev.valid_until is not None
        and evaluation_time is not None
        and evaluation_time > ev.valid_until
    ):
        return None, reasons.ORACLE_EVALUATION_EXPIRED
    return ev, None


def _safe_evaluate(
    oracle: InvarianceOracle, context: Context, evaluation_time: Optional[float]
) -> tuple[Optional[OracleEvaluation], Optional[str]]:
    try:
        ev = oracle.evaluate(context, evaluation_time=evaluation_time)
    except Exception:  # noqa: BLE001 — any oracle failure fails closed, never crashes
        return None, reasons.ORACLE_RAISED
    return _validate_eval(ev, context, evaluation_time)


def _contract_ok(ev: OracleEvaluation, base: OracleEvaluation) -> bool:
    return ev.oracle_id == base.oracle_id and ev.contract_version == base.contract_version


# --------------------------------------------------------------------------- #
# Protection resolution (fail closed).
# --------------------------------------------------------------------------- #
def _resolve_protection(
    context: Context,
    protection: Union[ProtectionResult, ProtectionProvider, None],
    protected_ids: Iterable[str],
) -> tuple[frozenset[str], Optional[str]]:
    """Return (protected_ids, failure_code). On provider failure, protect EVERY unit."""
    ids: set[str] = set(protected_ids)
    ids.update(u.id for u in context.units if u.protected)
    if isinstance(protection, ProtectionResult):
        ids.update(protection.effective_protected)
    elif protection is not None and hasattr(protection, "protect"):
        try:
            res = protection.protect(context)
        except Exception:  # noqa: BLE001 — fail closed: protect everything
            return frozenset(u.id for u in context.units), reasons.PROTECTION_PROVIDER_FAILED
        if not isinstance(res, ProtectionResult):
            return frozenset(u.id for u in context.units), reasons.PROTECTION_PROVIDER_FAILED
        ids.update(res.effective_protected)
    return frozenset(ids), None


# --------------------------------------------------------------------------- #
# Extractive selection (optimization only; safety lives elsewhere).
# --------------------------------------------------------------------------- #
def _extractive_select(
    context: Context,
    candidate_ids: Iterable[str],
    protected: frozenset[str],
    target_reduction: float,
    token_budget: Optional[int],
    policy: MinimizationPolicy,
    counter: Optional[TokenCounter],
) -> tuple[list[str], bool]:
    """Return (removed_ids, budget_unreachable). Never selects a protected unit."""
    total = context.total_tokens(counter)
    removable = [context.unit(i) for i in candidate_ids if i not in protected]
    removable.sort(key=lambda u: policy.removal_key(u, counter))

    need_by_reduction = target_reduction * total
    need_by_budget = (total - token_budget) if token_budget is not None else 0.0
    target_removed = max(need_by_reduction, need_by_budget)

    removed: list[str] = []
    removed_tok = 0
    for u in removable:
        if removed_tok >= target_removed:
            break
        removed.append(u.id)
        removed_tok += u.counted_tokens(counter)

    budget_unreachable = (
        token_budget is not None and (total - removed_tok) > token_budget
    )
    return removed, budget_unreachable


def _necessary(
    context: Context,
    oracle: InvarianceOracle,
    removed_ids: Iterable[str],
    base: OracleEvaluation,
    evaluation_time: Optional[float],
) -> set[str]:
    """Removed units whose INDIVIDUAL removal from the full context changes the
    equivalence key (or whose evaluation is uncertain — fail closed → restore)."""
    all_ids = context.unit_ids
    nec: set[str] = set()
    for rid in sorted(removed_ids):
        sub = [i for i in all_ids if i != rid]
        ev, err = _safe_evaluate(oracle, context.with_units(sub), evaluation_time)
        if err is not None or ev is None or ev.equivalence_key != base.equivalence_key \
                or not _contract_ok(ev, base):
            nec.add(rid)  # uncertain or key-changing → must restore
    return nec


# --------------------------------------------------------------------------- #
# Result builders.
# --------------------------------------------------------------------------- #
def _build_result(
    context: Context,
    *,
    mode: MinimizationMode,
    surviving: list[str],
    removed_structural: Iterable[str],
    removed_extractive: Iterable[str],
    restored: Iterable[str],
    protected: frozenset[str],
    equivalence_status: EquivalenceStatus,
    fell_back: bool,
    codes: Iterable[str],
    policy: MinimizationPolicy,
    counter: Optional[TokenCounter],
    base_eval: Optional[OracleEvaluation],
) -> MinimizationResult:
    # `surviving` is authoritative; anything not surviving was removed. This keeps
    # restored/fallback ids out of the removed sets automatically.
    surviving_set = set(surviving)
    removed = set(context.unit_ids) - surviving_set
    removed_structural = [i for i in removed_structural if i in removed]
    removed_extractive = [i for i in removed_extractive if i in removed]
    original_tokens = context.total_tokens(counter)
    resulting_tokens = sum(context.unit(i).counted_tokens(counter) for i in surviving)
    oracle_id = base_eval.oracle_id if base_eval else None
    oracle_cv = base_eval.contract_version if base_eval else None

    # de-dupe codes preserving order
    seen: set[str] = set()
    ordered_codes = tuple(c for c in codes if not (c in seen or seen.add(c)))

    fp = result_fingerprint(
        context_id=context.id,
        mode=mode.value,
        surviving_ids=surviving,
        removed_structural=[i for i in removed_structural if i in removed],
        removed_extractive=[i for i in removed_extractive if i in removed],
        restored_ids=restored,
        protected_ids=protected,
        equivalence_status=equivalence_status.value,
        fell_back=fell_back,
        policy_version=policy.version,
        oracle_id=oracle_id,
        oracle_contract_version=oracle_cv,
    )
    return MinimizationResult(
        context_id=context.id,
        mode=mode,
        original_ids=context.unit_ids,
        surviving_ids=tuple(surviving),
        removed_ids=tuple(i for i in context.unit_ids if i in removed),
        removed_structural=tuple(i for i in removed_structural if i in removed),
        removed_extractive=tuple(i for i in removed_extractive if i in removed),
        restored_ids=tuple(sorted(restored)),
        protected_ids=tuple(sorted(protected)),
        original_tokens=original_tokens,
        resulting_tokens=resulting_tokens,
        requested_reduction=0.0,
        equivalence_status=equivalence_status,
        reduced=bool(removed),
        fell_back=fell_back,
        reason_codes=ordered_codes,
        policy_version=policy.version,
        oracle_id=oracle_id,
        oracle_contract_version=oracle_cv,
        fingerprint=fp,
    )


def _fallback(
    context: Context,
    protected: frozenset[str],
    code: str,
    policy: MinimizationPolicy,
    counter: Optional[TokenCounter],
    base_eval: Optional[OracleEvaluation],
) -> MinimizationResult:
    """Full-context fallback: nothing removed, everything retained."""
    return _build_result(
        context,
        mode=MinimizationMode.ORACLE_VERIFIED,
        surviving=list(context.unit_ids),
        removed_structural=[],
        removed_extractive=[],
        restored=[],
        protected=protected,
        equivalence_status=EquivalenceStatus.FALLBACK,
        fell_back=True,
        codes=[code],
        policy=policy,
        counter=counter,
        base_eval=base_eval,
    )


# --------------------------------------------------------------------------- #
# Public entry point — Mode B.
# --------------------------------------------------------------------------- #
def minimize_context(
    context: Context,
    *,
    oracle: Optional[InvarianceOracle],
    target_reduction: float = 0.0,
    token_budget: Optional[int] = None,
    protection: Union[ProtectionResult, ProtectionProvider, None] = None,
    protected_ids: Iterable[str] = (),
    policy: MinimizationPolicy = DEFAULT_POLICY,
    token_counter: Optional[TokenCounter] = None,
    evaluation_time: Optional[float] = None,
) -> MinimizationResult:
    """Oracle-verified extractive minimization of ``context``.

    Raises :class:`OracleRequiredError` if no oracle is supplied — this mode never
    silently operates without an oracle and still claims equivalence preservation.
    All *runtime* failures fail closed to a full-context result (see reason codes).
    """
    if oracle is None:
        raise OracleRequiredError(
            "minimize_context requires an InvarianceOracle; use structural_minimize "
            "for oracle-free structural deduplication."
        )
    if not 0.0 <= target_reduction <= 1.0:
        raise InvalidRequestError("target_reduction must be within [0, 1]")
    if token_budget is not None and token_budget < 0:
        raise InvalidRequestError("token_budget must be >= 0")

    protected, prot_fail = _resolve_protection(context, protection, protected_ids)

    # Base evaluation on the FULL context. If it is unusable, fail closed.
    base, base_err = _safe_evaluate(oracle, context, evaluation_time)
    if base_err is not None or base is None:
        return _fallback(context, protected, base_err or reasons.ORACLE_RAISED,
                         policy, token_counter, None)

    if prot_fail is not None:
        # Provider failed → protect everything → nothing removable → full context,
        # reported honestly (equivalence trivially holds; we simply removed nothing).
        return _build_result(
            context, mode=MinimizationMode.ORACLE_VERIFIED,
            surviving=list(context.unit_ids), removed_structural=[], removed_extractive=[],
            restored=[], protected=protected, equivalence_status=EquivalenceStatus.VERIFIED,
            fell_back=False, codes=[prot_fail, reasons.NO_REDUCTION_POSSIBLE],
            policy=policy, counter=token_counter, base_eval=base,
        )

    codes: list[str] = []
    if not protected:
        codes.append(reasons.PROTECTION_EMPTY)

    # Stage 1: structural (protected excluded).
    kept, removed_struct = deduplicate_context(context, protected)
    if removed_struct:
        codes.append(reasons.STRUCTURAL_DEDUP_APPLIED)

    # Stage 2: extractive selection to budget (protected excluded).
    removed_ext, budget_unreachable = _extractive_select(
        context, kept, protected, target_reduction, token_budget, policy, token_counter
    )
    if removed_ext:
        codes.append(reasons.EXTRACTIVE_REMOVAL_APPLIED)
    if budget_unreachable:
        codes.append(reasons.BUDGET_UNREACHABLE_WITHOUT_PROTECTED)

    removed = set(removed_struct) | set(removed_ext)
    surviving = [i for i in context.unit_ids if i not in removed]

    if not removed:
        codes.append(reasons.NO_REDUCTION_POSSIBLE)
        codes.append(reasons.EQUIVALENCE_VERIFIED)
        return _build_result(
            context, mode=MinimizationMode.ORACLE_VERIFIED, surviving=surviving,
            removed_structural=[], removed_extractive=[], restored=[], protected=protected,
            equivalence_status=EquivalenceStatus.VERIFIED, fell_back=False, codes=codes,
            policy=policy, counter=token_counter, base_eval=base,
        )

    # Stage 3: verify the reduced context.
    red, red_err = _safe_evaluate(oracle, context.with_units(surviving), evaluation_time)
    if red_err is not None or red is None:
        return _fallback(context, protected, red_err or reasons.ORACLE_RAISED,
                         policy, token_counter, base)
    if not _contract_ok(red, base):
        return _fallback(context, protected, reasons.ORACLE_CONTRACT_MISMATCH,
                         policy, token_counter, base)

    if red.equivalence_key == base.equivalence_key:
        codes.append(reasons.EQUIVALENCE_VERIFIED)
        return _build_result(
            context, mode=MinimizationMode.ORACLE_VERIFIED, surviving=surviving,
            removed_structural=removed_struct, removed_extractive=removed_ext, restored=[],
            protected=protected, equivalence_status=EquivalenceStatus.VERIFIED,
            fell_back=False, codes=codes, policy=policy, counter=token_counter, base_eval=base,
        )

    # Stage 4: restoration of individually-necessary spans.
    nec = _necessary(context, oracle, removed, base, evaluation_time)
    if nec:
        removed -= nec
        surviving = [i for i in context.unit_ids if i not in removed]
        red2, red2_err = _safe_evaluate(oracle, context.with_units(surviving), evaluation_time)
        if red2_err is None and red2 is not None and _contract_ok(red2, base) \
                and red2.equivalence_key == base.equivalence_key:
            codes.append(reasons.SPANS_RESTORED)
            codes.append(reasons.EQUIVALENCE_VERIFIED)
            return _build_result(
                context, mode=MinimizationMode.ORACLE_VERIFIED, surviving=surviving,
                removed_structural=removed_struct, removed_extractive=removed_ext,
                restored=sorted(nec), protected=protected,
                equivalence_status=EquivalenceStatus.RESTORED, fell_back=False, codes=codes,
                policy=policy, counter=token_counter, base_eval=base,
            )

    # Stage 5: joint effects unresolved by individual restoration → full fallback.
    codes.append(reasons.JOINT_EFFECT_FALLBACK)
    return _fallback(context, protected, reasons.JOINT_EFFECT_FALLBACK,
                     policy, token_counter, base)


def minimize(
    request: MinimizationRequest,
    *,
    oracle: Optional[InvarianceOracle] = None,
    protection: Union[ProtectionResult, ProtectionProvider, None] = None,
    protected_ids: Iterable[str] = (),
    policy: MinimizationPolicy = DEFAULT_POLICY,
    token_counter: Optional[TokenCounter] = None,
) -> MinimizationResult:
    """Dispatch a :class:`MinimizationRequest` by its mode.

    STRUCTURAL → :func:`structural_minimize`; ORACLE_VERIFIED → :func:`minimize_context`.
    """
    from .structural import structural_minimize

    if request.mode is MinimizationMode.STRUCTURAL:
        return structural_minimize(
            request.context, protection=protection if isinstance(protection, ProtectionResult) else None,
            protected_ids=protected_ids, policy=policy, token_counter=token_counter,
        )
    return minimize_context(
        request.context, oracle=oracle, target_reduction=request.target_reduction,
        token_budget=request.token_budget, protection=protection, protected_ids=protected_ids,
        policy=policy, token_counter=token_counter, evaluation_time=request.evaluation_time,
    )
