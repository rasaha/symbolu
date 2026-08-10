"""TAP core engine — the vendor assertion-governance engine (pure).

This package is the TAP *product core*. Per the platform's dependency rules it
imports **neither** the DGM kernel **nor** the provider framework: it speaks only
its own native assertion-governance vocabulary. The provider layer
(``tap_provider.provider``) adapts this core onto the neutral
``AssertionGovernanceProvider`` contract.

TAP evaluates whether a *material assertion* is adequately supported by supplied
*evidence*, and returns a structured, component-level result. It never authorizes
or executes actions.

Deterministic and offline: a result is a pure function of the request and the
configured policy. Configurable failure flags simulate a real engine's error
modes (timeout / unavailable / malformed / config) so the provider's error
translation can be validated without a network or a live model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


# --- native exceptions (must never cross the provider boundary) -------------

class TapError(Exception):
    """Base class for TAP engine failures."""


class TapTimeout(TapError):
    """The engine did not produce a determination within its deadline."""


class TapUnavailable(TapError):
    """The engine (or its backing evaluator) is not currently available."""


class TapConfigError(TapError):
    """The engine configuration is invalid."""


class TapMalformedResult(TapError):
    """The engine produced a result that failed its own schema."""


class TapProtocolError(TapError):
    """The engine speaks an incompatible protocol / contract version."""


# --- native vocabulary ------------------------------------------------------

class TapOutcome(str, Enum):
    """TAP-native assertion outcomes.

    ``SUPPORTED`` / ``UNSUPPORTED`` / ``CONSTRAINED`` / ``INDETERMINATE`` are the
    determinations. ``UNKNOWN`` is a native *non-determination* (unresolved /
    unrecognized) that must map fail-safely to INDETERMINATE — never SUPPORTED.
    """

    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONSTRAINED = "CONSTRAINED"
    INDETERMINATE = "INDETERMINATE"
    UNKNOWN = "UNKNOWN"


#: Reason code stamped when the reference engine's evidence-derived ``SUPPORTED``
#: rests on the **default** stance (no per-assertion rule and no explicit
#: ``stance:<id>`` context) — i.e. it presumes support from mere evidence
#: *presence*, rather than an explicit affirmative determination. Downstream
#: consumers that require an explicit determination (e.g. the RA-5 production
#: Control-Assurance adapter) must treat presumptive support as *not* a PASS
#: (RA-5 audit H-1). It is additive metadata; it never changes the native outcome.
PRESUMPTIVE_SUPPORT_REASON = "presumptive_support"


class TapEvidenceClass(str, Enum):
    """Provenance class of an evidence item (kept separate from support)."""

    DIRECT = "direct"
    DERIVED = "derived"
    POLICY = "policy"
    HISTORICAL = "historical"
    MODEL_GENERATED = "model_generated"
    HUMAN_PROVIDED = "human_provided"


@dataclass(frozen=True)
class TapEvidenceItem:
    """A structured evidence projection with provenance kept separate from support.

    ``content`` is a governed excerpt only — never an unrestricted source
    document. Provenance/authority describe *where the evidence came from*, which
    is distinct from *whether it supports* the assertion.
    """

    evidence_id: str
    source_type: str = ""
    source_reference: str = ""
    content: str = ""
    provenance: str = ""
    evidence_class: TapEvidenceClass = TapEvidenceClass.DIRECT
    effective_period: str = ""
    authority: str = ""
    fingerprint: str = ""

    def with_fingerprint(self) -> "TapEvidenceItem":
        if self.fingerprint:
            return self
        payload = json.dumps(
            {"id": self.evidence_id, "ref": self.source_reference,
             "content": self.content, "prov": self.provenance},
            sort_keys=True, default=str)
        fp = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return TapEvidenceItem(
            evidence_id=self.evidence_id, source_type=self.source_type,
            source_reference=self.source_reference, content=self.content,
            provenance=self.provenance, evidence_class=self.evidence_class,
            effective_period=self.effective_period, authority=self.authority,
            fingerprint=fp)


@dataclass(frozen=True)
class TapConstraint:
    """A typed control limiting what may be asserted (e.g. required_qualifier)."""

    type: str
    value: str = ""


@dataclass(frozen=True)
class TapObligation:
    """A typed obligation requiring an additional step/disclosure (e.g. citation)."""

    type: str
    value: str = ""


@dataclass(frozen=True)
class TapEvaluationRequest:
    """TAP-native request to evaluate an assertion against evidence."""

    assertion: str
    evidence: tuple[TapEvidenceItem, ...] = ()
    context: Mapping[str, object] = field(default_factory=dict)
    assertion_type: Optional[str] = None
    source_identity: str = ""
    policy_references: tuple[str, ...] = ()
    correlation_id: str = ""
    trace_id: str = ""


@dataclass(frozen=True)
class TapEvaluationResult:
    """TAP-native structured assertion-governance result."""

    outcome: TapOutcome
    evidence_coverage: Optional[float] = None
    supported_components: tuple[str, ...] = ()
    unsupported_components: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    covered_evidence_ids: tuple[str, ...] = ()
    constraints: tuple[TapConstraint, ...] = ()
    obligations: tuple[TapObligation, ...] = ()
    reason_codes: tuple[str, ...] = ()
    trace_id: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class TapRule:
    """A deterministic per-assertion policy outcome for the reference engine."""

    outcome: TapOutcome
    evidence_coverage: Optional[float] = None
    supported_components: tuple[str, ...] = ()
    unsupported_components: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    constraints: tuple[TapConstraint, ...] = ()
    obligations: tuple[TapObligation, ...] = ()
    reason_codes: tuple[str, ...] = ()


class TapEngine:
    """A deterministic TAP assertion-governance engine.

    Policy resolution order for an assertion:

    1. an explicit :class:`TapRule` in ``rules`` (keyed by assertion text) wins;
    2. otherwise the outcome is *derived from the supplied evidence*:
       * no evidence            → INDETERMINATE (``missing_evidence``);
       * any contradicting item → UNSUPPORTED (the contradicted components);
       * all items support       → SUPPORTED (full coverage);
       * a mix                   → CONSTRAINED (partial coverage retained).

    The ``fail`` flag simulates an engine error mode by native-exception type; a
    model-backed evaluator would live behind the same seam. Evidence *stance* is
    read from ``context['stance:<evidence_id>']`` when present (``supports`` /
    ``contradicts`` / ``neutral``); this keeps the engine deterministic and
    offline while still exercising contradiction/partial-coverage paths.
    """

    #: policy bundle/version the engine reports (health + observability)
    policy_version = "tap-policy-1"

    def __init__(
        self,
        *,
        rules: Optional[Mapping[str, TapRule]] = None,
        default_obligations: tuple[TapObligation, ...] = (),
        fail: Optional[str] = None,
        available: bool = True,
        emit_unknown: bool = False,
    ) -> None:
        self._rules = dict(rules or {})
        self._default_obligations = default_obligations
        self._fail = fail
        self._available = available
        self._emit_unknown = emit_unknown

    @property
    def available(self) -> bool:
        return self._available and self._fail != "unavailable"

    def evaluate(self, request: TapEvaluationRequest) -> TapEvaluationResult:
        if self._fail == "timeout":
            raise TapTimeout("tap engine timed out")
        if self._fail == "unavailable":
            raise TapUnavailable("tap engine unavailable")
        if self._fail == "config":
            raise TapConfigError("tap engine misconfigured")
        if self._fail == "malformed":
            raise TapMalformedResult("tap returned a malformed result")
        if self._fail == "protocol":
            raise TapProtocolError("tap protocol/version mismatch")

        trace = request.trace_id or self._trace(request)

        if self._emit_unknown:
            # A native non-determination (never SUPPORTED downstream).
            return self._finalize(TapEvaluationResult(
                outcome=TapOutcome.UNKNOWN, evidence_coverage=None,
                reason_codes=("unresolved",), trace_id=trace))

        rule = self._rules.get(request.assertion)
        if rule is not None:
            return self._finalize(TapEvaluationResult(
                outcome=rule.outcome, evidence_coverage=rule.evidence_coverage,
                supported_components=rule.supported_components,
                unsupported_components=rule.unsupported_components,
                omitted_qualifiers=rule.omitted_qualifiers,
                covered_evidence_ids=self._covered_ids(request, rule),
                constraints=rule.constraints,
                obligations=rule.obligations or self._default_obligations,
                reason_codes=rule.reason_codes or (rule.outcome.value.lower(),),
                trace_id=trace))

        return self._finalize(self._derive_from_evidence(request, trace))

    # --- evidence-derived default ------------------------------------------

    def _has_explicit_stance(
        self, request: TapEvaluationRequest, item: TapEvidenceItem
    ) -> bool:
        key = f"stance:{item.evidence_id}"
        return bool(request.context) and key in request.context

    def _stance(self, request: TapEvaluationRequest, item: TapEvidenceItem) -> str:
        key = f"stance:{item.evidence_id}"
        val = request.context.get(key) if request.context else None
        return str(val) if val is not None else "supports"

    def _derive_from_evidence(self, request: TapEvaluationRequest, trace: str
                              ) -> TapEvaluationResult:
        evidence = request.evidence
        if not evidence:
            return TapEvaluationResult(
                outcome=TapOutcome.INDETERMINATE, evidence_coverage=0.0,
                unsupported_components=(request.assertion,) if request.assertion else (),
                reason_codes=("missing_evidence",), trace_id=trace)

        supporting = [e for e in evidence if self._stance(request, e) == "supports"]
        contradicting = [e for e in evidence if self._stance(request, e) == "contradicts"]
        coverage = round(len(supporting) / len(evidence), 4)
        covered_ids = tuple(e.evidence_id for e in supporting)
        # Support is "presumptive" when NO supporting item carried an explicit
        # stance — the reference engine is presuming support from mere presence.
        presumptive = not any(self._has_explicit_stance(request, e) for e in supporting)

        if contradicting:
            return TapEvaluationResult(
                outcome=TapOutcome.UNSUPPORTED, evidence_coverage=coverage,
                supported_components=covered_ids,
                unsupported_components=tuple(e.evidence_id for e in contradicting),
                covered_evidence_ids=covered_ids,
                reason_codes=("contradicting_evidence",), trace_id=trace)
        if coverage >= 1.0:
            reason_codes = ("evidence_supports",)
            if presumptive:
                # No explicit rule matched (we are in the derive path) and no
                # explicit stance was given ⇒ presumptive support (RA-5 audit H-1).
                reason_codes = reason_codes + (PRESUMPTIVE_SUPPORT_REASON,)
            return TapEvaluationResult(
                outcome=TapOutcome.SUPPORTED, evidence_coverage=1.0,
                supported_components=covered_ids, covered_evidence_ids=covered_ids,
                obligations=self._default_obligations,
                reason_codes=reason_codes, trace_id=trace)
        if coverage <= 0.0:
            return TapEvaluationResult(
                outcome=TapOutcome.INDETERMINATE, evidence_coverage=0.0,
                reason_codes=("insufficient_support",), trace_id=trace)
        # partial support → CONSTRAINED (only assertible with scope retained)
        return TapEvaluationResult(
            outcome=TapOutcome.CONSTRAINED, evidence_coverage=coverage,
            supported_components=covered_ids, covered_evidence_ids=covered_ids,
            unsupported_components=tuple(
                e.evidence_id for e in evidence if self._stance(request, e) == "neutral"),
            constraints=(TapConstraint("allowed_scope", "supported_components_only"),),
            reason_codes=("partial_support",), trace_id=trace)

    @staticmethod
    def _covered_ids(request: TapEvaluationRequest, rule: TapRule) -> tuple[str, ...]:
        if rule.outcome in (TapOutcome.SUPPORTED, TapOutcome.CONSTRAINED):
            return tuple(e.evidence_id for e in request.evidence)
        return ()

    # --- determinism -------------------------------------------------------

    def _finalize(self, result: TapEvaluationResult) -> TapEvaluationResult:
        if result.fingerprint:
            return result
        payload = json.dumps({
            "outcome": result.outcome.value,
            "coverage": result.evidence_coverage,
            "supported": sorted(result.supported_components),
            "unsupported": sorted(result.unsupported_components),
            "omitted": sorted(result.omitted_qualifiers),
            "constraints": sorted(f"{c.type}={c.value}" for c in result.constraints),
            "obligations": sorted(f"{o.type}={o.value}" for o in result.obligations),
            "reasons": sorted(result.reason_codes),
        }, sort_keys=True, default=str)
        fp = hashlib.sha256(payload.encode()).hexdigest()
        return TapEvaluationResult(
            outcome=result.outcome, evidence_coverage=result.evidence_coverage,
            supported_components=result.supported_components,
            unsupported_components=result.unsupported_components,
            omitted_qualifiers=result.omitted_qualifiers,
            covered_evidence_ids=result.covered_evidence_ids,
            constraints=result.constraints, obligations=result.obligations,
            reason_codes=result.reason_codes, trace_id=result.trace_id, fingerprint=fp)

    @staticmethod
    def _trace(request: TapEvaluationRequest) -> str:
        payload = json.dumps(
            {"a": request.assertion, "t": request.assertion_type,
             "e": [e.evidence_id for e in request.evidence]},
            sort_keys=True, default=str)
        return "tap-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
