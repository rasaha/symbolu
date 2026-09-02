"""§5 Quality evaluator declaration: declared, not proven."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode

from .._canon import digest_of, require_digest, require_member, require_nonblank, settle_digest
from ..errors import PilotError, PilotErrorCode

INDEPENDENCE_DECLARED_UNVERIFIED = "DECLARED_UNVERIFIED"


class EvaluatorKind(str, Enum):
    HUMAN = "HUMAN"
    LLM = "LLM"
    PROGRAMMATIC = "PROGRAMMATIC"


@dataclass(frozen=True)
class QualityEvaluatorDeclaration:
    evaluator_identity: str
    evaluator_version: str
    kind: EvaluatorKind
    model_ref: Optional[str]
    separation_declaration_ref: str
    scoring_instruction_digest: str
    benchmark_manifest_digest: str
    calibration_evidence_ref: str
    independence_status: str = INDEPENDENCE_DECLARED_UNVERIFIED
    declaration_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.evaluator_identity, "QualityEvaluatorDeclaration.evaluator_identity")
        require_nonblank(self.evaluator_version, "QualityEvaluatorDeclaration.evaluator_version")
        require_member(self.kind, EvaluatorKind, "QualityEvaluatorDeclaration.kind", ContractErrorCode.REF_BLANK_FIELD)
        if self.kind is EvaluatorKind.LLM:
            if not isinstance(self.model_ref, str) or not self.model_ref.strip():
                raise PilotError(PilotErrorCode.EVALUATOR_KIND_INCONSISTENT, "an LLM evaluator requires model_ref")
        elif self.model_ref is not None:
            raise PilotError(PilotErrorCode.EVALUATOR_KIND_INCONSISTENT, f"a {self.kind.value} evaluator carries no model_ref")
        require_nonblank(self.separation_declaration_ref, "QualityEvaluatorDeclaration.separation_declaration_ref")
        require_digest(self.scoring_instruction_digest, "QualityEvaluatorDeclaration.scoring_instruction_digest")
        require_digest(self.benchmark_manifest_digest, "QualityEvaluatorDeclaration.benchmark_manifest_digest")
        if not isinstance(self.calibration_evidence_ref, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "calibration_evidence_ref must be a string (may be blank)")
        if self.independence_status != INDEPENDENCE_DECLARED_UNVERIFIED:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"independence_status is fixed at {INDEPENDENCE_DECLARED_UNVERIFIED} in 4A")
        settle_digest(self, "declaration_digest", digest_of(self, exclude=("declaration_digest",)))

    @property
    def calibration_is_blank(self) -> bool:
        return not self.calibration_evidence_ref.strip()


__all__ = ["INDEPENDENCE_DECLARED_UNVERIFIED", "EvaluatorKind", "QualityEvaluatorDeclaration"]
