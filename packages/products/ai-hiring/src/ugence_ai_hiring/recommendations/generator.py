"""Recommendation-generator port + deterministic reference generator (H2).

The generator turns a bounded evidence package into a *draft* recommendation
proposal (advisory outcome + structured draft claims). It is a **replaceable port**
so a real model implementation can be supplied by an application adapter. The core
domain must not import vendor SDKs, LLM clients, model-specific libraries, or
prompt frameworks — only this port. A real model adapter that fails, times out, or
returns malformed output surfaces as typed errors and never falls back to an
ungoverned model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..errors import GeneratorOutputInvalidError, RecommendationGenerationError
from ..synthesis.package import EvidencePackage
from .claim import ClaimType, EvidenceSufficiency
from .recommendation import RecommendationOutcome


@dataclass(frozen=True)
class DraftClaim:
    claim_type: ClaimType
    proposition: str
    competency_id: str = ""
    criterion_id: str = ""
    material: bool = True
    supporting_evidence_refs: tuple[str, ...] = ()
    contradicting_evidence_refs: tuple[str, ...] = ()
    evidence_sufficiency: EvidenceSufficiency = EvidenceSufficiency.ABSENT
    confidence: float = 0.0


@dataclass(frozen=True)
class GenerationContext:
    package: EvidencePackage
    required_capability_ids: tuple[str, ...] = ()
    required_evidence_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratorOutput:
    outcome: RecommendationOutcome
    rationale: tuple[str, ...]
    uncertainty_note: str
    confidence: float
    claims: tuple[DraftClaim, ...]
    generator_id: str


@runtime_checkable
class RecommendationGeneratorPort(Protocol):
    """Replaceable generator seam. Implementations must not leak model internals."""

    def generator_id(self) -> str: ...
    def generate(self, context: GenerationContext) -> GeneratorOutput: ...


def validate_generator_output(output: GeneratorOutput) -> GeneratorOutput:
    """Schema-validate a generator output; raise on malformed content."""
    if not isinstance(output, GeneratorOutput):
        raise GeneratorOutputInvalidError("generator did not return a GeneratorOutput")
    if not isinstance(output.outcome, RecommendationOutcome):
        raise GeneratorOutputInvalidError("invalid recommendation outcome")
    if not 0.0 <= output.confidence <= 1.0:
        raise GeneratorOutputInvalidError("confidence out of range")
    if not output.generator_id.strip():
        raise GeneratorOutputInvalidError("generator_id is required")
    for c in output.claims:
        if not isinstance(c, DraftClaim) or not c.proposition.strip():
            raise GeneratorOutputInvalidError("malformed draft claim (empty proposition)")
        if not isinstance(c.claim_type, ClaimType):
            raise GeneratorOutputInvalidError("invalid claim_type")
        if not 0.0 <= c.confidence <= 1.0:
            raise GeneratorOutputInvalidError("claim confidence out of range")
    return output


class DeterministicRecommendationGenerator:
    """Deterministic, rule-based reference generator (no model, no vendor SDK).

    Produces one material claim per required capability/evidence type from the
    bounded package: satisfied types → REQUIREMENT_SATISFIED, missing → INSUFFICIENT
    evidence, adverse → CONFLICTING_EVIDENCE. Outcome and confidence follow
    deterministically from coverage. Optional flags simulate a failing/malformed
    model implementation for failure-path tests.
    """

    def __init__(self, *, generator_id: str = "deterministic-generator",
                 timeout: bool = False, malformed: bool = False) -> None:
        self._id = generator_id
        self._timeout = timeout
        self._malformed = malformed

    def generator_id(self) -> str:
        return self._id

    def generate(self, context: GenerationContext) -> GeneratorOutput:
        if self._timeout:
            raise RecommendationGenerationError(f"generator '{self._id}' timed out")
        pkg = context.package
        covered = pkg.covered_evidence_types(include_quarantined=False)
        required = tuple(context.required_evidence_types)
        type_to_refs: dict[str, list[str]] = {}
        adverse_types: set[str] = set()
        for item in pkg.items:
            if item.evidence_ref in set(pkg.quarantined_refs):
                continue
            type_to_refs.setdefault(item.evidence_type, []).append(item.evidence_ref)
            if item.adverse:
                adverse_types.add(item.evidence_type)

        claims: list[DraftClaim] = []
        satisfied = 0
        for etype in required:
            refs = tuple(sorted(type_to_refs.get(etype, [])))
            if etype in adverse_types and refs:
                claims.append(DraftClaim(
                    claim_type=ClaimType.CONFLICTING_EVIDENCE,
                    proposition=f"Evidence for '{etype}' is conflicting.",
                    criterion_id=etype, material=True,
                    supporting_evidence_refs=tuple(r for r in refs),
                    contradicting_evidence_refs=tuple(
                        i.evidence_ref for i in pkg.items if i.evidence_type == etype and i.adverse),
                    evidence_sufficiency=EvidenceSufficiency.CONFLICTING, confidence=0.4))
            elif etype in covered:
                satisfied += 1
                claims.append(DraftClaim(
                    claim_type=ClaimType.REQUIREMENT_SATISFIED,
                    proposition=f"Requirement '{etype}' is demonstrated by collected evidence.",
                    criterion_id=etype, material=True, supporting_evidence_refs=refs,
                    evidence_sufficiency=EvidenceSufficiency.SUFFICIENT, confidence=0.9))
            else:
                claims.append(DraftClaim(
                    claim_type=ClaimType.INSUFFICIENT_EVIDENCE_FOR_CAPABILITY,
                    proposition=f"Insufficient evidence for requirement '{etype}'.",
                    criterion_id=etype, material=True,
                    evidence_sufficiency=EvidenceSufficiency.ABSENT, confidence=0.2))

        if self._malformed:
            # Simulate a model returning a structurally-invalid claim.
            claims.append(DraftClaim(claim_type=ClaimType.REQUIREMENT_SATISFIED,
                                     proposition="   ", material=True))

        total = max(len(required), 1)
        confidence = round(satisfied / total, 4)
        if pkg.missing_evidence_types or any(
                c.claim_type == ClaimType.INSUFFICIENT_EVIDENCE_FOR_CAPABILITY for c in claims):
            outcome = RecommendationOutcome.INSUFFICIENT_EVIDENCE
        elif adverse_types:
            outcome = RecommendationOutcome.RECOMMEND_HOLD
        elif satisfied == total:
            outcome = RecommendationOutcome.RECOMMEND_ADVANCE
        else:
            outcome = RecommendationOutcome.NO_RECOMMENDATION

        rationale = tuple(
            f"{c.claim_type.value}: {c.criterion_id or c.competency_id}".strip() for c in claims)
        uncertainty = "" if confidence >= 0.8 else "coverage below high-confidence threshold"
        return GeneratorOutput(outcome=outcome, rationale=rationale, uncertainty_note=uncertainty,
                               confidence=confidence, claims=tuple(claims), generator_id=self._id)
