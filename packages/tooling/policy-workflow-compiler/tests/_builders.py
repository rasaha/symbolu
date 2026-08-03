"""Shared synthetic pack builders for the compiler test suite."""

from __future__ import annotations

from ugence_policy_workflow_compiler.api import (
    ActionConstraint,
    ApprovalPath,
    ApprovalStep,
    AuthorityRequirement,
    AuthorityType,
    BlockBehavior,
    Comparator,
    ConstraintKind,
    DecisionRule,
    ExceptionRule,
    LegitimateCounterexample,
    OverrideRule,
    PolicyPack,
    PolicyPackStatus,
    Predicate,
    ProhibitedCondition,
    ProvenanceSourceType,
    RequiredEvidence,
    SourceDocument,
)

_PROV = ("src.test",)


def _source() -> SourceDocument:
    return SourceDocument(
        object_id="src.test",
        name="test source",
        source_type=ProvenanceSourceType.POLICY_CLAUSE,
        title="synthetic test policy",
    )


def build_full_synthetic_pack(status: PolicyPackStatus = PolicyPackStatus.APPROVED) -> PolicyPack:
    """A synthetic pack that exercises every object category (incl. exceptions,
    overrides, sequence-risk) so coverage/assurance categories all fire."""
    auth = AuthorityRequirement(
        object_id="auth.1", name="approver", provenance_refs=_PROV,
        decision_scope="thing", authority_type=AuthorityType.HUMAN_APPROVER,
    )
    rule = DecisionRule(
        object_id="rule.1", name="main rule", provenance_refs=_PROV,
        conditions=(Predicate(fact_key="ok", comparator=Comparator.IS_TRUE),),
        authority_requirement_id="auth.1", related_object_ids=("auth.1",),
    )
    prohibited = ProhibitedCondition(
        object_id="proh.1", name="blocked", provenance_refs=_PROV,
        conditions=(Predicate(fact_key="bad", comparator=Comparator.IS_TRUE),),
    )
    evidence = RequiredEvidence(
        object_id="ev.1", name="doc", provenance_refs=_PROV, fact_key="doc",
        on_missing=BlockBehavior.BLOCK,
    )
    exc = ExceptionRule(
        object_id="exc.1", name="exception", provenance_refs=_PROV,
        decision_rule_id="rule.1", related_object_ids=("rule.1",),
    )
    ovr = OverrideRule(
        object_id="ovr.1", name="override", provenance_refs=_PROV,
        decision_rule_id="rule.1", authority_requirement_id="auth.1",
        related_object_ids=("rule.1", "auth.1"),
    )
    constraint = ActionConstraint(
        object_id="act.1", name="limit", provenance_refs=_PROV,
        action_type="DO", parameter="amount", kind=ConstraintKind.HARD_LIMIT,
        max_value=100, authority_requirement_id="auth.1",
        related_object_ids=("auth.1",),
    )
    ce = LegitimateCounterexample(
        object_id="ce.1", name="benign", provenance_refs=_PROV,
        resembles_object_id="proh.1", must_allow_outcome="ADVANCE",
    )
    steps = (
        ApprovalStep(object_id="step.1", name="s1", provenance_refs=_PROV, order=1,
                     authority_requirement_id="auth.1", role_label="maker"),
        ApprovalStep(object_id="step.2", name="s2", provenance_refs=_PROV, order=2,
                     authority_requirement_id="auth.1", role_label="checker"),
    )
    path = ApprovalPath(
        object_id="path.1", name="path", provenance_refs=_PROV,
        step_ids=("step.1", "step.2"), segregation_pairs=(("maker", "checker"),),
        related_object_ids=("step.1", "step.2"),
    )
    return PolicyPack(
        pack_id="pack.test", name="synthetic", status=status, domain="test",
        source_documents=(_source(),),
        authority_requirements=(auth,), decision_rules=(rule,),
        prohibited_conditions=(prohibited,), required_evidence=(evidence,),
        exception_rules=(exc,), override_rules=(ovr,), action_constraints=(constraint,),
        legitimate_counterexamples=(ce,), approval_steps=steps, approval_paths=(path,),
    )
