"""Tests for the constrained output-mapping + duplicate-hardening phase."""
from __future__ import annotations

import torch

from experiments.enterprise_slots_quadratic.schema import DomainCfg, Evidence, ACTIVE, SUPERSEDED
from experiments.enterprise_output_mapping.workflows import build_outcome
from experiments.enterprise_output_mapping.outcome_contract import (StructuredFinding, decide, APPROVE,
    REJECT, REVIEW_REQUIRED, ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT, INVALID_RUN,
    BUDGET_SUFFICIENT, BUDGET_INSUFFICIENT, POLICY_IDENTIFIED, POLICY_CONFLICTED, POLICY_MISSING,
    APPROVAL_PRESENT, APPROVAL_MISSING)
from experiments.enterprise_output_mapping.duplicate_equivalence import (classify_pair, dedup,
    EXACT_DUPLICATE, SOURCE_REDUNDANT, VERSION_PAIR, CONFLICT_PAIR, COLLAPSIBLE)


def _f(**kw):
    d = dict(budget_status=BUDGET_SUFFICIENT, policy_status=POLICY_IDENTIFIED,
             approval_status=APPROVAL_PRESENT, material_conflict=False, evidence_complete=True)
    d.update(kw); return StructuredFinding(**d)


def test_contract_semantics():
    assert decide(_f()) == APPROVE
    assert decide(_f(approval_status=APPROVAL_MISSING)) == REVIEW_REQUIRED
    assert decide(_f(budget_status=BUDGET_INSUFFICIENT)) == REJECT
    assert decide(_f(material_conflict=True)) == ABSTAIN_MATERIAL_CONFLICT
    assert decide(_f(policy_status=POLICY_MISSING, evidence_complete=False)) == ABSTAIN_INCOMPLETE_EVIDENCE
    assert decide(_f(unauthorized_present=True)) == INVALID_RUN


def test_hard_gates_priority():
    # conflict gate beats everything else
    assert decide(_f(material_conflict=True, budget_status=BUDGET_INSUFFICIENT)) == ABSTAIN_MATERIAL_CONFLICT


def test_outcome_labels_match_contract():
    cfg = DomainCfg(); g = torch.Generator().manual_seed(3)
    for _ in range(200):
        ex = build_outcome(cfg, 128, "streaming", g)
        f = ex["finding"]
        assert ex["outcome"] == decide(StructuredFinding(f["budget_status"], f["policy_status"],
                                       f["approval_status"], bool(f["material_conflict"]),
                                       bool(f["evidence_complete"])))


def _ev(**kw):
    d = dict(tenant_id=0, evidence_id=0, document_id=0, section_id=0, subject_type=2, subject_id=5,
             relation_type=3, object_type=4, object_id_or_value=7, timestamp=0, valid_from=0,
             valid_to=100, version=2, status=ACTIVE, source_authority=1.0, source_span=0,
             access_roles=0xffff)
    d.update(kw); return Evidence(**d)


def test_duplicate_classification():
    a = _ev(evidence_id=1)
    assert classify_pair(a, _ev(evidence_id=2)) == EXACT_DUPLICATE
    assert classify_pair(a, _ev(evidence_id=3, document_id=9, source_authority=0.8)) == SOURCE_REDUNDANT
    assert classify_pair(a, _ev(evidence_id=4, status=SUPERSEDED, version=1)) == VERSION_PAIR
    assert classify_pair(a, _ev(evidence_id=5, object_id_or_value=8)) == CONFLICT_PAIR


def test_dedup_never_collapses_pairs():
    a = _ev(evidence_id=1)
    stale = _ev(evidence_id=2, status=SUPERSEDED, version=1)
    conflict = _ev(evidence_id=3, object_id_or_value=8)
    id_of = {e.evidence_id: e for e in (a, stale, conflict)}
    kept, audit = dedup([1, 2, 3], id_of)
    assert set(kept) == {1, 2, 3}                              # version + conflict pairs preserved
    for rec in audit:
        assert rec["kind"] in COLLAPSIBLE


def test_dedup_collapses_exact():
    a = _ev(evidence_id=1); dup = _ev(evidence_id=2)
    id_of = {1: a, 2: dup}
    kept, audit = dedup([1, 2], id_of)
    assert len(kept) == 1 and audit and audit[0]["provenance_preserved"]


def test_frozen_slot_package_unmodified():
    """This phase must not modify the frozen slot/quadratic modules (import only)."""
    import experiments.enterprise_slots_quadratic.admission_policies as A
    src = open(A.__file__).read()
    assert "query_subjects" in src and "protected_ids" in src   # the validated P5 logic intact


def test_no_label_leak_into_working_set():
    from experiments.enterprise_slots_quadratic.models import working_set
    cfg = DomainCfg(); ex = build_outcome(cfg, 128, "streaming", torch.Generator().manual_seed(9))
    ex2 = {**ex, "outcome": (ex["outcome"] + 1) % 5,
           "finding": {k: 0 for k in ex["finding"]}}
    assert working_set(ex, "S3", 4, "P5")["ids"] == working_set(ex2, "S3", 4, "P5")["ids"]
