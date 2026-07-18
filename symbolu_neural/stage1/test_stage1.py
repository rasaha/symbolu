"""Fast CPU smoke checks for the Stage-1 grounding harness.

Run:  pytest symbolu_neural/stage1/test_stage1.py    (or)   python -m symbolu_neural.stage1.test_stage1

Covers: metrics sanity, backbone-frozen invariant, that the typed heads LEARN a
learnable surface signal above chance on synthetic data, that the global
shuffle-label control collapses to ~majority (kill-criteria bite), and that the
toy generator writes files + a synthetic meta.json.
"""
from __future__ import annotations

import os
import random
import tempfile

import torch
from torch.utils.data import DataLoader

from .data import GroundingDataset, make_collate
from .featurizer import ToyFeatureBackbone
from .model_stage1 import Stage1GroundingModel
from .make_toy_grounding_dataset import _gen_word, _label_names
from . import metrics


def _toy_rows(n, words, seed=0):
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        units = [rng.choice(words) for _ in range(rng.randint(4, 9))]
        rows.append({"units": units,
                     "vritti": [_label_names(u)["vritti"] for u in units],
                     "aspect": [_label_names(u)["aspect"] for u in units]})
    return rows


def _disjoint_vocab(seed=0, n=120):
    rng = random.Random(seed)
    s = set()
    while len(s) < n:
        s.add(_gen_word(rng))
    w = list(s)
    rng.shuffle(w)
    return w[: n // 2], w[n // 2:]


def _train(model, rows, heads, epochs, pool="sum", shuffle=False, lr=1e-2):
    from .data import GroundingDataset
    from .data import CharTokenizer
    ds = GroundingDataset(rows, CharTokenizer(), shuffle, seed=0)
    dl = DataLoader(ds, batch_size=16, shuffle=True, collate_fn=make_collate(pool))
    opt = torch.optim.Adam(model.head_parameters(), lr=lr)
    import torch.nn.functional as F
    from .labels import IGNORE
    for _ in range(epochs):
        for b in dl:
            out = model(b["input_ids"], b["attention_mask"], b["pool"])
            loss = sum(F.nll_loss(out[h].reshape(-1, out[h].shape[-1]),
                                  b["labels"][h].reshape(-1), ignore_index=IGNORE)
                       for h in heads)
            opt.zero_grad(); loss.backward(); opt.step()


def _val_acc(model, rows, head, pool="sum"):
    from .data import CharTokenizer
    ds = GroundingDataset(rows, CharTokenizer(), False, seed=0)
    dl = DataLoader(ds, batch_size=32, shuffle=False, collate_fn=make_collate(pool))
    lp, ys = [], []
    with torch.no_grad():
        for b in dl:
            o = model(b["input_ids"], b["attention_mask"], b["pool"])[head]
            lp.append(o.reshape(-1, o.shape[-1])); ys.append(b["labels"][head].reshape(-1))
    L = torch.cat(lp).unsqueeze(1); Y = torch.cat(ys).unsqueeze(1)
    return metrics.accuracy(L, Y), metrics.majority_baseline(Y)


def _model(seed=0):
    torch.manual_seed(seed)
    return Stage1GroundingModel(ToyFeatureBackbone(d_model=32, seed=seed), 32,
                                ["vritti", "aspect"])


def test_metrics_sane():
    logp = torch.log_softmax(torch.randn(50, 1, 5), dim=-1)
    y = torch.randint(0, 5, (50, 1))
    assert 0.0 <= metrics.accuracy(logp, y) <= 1.0
    assert 0.0 <= metrics.expected_calibration_error(logp, y) <= 1.0
    assert abs(metrics.chance_baseline(5) - 0.2) < 1e-9


def test_backbone_frozen():
    m = _model()
    m.assert_backbone_frozen()
    tr, _ = _disjoint_vocab()
    _train(m, _toy_rows(40, tr), ["vritti", "aspect"], epochs=1)
    assert m.backbone.embed.weight.grad is None  # no grad to backbone


def test_grounding_beats_shuffle_control():
    """The principled grounding test: real labels must beat a globally-shuffled
    control (same vocab/config) by a margin, AND clear chance. This compares
    signal vs. no-signal directly instead of relying on an absolute threshold."""
    tr, va = _disjoint_vocab()
    train_rows, val_rows = _toy_rows(160, tr), _toy_rows(80, va)

    m_real = _model()
    _train(m_real, train_rows, ["vritti", "aspect"], epochs=12, shuffle=False)
    acc_real, _ = _val_acc(m_real, val_rows, "vritti")

    m_ctrl = _model()
    _train(m_ctrl, train_rows, ["vritti", "aspect"], epochs=12, shuffle=True)
    acc_ctrl, maj = _val_acc(m_ctrl, val_rows, "vritti")

    assert acc_real > 0.30, f"real vritti acc {acc_real:.3f} not clearly above chance(0.20)"
    assert acc_real - acc_ctrl > 0.08, (
        f"real {acc_real:.3f} must beat shuffled control {acc_ctrl:.3f} by >0.08")
    assert acc_ctrl <= maj + 0.10, (
        f"shuffled control {acc_ctrl:.3f} should collapse to ~majority {maj:.3f}")


def test_generator_writes_synthetic_meta():
    import json
    from .make_toy_grounding_dataset import main as gen_main
    import sys
    with tempfile.TemporaryDirectory() as d:
        argv = sys.argv
        sys.argv = ["x", "--out-dir", d, "--n-train", "10", "--n-val", "5", "--vocab", "40"]
        try:
            gen_main()
        finally:
            sys.argv = argv
        assert os.path.exists(os.path.join(d, "train.jsonl"))
        meta = json.load(open(os.path.join(d, "meta.json")))
        assert meta["synthetic"] is True


def _run_all():
    fns = [test_metrics_sane, test_backbone_frozen, test_grounding_beats_shuffle_control,
           test_generator_writes_synthetic_meta]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print("ALL STAGE-1 SMOKE CHECKS PASSED")


if __name__ == "__main__":
    _run_all()
