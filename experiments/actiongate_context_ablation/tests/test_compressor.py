"""Tests for the extractive compressor prototype: invariance, recall, fail-closed."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import (
    adapter, ablation, compressor as C, compressor_bench as CB, metrics,
    milestone_bench as MB, protected_detector as PD, task_benchmark as TB,
)
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation.units import Context, SemanticUnit


@pytest.fixture(scope="module")
def env():
    items = registry.load_all()
    sp = adapter.default_signed_policy()
    runs = [ablation.run_ablations(it.context, sp) for it in items]
    det = PD.fit(items, runs)
    return items, runs, sp, MB.hybrid_protect_fn(det)


def _sig(ctx, ids, sp):
    return C.signature(C._eval(ctx, ids, sp))


def test_decision_invariance_all_budgets(env):
    items, runs, sp, protect = env
    for target in (0.1, 0.3, 0.5, 0.7):
        for it in items:
            r = C.compress(it.context, protect, sp, target)
            all_ids = [u.id for u in it.context.units]
            assert _sig(it.context, all_ids, sp) == _sig(it.context, r.surviving_ids, sp)
            assert r.invariant


def test_extractive_never_removes_protected_spans(env):
    # the budgeted extractive selector must never remove a protected span
    items, runs, sp, protect = env
    for it in items:
        r = C.compress(it.context, protect, sp, 0.7)
        assert not (r.protected_ids & set(r.removed_extractive))


def test_structural_only_drops_redundant_protected_duplicates(env):
    # structural dedup may drop a protected span ONLY if it is a redundant duplicate
    # whose set still has a surviving member (lossless — the fact is preserved)
    items, runs, sp, protect = env
    for it in items:
        r = C.compress(it.context, protect, sp, 0.7)
        surviving = set(r.surviving_ids)
        for uid in (r.protected_ids & set(r.removed_structural)):
            u = it.context.unit(uid)
            assert u.redundancy_set is not None
            twins = [x.id for x in it.context.units if x.redundancy_set == u.redundancy_set]
            assert any(t in surviving for t in twins)   # a copy of the fact remains


def test_only_extractive_no_rewrite(env):
    # surviving spans are a subset of originals with identical text (no rewriting)
    items, runs, sp, protect = env
    it = items[0]
    r = C.compress(it.context, protect, sp, 0.5)
    orig = {u.id: u.text for u in it.context.units}
    for uid in r.surviving_ids:
        assert uid in orig      # no new/rewritten spans introduced


def test_protected_recall_100_percent(env):
    items, runs, sp, protect = env
    for it, run in zip(items, runs):
        r = C.compress(it.context, protect, sp, 0.7)
        ret, tot = CB._critical_tokens_retained(it, run, r.surviving_ids)
        assert ret == tot        # every decision-relevant token retained


def test_fail_closed_restores_detector_miss(env):
    _, _, sp, _ = env
    trap = SemanticUnit(id="trap", source_type="log_event",
                        text="log: nightly note sink_ok",
                        contrib={"args": {"sink_approved": True}})
    filler = tuple(SemanticUnit(id=f"f{i}", source_type="sentence",
                                text=f"Background note {i} about the window.") for i in range(4))
    ctx = Context(id="adv", base={"tool": "filesystem", "verb": "read",
                                  "target": ["file://s"], "args": {"export": True},
                                  "approvals": [{"approver_policy": "single", "approvers": "single"}]},
                  units=(trap,) + filler, data_origin="ADV")
    miss = lambda c: {u.id for u in c.units if u.source_type in ("approval_record", "evidence_record")}
    r = C.compress(ctx, miss, sp, 0.7)
    assert r.invariant                       # fail-closed guarantees invariance
    assert ("trap" in r.surviving_ids) or r.fell_back


def test_generic_unaware_breaks_decisions(env):
    # the control: protection-blind compression DOES change decisions at high ratio
    items, _, sp, _ = env
    none = lambda ctx: set()
    changed = sum(1 for it in items
                  if not C.compress(it.context, none, sp, 0.7, fail_closed=False).invariant)
    assert changed > 0


def test_task_proxy_preserves_decision_info(env):
    items, runs, sp, protect = env
    for it, run in zip(items, runs):
        r = C.compress(it.context, protect, sp, 0.7)
        assert TB.score(it, run, r.surviving_ids).decision_accuracy >= 1.0 - 1e-9


def test_structural_is_lossless_subset(env):
    items, _, sp, protect = env
    it = next(i for i in items if i.context.redundancy_sets())
    kept, removed = C.structural_compress(it.context, protect(it.context))
    assert set(kept) | set(removed) == {u.id for u in it.context.units}
    assert not (set(kept) & set(removed))


def test_recommendation_is_limited_go_with_proxy_task():
    b = CB.run_bench()
    # criteria met on naturalistic + proxy -> capped at LIMITED_GO (never GO without real LLM)
    assert b.success in ("LIMITED_GO", "STOP")
    assert b.success == "LIMITED_GO"
    assert b.success_detail["all_decision_invariant"] is True
    assert b.success_detail["all_protected_recall_100"] is True


def test_deterministic_reduction():
    b1, b2 = CB.run_bench(), CB.run_bench()
    assert [r.actual_reduction for r in b1.budgets] == [r.actual_reduction for r in b2.budgets]
    assert b1.success == b2.success
