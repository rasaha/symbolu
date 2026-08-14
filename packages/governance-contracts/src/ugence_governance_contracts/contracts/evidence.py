"""Neutral UVI evidence contracts (GV-2E-a).

The provider-neutral evidence vocabulary that future Ugence Value Intelligence
engines (Agent Value Readiness, Value Forecasting, Governed Value Verification)
share. This module defines **contracts and structural invariants only**. It is
NOT an evidence authority, attribution engine, verification engine, policy
authority, readiness evaluator, or financial calculator. It grants no action
permission and mints no authority.

Evidence quality is modelled as **orthogonal axes**, never one linear
maturity score:

* :class:`SourceBasis` — where the ground inputs come from.
* :class:`TransformationMethod` — how the value was produced from them.
* :class:`AttestationStatus` — whether an authority signed the provenance.
* :class:`AttributionStatus` — whether a causal link to the subject is
  established.
* :class:`VerificationStatus` — whether a specifically declared claim was
  checked.

Trust boundary (structural, not cryptographic): a caller can *submit* a claim,
but **selecting an enum value never creates authority or proves evidence**.
Stronger statuses (ATTESTED / ATTRIBUTED / VERIFIED) are only *structurally
constructible* when the caller supplies the corresponding authority-produced
assessment references (an attestation reference + attester identity, an
attribution assessment + counterfactual + causal method, a verification
assessment + exact claim reference + verifier identity + time). Actual
signature / authority verification belongs to later admission and authority
milestones — a dataclass constructor performs **no** cryptographic or
organizational verification.

Subject binding uses the existing repository convention (plain ``tenant_id`` /
``subject_id`` strings). The RA-owned canonical neutral subject-context contract
is a **deferred dependency**; ``AssessedSystemBinding`` / ``SubjectContext`` are
intentionally **out of scope** for GV-2E-a and are not defined here (no competing
subject-context contract is minted).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

__all__ = [
    "SourceBasis",
    "TransformationMethod",
    "AttestationStatus",
    "AttributionStatus",
    "VerificationStatus",
    "EvidenceUsageScope",
    "EvidenceContractError",
    "EvidenceReference",
    "EvidenceProvenance",
    "BenchmarkReference",
    "AssessmentWindow",
    "ForecastHorizon",
    "PopulationSlice",
    "ConfidenceBasis",
    "MetricClaim",
    "MetricObservation",
]


# --------------------------------------------------------------------------- #
# Orthogonal evidence axes
# --------------------------------------------------------------------------- #
class SourceBasis(str, Enum):
    """Where the ground inputs of a value come from. Orthogonal to the rest."""

    REPORTED = "REPORTED"
    OBSERVED = "OBSERVED"
    SYNTHETIC = "SYNTHETIC"
    MIXED = "MIXED"


class TransformationMethod(str, Enum):
    """How the value was produced from its inputs. Orthogonal to source basis."""

    DIRECT = "DIRECT"
    CALCULATED = "CALCULATED"
    MODELED = "MODELED"


class AttestationStatus(str, Enum):
    """Whether an authority signed/confirmed the provenance. Never implies

    OBSERVED, ATTRIBUTED, or VERIFIED.
    """

    UNATTESTED = "UNATTESTED"
    ATTESTED = "ATTESTED"


class AttributionStatus(str, Enum):
    """Whether a causal link to the subject is established. Independent of

    verification.
    """

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_ATTRIBUTED = "NOT_ATTRIBUTED"
    PARTIALLY_ATTRIBUTED = "PARTIALLY_ATTRIBUTED"
    ATTRIBUTED = "ATTRIBUTED"


class VerificationStatus(str, Enum):
    """Whether a specifically declared claim was checked. Never implies

    attribution.
    """

    UNVERIFIED = "UNVERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFIED = "VERIFIED"


class EvidenceUsageScope(str, Enum):
    """Permitted use of a claim. Synthetic evidence must be EVALUATION_ONLY."""

    GENERAL = "GENERAL"
    EVALUATION_ONLY = "EVALUATION_ONLY"


class EvidenceContractError(ValueError):
    """A structural evidence-contract invariant was violated at construction.

    Subclasses ``ValueError`` so existing ``ValueError`` handling still catches
    it. It signals a *structural* rejection — never a claim that authority
    verification was performed.
    """


# --------------------------------------------------------------------------- #
# Small validation helpers (stdlib-only; no Risk Authority dependency)
# --------------------------------------------------------------------------- #
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceContractError(f"{name} must be a non-empty string")


def _validate_digest(value: str, name: str, *, required: bool) -> None:
    if not value:
        if required:
            raise EvidenceContractError(f"{name} is required (sha-256 hex digest)")
        return
    if not _SHA256_RE.match(value):
        raise EvidenceContractError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )


def _require_tzaware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise EvidenceContractError(f"{name} must be a datetime")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise EvidenceContractError(f"{name} must be timezone-aware")


def _normalize_refs(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    """Reject blank and duplicate references; preserve caller order."""

    seen: set[str] = set()
    for v in values:
        if not isinstance(v, str) or not v.strip():
            raise EvidenceContractError(f"{name} contains a blank reference")
        if v in seen:
            raise EvidenceContractError(f"{name} contains duplicate reference {v!r}")
        seen.add(v)
    return tuple(values)


def _canonical_digest(obj) -> str:
    """Deterministic sha-256 over a canonical JSON serialization.

    Mirrors the package's established fingerprint pattern (sorted-key, tight
    separators, ``default=str``) — identical inputs yield an identical digest.
    """

    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Time bounds — distinct types so a window and a horizon can never be
# silently interchanged.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AssessmentWindow:
    """A retrospective/observation interval. Both bounds timezone-aware."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        _require_tzaware(self.start, "AssessmentWindow.start")
        _require_tzaware(self.end, "AssessmentWindow.end")
        if not self.start < self.end:
            raise EvidenceContractError("AssessmentWindow.start must be before end")


@dataclass(frozen=True)
class ForecastHorizon:
    """A prospective horizon. Distinct from :class:`AssessmentWindow`."""

    as_of: datetime
    horizon_end: datetime

    def __post_init__(self) -> None:
        _require_tzaware(self.as_of, "ForecastHorizon.as_of")
        _require_tzaware(self.horizon_end, "ForecastHorizon.horizon_end")
        if not self.as_of < self.horizon_end:
            raise EvidenceContractError("ForecastHorizon.as_of must be before horizon_end")


# --------------------------------------------------------------------------- #
# Neutral references
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PopulationSlice:
    """The population a claim pertains to."""

    population_id: str
    geography: str = ""
    language: str = ""
    cohort: str = ""
    size: Optional[int] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.population_id, "PopulationSlice.population_id")
        if self.size is not None:
            if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size < 0:
                raise EvidenceContractError("PopulationSlice.size must be a non-negative int")


@dataclass(frozen=True)
class ConfidenceBasis:
    """How confidence was established. Qualitative or interval — never money."""

    method: str
    interval_or_class: str = ""
    sample_size: Optional[int] = None
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.method, "ConfidenceBasis.method")
        if self.sample_size is not None:
            if (
                not isinstance(self.sample_size, int)
                or isinstance(self.sample_size, bool)
                or self.sample_size < 0
            ):
                raise EvidenceContractError(
                    "ConfidenceBasis.sample_size must be a non-negative int"
                )
        object.__setattr__(self, "caveats", _normalize_refs(self.caveats, "ConfidenceBasis.caveats"))


@dataclass(frozen=True)
class EvidenceProvenance:
    """Where a piece of evidence came from and how it was collected/produced."""

    source_identity: str
    source_type: str
    collection_method: str = ""
    produced_at: Optional[datetime] = None
    integrity_digest: str = ""
    issuer_ref: str = ""
    window: Optional[AssessmentWindow] = None
    population_ref: str = ""
    freshness: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.source_identity, "EvidenceProvenance.source_identity")
        _require_nonempty(self.source_type, "EvidenceProvenance.source_type")
        _validate_digest(self.integrity_digest, "EvidenceProvenance.integrity_digest", required=False)
        if self.produced_at is not None:
            _require_tzaware(self.produced_at, "EvidenceProvenance.produced_at")


@dataclass(frozen=True)
class EvidenceReference:
    """An immutable, digest-bound reference to a piece of evidence.

    Binds tenant/subject identity, kind, and a content digest so downstream
    consumers can dereference without embedding the (mutable) evidence body.
    """

    evidence_id: str
    tenant_id: str
    subject_id: str
    evidence_kind: str
    content_digest: str
    provenance_ref: str = ""
    created_at: Optional[datetime] = None
    supersedes_ref: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.evidence_id, "EvidenceReference.evidence_id")
        _require_nonempty(self.tenant_id, "EvidenceReference.tenant_id")
        _require_nonempty(self.subject_id, "EvidenceReference.subject_id")
        _require_nonempty(self.evidence_kind, "EvidenceReference.evidence_kind")
        _validate_digest(self.content_digest, "EvidenceReference.content_digest", required=True)
        if self.created_at is not None:
            _require_tzaware(self.created_at, "EvidenceReference.created_at")


@dataclass(frozen=True)
class BenchmarkReference:
    """An immutable, versioned reference to a separately-governed benchmark."""

    benchmark_id: str
    version: str
    content_digest: str
    issuer_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.benchmark_id, "BenchmarkReference.benchmark_id")
        _require_nonempty(self.version, "BenchmarkReference.version")
        _validate_digest(self.content_digest, "BenchmarkReference.content_digest", required=True)
        if self.effective_from is not None:
            _require_tzaware(self.effective_from, "BenchmarkReference.effective_from")
        if self.effective_to is not None:
            _require_tzaware(self.effective_to, "BenchmarkReference.effective_to")
        if self.effective_from is not None and self.effective_to is not None:
            if not self.effective_from < self.effective_to:
                raise EvidenceContractError(
                    "BenchmarkReference.effective_from must be before effective_to"
                )


# --------------------------------------------------------------------------- #
# MetricClaim — the neutral value contract (reported/observed/calculated/modeled)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MetricClaim:
    """A neutral, immutable claim about a metric value for a subject.

    ``value`` is a portable scalar carried as a string (deterministic
    serialization; no arbitrary-object field). The evidence axes are orthogonal;
    structural validation enforces that stronger axis values are only
    constructible with the corresponding authority-produced references — it does
    NOT perform authority verification.
    """

    claim_id: str
    tenant_id: str
    subject_id: str
    metric_id: str
    value: str
    governed_unit: str
    source_basis: SourceBasis
    transformation_method: TransformationMethod
    usage_scope: EvidenceUsageScope = EvidenceUsageScope.GENERAL
    evidence_refs: tuple[str, ...] = ()
    input_evidence_refs: tuple[str, ...] = ()
    assessment_window: Optional[AssessmentWindow] = None
    forecast_horizon: Optional[ForecastHorizon] = None
    population_ref: str = ""
    confidence_ref: str = ""
    attestation_status: AttestationStatus = AttestationStatus.UNATTESTED
    attestation_ref: str = ""
    attester_identity: str = ""
    attribution_status: AttributionStatus = AttributionStatus.NOT_APPLICABLE
    attribution_ref: str = ""
    counterfactual_ref: str = ""
    causal_method_ref: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_ref: str = ""
    verifier_identity: str = ""
    verified_at: Optional[datetime] = None
    verified_claim_ref: str = ""
    calculation_ref: str = ""
    model_ref: str = ""
    policy_refs: tuple[str, ...] = ()
    benchmark_refs: tuple[str, ...] = ()
    content_digest: str = ""

    def __post_init__(self) -> None:
        # -- identity + portable scalar -------------------------------------
        _require_nonempty(self.claim_id, "MetricClaim.claim_id")
        _require_nonempty(self.tenant_id, "MetricClaim.tenant_id")
        _require_nonempty(self.subject_id, "MetricClaim.subject_id")
        _require_nonempty(self.metric_id, "MetricClaim.metric_id")
        _require_nonempty(self.value, "MetricClaim.value")
        _require_nonempty(self.governed_unit, "MetricClaim.governed_unit")
        if not isinstance(self.source_basis, SourceBasis):
            raise EvidenceContractError("MetricClaim.source_basis must be a SourceBasis")
        if not isinstance(self.transformation_method, TransformationMethod):
            raise EvidenceContractError(
                "MetricClaim.transformation_method must be a TransformationMethod"
            )

        # -- references: reject blanks + duplicates -------------------------
        object.__setattr__(self, "evidence_refs", _normalize_refs(self.evidence_refs, "MetricClaim.evidence_refs"))
        object.__setattr__(self, "input_evidence_refs", _normalize_refs(self.input_evidence_refs, "MetricClaim.input_evidence_refs"))
        object.__setattr__(self, "policy_refs", _normalize_refs(self.policy_refs, "MetricClaim.policy_refs"))
        object.__setattr__(self, "benchmark_refs", _normalize_refs(self.benchmark_refs, "MetricClaim.benchmark_refs"))
        _validate_digest(self.content_digest, "MetricClaim.content_digest", required=False)

        # -- time: window XOR horizon; verified_at tz-aware -----------------
        if self.assessment_window is not None and self.forecast_horizon is not None:
            raise EvidenceContractError(
                "MetricClaim cannot carry both an AssessmentWindow and a ForecastHorizon"
            )
        if self.verified_at is not None:
            _require_tzaware(self.verified_at, "MetricClaim.verified_at")

        # -- transformation-method structural rules -------------------------
        if self.transformation_method is TransformationMethod.DIRECT:
            if self.calculation_ref or self.model_ref:
                raise EvidenceContractError(
                    "DIRECT claim must not declare a calculation_ref or model_ref"
                )
        elif self.transformation_method is TransformationMethod.CALCULATED:
            if not self.input_evidence_refs:
                raise EvidenceContractError("CALCULATED claim requires input_evidence_refs")
            _require_nonempty(self.calculation_ref, "CALCULATED claim calculation_ref")
        elif self.transformation_method is TransformationMethod.MODELED:
            if not self.input_evidence_refs:
                raise EvidenceContractError("MODELED claim requires input_evidence_refs")
            _require_nonempty(self.model_ref, "MODELED claim model_ref")
            if (self.assessment_window is None) == (self.forecast_horizon is None):
                raise EvidenceContractError(
                    "MODELED claim requires exactly one of AssessmentWindow "
                    "(retrospective) or ForecastHorizon (prospective)"
                )

        # -- source-basis structural rules ----------------------------------
        if self.source_basis is SourceBasis.OBSERVED:
            if self.forecast_horizon is not None:
                raise EvidenceContractError("OBSERVED claim must not carry a ForecastHorizon")
            if self.assessment_window is None:
                raise EvidenceContractError("OBSERVED claim requires an AssessmentWindow")
        elif self.source_basis is SourceBasis.MIXED:
            if len(self.input_evidence_refs) < 2:
                raise EvidenceContractError(
                    "MIXED claim requires at least two input evidence references "
                    "(or an explicit input-lineage manifest)"
                )
        elif self.source_basis is SourceBasis.SYNTHETIC:
            if self.usage_scope is not EvidenceUsageScope.EVALUATION_ONLY:
                raise EvidenceContractError(
                    "SYNTHETIC claim requires usage_scope=EVALUATION_ONLY"
                )
            if not self.evidence_refs:
                raise EvidenceContractError(
                    "SYNTHETIC claim requires evidence_refs to the generator/dataset"
                )
            _validate_digest(self.content_digest, "SYNTHETIC claim content_digest", required=True)
            if self.attribution_status in (
                AttributionStatus.ATTRIBUTED,
                AttributionStatus.PARTIALLY_ATTRIBUTED,
            ):
                raise EvidenceContractError(
                    "SYNTHETIC evidence cannot independently support an attributed result"
                )
            if self.verification_status is VerificationStatus.VERIFIED:
                raise EvidenceContractError(
                    "SYNTHETIC evidence cannot independently support a verified realized result"
                )

        # -- attestation / attribution / verification structural rules ------
        if self.attestation_status is AttestationStatus.ATTESTED:
            _require_nonempty(self.attestation_ref, "ATTESTED claim attestation_ref")
            _require_nonempty(self.attester_identity, "ATTESTED claim attester_identity")

        if self.attribution_status in (
            AttributionStatus.ATTRIBUTED,
            AttributionStatus.PARTIALLY_ATTRIBUTED,
        ):
            # ADR §12: attribution requires OBSERVED or MIXED grounding; a
            # REPORTED-only or SYNTHETIC claim can only be NOT_APPLICABLE or
            # NOT_ATTRIBUTED. (MODELED transform is permitted — causal
            # attribution is routinely model-based — provided the *source basis*
            # is observed/mixed and a method is declared.)
            if self.source_basis not in (SourceBasis.OBSERVED, SourceBasis.MIXED):
                raise EvidenceContractError(
                    "attributed claim requires SourceBasis OBSERVED or MIXED grounding; "
                    f"{self.source_basis.value} claims cannot be attributed"
                )
            _require_nonempty(self.attribution_ref, "attributed claim attribution_ref")
            _require_nonempty(self.counterfactual_ref, "attributed claim counterfactual_ref")
            _require_nonempty(self.causal_method_ref, "attributed claim causal_method_ref")

        if self.verification_status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.VERIFICATION_FAILED,
        ):
            _require_nonempty(self.verified_claim_ref, "verified claim verified_claim_ref")
            _require_nonempty(self.verification_ref, "verified claim verification_ref")
            _require_nonempty(self.verifier_identity, "verified claim verifier_identity")
            if self.verified_at is None:
                raise EvidenceContractError("verified claim requires verified_at")

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the claim's canonical serialization."""

        return _canonical_digest(self)

    @staticmethod
    def from_evidence(
        *,
        evidence: tuple["EvidenceReference", ...] = (),
        inputs: tuple["EvidenceReference", ...] = (),
        **kwargs,
    ) -> "MetricClaim":
        """Build a claim from :class:`EvidenceReference` objects, enforcing that

        every referenced evidence shares the claim's tenant and subject. This is
        the structural guard against cross-tenant / cross-subject input mixing;
        the referenced evidence IDs are stored as the ``evidence_refs`` /
        ``input_evidence_refs`` tuples (bodies are never embedded).
        """

        tenant_id = kwargs.get("tenant_id", "")
        subject_id = kwargs.get("subject_id", "")
        for ref in tuple(evidence) + tuple(inputs):
            if not isinstance(ref, EvidenceReference):
                raise EvidenceContractError("from_evidence expects EvidenceReference objects")
            if ref.tenant_id != tenant_id:
                raise EvidenceContractError(
                    f"cross-tenant evidence mixing: {ref.evidence_id} tenant "
                    f"{ref.tenant_id!r} != claim tenant {tenant_id!r}"
                )
            if ref.subject_id != subject_id:
                raise EvidenceContractError(
                    f"cross-subject evidence mixing: {ref.evidence_id} subject "
                    f"{ref.subject_id!r} != claim subject {subject_id!r}"
                )
        kwargs.setdefault("evidence_refs", tuple(r.evidence_id for r in evidence))
        kwargs.setdefault("input_evidence_refs", tuple(r.evidence_id for r in inputs))
        return MetricClaim(**kwargs)


# --------------------------------------------------------------------------- #
# MetricObservation — a constrained OBSERVED form of MetricClaim
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MetricObservation:
    """A genuinely observed measurement.

    Source basis is fixed to ``OBSERVED`` internally (never caller-selected); an
    :class:`AssessmentWindow` is required and a :class:`ForecastHorizon` is
    structurally impossible. Constructing one does **not** make it ATTESTED,
    ATTRIBUTED, or VERIFIED — :meth:`to_metric_claim` yields the weakest cell on
    every quality axis.
    """

    observation_id: str
    tenant_id: str
    subject_id: str
    metric_id: str
    value: str
    governed_unit: str
    assessment_window: Optional[AssessmentWindow] = None
    evidence_refs: tuple[str, ...] = ()
    transformation_method: TransformationMethod = TransformationMethod.DIRECT
    input_evidence_refs: tuple[str, ...] = ()
    calculation_ref: str = ""
    population_ref: str = ""
    confidence_ref: str = ""
    content_digest: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.observation_id, "MetricObservation.observation_id")
        if self.assessment_window is None:
            raise EvidenceContractError("MetricObservation requires an AssessmentWindow")
        object.__setattr__(self, "evidence_refs", _normalize_refs(self.evidence_refs, "MetricObservation.evidence_refs"))
        if not self.evidence_refs:
            raise EvidenceContractError("MetricObservation requires observation/evidence references")
        if self.transformation_method is TransformationMethod.MODELED:
            raise EvidenceContractError(
                "MetricObservation cannot be MODELED (it is an observed measurement)"
            )
        # Delegate the remaining structural rules to MetricClaim (fixes OBSERVED);
        # constructing the projection validates it and is then discarded.
        self.to_metric_claim()

    def to_metric_claim(self) -> "MetricClaim":
        """Project to the neutral MetricClaim, fixing source basis to OBSERVED."""

        return MetricClaim(
            claim_id=self.observation_id,
            tenant_id=self.tenant_id,
            subject_id=self.subject_id,
            metric_id=self.metric_id,
            value=self.value,
            governed_unit=self.governed_unit,
            source_basis=SourceBasis.OBSERVED,
            transformation_method=self.transformation_method,
            evidence_refs=self.evidence_refs,
            input_evidence_refs=self.input_evidence_refs,
            assessment_window=self.assessment_window,
            calculation_ref=self.calculation_ref,
            population_ref=self.population_ref,
            confidence_ref=self.confidence_ref,
            content_digest=self.content_digest,
        )

    def canonical_digest(self) -> str:
        return self.to_metric_claim().canonical_digest()
