#!/usr/bin/env python3
# Phase 6K.16 — S1 BYTE-GATE (contract C-GATE / P1, PHASE6K16_APC_CONTRACT.md §6).
#
# Tests the APC machinery EXACTLY, decoupled from the int4-vs-bf16 quant
# residual: a cached block reused by APC must be BYTE-IDENTICAL (packed K +
# packed V nibbles + all five sidecars) to what a fresh no-APC prefill of the
# same tokens writes. Pass/fail is binary; a failing event names the exact
# block + field to inspect.
#
# HOW: both engines run the SAME warm prompt. The layer-0 writer dumps its
# first N finalized blocks (INT4_PROTECTED_DUMP_BLOCKS) — those are the prefix
# blocks, in the same deterministic order in both engines. Compare the dumps.
#
# Usage (pod, venv-vllm):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
#   python Bench/scripts/phase6k16_byte_gate.py --mode noapc --dump /tmp/s1_noapc.pt --model $M
#   python Bench/scripts/phase6k16_byte_gate.py --mode apc   --dump /tmp/s1_apc.pt   --model $M
#   python Bench/scripts/phase6k16_byte_gate.py --compare /tmp/s1_noapc.pt /tmp/s1_apc.pt
#   python Bench/scripts/phase6k16_byte_gate.py --selftest          # CPU

from __future__ import annotations

import argparse
import os
import sys
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

FIELDS = ("packed_k", "packed_v", "k_scale", "k_xmin", "k_protect",
          "v_scale", "v_xmin")


def run_mode(args):
    os.environ["INT4_PROTECTED_DUMP_BLOCKS"] = args.dump
    if args.mode == "apc":
        os.environ["INT4_PROTECTED_ALLOW_PREFIX_CACHING"] = "1"
        print("[s1] APC mode (Tier-1 path + contract refusals armed)")
    import kv_policy.int4_protected  # noqa: F401
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    # Same workload builder as the gates script => identical warm prompt.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from phase6k16_prefix_gates import build_workload
    prefix, code, _ = build_workload()

    llm = Int4ProtectedLLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_util,
        enable_prefix_caching=(args.mode == "apc"),
        enforce_eager=True,            # eager: deterministic, no capture noise
    )
    sp = SamplingParams(temperature=0.0, max_tokens=2)
    llm.generate([prefix + "Summarize the above in one sentence."], sp)
    import torch
    ev = torch.load(args.dump, weights_only=True) if Path(args.dump).exists() else []
    print(f"[s1] mode={args.mode} dumped {len(ev)} finalize events -> {args.dump}")
    return 0 if ev else 1


def compare(noapc_path, apc_path):
    import torch
    a = torch.load(noapc_path, weights_only=True)
    b = torch.load(apc_path, weights_only=True)
    n = min(len(a), len(b))
    print("\n" + "=" * 74)
    print(f"S1 BYTE-GATE — cached blocks vs fresh prefill ({n} events compared; "
          f"noapc={len(a)} apc={len(b)})")
    print("=" * 74)
    if n == 0:
        print("S1: n/a — no events captured (dump env not honored?)")
        return 1
    all_ok = True
    for i in range(n):
        bad = []
        for f in FIELDS:
            ta, tb = a[i][f], b[i][f]
            if ta.shape != tb.shape:
                bad.append(f"{f}(shape {tuple(ta.shape)}!={tuple(tb.shape)})")
                continue
            # bit-exact comparison via byte views (bf16-safe).
            if not torch.equal(ta.view(torch.uint8) if ta.dtype == torch.uint8
                               else ta.view(torch.int16) if ta.dtype == torch.bfloat16
                               else ta, tb.view(torch.uint8) if tb.dtype == torch.uint8
                               else tb.view(torch.int16) if tb.dtype == torch.bfloat16
                               else tb):
                nbad = int((ta != tb).sum())
                bad.append(f"{f}({nbad} elems differ)")
        status = "OK " if not bad else "FAIL"
        if bad:
            all_ok = False
        print(f"  event[{i:2d}] {status}" + ("" if not bad else "  " + ", ".join(bad)))
    print("-" * 74)
    print("S1 VERDICT:", "PASS — machinery byte-exact (P1 holds); any e2e gap "
          "is the bounded quant residual (S3)." if all_ok else
          "FAIL — a named block/field differs from fresh prefill; this is the "
          "machinery bug, independent of quant residual.")
    print("=" * 74)
    return 0 if all_ok else 1


def selftest():
    import torch
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6k16_byte_gate selftest")
    ev = [{f: torch.randint(0, 255, (4, 4), dtype=torch.uint8) for f in FIELDS}
          for _ in range(3)]
    import copy
    same = copy.deepcopy(ev)
    p1, p2 = "/tmp/_s1a.pt", "/tmp/_s1b.pt"
    torch.save(ev, p1)
    torch.save(same, p2)
    check("identical dumps PASS", compare(p1, p2) == 0)
    same[1]["k_scale"] = same[1]["k_scale"].clone()
    same[1]["k_scale"][0, 0] ^= 1
    torch.save(same, p2)
    check("1-byte diff FAILS", compare(p1, p2) == 1)
    # pad/refusal helpers (contract C-ID/B2) are importable + behave:
    from kv_policy.phase5b_4c_paged_writer import (
        is_pad_seq_id, _PAD_SEQ_ID_BASE, set_apc_active, apc_active,
    )
    check("pad sentinel detected", is_pad_seq_id(_PAD_SEQ_ID_BASE - 3))
    check("rid not pad", not is_pad_seq_id(0) and not is_pad_seq_id(7))
    set_apc_active(True)
    check("apc flag arms", apc_active())
    set_apc_active(False)
    check("apc flag disarms", not apc_active())
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="S1 byte-gate (APC contract)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mode", choices=["noapc", "apc"])
    ap.add_argument("--compare", nargs=2, metavar=("NOAPC", "APC"))
    ap.add_argument("--dump", default="/tmp/s1_dump.pt")
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare:
        return compare(*args.compare)
    if args.mode:
        return run_mode(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
