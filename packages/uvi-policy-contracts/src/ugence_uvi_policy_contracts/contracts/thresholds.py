"""Governed thresholds and policy gates.

A :class:`GovernedThreshold` is a **policy artifact, not a metric evidence
claim** (ADR §13): it carries no evidence axes and is compared *against*
``MetricClaim`` values by a downstream evaluator. It is either an **immutable
policy literal** (a bar intrinsic to the signed policy) **or** a
:class:`BenchmarkReference` into separately-governed data — never both, and
never neither (ADR §15, D-3).

A :class:`PolicyGate` is a declared gate: a category, a requirement class, the
targets it applies to, and an optional threshold. The contract enforces the
non-waivable-mandatory invariant structurally — a ``MANDATORY`` gate can never
be marked conditionally compensable (ADR §8, D-6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_governance_contracts.api import BenchmarkReference

from ._util import canonical_digest, require_nonempty
from .enums import ComparisonOperator, GateCategory, RequirementClass, ReadinessTarget
from .errors import PolicyContractError

__all__ = ["GovernedThreshold", "PolicyGate"]


@dataclass(frozen=True)
class GovernedThreshold:
    """An immutable policy literal **or** a reference to a governed benchmark.

    ``literal_value`` is a portable scalar carried as a string (the same
    deterministic-serialization discipline as ``MetricClaim.value``). Exactly one
    of ``literal_value`` (non-empty) or ``benchmark_ref`` (present) must be
    supplied. A threshold carries **no** ``SourceBasis``/evidence axes — it is a
    policy bar, not evidence.
    """

    threshold_id: str
    governed_unit: str
    comparator: ComparisonOperator
    literal_value: str = ""
    benchmark_ref: Optional[BenchmarkReference] = None

    def __post_init__(self) -> None:
        require_nonempty(self.threshold_id, "GovernedThreshold.threshold_id")
        require_nonempty(self.governed_unit, "GovernedThreshold.governed_unit")
        if not isinstance(self.comparator, ComparisonOperator):
            raise PolicyContractError("GovernedThreshold.comparator must be a ComparisonOperator")
        if self.benchmark_ref is not None and not isinstance(self.benchmark_ref, BenchmarkReference):
            raise PolicyContractError(
                "GovernedThreshold.benchmark_ref must be a governance-contracts BenchmarkReference"
            )
        has_literal = bool(self.literal_value and self.literal_value.strip())
        has_benchmark = self.benchmark_ref is not None
        if has_literal == has_benchmark:
            raise PolicyContractError(
                "GovernedThreshold requires exactly one of an immutable literal_value "
                "or a BenchmarkReference (never both, never neither)"
            )

    @property
    def is_literal(self) -> bool:
        return self.benchmark_ref is None

    def canonical_digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class PolicyGate:
    """A declared readiness/quality gate within a policy (schema only).

    This is a *declaration* — no gate is evaluated here. The non-waivable
    invariant is enforced structurally: only a ``CONDITIONAL`` gate may be
    ``conditionally_compensable``; a ``MANDATORY`` or ``ADVISORY`` gate must not
    be (a mandatory concern is never eligible for a compensating control, D-6).
    """

    gate_id: str
    category: GateCategory
    requirement_class: RequirementClass
    applicability: tuple[ReadinessTarget, ...]
    threshold: Optional[GovernedThreshold] = None
    conditionally_compensable: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        require_nonempty(self.gate_id, "PolicyGate.gate_id")
        if not isinstance(self.category, GateCategory):
            raise PolicyContractError("PolicyGate.category must be a GateCategory")
        if not isinstance(self.requirement_class, RequirementClass):
            raise PolicyContractError("PolicyGate.requirement_class must be a RequirementClass")
        if self.threshold is not None and not isinstance(self.threshold, GovernedThreshold):
            raise PolicyContractError("PolicyGate.threshold must be a GovernedThreshold")

        if not self.applicability:
            raise PolicyContractError("PolicyGate.applicability must name at least one ReadinessTarget")
        seen: set[ReadinessTarget] = set()
        for t in self.applicability:
            if not isinstance(t, ReadinessTarget):
                raise PolicyContractError("PolicyGate.applicability entries must be ReadinessTarget")
            if t in seen:
                raise PolicyContractError(f"PolicyGate.applicability contains duplicate {t.value}")
            seen.add(t)

        if not isinstance(self.conditionally_compensable, bool):
            raise PolicyContractError("PolicyGate.conditionally_compensable must be a bool")
        if self.conditionally_compensable and self.requirement_class is not RequirementClass.CONDITIONAL:
            raise PolicyContractError(
                "only a CONDITIONAL gate may be conditionally_compensable; a "
                f"{self.requirement_class.value} gate cannot be waived or compensated (D-6)"
            )

    def canonical_digest(self) -> str:
        return canonical_digest(self)
