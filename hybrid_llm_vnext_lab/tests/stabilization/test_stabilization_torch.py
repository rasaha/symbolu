"""Torch-dependent tests for the intervention mechanics. Self-skips (RESOURCE_BLOCKED) when torch
is unavailable so the stdlib runner and CI do not fail. When torch is present these run for real."""
from __future__ import annotations

import pathlib
import random
import sys

LAB = pathlib.Path(__file__).resolve().parents[2]
EXP = LAB / "experiments" / "slot_formation_stabilization"
NEURAL = LAB / "experiments" / "neural_slots_only"
for p in (str(EXP), str(NEURAL)):
    sys.path.insert(0, p)

try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False

SKIP = "RESOURCE_BLOCKED: torch unavailable; skipping"


def _build():
    import torch
    import _nso
    MDL = _nso.models
    TA = _nso.tasks_adapter
    words, vocab, stream = TA.build_corpus()
    random.seed(3); torch.manual_seed(3)
    model, n, ff = MDL.build_matched("S", len(vocab), 2000000, d=128, h=4, layers=4,
                                     max_len=1200, window=64, num_slots=32)
    return model, vocab, stream, n, ff, TA


# ------------------------------------------------------------------ optimizer grouping
def test_param_groups_partition_exactly():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    model, *_ = _build()
    audit = IV.param_group_audit(model)
    assert audit["numel_reconciles"], "slot+nonslot numel must equal total"
    assert audit["no_duplicates"] and audit["no_omissions"]
    # every slot param name is inside a .mix.slots. module; none of the window/ffn params leak in
    for nm in audit["slot_param_names"]:
        assert ".mix.slots." in nm
        assert ".local." not in nm and ".ff." not in nm


def test_slot_group_contains_expected_components():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    model, *_ = _build()
    slot_named, _ = IV.split_param_groups(model)
    names = " ".join(n for n, _ in slot_named)
    for comp in ("slot_keys", "W_wk", "W_rq", "W_wv", "gate", "W_o", "norm"):
        assert comp in names, f"slot group missing {comp}"
    # 4 layers x 9 slot tensors = 36
    assert len(slot_named) == 36


def test_per_group_warmup_schedule_matches_arm():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    model, *_ = _build()
    opt, sched, warm = IV.build_optimizer_and_scheduler(
        model, nonslot_lr=2e-3, nonslot_warmup=60, slot_lr=1e-3, slot_warmup=180,
        weight_decay=0.01, steps=1200, grouped=True)
    assert warm == [60, 180]
    for _ in range(60):
        opt.step(); sched.step()
    lrs = [g["lr"] for g in opt.param_groups]
    assert abs(lrs[0] - 2e-3) < 1e-9, "non-slot warmup(60) should be complete"
    assert abs(lrs[1] - 1e-3 * 60 / 180) < 1e-6, "slot warmup(180) should be 1/3 ramped"


def test_ungrouped_is_single_group_like_frozen():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    model, *_ = _build()
    opt, sched, warm = IV.build_optimizer_and_scheduler(
        model, nonslot_lr=2e-3, nonslot_warmup=60, slot_lr=2e-3, slot_warmup=60,
        weight_decay=0.01, steps=1200, grouped=False)
    assert len(opt.param_groups) == 1 and warm == [60]


# ------------------------------------------------------------------ orthogonal init
def test_orthogonal_init_deterministic_and_shape_preserved():
    if not HAVE_TORCH:
        print(SKIP); return
    import torch
    import interventions as IV
    m1, *_ = _build()
    shp0 = [tuple(sm.slot_keys.shape) for sm in m1.slot_mixers()]
    dt0 = [sm.slot_keys.dtype for sm in m1.slot_mixers()]
    cnt0 = sum(p.numel() for p in m1.parameters())
    h1 = IV.orthogonal_slot_key_init(m1, 8)
    m2, *_ = _build()
    IV.orthogonal_slot_key_init(m2, 8)
    for a, b in zip(m1.slot_mixers(), m2.slot_mixers()):
        assert torch.allclose(a.slot_keys, b.slot_keys), "same seed must give identical keys"
    # different seed -> different keys
    m3, *_ = _build()
    IV.orthogonal_slot_key_init(m3, 9)
    assert not torch.allclose(m1.slot_mixers()[0].slot_keys, m3.slot_mixers()[0].slot_keys)
    # shape/dtype/count preserved; trainable
    assert [tuple(sm.slot_keys.shape) for sm in m1.slot_mixers()] == shp0
    assert [sm.slot_keys.dtype for sm in m1.slot_mixers()] == dt0
    assert sum(p.numel() for p in m1.parameters()) == cnt0
    assert all(sm.slot_keys.requires_grad for sm in m1.slot_mixers())


def test_orthogonal_init_off_diag_cosine_not_worse():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    m, *_ = _build()
    base = [IV.key_cosine_stats(sm.slot_keys) for sm in m.slot_mixers()]
    IV.orthogonal_slot_key_init(m, 8)
    new = [IV.key_cosine_stats(sm.slot_keys) for sm in m.slot_mixers()]
    for b, n in zip(base, new):
        # baseline is already orthogonal (~0); K1 must be <= baseline + tiny epsilon
        assert n["off_diag_cos_mean_abs"] <= b["off_diag_cos_mean_abs"] + 1e-5
        assert abs(n["row_norm_mean"] - 1.0) < 1e-4  # unit rows


# ------------------------------------------------------------------ curriculum
def test_curriculum_phase_boundaries_and_original_tail():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    model, vocab, stream, *_ , TA = _build()
    T = TA.T
    rng = random.Random(0)
    # phase 1: needle-only, all masks single-position
    _, _, m, ph = IV.curriculum_batch(0, stream, vocab, 16, 160, rng, T)
    assert ph == 1 and int(m.sum().item()) == 16  # one supervised pos per example
    _, _, _, ph2 = IV.curriculum_batch(299, stream, vocab, 16, 160, rng, T)
    assert ph2 == 1
    _, _, _, ph3 = IV.curriculum_batch(300, stream, vocab, 16, 160, rng, T)
    assert ph3 == 2
    _, _, _, ph4 = IV.curriculum_batch(699, stream, vocab, 16, 160, rng, T)
    assert ph4 == 2
    # phase 3 (>=700): original distribution (delegates to frozen train_batch)
    _, _, _, ph5 = IV.curriculum_batch(700, stream, vocab, 16, 160, rng, T)
    assert ph5 == 3
    _, _, _, ph6 = IV.curriculum_batch(1199, stream, vocab, 16, 160, rng, T)
    assert ph6 == 3


def test_curriculum_uses_frozen_tokenizer_corpus():
    if not HAVE_TORCH:
        print(SKIP); return
    _, vocab, stream, *_ = _build()
    assert len(vocab) == 1291 and len(stream) == 55547  # frozen tokenizer/corpus unchanged


# ------------------------------------------------------------------ alignment
def test_alignment_formula_and_bounded_shapes():
    if not HAVE_TORCH:
        print(SKIP); return
    import math
    import torch
    import interventions as IV
    model, vocab, stream, *_ , TA = _build()
    T = TA.T
    IV.install_capture_hooks(model)
    x, fp, qp = IV.aux_needle_batch(vocab, 8, 160, random.Random(1), T)
    la, ov = IV.alignment_loss(model, x, fp, qp)
    # L = -log(overlap + eps)
    assert abs(la.item() - (-math.log(ov + 1e-6))) < 1e-4
    # captured address vectors are bounded [B, M] — no N x N tensor
    for sm in model.slot_mixers():
        sm._sfs_capture = True
    _ = model(x)
    for sm in model.slot_mixers():
        assert sm._sfs_waddr.shape[-1] == 32  # M slots
        assert sm._sfs_waddr.dim() == 3        # [B, N, M], never [B, N, N]
        assert sm._sfs_waddr.shape[1] == 160   # N
        assert sm._sfs_waddr.shape[1] != sm._sfs_waddr.shape[2]  # N != M -> not a token-token matrix


def test_alignment_lambda_zero_after_600():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    assert IV.lambda_align(0) == 0.10
    assert IV.lambda_align(299) == 0.10
    assert abs(IV.lambda_align(450) - 0.05) < 1e-6
    assert IV.lambda_align(600) == 0.0
    for s in (601, 700, 900, 1199):
        assert IV.lambda_align(s) == 0.0


def test_alignment_no_answer_token_leakage():
    if not HAVE_TORCH:
        print(SKIP); return
    import torch
    import interventions as IV
    model, vocab, stream, *_ , TA = _build()
    T = TA.T
    IV.install_capture_hooks(model)
    x, fp, qp = IV.aux_needle_batch(vocab, 8, 160, random.Random(2), T)
    la1, _ = IV.alignment_loss(model, x, fp, qp)
    # mutate the answer (value) token at the query end; alignment loss must be UNCHANGED
    x2 = x.clone()
    x2[:, -1] = (x2[:, -1] + 1)  # change the target token only
    la2, _ = IV.alignment_loss(model, x2, fp, qp)
    assert abs(la1.item() - la2.item()) < 1e-6, "alignment must not depend on the answer token"


def test_hooks_do_not_change_inference_output():
    if not HAVE_TORCH:
        print(SKIP); return
    import torch
    import interventions as IV
    model, vocab, stream, *_ , TA = _build()
    x, _, _ = IV.aux_needle_batch(vocab, 4, 160, random.Random(3), TA.T)
    with torch.no_grad():
        y0 = model(x).clone()
    IV.install_capture_hooks(model)          # capture disabled by default
    with torch.no_grad():
        y1 = model(x)
    assert torch.allclose(y0, y1), "installing disabled capture hooks must not change forward output"


def test_param_count_unchanged_across_interventions():
    if not HAVE_TORCH:
        print(SKIP); return
    import interventions as IV
    base, *_ = _build()
    n_base = sum(p.numel() for p in base.parameters())
    k1, *_ = _build()
    IV.orthogonal_slot_key_init(k1, 3)
    assert sum(p.numel() for p in k1.parameters()) == n_base
    IV.install_capture_hooks(k1)
    assert sum(p.numel() for p in k1.parameters()) == n_base  # hooks add no params
