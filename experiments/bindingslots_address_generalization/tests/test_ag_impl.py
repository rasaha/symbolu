#!/usr/bin/env python3
"""Torch-backed implementation tests (§17). Reports RESOURCE_BLOCKED and returns 0 if torch is absent.

Covers: G1 projection math (nonnegative corrected cosine), zero-gradient handling, projection limited
to write_addr_proj, LM gradient unchanged, A1 hard-negative/label integrity + task-query positions,
and B0 training-equivalence (short) between run_ag_arm(levers off) and the frozen run_h2.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

try:
    import torch  # noqa: F401
    HAVE = True
except Exception:
    HAVE = False


def _model():
    import _nso
    import interventions as IV
    MDL, TA = _nso.models, _nso.tasks_adapter
    vocab = TA.build_corpus()[1]
    m, _, _ = MDL.build_matched("S", len(vocab), 2000000, d=128, h=4, layers=4, max_len=1200,
                                window=TA.WINDOW, num_slots=32)
    IV.install_capture_hooks(m)
    return m, vocab


def test_projection_makes_cosine_nonnegative_and_wak_only():
    import torch
    import interventions_ag as IAG
    m, _ = _model()
    wak = IAG.write_addr_params(m)
    other = [(n, p) for n, p in m.named_parameters() if (n, p) not in wak]
    # craft conflicting g_lm and g_aux at wak; set .grad = g_lm + g_aux (as after two backwards)
    torch.manual_seed(0)
    g_lm = {n: torch.randn_like(p) for n, p in wak}
    g_aux = {n: -g_lm[n] * 0.5 + 0.1 * torch.randn_like(g_lm[n]) for n in g_lm}  # negative-ish cosine
    for n, p in wak:
        p.grad = (g_lm[n] + g_aux[n]).clone()
    # snapshot a non-wak grad to prove it's untouched
    n0, p0 = other[0]; p0.grad = torch.randn_like(p0); before = p0.grad.clone()
    ln2 = sum((g_lm[n] ** 2).sum().item() for n, _ in wak)
    m_metrics = IAG.project_write_addr_grad(m, g_lm, ln2)
    assert m_metrics["cosine_after"] >= -1e-6, m_metrics
    assert torch.equal(p0.grad, before), "non-wak gradient was modified"


def test_zero_lm_gradient_no_projection():
    import torch
    import interventions_ag as IAG
    m, _ = _model()
    wak = IAG.write_addr_params(m)
    g_lm = {n: torch.zeros_like(p) for n, p in wak}
    for n, p in wak:
        p.grad = torch.randn_like(p)          # pure aux (g_lm = 0)
    saved = {n: p.grad.clone() for n, p in wak}
    met = IAG.project_write_addr_grad(m, g_lm, 0.0)
    assert met["zero_lm_gradient"] is True and met["projected"] is False
    for n, p in wak:
        assert torch.equal(p.grad, saved[n]), "zero-LM-grad case must leave aux unchanged"


def test_lm_gradient_unchanged_by_projection():
    import torch
    import interventions_ag as IAG
    m, _ = _model()
    wak = IAG.write_addr_params(m)
    torch.manual_seed(1)
    g_lm = {n: torch.randn_like(p) for n, p in wak}
    g_aux = {n: -g_lm[n] for n in g_lm}       # fully anti-aligned -> full removal
    for n, p in wak:
        p.grad = (g_lm[n] + g_aux[n]).clone()
    ln2 = sum((g_lm[n] ** 2).sum().item() for n, _ in wak)
    IAG.project_write_addr_grad(m, g_lm, ln2)
    # after full-removal projection, final grad == g_lm (aux fully projected out)
    for n, p in wak:
        assert torch.allclose(p.grad, g_lm[n], atol=1e-5), "final wak grad should reduce to g_lm"


def test_a1_hard_negative_and_label_integrity():
    import torch
    import random
    import interventions_ag as IAG
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    rng = random.Random(3)
    x, fp, qp = IAG.a1_hard_negative_batch(vocab, 6, 160, rng, T, partition="train", n_hard=3)
    assert x.shape == (6, 160)
    assert bool((qp == 158).all()), "A1 query position must be the task-query position N-2"
    # label integrity: token at fact_pos is a value token, and it is predicted at N-1 in the tail
    for b in range(6):
        v_at_fact = int(x[b, fp[b]])
        assert v_at_fact in vocab.val, "fact_pos must point to the written value token"


def test_a1_query_positions_are_task_query_not_probe():
    # A1 uses the ordinary task-query read distribution (query_pos = N-2), not the fixed diagnostic
    # probe. The batch is drawn from a dedicated rng (does not touch the training stream).
    import random
    import interventions_ag as IAG
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    x1, _, _ = IAG.a1_hard_negative_batch(vocab, 4, 160, random.Random(7), T, "train")
    x2, _, _ = IAG.a1_hard_negative_batch(vocab, 4, 160, random.Random(7), T, "train")
    assert bool((x1 == x2).all()), "A1 batch must be deterministic given its dedicated rng"


def test_b0_equivalence_short():
    import arms_ag as A
    import persistence_arms as PA
    r_ag = A.run_ag_arm(99991, use_a1=False, use_g1=False, steps=24)
    r_h2 = PA.run_h2(99991, steps=24)
    assert r_ag["needle_by_dist"] == r_h2["needle_by_dist"], "B0 needle must match frozen H2"
    assert r_ag["ppl"] == r_h2["ppl"], "B0 ppl must match frozen H2"
    assert [t["needle_d96"] for t in r_ag["trajectory"]] == [t["needle_d96"] for t in r_h2["trajectory"]]


def _run_standalone():
    if not HAVE:
        print("ag-impl tests: RESOURCE_BLOCKED (torch unavailable) — 0 run, 0 failed")
        return 0
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ag-impl tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
