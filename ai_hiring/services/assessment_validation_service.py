"""Assessment validation service — deterministic observation validation.

Validates that a supplied observation *conforms to the published contract*
(criterion, capability version, scale membership, evidence references, required
uncertainty, permitted reason codes, authorized supplier). It never chooses or
computes an observation value. Pure and deterministic — no repositories, no
inference.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..assessments.evidence_binding import EvidenceBinding
from ..assessments.status import PERMITTED_SUPPLIERS, SupplierType
from ..assessments.validation import (
    ValidationIssue,
    ValidationResult,
    validate_value_against_scale,
)
from ..assessments.workspace import AssessmentWorkspace, CapabilityBinding
from ..ontology.taxonomy import ReasonCode, is_known_reason_code
from ..rubrics.rubric import Rubric
from ..rubrics.scoring_scale import STANDARD_SCALES, ScaleType, ScoringScale
from ..rubrics.uncertainty import UncertaintyLevel


def resolve_scale(rubric: Rubric, scale_id: str) -> Optional[ScoringScale]:
    if scale_id in STANDARD_SCALES:
        return STANDARD_SCALES[scale_id]
    for s in rubric.custom_scales:
        if s.scale_id == scale_id:
            return s
    return None


class AssessmentValidationService:
    def validate_observation(
        self,
        workspace: AssessmentWorkspace,
        rubric: Rubric,
        criterion: CapabilityBinding,
        *,
        value: str,
        scale_type: ScaleType,
        supplier_type: SupplierType,
        uncertainty: Optional[UncertaintyLevel],
        reason_codes: tuple[ReasonCode, ...],
        evidence_binding_ids: tuple[str, ...],
        bindings_by_id: Mapping[str, EvidenceBinding],
    ) -> ValidationResult:
        errors: list[ValidationIssue] = []

        def err(code: str, msg: str, blocking: bool = True) -> None:
            errors.append(ValidationIssue(
                code=code, message=msg, criterion_id=criterion.criterion_id,
                capability_id=criterion.capability_id, blocking=blocking))

        # 1. supplier authorization (AI is never allowed to supply in Phase 3B)
        if supplier_type is SupplierType.AI_MODEL:
            err("AI_OBSERVATION_NOT_ALLOWED",
                "AI-supplied observations are prohibited in Phase 3B")
        elif supplier_type not in PERMITTED_SUPPLIERS:
            err("OBSERVATION_SUPPLIER_NOT_AUTHORIZED",
                f"supplier '{supplier_type.value}' is not permitted")

        # 2. scale resolution + declared-scale match
        scale = resolve_scale(rubric, criterion.scoring_scale_id)
        if scale is None:
            err("OBSERVATION_SCALE_UNKNOWN",
                f"scale '{criterion.scoring_scale_id}' not resolvable")
        else:
            if scale_type is not scale.scale_type:
                err("OBSERVATION_SCALE_MISMATCH",
                    f"declared scale {scale_type.value} != rubric {scale.scale_type.value}")
            else:
                # 3. value membership (deterministic, never computed)
                code = validate_value_against_scale(value, scale)
                if code is not None:
                    err(code, f"value '{value}' not valid for {scale.scale_type.value}")

        # 4. evidence references: must exist, belong to workspace + criterion
        rule = criterion.evidence_rule
        admissible_refs = 0
        for bid in evidence_binding_ids:
            binding = bindings_by_id.get(bid)
            if binding is None:
                err("INVALID_EVIDENCE_BINDING_REFERENCE",
                    f"binding '{bid}' not found in this workspace")
                continue
            if (binding.workspace_id != workspace.workspace_id
                    or binding.criterion_id != criterion.criterion_id):
                err("EVIDENCE_BINDING_WRONG_CRITERION",
                    f"binding '{bid}' does not belong to this criterion")
                continue
            admissible_refs += 1
        if rule.minimum_count > 0 and admissible_refs < rule.minimum_count:
            err("MISSING_REQUIRED_EVIDENCE",
                f"criterion requires {rule.minimum_count} admissible evidence item(s), "
                f"got {admissible_refs} (explanation references do not substitute)")

        # 5. uncertainty
        urule = workspace.uncertainty_rule_for(criterion.criterion_id)
        if urule is not None and urule.requires_uncertainty and uncertainty is None:
            err("REQUIRED_UNCERTAINTY_MISSING", "criterion requires an uncertainty level")
        if uncertainty is not None and urule is not None \
                and uncertainty not in urule.allowed_levels:
            err("UNCERTAINTY_LEVEL_NOT_ALLOWED",
                f"uncertainty '{uncertainty.value}' not in allowed levels")

        # 6. reason codes: known + permitted for this criterion/rubric
        permitted = set(criterion.allowed_reason_codes) or set(rubric.allowed_reason_codes)
        for rc in reason_codes:
            if not is_known_reason_code(rc.value):
                err("REASON_CODE_UNKNOWN", f"reason code '{rc}' is not in the catalog")
            elif permitted and rc not in permitted:
                err("REASON_CODE_NOT_PERMITTED",
                    f"reason code '{rc.value}' not permitted for this criterion")

        versions = (f"rubric:{rubric.rubric_id}:{rubric.version}",
                    f"capability:{criterion.capability_id}:{criterion.capability_version}")
        return ValidationResult(
            valid=not errors, errors=tuple(errors),
            blocking_conditions=tuple(i.code for i in errors if i.blocking),
            referenced_contract_versions=versions)
