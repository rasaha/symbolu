"""Tests: effect detection, ablation modes, and classification correctness."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import adapter, ablation, effects
from actiongate_context_ablation.corpus import tier1_fixtures as T


@pytest.fixture(scope="module")
def sp():
    return adapter.default_signed_policy()


def _run(ctx, sp, dev=False):
    return ablation.run_ablations(ctx, sp, dev=dev)


def test_adapter_drives_real_gate(sp):
    # ALLOW path and DENY path, from the REAL frozen gate.
    allow = adapter.evaluate(adapter.RequestSpec(
        tool="terraform", verb="apply", target=("svc://x",),
        evidence=({"kind": "signed_artifact"}, {"kind": "simulation", "fidelity": "HIGH"})), sp)
    assert allow["decision"]["outcome"] == "ALLOW"
    deny = adapter.evaluate(adapter.RequestSpec(
        tool="filesystem", verb="read", target=("file://s",),
        args={"export": True, "sink_approved": False},
        approvals=({"approver_policy": "single", "approvers": "single"},)), sp)
    assert deny["decision"]["outcome"] == "DENY"


def test_envelope_field_change_detected(sp):
    run = _run(T.changed_amount(), sp)
    assert "amt" in run.envelope_units


def test_outcome_flip_detected(sp):
    run = _run(T.hidden_negation(), sp)
    assert "sink" in run.decision_units
    rec = next(r for r in run.records if r.ablation_id == "single:sink")
    assert rec.oracle_effect.outcome_before != rec.oracle_effect.outcome_after


def test_assurance_only_change_detected():
    # Unit-level: same outcome, changed dispositive rules -> ASSURANCE only.
    before = {"envelope": {"operation": "DEPLOY"},
              "decision": {"outcome": "ALLOW", "dispositive_rules": ["R2"],
                           "applied_constraints": None, "reason": ""}}
    after = {"envelope": {"operation": "DEPLOY"},
             "decision": {"outcome": "ALLOW", "dispositive_rules": ["R2", "R9"],
                          "applied_constraints": None, "reason": ""}}

    class _Ctx:
        units = ()
    eff = effects.classify(before, after, ctx=_Ctx(), removed_ids=set())
    assert effects.ASSURANCE_CRITICAL in eff.labels
    assert effects.DECISION_OUTCOME_CRITICAL not in eff.labels
    assert effects.ENVELOPE_FIELD_CRITICAL not in eff.labels


def test_duplicate_requires_redundancy_ablation(sp):
    # dev=False so ONLY redundancy-set ablation can catch the duplicated fact.
    run = _run(T.duplicated_critical_fact(), sp, dev=False)
    assert "sink1" not in run.decision_units and "sink1" not in run.envelope_units
    assert "sink2" not in run.decision_units and "sink2" not in run.envelope_units
    assert {"sink1", "sink2"} <= run.redundant_units
    # single ablation of either was individually inert
    s1 = next(r for r in run.records if r.ablation_id == "single:sink1")
    assert effects.NO_OBSERVED_EFFECT in s1.oracle_effect.labels


def test_rule_exception_interaction(sp):
    run = _run(T.rule_plus_distant_exception(), sp)
    # the approval (exception) is decision-critical because the widening rule is present
    assert "appr" in run.decision_units
    assert any(r.mode == ablation.LINKED_PAIR for r in run.records)


def test_single_ablation_misses_pairwise(sp):
    run = _run(T.jointly_necessary_pair(), sp)
    for uid in ("simA", "simB"):
        s = next(r for r in run.records if r.ablation_id == f"single:{uid}")
        assert effects.NO_OBSERVED_EFFECT in s.oracle_effect.labels   # inert alone
    assert {"simA", "simB"} <= run.interaction_units                  # caught jointly


def test_structure_break_detected(sp):
    run = _run(T.entity_alias(), sp)
    assert "entity" in run.structure_units


def test_extractor_sensitive_not_semantic_ground_truth(sp):
    # Any unit flagged extractor-sensitive whose ORACLE effect is inert must not be
    # counted as semantically critical.
    from actiongate_context_ablation.corpus import tier3_heldout as T3
    seen_flag = False
    for ctx in T3.load():
        run = _run(ctx, sp)
        for r in run.records:
            if r.mode == ablation.SINGLE and r.extractor_sensitive:
                seen_flag = True
                if effects.NO_OBSERVED_EFFECT in r.oracle_effect.labels:
                    uid = r.removed_ids[0]
                    assert uid not in run.decision_units
                    assert uid not in run.envelope_units
                    assert uid not in run.assurance_units
    assert seen_flag  # tier3 paraphrase must produce at least one extractor-sensitive case
