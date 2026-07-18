#!/usr/bin/env python3
"""V2 single-GPU orchestrator — INDEPENDENT judgments (no author→scorer crossover).

Two sequential model loads (one resident at a time):
  1) Qwen    -> independent judge of all 20 words
  2) Mistral -> independent judge of all 20 words (blind to Qwen)
Then MECHANICAL Phase-4 aggregation comparing the two independent judgments. No interpretation here.

Usage on one 80GB GPU:
  python run_v2_independent.py --qwen Qwen/Qwen3-32B \
      --mistral mistralai/Mistral-Small-3.1-24B-Instruct-2503 --seed 20260714
"""
from __future__ import annotations
import argparse, json, subprocess, sys, pathlib, statistics
HERE = pathlib.Path(__file__).resolve().parent
EXPT = HERE.parent
OUT = EXPT / "results" / "b1_12_symbolic_resonance_v2"
sys.path.insert(0, str(HERE))
import verify_inputs, backends
import bsr_rubric as R
LABEL = "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE"

def dump(n, o):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / n).write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")

def run_judge(model, out_file, wl, args):
    if pathlib.Path(out_file).exists():
        try:
            json.load(open(out_file)); print("SKIP (resume)", model, out_file, flush=True); return
        except Exception:
            pass
    cmd = [sys.executable, str(HERE / "phase_worker.py"), "--model", model, "--wordlist", str(wl),
           "--out", str(out_file), "--raw-out", str(OUT / "raw_all.jsonl"),
           "--seed", str(args.seed), "--max-tokens", str(args.max_tokens),
           "--gpu-mem-util", str(args.gpu_mem_util), "--max-model-len", str(args.max_model_len)]
    if args.qwen_thinking and "qwen" in model.lower():
        cmd.append("--qwen-thinking")
    print(">>", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

def _comps(data):
    return {(c["word"], c["occurrence_index"]): c for s in data["scores"] for c in s["components"]}

def aggregate(qwen, mistral):
    """MECHANICAL comparison of two independent judgments (Qwen vs Mistral). No interpretation."""
    QC, MC = _comps(qwen), _comps(mistral)
    keys = sorted(set(QC) & set(MC))
    # --- component score agreement ---
    diffs = [QC[k]["dbr_score"] - MC[k]["dbr_score"] for k in keys]
    absd = [abs(d) for d in diffs]
    comp_agree = {
        "n_components": len(keys),
        "exact_agreement": round(sum(d == 0 for d in absd) / len(keys), 4),
        "within_one_step_agreement": round(sum(d <= 25 for d in absd) / len(keys), 4),
        "mean_abs_diff": round(statistics.mean(absd), 2),
        "median_abs_diff": round(statistics.median(absd), 2),
        "signed_mean_diff_Qwen_minus_Mistral": round(statistics.mean(diffs), 2),
    }
    # --- relationship agreement ---
    rel_rows, rc = [], {"exact": 0, "compatible": 0, "incompatible": 0}
    for k in keys:
        a = R.relationship_agreement(QC[k]["relationship"], MC[k]["relationship"]); rc[a] += 1
        rel_rows.append({"word": k[0], "occurrence_index": k[1], "rel_Qwen": QC[k]["relationship"],
                         "rel_Mistral": MC[k]["relationship"], "agreement": a})
    rel_agree = {**rc, "rows": rel_rows}
    # --- score distributions ---
    def dist(store):
        from collections import Counter
        c = Counter(v["dbr_score"] for v in store.values())
        return {str(s): c.get(s, 0) for s in R.BSR_SCALE}
    score_dist = {"Qwen": dist(QC), "Mistral": dist(MC)}
    # --- per-word verdict agreement ---
    QW = {s["word"]: s for s in qwen["scores"]}; MW = {s["word"]: s for s in mistral["scores"]}
    vrows, agree_n, sens = [], 0, []
    for w in sorted(QW):
        q, m = QW[w], MW[w]
        ag = q["verdict"] == m["verdict"]; agree_n += ag
        es = R.cross_run_word_indeterminate(q["verdict"], m["verdict"], q["mean_dbr"], m["mean_dbr"])
        if es: sens.append(w)
        vrows.append({"word": w, "category": q["category"], "verdict_Qwen": q["verdict"], "verdict_Mistral": m["verdict"],
                      "mean_Qwen": q["mean_dbr"], "mean_Mistral": m["mean_dbr"], "agree": ag, "model_sensitive": es})
    verdict_agree = {"exact_verdict_agreement": round(agree_n / len(QW), 4), "n_words": len(QW),
                     "rows": vrows, "model_sensitive_words": sens}
    # --- disagreement table (by |score diff|, desc) ---
    dis = sorted(({"word": k[0], "occurrence_index": k[1], "varna": QC[k]["varna"],
                   "score_Qwen": QC[k]["dbr_score"], "score_Mistral": MC[k]["dbr_score"],
                   "abs_diff": abs(QC[k]["dbr_score"] - MC[k]["dbr_score"]),
                   "rel_Qwen": QC[k]["relationship"], "rel_Mistral": MC[k]["relationship"]} for k in keys),
                  key=lambda r: -r["abs_diff"])
    strongest_dis = [r for r in dis if r["abs_diff"] >= 50]
    strongest_agree = [r for r in dis if r["abs_diff"] == 0 and r["score_Qwen"] >= 75]
    # --- profile agreement ---
    QP = {p["word"]: p for p in qwen["profiles"]}; MP = {p["word"]: p for p in mistral["profiles"]}
    prof_rows = []
    for w in sorted(QP):
        sim = R.profile_similarity(QP[w]["profile"], MP[w]["profile"])
        prof_rows.append({"word": w, "similarity": round(sim, 3), "agreement": R.profile_agreement_label(sim)})
    n_material = sum(1 for r in prof_rows if r["agreement"] == "material_difference")
    # --- model-identity dependence (reuses v1 role-dependence bands) ---
    one_step = comp_agree["within_one_step_agreement"]
    exact_verdict = verdict_agree["exact_verdict_agreement"]
    signed = comp_agree["signed_mean_diff_Qwen_minus_Mistral"]
    dep = R.role_dependence(exact_verdict, one_step, n_material, signed)
    return {
        "component_agreement": comp_agree, "relationship_agreement": rel_agree, "score_distributions": score_dist,
        "word_verdict_agreement": verdict_agree, "disagreement_table": dis, "strongest_disagreements": strongest_dis,
        "strongest_agreements": strongest_agree,
        "profile_agreement": {"material_disagreements": n_material, "rows": prof_rows},
        "model_identity_dependence": dep,
    }

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
        dump("run_manifest.json", {"schema": "b1_12_bsr_v2_run_manifest", "label": LABEL,
             "status": "RUN_INVALID_INPUT_MISMATCH", "reasons": det})
        print("RUN_INVALID_INPUT_MISMATCH", det); return
    dump("input_hashes.json", {"schema": "b1_12_bsr_v2_input_hashes", **det})

    ok, info = backends.availability(args.qwen, args.mistral, "vllm")
    if not ok:
        dump("run_manifest.json", {"schema": "b1_12_bsr_v2_run_manifest", "label": LABEL,
             "status": "BLOCKED_REQUIRED_MODEL_UNAVAILABLE", "availability": info})
        print("BLOCKED_REQUIRED_MODEL_UNAVAILABLE", info); return

    wl = verify_inputs.WORDLIST_JSON
    tmp = OUT / "_tmp"; tmp.mkdir(exist_ok=True)
    q_out, m_out = tmp / "qwen_judge.json", tmp / "mistral_judge.json"
    if not any(p.exists() for p in (q_out, m_out)) or not (OUT / "raw_all.jsonl").exists():
        (OUT / "raw_all.jsonl").write_text("", encoding="utf-8")

    run_judge(args.qwen, q_out, wl, args)
    run_judge(args.mistral, m_out, wl, args)

    qwen, mistral = json.load(open(q_out)), json.load(open(m_out))
    dump("qwen_profiles.json", {"label": LABEL, "profiles": qwen["profiles"]})
    dump("mistral_profiles.json", {"label": LABEL, "profiles": mistral["profiles"]})
    dump("qwen_scores.json", {"label": LABEL, "scores": qwen["scores"]})
    dump("mistral_scores.json", {"label": LABEL, "scores": mistral["scores"]})

    ag = aggregate(qwen, mistral)
    for name in ("component_agreement", "relationship_agreement", "word_verdict_agreement",
                 "score_distributions", "disagreement_table", "strongest_disagreements",
                 "strongest_agreements", "profile_agreement"):
        dump(f"{name}.json", ag[name])
    dump("summary_statistics.json", {"label": LABEL,
         "model_identity_dependence": ag["model_identity_dependence"],
         "component": ag["component_agreement"],
         "verdict": {"exact_verdict_agreement": ag["word_verdict_agreement"]["exact_verdict_agreement"],
                     "model_sensitive_words": ag["word_verdict_agreement"]["model_sensitive_words"]},
         "relationship": {k: ag["relationship_agreement"][k] for k in ("exact", "compatible", "incompatible")},
         "score_distributions": ag["score_distributions"],
         "profile_material_disagreements": ag["profile_agreement"]["material_disagreements"],
         "n_strongest_disagreements_ge50": len(ag["strongest_disagreements"])})

    dump("model_manifest.json", {"schema": "b1_12_bsr_v2_model_manifest", "label": LABEL,
         "mode": "vllm_independent_two_model_no_crossover",
         "qwen": {"model_id": args.qwen, "family": "Qwen3", "param_class": "~30-32B",
                  "reasoning_mode": ("thinking" if args.qwen_thinking else "non_thinking")},
         "mistral": {"model_id": args.mistral, "family": "Mistral Small 3.x", "param_class": "~24B",
                     "load_format": "mistral"},
         "decoding": {"temperature": 0.0, "top_p": 1.0, "top_k": -1, "repetition_penalty": 1.0,
                      "seed": args.seed, "max_tokens": args.max_tokens, "dtype": "bfloat16"},
         "loads": "2 sequential independent judges (Qwen; Mistral) — one model resident at a time; NO crossover",
         "independence": "each model judged all words blind to the other's evidence/relationship/score/verdict",
         "substitution_policy": "PROHIBITED"})
    dump("wordlist_manifest.json", json.load(open(verify_inputs.WORDLIST_DIR / "wordlist_manifest.json", encoding="utf-8")))
    dump("run_manifest.json", {"schema": "b1_12_bsr_v2_run_manifest", "label": LABEL, "status": "COMPLETED",
         "mode": "vllm_independent_two_model_no_crossover",
         "controlling_preregistration": "VARNA_SYMBOLIC_RESONANCE_PREREG_V2_1.md",
         "amends": "VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md",
         "freeze_record": "B1_12_V2_1_PREREG_FREEZE.md",
         "wordlist_sha256": det["wordlist_sha256"], "model_identity_dependence": ag["model_identity_dependence"],
         "no_forced_consensus": True})
    print("COMPLETED model_identity_dependence=", ag["model_identity_dependence"])

if __name__ == "__main__":
    main()
