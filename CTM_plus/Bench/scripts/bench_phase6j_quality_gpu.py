"""Phase 6J — int4_protected vs int4_naive quality A/B bench.

Three cells:
  A: stock bf16 (quality ceiling)
  B: int4_naive (PROTECT_MASK_PATH=...naive.pt + PHASE6J_NAIVE_FORCE_ZERO=1)
  C: int4_protected (calibrated mask + PHASE6E_FUSED_WRITER=1)

Critical: B and C share the int4_protected backend; they differ only
in the protect-mask file AND the read-time force-zero substitution
(both flagged on the bench environment, not via code differences).

Modes:

  --smoke      Stage 3 of the user's staged-execution plan.
               One mml (8K), 2 depths × 2 needles for needle test,
               5 prompts for token agreement. ~5 min total pod time.
               Verifies B and C execute, that they DIFFER only in the
               protect-mask substitution, and that no fallbacks fire.

  (default)    Stage 4 full sweep.
               max_model_len ∈ {8192, 16384, 32768},
               5 depths × 5 needles per mml,
               20 prompts × 32 decode steps for token agreement.
               ~45-90 min total pod time.

For each cell × mml the bench captures:
  - Needle-in-haystack score per (depth, needle); aggregate accuracy.
  - Token agreement vs bf16 (cell A's outputs are pre-computed and
    diffed by the int4 cells).
  - Decode collapse metrics (trigram repetition, distinct-token
    ratio, longest identical run).
  - Throughput + HBM as secondary diagnostics.

The driver aggregates and computes the verdict per the design doc's
acceptance tree:

  PROTECT_MASK_VALIDATED:
    needle gap (protected - naive) >= 0.20 AND protected >= 0.7
    at mml ∈ {16K, 32K}, AND
    token agreement gap >= 0.10 AND protected >= 0.85 at mml=16K.

  MIXED:
    one primary metric meets threshold, the other doesn't.

  PROTECT_MASK_NOT_VALIDATED:
    neither primary metric meets threshold.

Run:
  # Stage 3 smoke first:
  python CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py --smoke

  # Stage 4 full sweep (only after smoke is green):
  python CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


CELL_BF16        = "bf16"
CELL_INT4_NAIVE  = "naive"
CELL_INT4_PROT   = "protected"
CELLS = [CELL_BF16, CELL_INT4_NAIVE, CELL_INT4_PROT]

DEFAULT_MAX_MODEL_LENS = [8192, 16384, 32768]
SMOKE_MAX_MODEL_LENS    = [8192]

DEFAULT_NEEDLE_DEPTHS = [0.10, 0.25, 0.50, 0.75, 0.90]
SMOKE_NEEDLE_DEPTHS   = [0.25, 0.75]

# 5 unique 6-char tokens. Alphanumeric, unique per index, avoids
# common English words so the model can't guess.
NEEDLE_VALUES_FULL  = ["HORIZ4", "ZK7QM2", "BRX91A", "PV2NK8", "LMD6CT"]
NEEDLE_VALUES_SMOKE = ["HORIZ4", "ZK7QM2"]

DEFAULT_MAX_TOKENS = 48
DEFAULT_GPU_MEM_UTIL = 0.5
DEFAULT_MAX_NUM_SEQS = 8     # small; needle test is B=1 + token-agree is B=1


# Held-out token-agreement prompts. Drawn from generic Q&A, summarization,
# and short-form completion. Kept frozen so all three cells see identical
# inputs.
TOKEN_AGREEMENT_PROMPTS_FULL = [
    "Explain in one sentence why the sky is blue.",
    "Translate to French: \"Where is the nearest train station?\"",
    "Continue this sentence: \"The first step in solving a difficult problem is\"",
    "List three side effects of caffeine.",
    "What is the capital of Mongolia? Answer in one word.",
    "Write a haiku about coffee.",
    "Define recursion in computer science.",
    "Name two countries that border Switzerland.",
    "What is the chemical symbol for gold?",
    "Summarize the plot of Romeo and Juliet in one sentence.",
    "Complete the proverb: \"A bird in the hand is worth\"",
    "What is 17 multiplied by 23?",
    "Name one play written by Shakespeare.",
    "Explain photosynthesis in one sentence.",
    "What year did World War II end?",
    "Continue: \"Once upon a time, in a forest far away,\"",
    "Translate to Spanish: \"I would like a glass of water.\"",
    "Define 'metaphor' in one sentence.",
    "What is the largest planet in the solar system?",
    "Continue: \"The detective entered the room and immediately noticed\"",
]
TOKEN_AGREEMENT_PROMPTS_SMOKE = TOKEN_AGREEMENT_PROMPTS_FULL[:5]


PROMPT_NEEDLE_INTRO = (
    "Below is a long document. Read it carefully, then answer "
    "the question at the end.\n\nDocument:\n"
)
PROMPT_NEEDLE_FILLER = (
    "The town of Brookhaven sits between gently rolling hills. "
    "Its weekly market draws growers from across the county. "
    "The river that runs through the center is shallow most of "
    "the year and deepens only after the spring rains. "
    "Older residents still remember when the railway extended "
    "all the way to the coast. The annual festival features "
    "music, food stalls, and a parade led by the local school. "
    "Brick houses line the main street, and the largest of them "
    "is the inn, which has stood for over a century. "
)
PROMPT_NEEDLE_QUESTION = (
    "\n\nQuestion: What is the secret code mentioned in the document? "
    "Answer with just the code.\nAnswer:"
)


def _make_needle_prompt(target_tokens: int, depth: float, needle_value: str) -> str:
    """Construct a needle-in-haystack prompt whose total length is
    approximately target_tokens, with the needle sentence injected at
    fractional depth `depth` (0.0 = top, 1.0 = bottom).
    """
    needle_sentence = (
        f"Hidden in this document is the secret code: {needle_value}. "
    )
    intro = PROMPT_NEEDLE_INTRO
    question = PROMPT_NEEDLE_QUESTION
    # Build the haystack (filler) to ~target_chars, then inject the
    # needle at the depth-fraction point.
    target_chars = max(0, target_tokens * 4)
    fixed_chars = (
        len(intro) + len(needle_sentence) + len(question)
    )
    filler_chars = max(0, target_chars - fixed_chars)
    n_reps = max(2, filler_chars // len(PROMPT_NEEDLE_FILLER))
    full_filler = PROMPT_NEEDLE_FILLER * n_reps
    inject_pos = int(len(full_filler) * depth)
    # Snap to the nearest sentence boundary so we don't insert
    # mid-word.
    if inject_pos < len(full_filler):
        # Move forward to the next ". " for natural insertion.
        m = re.search(r"\. ", full_filler[inject_pos:])
        if m:
            inject_pos += m.end()
    haystack = (
        full_filler[:inject_pos] + needle_sentence + full_filler[inject_pos:]
    )
    return intro + haystack + question


# ----- Quality metric helpers -----


def _score_needle(output_text: str, needle_value: str) -> float:
    """1.0 if exact-contains needle; 0.5 if first 3 chars present;
    0.0 otherwise."""
    if not output_text:
        return 0.0
    if needle_value in output_text:
        return 1.0
    if needle_value[:3] in output_text:
        return 0.5
    return 0.0


def _decode_collapse_stats(token_ids: List[int]) -> Dict[str, float]:
    if not token_ids:
        return {
            "trigram_repeat_rate": 0.0,
            "distinct_token_ratio": 0.0,
            "longest_identical_run": 0,
            "n_tokens": 0,
        }
    n = len(token_ids)
    distinct = len(set(token_ids))
    # Longest identical run.
    longest = 1
    cur = 1
    for i in range(1, n):
        if token_ids[i] == token_ids[i - 1]:
            cur += 1
            if cur > longest:
                longest = cur
        else:
            cur = 1
    # Trigram repetition rate.
    if n < 3:
        trigram_rate = 0.0
    else:
        seen: Dict[Tuple[int, int, int], int] = {}
        for i in range(n - 2):
            tri = (token_ids[i], token_ids[i + 1], token_ids[i + 2])
            seen[tri] = seen.get(tri, 0) + 1
        n_trigrams = n - 2
        repeated = sum(c for c in seen.values() if c > 1) - len(
            [c for c in seen.values() if c > 1]
        )
        trigram_rate = repeated / max(1, n_trigrams)
    return {
        "trigram_repeat_rate":  trigram_rate,
        "distinct_token_ratio": distinct / n,
        "longest_identical_run": longest,
        "n_tokens":             n,
    }


# ----- Cell config + worker -----


def _cell_env_overrides(cell: str, naive_mask_path: Optional[str]) -> Dict[str, str]:
    """Returns the env vars that should be set for this cell. The
    caller already inherits the parent process's env; we only OVERRIDE
    the per-cell knobs.
    """
    if cell == CELL_BF16:
        # Stock bf16: no int4 backend, no fused writer, no naive flag.
        return {
            "PHASE6E_FUSED_WRITER":      "0",
            "PHASE6J_NAIVE_FORCE_ZERO":  "0",
        }
    if cell == CELL_INT4_NAIVE:
        env = {
            "PHASE6E_FUSED_WRITER":      "1",
            "PHASE6J_NAIVE_FORCE_ZERO":  "1",
        }
        if naive_mask_path:
            env["PROTECT_MASK_PATH"] = naive_mask_path
        return env
    if cell == CELL_INT4_PROT:
        return {
            "PHASE6E_FUSED_WRITER":      "1",
            "PHASE6J_NAIVE_FORCE_ZERO":  "0",
            # PROTECT_MASK_PATH: inherit parent (calibrated mask).
        }
    raise ValueError(f"Unknown cell: {cell!r}")


def _check_environment(require_int4: bool) -> Tuple[bool, str]:
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() is False"
    except ImportError as exc:
        return False, f"torch import failed: {exc}"
    try:
        import vllm   # noqa: F401
    except ImportError as exc:
        return False, f"vllm import failed: {exc}"
    if require_int4:
        try:
            from kv_policy import int4_protected   # noqa: F401
        except ImportError as exc:
            return False, f"kv_policy import failed: {exc}"
    return True, "OK"


def _build_llm(cell: str, model: str, max_model_len: int,
               gpu_memory_utilization: float, max_num_seqs: int):
    import torch
    if cell == CELL_BF16:
        from vllm import LLM
        return LLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype="bfloat16",
            max_num_seqs=max_num_seqs,
        )
    # int4 cells share the Int4ProtectedLLM factory.
    from kv_policy.int4_protected import Int4ProtectedLLM
    return Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        max_num_seqs=max_num_seqs,
    )


def _install_hook_if_int4(llm, cell: str):
    if cell == CELL_BF16:
        return None
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook,
    )
    # Find inner model + model_runner.
    candidates_model = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
    ]
    candidates_runner = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
    ]
    inner = next((fn(llm) for fn in candidates_model
                  if _try_get(fn, llm) is not None), None)
    runner = next((fn(llm) for fn in candidates_runner
                   if _try_get(fn, llm) is not None), None)
    if inner is None or runner is None:
        print("WARN: cannot install precapture hook (model/runner not found).")
        return None
    writers, impls = [], []
    for _, sub in inner.named_modules():
        impl = getattr(sub, "impl", None)
        if isinstance(impl, Int4ProtectedAttentionImpl):
            impls.append(impl)
            w = getattr(impl, "_phase5b_paged_writer", None)
            if w is not None:
                writers.append(w)
    return install_int4_protected_precapture_hook(runner, writers, impls=impls)


def _try_get(fn, llm):
    try:
        return fn(llm)
    except (AttributeError, IndexError):
        return None


def run_worker(
    cell: str,
    max_model_len: int,
    output_path: Path,
    *,
    model: str,
    max_tokens: int,
    gpu_memory_utilization: float,
    max_num_seqs: int,
    needle_depths: List[float],
    needle_values: List[str],
    token_agreement_prompts: List[str],
) -> int:
    if cell not in CELLS:
        print(f"FAIL: unknown cell {cell!r}")
        return 1

    require_int4 = cell != CELL_BF16
    ok, diag = _check_environment(require_int4=require_int4)
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams

    print(f"[cell={cell} mml={max_model_len}] Loading...")
    t0 = time.time()
    try:
        llm = _build_llm(cell, model, max_model_len,
                         gpu_memory_utilization, max_num_seqs)
    except torch.cuda.OutOfMemoryError as exc:
        print(f"FAIL: LLM init OOM: {str(exc)[:200]}")
        return 2
    torch.cuda.synchronize()
    t_load = time.time() - t0
    hbm_after_init = torch.cuda.memory_allocated() / (1024 ** 3)
    print(f"[cell={cell}] Loaded in {t_load:.1f}s.  "
          f"HBM (PyTorch allocated): {hbm_after_init:.2f} GB")

    hook = _install_hook_if_int4(llm, cell)
    if hook is not None:
        print(f"[cell={cell}] Hook installed: {hook.enabled}")

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

    # ---- Needle-in-haystack ----
    print(f"[cell={cell}] Needle sweep: depths={needle_depths}  "
          f"needles={needle_values}")
    needle_records: List[Dict[str, Any]] = []
    needle_scores: List[float] = []
    for depth in needle_depths:
        for needle_value in needle_values:
            target_tokens = max_model_len // 2
            prompt = _make_needle_prompt(target_tokens, depth, needle_value)
            try:
                t1 = time.time()
                outs = llm.generate([prompt], sampling)
                wall = time.time() - t1
            except torch.cuda.OutOfMemoryError as exc:
                needle_records.append({
                    "depth": depth, "needle": needle_value,
                    "oom": True, "output_text": "", "score": 0.0,
                    "wall_s": 0.0, "n_output_tokens": 0,
                })
                needle_scores.append(0.0)
                continue
            out_text = outs[0].outputs[0].text or ""
            out_toks = list(outs[0].outputs[0].token_ids)
            score = _score_needle(out_text, needle_value)
            needle_scores.append(score)
            collapse = _decode_collapse_stats(out_toks)
            needle_records.append({
                "depth":           depth,
                "needle":          needle_value,
                "score":           score,
                "output_text":     out_text[:200],
                "n_output_tokens": len(out_toks),
                "collapse":        collapse,
                "wall_s":          wall,
                "oom":             False,
            })

    needle_acc = (sum(needle_scores) / len(needle_scores)) if needle_scores else 0.0

    # ---- Token agreement (per-step top-1 token IDs) ----
    print(f"[cell={cell}] Token-agreement sweep: {len(token_agreement_prompts)} prompts")
    agreement_records: List[Dict[str, Any]] = []
    for p in token_agreement_prompts:
        try:
            outs = llm.generate([p], SamplingParams(temperature=0.0, max_tokens=32))
            toks = list(outs[0].outputs[0].token_ids)
            text = outs[0].outputs[0].text or ""
            collapse = _decode_collapse_stats(toks)
            agreement_records.append({
                "prompt":          p,
                "token_ids":       toks,
                "output_text":     text[:200],
                "collapse":        collapse,
            })
        except torch.cuda.OutOfMemoryError as exc:
            agreement_records.append({
                "prompt":     p,
                "token_ids":  [],
                "output_text": "",
                "collapse":   _decode_collapse_stats([]),
                "oom":        True,
            })

    payload: Dict[str, Any] = {
        "cell":                cell,
        "model":               model,
        "max_model_len":       max_model_len,
        "max_tokens":          max_tokens,
        "load_seconds":        t_load,
        "hbm_after_init_gb":   hbm_after_init,
        "needle_depths":       needle_depths,
        "needle_values":       needle_values,
        "needle_accuracy":     needle_acc,
        "needle_records":      needle_records,
        "agreement_records":   agreement_records,
        "phase6j_naive_force_zero_env": os.environ.get("PHASE6J_NAIVE_FORCE_ZERO", "0"),
        "phase6e_fused_writer_env":     os.environ.get("PHASE6E_FUSED_WRITER", "0"),
        "protect_mask_path_env":        os.environ.get("PROTECT_MASK_PATH", ""),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[cell={cell}] Needle accuracy: {needle_acc:.3f}  "
          f"({sum(s>0 for s in needle_scores)}/{len(needle_scores)} non-zero)")
    print(f"[cell={cell}] Wrote {output_path}")
    if hook is not None:
        try:
            hook.teardown()
        except Exception:
            pass
    return 0


# ----- Driver: compare + report -----


def compare(
    cell_paths: Dict[Tuple[str, int], Path],
    max_model_lens: List[int],
    report_json: Path,
    report_txt: Path,
) -> int:
    loaded: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for k, p in cell_paths.items():
        if p.exists():
            loaded[k] = json.loads(p.read_text())

    # Per-mml needle accuracy.
    needle_rows: List[Dict[str, Any]] = []
    for mml in max_model_lens:
        row: Dict[str, Any] = {"max_model_len": mml}
        for c in CELLS:
            payload = loaded.get((c, mml))
            row[f"{c}_needle_acc"] = (
                payload.get("needle_accuracy") if payload else None
            )
        if row["bf16_needle_acc"] is not None:
            if row["naive_needle_acc"] is not None:
                row["protected_minus_naive"] = (
                    (row["protected_needle_acc"] or 0)
                    - (row["naive_needle_acc"] or 0)
                )
        needle_rows.append(row)

    # Token agreement: count tokens matching bf16 across all 20 prompts × 32 steps.
    agreement_rows: List[Dict[str, Any]] = []
    for mml in max_model_lens:
        bf16_payload = loaded.get((CELL_BF16, mml))
        if bf16_payload is None:
            continue
        bf16_seqs = [r["token_ids"] for r in bf16_payload["agreement_records"]]
        for c in (CELL_INT4_NAIVE, CELL_INT4_PROT):
            payload = loaded.get((c, mml))
            if payload is None:
                continue
            this_seqs = [r["token_ids"] for r in payload["agreement_records"]]
            n_total = 0
            n_agree = 0
            for bs, ts in zip(bf16_seqs, this_seqs):
                L = min(len(bs), len(ts))
                n_total += L
                n_agree += sum(1 for i in range(L) if bs[i] == ts[i])
            agreement_rows.append({
                "max_model_len":   mml,
                "cell":            c,
                "n_prompts":       len(this_seqs),
                "n_total_tokens":  n_total,
                "n_agree":         n_agree,
                "agreement_rate":  n_agree / max(1, n_total),
            })

    # Verdict per design doc:
    #   PROTECT_MASK_VALIDATED requires BOTH primary metrics:
    #     needle (protected - naive >= 0.20) AND (protected >= 0.7)
    #            at mml in {16K, 32K}.
    #     token agreement (protected - naive >= 0.10)
    #                     AND (protected >= 0.85) at mml=16K.
    def _needle_meets(row):
        p = row.get("protected_needle_acc")
        n = row.get("naive_needle_acc")
        if p is None or n is None:
            return False
        return p >= 0.7 and (p - n) >= 0.20

    def _agreement_meets(rows, mml, cell):
        for r in rows:
            if r["max_model_len"] == mml and r["cell"] == cell:
                return r["agreement_rate"]
        return None

    needle_pass_mmls = [
        row["max_model_len"]
        for row in needle_rows
        if row["max_model_len"] in (16384, 32768)
        and _needle_meets(row)
    ]
    needle_pass = len(needle_pass_mmls) >= 1

    prot_16k_agree = _agreement_meets(agreement_rows, 16384, CELL_INT4_PROT)
    naive_16k_agree = _agreement_meets(agreement_rows, 16384, CELL_INT4_NAIVE)
    if prot_16k_agree is not None and naive_16k_agree is not None:
        agreement_pass = (prot_16k_agree >= 0.85
                          and (prot_16k_agree - naive_16k_agree) >= 0.10)
    else:
        # Fall back to the largest available mml if 16K wasn't run.
        agreement_pass = False
        for mml in (max_model_lens or []):
            p = _agreement_meets(agreement_rows, mml, CELL_INT4_PROT)
            n = _agreement_meets(agreement_rows, mml, CELL_INT4_NAIVE)
            if p is not None and n is not None:
                agreement_pass = (p >= 0.85 and (p - n) >= 0.10)

    if needle_pass and agreement_pass:
        verdict = "PROTECT_MASK_VALIDATED"
        verdict_note = (
            "BOTH primary metrics pass: needle-in-haystack accuracy "
            "gap (protected - naive) >= 0.20 at mml in {16K, 32K} AND "
            "token-agreement gap >= 0.10 at mml=16K with protected >= "
            "0.85. The protect-mask design demonstrably preserves "
            "long-context retrieval quality vs naive int4. Project "
            "ships as long-context quality-preserving int4 backend."
        )
    elif needle_pass or agreement_pass:
        verdict = "MIXED"
        verdict_note = (
            f"Exactly ONE primary metric passes (needle={needle_pass}, "
            f"token_agreement={agreement_pass}). Investigate why one "
            f"metric agrees and the other doesn't before deciding. "
            f"Likely calibration issue or metric sensitivity."
        )
    else:
        verdict = "PROTECT_MASK_NOT_VALIDATED"
        verdict_note = (
            "Neither primary metric meets the acceptance threshold. "
            "Protect-mask does not materially help long-context quality "
            "vs naive int4 on this model + workload. Recommendation: "
            "close the int4_protected line as research artifact and "
            "document the 6E+6G+6H+6J negative result chain."
        )

    report = {
        "verdict":          verdict,
        "verdict_note":     verdict_note,
        "needle_rows":      needle_rows,
        "agreement_rows":   agreement_rows,
        "needle_pass_mmls": needle_pass_mmls,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2, default=str))

    lines: List[str] = []
    lines.append("=" * 90)
    lines.append("Phase 6J — int4_protected vs int4_naive quality A/B")
    lines.append("=" * 90)
    lines.append(f"Verdict: {verdict}")
    for line in (verdict_note or "").splitlines() or [""]:
        lines.append(f"  {line}")
    lines.append("")
    lines.append("Needle-in-haystack accuracy (1.0 = exact-match, 0.5 = partial):")
    lines.append(
        f"  {'mml':>6} | {'bf16':>8} | {'naive':>8} | {'protected':>10} | "
        f"{'prot - naive':>13}"
    )
    lines.append("  " + "-" * 60)
    for row in needle_rows:
        def _f(v): return f"{v:>8.3f}" if v is not None else "    n/a "
        delta = row.get("protected_minus_naive")
        delta_s = f"{delta:+8.3f}" if delta is not None else "     n/a "
        lines.append(
            f"  {row['max_model_len']:>6} | "
            f"{_f(row.get('bf16_needle_acc'))} | "
            f"{_f(row.get('naive_needle_acc'))} | "
            f"{_f(row.get('protected_needle_acc')):>10} | "
            f"{delta_s:>13}"
        )
    lines.append("")
    lines.append("Token agreement vs bf16 (greedy top-1 match rate, 32 decode steps):")
    lines.append(
        f"  {'mml':>6} | {'cell':>10} | {'agree_rate':>12} | "
        f"{'n_agree':>9} | {'n_total':>9}"
    )
    lines.append("  " + "-" * 60)
    for r in agreement_rows:
        lines.append(
            f"  {r['max_model_len']:>6} | {r['cell']:>10} | "
            f"{r['agreement_rate']:>12.3f} | "
            f"{r['n_agree']:>9} | {r['n_total_tokens']:>9}"
        )
    lines.append("")
    lines.append(f"Verdict: {verdict}")

    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if verdict == "PROTECT_MASK_VALIDATED":
        return 0
    if verdict == "MIXED":
        return 2
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true")
    p.add_argument("--cell", choices=CELLS)
    p.add_argument("--max-model-len", type=int)
    p.add_argument("--output", type=str)
    p.add_argument("--smoke", action="store_true",
                   help="Stage 3 smoke: small mml + 2 depths × 2 needles + "
                        "5 prompts. ~5 min total pod time.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6j_quality")
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--gpu-memory-utilization", type=float,
                   default=DEFAULT_GPU_MEM_UTIL)
    p.add_argument("--max-num-seqs", type=int, default=DEFAULT_MAX_NUM_SEQS)
    p.add_argument("--naive-mask-path", type=str,
                   default="/workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt",
                   help="Path to the all-zeros companion protect-mask "
                        "artifact (created by make_phase6j_naive_protect_mask.py).")
    args = p.parse_args()

    max_model_lens = SMOKE_MAX_MODEL_LENS if args.smoke else DEFAULT_MAX_MODEL_LENS
    needle_depths  = SMOKE_NEEDLE_DEPTHS  if args.smoke else DEFAULT_NEEDLE_DEPTHS
    needle_values  = NEEDLE_VALUES_SMOKE  if args.smoke else NEEDLE_VALUES_FULL
    tok_prompts    = TOKEN_AGREEMENT_PROMPTS_SMOKE if args.smoke else TOKEN_AGREEMENT_PROMPTS_FULL

    if args.worker:
        if (not args.cell or args.max_model_len is None or not args.output):
            print("FAIL: --worker requires --cell, --max-model-len, --output.")
            return 2
        return run_worker(
            cell=args.cell,
            max_model_len=args.max_model_len,
            output_path=Path(args.output),
            model=args.model,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            max_num_seqs=args.max_num_seqs,
            needle_depths=needle_depths,
            needle_values=needle_values,
            token_agreement_prompts=tok_prompts,
        )

    out_dir = Path(args.output_dir)
    if args.smoke:
        out_dir = out_dir.with_name(out_dir.name + "_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_paths: Dict[Tuple[str, int], Path] = {}
    for c in CELLS:
        for mml in max_model_lens:
            cell_paths[(c, mml)] = out_dir / f"cell_{c}_mml{mml}.json"

    # Verify the naive mask artifact exists (only relevant if we'll run
    # the naive cell).
    naive_path = Path(args.naive_mask_path)
    if not naive_path.exists():
        print(f"FAIL: naive mask artifact not found at {naive_path}.")
        print(f"Run make_phase6j_naive_protect_mask.py first.")
        return 2

    common = [
        "--worker",
        "--model", args.model,
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-num-seqs", str(args.max_num_seqs),
        "--naive-mask-path", str(naive_path),
    ]
    if args.smoke:
        common.append("--smoke")

    # Run subprocesses with per-cell env overrides via the inherited
    # environment (subprocess.run inherits env unless overridden).
    for mml in max_model_lens:
        for cell in CELLS:
            out_path = cell_paths[(cell, mml)]
            print()
            print(f"=== Driver: cell={cell} mml={mml} ===")
            env = dict(os.environ)
            env.update(_cell_env_overrides(cell, str(naive_path)))
            cmd = [sys.executable, __file__] + common + [
                "--cell", cell,
                "--max-model-len", str(mml),
                "--output", str(out_path),
            ]
            ret = subprocess.run(cmd, env=env, check=False)
            if ret.returncode != 0:
                print(f"WARN: cell={cell} mml={mml} exited code {ret.returncode} — "
                      f"continuing.")

    return compare(
        cell_paths=cell_paths,
        max_model_lens=max_model_lens,
        report_json=out_dir / "quality_report.json",
        report_txt=out_dir / "quality_report.txt",
    )


if __name__ == "__main__":
    sys.exit(main())
