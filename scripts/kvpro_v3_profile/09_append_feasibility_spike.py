#!/usr/bin/env python3
"""KVPro V3 6F-A follow-on — active-partial-block APPEND feasibility spike.

The 6F-A page-local layout wins on READ by making a head's block contiguous. The cost it
risks is on the WRITE: in the current native (S,H,*) layout, appending one decode token writes
`(H, *)` CONTIGUOUS bytes (all heads of that token are adjacent); in the page-local
`(H, n_blocks, BS, *)` layout, the same token's heads land in H slots strided by
`n_blocks*BS*...` — a scattered write. This spike measures that write delta with CUDA events,
for the four cases the reviewer required:

  1. one-token append WITHOUT block repacking (a plain slot-write — no re-transpose needed);
  2. full-block rollover (crossing a BS boundary — also just a slot-write + the once-per-block
     K scale/xmin write);
  3. mixed tail lengths (per-sequence random block/offset — append cost must be fill-independent);
  4. saturation write cost (batch/concurrency sweep B in {1,32,128,256}).

Gate (frozen, DECISION_THRESHOLDS.md 6F-A): added per-step write cost must be < 25% of the
per-step READ gain (WRITE_COST_MAX). Because a token is WRITTEN once but READ every subsequent
decode step, the ratio is `ΔW_per_step / (B · ΔR_per_seq(L))` — amortised over the whole
context; it is reported at the decision context using the 6F-A read gain from the probe JSON.

POD-ONLY (needs a CUDA GPU). Writes label=UNAVAILABLE (never fabricated) if absent. Only the
STORE pattern differs between layouts (the quantise math is common-mode and cancels in ΔW), so
the spike stores pre-quantised payloads — it isolates exactly the layout-induced write penalty.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
WRITE_COST_MAX = 0.25          # frozen: added write < 25% of read gain

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore


def _alloc(B, S, H, D, BS, n_protect, v_group_size, layout, device):
    """Allocate the per-sequence cache buffers + a per-token payload in `layout`
    ('current' native (S,H,*) or 'pagelocal' (H,n_blocks,BS,*)). Pre-quantised dtypes."""
    DH = (D + 1) // 2
    VNG = D // v_group_size
    nb = (S + BS - 1) // BS
    u8 = lambda *sh: torch.zeros(sh, dtype=torch.uint8, device=device)
    bf = lambda *sh: torch.zeros(sh, dtype=torch.bfloat16, device=device)
    if layout == "current":
        buf = dict(k_packed=u8(B, S, H, DH), v_packed=u8(B, S, H, DH),
                   v_scale=bf(B, S, H, VNG), v_xmin=bf(B, S, H, VNG),
                   k_protect=bf(B, S, H, n_protect),
                   k_scale=bf(B, nb, H, D), k_xmin=bf(B, nb, H, D))
    else:
        buf = dict(k_packed=u8(B, H, nb, BS, DH), v_packed=u8(B, H, nb, BS, DH),
                   v_scale=bf(B, H, nb, BS, VNG), v_xmin=bf(B, H, nb, BS, VNG),
                   k_protect=bf(B, H, nb, BS, n_protect),
                   k_scale=bf(B, H, nb, D), k_xmin=bf(B, H, nb, D))
    pay = dict(k_packed=u8(B, H, DH), v_packed=u8(B, H, DH), v_scale=bf(B, H, VNG),
               v_xmin=bf(B, H, VNG), k_protect=bf(B, H, n_protect),
               k_scale=bf(B, H, D), k_xmin=bf(B, H, D))
    return buf, pay, dict(DH=DH, VNG=VNG, nb=nb)


def _append(buf, pay, blk, t, layout, roll):
    """One decode-step append of B tokens (one per sequence) into their active slot. `blk`,`t`
    are (B,) LongTensors (per-sequence block/offset). Writes only the per-token fields; on `roll`
    (a block boundary) also writes the once-per-block K scale/xmin. Slot-write only — NO repack."""
    b = torch.arange(blk.shape[0], device=blk.device)
    if layout == "current":
        s = blk * _BS + t                        # physical position (B,)
        buf["k_packed"][b, s] = pay["k_packed"]
        buf["v_packed"][b, s] = pay["v_packed"]
        buf["v_scale"][b, s] = pay["v_scale"]
        buf["v_xmin"][b, s] = pay["v_xmin"]
        buf["k_protect"][b, s] = pay["k_protect"]
        if roll:
            buf["k_scale"][b, blk] = pay["k_scale"]
            buf["k_xmin"][b, blk] = pay["k_xmin"]
    else:                                        # pagelocal: scattered across H
        buf["k_packed"][b, :, blk, t] = pay["k_packed"]
        buf["v_packed"][b, :, blk, t] = pay["v_packed"]
        buf["v_scale"][b, :, blk, t] = pay["v_scale"]
        buf["v_xmin"][b, :, blk, t] = pay["v_xmin"]
        buf["k_protect"][b, :, blk, t] = pay["k_protect"]
        if roll:
            buf["k_scale"][b, :, blk] = pay["k_scale"]
            buf["k_xmin"][b, :, blk] = pay["k_xmin"]


_BS = 32  # bound at runtime


def _time_ms(fn, iters):
    for _ in range(5):
        fn()
    torch.cuda.synchronize()
    s = torch.cuda.Event(True); e = torch.cuda.Event(True)
    s.record()
    for _ in range(iters):
        fn()
    e.record(); torch.cuda.synchronize()
    return s.elapsed_time(e) / iters


def run_spike(context_len, batches, iters, H, D, BS, v_group_size, n_protect, seed=0):
    global _BS
    _BS = BS
    torch.manual_seed(seed)
    S = ((context_len + BS - 1) // BS) * BS
    nb = S // BS
    dev = "cuda"
    out = {}
    for B in batches:
        buf_c, pay_c, g = _alloc(B, S, H, D, BS, n_protect, v_group_size, "current", dev)
        buf_p, pay_p, _ = _alloc(B, S, H, D, BS, n_protect, v_group_size, "pagelocal", dev)
        blk_mid = torch.full((B,), nb // 2, dtype=torch.long, device=dev)
        t_mid = torch.full((B,), BS // 2, dtype=torch.long, device=dev)
        t_roll = torch.zeros((B,), dtype=torch.long, device=dev)      # offset 0 => block start
        blk_mix = torch.randint(0, nb, (B,), device=dev)
        t_mix = torch.randint(0, BS, (B,), device=dev)
        cases = {
            "append_no_repack": (blk_mid, t_mid, False),
            "block_rollover":   (blk_mid, t_roll, True),
            "mixed_tail":       (blk_mix, t_mix, False),
        }
        rec = {}
        for name, (blk, t, roll) in cases.items():
            wc = _time_ms(lambda: _append(buf_c, pay_c, blk, t, "current", roll), iters)
            wp = _time_ms(lambda: _append(buf_p, pay_p, blk, t, "pagelocal", roll), iters)
            rec[name] = {"current_ms": round(wc, 6), "pagelocal_ms": round(wp, 6),
                         "added_write_ms": round(wp - wc, 6)}
        out[str(B)] = rec
        am = rec["append_no_repack"]
        print(f"  B={B:4} append: cur={am['current_ms']:.5f} pl={am['pagelocal_ms']:.5f} "
              f"Δ={am['added_write_ms']:+.5f}ms | rollover Δ={rec['block_rollover']['added_write_ms']:+.5f} "
              f"| mixed Δ={rec['mixed_tail']['added_write_ms']:+.5f}")
    return out, S


def evaluate_gate(spike, read_gain_ms, decision_batch):
    """ratio = ΔW_per_step / (B · ΔR_per_seq). read_gain_ms = per-sequence fetch gain
    (fetch_current - fetch_pagelocal) at the decision context from the probe. PASS if < 25%."""
    if read_gain_ms is None or read_gain_ms <= 0:
        return {"label": "INDETERMINATE",
                "reason": "no positive read gain from the probe (6F-A read gate must pass first)"}
    B = str(decision_batch)
    if B not in spike:
        B = sorted(spike, key=int)[-1]
    dW = spike[B]["append_no_repack"]["added_write_ms"]      # per-step, B tokens
    per_step_read_gain = int(B) * read_gain_ms
    ratio = dW / per_step_read_gain if per_step_read_gain > 0 else float("inf")
    return {"label": "MEASURED", "decision_batch": int(B),
            "added_write_ms_per_step": round(dW, 6),
            "read_gain_ms_per_seq": round(read_gain_ms, 6),
            "per_step_read_gain_ms": round(per_step_read_gain, 6),
            "write_over_read_ratio": round(ratio, 4),
            "gate_max": WRITE_COST_MAX,
            "gate_pass": bool(ratio < WRITE_COST_MAX),
            "note": "A token is written once but read every later step, so the write penalty amortises "
                    "over the context; the ratio is per-step and B-independent to first order."}


def _read_gain_from_probe(probe_path, decision_ctx=None):
    if not os.path.exists(probe_path):
        return None, None
    p = json.load(open(probe_path))
    per = p.get("per_ctx", {})
    if p.get("label") != "GPU-measured" or not per:
        return None, None
    dc = decision_ctx or sorted((int(k) for k in per), key=int)[-1]
    row = per.get(str(dc), {})
    fc, fp = row.get("fetch_only_ms"), row.get("fetch_pagelocal_ms")
    if isinstance(fc, (int, float)) and isinstance(fp, (int, float)):
        return fc - fp, dc
    return None, dc


def main(argv=None):
    ap = argparse.ArgumentParser(description="6F-A active-partial-block append feasibility spike")
    ap.add_argument("--context-len", type=int, default=32768)
    ap.add_argument("--batches", default="1 32 128 256")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--h-kv", type=int, default=4)
    ap.add_argument("--head-dim", type=int, default=128)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--v-group-size", type=int, default=32)
    ap.add_argument("--n-protect", type=int, default=5)
    ap.add_argument("--decision-batch", type=int, default=256)
    ap.add_argument("--probe", default=os.path.join(_HERE, "runs", "unzip_bound.json"))
    ap.add_argument("--out", default=os.path.join(_HERE, "runs", "append_spike.json"))
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    def bail(msg):
        json.dump({"label": "UNAVAILABLE", "error": msg, "per_batch": {}}, open(a.out, "w"), indent=2)
        print(f"[UNAVAILABLE] {msg} -> {a.out}")
        return 3

    if torch is None:
        return bail("torch import failed")
    if not torch.cuda.is_available():
        return bail("no CUDA GPU")
    batches = [int(b) for b in a.batches.split()]
    try:
        spike, S = run_spike(a.context_len, batches, a.iters, a.h_kv, a.head_dim, a.bs,
                             a.v_group_size, a.n_protect)
    except Exception as e:  # noqa: BLE001
        return bail(f"spike failed: {e}")
    read_gain, dc = _read_gain_from_probe(a.probe)
    gate = evaluate_gate(spike, read_gain, a.decision_batch)
    blob = {"label": "GPU-measured", "spike": "append_feasibility",
            "geom": {"H_kv": a.h_kv, "D": a.head_dim, "BS": a.bs, "context_len": a.context_len,
                     "S_padded": S, "n_protect": a.n_protect},
            "per_batch": spike, "read_gain_source_ctx": dc, "gate": gate,
            "note": "Only the STORE pattern differs by layout (quantise is common-mode). append_no_repack "
                    "is a plain slot-write (no re-transpose); rollover adds the once-per-block K scale write; "
                    "mixed_tail uses per-seq random block/offset. Gate: added write < 25% of read gain."}
    json.dump(blob, open(a.out, "w"), indent=2)
    print(f"\nGATE: added-write/read-gain = {gate.get('write_over_read_ratio', 'NA')} "
          f"(< {WRITE_COST_MAX} -> {gate.get('gate_pass', 'INDETERMINATE')}) [{gate['label']}]")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
