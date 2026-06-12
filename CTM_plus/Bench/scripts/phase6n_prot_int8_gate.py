#!/usr/bin/env python3
# Phase 6N — prot-int8 A/B gate (design doc gate 3/4): 6-prompt greedy
# bit-exactness of the flag-ON build vs the flag-OFF build, with an
# activation guard so a silent bf16 fallback can never fake a PASS.
#
# Methodology mirrors bench_8bit_kv_gate's bitexact cell (same 6 prompts,
# greedy, identical-count + common-prefix overlap%). The needle + sidecar
# bytes halves of the gate run through deploy/_savings_probe.py with the
# env flag toggled (see PHASE6N_PROT_INT8_DESIGN.md gate checklist).
#
# Usage (pod):
#   M=NousResearch/Meta-Llama-3.1-8B-Instruct
#   export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt   # v2 artifact (recalibrated)
#   python Bench/scripts/phase6n_prot_int8_gate.py --cell off --model $M --out /tmp/p6n_off.json
#   python Bench/scripts/phase6n_prot_int8_gate.py --cell on  --model $M --out /tmp/p6n_on.json
#   python Bench/scripts/phase6n_prot_int8_gate.py --compare /tmp/p6n_off.json /tmp/p6n_on.json
#   python Bench/scripts/phase6n_prot_int8_gate.py --selftest      # CPU
#
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
for _r in (Path("/workspace/symbolu/CTM_plus"), _SCRIPTS.parent.parent):
    if (_r / "KVPolicy").is_dir() and str(_r / "KVPolicy") not in sys.path:
        sys.path.insert(0, str(_r / "KVPolicy"))
        break

_PROT_INT8_ENV = "INT4_PROTECTED_PROT_INT8"


def _prot_int8_layer_counts(llm):
    """(active, total) prot-int8 writers on the live engine. The ON cell
    must show active == total — flag set but a pre-v2 artifact silently
    falls back to bf16, and an OFF-vs-fallback compare would trivially
    bit-match (a fake PASS). Refuse instead."""
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    model = llm.llm_engine.model_executor.driver_worker.model_runner.model
    active = total = 0
    for _, sub in model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is None or not getattr(w, "_allocated", False):
            continue
        total += 1
        if getattr(w, "_prot_int8_active", False):
            active += 1
    return active, total


def check_cell_config(cell: str, active: int, total: int):
    """Pure (selftested): None if the cell's writer state matches its
    flag, else the refusal message."""
    if total <= 0:
        return f"cell={cell}: no allocated int4_protected writers found"
    if cell == "on" and active != total:
        return (f"cell=on: prot-int8 active on {active}/{total} layers — "
                f"the artifact at $PROTECT_MASK_PATH lacks k_min/k_max "
                f"(recalibrate) or the flag was lost; an OFF-vs-fallback "
                f"compare would be a fake PASS, refusing")
    if cell == "off" and active != 0:
        return (f"cell=off: prot-int8 active on {active}/{total} layers "
                f"despite the flag being unset — env leak, refusing")
    return None


def run_cell(args):
    # The flag must be resolved before the writers' first forward
    # (_lazy_alloc reads it once per writer) — set/clear it NOW.
    if args.cell == "on":
        os.environ[_PROT_INT8_ENV] = "1"
    else:
        os.environ.pop(_PROT_INT8_ENV, None)

    from bench_8bit_kv_gate import _BITEXACT_PROMPTS
    import kv_policy.int4_protected  # noqa: F401  (registers the backend)
    from kv_policy.int4_protected import Int4ProtectedLLM
    from vllm import SamplingParams

    llm = Int4ProtectedLLM(
        model=args.model,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_util,
        enforce_eager=True,            # determinism for the bitexact A/B
    )
    sp = SamplingParams(temperature=0.0, max_tokens=args.max_tokens)
    outs = llm.generate(list(_BITEXACT_PROMPTS), sp)
    outputs = {p: o.outputs[0].text for p, o in zip(_BITEXACT_PROMPTS, outs)}

    active, total = _prot_int8_layer_counts(llm)
    refusal = check_cell_config(args.cell, active, total)
    rep = {
        "cell": args.cell, "model": args.model,
        "max_model_len": args.max_model_len, "max_tokens": args.max_tokens,
        "prot_int8_layers": {"active": active, "total": total},
        "config_refusal": refusal,
        "outputs": outputs,
    }
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print(f"[p6n] cell={args.cell}: prot-int8 layers {active}/{total} "
          f"-> {args.out}")
    if refusal:
        print(f"[p6n] CONFIG REFUSAL: {refusal}")
        return 1
    return 0


def compare(off_path: str, on_path: str) -> int:
    from bench_8bit_kv_gate import common_prefix_pct
    a = json.loads(Path(off_path).read_text())
    b = json.loads(Path(on_path).read_text())
    print("\n" + "=" * 74)
    print("PHASE 6N PROT-INT8 GATE — 6-prompt greedy, flag ON vs flag OFF")
    print("=" * 74)
    for rep, want in ((a, "off"), (b, "on")):
        if rep.get("cell") != want:
            print(f"FAIL: {want}-cell file holds cell={rep.get('cell')!r}")
            return 1
        if rep.get("config_refusal"):
            print(f"FAIL: {want}-cell was refused at run time: "
                  f"{rep['config_refusal']}")
            return 1
    la, lb = a["prot_int8_layers"], b["prot_int8_layers"]
    print(f"  off: prot-int8 {la['active']}/{la['total']} layers   "
          f"on: {lb['active']}/{lb['total']} layers")
    prompts = list(a["outputs"].keys())
    if set(prompts) != set(b["outputs"].keys()):
        print("FAIL: prompt sets differ between cells")
        return 1
    n_identical, overlaps = 0, []
    for i, p in enumerate(prompts):
        ta, tb = a["outputs"][p], b["outputs"][p]
        ident = (ta == tb)
        n_identical += int(ident)
        ov = common_prefix_pct(ta, tb)
        overlaps.append(ov)
        print(f"  [{i}] {'IDENTICAL' if ident else f'overlap {ov:5.1f}%':<16} "
              f"{p[:48]}")
    mean_ov = sum(overlaps) / len(overlaps)
    print("-" * 74)
    print(f"  identical: {n_identical}/{len(prompts)}   "
          f"mean prefix overlap: {mean_ov:.1f}%")
    # Same near bar as the brief's bitexact methodology (>=3/6 identical
    # OR mean overlap >= 80%). int4_protected itself scores 3/6 vs bf16;
    # ON vs OFF differ only by the protect int8 residual, so expect at
    # least as much agreement — paste these numbers either way.
    ok = (n_identical >= 3) or (mean_ov >= 80.0)
    print("P6N VERDICT:", "PASS — flag-ON greedy outputs are within the "
          "established near-bar of flag-OFF" if ok else
          "FAIL — ON vs OFF diverge beyond the near-bar (identical<3/6 "
          "and overlap<80%): do NOT enable the flag; investigate before "
          "re-running")
    print("=" * 74)
    return 0 if ok else 1


def selftest() -> int:
    import copy
    import tempfile
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    print("phase6n_prot_int8_gate selftest")
    from bench_8bit_kv_gate import common_prefix_pct  # import path works
    check("sibling import (bitexact helpers)",
          common_prefix_pct("abcd", "abXY") == 50.0)
    check("config: on-cell all active OK", check_cell_config("on", 32, 32) is None)
    check("config: on-cell fallback refused",
          "fake PASS" in (check_cell_config("on", 0, 32) or ""))
    check("config: on-cell partial refused",
          check_cell_config("on", 31, 32) is not None)
    check("config: off-cell clean OK", check_cell_config("off", 0, 32) is None)
    check("config: off-cell active refused",
          "env leak" in (check_cell_config("off", 32, 32) or ""))
    check("config: no writers refused", check_cell_config("on", 0, 0) is not None)

    base = {
        "cell": "off", "model": "m", "max_model_len": 4096, "max_tokens": 64,
        "prot_int8_layers": {"active": 0, "total": 32},
        "config_refusal": None,
        "outputs": {f"p{i}": f"out{i} text" for i in range(6)},
    }
    on = copy.deepcopy(base)
    on["cell"] = "on"
    on["prot_int8_layers"] = {"active": 32, "total": 32}
    with tempfile.TemporaryDirectory() as td:
        pa, pb = str(Path(td) / "a.json"), str(Path(td) / "b.json")
        Path(pa).write_text(json.dumps(base))
        Path(pb).write_text(json.dumps(on))
        check("identical outputs PASS", compare(pa, pb) == 0)
        div = copy.deepcopy(on)
        div["outputs"] = {k: "ZZZ totally different"
                          for k in div["outputs"]}
        Path(pb).write_text(json.dumps(div))
        check("full divergence FAILS", compare(pa, pb) == 1)
        fb = copy.deepcopy(on)
        fb["prot_int8_layers"] = {"active": 0, "total": 32}
        fb["config_refusal"] = "cell=on: prot-int8 active on 0/32 layers"
        Path(pb).write_text(json.dumps(fb))
        check("fallback on-cell refused in compare", compare(pa, pb) == 1)
    print(f"\n{'ALL PASS' if not fails else f'{len(fails)} FAIL: ' + ', '.join(fails)}")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Phase 6N prot-int8 greedy A/B gate (flag ON vs OFF)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cell", choices=["off", "on"])
    ap.add_argument("--compare", nargs=2, metavar=("OFF_JSON", "ON_JSON"))
    ap.add_argument("--model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    ap.add_argument("--max-model-len", type=int, default=4096)
    ap.add_argument("--gpu-util", type=float, default=0.5)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--out", default="/tmp/p6n_cell.json")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.compare:
        return compare(*args.compare)
    if args.cell:
        return run_cell(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
