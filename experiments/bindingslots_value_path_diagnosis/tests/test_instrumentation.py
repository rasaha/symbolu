#!/usr/bin/env python3
"""Instrumentation tests (§17). Require torch; if torch is unavailable the suite reports
RESOURCE_BLOCKED and returns 0 so torch-free CI stays green (mirrors the persistence suite).

Covers: hooks-disabled no-op, deterministic reproduction, checkpoint hashing, target-slot capture,
oracle-address/read-query/postwrite isolation, probe splits + no cohort leakage, zero optimizer
steps during diagnostics, unchanged diagnostic checkpoint hashes, gradient groups complete +
non-overlapping, zero-gradient-safe cosine, and zero-baseline non-informative labelling.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False


def _model():
    import _nso
    MDL, TA = _nso.models, _nso.tasks_adapter
    vocab = TA.build_corpus()[1]
    import interventions as IV
    m, _, _ = MDL.build_matched("S", len(vocab), 2000000, d=128, h=4, layers=4, max_len=1200,
                                window=TA.WINDOW, num_slots=32)
    IV.install_capture_hooks(m)
    m.eval()
    return m, vocab


def test_hooks_disabled_are_a_noop():
    import torch
    import diagnosis_lib as DL
    import _nso
    m, vocab = _model()
    T = _nso.tasks
    X, fp, qp, tg = DL.needle_examples(vocab, T, 123, 8, 96)
    with torch.no_grad():
        lo0 = m(X)
    with DL.instrumented_model(m, mode=None, capture=True, fact_pos=fp, query_pos=qp):
        with torch.no_grad():
            lo1 = m(X)
    assert torch.equal(lo0, lo1), "instrumented mode=None must be byte-identical to stock forward"


def test_target_slot_capture_shapes_and_sstar():
    import torch
    import diagnosis_lib as DL
    import _nso
    m, vocab = _model()
    T = _nso.tasks
    X, fp, qp, tg = DL.needle_examples(vocab, T, 123, 8, 96)
    with DL.instrumented_model(m, mode=None, capture=True, fact_pos=fp, query_pos=qp) as slots:
        with torch.no_grad():
            _ = m(X)
        sm = slots[0]
        cap = sm._cap
        B = len(X)
        assert cap["m_postwrite"].shape == (B, 128)
        assert cap["m_query"].shape == (B, 128)
        assert cap["waddr_fact"].shape[0] == B
        # s* is the argmax of the write address at the fact position
        assert torch.equal(cap["sstar"], cap["waddr_fact"].argmax(-1))


def test_oracle_address_isolation():
    _oracle_isolation("oracle_address")


def test_oracle_read_query_isolation():
    _oracle_isolation("oracle_read_query")


def test_oracle_postwrite_isolation():
    _oracle_isolation("oracle_postwrite")


def _oracle_isolation(mode):
    import torch
    import types
    import diagnosis_lib as DL
    from diagnosis_lib import _instrumented_forward
    import _nso
    m, vocab = _model()
    T = _nso.tasks
    X, fp, qp, tg = DL.needle_examples(vocab, T, 123, 8, 96)
    sm = m.slot_mixers()[0]
    grabbed = {}
    h = sm.register_forward_pre_hook(lambda mod, inp: grabbed.__setitem__("x", inp[0].detach()))
    with torch.no_grad():
        _ = m(X)
    h.remove()
    xin = grabbed["x"]
    sm.forward = types.MethodType(_instrumented_forward, sm)
    sm._diag_mode = None; sm._diag_capture = False
    with torch.no_grad():
        out_stock = sm(xin)
    sm._diag_mode = mode; sm._diag_fact_pos = fp; sm._diag_query_pos = qp
    with torch.no_grad():
        out_oracle = sm(xin)
    del sm.forward
    changed = (out_stock - out_oracle).abs().sum(-1) > 1e-9   # [B, N]
    j = torch.arange(len(X))
    # exactly one changed position per example, and it is the query position
    assert bool((changed.sum(1) == 1).all()), f"{mode}: more than the query position changed"
    assert bool(changed[j, qp].all()), f"{mode}: the query position did not change"


def test_reproduction_determinism_and_zero_extra_steps():
    import diagnosis_lib as DL
    rec1, snaps1, n1 = DL.reproduce_run("R0", 24, steps=6, targets=[6])
    rec2, snaps2, n2 = DL.reproduce_run("R0", 24, steps=6, targets=[6])
    assert n1 == 6 and n2 == 6, "exactly one optimizer step per training step"
    assert rec1["needle_by_dist"] == rec2["needle_by_dist"]
    assert rec1["trajectory"] == rec2["trajectory"], "trajectory must be deterministic"
    assert DL.model_state_hash(snaps1[6]) == DL.model_state_hash(snaps2[6]), "checkpoint hashing deterministic"


def test_gradient_groups_complete_and_non_overlapping():
    import gradients as GR
    m, _ = _model()
    audit = GR.audit_param_groups(m)
    assert audit["complete"] and audit["non_overlapping"]
    assert audit["covered_numel"] == audit["total_numel"]


def test_zero_gradient_safe_cosine():
    import torch
    import gradients as GR
    z = torch.zeros(5)
    v = torch.randn(5)
    r = GR._cos(z, v)
    assert r["zero_gradient"] is True and r["cosine"] is None
    r2 = GR._cos(v, v)
    assert abs(r2["cosine"] - 1.0) < 1e-6


def test_diagnostics_zero_steps_and_unchanged_hash():
    import diagnosis_lib as DL
    import gradients as GR
    import value_path as VP
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    _rec, snaps, _n = DL.reproduce_run("R0", 24, steps=6, targets=[6])
    m = snaps[6]
    h0 = DL.model_state_hash(m)
    _ = VP.slot_value_integrity(m, vocab, T)
    _ = VP.ordinary_eval(m, vocab, T)
    g = GR.run_gradient_diagnostics(m, "R0", vocab, T, TA)
    assert g["state_hash_unchanged"] is True
    assert DL.model_state_hash(m) == h0, "diagnostics must not change model state (zero optimizer steps)"


def test_probe_splits_fixed_and_no_cohort_leakage():
    import probes as PR
    tr, va, te = PR._split_indices(PR.PROBE_N)
    # disjoint splits
    s = set(tr.tolist()) | set(va.tolist()) | set(te.tolist())
    assert len(s) == PR.PROBE_N
    assert set(tr.tolist()).isdisjoint(te.tolist())
    assert set(tr.tolist()).isdisjoint(va.tolist())
    # probe seed disjoint from ledger eval seeds
    assert PR.PROBE_SEED not in (123, 124, 125, 128, 129)


def test_needle_examples_match_ledger():
    import diagnosis_lib as DL
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    v = DL.verify_needle_examples_match_ledger(vocab, T, 123, 40, 96)
    assert v["X_identical"] and v["target_identical"] and v["answer_pos_all_N_minus_1"]


def _run_standalone():
    if not HAVE_TORCH:
        print("instrumentation tests: RESOURCE_BLOCKED (torch unavailable) — 0 run, 0 failed")
        return 0
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"instrumentation tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
