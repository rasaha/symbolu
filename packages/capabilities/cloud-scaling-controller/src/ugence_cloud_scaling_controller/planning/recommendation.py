"""``CapacityActionRecommendation`` — the immutable, self-revalidating Phase-3 output.

A recommendation records the best capacity ACTION for a forecast, and *why*. It is advisory
only: it recommends, it never executes, authorizes, or verifies an effect, and it says so in
its own fields (``advisory_only=shadow_only=True``; ``actuation_performed=authorization_performed
=effect_verified=False``; ``authority_class=ADVISORY``; ``execution_capability=NONE``).

Construction-safety (the Phase-2 acceptance lesson, applied). The record EMBEDS the
authoritative inputs — the forecast evidence, the current canonical state, the dependency
topology, the cost book, the operating constraints, and the recommendation policy — and
DERIVES every calculated claim from them at construction:

  * each bound digest is re-derived from the embedded object (``forecast_evidence_digest ==
    forecast_evidence.digest()``, and likewise for state/topology/cost/constraints/policy),
    so a caller cannot pair one input with another input's digest;
  * the deterministic :class:`~.scoring.EvaluationContext` is rebuilt via
    :func:`~.scoring.build_context`, and EVERY evaluated candidate's feasibility, cost delta,
    and score breakdown are RECOMPUTED and compared to the stored values — a forged score,
    cost delta, feasibility flag, or fabricated candidate is rejected;
  * the selected plan must be present among the evaluated candidates AND be a feasible
    score-maximizer (no selecting a plan that was never evaluated, and no selecting a plan a
    contradictory score would rank below another);
  * NO_CHANGE must always be present as the mandatory baseline;
  * subject/tenant/scope must agree across the forecast, state, topology, and cost book;
  * temporal safety is enforced: the forecast cutoff precedes the recommendation time, and
    the recommendation validity window lies within the forecast horizon.

``from_dict`` rebuilds the embedded objects and runs the SAME ``__post_init__``, so no
deserialization path bypasses the relationship. The evidence digest is a canonical content
IDENTITY/integrity value — never a signature, authorization, or proof of effect.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..canonical.evidence import AUTHORITY_CLASS_ADVISORY, EXECUTION_CAPABILITY_NONE
from ..canonical.identity import CapacitySubject
from ..canonical.serialization import content_digest
from ..canonical.state import CanonicalCapacityState
from ..forecasting.evidence import CapacityForecastEvidence
from ..forecasting.series import _as_utc
from ..version import __version__ as CONTROLLER_PACKAGE_VERSION
from .candidates import ActionKind, CandidateActionPlan, generate_candidates
from .constraints import OperatingConstraints
from .cost import CostBook
from .policy import RecommendationPolicy, ScoreBreakdown
from .scoring import (
    EvaluationContext,
    build_context,
    evaluate_feasibility,
    plan_cost_delta_minor,
    score_candidate,
    select_best,
)
from .topology import DependencyTopology

RECOMMENDATION_SCHEMA_VERSION = "capacity-action-recommendation-1"
EVALUATED_CANDIDATE_SCHEMA_VERSION = "capacity-evaluated-candidate-1"

_TOL = 1e-6

# Excluded from the identity digest: the digest cannot cover itself; the diagnostic
# annotation is a non-authoritative human note that must not contradict the structured record.
DIGEST_EXCLUDED_FIELDS = ("evidence_digest", "diagnostic_annotation")


class RecommendationError(ValueError):
    """Raised when a recommendation record would be internally inconsistent (fail closed)."""


@dataclass(frozen=True)
class EvaluatedCandidate:
    """One candidate's deterministic evaluation: feasibility + (if feasible) policy score."""

    plan: CandidateActionPlan
    feasible: bool
    violations: Tuple[str, ...]
    cost_delta_minor: int
    score_breakdown: Optional[ScoreBreakdown] = None
    schema_version: str = EVALUATED_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CandidateActionPlan):
            raise RecommendationError("evaluated candidate plan must be a CandidateActionPlan")
        if not isinstance(self.feasible, bool):
            raise RecommendationError("feasible must be a bool")
        if not isinstance(self.violations, tuple):
            object.__setattr__(self, "violations", tuple(self.violations))
        for v in self.violations:
            if not isinstance(v, str) or v == "":
                raise RecommendationError("violations must be non-empty strings")
        if isinstance(self.cost_delta_minor, bool) or not isinstance(self.cost_delta_minor, int):
            raise RecommendationError("cost_delta_minor must be an int")
        if self.feasible:
            if self.violations:
                raise RecommendationError("a feasible candidate must have no violations")
            if not isinstance(self.score_breakdown, ScoreBreakdown):
                raise RecommendationError("a feasible candidate requires a ScoreBreakdown")
        else:
            if not self.violations:
                raise RecommendationError("an infeasible candidate requires >= 1 violation")
            if self.score_breakdown is not None:
                raise RecommendationError("an infeasible candidate must not carry a score")

    @property
    def total_score(self) -> Optional[float]:
        return self.score_breakdown.total_score if self.score_breakdown is not None else None

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan": self.plan.to_canonical_dict(),
            "feasible": self.feasible,
            "violations": list(self.violations),
            "cost_delta_minor": self.cost_delta_minor,
            "score_breakdown": self.score_breakdown.to_canonical_dict() if self.score_breakdown else None,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "EvaluatedCandidate":
        if not isinstance(data, Mapping):
            raise RecommendationError("evaluated candidate must be a mapping")
        known = {"schema_version", "plan", "feasible", "violations", "cost_delta_minor", "score_breakdown"}
        unknown = set(data) - known
        if unknown:
            raise RecommendationError(f"unknown evaluated candidate field(s): {sorted(unknown)}")
        for req in ("plan", "feasible", "violations", "cost_delta_minor"):
            if req not in data:
                raise RecommendationError(f"evaluated candidate requires '{req}'")
        sb = data.get("score_breakdown")
        return cls(
            plan=CandidateActionPlan.from_dict(data["plan"]),
            feasible=data["feasible"],
            violations=tuple(data["violations"]),
            cost_delta_minor=data["cost_delta_minor"],
            score_breakdown=ScoreBreakdown.from_dict(sb) if sb is not None else None,
            schema_version=data.get("schema_version", EVALUATED_CANDIDATE_SCHEMA_VERSION),
        )


def _subject_scope_equal(a: CapacitySubject, b: CapacitySubject) -> bool:
    return a == b


@dataclass(frozen=True)
class CapacityActionRecommendation:
    """Immutable, self-revalidating advisory capacity-action recommendation."""

    recommendation_id: str
    forecast_evidence: CapacityForecastEvidence
    current_state: CanonicalCapacityState
    cost_book: CostBook
    constraints: OperatingConstraints
    policy: RecommendationPolicy
    evaluated_candidates: Tuple[EvaluatedCandidate, ...]
    selected_plan_id: str
    recommendation_time: datetime
    validity_seconds: float
    topology: Optional[DependencyTopology] = None
    reason_codes: Tuple[str, ...] = ()
    dependency_explanation: str = ""
    diagnostic_annotation: str = ""
    controller_package_version: str = CONTROLLER_PACKAGE_VERSION
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    # Fixed advisory / shadow classification — never claims execution, authorization, effect.
    authority_class: str = AUTHORITY_CLASS_ADVISORY
    execution_capability: str = EXECUTION_CAPABILITY_NONE
    advisory_only: bool = True
    shadow_only: bool = True
    actuation_performed: bool = False
    authorization_performed: bool = False
    effect_verified: bool = False

    # ------------------------------------------------------------------ validation
    def __post_init__(self) -> None:
        # Fixed advisory invariants.
        if self.advisory_only is not True or self.shadow_only is not True:
            raise RecommendationError("recommendation must be advisory-only and shadow-only")
        if self.actuation_performed is not False:
            raise RecommendationError("actuation_performed must be False")
        if self.authorization_performed is not False:
            raise RecommendationError("authorization_performed must be False")
        if self.effect_verified is not False:
            raise RecommendationError("effect_verified must be False")
        if self.authority_class != AUTHORITY_CLASS_ADVISORY:
            raise RecommendationError("authority_class must be ADVISORY")
        if self.execution_capability != EXECUTION_CAPABILITY_NONE:
            raise RecommendationError("execution_capability must be NONE")

        if not isinstance(self.recommendation_id, str) or self.recommendation_id == "":
            raise RecommendationError("recommendation_id must be a non-empty string")
        if not isinstance(self.forecast_evidence, CapacityForecastEvidence):
            raise RecommendationError("forecast_evidence must be a CapacityForecastEvidence")
        if not isinstance(self.current_state, CanonicalCapacityState):
            raise RecommendationError("current_state must be a CanonicalCapacityState")
        if not isinstance(self.cost_book, CostBook):
            raise RecommendationError("cost_book must be a CostBook")
        if not isinstance(self.constraints, OperatingConstraints):
            raise RecommendationError("constraints must be an OperatingConstraints")
        if not isinstance(self.policy, RecommendationPolicy):
            raise RecommendationError("policy must be a RecommendationPolicy")
        if self.topology is not None and not isinstance(self.topology, DependencyTopology):
            raise RecommendationError("topology must be a DependencyTopology or None")
        if not isinstance(self.recommendation_time, datetime):
            raise RecommendationError("recommendation_time must be a datetime")
        if isinstance(self.validity_seconds, bool) or not isinstance(self.validity_seconds, (int, float)) \
                or not math.isfinite(self.validity_seconds) or self.validity_seconds <= 0:
            raise RecommendationError("validity_seconds must be a finite number > 0")
        if not isinstance(self.evaluated_candidates, tuple):
            object.__setattr__(self, "evaluated_candidates", tuple(self.evaluated_candidates))
        if not self.evaluated_candidates:
            raise RecommendationError("evaluated_candidates must be non-empty")
        for ec in self.evaluated_candidates:
            if not isinstance(ec, EvaluatedCandidate):
                raise RecommendationError("every evaluated candidate must be an EvaluatedCandidate")
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))

        fc = self.forecast_evidence.forecast

        # --- subject / tenant / scope binding --------------------------------------
        subject = self.current_state.subject
        if fc.subject != subject:
            raise RecommendationError("forecast subject must equal current_state subject")
        if self.cost_book.subject != subject:
            raise RecommendationError("cost_book subject must equal the recommendation subject")
        if self.topology is not None and self.topology.subject != subject:
            raise RecommendationError("topology subject must equal the recommendation subject")

        # --- temporal safety (every embedded evidence timestamp + validity window) --
        # Fail closed on future, stale, contradictory, or horizon-incompatible evidence at
        # BOTH direct construction and from_dict, mirroring the pipeline's typed abstentions.
        cutoff = _as_utc(fc.forecast_cutoff)
        rec_time = _as_utc(self.recommendation_time)
        if cutoff > rec_time:
            raise RecommendationError("forecast cutoff must not be after the recommendation time")
        # Canonical forecast relationship: forecast_for MUST equal forecast_cutoff + the
        # declared horizon duration. A contradictory endpoint (before the cutoff) or an
        # inflated endpoint (beyond cutoff + horizon, which would let a longer validity window
        # look in-bounds) fails closed here at construction AND reconstruction.
        horizon_seconds = float(fc.horizon.seconds)
        if not (horizon_seconds > 0):
            raise RecommendationError("forecast horizon duration must be > 0")
        forecast_for_dt = _as_utc(fc.forecast_for)
        expected_for_ts = cutoff.timestamp() + horizon_seconds
        if abs(forecast_for_dt.timestamp() - expected_for_ts) > 1e-6:
            raise RecommendationError(
                "forecast_for must equal forecast_cutoff + horizon "
                "(contradictory or inflated forecast endpoint)")
        # Forecast horizon must still be ahead of the recommendation time.
        if forecast_for_dt <= rec_time:
            raise RecommendationError("forecast horizon must be after the recommendation time")
        # Current canonical state must not be observed in the future.
        if _as_utc(self.current_state.observed_at) > rec_time:
            raise RecommendationError("current_state.observed_at must not be after the recommendation time")
        # Topology as_of must not be in the future.
        if self.topology is not None and _as_utc(self.topology.as_of) > rec_time:
            raise RecommendationError("topology as_of must not be after the recommendation time")
        # Every cost-evidence entry must be effective at the recommendation time (no
        # future-dated or stale/expired pricing masquerading as current).
        for entry in self.cost_book.entries:
            if not entry.is_effective_at(self.recommendation_time):
                raise RecommendationError("cost evidence is not effective at the recommendation time")
        # Operator-set forecast validity window: the forecast must not be expired.
        if self.constraints.forecast_validity_seconds is not None:
            age = (rec_time - cutoff).total_seconds()
            if age > self.constraints.forecast_validity_seconds:
                raise RecommendationError("forecast age exceeds the constraint forecast_validity_seconds")
        # Recommendation validity window must not extend beyond EITHER the forecast endpoint
        # OR the declared horizon duration measured from the cutoff (defence-in-depth: the two
        # coincide while forecast_for is pinned above, but both are asserted explicitly).
        validity_end = rec_time.timestamp() + float(self.validity_seconds)
        if validity_end > forecast_for_dt.timestamp() + 1e-6:
            raise RecommendationError("recommendation validity must not extend beyond the forecast endpoint")
        if validity_end > cutoff.timestamp() + horizon_seconds + 1e-6:
            raise RecommendationError("recommendation validity must not extend beyond the declared horizon duration")

        # --- rebuild the deterministic context and recompute every candidate -------
        try:
            ctx = build_context(
                self.forecast_evidence, self.current_state, self.topology,
                self.cost_book, self.constraints, recommendation_time=self.recommendation_time,
            )
        except Exception as exc:  # ScoringError / value errors -> record is inconsistent
            raise RecommendationError(f"recommendation inputs are inconsistent: {exc}") from exc

        # --- canonical candidate-set binding ---------------------------------------
        # Re-run the SAME bounded candidate generation the pipeline used and require exact
        # semantic set equality with evaluated_candidates. This rejects an omitted candidate
        # (a reduced set that lets a worse plan "win"), a fabricated/surplus candidate, a
        # duplicated candidate, or a content-tampered candidate — none of which the
        # per-candidate recompute above could catch on its own.
        canonical_plans = generate_candidates(
            ctx.primary_subject, ctx.current_capacity, ctx.required_capacity,
            allowed_step=self.constraints.allowed_step,
            min_capacity=self.constraints.min_capacity,
            max_capacity=self.constraints.effective_ceiling(),
            dependency=ctx.dependency_subject,
            dependency_current=ctx.dependency_current,
            dependency_required=ctx.dependency_required,
        )
        canonical_by_id = {p.plan_id: p.digest() for p in canonical_plans}
        if len(canonical_by_id) != len(canonical_plans):  # defensive; generation is unique
            raise RecommendationError("canonical candidate generation produced a non-unique set")
        evaluated_by_id: Dict[str, str] = {}
        for ec in self.evaluated_candidates:
            if ec.plan.plan_id in evaluated_by_id:
                raise RecommendationError(f"duplicate evaluated candidate: {ec.plan.plan_id!r}")
            evaluated_by_id[ec.plan.plan_id] = ec.plan.digest()
        if evaluated_by_id != canonical_by_id:
            missing = sorted(set(canonical_by_id) - set(evaluated_by_id))
            surplus = sorted(set(evaluated_by_id) - set(canonical_by_id))
            tampered = sorted(k for k in canonical_by_id.keys() & evaluated_by_id.keys()
                              if canonical_by_id[k] != evaluated_by_id[k])
            raise RecommendationError(
                "evaluated_candidates must be exactly the canonical generated candidate set "
                f"(missing={missing}, surplus={surplus}, tampered={tampered})")

        seen_plan_ids = set()
        seen_plan_digests = set()
        has_no_change = False
        selected: Optional[EvaluatedCandidate] = None
        for ec in self.evaluated_candidates:
            pid = ec.plan.plan_id
            if pid in seen_plan_ids:
                raise RecommendationError(f"duplicate evaluated plan_id: {pid!r}")
            seen_plan_ids.add(pid)
            seen_plan_digests.add(ec.plan.digest())
            if ec.plan.action_kind is ActionKind.NO_CHANGE:
                has_no_change = True
            # Recompute feasibility, cost delta, and score — reject any forged value.
            exp_violations = tuple(v.value for v in evaluate_feasibility(ec.plan, ctx))
            exp_feasible = not exp_violations
            if ec.feasible != exp_feasible:
                raise RecommendationError(f"feasibility of {pid!r} does not match recomputation")
            if set(ec.violations) != set(exp_violations):
                raise RecommendationError(f"violations of {pid!r} do not match recomputation")
            exp_cost = plan_cost_delta_minor(ec.plan, ctx)
            if ec.cost_delta_minor != exp_cost:
                raise RecommendationError(f"cost_delta_minor of {pid!r} does not match recomputation")
            if exp_feasible:
                exp_score = score_candidate(ec.plan, ctx, self.policy)
                if ec.score_breakdown is None or abs(ec.score_breakdown.total_score - exp_score.total_score) > _TOL:
                    raise RecommendationError(f"score of {pid!r} does not match recomputation")
                if ec.score_breakdown.policy_digest != self.policy.digest():
                    raise RecommendationError(f"score of {pid!r} bound to a different policy digest")
                for fname, fval in exp_score.features.items():
                    if abs(ec.score_breakdown.features[fname] - fval) > _TOL:
                        raise RecommendationError(f"feature {fname} of {pid!r} does not match recomputation")
            if pid == self.selected_plan_id:
                selected = ec

        if not has_no_change:
            raise RecommendationError("evaluated_candidates must include the NO_CHANGE baseline")
        if selected is None:
            raise RecommendationError("selected_plan_id is absent from evaluated_candidates")
        if not selected.feasible:
            raise RecommendationError("selected plan must be feasible")

        # Selected must be the unique winner under the SAME coverage-first, policy-scored,
        # deterministic selection rule the pipeline used (no forged winner, no ambiguity).
        triples = [(ec.plan.plan_id, ec.score_breakdown.features["coverage"], ec.total_score)
                   for ec in self.evaluated_candidates if ec.feasible]
        winner_id, ambiguous = select_best(triples, self.policy)
        if ambiguous:
            raise RecommendationError("a recommendation cannot be built from an ambiguous best plan")
        if winner_id != self.selected_plan_id:
            raise RecommendationError("selected plan is not the winner under the recommendation policy")

    # ------------------------------------------------------------------ accessors
    @property
    def subject(self) -> CapacitySubject:
        return self.current_state.subject

    @property
    def selected(self) -> EvaluatedCandidate:
        for ec in self.evaluated_candidates:
            if ec.plan.plan_id == self.selected_plan_id:
                return ec
        raise RecommendationError("selected plan missing")  # unreachable after validation

    @property
    def selected_plan(self) -> CandidateActionPlan:
        return self.selected.plan

    @property
    def alternatives(self) -> Tuple[EvaluatedCandidate, ...]:
        """Feasible, non-selected candidates ranked by descending score (ties by plan_id)."""
        others = [ec for ec in self.evaluated_candidates
                  if ec.feasible and ec.plan.plan_id != self.selected_plan_id]
        return tuple(sorted(others, key=lambda e: (-(e.total_score or 0.0), e.plan.plan_id)))

    @property
    def rejected(self) -> Tuple[EvaluatedCandidate, ...]:
        """Infeasible candidates with their typed violation reasons."""
        return tuple(ec for ec in self.evaluated_candidates if not ec.feasible)

    @property
    def estimated_cost_change_minor(self) -> int:
        return self.selected.cost_delta_minor

    @property
    def currency(self) -> str:
        return self.cost_book.entries[0].currency if self.cost_book.entries else ""

    @property
    def expected_forecast_coverage(self) -> float:
        sb = self.selected.score_breakdown
        return sb.features["coverage"] if sb else 0.0

    @property
    def forecast_confidence(self) -> float:
        unc = self.forecast_evidence.forecast.uncertainty
        return float(unc.requested_coverage) if unc.available else 0.0

    def forecast_evidence_digest(self) -> str:
        return self.forecast_evidence.digest()

    def canonical_state_digest(self) -> str:
        return self.current_state.digest()

    def topology_digest(self) -> Optional[str]:
        return self.topology.digest() if self.topology is not None else None

    def cost_evidence_digest(self) -> str:
        return self.cost_book.digest()

    def constraint_digest(self) -> str:
        return self.constraints.digest()

    def policy_digest(self) -> str:
        return self.policy.digest()

    def validity_interval(self) -> Tuple[datetime, float]:
        return (self.recommendation_time, self.validity_seconds)

    # ------------------------------------------------------------------ serialization
    def to_canonical_dict(self, *, include_digest: bool = True) -> Dict[str, Any]:
        # Evaluated candidates sorted by plan digest so identity is order-independent.
        candidates = sorted(self.evaluated_candidates, key=lambda e: e.plan.digest())
        data: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "controller_package_version": self.controller_package_version,
            "recommendation_id": self.recommendation_id,
            "subject": self.subject.to_canonical_dict(),
            "forecast_evidence": self.forecast_evidence.to_canonical_dict(),
            "forecast_evidence_digest": self.forecast_evidence_digest(),
            "canonical_state": self.current_state.to_canonical_dict(),
            "canonical_state_digest": self.canonical_state_digest(),
            "topology": self.topology.to_canonical_dict() if self.topology else None,
            "topology_digest": self.topology_digest(),
            "cost_book": self.cost_book.to_canonical_dict(),
            "cost_evidence_digest": self.cost_evidence_digest(),
            "constraints": self.constraints.to_canonical_dict(),
            "constraint_digest": self.constraint_digest(),
            "policy": self.policy.to_canonical_dict(),
            "policy_digest": self.policy_digest(),
            "evaluated_candidates": [ec.to_canonical_dict() for ec in candidates],
            "selected_plan_id": self.selected_plan_id,
            "selected_plan_digest": self.selected_plan.digest(),
            "estimated_cost_change_minor": self.estimated_cost_change_minor,
            "currency": self.currency,
            "expected_forecast_coverage": self.expected_forecast_coverage,
            "forecast_confidence": self.forecast_confidence,
            "reason_codes": list(self.reason_codes),
            "dependency_explanation": self.dependency_explanation,
            "recommendation_time": self.recommendation_time,
            "validity_seconds": self.validity_seconds,
            "diagnostic_annotation": self.diagnostic_annotation,
            "authority_class": self.authority_class,
            "execution_capability": self.execution_capability,
            "advisory_only": self.advisory_only,
            "shadow_only": self.shadow_only,
            "actuation_performed": self.actuation_performed,
            "authorization_performed": self.authorization_performed,
            "effect_verified": self.effect_verified,
        }
        if include_digest:
            data["evidence_digest"] = self.digest()
        return data

    def _digest_payload(self) -> Dict[str, Any]:
        data = self.to_canonical_dict(include_digest=False)
        for excluded in DIGEST_EXCLUDED_FIELDS:
            data.pop(excluded, None)
        return data

    def digest(self) -> str:
        """Deterministic ``sha256:`` content identity over all authoritative fields."""
        return content_digest("capacity_action_recommendation", self.schema_version,
                              self._digest_payload())

    @classmethod
    def from_dict(cls, data: Any) -> "CapacityActionRecommendation":
        """Reconstruct + fully re-validate a recommendation from its canonical dict."""
        if not isinstance(data, Mapping):
            raise RecommendationError("recommendation must be a mapping")
        required = {
            "recommendation_id", "forecast_evidence", "canonical_state", "cost_book",
            "constraints", "policy", "evaluated_candidates", "selected_plan_id",
            "recommendation_time", "validity_seconds",
        }
        missing = required - set(data)
        if missing:
            raise RecommendationError(f"recommendation missing field(s): {sorted(missing)}")
        # Reject surplus top-level fields that are not part of the canonical form — a stray
        # field must never be a silent channel that bypasses the derived-from-inputs checks.
        allowed = required | {
            "schema_version", "controller_package_version", "subject", "forecast_evidence_digest",
            "canonical_state_digest", "topology", "topology_digest", "cost_evidence_digest",
            "constraint_digest", "policy_digest", "selected_plan_digest",
            "estimated_cost_change_minor", "currency", "expected_forecast_coverage",
            "forecast_confidence", "reason_codes", "dependency_explanation",
            "diagnostic_annotation", "evidence_digest", "authority_class",
            "execution_capability", "advisory_only", "shadow_only", "actuation_performed",
            "authorization_performed", "effect_verified",
        }
        surplus = set(data) - allowed
        if surplus:
            raise RecommendationError(f"unknown recommendation field(s): {sorted(surplus)}")
        rec_time = data["recommendation_time"]
        if not isinstance(rec_time, datetime):
            raise RecommendationError("recommendation_time must be a datetime")
        topology = (DependencyTopology.from_dict(data["topology"])
                    if data.get("topology") is not None else None)
        return cls(
            recommendation_id=data["recommendation_id"],
            forecast_evidence=_forecast_evidence_from_dict(data["forecast_evidence"]),
            current_state=CanonicalCapacityState.from_dict(data["canonical_state"]),
            cost_book=CostBook.from_dict(data["cost_book"]),
            constraints=OperatingConstraints.from_dict(data["constraints"]),
            policy=RecommendationPolicy.from_dict(data["policy"]),
            evaluated_candidates=tuple(
                EvaluatedCandidate.from_dict(e) for e in data["evaluated_candidates"]),
            selected_plan_id=data["selected_plan_id"],
            recommendation_time=rec_time,
            validity_seconds=data["validity_seconds"],
            topology=topology,
            reason_codes=tuple(data.get("reason_codes") or ()),
            dependency_explanation=data.get("dependency_explanation", ""),
            diagnostic_annotation=data.get("diagnostic_annotation", ""),
            controller_package_version=data.get("controller_package_version", CONTROLLER_PACKAGE_VERSION),
            schema_version=data.get("schema_version", RECOMMENDATION_SCHEMA_VERSION),
            # Pass every supplied fixed advisory field through so a tampered/contradictory
            # value fails closed in __post_init__ rather than being silently normalized to a
            # safe default on reconstruction.
            authority_class=data.get("authority_class", AUTHORITY_CLASS_ADVISORY),
            execution_capability=data.get("execution_capability", EXECUTION_CAPABILITY_NONE),
            advisory_only=data.get("advisory_only", True),
            shadow_only=data.get("shadow_only", True),
            actuation_performed=data.get("actuation_performed", False),
            authorization_performed=data.get("authorization_performed", False),
            effect_verified=data.get("effect_verified", False),
        )


def _forecast_evidence_from_dict(data: Any) -> CapacityForecastEvidence:
    """Reconstruct a :class:`CapacityForecastEvidence` from its canonical dict.

    The forecasting layer's evidence has no public ``from_dict``; Phase 3 reconstructs the
    embedded forecast and rebinds it through the same immutable evidence dataclass so the
    recommendation's ``from_dict`` path re-derives (and re-validates) the forecast evidence
    digest exactly like direct construction."""
    from ..forecasting.forecast import CapacityForecast
    from ..forecasting.abstention import AbstentionReason
    from ..forecasting.targets import ForecastTarget
    from ..forecasting.window import ForecastHorizon
    from ..forecasting.uncertainty import UncertaintyInterval
    if not isinstance(data, Mapping):
        raise RecommendationError("forecast_evidence must be a mapping")
    fcd = data.get("forecast")
    if not isinstance(fcd, Mapping):
        raise RecommendationError("forecast_evidence requires an embedded forecast")
    horizon = ForecastHorizon(seconds=fcd["horizon"]["seconds"], label=fcd["horizon"].get("label", ""))
    unc = _uncertainty_from_dict(fcd["uncertainty"])
    reason = fcd.get("abstention_reason")
    forecast = CapacityForecast(
        schema_version=fcd["schema_version"],
        subject=CapacitySubject.from_dict(fcd["subject"]),
        correlation_id=fcd.get("correlation_id"),
        target=ForecastTarget(fcd["target"]),
        forecast_cutoff=fcd["forecast_cutoff"],
        horizon=horizon,
        forecast_for=fcd["forecast_for"],
        model_id=fcd["model_id"],
        model_version=fcd["model_version"],
        status=fcd["status"],
        unit=fcd["unit"],
        input_window_digest=fcd["input_window_digest"],
        model_config_digest=fcd["model_config_digest"],
        uncertainty=unc,
        point_estimate=fcd.get("point_estimate"),
        abstention_reason=AbstentionReason(reason) if reason else None,
        warnings=tuple(fcd.get("warnings") or ()),
        value_space=fcd.get("value_space", "projected_without_conversion"),
        normalization_applied=fcd.get("normalization_applied", False),
    )
    return CapacityForecastEvidence(
        evidence_schema_version=data["evidence_schema_version"],
        series_schema_version=data["series_schema_version"],
        input_window_schema_version=data["input_window_schema_version"],
        forecast_schema_version=data["forecast_schema_version"],
        controller_package_version=data["controller_package_version"],
        source_series_digest=data["source_series_digest"],
        input_window_digest=data["input_window_digest"],
        feature_config_digest=data["feature_config_digest"],
        admission_policy_digest=data["admission_policy_digest"],
        uncertainty_config_digest=data["uncertainty_config_digest"],
        model_config_digest=data["model_config_digest"],
        normalization_policy_id=data.get("normalization_policy_id"),
        normalization_policy_digest=data.get("normalization_policy_digest"),
        forecast=forecast,
        evidence_produced_at=data["evidence_produced_at"],
        diagnostic_annotation=data.get("diagnostic_annotation", ""),
    )


def _uncertainty_from_dict(data: Any):
    from ..forecasting.uncertainty import UncertaintyInterval
    return UncertaintyInterval(
        method=data["method"],
        requested_coverage=data["requested_coverage"],
        calibration_sample_count=data["calibration_sample_count"],
        available=data["available"],
        lower=data.get("lower"),
        upper=data.get("upper"),
        unavailable_reason=data.get("unavailable_reason"),
        calibration_window_id=data.get("calibration_window_id", ""),
    )


RECOMMENDATION_ABSTENTION_SCHEMA_VERSION = "capacity-recommendation-abstention-1"


@dataclass(frozen=True)
class RecommendationAbstention:
    """Immutable, typed abstention: the recommender declined to recommend an action.

    An abstention is a first-class Phase-3 output. It binds the subject, the typed reason,
    the recommendation time, and whatever authoritative input digests were available before
    the abstention was reached (so the abstention is auditable). It NEVER carries a selected
    plan and never claims an action was attempted."""

    subject: CapacitySubject
    reason: "RecommendationAbstentionReason"
    recommendation_time: datetime
    detail: str = ""
    forecast_evidence_digest: Optional[str] = None
    canonical_state_digest: Optional[str] = None
    topology_digest: Optional[str] = None
    cost_evidence_digest: Optional[str] = None
    constraint_digest: Optional[str] = None
    policy_digest: Optional[str] = None
    controller_package_version: str = CONTROLLER_PACKAGE_VERSION
    schema_version: str = RECOMMENDATION_ABSTENTION_SCHEMA_VERSION

    authority_class: str = AUTHORITY_CLASS_ADVISORY
    execution_capability: str = EXECUTION_CAPABILITY_NONE
    advisory_only: bool = True
    shadow_only: bool = True
    actuation_performed: bool = False

    def __post_init__(self) -> None:
        from .abstention import RecommendationAbstentionReason
        if not isinstance(self.subject, CapacitySubject):
            raise RecommendationError("abstention subject must be a CapacitySubject")
        if not isinstance(self.reason, RecommendationAbstentionReason):
            raise RecommendationError("abstention reason must be a RecommendationAbstentionReason")
        if not isinstance(self.recommendation_time, datetime):
            raise RecommendationError("recommendation_time must be a datetime")
        if self.advisory_only is not True or self.shadow_only is not True:
            raise RecommendationError("abstention must be advisory-only and shadow-only")
        if self.actuation_performed is not False:
            raise RecommendationError("actuation_performed must be False")
        if self.authority_class != AUTHORITY_CLASS_ADVISORY:
            raise RecommendationError("authority_class must be ADVISORY")
        if self.execution_capability != EXECUTION_CAPABILITY_NONE:
            raise RecommendationError("execution_capability must be NONE")

    @property
    def is_abstained(self) -> bool:
        return True

    def to_canonical_dict(self, *, include_digest: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "controller_package_version": self.controller_package_version,
            "subject": self.subject.to_canonical_dict(),
            "reason": self.reason.value,
            "recommendation_time": self.recommendation_time,
            "detail": self.detail,
            "forecast_evidence_digest": self.forecast_evidence_digest,
            "canonical_state_digest": self.canonical_state_digest,
            "topology_digest": self.topology_digest,
            "cost_evidence_digest": self.cost_evidence_digest,
            "constraint_digest": self.constraint_digest,
            "policy_digest": self.policy_digest,
            "authority_class": self.authority_class,
            "execution_capability": self.execution_capability,
            "advisory_only": self.advisory_only,
            "shadow_only": self.shadow_only,
            "actuation_performed": self.actuation_performed,
        }
        if include_digest:
            data["evidence_digest"] = self.digest()
        return data

    def digest(self) -> str:
        data = self.to_canonical_dict(include_digest=False)
        return content_digest("capacity_recommendation_abstention", self.schema_version, data)

    @classmethod
    def from_dict(cls, data: Any) -> "RecommendationAbstention":
        from .abstention import RecommendationAbstentionReason
        if not isinstance(data, Mapping):
            raise RecommendationError("abstention must be a mapping")
        for req in ("subject", "reason", "recommendation_time"):
            if req not in data:
                raise RecommendationError(f"abstention requires '{req}'")
        # Reject surplus fields (matching the recommendation serializer) so a stray field is
        # never a silent bypass channel.
        allowed = {
            "schema_version", "controller_package_version", "subject", "reason",
            "recommendation_time", "detail", "forecast_evidence_digest", "canonical_state_digest",
            "topology_digest", "cost_evidence_digest", "constraint_digest", "policy_digest",
            "evidence_digest", "authority_class", "execution_capability", "advisory_only",
            "shadow_only", "actuation_performed",
        }
        surplus = set(data) - allowed
        if surplus:
            raise RecommendationError(f"unknown abstention field(s): {sorted(surplus)}")
        rec_time = data["recommendation_time"]
        if not isinstance(rec_time, datetime):
            raise RecommendationError("recommendation_time must be a datetime")
        try:
            reason = RecommendationAbstentionReason(data["reason"])
        except ValueError as exc:
            raise RecommendationError(f"unsupported abstention reason: {data['reason']!r}") from exc
        return cls(
            subject=CapacitySubject.from_dict(data["subject"]),
            reason=reason,
            recommendation_time=rec_time,
            detail=data.get("detail", ""),
            forecast_evidence_digest=data.get("forecast_evidence_digest"),
            canonical_state_digest=data.get("canonical_state_digest"),
            topology_digest=data.get("topology_digest"),
            cost_evidence_digest=data.get("cost_evidence_digest"),
            constraint_digest=data.get("constraint_digest"),
            policy_digest=data.get("policy_digest"),
            controller_package_version=data.get("controller_package_version", CONTROLLER_PACKAGE_VERSION),
            schema_version=data.get("schema_version", RECOMMENDATION_ABSTENTION_SCHEMA_VERSION),
            # Pass the advisory/authority fields through so a tampered value fails closed in
            # __post_init__ rather than being silently normalized on reconstruction.
            authority_class=data.get("authority_class", AUTHORITY_CLASS_ADVISORY),
            execution_capability=data.get("execution_capability", EXECUTION_CAPABILITY_NONE),
            advisory_only=data.get("advisory_only", True),
            shadow_only=data.get("shadow_only", True),
            actuation_performed=data.get("actuation_performed", False),
        )


__all__ = [
    "RECOMMENDATION_SCHEMA_VERSION",
    "EVALUATED_CANDIDATE_SCHEMA_VERSION",
    "RECOMMENDATION_ABSTENTION_SCHEMA_VERSION",
    "DIGEST_EXCLUDED_FIELDS",
    "RecommendationError",
    "EvaluatedCandidate",
    "CapacityActionRecommendation",
    "RecommendationAbstention",
]
