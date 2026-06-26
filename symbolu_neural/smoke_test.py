"""Shape + gradient smoke test for the Symbol-U skeleton.

Run where torch is available:
    python -m symbolu_neural.smoke_test

It constructs each ablation rung on a DummyBackbone, runs a forward pass with
random ids, checks the documented output shapes, composes the available losses,
and verifies a backward pass produces gradients on the Symbol-U heads. It does
NOT train. Exit code 0 == all interface contracts hold.
"""
from __future__ import annotations

import sys

import torch

from .config import SymbolUConfig
from .backbone import BackboneWrapper
from .model import SymbolUModel
from .ablations import ABLATIONS
from . import losses


def run() -> int:
    B, L, d, V = 2, 16, 64, 256
    ids = torch.randint(0, V, (B, L))
    batch = {
        "target_ids": ids,
        "vritti_labels": torch.randint(0, 5, (B, L // 2)),
        "aspect_labels": torch.randint(0, 10, (B, L // 2)),
        "per_example_error": torch.rand(B),
        "safety_labels": torch.rand(B, 3),
    }
    ok = True
    for name, make in ABLATIONS.items():
        cfg: SymbolUConfig = make()
        cfg.d_model = d
        cfg.seg_stride = 2
        bb = BackboneWrapper.dummy(vocab_size=V, d_model=d)
        model = SymbolUModel(cfg, bb)
        model.train()
        aux = model(ids)
        assert aux["logits"].shape == (B, L, V), (name, aux["logits"].shape)
        if cfg.enable_typed_heads:
            assert aux["log_p_v"].shape == (B, L // 2, 5)
            assert aux["log_p_w"].shape == (B, 10)
        if cfg.enable_entropy:
            assert aux["H_D"].shape == (B,)
        loss = losses.total_loss(aux, batch)
        trainable = [p for p in model.parameters() if p.requires_grad]
        # backbone_only with a frozen backbone has no trainable params: that is
        # the expected floor (nothing to learn), so backward/grad is N/A there.
        if loss["total"].requires_grad and trainable:
            loss["total"].backward()
            has_grad = any(p.grad is not None for p in trainable)
            symbolu_modules = name != "backbone_only"
            ok = ok and (has_grad or not symbolu_modules)
            tag = "yes" if has_grad else "NONE"
        else:
            tag = "n/a (frozen floor)"
        print(f"[{name:22s}] forward OK  loss={loss['total'].item():.3f}  grad={tag}")
    print("SMOKE TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run())
