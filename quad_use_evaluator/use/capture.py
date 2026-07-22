"""Read-only capture of a completed inference's internal representations.

Forward hooks record intermediate tensors during the model's *ordinary* forward pass and return
``None`` everywhere, so they never alter attention, logits, probabilities, retrieval, decoding,
the KV path, or any activation. Inference is exactly what it is today; USE only reads the frozen
tensors afterwards.

Captured per forward pass (all detached):
    block_in[L]   residual stream entering block L   [B,N,D]   (block_in[0] == token+pos emb)
    block_out[L]  residual stream leaving block L    [B,N,D]
    attn_out[L]   merged Quad attention output       [B,N,D]
    ff_out[L]     feed-forward output                [B,N,D]
    quad_score[L] causal Quad score S^Q              [B,H,N,N]
    final_hidden  last block output                  [B,N,D]
    logits        output logits                      [B,N,V]

Per-head Quad-retrieval outputs and value vectors are recomputed read-only in ``channels.py``
from ``block_in[L]`` and the (frozen) attention module — using the model's own weights without
running or modifying the model.
"""

from __future__ import annotations

from typing import Dict, List

import torch

from . import _qgr_path  # noqa: F401
from qgr.quad_model import QuadTransformer, QuadConfig, QuadBlock, QuadAttention, FeedForward


class Capture:
    """Context manager registering read-only forward hooks on a frozen QuadTransformer."""

    def __init__(self, model: QuadTransformer):
        self.model = model
        self.handles = []
        self.store: Dict[str, object] = {}

    def _attn_hook(self, L):
        def hook(module, inp, out):
            o, score = out
            self.store.setdefault("attn_out", {})[L] = o.detach()
            self.store.setdefault("quad_score", {})[L] = score.detach()
            return None
        return hook

    def _ff_hook(self, L):
        def hook(module, inp, out):
            self.store.setdefault("ff_out", {})[L] = out.detach()
            return None
        return hook

    def _block_pre(self, L):
        def hook(module, args):
            self.store.setdefault("block_in", {})[L] = args[0].detach()
            return None
        return hook

    def _block_post(self, L):
        def hook(module, inp, out):
            x_out = out[0] if isinstance(out, tuple) else out
            self.store.setdefault("block_out", {})[L] = x_out.detach()
            return None
        return hook

    def __enter__(self):
        for L, block in enumerate(self.model.blocks):
            self.handles.append(block.register_forward_pre_hook(self._block_pre(L)))
            self.handles.append(block.register_forward_hook(self._block_post(L)))
            self.handles.append(block.attn.register_forward_hook(self._attn_hook(L)))
            self.handles.append(block.ff.register_forward_hook(self._ff_hook(L)))
        return self

    def __exit__(self, *a):
        for h in self.handles:
            h.remove()
        self.handles = []


@torch.no_grad()
def run_inference(model: QuadTransformer, tokens: torch.Tensor) -> Dict:
    """Run the model's ordinary forward pass and return frozen internal states + outputs.

    Nothing here changes the computation: hooks only read. Returns a dict with the captured
    tensors, plus 'logits', 'probs', 'pred' (argmax), and the number of layers/heads.
    """
    model.eval()
    with Capture(model) as cap:
        out = model(tokens)
    logits = out["logits"].detach()
    probs = torch.softmax(logits, dim=-1)
    rec = {
        "block_in": cap.store.get("block_in", {}),
        "block_out": cap.store.get("block_out", {}),
        "attn_out": cap.store.get("attn_out", {}),
        "ff_out": cap.store.get("ff_out", {}),
        "quad_score": cap.store.get("quad_score", {}),
        "logits": logits, "probs": probs, "pred": logits.argmax(-1),
        "num_layers": len(model.blocks), "num_heads": model.cfg.num_heads,
        "final_hidden": cap.store.get("block_out", {}).get(len(model.blocks) - 1),
    }
    return rec
