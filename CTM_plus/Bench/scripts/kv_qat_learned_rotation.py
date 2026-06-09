#!/usr/bin/env python3
# Learned-rotation probe — is K's anisotropy ROTATABLE? (the SpinQuant-style lever)
#
# THE QUESTION
#   int4_protected pays a ~3.4 GB sidecar tax because K needs PER-CHANNEL scales
#   (Qwen2.5 K is anisotropic; dropping them = 7.1x worse, kv_qat_scale_probe). The
#   one untested escape hatch is a LEARNED, data-dependent orthogonal rotation R that
#   makes K quantizable with a single PER-TENSOR scale -- deleting the tax. Random
#   rotation failed (7.1x); Hadamard+per-channel failed (+5%). Both are data-OBLIVIOUS.
#   A *learned* R is the only point that can adapt to where K's outliers live.
#
# WHAT THIS PROBE ANSWERS (cheaply, before any kernel/RoPE-fusion work)
#   Is K's anisotropy in the CHANNEL axis (rotatable -> a rotation can spread it so
#   per-tensor works) or in the ROW/spectral structure (NOT rotatable -- rotation only
#   relocates it; failure-mode #1)? It learns R by 4th-moment (kurtosis) minimization
#   on the Stiefel manifold (Cayley retraction), then measures whether per-tensor int4
#   in the rotated basis approaches per-channel. Output: a gap-closed % and a verdict.
#
# THREE FIXES vs the external write-ups (baked in)
#   1. FIRST MODEL = base Qwen2.5-7B (STANDARD rope), NOT Qwen-1M. Qwen-1M conflates
#      "are outliers rotatable" with "does it survive extreme rope" -- if it fails you
#      can't tell which. Standard rope is apples-to-apples with our 7.1x / +5% points.
#   2. We rotate POST-RoPE K (how the cache actually stores it) -- stated explicitly,
#      because where R sits vs RoPE decides feasibility AND kernel cost downstream.
#   3. The RECON screen here is a NECESSARY PRE-FILTER, not the gate. recon != downstream
#      (head-wise won recon, lost downstream). The GO/NO-GO is the HARD-TAIL downstream
#      eval (kv_qat_gen_eval / downstream_resolver) wired below -- run it if recon passes.
#
# Run:
#   python CTM_plus/Bench/scripts/kv_qat_learned_rotation.py --selftest         # CPU, math gates
#   # pod (venv-vllm), real K from Qwen2.5-7B post-RoPE:
#   PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_learned_rotation.py \
#       --model Qwen/Qwen2.5-7B-Instruct --layers 0,13,27 --tokens 4000
#
# numpy-only core (no torch) -> the optimizer + detector are tested here; only the K
# extraction needs the GPU.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------- #
# Quantizers (numpy) -- symmetric int4
# --------------------------------------------------------------------------- #
def _qmax(bits: int) -> int:
    return 2 ** (bits - 1) - 1            # 7 for 4-bit


def per_tensor_rt(X: np.ndarray, bits: int = 4) -> np.ndarray:
    """Round-trip quant with ONE scale for the whole tensor (the goal config)."""
    qm = _qmax(bits)
    s = np.abs(X).max() / qm
    return X.copy() if s == 0 else np.clip(np.round(X / s), -qm, qm) * s


def per_channel_rt(X: np.ndarray, bits: int = 4) -> np.ndarray:
    """Round-trip quant with a scale PER COLUMN (the current baseline analog --
    this is the metadata int4_protected pays ~3.4 GB to store)."""
    qm = _qmax(bits)
    s = np.abs(X).max(0, keepdims=True) / qm
    s = np.where(s == 0, 1.0, s)
    return np.clip(np.round(X / s), -qm, qm) * s


def rel_err(X: np.ndarray, Xh: np.ndarray) -> float:
    d = np.linalg.norm(X)
    return float(np.linalg.norm(X - Xh) / d) if d else 0.0


def pt_err_rotated(K: np.ndarray, R: np.ndarray, bits: int = 4) -> float:
    """Error of: rotate -> per-tensor quant -> dequant -> UN-rotate -> compare to K.
    (== per-tensor quant error measured in the rotated basis, since R is orthogonal.)"""
    return rel_err(K, per_tensor_rt(K @ R, bits) @ R.T)


# --------------------------------------------------------------------------- #
# Learned rotation: 4th-moment (kurtosis) minimization on the Stiefel manifold
#   Minimizing sum((K@R)^4) at fixed Frobenius norm (R orthogonal preserves it)
#   Gaussianizes / de-peaks the coordinates -> a single per-tensor scale fits better.
#   This is the data-DEPENDENT analog of the fixed Hadamard (which de-peaks data-
#   obliviously). The optimizer keeps R exactly orthogonal via a Cayley retraction.
# --------------------------------------------------------------------------- #
def _m4(KR: np.ndarray) -> float:
    return float((KR ** 4).sum())


def _m4_grad(K: np.ndarray, R: np.ndarray) -> np.ndarray:
    KR = K @ R
    return 4.0 * (K.T @ (KR ** 3))       # d/dR sum (K@R)^4


def cayley_descent(R: np.ndarray, G: np.ndarray, lr: float) -> np.ndarray:
    """One Cayley-retraction DESCENT step on the Stiefel manifold for min f, G=grad f.
    Keeps R orthogonal exactly (Cayley of a skew matrix is orthogonal)."""
    A = G @ R.T - R @ G.T                 # skew-symmetric tangent
    n = R.shape[0]
    I = np.eye(n)
    return np.linalg.solve(I - (lr / 2.0) * A, (I + (lr / 2.0) * A) @ R)


def learn_rotation(K: np.ndarray, *, iters: int = 300, lr: float = 0.02,
                   seed: int = 0):
    """Learn an orthogonal R that de-peaks K's coordinates. Returns (R, m4_before, m4_after).
    K is RMS-normalized for step-size stability (rotation is scale-free in direction)."""
    rng = np.random.default_rng(seed)
    D = K.shape[1]
    Kn = K / (np.sqrt((K ** 2).mean()) + 1e-9)
    R = np.linalg.qr(rng.standard_normal((D, D)))[0]
    m0 = _m4(Kn @ R)
    for _ in range(iters):
        R = cayley_descent(R, _m4_grad(Kn, R), lr)
    return R, m0, _m4(Kn @ R)


def hadamard(D: int) -> "np.ndarray | None":
    """Normalized Sylvester Hadamard if D is a power of 2 (128 is); else None.
    The data-OBLIVIOUS structured rotation (QuaRot's de-peaker) -- a comparison point."""
    if D & (D - 1) != 0:
        return None
    H = np.array([[1.0]])
    while H.shape[0] < D:
        H = np.block([[H, H], [H, -H]])
    return H / np.sqrt(D)


# --------------------------------------------------------------------------- #
# RoPE interaction (the crux). Why this probe rotates POST-RoPE K:
#   post-RoPE rotation by ANY orthogonal R, applied to BOTH Q and K, preserves the
#   attention dot product (R Rt = I cancels). PRE-RoPE rotation by a general dense R
#   does NOT -- it preserves attention only if R COMMUTES with RoPE (the same 2x2
#   rotation on every dim-pair). So a general learned R must go post-RoPE (an online
#   per-token matmul, NOT foldable into weights); only a RoPE-structured R can fold
#   pre-RoPE into Wq/Wk for free. (Tested in selftest below.)
# --------------------------------------------------------------------------- #
def _rope(x: np.ndarray, pos: np.ndarray, base: float = 10000.0) -> np.ndarray:
    """Minimal RoPE for the equivalence selftest. x:[T,D] row vectors."""
    T, D = x.shape
    inv = 1.0 / (base ** (np.arange(0, D, 2) / D))
    ang = np.outer(pos, inv)
    cos, sin = np.cos(ang), np.sin(ang)
    o = np.empty_like(x)
    x0, x1 = x[:, 0::2], x[:, 1::2]
    o[:, 0::2] = x0 * cos - x1 * sin
    o[:, 1::2] = x1 * cos + x0 * sin
    return o


def _rope_commuting_R(D: int, seed: int = 2) -> np.ndarray:
    """An R that commutes with RoPE: identical 2x2 rotation on every dim-pair."""
    th = np.random.default_rng(seed).uniform(0, 2 * np.pi)
    c, s = np.cos(th), np.sin(th)
    R = np.eye(D)
    for i in range(0, D, 2):
        R[i, i], R[i, i + 1], R[i + 1, i], R[i + 1, i + 1] = c, -s, s, c
    return R


def rope_equivalence_diffs(D: int = 64, T: int = 8, seed: int = 0):
    """Return max|attn diff vs standard RoPE| for the three rotation placements."""
    rng = np.random.default_rng(seed)
    Q, K = rng.standard_normal((T, D)), rng.standard_normal((T, D))
    pos = np.arange(T)
    Rg = np.linalg.qr(rng.standard_normal((D, D)))[0]      # general dense (learned-like)
    Rc = _rope_commuting_R(D, seed + 1)                    # RoPE-structured
    base = _rope(Q, pos) @ _rope(K, pos).T
    post = (_rope(Q, pos) @ Rg) @ (_rope(K, pos) @ Rg).T   # post-RoPE, general R
    pre_g = _rope(Q @ Rg, pos) @ _rope(K @ Rg, pos).T      # pre-RoPE, general R
    pre_c = _rope(Q @ Rc, pos) @ _rope(K @ Rc, pos).T      # pre-RoPE, commuting R
    f = lambda m: float(np.abs(m - base).max())
    return {"post_general": f(post), "pre_general": f(pre_g), "pre_commuting": f(pre_c)}


# --------------------------------------------------------------------------- #
# Compare schemes on a K matrix [tokens, head_dim] + a rotatability verdict
# --------------------------------------------------------------------------- #
def compare_schemes(K: np.ndarray, bits: int = 4, seed: int = 0) -> dict:
    D = K.shape[1]
    rng = np.random.default_rng(seed)
    Rr = np.linalg.qr(rng.standard_normal((D, D)))[0]
    Rl, m0, m1 = learn_rotation(K, seed=seed)
    Hd = hadamard(D)
    out = {
        "per_channel":  rel_err(K, per_channel_rt(K, bits)),   # the baseline we want to drop
        "unrotated_pt": rel_err(K, per_tensor_rt(K, bits)),    # naive per-tensor (no rotation)
        "random_pt":    pt_err_rotated(K, Rr, bits),           # our measured 7.1x family
        "learned_pt":   pt_err_rotated(K, Rl, bits),           # THE lever
        "hadamard_pt":  (pt_err_rotated(K, Hd, bits) if Hd is not None else None),
        "m4_before": m0, "m4_after": m1, "m4_descended": m1 < m0,
        "ortho_resid": float(np.linalg.norm(Rl.T @ Rl - np.eye(D))),
    }
    out["verdict"] = rotatability_verdict(out)
    return out


def rotatability_verdict(s: dict) -> dict:
    """How much of the per-tensor->per-channel gap did learned rotation close?
    >70% rotatable; 30-70% partial; <30% not rotatable (anisotropy is row/spectral)."""
    gap = s["unrotated_pt"] - s["per_channel"]
    closed = (s["unrotated_pt"] - s["learned_pt"]) / gap if abs(gap) > 1e-9 else 0.0
    label = ("rotatable" if closed >= 0.70 else
             "partial"   if closed >= 0.30 else
             "not_rotatable")
    return {"gap_closed_frac": round(float(closed), 3), "label": label,
            "learned_matches_per_channel": bool(s["learned_pt"] <= s["per_channel"] * 1.05)}


# --------------------------------------------------------------------------- #
# Downstream hook (the REAL gate) -- provided for the hard-regime eval to call.
# --------------------------------------------------------------------------- #
def rotated_per_tensor_round_trip(K: np.ndarray, R: np.ndarray, bits: int = 4) -> np.ndarray:
    """The candidate replacement for round_trip_kv's per-channel K path:
    rotate -> per-tensor int4 -> dequant -> un-rotate. Feed this (and the matching
    Q-rotation) into kv_qat_gen_eval / downstream_resolver for the HARD-TAIL gate.
    NOTE: in serving you store K@R int4 and rotate Q by R too (QK^T preserved), so
    no un-rotate is needed online; the un-rotate here is only to score reconstruction."""
    return per_tensor_rt(K @ R, bits) @ R.T


# --------------------------------------------------------------------------- #
# GPU/pod mode: extract POST-RoPE K from the real model, run the recon screen.
# --------------------------------------------------------------------------- #
def run_gpu(args) -> int:
    # HF/system-python path (NO vLLM): transformers + the pure-torch round-trip,
    # like kv_qat_gen_eval. Run in the same env as the other KV-QAT scripts.
    import torch
    sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "KVPolicy"))
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from kv_policy.kv_aware_qat import rotary_module

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model)
    # .to(dev) (not device_map=) so we don't require `accelerate` -- matches the gate.
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.float16).to(dev).eval()
    layers = [int(x) for x in args.layers.split(",") if x.strip()]
    captured: dict = {}

    rmod = rotary_module(model)
    orig = rmod.apply_rotary_pos_emb

    def wrap(q, k, cos, sin, *a, **kw):
        q2, k2 = orig(q, k, cos, sin, *a, **kw)
        # k2: [B, n_kv_heads, T, D] post-RoPE. Stash per call; we slice layers after.
        captured.setdefault("k", []).append(k2.detach().float().cpu().numpy())
        return q2, k2
    rmod.apply_rotary_pos_emb = wrap

    text = ("The quick brown fox jumps over the lazy dog. " * 200)
    ids = tok(text, return_tensors="pt", truncation=True,
              max_length=args.tokens).input_ids.to(dev)
    with torch.no_grad():
        model(ids)
    rmod.apply_rotary_pos_emb = orig

    ks = captured.get("k", [])
    if not ks:
        print("FAIL: no post-RoPE K captured (apply_rotary_pos_emb not hit)")
        return 2
    # ks is one entry per attention layer call (in order). Pick requested layers.
    results = {}
    for li in layers:
        if li >= len(ks):
            continue
        kl = ks[li]                       # [B, H, T, D]
        B, H, T, D = kl.shape
        # aggregate heads: probe per-head, report the median head (honest middle)
        per_head = [compare_schemes(kl[0, h].reshape(T, D), bits=args.bits, seed=1)
                    for h in range(H)]
        med = sorted(per_head, key=lambda s: s["verdict"]["gap_closed_frac"])[H // 2]
        results[f"layer{li}"] = {"D": D, "n_heads": H, "tokens": T, "median_head": med}
        v = med["verdict"]
        print(f"\nlayer {li}: D={D} heads={H} tok={T}")
        print(f"  per_channel   {med['per_channel']:.4f}   (the ~3.4GB baseline to beat)")
        print(f"  unrotated_pt  {med['unrotated_pt']:.4f}")
        print(f"  random_pt     {med['random_pt']:.4f}   (our measured 7.1x family)")
        print(f"  hadamard_pt   {med['hadamard_pt']}")
        print(f"  learned_pt    {med['learned_pt']:.4f}   <-- the lever")
        print(f"  VERDICT: {v['label']}  (gap closed {v['gap_closed_frac']*100:.0f}%, "
              f"matches per-channel: {v['learned_matches_per_channel']})")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": args.model, "bits": args.bits,
                               "results": results}, indent=2, default=float))
    print(f"\nwrote {out}")
    print("\nRECON SCREEN ONLY. If labels are 'rotatable' (gap >70%) on the K-heavy "
          "layers, proceed to the HARD-TAIL downstream gate (see runbook); recon != "
          "downstream, so do NOT ship on this alone.")
    return 0


# --------------------------------------------------------------------------- #
# Selftest (CPU): the optimizer + the rotatability detector
# --------------------------------------------------------------------------- #
def selftest() -> int:
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("kv_qat_learned_rotation selftest")
    rng = np.random.default_rng(1)
    N, D = 2000, 16

    # ROTATABLE: channel-axis anisotropy (a few high-variance CHANNELS).
    cs = np.ones(D); cs[0] = 10.0; cs[1] = 6.0
    K_chan = rng.standard_normal((N, D)) * cs
    s_chan = compare_schemes(K_chan, seed=1)

    # NOT ROTATABLE: row/token anisotropy (a few huge-norm ROWS), channels balanced.
    K_row = rng.standard_normal((N, D)); K_row[:20] *= 15.0
    s_row = compare_schemes(K_row, seed=1)

    check("Cayley keeps R orthogonal (||RtR-I|| < 1e-6)",
          s_chan["ortho_resid"] < 1e-6 and s_row["ortho_resid"] < 1e-6)
    check("4th-moment objective DESCENDS (optimizer works)",
          s_chan["m4_descended"] and s_row["m4_descended"])
    check("CHANNEL-aniso is detected ROTATABLE (learned beats random AND unrotated)",
          s_chan["learned_pt"] < s_chan["random_pt"]
          and s_chan["learned_pt"] < s_chan["unrotated_pt"]
          and s_chan["verdict"]["gap_closed_frac"] >= 0.30)
    check("ROW-aniso is detected NOT rotatable (learned ~ unrotated)",
          s_row["verdict"]["label"] == "not_rotatable"
          and abs(s_row["learned_pt"] - s_row["unrotated_pt"]) / s_row["unrotated_pt"] < 0.05)
    # Honest: even rotatable doesn't fully reach per-channel here -> recon screen, not a ship gate.
    check("learned does NOT fully match per-channel on synthetic (recon != ship gate)",
          not s_chan["verdict"]["learned_matches_per_channel"])
    # Hadamard available at D=128 (the real head dim) and is a valid orthogonal de-peaker.
    Hd = hadamard(128)
    check("Hadamard(128) built and orthogonal",
          Hd is not None and np.linalg.norm(Hd.T @ Hd - np.eye(128)) < 1e-9)
    # Round-trip identity at high bits (quantizer sanity).
    X = rng.standard_normal((100, 8))
    check("per-tensor RT ~ identity at 12-bit", rel_err(X, per_tensor_rt(X, 12)) < 0.02)

    # RoPE interaction (the crux): post-RoPE rotation (any R) preserves attention;
    # pre-RoPE by a GENERAL R breaks it; only a RoPE-COMMUTING R works pre-RoPE.
    # (Corrects the external claim that "pre-RoPE rotation also works" for general R.)
    rd = rope_equivalence_diffs(D=64, T=8, seed=0)
    check("post-RoPE rotation (any R) preserves attention", rd["post_general"] < 1e-9)
    check("pre-RoPE rotation by a GENERAL R BREAKS attention (>> 0)", rd["pre_general"] > 1e-3)
    check("pre-RoPE works ONLY for a RoPE-commuting R", rd["pre_commuting"] < 1e-9)

    print(f"\n  CHANNEL-aniso: {s_chan['verdict']}")
    print(f"  ROW-aniso    : {s_row['verdict']}")
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Learned-rotation rotatability probe for K")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct",
                    help="STANDARD-rope model (apples-to-apples with the 7.1x/+5% points)")
    ap.add_argument("--layers", default="0,13,27")
    ap.add_argument("--tokens", type=int, default=4000)
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--out", default="bench_out/learned_rotation/probe.json")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return run_gpu(args)


if __name__ == "__main__":
    raise SystemExit(main())
