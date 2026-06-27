"""Machinery tests for the internal policy-controller prototype.

Run: python symbolu_neural/internal_policy_controller/tests/test_controller.py
"""
from __future__ import annotations

import numpy as np

from symbolu_neural.internal_policy_controller.drafts import make_drafts, FLAWS
from symbolu_neural.internal_policy_controller.critics import (
    CRITICS, build_feature_matrix, Critic, FLAW_TO_POLICY)
from symbolu_neural.internal_policy_controller.reviser import revise
from symbolu_neural.internal_policy_controller import evaluator, pilot


def test_drafts_labeled_and_cover_flaws():
    d = make_drafts()
    flaws_seen = {f for _, _, f in d}
    assert flaws_seen == set(FLAWS)
    assert all(isinstance(x[1], str) and x[1] for x in d)


def test_reviser_removes_targeted_markers():
    draft = "It might be that, perhaps, the deploy failed but i could be wrong."
    final = revise(draft, "reduce_speculation")
    assert "perhaps" not in final.lower()
    assert "might be that" not in final.lower()


def test_evaluator_flaw_scores():
    assert evaluator.flaw_score("this is a disaster and a nightmare", "escalated") > 0
    assert evaluator.flaw_score("the config value on line 12", "escalated") == 0
    assert evaluator.improvement("maybe perhaps possibly", "the value", "speculative") > 0


def test_all_critic_feature_matrices_build():
    drafts = [d for _, d, _ in make_drafts()]
    for name in CRITICS:
        M, _ = build_feature_matrix(name, drafts)
        assert M.shape[0] == len(drafts)
        assert M.shape[1] > 0


def test_relabeled_ties_symbolu_diag_acc():
    # a linear classifier is invariant to a fixed input-dim permutation
    r = pilot.run(seed=0)
    su = r["arms"]["symbolu"]["diag_acc"]
    rel = r["arms"]["relabeled_symbolu"]["diag_acc"]
    assert abs(su - rel) < 1e-6


def test_pilot_runs_end_to_end():
    r = pilot.run(seed=0)
    for arm in pilot.ARMS:
        assert arm in r["arms"]
    assert r["arms"]["generic_refine"]["diag_acc"] is not None
    assert 0.0 <= r["arms"]["symbolu"]["diag_acc"] <= 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
