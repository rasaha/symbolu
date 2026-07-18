#!/usr/bin/env python3
"""run_ablation.py — the A/B(/C/D/E) ablation over the pre-registered eval sets (Task 5).

For each arm and each pre-registered eval set, generates a continuation per example per seed,
scores it with the objective metrics, and logs full diagnostics. Saves ALL artifacts under
runs/cg_wrapper_ablation/<timestamp>/ for the metrics parser to summarize.

Arms: A_base, B_full, C_phase_off, D_gate0 (+ E_csr only if CSR is wired in).

Env vars (see README.md): MODEL_ID, CG_CHECKPOINT, DEVICE, DTYPE, SEEDS, N_SAMPLES,
MAX_NEW_TOKENS, ALLOW_UNTRAINED_CG_HEAD.

This writes raw generations + per-example scores + per-example diagnostics; it deliberately does
NOT compute the final verdict (that's metrics_report.py) so raw artifacts stay separable from
the analysis.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from cg_ablation.arms import active_arms  # noqa: E402
from cg_ablation.evalsets import EVAL_SETS, load_eval_set  # noqa: E402
from cg_ablation.runtime import (  # noqa: E402
    build_wrapper,
    detect_csr_present,
    generate,
    parse_env,
    prompt_logit_diag,
)


def _adapter_weight_norm(wrapper) -> float:
    """L2 norm of the phase_adapter output-layer weight (static checkpoint property)."""
    try:
        import torch  # noqa: F401
        w = wrapper.phase_adapter[-1].weight
        return float(w.detach().float().norm().item())
    except Exception:
        return 0.0


def _score(kind, text, row, metrics):
    """Objective score for one (kind, text, row). Returns (ok: bool, answer)."""
    if kind == "exact_match":
        ans = metrics.extract_final_integer(text)
        return metrics.exact_match(text, row["answer"]), ans
    if kind == "constraint":
        ok = all(metrics.constraint_satisfied(text, c) for c in row["constraints"])
        return ok, text.strip()[:64]
    if kind == "json":
        ok = metrics.json_has_keys(text, row["required_keys"])
        return ok, text.strip()[:64]
    return False, None


def main() -> int:
    from cg_ablation import metrics

    cfg = parse_env()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = _REPO / "runs" / "cg_wrapper_ablation" / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"== ablation run :: {run_dir} ==")

    wrapper, tok = build_wrapper(cfg)
    csr = detect_csr_present(wrapper)
    arms = active_arms(csr_present=csr)
    base_arm = next(a for a in arms if a.name == "A_base")

    # Persist resolved config + plan provenance.
    (run_dir / "config.json").write_text(json.dumps({
        "timestamp": ts,
        "model_id": cfg.model_id,
        "checkpoint": cfg.checkpoint,
        "device": cfg.device,
        "dtype": cfg.dtype,
        "seeds": cfg.seeds,
        "n_samples": cfg.n_samples,
        "max_new_tokens": cfg.max_new_tokens,
        "allow_untrained": cfg.allow_untrained,
        "csr_present": csr,
        "arms": [a.name for a in arms],
        "eval_sets": {k: v["file"] for k, v in EVAL_SETS.items()},
        "decoding_task": {"temperature": 0.0},
        "decoding_consistency": {"temperature": 0.7, "top_p": 0.9, "top_k": 50},
    }, indent=2))

    gen_fp = (run_dir / "raw_generations.jsonl").open("w", buffering=1)
    score_fp = (run_dir / "per_example_scores.jsonl").open("w", buffering=1)
    diag_fp = (run_dir / "diagnostics.jsonl").open("w", buffering=1)

    t0 = time.time()
    for set_name, meta in EVAL_SETS.items():
        kind = meta["kind"]
        rows = load_eval_set(set_name)
        if cfg.n_samples:
            rows = rows[: cfg.n_samples]
        # Cross-seed consistency (stochastic decoding over seeds) is the expensive part; only do
        # it when more than one seed is requested. Greedy is seed-independent → generate it ONCE.
        do_consistency = len(cfg.seeds) > 1
        for ei, row in enumerate(rows):
            prompt = row["prompt"]

            for arm in arms:
                # greedy (deterministic) for the scored answer — generated ONCE, not per seed.
                g = generate(wrapper, tok, prompt, arm,
                             max_new_tokens=cfg.max_new_tokens, temperature=0.0, seed=cfg.seeds[0])
                ok, ans = _score(kind, g["text"], row, metrics)
                gen_fp.write(json.dumps({
                    "set": set_name, "id": row["id"], "arm": arm.name,
                    "seed": cfg.seeds[0], "prompt": prompt, "text": g["text"],
                    "n_new_tokens": g["n_new_tokens"], "diag": g["diag"],
                }) + "\n")
                score_fp.write(json.dumps({
                    "set": set_name, "id": row["id"], "arm": arm.name,
                    "kind": kind, "ok": bool(ok), "answer": ans,
                }) + "\n")
                # cross-seed consistency via stochastic decoding (only if >1 seed)
                if do_consistency:
                    seed_answers = []
                    for seed in cfg.seeds:
                        cs = generate(wrapper, tok, prompt, arm, max_new_tokens=cfg.max_new_tokens,
                                      temperature=0.7, top_p=0.9, top_k=50, seed=seed)
                        _, cans = _score(kind, cs["text"], row, metrics)
                        seed_answers.append(cans)
                    score_fp.write(json.dumps({
                        "set": set_name, "id": row["id"], "arm": arm.name,
                        "kind": kind, "metric": "seed_agreement",
                        "value": metrics.pairwise_agreement(seed_answers),
                    }) + "\n")
            print(f"  [{set_name}] {ei+1}/{len(rows)} "
                  f"({time.time()-t0:.0f}s)", flush=True)

            # Base-vs-wrapper logit diagnostics (teacher-forced on the prompt), per non-base arm.
            for arm in arms:
                if arm.name == "A_base":
                    continue
                d = prompt_logit_diag(wrapper, tok, prompt, base_arm, arm)
                d["adapter_weight_norm"] = _adapter_weight_norm(wrapper)
                diag_fp.write(json.dumps({
                    "set": set_name, "id": row["id"], "arm": arm.name, **d,
                }) + "\n")

            # B-vs-C logit separation: phase ON (B) vs phase OFF (C) on the SAME prompt.
            # KL(C||B) ~ 0 ⇒ the phase/Bhava dynamics add ~nothing beyond C's static offset.
            c_arm = next((a for a in arms if a.name == "C_phase_off"), None)
            b_arm = next((a for a in arms if a.name == "B_full"), None)
            if c_arm is not None and b_arm is not None:
                dbc = prompt_logit_diag(wrapper, tok, prompt, c_arm, b_arm)
                diag_fp.write(json.dumps({
                    "set": set_name, "id": row["id"], "arm": "B_vs_C", **dbc,
                }) + "\n")

        print(f"  [{set_name}] {len(rows)} examples done ({time.time()-t0:.0f}s elapsed)")

    gen_fp.close()
    score_fp.close()
    diag_fp.close()
    print(f"== artifacts written to {run_dir} ==")
    print("Next: python scripts/cg_wrapper_ablation/metrics_report.py", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
