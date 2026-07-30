"""CPU unit test for analyze_kv_outliers — proves the go/no-go logic discriminates.

Synthesizes three KV distributions and checks the verdict flips correctly:
  A. text-like + visual-like BOTH concentrated, SAME outlier channels  -> GO
  B. visual DIFFUSE (no dominant channels)                              -> NO_GO_STRUCTURE
  C. both concentrated but visual outliers on DIFFERENT channels        -> mask does not transfer
No GPU, no model — validates the analysis math itself.
"""
from __future__ import annotations

import os
import sys
import tempfile

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_kv_outliers as A

H, D, S = 4, 128, 256
NPROT = max(1, int(0.04 * D))   # 5


def _concentrated(seed, outlier_channels, scale=25.0):
    """(S,H,D) with a few dominant channels at `outlier_channels` (per head)."""
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(S, H, D, generator=g)
    for h in range(H):
        x[:, h, outlier_channels] *= scale
    return x


def _diffuse(seed):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(S, H, D, generator=g)   # no dominant channels


def _write(vis, txt):
    tt = torch.cat([torch.ones(vis.shape[0]), torch.zeros(txt.shape[0])]).to(torch.int64)
    k = torch.cat([vis, txt], dim=0)
    p = os.path.join(tempfile.mkdtemp(), "kv.pt")
    torch.save({"k": k, "token_type": tt, "layer": 0}, p)
    return p


def _verdict(vis, txt):
    return A.run(_write(vis, txt), A.DEFAULT_GATES, None, None)["VERDICT"]


def test_go_when_visual_matches_text():
    ch = list(range(NPROT))                       # same outlier channels
    v = _verdict(_concentrated(1, ch), _concentrated(2, ch))
    assert v == "GO", v


def test_no_go_when_visual_diffuse():
    v = _verdict(_diffuse(3), _concentrated(4, list(range(NPROT))))
    assert v.startswith("NO_GO_STRUCTURE"), v


def test_mask_mismatch_when_outliers_differ():
    txt_ch = list(range(NPROT))                   # text outliers low channels
    vis_ch = list(range(D - NPROT, D))            # visual outliers high channels
    v = _verdict(_concentrated(5, vis_ch), _concentrated(6, txt_ch))
    # structure + protection present on visual, but mask won't transfer (low IoU);
    # union of two disjoint 4% sets = 8% <= 2x budget, so combined-mask path may rescue it.
    assert v in ("GO_BUT_MASK_DOES_NOT_TRANSFER (visual needs its own mask)",
                 "GO_WITH_COMBINED_MASK"), v


def test_protection_actually_helps_concentrated():
    ch = list(range(NPROT))
    _, mask = A.analyze_subset(_concentrated(7, ch), A.PROTECT_FRAC)
    m, _ = A.analyze_subset(_concentrated(7, ch), A.PROTECT_FRAC)
    assert m["protection_benefit_x"] > 1.3, m["protection_benefit_x"]
    assert m["concentration_ratio"] > 3.0, m["concentration_ratio"]


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
