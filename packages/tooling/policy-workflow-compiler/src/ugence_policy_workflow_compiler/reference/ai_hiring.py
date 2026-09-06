"""The AI Hiring reference policy pack (decision D3, second equivalence domain).

Procurement's governance shape is threshold authorization: an amount is compared to
bounds and an authority decides. AI Hiring's shape is different, which is exactly why
ruling D3 chose it — agreement across two differently shaped domains is evidence of
generality, where agreement within one is repetition.

What this pack models, taken from the live product's own rules:

* **Eligibility is non-compensatory.** It derives from mandatory gates alone, in a
  fixed order — any FAIL blocks, then any INDETERMINATE blocks fail-closed, else
  eligible. Scores never enter it.
* **Compatibility is not eligibility.** A dimension score may inform an advisory
  disposition; it may never decide eligibility.
* **The recommendation is advisory.** The product types it ``actor_type="AI"`` and
  ``binding=False``; only a human authority makes a binding employment decision.
* **Advisory dispositions are transparent.** Every scored dimension at or above the
  stated score floor plus confidence at or above the confidence floor advances;
  insufficient evidence holds; anything else declines.

Nothing here is invented: each bound and ordering traces to the live product.
"""

from __future__ import annotations

from ..api import (
    ActionConstraint,
    ApprovalPath,
    ApprovalStep,
    AuthorityRequirement,
    AuthorityType,
    BlockBehavior,
    CapabilityId,
    Comparator,
    ConstraintKind,
    DecisionRule,
    EvidenceKind,
    PolicyPack,
    PolicyPackStatus,
    Predicate,
    ProhibitedCondition,
    ProvenanceSourceType,
    RequiredEvidence,
    SourceDocument,
)

SOURCE_ID = "src.ai_hiring_reference"
_PROV = (SOURCE_ID,)

#: Advisory-disposition floors, taken from the live product's recommendation module,
#: which states them as floats (``60.0`` and ``0.6``).
#:
#: The compiler refuses a float in policy logic — a float comparison is not
#: reproducibly deterministic across platforms, and the pack must be. The reference
#: therefore states the same floors in integer units: the score floor unchanged on
#: the product's 0-100 scale, and the confidence floor as whole percent. The
#: equivalence harness translates, and a dimension checks that the translation is
#: exact rather than approximate.
PRODUCT_MIN_SCORE_FOR_ADVANCE = 60.0
PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE = 0.6
MIN_SCORE_FOR_ADVANCE = 60
MIN_CONFIDENCE_PERCENT_FOR_ADVANCE = 60

#: The authority that owns a binding employment decision. Never a machine actor.
AUTHORITY_ID = "auth.employment_decision"

#: Mandatory gates. Their *states* — PASS / FAIL / INDETERMINATE — drive eligibility.
GATE_FACT_KEYS = ("gate_work_authorization", "gate_role_requirements")


def _source_document() -> SourceDocument:
    return SourceDocument(
        object_id=SOURCE_ID,
        name="Ugence AI Hiring reference governance",
        source_type=ProvenanceSourceType.REFERENCE_IMPLEMENTATION,
        title="ugence-ai-hiring governed hiring-decision workflow",
        document_version="0.6.0",
        authority_level="reference",
        description="Authoritative reference: non-compensatory eligibility over "
        "mandatory gates, advisory-versus-binding separation, transparent advisory "
        "disposition floors, and fail-closed evidence admissibility.",
    )


def build_ai_hiring_policy_pack(
    *, status: PolicyPackStatus = PolicyPackStatus.APPROVED
) -> PolicyPack:
    """Build the structured AI Hiring reference pack (APPROVED by default)."""

    authority = AuthorityRequirement(
        object_id=AUTHORITY_ID,
        name="binding employment decision authority",
        provenance_refs=_PROV,
        decision_scope="EMPLOYMENT_DECISION",
        authority_type=AuthorityType.HUMAN_APPROVER,
        # The product enforces this in types: an AI actor never decides.
        allow_non_human=False,
    )

    step = ApprovalStep(
        object_id="step.hiring_manager",
        name="hiring manager decision",
        provenance_refs=_PROV,
        order=1,
        authority_requirement_id=AUTHORITY_ID,
        role_label="hiring_manager",
    )
    path = ApprovalPath(
        object_id="path.employment_decision",
        name="employment decision path",
        provenance_refs=_PROV,
        related_object_ids=(step.object_id,),
        step_ids=(step.object_id,),
    )

    # Evidence must be admitted before any gate is evaluated; absence blocks.
    evidence = tuple(
        RequiredEvidence(
            object_id=f"ev.{key}",
            name=f"admitted evidence for {key}",
            provenance_refs=_PROV,
            evidence_kind=EvidenceKind.FIELD_VALUE,
            fact_key=key,
            on_missing=BlockBehavior.BLOCK,
            requires_admissibility_check=True,
            admissibility_capability=CapabilityId.TAP,
        )
        for key in GATE_FACT_KEYS
    )

    # A failed mandatory gate blocks outright — eligibility is non-compensatory, so
    # no score can compensate for it.
    prohibitions = tuple(
        ProhibitedCondition(
            object_id=f"proh.{key}_failed",
            name=f"{key} failed",
            provenance_refs=_PROV,
            conditions=(Predicate(fact_key=key, comparator=Comparator.EQ, value="FAIL"),),
            behavior=BlockBehavior.BLOCK,
            reason_code="MANDATORY_GATE_FAILED",
        )
        for key in GATE_FACT_KEYS
    ) + tuple(
        # An indeterminate gate blocks too: fail-closed, never "proceed and see".
        ProhibitedCondition(
            object_id=f"proh.{key}_indeterminate",
            name=f"{key} indeterminate",
            provenance_refs=_PROV,
            conditions=(
                Predicate(fact_key=key, comparator=Comparator.EQ, value="INDETERMINATE"),
            ),
            behavior=BlockBehavior.BLOCK,
            reason_code="MANDATORY_GATE_INDETERMINATE",
        )
        for key in GATE_FACT_KEYS
    )

    # The advisory disposition: transparent floors over dimension evidence and
    # confidence. This informs; it does not decide.
    advisory_rule = DecisionRule(
        object_id="rule.advisory_advance",
        name="advisory ADVANCE floors",
        provenance_refs=_PROV,
        conditions=(
            Predicate(
                fact_key="lowest_dimension_score",
                comparator=Comparator.GTE,
                value=MIN_SCORE_FOR_ADVANCE,
            ),
            Predicate(
                fact_key="aggregate_confidence_percent",
                comparator=Comparator.GTE,
                value=MIN_CONFIDENCE_PERCENT_FOR_ADVANCE,
            ),
        ),
        authority_requirement_id=AUTHORITY_ID,
        on_satisfied_outcome="ADVANCE",
        on_unsatisfied_outcome="DECLINE",
    )

    # The proposed action stays inside the contract's ceiling.
    constraint = ActionConstraint(
        object_id="act.salary_ceiling",
        name="offer salary ceiling",
        provenance_refs=_PROV,
        action_type="EXTEND_OFFER",
        parameter="salary",
        kind=ConstraintKind.HARD_LIMIT,
        max_value=250_000,
        authority_requirement_id=AUTHORITY_ID,
    )

    return PolicyPack(
        pack_id="pack.ai_hiring.reference",
        name="AI Hiring reference policy pack",
        status=status,
        domain="ai_hiring",
        description="Reference pack for the second equivalence domain (decision D3).",
        source_documents=(_source_document(),),
        decision_rules=(advisory_rule,),
        required_evidence=evidence,
        authority_requirements=(authority,),
        approval_paths=(path,),
        approval_steps=(step,),
        prohibited_conditions=prohibitions,
        action_constraints=(constraint,),
    )


__all__ = [
    "build_ai_hiring_policy_pack",
    "SOURCE_ID",
    "AUTHORITY_ID",
    "GATE_FACT_KEYS",
    "MIN_SCORE_FOR_ADVANCE",
    "MIN_CONFIDENCE_PERCENT_FOR_ADVANCE",
    "PRODUCT_MIN_SCORE_FOR_ADVANCE",
    "PRODUCT_MIN_CONFIDENCE_FOR_ADVANCE",
]
