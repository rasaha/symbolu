#!/usr/bin/env python3
"""Single-GPU sequential orchestrator for the B1.12 BSR crossover.

One model resident at a time (bf16, deterministic), via 3 subprocess model loads:
  1) Qwen   -> Run A author
  2) Mistral-> Run A score (uses A author) + Run B author
  3) Qwen   -> Run B score (uses B author)
Then mechanical aggregation, agreement, and role-dependence (imported from run_crossover).

Usage on a single 80GB GPU:
  python run_sequential.py --qwen Qwen/Qwen3-32B \
      --mistral mistralai/Mistral-Small-3.1-24B-Instruct-2503 --seed 20260714
"""
from __future__ import annotations
import argparse, json, subprocess, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
EXPT = HERE.parent
OUT = EXPT / "results" / "b1_12_symbolic_resonance_multillm_v1"
sys.path.insert(0, str(HERE))
import verify_inputs, backends
from run_crossover import agreement
LABEL = "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE"

def dump(n, o):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / n).write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")

def phase_done(jobs):
    """Resume guard: a phase is already complete iff every job's output JSON exists and parses."""
    for j in jobs:
        p = pathlib.Path(j["out"])
        if not p.exists():
            return False
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception:
            return False
    return True

def run_worker(model, jobs, tmp, wl, args, tag):
    if phase_done(jobs):
        print("SKIP (resume: outputs already present)", tag, [j["out"] for j in jobs], flush=True)
        return
    jf = tmp / f"jobs_{tag}.json"
    jf.write_text(json.dumps(jobs), encoding="utf-8")
    cmd = [sys.executable, str(HERE / "phase_worker.py"), "--model", model, "--jobs", str(jf),
           "--wordlist", str(wl), "--raw-out", str(OUT / "raw_all.jsonl"),
           "--seed", str(args.seed), "--max-tokens", str(args.max_tokens),
           "--gpu-mem-util", str(args.gpu_mem_util), "--max-model-len", str(args.max_model_len)]
    if args.qwen_thinking and "qwen" in model.lower():
        cmd.append("--qwen-thinking")
    print(">>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qwen", default=backends.QWEN_DEFAULT)
    ap.add_argument("--mistral", default=backends.MISTRAL_DEFAULT)
    ap.add_argument("--seed", type=int, default=20260714)
    ap.add_argument("--qwen-thinking", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--gpu-mem-util", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=8192)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    st, det = verify_inputs.verify()
    if st != "OK":
        dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL,
             "status": "RUN_INVALID_INPUT_MISMATCH", "reasons": det})
        print("RUN_INVALID_INPUT_MISMATCH", det); return
    dump("input_hashes.json", {"schema": "b1_12_bsr_input_hashes_v1", **det})

    ok, info = backends.availability(args.qwen, args.mistral, "vllm")
    if not ok:
        dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL,
             "status": "BLOCKED_REQUIRED_MODEL_UNAVAILABLE", "availability": info})
        print("BLOCKED_REQUIRED_MODEL_UNAVAILABLE", info); return

    wl = verify_inputs.WORDLIST_JSON
    tmp = OUT / "_tmp"; tmp.mkdir(exist_ok=True)
    A_auth, A_sc = tmp / "A_author.json", tmp / "A_scores.json"
    B_auth, B_sc = tmp / "B_author.json", tmp / "B_scores.json"
    resuming = any(p.exists() for p in (A_auth, A_sc, B_auth, B_sc))
    if not resuming:  # fresh run truncates the raw log; resume appends to preserve completed phases
        (OUT / "raw_all.jsonl").write_text("", encoding="utf-8")
    elif not (OUT / "raw_all.jsonl").exists():
        (OUT / "raw_all.jsonl").write_text("", encoding="utf-8")

    run_worker(args.qwen, [{"run": "A", "role": "author", "out": str(A_auth)}], tmp, wl, args, "qwen_A_author")
    run_worker(args.mistral, [{"run": "A", "role": "score", "author_file": str(A_auth), "out": str(A_sc)},
                              {"run": "B", "role": "author", "out": str(B_auth)}], tmp, wl, args, "mistral_A_score_B_author")
    run_worker(args.qwen, [{"run": "B", "role": "score", "author_file": str(B_auth), "out": str(B_sc)}], tmp, wl, args, "qwen_B_score")

    aa, asc = json.load(open(A_auth)), json.load(open(A_sc))
    ba, bsc = json.load(open(B_auth)), json.load(open(B_sc))
    run_a = {"profiles": aa["profiles"], "evidence": aa["evidence"], "scores": asc["scores"]}
    run_b = {"profiles": ba["profiles"], "evidence": ba["evidence"], "scores": bsc["scores"]}

    for tag, run in (("a", run_a), ("b", run_b)):
        dump(f"run_{tag}_profiles.json", {"label": LABEL, "profiles": run["profiles"]})
        dump(f"run_{tag}_evidence.json", {"label": LABEL, "evidence": run["evidence"]})
        dump(f"run_{tag}_scores.json", {"label": LABEL, "scores": run["scores"]})
    # split raw log by run
    raw = [json.loads(l) for l in (OUT / "raw_all.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    for tag in ("A", "B"):
        with open(OUT / f"run_{tag.lower()}_raw_outputs.jsonl", "w", encoding="utf-8") as f:
            for r in raw:
                if r.get("run") == tag:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        dump(f"run_{tag.lower()}_model_inputs.json", {"label": LABEL,
             "inputs": [{"run": r["run"], "role": r["role"], "model": r["model"], "word": r["word"],
                         "prompt_sha256": r.get("prompt_sha256"), "attempt": r["attempt"]}
                        for r in raw if r.get("run") == tag and r.get("valid")]})

    ag = agreement(run_a, run_b)
    dump("component_agreement.json", ag["component_agreement"])
    dump("relationship_agreement.json", ag["relationship_agreement"])
    dump("word_verdict_agreement.json", ag["word_verdict_agreement"])
    dump("role_dependence_summary.json", {"role_dependence": ag["role_dependence"],
         "profile_agreement": ag["profile_agreement"],
         "component_summary": {k: ag["component_agreement"][k] for k in
             ("n_components", "exact_agreement", "within_one_step_agreement", "mean_abs_diff",
              "median_abs_diff", "signed_mean_diff_A_minus_B")},
         "verdict_summary": {"exact_verdict_agreement": ag["word_verdict_agreement"]["exact_verdict_agreement"],
                             "evaluator_sensitive_words": ag["word_verdict_agreement"]["evaluator_sensitive_words"]}})
    dump("model_manifest.json", {"schema": "b1_12_bsr_model_manifest_v1", "label": LABEL,
         "mode": "vllm_sequential_single_gpu",
         "qwen": {"model_id": args.qwen, "family": "Qwen3", "param_class": "~30-32B",
                  "reasoning_mode": ("thinking" if args.qwen_thinking else "non_thinking")},
         "mistral": {"model_id": args.mistral, "family": "Mistral Small 3.x", "param_class": "~24B"},
         "decoding": {"temperature": 0.0, "top_p": 1.0, "top_k": -1, "repetition_penalty": 1.0,
                      "seed": args.seed, "max_tokens": args.max_tokens, "dtype": "bfloat16"},
         "loads": "3 sequential (Qwen A-author; Mistral A-score+B-author; Qwen B-score) — one model resident at a time",
         "substitution_policy": "PROHIBITED"})
    dump("wordlist_manifest.json", json.load(open(verify_inputs.WORDLIST_DIR / "wordlist_manifest.json", encoding="utf-8")))
    dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL, "status": "COMPLETED",
         "mode": "vllm_sequential_single_gpu",
         "controlling_preregistration": "VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md",
         "verdict_role_freeze": "B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md",
         "wordlist_sha256": det["wordlist_sha256"], "role_dependence": ag["role_dependence"],
         "no_forced_consensus": True})
    print("COMPLETED role_dependence=", ag["role_dependence"])

if __name__ == "__main__":
    main()
