"""WorkflowIR — the versioned, deterministic executable policy representation.

WorkflowIR is compiled upstream by the Policy Workflow Compiler (consumed here
through a contract, never re-implemented). This module owns only the *executable*
shape: immutable typed rules whose conditions are a bounded predicate language,
so runtime policy execution is deterministic and contains no arbitrary Python
(spec §7.4, user brief §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from ..crypto.hashing import digest
from .enums import PredicateOp, RuleEffect, WorkflowStatus

__all__ = [
    "Predicate",
    "WorkflowRule",
    "WorkflowIR",
    "compute_workflow_digest",
]

_MISSING = object()


@dataclass(frozen=True)
class Predicate:
    """A single bounded condition over case facts.

    ``path`` selects a fact from the evaluation context (dotted paths descend
    into nested mappings). ``op`` is one of the bounded operators; ``value`` is
    the operand (unused for ``EXISTS``).
    """

    path: str
    op: PredicateOp
    value: Any = None

    def _resolve(self, context: Mapping[str, Any]) -> Any:
        current: Any = context
        for part in self.path.split("."):
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                return _MISSING
        return current

    def evaluate(self, context: Mapping[str, Any]) -> bool:
        """Evaluate this predicate against a fact ``context``.

        Fail-closed: an operand that cannot be resolved yields ``False`` for
        every operator except the explicit ``NOT_IN`` / ``NE`` negations, and
        ``EXISTS`` which reports presence directly.
        """

        actual = self._resolve(context)
        op = self.op

        if op is PredicateOp.EXISTS:
            return actual is not _MISSING and actual is not None

        if actual is _MISSING:
            # An absent fact only satisfies the negative membership/inequality
            # operators; everything else is False (fail closed).
            if op is PredicateOp.NOT_IN:
                return True
            if op is PredicateOp.NE:
                return True
            return False

        if op is PredicateOp.EQ:
            return actual == self.value
        if op is PredicateOp.NE:
            return actual != self.value
        if op is PredicateOp.GT:
            return _comparable(actual, self.value) and actual > self.value
        if op is PredicateOp.GTE:
            return _comparable(actual, self.value) and actual >= self.value
        if op is PredicateOp.LT:
            return _comparable(actual, self.value) and actual < self.value
        if op is PredicateOp.LTE:
            return _comparable(actual, self.value) and actual <= self.value
        if op is PredicateOp.IN:
            return actual in _as_collection(self.value)
        if op is PredicateOp.NOT_IN:
            return actual not in _as_collection(self.value)
        if op is PredicateOp.SUBSET_OF:
            return set(_as_collection(actual)).issubset(set(_as_collection(self.value)))
        if op is PredicateOp.ALL_OF:
            return set(_as_collection(self.value)).issubset(set(_as_collection(actual)))
        if op is PredicateOp.ANY_OF:
            return bool(set(_as_collection(self.value)) & set(_as_collection(actual)))
        return False


def _comparable(a: Any, b: Any) -> bool:
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(
        a, bool
    ) and not isinstance(b, bool)


def _as_collection(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


@dataclass(frozen=True)
class WorkflowRule:
    """A single executable policy rule."""

    rule_id: str
    conditions: tuple[Predicate, ...] = ()
    required_controls: tuple[str, ...] = ()
    effect: RuleEffect = RuleEffect.DENY_UNLESS_ALL

    def applies(self, context: Mapping[str, Any]) -> bool:
        """A rule applies when *all* of its conditions hold (AND semantics)."""

        return all(cond.evaluate(context) for cond in self.conditions)


@dataclass(frozen=True)
class WorkflowIR:
    """A versioned, digest-bound, immutable executable policy."""

    workflow_ir_id: str
    version: str
    status: WorkflowStatus
    rules: tuple[WorkflowRule, ...]
    source_refs: tuple[str, ...]
    effective_at: datetime
    subject_selector: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    digest: str = ""

    def with_digest(self) -> "WorkflowIR":
        """Return a copy whose ``digest`` binds the executable content.

        The digest is computed over everything *except* the digest field, so a
        recompute is idempotent and any post-activation mutation is detectable
        (spec §29 policy immutability, AC-01).
        """

        from dataclasses import replace

        base = replace(self, digest="")
        return replace(self, digest=digest(base))

    def applicable_rules(self, context: Mapping[str, Any]) -> tuple[WorkflowRule, ...]:
        return tuple(rule for rule in self.rules if rule.applies(context))


def compute_workflow_digest(workflow: WorkflowIR) -> str:
    from dataclasses import replace

    return digest(replace(workflow, digest=""))
