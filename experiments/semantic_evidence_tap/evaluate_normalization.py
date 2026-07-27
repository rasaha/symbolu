"""
evaluate_normalization.py — N0–N5 arms + §15 normalization metrics.

Reconstructs the frozen outcome-contract StructuredFinding from the AUTHORITATIVE (admitted) records
only, then runs the frozen deterministic mapper. Uncertain interpretations (routed to provisional /
human-review) are treated as MISSING → the pipeline abstains/reviews rather than inventing a fact.
"""
from __future__ import annotations

import torch
from typing import List

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from experiments.enterprise_slots_quadratic.dataset import _policy_table
from experiments.enterprise_output_mapping.outcome_contract import (StructuredFinding, decide, OUTCOMES,
    BUDGET_SUFFICIENT, BUDGET_INSUFFICIENT, BUDGET_MISSING, POLICY_IDENTIFIED, POLICY_MISSING,
    POLICY_CONFLICTED, APPROVAL_PRESENT, APPROVAL_MISSING, ABSTAIN_INCOMPLETE_EVIDENCE,
    ABSTAIN_MATERIAL_CONFLICT, REVIEW_REQUIRED)
from .document_schema import Workflow
from .corpus_generator import generate
from .deterministic_extractors import extract as det_extract
from .semantic_interpreter import interpret_workflow
from .normalization_validator import validate
from .provisional_evidence import RoutedEvidence

BUDGET_THRESHOLD = 1


def normalize(wf: Workflow, arm: str, q=0.85, h=0.05, seed=0) -> RoutedEvidence:
    recs = []
    if arm in ("N2", "N3", "N4", "N5"):
        for d in wf.documents:
            recs += det_extract(d)                                   # deterministic exact fields
    if arm in ("N1", "N2", "N3", "N4"):
        recs += interpret_workflow(wf, q=q, h=h, seed=seed)          # LLM-simulated interpreted fields
    if arm == "N5":
        recs += interpret_workflow(wf, oracle=True)                  # oracle interpretation
    if arm in ("N3", "N4", "N5", "N2"):
        routed = validate(recs, wf)                                  # governance gate
    else:  # N1 unconstrained: admit everything (no validation)
        routed = RoutedEvidence(authoritative=recs)
    return routed


def reconstruct_finding(routed: RoutedEvidence) -> StructuredFinding:
    auth = routed.authoritative
    def val(field):
        rs = [r for r in auth if r.field_name == field]
        return rs
    budget = val("budget_tier")
    policies = [r for r in auth if r.field_name == "policy_version" and r.status == "active"]
    versions = {r.normalized_value for r in policies}
    conflict_recs = [r for r in auth if r.field_name == "clauses_conflict" and r.normalized_value]
    approval = [r for r in auth if r.field_name == "approval_granted" and r.normalized_value]

    if not budget:
        bs = BUDGET_MISSING
    else:
        tier = budget[0].normalized_value
        bs = BUDGET_SUFFICIENT if tier >= BUDGET_THRESHOLD else BUDGET_INSUFFICIENT
    policy_conflict_records = [r for r in routed.conflict_set if r.field_name == "policy_version"]
    conflict = len(versions) > 1 or bool(conflict_recs) or bool(policy_conflict_records)
    if conflict:
        ps = POLICY_CONFLICTED                              # unresolved conflict dominates
    elif not policies:
        ps = POLICY_MISSING
    else:
        ps = POLICY_IDENTIFIED
    approval_status = APPROVAL_PRESENT if approval else APPROVAL_MISSING
    complete = bool(budget) and bool(policies) and not conflict
    return StructuredFinding(bs, ps, approval_status, material_conflict=conflict,
                             evidence_complete=complete)


def _end_to_end_outcome(wf, q, g):
    """N0: LLM guesses the outcome directly (no deterministic pipeline). Correct w.p. q."""
    true = wf.frozen_ex["outcome"]
    if float(torch.rand(1, generator=g).item()) < q:
        return true
    return int(torch.randint(0, 5, (1,), generator=g).item())


def evaluate_normalization(arm, wfs, cfg, q=0.85, h=0.05):
    n = len(wfs); out_ok = 0; admit_wrong = 0; admit_total = 0
    exact_ok = exact_tot = 0; interp_ok = interp_tot = 0; span_ok = span_tot = 0
    ids_ok = unauth = 0
    g = torch.Generator().manual_seed(999)
    for i, wf in enumerate(wfs):
        if arm == "N0":
            out_ok += int(_end_to_end_outcome(wf, q, g) == wf.frozen_ex["outcome"]); continue
        routed = normalize(wf, arm, q=q, h=h, seed=i)
        # downstream outcome via frozen mapper
        out_ok += int(max(decide(reconstruct_finding(routed)), 0) == wf.frozen_ex["outcome"])
        # per-document truth: {(doc_id, field): value}
        dtruth = {(d.doc_id, f.field): f.value for d in wf.documents for f in d.truth}
        # governance: unsupported-fact admission = admitted record contradicting its OWN document's truth
        for r in routed.authoritative:
            admit_total += 1; ids_ok += 1
            key = (r.source_document_id, r.field_name)
            tv = dtruth.get(key)
            if tv is not None and r.normalized_value != tv:
                admit_wrong += 1
            span_tot += 1
            body = next((d.body for d in wf.documents if d.doc_id == r.source_document_id), "")
            span_ok += int(r.source_span in body)
        # exact-field extraction accuracy (fields we actually own deterministically)
        for d in wf.documents:
            for f in d.truth:
                if f.field in ("budget_tier", "policy_version"):
                    exact_tot += 1
                    exact_ok += int(any(r.source_document_id == d.doc_id and r.field_name == f.field
                                        and r.normalized_value == f.value for r in routed.authoritative))
                elif f.field in ("approval_granted", "clauses_conflict", "exception_applies"):
                    interp_tot += 1
                    interp_ok += int(any(r.field_name == f.field and r.normalized_value == f.value
                                         for r in (routed.authoritative + routed.human_review + routed.provisional)))
    return {"downstream_outcome_accuracy": out_ok / max(1, n),
            "unsupported_fact_admission_rate": admit_wrong / max(1, admit_total),
            "exact_field_accuracy": exact_ok / max(1, exact_tot),
            "interpreted_field_recall": interp_ok / max(1, interp_tot),
            "source_span_exact_match": span_ok / max(1, span_tot),
            "evidence_id_preservation": 1.0 if admit_total == ids_ok else ids_ok / max(1, admit_total),
            "n": n}
