"""CPU byte-equivalence tests for Phase 6F int4 read-path dequant-prep.

Scope: validates the **numerics** of the read-path gather+splice+dequant-prep — the fused variant
is byte-equal to the staged reference, and both invert the writer's pack/quantize convention. This
is the CPU oracle for the GPU kernel; it does NOT measure throughput (the decode-recovery speedup is
PROJECTED ≤~0.30×, never parity, and is pod-only). Needs torch (CPU is fine); skips if absent.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

try:
    import torch
    _HAS_TORCH = True
except Exception:  # noqa: BLE001
    _HAS_TORCH = False

if _HAS_TORCH:
    from kv_policy import phase6f_read_fusion as p6f


def _make_view(B=2, n_blocks=3, H=2, D=8, BS=4, n_protect=2, v_n_groups=2, seed=0):
    """Synthetic get_packed_view_batched-shaped dict with self-consistent K codes/scale/xmin."""
    g = torch.Generator().manual_seed(seed)
    S = n_blocks * BS
    dt = torch.bfloat16

    # Build K block-by-block via the production quantizer so codes<->scale/xmin are consistent.
    k_codes = torch.empty((B, S, H, D), dtype=torch.uint8)
    k_scale = torch.empty((B, n_blocks, H, D), dtype=dt)
    k_xmin = torch.empty((B, n_blocks, H, D), dtype=dt)
    for b in range(B):
        for blk in range(n_blocks):
            x = torch.randn((BS, H, D), generator=g)
            codes, scale, xmin = p6f.quantize_k_block(x)
            k_codes[b, blk * BS:(blk + 1) * BS] = codes
            k_scale[b, blk] = scale.to(dt)
            k_xmin[b, blk] = xmin.to(dt)
    k_int4 = p6f.pack_nibbles(k_codes)

    # protect_slot: assign a couple of channels to protect slots, rest -1.
    protect_slot = torch.full((H, D), -1, dtype=torch.int8)
    protect_slot[0, 1] = 0
    if n_protect > 1:
        protect_slot[H - 1, D - 1] = 1
    k_protect_bf16 = torch.randn((B, S, H, n_protect), generator=g).to(dt)

    v_codes = torch.randint(0, 16, (B, S, H, D), generator=g, dtype=torch.int32).to(torch.uint8)
    v_int4 = p6f.pack_nibbles(v_codes)
    v_scale = torch.randn((B, S, H, v_n_groups), generator=g).to(dt)
    v_xmin = torch.randn((B, S, H, v_n_groups), generator=g).to(dt)

    view = {
        "k_int4": k_int4, "k_scale": k_scale, "k_xmin": k_xmin,
        "k_protect_bf16": k_protect_bf16, "protect_slot": protect_slot, "n_protect": n_protect,
        "v_int4": v_int4, "v_scale": v_scale, "v_xmin": v_xmin, "v_group_size": D // v_n_groups,
        "group_size": BS, "n_blocks_max": n_blocks, "S": S,
    }
    return view, dict(k_codes=k_codes, v_codes=v_codes, BS=BS, D=D)


@unittest.skipUnless(_HAS_TORCH, "torch required")
class TestNibbleCodec(unittest.TestCase):
    def test_pack_unpack_roundtrip(self):
        g = torch.Generator().manual_seed(1)
        codes = torch.randint(0, 16, (5, 8), generator=g, dtype=torch.int32).to(torch.uint8)
        packed = p6f.pack_nibbles(codes)
        self.assertEqual(packed.shape[-1], 8 // 2)
        back = p6f.unpack_nibbles(packed, 8)
        self.assertTrue(torch.equal(codes, back))

    def test_even_channel_is_low_nibble(self):
        # Matches the writer: byte j = code[2j] | code[2j+1]<<4.
        codes = torch.tensor([[3, 12]], dtype=torch.uint8)   # (1,2)
        packed = p6f.pack_nibbles(codes)
        self.assertEqual(int(packed[0, 0]), 3 | (12 << 4))

    def test_unpack_rejects_odd_D(self):
        with self.assertRaises(ValueError):
            p6f.unpack_nibbles(torch.zeros((2, 3), dtype=torch.uint8), 7)


@unittest.skipUnless(_HAS_TORCH, "torch required")
class TestDequantNumerics(unittest.TestCase):
    def test_quantize_dequant_bounded_error(self):
        # 4-bit asymmetric: reconstruction error per element <= one step (scale).
        g = torch.Generator().manual_seed(2)
        x = torch.randn((4, 2, 8), generator=g)             # (BS,H,D)
        codes, scale, xmin = p6f.quantize_k_block(x)
        recon = codes.float() * scale.unsqueeze(0) + xmin.unsqueeze(0)
        err = (recon - x).abs()
        self.assertTrue(torch.all(err <= scale.unsqueeze(0) + 1e-5))

    def test_protect_overlay_exact(self):
        view, meta = _make_view(seed=3)
        k = p6f.dequant_k_reference(meta["k_codes"], view["k_scale"], view["k_xmin"],
                                    view["k_protect_bf16"], view["protect_slot"], meta["BS"])
        slot = view["protect_slot"]
        # Protected channel (0,1)->slot 0 must equal the protect side-tensor exactly.
        self.assertTrue(torch.equal(k[:, :, 0, 1], view["k_protect_bf16"][:, :, 0, 0]))
        # An unprotected channel must equal the int4 dequant base (not the protect tensor).
        self.assertEqual(int(slot[0, 0]), -1)
        base00 = (meta["k_codes"][:, :, 0, 0].float()
                  * view["k_scale"].repeat_interleave(meta["BS"], 1)[:, :view["S"], 0, 0].float()
                  + view["k_xmin"].repeat_interleave(meta["BS"], 1)[:, :view["S"], 0, 0].float()
                  ).to(view["k_protect_bf16"].dtype)
        self.assertTrue(torch.equal(k[:, :, 0, 0], base00))


@unittest.skipUnless(_HAS_TORCH, "torch required")
class TestFusedEqualsReference(unittest.TestCase):
    def test_k_fused_byte_equal(self):
        for seed in (0, 1, 7):
            view, meta = _make_view(seed=seed)
            ref = p6f.dequant_k_reference(meta["k_codes"], view["k_scale"], view["k_xmin"],
                                          view["k_protect_bf16"], view["protect_slot"], meta["BS"])
            fused = p6f.dequant_k_fused(meta["k_codes"], view["k_scale"], view["k_xmin"],
                                        view["k_protect_bf16"], view["protect_slot"], meta["BS"])
            self.assertTrue(torch.equal(ref, fused), f"K mismatch seed={seed}")

    def test_k_fused_byte_equal_no_protect(self):
        view, meta = _make_view(seed=4)
        no_prot = torch.full_like(view["protect_slot"], -1)
        ref = p6f.dequant_k_reference(meta["k_codes"], view["k_scale"], view["k_xmin"],
                                      view["k_protect_bf16"], no_prot, meta["BS"])
        fused = p6f.dequant_k_fused(meta["k_codes"], view["k_scale"], view["k_xmin"],
                                    view["k_protect_bf16"], no_prot, meta["BS"])
        self.assertTrue(torch.equal(ref, fused))

    def test_v_fused_byte_equal(self):
        for seed in (0, 2, 9):
            view, meta = _make_view(seed=seed)
            ref = p6f.dequant_v_reference(meta["v_codes"], view["v_scale"], view["v_xmin"])
            fused = p6f.dequant_v_fused(meta["v_codes"], view["v_scale"], view["v_xmin"])
            self.assertTrue(torch.equal(ref, fused), f"V mismatch seed={seed}")

    def test_prep_fused_equals_reference(self):
        view, _ = _make_view(seed=5)
        a = p6f.fused_read_dequant_prep(view, fused=True)
        b = p6f.fused_read_dequant_prep(view, fused=False)
        self.assertTrue(torch.equal(a["k_bf16"], b["k_bf16"]))
        self.assertTrue(torch.equal(a["v_bf16"], b["v_bf16"]))
        self.assertEqual(tuple(a["k_bf16"].shape), (view["k_int4"].shape[0], view["S"],
                                                    view["k_int4"].shape[2], view["k_int4"].shape[3] * 2))


@unittest.skipUnless(_HAS_TORCH, "torch required")
class TestDispatchAndEnv(unittest.TestCase):
    def test_env_forces_reference(self):
        view, _ = _make_view(seed=6)
        old = os.environ.get(p6f._FUSED_READ_ENV)
        try:
            os.environ[p6f._FUSED_READ_ENV] = "0"
            self.assertFalse(p6f._fused_read_enabled())
            out = p6f.fused_read_dequant_prep(view)             # fused=None -> reads env (reference)
            ref = p6f.fused_read_dequant_prep(view, fused=False)
            self.assertTrue(torch.equal(out["k_bf16"], ref["k_bf16"]))
        finally:
            if old is None:
                os.environ.pop(p6f._FUSED_READ_ENV, None)
            else:
                os.environ[p6f._FUSED_READ_ENV] = old

    def test_dispatch_cpu_returns_bf16(self):
        view, _ = _make_view(seed=8)
        out = p6f.read_prep_dispatch(view, q_is_cuda=False)
        self.assertIn("k_bf16", out)
        # q_is_cuda=True with no Triton on this box must fall back to the host-fused prep.
        out2 = p6f.read_prep_dispatch(view, q_is_cuda=True)
        self.assertTrue("k_bf16" in out2 or out2.get("use_inline_kernel") is True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
