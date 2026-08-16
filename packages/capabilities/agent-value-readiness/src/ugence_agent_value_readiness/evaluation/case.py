"""The immutable readiness **evaluation case** — the evaluator's whole input.

A :class:`ReadinessEvaluationCase` is everything the GV-3R-b evaluator is
allowed to look at. It deliberately carries **no classification field**: the
caller states the facts, the evaluator selects the tier. There is no way to
propose, hint, or default a :class:`ReadinessClassification` through this shape.

The constructor rejects only inputs that **contradict themselves**; it never
rejects an assessment merely for being incomplete (that is a
``NOT_ASSESSABLE`` determination, not an exception):

* tenant / subject consistency across the context, indicator results and claims;
* ``readiness_policy_ref`` must be exactly ``readiness_policy.reference``
  (policy id, family, version, content digest, scope and tenant);
* every ``GateResult`` must carry that same ``readiness_policy_ref``, must have
  been evaluated for the requested target, must name a gate that exists in the
  supplied ``ReadinessPolicy``, and must embed **that policy's** ``PolicyGate``
  by value — a gate borrowed from another policy, or a locally-redefined gate,
  is rejected rather than silently evaluated;
* gate ids, condition ids and indicator result ids are unique — a caller cannot
  supply two contradictory results for the same gate.

Every sequence is normalized to a real tuple at construction, so mutating a
caller-owned list afterwards can never reach the frozen case or change its
:meth:`canonical_input_digest`.

Nothing here verifies authenticity. The ``ReadinessPolicy``, its gates, the
recorded gate statuses and the condition lifecycle labels all remain
**structurally supplied, authority-unverified** artifacts.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    PolicyFamily,
    PolicyReference,
    ReadinessPolicy,
    ReadinessTarget,
)

from ..contracts._util import coerce_tuple, normalize_tokens, require_nonempty
from ..contracts.errors import ReadinessContractError
from ..contracts.composite import AdvisoryComposite
from ..contracts.conditions import ConditionSet
from ..contracts.gates import GateResult
from ..contracts.indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)
from .errors import ReadinessEvaluationError

__all__ = ["ReadinessEvaluationCase"]


@contextmanager
def _as_evaluation_error():
    """Surface every structural rejection as :class:`ReadinessEvaluationError`.

    The shared contract helpers raise the base ``ReadinessContractError``; a
    caller of the evaluator should see the evaluator's own typed error for any
    malformed input, without losing the original message or traceback.
    """

    try:
        yield
    except ReadinessEvaluationError:
        raise
    except ReadinessContractError as exc:
        raise ReadinessEvaluationError(str(exc)) from exc


@dataclass(frozen=True)
class ReadinessEvaluationCase:
    """The complete, immutable input to one readiness evaluation.

    ``readiness_policy`` is consumed **by value**: the applicable-gate inventory
    is derived from it, so a caller cannot shrink the assessment by omitting an
    inconvenient gate — an applicable mandatory or conditional gate with no
    supplied result makes the case ``NOT_ASSESSABLE``.
    """

    case_id: str
    tenant_id: str
    subject_id: str
    context: AssessmentContext
    readiness_policy: ReadinessPolicy
    readiness_policy_ref: PolicyReference
    requested_target: ReadinessTarget
    intelligence_results: tuple[IntelligenceFitnessResult, ...] = ()
    capability_results: tuple[CapabilityReadinessResult, ...] = ()
    adoption_results: tuple[AdoptionReadinessResult, ...] = ()
    gate_results: tuple[GateResult, ...] = ()
    conditions: tuple[ConditionSet, ...] = ()
    advisory_composite: Optional[AdvisoryComposite] = None
    evidence_refs: tuple[str, ...] = ()
    assessment_window_ref: str = ""

    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        with _as_evaluation_error():
            require_nonempty(self.case_id, "ReadinessEvaluationCase.case_id")
            require_nonempty(self.tenant_id, "ReadinessEvaluationCase.tenant_id")
            require_nonempty(self.subject_id, "ReadinessEvaluationCase.subject_id")

            self._check_context()
            self._check_policy()
            self._check_target()
            for field, expected in (
                ("intelligence_results", IntelligenceFitnessResult),
                ("capability_results", CapabilityReadinessResult),
                ("adoption_results", AdoptionReadinessResult),
            ):
                self._check_indicator_results(field, expected)
            self._check_gate_results()
            self._check_conditions()
            self._check_composite()
            object.__setattr__(
                self,
                "evidence_refs",
                normalize_tokens(self.evidence_refs, "ReadinessEvaluationCase.evidence_refs"),
            )
            if not isinstance(self.assessment_window_ref, str):
                raise ReadinessEvaluationError(
                    "ReadinessEvaluationCase.assessment_window_ref must be a string"
                )

    # ------------------------------------------------------------------ #
    def _check_context(self) -> None:
        # AssessmentContext structurally guarantees a Geography, Domain and
        # Intended-Outcome binding (its own constructor rejects a context without
        # all three), so "required G/D/O binding absent" is unrepresentable once a
        # real AssessmentContext exists. Requiring the type here is therefore the
        # complete check — no G/D/O rule is fabricated on top of it.
        if not isinstance(self.context, AssessmentContext):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.context must be an AssessmentContext"
            )
        if self.context.tenant_id != self.tenant_id:
            raise ReadinessEvaluationError(
                f"cross-tenant case: context tenant {self.context.tenant_id!r} != {self.tenant_id!r}"
            )
        if self.context.subject_id != self.subject_id:
            raise ReadinessEvaluationError(
                f"cross-subject case: context subject {self.context.subject_id!r} != {self.subject_id!r}"
            )

    def _check_policy(self) -> None:
        if not isinstance(self.readiness_policy, ReadinessPolicy):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.readiness_policy must be a ReadinessPolicy body "
                "(the evaluator consumes the complete policy by value, not a reference alone)"
            )
        if not isinstance(self.readiness_policy_ref, PolicyReference):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.readiness_policy_ref must be a PolicyReference"
            )
        if self.readiness_policy_ref.policy_family is not PolicyFamily.READINESS:
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.readiness_policy_ref must reference a READINESS policy"
            )
        if self.readiness_policy_ref != self.readiness_policy.reference:
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.readiness_policy_ref does not match the supplied "
                "readiness_policy (policy_id/family/version/content_digest/scope/tenant must match)"
            )

    def _check_target(self) -> None:
        if not isinstance(self.requested_target, ReadinessTarget):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.requested_target must be a ReadinessTarget"
            )

    def _check_indicator_results(self, field: str, expected) -> None:
        coerced = coerce_tuple(getattr(self, field), f"ReadinessEvaluationCase.{field}")
        seen: set[str] = set()
        for r in coerced:
            if not isinstance(r, expected):
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.{field} entries must be {expected.__name__}"
                )
            if r.tenant_id != self.tenant_id or r.subject_id != self.subject_id:
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.{field} contains a cross-tenant/subject result"
                )
            if r.context_id != self.context.context_id:
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.{field} result {r.result_id!r} is bound to a "
                    "different AssessmentContext"
                )
            if r.result_id in seen:
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.{field} duplicates result_id {r.result_id!r}"
                )
            seen.add(r.result_id)
        object.__setattr__(self, field, coerced)

    def _check_gate_results(self) -> None:
        coerced = coerce_tuple(self.gate_results, "ReadinessEvaluationCase.gate_results")
        policy_gates = {g.gate_id: g for g in self.readiness_policy.gates}
        seen: set[str] = set()
        for g in coerced:
            if not isinstance(g, GateResult):
                raise ReadinessEvaluationError(
                    "ReadinessEvaluationCase.gate_results entries must be GateResult"
                )
            if g.requested_target is not self.requested_target:
                raise ReadinessEvaluationError(
                    f"gate result {g.gate_id!r} was evaluated for {g.requested_target.value}, "
                    f"not the requested {self.requested_target.value}"
                )
            if g.readiness_policy_ref != self.readiness_policy_ref:
                raise ReadinessEvaluationError(
                    f"gate result {g.gate_id!r} is bound to a different ReadinessPolicy than the "
                    "case (policy_id/version/content_digest/scope/tenant/family must match)"
                )
            owned = policy_gates.get(g.gate_id)
            if owned is None:
                raise ReadinessEvaluationError(
                    f"gate result {g.gate_id!r} names a gate that does not exist in the supplied "
                    "ReadinessPolicy — the policy is the authoritative gate inventory"
                )
            if owned != g.policy_gate:
                raise ReadinessEvaluationError(
                    f"gate result {g.gate_id!r} embeds a PolicyGate that differs from the "
                    "ReadinessPolicy's gate of that id (requirement class, applicability, "
                    "compensability or threshold was redefined)"
                )
            if g.gate_id in seen:
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.gate_results supplies more than one result for "
                    f"gate {g.gate_id!r}"
                )
            seen.add(g.gate_id)
        object.__setattr__(self, "gate_results", coerced)

    def _check_conditions(self) -> None:
        coerced = coerce_tuple(self.conditions, "ReadinessEvaluationCase.conditions")
        seen: set[str] = set()
        for c in coerced:
            if not isinstance(c, ConditionSet):
                raise ReadinessEvaluationError(
                    "ReadinessEvaluationCase.conditions entries must be ConditionSet"
                )
            if c.condition_id in seen:
                raise ReadinessEvaluationError(
                    f"ReadinessEvaluationCase.conditions duplicates condition_id {c.condition_id!r}"
                )
            seen.add(c.condition_id)
        object.__setattr__(self, "conditions", coerced)

    def _check_composite(self) -> None:
        if self.advisory_composite is None:
            return
        if not isinstance(self.advisory_composite, AdvisoryComposite):
            raise ReadinessEvaluationError(
                "ReadinessEvaluationCase.advisory_composite must be an AdvisoryComposite"
            )
        # AdvisoryComposite validates itself (Decimal-only, in-scale, advisory
        # locked). It is carried through and never consulted when selecting a tier.

    # ------------------------------------------------------------------ #
    # Derived views
    # ------------------------------------------------------------------ #
    @property
    def applicable_policy_gates(self) -> tuple:
        """Policy gates whose applicability contains the requested target.

        Derived from the ``ReadinessPolicy`` body — never from the supplied gate
        results — so the authoritative inventory cannot be narrowed by omission.
        Ordered by ``gate_id`` for determinism.
        """

        return tuple(
            sorted(
                (g for g in self.readiness_policy.gates if self.requested_target in g.applicability),
                key=lambda g: g.gate_id,
            )
        )

    @property
    def diagnostic_policy_gates(self) -> tuple:
        """Supplied policy gates not applicable to the requested target."""

        applicable = {g.gate_id for g in self.applicable_policy_gates}
        return tuple(
            sorted(
                (g for g in self.readiness_policy.gates if g.gate_id not in applicable),
                key=lambda g: g.gate_id,
            )
        )

    def canonical_input_digest(self) -> str:
        """A deterministic sha-256 over an **order-independent** projection.

        Component digests are sorted, so two cases that differ only in the order
        their gate results / conditions / indicator results were supplied produce
        the same digest. This is an input fingerprint for the trace — it is not
        evidence, a signature, or an authenticity proof.
        """

        payload = {
            "case_id": self.case_id,
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "context": self.context.canonical_digest(),
            "readiness_policy": self.readiness_policy.canonical_digest(),
            "readiness_policy_ref": self.readiness_policy_ref.canonical_digest(),
            "requested_target": self.requested_target.value,
            "intelligence_results": sorted(r.canonical_digest() for r in self.intelligence_results),
            "capability_results": sorted(r.canonical_digest() for r in self.capability_results),
            "adoption_results": sorted(r.canonical_digest() for r in self.adoption_results),
            "gate_results": sorted(g.canonical_digest() for g in self.gate_results),
            "conditions": sorted(c.canonical_digest() for c in self.conditions),
            "advisory_composite": (
                self.advisory_composite.canonical_digest()
                if self.advisory_composite is not None
                else None
            ),
            "evidence_refs": sorted(self.evidence_refs),
            "assessment_window_ref": self.assessment_window_ref,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
