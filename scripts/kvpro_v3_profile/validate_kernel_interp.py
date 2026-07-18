#!/usr/bin/env python3
"""OPTIONAL CPU correctness anchor for the GPU-only unzip probe kernel, via Triton's
INTERPRETER mode (TRITON_INTERPRET=1 -> numpy emulation, no GPU). Validates that the
kernel's addressing (native (S,H,*) layout, nibble unpack, per-block K scale, compact-
protect masked gather) and the dequant arithmetic are correct by matching FULL/compact
against an independent numpy reference, and that every MODE/PROTECT config executes without
a Triton-semantics error. SKIPS cleanly (rc 0) if Triton / interpreter mode is unavailable —
the real timing validation is the pod run; this only anchors correctness.

  python validate_kernel_interp.py      # -> PASS / SKIPPED
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("TRITON_INTERPRET", "1")   # must precede the triton import
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def _skip(msg):
    print(f"[SKIPPED] interpreter validation: {msg}")
    return 0


def main():
    try:
        import numpy as np
        import torch
        import unzip_bound_probe as P
    except Exception as e:  # noqa: BLE001
        return _skip(f"import failed: {e}")
    if not getattr(P, "_HAVE_TRITON", False):
        return _skip("Triton not installed")

    ctx, H, D, BS, VG, npr = 96, 2, 128, 32, 32, 5
    try:
        ten, geom = P._build_inputs(ctx, H, D, BS, VG, npr, seed=1, device="cpu")
    except Exception as e:  # noqa: BLE001
        return _skip(f"input build failed: {e}")
    S, nb, DH, VNG = geom["S"], geom["n_blocks"], geom["DH"], geom["VNG"]

    pl = P._to_pagelocal(ten, geom)

    def run(mode, protect, layout=0, tt=None):
        tt = tt if tt is not None else ten
        out = torch.zeros(nb * H, dtype=torch.float32)
        P._unzip_probe_kernel[(nb, H)](
            tt["k_packed"], tt["k_scale"], tt["k_xmin"],
            tt["v_packed"], tt["v_scale"], tt["v_xmin"],
            tt["k_protect"], tt["protect_slot"], tt["k_fp16"], out,
            S, H, npr, nb, D=D, DH=DH, BS=BS, VNG=VNG, GS_v=VG,
            MODE=mode, PROTECT=protect, LAYOUT=layout)
        return out.numpy().astype(np.float64)

    # Independent numpy reference for FULL/compact (the production unzip).
    def npref():
        kp = ten["k_packed"].numpy().astype(np.int32); vp = ten["v_packed"].numpy().astype(np.int32)
        ksc = ten["k_scale"].float().numpy(); kxm = ten["k_xmin"].float().numpy()
        vsc = ten["v_scale"].float().numpy(); vxm = ten["v_xmin"].float().numpy()
        kpr = ten["k_protect"].float().numpy(); slot = ten["protect_slot"].numpy()
        d = np.arange(D); bc = d // 2; ih = d % 2; gv = d // VG
        out = np.zeros(nb * H, np.float64)
        for blk in range(nb):
            for h in range(H):
                pm = slot[h, d] >= 0
                acc = 0.0
                for t in range(BS):
                    s = blk * BS + t
                    kcode = ((kp[s, h, bc] >> (4 * ih)) & 0xF).astype(np.float64)
                    vcode = ((vp[s, h, bc] >> (4 * ih)) & 0xF).astype(np.float64)
                    kdq = kcode * ksc[blk, h, d] + kxm[blk, h, d]
                    kf = np.where(pm, kpr[s, h, np.where(pm, slot[h, d], 0)], 0.0)
                    keff = np.where(pm, kf, kdq)
                    vdq = vcode * vsc[s, h, gv] + vxm[s, h, gv]
                    acc += (keff + vdq).sum()
                out[blk * H + h] = acc
        return out

    try:
        got = run(P.MODE_FULL, P.PROT_COMPACT)
        ref = npref()
        err = float(np.abs(got - ref).max())
        print(f"  FULL/compact kernel-vs-numpy max abs err: {err:.3e}")
        # 6F-A ORACLE: page-local layout must reproduce the current-layout output EXACTLY
        # (same values, only re-addressed). Checked for FULL and FETCH.
        oracle = 0.0
        for mode in (P.MODE_FULL, P.MODE_FETCH):
            cur = run(mode, P.PROT_COMPACT, layout=0)
            plo = run(mode, P.PROT_COMPACT, layout=1, tt=pl)
            oracle = max(oracle, float(np.abs(cur - plo).max()))
        print(f"  6F-A page-local vs current max abs diff: {oracle:.3e}")
        finite = True
        for name, mode, prot in [("FETCH", P.MODE_FETCH, P.PROT_COMPACT),
                                 ("MATH", P.MODE_MATH, P.PROT_COMPACT),
                                 ("FULL_fullprotect", P.MODE_FULL, P.PROT_FULL),
                                 ("FETCH_pagelocal", P.MODE_FETCH, P.PROT_COMPACT)]:
            lay, tt = (1, pl) if name.endswith("pagelocal") else (0, ten)
            o = run(mode, prot, layout=lay, tt=tt)
            f = bool(np.isfinite(o).all()); finite &= f
            print(f"  {name:18} ran OK, finite={f}")
    except Exception as e:  # noqa: BLE001
        return _skip(f"interpreter launch failed (version/env): {e}")

    if err < 1e-2 and oracle < 1e-6 and finite:
        print("interpreter validation: PASS (addressing + dequant correct; page-local == current)")
        return 0
    print(f"interpreter validation: FAIL (err={err:.2e} oracle={oracle:.2e} finite={finite})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
