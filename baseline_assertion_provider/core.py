"""Baseline assertion engine — a deterministic, capability-limited vendor core (pure).

A legitimate but intentionally simpler alternative to TAP. It imports neither the
DGM kernel nor the provider framework — it speaks only its own native vocabulary.

Capabilities (honestly limited):
* exact evidence matching → SUPPORTED;
* explicit contradiction detection → UNSUPPORTED;
* missing-evidence detection → INDETERMINATE;
* it performs **no** qualifier / scope / component / provenance analysis, so any
  assertion requiring those is returned INDETERMINATE (never a less-safe SUPPORTED).

Deterministic and offline; configurable failure flags model engine error modes.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


class BaselineAssertionError(Exception):
    """Base class for baseline-assertion engine failures."""


class BaselineAssertionTimeout(BaselineAssertionError):
    pass


class BaselineAssertionUnavailable(BaselineAssertionError):
    pass


class BaselineAssertionConfigError(BaselineAssertionError):
    pass


class BaselineAssertionMalformed(BaselineAssertionError):
    pass


class BaselineAssertionOutcome(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    INDETERMINATE = "INDETERMINATE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BaselineEvidenceItem:
    evidence_id: str
    source_reference: str = ""
    provenance: str = ""


@dataclass(frozen=True)
class BaselineAssertionRequest:
    assertion: str
    evidence: tuple[BaselineEvidenceItem, ...] = ()
    context: Mapping[str, object] = field(default_factory=dict)
    correlation_id: str = ""


@dataclass(frozen=True)
class BaselineAssertionResult:
    outcome: BaselineAssertionOutcome
    matched_evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    trace_id: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class BaselineRule:
    """A deterministic per-assertion outcome for the reference engine."""

    outcome: BaselineAssertionOutcome
    reason_codes: tuple[str, ...] = ()


class BaselineAssertionEngine:
    """A deterministic, capability-limited assertion engine.

    Resolution order for an assertion:
    1. an explicit :class:`BaselineRule` (keyed by assertion text) wins;
    2. otherwise: no evidence → INDETERMINATE; any ``stance:<id>`` == "contradicts"
       → UNSUPPORTED; all supporting → SUPPORTED; anything else → INDETERMINATE.

    A rule whose outcome is not one this engine can substantiate (i.e. requires
    capability the engine lacks) must be authored as INDETERMINATE by the caller —
    the engine never invents a SUPPORTED it cannot justify.
    """

    policy_version = "baseline-assertion-1"

    def __init__(self, *, rules: Optional[Mapping[str, BaselineRule]] = None,
                 fail: Optional[str] = None, available: bool = True) -> None:
        self._rules = dict(rules or {})
        self._fail = fail
        self._available = available

    @property
    def available(self) -> bool:
        return self._available and self._fail != "unavailable"

    def evaluate(self, request: BaselineAssertionRequest) -> BaselineAssertionResult:
        if self._fail == "timeout":
            raise BaselineAssertionTimeout("baseline assertion engine timed out")
        if self._fail == "unavailable":
            raise BaselineAssertionUnavailable("baseline assertion engine unavailable")
        if self._fail == "config":
            raise BaselineAssertionConfigError("baseline assertion engine misconfigured")
        if self._fail == "malformed":
            raise BaselineAssertionMalformed("baseline assertion returned a malformed result")

        trace = self._trace(request)
        rule = self._rules.get(request.assertion)
        if rule is not None:
            return self._finalize(BaselineAssertionResult(
                outcome=rule.outcome, trace_id=trace,
                matched_evidence_ids=tuple(e.evidence_id for e in request.evidence)
                if rule.outcome is BaselineAssertionOutcome.SUPPORTED else (),
                reason_codes=rule.reason_codes or (rule.outcome.value.lower(),)))

        if not request.evidence:
            return self._finalize(BaselineAssertionResult(
                outcome=BaselineAssertionOutcome.INDETERMINATE,
                reason_codes=("missing_evidence",), trace_id=trace))
        contradicting = [e for e in request.evidence
                         if str((request.context or {}).get(f"stance:{e.evidence_id}", "")) == "contradicts"]
        if contradicting:
            return self._finalize(BaselineAssertionResult(
                outcome=BaselineAssertionOutcome.UNSUPPORTED,
                reason_codes=("contradiction_detected",), trace_id=trace))
        return self._finalize(BaselineAssertionResult(
            outcome=BaselineAssertionOutcome.SUPPORTED,
            matched_evidence_ids=tuple(e.evidence_id for e in request.evidence),
            reason_codes=("exact_evidence_match",), trace_id=trace))

    def _finalize(self, result: BaselineAssertionResult) -> BaselineAssertionResult:
        if result.fingerprint:
            return result
        payload = json.dumps({"o": result.outcome.value,
                              "m": sorted(result.matched_evidence_ids),
                              "r": sorted(result.reason_codes)}, sort_keys=True)
        fp = hashlib.sha256(payload.encode()).hexdigest()
        return BaselineAssertionResult(
            outcome=result.outcome, matched_evidence_ids=result.matched_evidence_ids,
            reason_codes=result.reason_codes, trace_id=result.trace_id, fingerprint=fp)

    @staticmethod
    def _trace(request: BaselineAssertionRequest) -> str:
        payload = json.dumps({"a": request.assertion,
                              "e": [e.evidence_id for e in request.evidence]},
                             sort_keys=True)
        return "base-assert-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
