"""Structured Procurement reference policy pack.

Encodes the existing Ugence Procurement reference workflow as a reviewed policy
pack. Amounts are integer minor units. Every substantive object cites the
procurement reference source. The authorization action constraints are declared in
the exact priority order the reference ``BudgetAuthorityAdapter`` evaluates:

    expired -> restricted supplier -> restricted budget -> hard limit ->
    threshold (senior approval) -> authorized

so the equivalence harness can replay that order deterministically.
"""

from __future__ import annotations

from ..api import (
    ActionConstraint,
    ApprovalDecision,
    ApprovalPath,
    ApprovalStep,
    AuditRequirement,
    AuthorityRequirement,
    AuthorityType,
    BlockBehavior,
    CapabilityId,
    Comparator,
    ConnectorMapping,
    ConstraintKind,
    DecisionRule,
    EvidenceKind,
    ExpectedOutcome,
    HumanApprovalRecord,
    LegitimateCounterexample,
    PolicyPack,
    PolicyPackStatus,
    Predicate,
    ProhibitedCondition,
    ProvenanceReference,
    ProvenanceSourceType,
    RequiredEvidence,
    SourceDocument,
    TestCategory,
    TestScenario,
)

# -- reference constants (authoritative: mirror ugence_procurement behavior) ----

#: Hard spending limit (minor units) — reference BudgetAuthorityAdapter default.
HARD_LIMIT = 10_000_000
#: Senior-approval threshold (minor units) — reference default.
APPROVAL_THRESHOLD = 1_000_000

#: The single provenance source for every substantive object in this pack.
SOURCE_ID = "src.procurement.reference"

_PROV = (SOURCE_ID,)


def _source_document() -> SourceDocument:
    return SourceDocument(
        object_id=SOURCE_ID,
        name="Ugence Procurement reference workflow",
        source_type=ProvenanceSourceType.REFERENCE_IMPLEMENTATION,
        title="ugence-procurement 0.1.0 governed purchase-approval workflow",
        document_version="0.1.0",
        content_digest="",
        authority_level="reference",
        description="Authoritative reference: assessment checks, budget-authority "
        "classification, approval/decision vocabulary, action mappings, supplier "
        "outcomes, reconciliation and compensation.",
    )


def build_procurement_policy_pack(
    *, status: PolicyPackStatus = PolicyPackStatus.APPROVED
) -> PolicyPack:
    """Build the structured Procurement reference pack (APPROVED by default)."""

    provenance_source = ProvenanceReference(
        source_id=SOURCE_ID,
        source_type=ProvenanceSourceType.REFERENCE_IMPLEMENTATION,
        title="ugence-procurement reference workflow",
        version="0.1.0",
    )
    # (kept for documentation; the SourceDocument below is what objects cite)
    del provenance_source

    # -- connector mappings ---------------------------------------------------
    connectors = (
        ConnectorMapping(
            object_id="conn.supplier_id",
            name="supplier id -> supplier system",
            provenance_refs=_PROV,
            policy_concept="supplier_id",
            target_system="SUPPLIER",
            target_field="supplier.supplier_id",
            authoritative=True,
        ),
        ConnectorMapping(
            object_id="conn.budget_id",
            name="budget id -> budget system",
            provenance_refs=_PROV,
            policy_concept="budget_id",
            target_system="SUPPLIER",
            target_field="budget.budget_id",
            authoritative=True,
        ),
        ConnectorMapping(
            object_id="conn.amount",
            name="amount -> purchase order amount",
            provenance_refs=_PROV,
            policy_concept="amount",
            target_system="SUPPLIER",
            target_field="purchase_order.amount",
            authoritative=True,
        ),
    )

    # -- authority requirements ----------------------------------------------
    authorities = (
        AuthorityRequirement(
            object_id="auth.human_approver",
            name="human purchase approver",
            provenance_refs=_PROV,
            decision_scope="purchase_approval",
            authority_type=AuthorityType.HUMAN_APPROVER,
            required_role="approver",
            allow_non_human=False,
        ),
        AuthorityRequirement(
            object_id="auth.budget_authority",
            name="budget authorization (control plane)",
            provenance_refs=_PROV,
            decision_scope="purchase_order_authorization",
            authority_type=AuthorityType.DELEGATED_POLICY,
            required_role="budget_authority",
            allow_non_human=True,
        ),
    )

    # -- required evidence (the three fail-closed blocking checks) ------------
    evidence = (
        RequiredEvidence(
            object_id="ev.supplier_exists",
            name="supplier present",
            provenance_refs=_PROV,
            evidence_kind=EvidenceKind.FIELD_VALUE,
            fact_key="supplier_id",
            connector_mapping_id="conn.supplier_id",
            on_missing=BlockBehavior.BLOCK,
            requires_admissibility_check=False,
        ),
        RequiredEvidence(
            object_id="ev.budget_exists",
            name="budget present",
            provenance_refs=_PROV,
            evidence_kind=EvidenceKind.FIELD_VALUE,
            fact_key="budget_id",
            connector_mapping_id="conn.budget_id",
            on_missing=BlockBehavior.BLOCK,
            requires_admissibility_check=False,
        ),
        RequiredEvidence(
            object_id="ev.required_fields_complete",
            name="required request fields complete",
            provenance_refs=_PROV,
            evidence_kind=EvidenceKind.SYSTEM_RECORD,
            fact_key="required_fields_complete",
            connector_mapping_id="",
            on_missing=BlockBehavior.BLOCK,
            requires_admissibility_check=True,
        ),
    )

    # -- prohibited conditions (validation-time fail-closed) ------------------
    prohibited = (
        ProhibitedCondition(
            object_id="prohibit.non_positive_total",
            name="non-positive total blocked",
            provenance_refs=_PROV,
            conditions=(Predicate(fact_key="total_amount", comparator=Comparator.LTE, value=0),),
            behavior=BlockBehavior.BLOCK,
            reason_code="PURCHASE_REQUEST_INVALID",
        ),
        ProhibitedCondition(
            object_id="prohibit.unknown_supplier",
            name="unknown supplier blocked",
            provenance_refs=_PROV,
            conditions=(Predicate(fact_key="supplier_known", comparator=Comparator.IS_FALSE),),
            behavior=BlockBehavior.BLOCK,
            reason_code="SUPPLIER_NOT_KNOWN",
        ),
        ProhibitedCondition(
            object_id="prohibit.unknown_budget",
            name="unknown budget blocked",
            provenance_refs=_PROV,
            conditions=(Predicate(fact_key="budget_known", comparator=Comparator.IS_FALSE),),
            behavior=BlockBehavior.BLOCK,
            reason_code="BUDGET_NOT_KNOWN",
        ),
    )

    # -- decision rule (human approver binds the decision) --------------------
    decision_rules = (
        DecisionRule(
            object_id="rule.purchase_approval",
            name="purchase approval decision",
            provenance_refs=_PROV,
            conditions=(
                Predicate(fact_key="assessment_blocked", comparator=Comparator.IS_FALSE),
            ),
            authority_requirement_id="auth.human_approver",
            on_satisfied_outcome="ADVANCE",
            on_unsatisfied_outcome="REJECT",
            related_object_ids=("auth.human_approver",),
        ),
    )

    # -- approval path + segregation of duties --------------------------------
    approval_steps = (
        ApprovalStep(
            object_id="step.requester",
            name="requester submits",
            provenance_refs=_PROV,
            order=1,
            authority_requirement_id="auth.human_approver",
            role_label="requester",
        ),
        ApprovalStep(
            object_id="step.approver",
            name="approver approves",
            provenance_refs=_PROV,
            order=2,
            authority_requirement_id="auth.human_approver",
            role_label="approver",
        ),
    )
    approval_paths = (
        ApprovalPath(
            object_id="path.purchase_approval",
            name="purchase approval path",
            provenance_refs=_PROV,
            step_ids=("step.requester", "step.approver"),
            segregation_pairs=(("requester", "approver"),),
            related_object_ids=("step.requester", "step.approver"),
        ),
    )

    # -- action constraints (exact-action authorization, in reference order) --
    action_constraints = (
        ActionConstraint(
            object_id="act.cer_not_expired",
            name="authorization not expired",
            provenance_refs=_PROV,
            action_type="CREATE_PURCHASE_ORDER",
            parameter="cer_expiry",
            kind=ConstraintKind.ONCE_ONLY,
            authority_requirement_id="auth.budget_authority",
            violation_reason_code="EXPIRED",
            related_object_ids=("auth.budget_authority",),
        ),
        ActionConstraint(
            object_id="act.supplier_not_restricted",
            name="supplier not restricted",
            provenance_refs=_PROV,
            action_type="CREATE_PURCHASE_ORDER",
            parameter="supplier_id",
            kind=ConstraintKind.NOT_MEMBER_OF,
            authority_requirement_id="auth.budget_authority",
            violation_reason_code="DENIED",
            related_object_ids=("auth.budget_authority",),
        ),
        ActionConstraint(
            object_id="act.budget_not_restricted",
            name="budget not restricted",
            provenance_refs=_PROV,
            action_type="CREATE_PURCHASE_ORDER",
            parameter="budget_id",
            kind=ConstraintKind.NOT_MEMBER_OF,
            authority_requirement_id="auth.budget_authority",
            violation_reason_code="DENIED",
            related_object_ids=("auth.budget_authority",),
        ),
        ActionConstraint(
            object_id="act.amount_hard_limit",
            name="amount within hard limit",
            provenance_refs=_PROV,
            action_type="CREATE_PURCHASE_ORDER",
            parameter="amount",
            kind=ConstraintKind.HARD_LIMIT,
            max_value=HARD_LIMIT,
            authority_requirement_id="auth.budget_authority",
            violation_reason_code="DENIED",
            related_object_ids=("auth.budget_authority",),
        ),
        ActionConstraint(
            object_id="act.amount_threshold",
            name="amount within auto-authorize threshold",
            provenance_refs=_PROV,
            action_type="CREATE_PURCHASE_ORDER",
            parameter="amount",
            kind=ConstraintKind.NUMERIC_RANGE,
            max_value=APPROVAL_THRESHOLD,
            authority_requirement_id="auth.budget_authority",
            violation_reason_code="AUTHORIZED_WITH_CONSTRAINTS",
            related_object_ids=("auth.budget_authority",),
        ),
    )

    # -- legitimate counterexample (must-allow) -------------------------------
    counterexamples = (
        LegitimateCounterexample(
            object_id="ce.elevated_within_approved_budget",
            name="large purchase within approved elevated budget",
            provenance_refs=_PROV,
            resembles_object_id="act.amount_hard_limit",
            distinguishing_conditions=(
                Predicate(fact_key="amount", comparator=Comparator.LTE, value=HARD_LIMIT),
                Predicate(fact_key="budget_restricted", comparator=Comparator.IS_FALSE),
            ),
            must_allow_outcome="ADVANCE",
        ),
    )

    # -- audit requirements ---------------------------------------------------
    audit = (
        AuditRequirement(
            object_id="audit.decision",
            name="decision audit",
            provenance_refs=_PROV,
            required_fields=("decision_reference", "actor_identity", "actor_role", "reason_codes"),
            applies_to_node_kinds=("DECISION_RULE", "APPROVAL_GATE"),
        ),
        AuditRequirement(
            object_id="audit.action",
            name="action authorization audit",
            provenance_refs=_PROV,
            required_fields=("action_reference", "constraint_digest", "authorization_outcome"),
            applies_to_node_kinds=("ACTION_CONSTRAINT",),
        ),
        AuditRequirement(
            object_id="audit.execution",
            name="execution/reconciliation audit",
            provenance_refs=_PROV,
            required_fields=("outcome", "reconciliation_status", "compensation_required"),
            applies_to_node_kinds=("TERMINAL_OUTCOME",),
        ),
    )

    # -- authored supplier-outcome scenarios (reference terminal behavior) ----
    scenarios = (
        TestScenario(
            object_id="scn.supplier_accepted",
            name="supplier accepts -> succeeded",
            provenance_refs=_PROV,
            category=TestCategory.POSITIVE,
            source_object_ids=("rule.purchase_approval",),
            initial_facts={"supplier_outcome": "ACCEPTED"},
            requested_action="CREATE_PURCHASE_ORDER",
            expected_outcome=ExpectedOutcome(
                terminal_state="ADVANCE_AUTHORIZED",
                reason_codes=("ACCEPTED",),
                authorization_outcome="AUTHORIZED",
            ),
        ),
        TestScenario(
            object_id="scn.supplier_rejected",
            name="supplier rejects -> compensation required",
            provenance_refs=_PROV,
            category=TestCategory.NEGATIVE,
            source_object_ids=("rule.purchase_approval",),
            initial_facts={"supplier_outcome": "REJECTED"},
            requested_action="CREATE_PURCHASE_ORDER",
            expected_outcome=ExpectedOutcome(
                terminal_state="DENIED",
                reason_codes=("REJECTED",),
            ),
        ),
        TestScenario(
            object_id="scn.supplier_timeout",
            name="supplier times out -> unknown/indeterminate",
            provenance_refs=_PROV,
            category=TestCategory.TIMEOUT,
            source_object_ids=("rule.purchase_approval",),
            initial_facts={"supplier_outcome": "TIMED_OUT"},
            requested_action="CREATE_PURCHASE_ORDER",
            expected_outcome=ExpectedOutcome(
                terminal_state="INDETERMINATE",
                reason_codes=("TIMED_OUT",),
            ),
        ),
    )

    return PolicyPack(
        pack_id="pack.procurement.reference",
        name="Ugence Procurement reference policy pack",
        version=1,
        status=status,
        domain="procurement",
        description="Structured encoding of the ugence-procurement reference workflow.",
        source_documents=(_source_document(),),
        decision_rules=decision_rules,
        required_evidence=evidence,
        authority_requirements=authorities,
        approval_paths=approval_paths,
        approval_steps=approval_steps,
        prohibited_conditions=prohibited,
        action_constraints=action_constraints,
        legitimate_counterexamples=counterexamples,
        connector_mappings=connectors,
        audit_requirements=audit,
        test_scenarios=scenarios,
    )


def build_procurement_approval_fixture(pack: PolicyPack) -> HumanApprovalRecord:
    """An OFFLINE approval fixture for the procurement pack.

    Clearly labeled ``is_fixture=True``; it is not a real reviewer authority.
    """
    from ..api import build_approval_record

    return build_approval_record(
        approval_id="approval.procurement.reference.fixture",
        pack=pack,
        reviewer_id="fixture.reviewer",
        reviewer_role="procurement_governance_reviewer",
        reviewer_authority_reference="offline-fixture://procurement",
        decision=ApprovalDecision.APPROVED,
        approved_at="2026-08-03T00:00:00Z",
        reviewed_gap_ids=(),
        accepted_warning_ids=(),
        justification="Offline reference-equivalence fixture; not a production approval.",
        is_fixture=True,
        name="procurement reference approval fixture",
    )
