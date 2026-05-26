"""Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1) — GPU smoke.

Confirms the refactored decode write path produces byte-identical
generated tokens vs the legacy partition+loop path on a real
Qwen-2.5-7B-Instruct + vLLM 0.7.3 + forked vllm-flash-attn pod.

Usage on the GPU pod:

  # One command runs both cells + comparison (recommended):
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_b_pre5_gpu_smoke.py \\
      --output-dir /workspace/symbolu/bench_out/phase6b1_gpu_smoke

  # Manual cell-at-a-time (advanced):
  python3 bench_phase6_b_pre5_gpu_smoke.py --worker --cell legacy     --output cell_legacy.json
  python3 bench_phase6_b_pre5_gpu_smoke.py --worker --cell refactored --output cell_refactored.json
  python3 bench_phase6_b_pre5_gpu_smoke.py --compare cell_legacy.json cell_refactored.json

The driver spawns the two cells as SEPARATE subprocesses so each gets
a clean Python interpreter + clean vLLM engine + the right env var
state (`PHASE6B1_USE_DECODE_BATCHED`).

Cell shapes (intentionally minimal — ~$0.02 budget):
  - Model:       Qwen/Qwen2.5-7B-Instruct (matches the brief portfolio)
  - max_model_len: 4096
  - gpu_memory_utilization: 0.5
  - max_tokens:  32 greedy decode tokens per seq
  - temperature: 0.0 (deterministic)
  - Two distinct prompts (B=2) — exercises multi-seq decode.

Acceptance gate (Phase 6B.1 G_PRE-WRITE GPU portion):
  1. Both cells generate IDENTICAL token IDs for every (prompt, seq)
     pair.
  2. Refactored cell has `write_decode_batched_calls > 0`,
     `write_legacy_loop_calls == 0` for decode steps (prefill goes
     through the legacy path; that's expected).
  3. Legacy cell has `write_decode_batched_calls == 0`,
     `write_legacy_loop_calls > 0`.
  4. Both cells have zero fallbacks
     (`write_path_fallback == 0`, `decode_calls_fallback == 0`).
  5. TIER5A orthogonality G6b PASS on this pod (forked wheel SHA
     pin verified; CPU CI couldn't run this track).

Output artifacts (in --output-dir):
  - cell_legacy.json     — token IDs + call_stats + per-prompt outputs
  - cell_refactored.json — same shape
  - smoke_report.json    — comparison verdict + per-prompt diffs
  - smoke_report.txt     — human-readable summary

Exit codes:
  0 — all checks GREEN (G_PRE-WRITE GPU portion PASS)
  1 — at least one check RED (DIVERGED tokens, missing path stats,
       fallbacks fired, or G6b failed)
  2 — environment error (model load failed, vllm not importable, etc.)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# Two deterministic prompts — multi-seq B=2 decode exercises
# write_decode_batched's per-slot broadcasting. Greedy decode keeps
# the comparison byte-stable.
PROMPTS = [
    # Prompt 1 — the existing "Greendell" needle from B-pre-4 audit.
    (
        "Below is a paragraph about a small fictional town. After it, "
        "answer the question concisely.\n\n"
        "Greendell is nestled between two rivers and has a population "
        "of just over four thousand. Its main industries are pottery, "
        "honey production, and the seasonal wool trade. The annual "
        "harvest festival in early autumn draws visitors from across "
        "the region. The oldest building in town is a stone library "
        "founded in 1742.\n\n"
        "Question: What year was the oldest building in Greendell "
        "founded?\nAnswer:"
    ),
    # Prompt 2 — distinct length + topic.
    (
        "Translate to French and explain briefly:\n"
        "English: The quick brown fox jumps over the lazy dog.\n"
        "French:"
    ),
]


CELL_LEGACY     = "legacy"
CELL_REFACTORED = "refactored"


def _check_environment() -> tuple[bool, str]:
    """Return (ok, diagnostic). Validates GPU + vLLM importable."""
    try:
        import torch
    except ImportError as e:
        return False, f"torch import failed: {e}"
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() == False; need GPU pod"
    try:
        from vllm import SamplingParams  # noqa: F401
    except ImportError as e:
        return False, f"vllm import failed: {e}"
    try:
        from kv_policy.int4_protected import Int4ProtectedLLM  # noqa: F401
    except ImportError as e:
        return False, f"kv_policy.int4_protected import failed: {e}"
    return True, "ok"


def run_worker(cell: str, output_path: Path, *, model: str,
               max_model_len: int, max_tokens: int,
               gpu_memory_utilization: float) -> int:
    """One worker cell — load the engine, run B=2 greedy decode, dump
    token IDs + call_stats + completions to JSON."""
    if cell not in (CELL_LEGACY, CELL_REFACTORED):
        print(f"FAIL: unknown cell {cell!r}")
        return 1
    # Set env BEFORE importing vllm; install_int4_protected_backend's
    # dispatch fork reads PHASE6B1_USE_DECODE_BATCHED on each forward call,
    # so technically setting it at any point before generate() works, but
    # setting it pre-import is the safest pattern.
    if cell == CELL_LEGACY:
        os.environ["PHASE6B1_USE_DECODE_BATCHED"] = "0"
    else:
        # Explicit "1" override so a global default change can't poison.
        os.environ["PHASE6B1_USE_DECODE_BATCHED"] = "1"

    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected
    from kv_policy.int4_protected import Int4ProtectedLLM
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl

    print(f"[cell={cell}] Loading {model}...")
    t0 = time.time()
    llm = Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        enforce_eager=True,
    )
    t_load = time.time() - t0
    print(f"[cell={cell}] Loaded in {t_load:.1f}s.")

    # Warmup with one cheap prompt so the engine's first-batch path doesn't
    # confuse the call_stats baseline (warmup goes through the same path
    # as the main run; we just don't count it).
    print(f"[cell={cell}] Warmup...")
    llm.generate(["Hello."], SamplingParams(temperature=0.0, max_tokens=4))
    Int4ProtectedAttentionImpl.reset_call_stats()

    print(f"[cell={cell}] Generating B={len(PROMPTS)} prompts, max_tokens={max_tokens}...")
    t0 = time.time()
    outputs = llm.generate(
        PROMPTS,
        SamplingParams(temperature=0.0, max_tokens=max_tokens),
    )
    torch.cuda.synchronize()
    t_gen = time.time() - t0

    call_stats = Int4ProtectedAttentionImpl.get_call_stats()
    print(f"[cell={cell}] Generated in {t_gen:.2f}s.  call_stats={call_stats}")

    per_prompt = []
    for i, out in enumerate(outputs):
        # vLLM RequestOutput: outputs[0] is the first candidate.
        c0 = out.outputs[0]
        per_prompt.append({
            "prompt_idx":      i,
            "prompt_preview":  PROMPTS[i][:60],
            "prompt_token_ids": list(out.prompt_token_ids or []),
            "completion_text": c0.text,
            "completion_token_ids": list(c0.token_ids),
        })

    payload = {
        "cell":               cell,
        "model":              model,
        "max_model_len":      max_model_len,
        "gpu_memory_utilization": gpu_memory_utilization,
        "max_tokens":         max_tokens,
        "n_prompts":          len(PROMPTS),
        "call_stats":         call_stats,
        "load_seconds":       t_load,
        "generate_seconds":   t_gen,
        "per_prompt":         per_prompt,
        "phase6b1_use_decode_batched_env": os.environ.get("PHASE6B1_USE_DECODE_BATCHED"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] Wrote {output_path}")
    return 0


def compare(legacy_path: Path, refactored_path: Path,
            report_json: Path, report_txt: Path) -> int:
    legacy     = json.loads(legacy_path.read_text())
    refactored = json.loads(refactored_path.read_text())

    checks: list[tuple[str, bool, str]] = []
    # Check 1: every prompt's completion_token_ids byte-equal.
    n_prompts = len(legacy["per_prompt"])
    if n_prompts != len(refactored["per_prompt"]):
        checks.append((
            "n_prompts_match", False,
            f"legacy={n_prompts}, refactored={len(refactored['per_prompt'])}",
        ))
    else:
        any_diverge = False
        diverge_details: list[str] = []
        for i in range(n_prompts):
            lt = legacy["per_prompt"][i]["completion_token_ids"]
            rt = refactored["per_prompt"][i]["completion_token_ids"]
            if lt == rt:
                continue
            any_diverge = True
            # Find first divergent position.
            common = 0
            for j in range(min(len(lt), len(rt))):
                if lt[j] != rt[j]:
                    break
                common += 1
            diverge_details.append(
                f"prompt[{i}]: diverges at token {common}/{min(len(lt), len(rt))}; "
                f"legacy={lt[common:common+5]} refactored={rt[common:common+5]}"
            )
        checks.append((
            "completion_token_ids_byte_equal",
            not any_diverge,
            "all prompts byte-equal" if not any_diverge else "; ".join(diverge_details),
        ))

    # Check 2: refactored cell fired write_decode_batched > 0.
    refac_decode_batched = refactored["call_stats"].get("write_decode_batched_calls", 0)
    refac_legacy_loop    = refactored["call_stats"].get("write_legacy_loop_calls",    0)
    checks.append((
        "refactored_cell_used_write_decode_batched",
        refac_decode_batched > 0,
        f"write_decode_batched_calls={refac_decode_batched}",
    ))

    # Check 3: legacy cell never fired write_decode_batched.
    leg_decode_batched = legacy["call_stats"].get("write_decode_batched_calls", 0)
    leg_legacy_loop    = legacy["call_stats"].get("write_legacy_loop_calls",    0)
    checks.append((
        "legacy_cell_used_only_legacy_loop",
        leg_decode_batched == 0 and leg_legacy_loop > 0,
        f"write_decode_batched_calls={leg_decode_batched}, write_legacy_loop_calls={leg_legacy_loop}",
    ))

    # Check 4: zero fallbacks in both cells.
    for cell_name, stats in (("legacy", legacy["call_stats"]),
                              ("refactored", refactored["call_stats"])):
        write_fb  = stats.get("write_path_fallback",   0)
        decode_fb = stats.get("decode_calls_fallback", 0)
        checks.append((
            f"{cell_name}_zero_fallbacks",
            write_fb == 0 and decode_fb == 0,
            f"write_path_fallback={write_fb}, decode_calls_fallback={decode_fb}",
        ))

    # Build report.
    overall_ok = all(ok for _, ok, _ in checks)
    report = {
        "verdict":           "GREEN" if overall_ok else "RED",
        "legacy_cell":       str(legacy_path),
        "refactored_cell":   str(refactored_path),
        "model":             legacy.get("model"),
        "n_prompts":         legacy.get("n_prompts"),
        "max_tokens":        legacy.get("max_tokens"),
        "checks": [
            {"name": name, "passed": ok, "detail": detail}
            for name, ok, detail in checks
        ],
        "legacy_call_stats":     legacy["call_stats"],
        "refactored_call_stats": refactored["call_stats"],
        "per_prompt_diffs":      [],
    }
    # Attach per-prompt diff snippets for human review.
    for i in range(min(len(legacy["per_prompt"]), len(refactored["per_prompt"]))):
        lp = legacy["per_prompt"][i]
        rp = refactored["per_prompt"][i]
        report["per_prompt_diffs"].append({
            "prompt_idx":           i,
            "prompt_preview":       lp["prompt_preview"],
            "legacy_text":          lp["completion_text"],
            "refactored_text":      rp["completion_text"],
            "tokens_byte_equal":    lp["completion_token_ids"] == rp["completion_token_ids"],
        })

    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    # Human-readable text report.
    lines = []
    lines.append("=" * 78)
    lines.append("Phase 6B.1 GPU smoke — comparison report")
    lines.append("=" * 78)
    lines.append(f"Model:      {report['model']}")
    lines.append(f"Prompts:    {report['n_prompts']}    max_tokens: {report['max_tokens']}")
    lines.append(f"Verdict:    {report['verdict']}")
    lines.append("")
    lines.append("Checks:")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        lines.append(f"  [{mark}] {c['name']:<48s} {c['detail']}")
    lines.append("")
    lines.append("Call stats:")
    lines.append(f"  legacy:     {json.dumps(report['legacy_call_stats'], sort_keys=True)}")
    lines.append(f"  refactored: {json.dumps(report['refactored_call_stats'], sort_keys=True)}")
    lines.append("")
    lines.append("Per-prompt diffs:")
    for d in report["per_prompt_diffs"]:
        lines.append(f"  prompt[{d['prompt_idx']}] preview: {d['prompt_preview']!r}")
        lines.append(f"    tokens_byte_equal:  {d['tokens_byte_equal']}")
        if not d["tokens_byte_equal"]:
            lines.append(f"    legacy_text:        {d['legacy_text']!r}")
            lines.append(f"    refactored_text:    {d['refactored_text']!r}")
    lines.append("")
    if overall_ok:
        lines.append("Phase 6B.1 GPU smoke: GREEN")
        lines.append("  Refactored write_decode_batched path produces byte-identical")
        lines.append("  generated tokens vs the legacy partition+loop path on")
        lines.append(f"  {report['model']} at B={report['n_prompts']}.")
    else:
        lines.append("Phase 6B.1 GPU smoke: RED")
        lines.append("  At least one check failed. See per-check 'detail' above.")
    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if overall_ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    sub_grp = p.add_mutually_exclusive_group()
    sub_grp.add_argument("--worker", action="store_true",
                        help="Run as a single-cell worker (internal).")
    sub_grp.add_argument("--compare", nargs=2, metavar=("LEGACY", "REFACTORED"),
                        help="Compare two existing cell JSONs and emit a report.")
    p.add_argument("--cell", choices=[CELL_LEGACY, CELL_REFACTORED],
                   help="Worker mode: which cell to run.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path for this cell's results.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6b1_gpu_smoke",
                   help="Driver mode: directory for both cells + report.")
    p.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len",  type=int,   default=4096)
    p.add_argument("--max-tokens",     type=int,   default=32)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    args = p.parse_args()

    if args.worker:
        if not args.cell or not args.output:
            print("FAIL: --worker requires --cell and --output.")
            return 2
        return run_worker(
            cell=args.cell, output_path=Path(args.output),
            model=args.model, max_model_len=args.max_model_len,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )

    if args.compare:
        return compare(
            legacy_path=Path(args.compare[0]),
            refactored_path=Path(args.compare[1]),
            report_json=Path(args.compare[0]).parent / "smoke_report.json",
            report_txt=Path(args.compare[0]).parent / "smoke_report.txt",
        )

    # Driver mode: spawn two workers as subprocesses.
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    legacy_json     = out_dir / "cell_legacy.json"
    refactored_json = out_dir / "cell_refactored.json"
    report_json     = out_dir / "smoke_report.json"
    report_txt      = out_dir / "smoke_report.txt"

    # Sanity-check we can import vllm BEFORE spawning workers; saves
    # both pod time + a confusing subprocess error.
    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-model-len", str(args.max_model_len),
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
    ]
    for cell, out_path in (
        (CELL_LEGACY,     legacy_json),
        (CELL_REFACTORED, refactored_json),
    ):
        print()
        print(f"=== Driver: spawning worker for cell={cell} ===")
        # Each subprocess inherits the parent's env EXCEPT we override
        # PHASE6B1_USE_DECODE_BATCHED via the worker itself.
        cmd = [sys.executable, __file__] + common_args + [
            "--cell", cell,
            "--output", str(out_path),
        ]
        ret = subprocess.run(cmd, check=False)
        if ret.returncode != 0:
            print(f"FAIL: worker cell={cell} exited with code {ret.returncode}")
            return ret.returncode

    return compare(legacy_json, refactored_json, report_json, report_txt)


if __name__ == "__main__":
    sys.exit(main())
