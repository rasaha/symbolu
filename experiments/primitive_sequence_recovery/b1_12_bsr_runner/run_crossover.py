#!/usr/bin/env python3
"""B1.12 Bare-Word Symbolic Resonance — two-LLM crossover runner (RunPod).

Run A: Qwen authors profile+evidence -> Mistral scores.
Run B: Mistral authors profile+evidence -> Qwen scores.  (fresh, no Run-A context)
Deterministic aggregation + agreement + frozen role-dependence. No forced consensus.

Usage (on RunPod, GPU + vLLM):
  python run_crossover.py --mode vllm --qwen Qwen/Qwen3-32B \
      --mistral mistralai/Mistral-Small-3.1-24B-Instruct-2503 --seed 20260714
"""
from __future__ import annotations
import argparse, json, hashlib, pathlib, re, statistics, sys

HERE = pathlib.Path(__file__).resolve().parent
EXPT = HERE.parent
OUTDIR = EXPT / "results" / "b1_12_symbolic_resonance_multillm_v1"
sys.path.insert(0, str(HERE))

import bsr_rubric as R
import prompts as PROMPTS
from mappings import word_occurrences
import verify_inputs
import backends

LABEL = "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE"
MAX_RETRIES = 3

def _dump(name, obj):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _jsonl(name, rows):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with open(OUTDIR / name, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def extract_json(text):
    """Extract the first balanced top-level JSON object from model text (tolerates ``` fences / prose)."""
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None

def call_validated(backend, system, user, validate_fn, raw_log, meta, retry_prefix=""):
    """Generate -> extract -> validate, retrying (with corrective note) only for structural invalidity."""
    reason = ""
    for attempt in range(1, MAX_RETRIES + 1):
        u = user if attempt == 1 else f"{retry_prefix}Your previous output was invalid ({reason}). Return corrected STRICT JSON only.\n\n{user}"
        out, hsh = backend.generate(system, u)
        obj = extract_json(out)
        ok, reason = (False, "malformed_json") if obj is None else validate_fn(obj)
        raw_log.append({**meta, "attempt": attempt, "valid": ok, "reason": reason,
                        "prompt_sha256": hsh["prompt_sha256"], "output_sha256": hsh["output_sha256"], "raw": out})
        if ok:
            return obj, hsh, attempt, ""
    return None, None, MAX_RETRIES, reason

def run_direction(words, author_backend, scorer_backend, author_model, scorer_model, run_id):
    """Author phase then score phase (one model in memory at a time is the caller's concern)."""
    profiles, evidence, scores, model_inputs, raw = [], [], [], [], []
    occ_by_word = {}
    for w in words:
        wo = word_occurrences(w["dev"])
        mapped = [o for o in wo["occurrences"] if o["is_mapped"]]
        occ_by_word[w["iast"]] = mapped
        occ_idx = [o["occurrence_index"] for o in mapped]
        frozen_glosses = {o["occurrence_index"]: o["mapping_gloss"] for o in mapped}
        # ---- author ----
        a_sys, a_user = PROMPTS.build_author_prompt(w["iast"], w["dev"], w["gloss"], mapped)
        model_inputs.append({"run": run_id, "phase": "author", "word": w["iast"], "author_model": author_model,
                             "system_sha256": backends.sha_text(a_sys), "user_sha256": backends.sha_text(a_user)})
        aobj, ahsh, aattempt, aerr = call_validated(
            author_backend, a_sys, a_user, lambda o: R.validate_author(o, occ_idx), raw,
            {"run": run_id, "role": "author", "model": author_model, "word": w["iast"]})
        if aobj is None:
            return None, f"RUN_INVALID:author_invalid:{w['iast']}:{aerr}"
        profiles.append({"run": run_id, "word": w["iast"], "gloss": w["gloss"], "author_model": author_model,
                         "profile": aobj["profile"]})
        acomps = []
        for c in aobj["components"]:
            oi = c["occurrence_index"]
            acomps.append({"occurrence_index": oi, "varna": frozen_glosses and next(o["varna"] for o in mapped if o["occurrence_index"] == oi),
                           "mapping": frozen_glosses[oi], "supporting_evidence": c["supporting_evidence"],
                           "opposing_evidence": c["opposing_evidence"], "proposed_relationship": c["proposed_relationship"]})
        evidence.append({"run": run_id, "word": w["iast"], "author_model": author_model, "components": acomps})
        # ---- scorer ----
        s_sys, s_user = PROMPTS.build_scorer_prompt(w["iast"], w["gloss"], aobj["profile"], acomps)
        model_inputs.append({"run": run_id, "phase": "scorer", "word": w["iast"], "scorer_model": scorer_model,
                             "system_sha256": backends.sha_text(s_sys), "user_sha256": backends.sha_text(s_user)})
        sobj, shsh, sattempt, serr = call_validated(
            scorer_backend, s_sys, s_user, lambda o: R.validate_scorer(o, occ_idx, frozen_glosses), raw,
            {"run": run_id, "role": "scorer", "model": scorer_model, "word": w["iast"]})
        if sobj is None:
            return None, f"RUN_INVALID:scorer_invalid:{w['iast']}:{serr}"
        comp_scores = [c["bsr_score"] for c in sobj["components"]]
        agg = R.aggregate(comp_scores)
        verdict = R.word_verdict(agg["mean"], agg["min"])
        cr = sobj.get("combined_reconciliation")
        comps_out = []
        amap = {c["occurrence_index"]: c for c in acomps}
        for c in sobj["components"]:
            oi = c["occurrence_index"]; a = amap[oi]
            comps_out.append({
                "run_id": run_id, "word_id": w["iast"], "word": w["iast"], "gloss": w["gloss"],
                "occurrence_index": oi, "varna": a["varna"], "frozen_mapping": a["mapping"],
                "supporting_evidence": a["supporting_evidence"], "opposing_evidence": a["opposing_evidence"],
                "proposed_relationship": a["proposed_relationship"], "final_relationship": c["final_relationship"],
                "bsr_score": c["bsr_score"], "adjudication": c["adjudication"],
                "evidence_author_model": author_model, "scorer_model": scorer_model})
        scores.append({"run": run_id, "word": w["iast"], "gloss": w["gloss"], "category": w["category"],
                       "author_model": author_model, "scorer_model": scorer_model,
                       "components": comps_out, "mean_bsr": agg["mean"], "min_bsr": agg["min"],
                       "counts": agg["counts"], "weak_components_le_25": agg["weak_components_le_25"],
                       "combined_reconciliation": cr, "holistic_only_resonance": R.holistic_only(cr, agg["mean"]),
                       "verdict": verdict})
    return {"profiles": profiles, "evidence": evidence, "scores": scores, "model_inputs": model_inputs, "raw": raw,
            "occ_by_word": occ_by_word}, "OK"

def agreement(run_a, run_b):
    sa = {s["word"]: s for s in run_a["scores"]}
    sb = {s["word"]: s for s in run_b["scores"]}
    pa = {p["word"]: p for p in run_a["profiles"]}
    pb = {p["word"]: p for p in run_b["profiles"]}
    comp_rows, rel_rows, diffs, signed = [], [], [], []
    exact_c = one_step_c = tot_c = 0
    for w in sa:
        ca = {c["occurrence_index"]: c for c in sa[w]["components"]}
        cb = {c["occurrence_index"]: c for c in sb[w]["components"]}
        for oi in sorted(set(ca) & set(cb)):
            A, B = ca[oi], cb[oi]
            st = R.score_step_agreement(A["bsr_score"], B["bsr_score"])
            tot_c += 1; exact_c += st["exact"]; one_step_c += st["within_one_step"]
            signed.append(A["bsr_score"] - B["bsr_score"])
            if st["ge50"]:
                diffs.append({"word": w, "occurrence_index": oi, "score_A": A["bsr_score"], "score_B": B["bsr_score"]})
            comp_rows.append({"word": w, "occurrence_index": oi, "varna": A["varna"],
                              "score_A": A["bsr_score"], "score_B": B["bsr_score"], "abs_diff": st["abs_diff"]})
            rel_rows.append({"word": w, "occurrence_index": oi, "rel_A": A["final_relationship"],
                             "rel_B": B["final_relationship"],
                             "agreement": R.relationship_agreement(A["final_relationship"], B["final_relationship"])})
    absdiffs = [c["abs_diff"] for c in comp_rows]
    # verdicts
    vrows, exact_v, tot_v = [], 0, 0
    evaluator_sensitive = []
    for w in sa:
        va, vb = sa[w]["verdict"], sb[w]["verdict"]
        tot_v += 1; exact_v += (va == vb)
        indet = R.cross_run_word_indeterminate(va, vb, sa[w]["mean_bsr"], sb[w]["mean_bsr"])
        if indet:
            evaluator_sensitive.append(w)
        vrows.append({"word": w, "category": sa[w]["category"], "verdict_A": va, "verdict_B": vb,
                      "mean_A": sa[w]["mean_bsr"], "mean_B": sb[w]["mean_bsr"],
                      "agree": va == vb, "evaluator_sensitive": indet})
    # profiles
    prows, material = [], 0
    for w in pa:
        sim = R.profile_similarity(pa[w]["profile"], pb[w]["profile"])
        lab = R.profile_agreement_label(sim)
        material += (lab == "material_difference")
        prows.append({"word": w, "similarity": round(sim, 3), "agreement": lab})
    exact_va = exact_v / tot_v if tot_v else 0.0
    one_step_ca = one_step_c / tot_c if tot_c else 0.0
    signed_mean = statistics.fmean(signed) if signed else 0.0
    role = R.role_dependence(exact_va, one_step_ca, material, signed_mean)
    return {
        "component_agreement": {
            "n_components": tot_c, "exact_agreement": round(exact_c / tot_c, 3) if tot_c else 0.0,
            "within_one_step_agreement": round(one_step_ca, 3),
            "mean_abs_diff": round(statistics.fmean(absdiffs), 2) if absdiffs else 0.0,
            "median_abs_diff": (statistics.median(absdiffs) if absdiffs else 0.0),
            "signed_mean_diff_A_minus_B": round(signed_mean, 2),
            "disagreements_ge50": diffs, "rows": comp_rows},
        "relationship_agreement": {
            "exact": sum(1 for r in rel_rows if r["agreement"] == "exact"),
            "compatible": sum(1 for r in rel_rows if r["agreement"] == "compatible"),
            "incompatible": sum(1 for r in rel_rows if r["agreement"] == "incompatible"),
            "rows": rel_rows},
        "word_verdict_agreement": {
            "exact_verdict_agreement": round(exact_va, 3),
            "n_words": tot_v, "rows": vrows, "evaluator_sensitive_words": evaluator_sensitive},
        "profile_agreement": {"material_disagreements": material, "rows": prows},
        "role_dependence": role,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["vllm", "openai"], default="vllm")
    ap.add_argument("--qwen", default=backends.QWEN_DEFAULT)
    ap.add_argument("--mistral", default=backends.MISTRAL_DEFAULT)
    ap.add_argument("--seed", type=int, default=20260714)
    ap.add_argument("--qwen-base-url", default=None)
    ap.add_argument("--mistral-base-url", default=None)
    ap.add_argument("--qwen-thinking", action="store_true", help="fixed Qwen reasoning mode ON (default OFF)")
    ap.add_argument("--max-tokens", type=int, default=2048)
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)

    # ---- Gate: hard input verification ----
    vstatus, vdet = verify_inputs.verify()
    if vstatus != "OK":
        _dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL,
              "status": "RUN_INVALID_INPUT_MISMATCH", "reasons": vdet})
        print("RUN_INVALID_INPUT_MISMATCH", vdet); return "RUN_INVALID_INPUT_MISMATCH"
    _dump("input_hashes.json", {"schema": "b1_12_bsr_input_hashes_v1", **vdet})

    # ---- Gate: required models available (no substitution) ----
    ok, ainfo = backends.availability(args.qwen, args.mistral, args.mode)
    if not ok:
        _dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL,
              "status": "BLOCKED_REQUIRED_MODEL_UNAVAILABLE", "availability": ainfo})
        print("BLOCKED_REQUIRED_MODEL_UNAVAILABLE", ainfo); return "BLOCKED_REQUIRED_MODEL_UNAVAILABLE"

    words = json.load(open(verify_inputs.WORDLIST_JSON, encoding="utf-8"))["words"]
    words = sorted(words, key=lambda x: x["iast"])

    model_manifest = {
        "schema": "b1_12_bsr_model_manifest_v1", "label": LABEL, "mode": args.mode,
        "qwen": {"model_id": args.qwen, "family": "Qwen3", "param_class": "~30-32B",
                 "reasoning_mode": ("thinking" if args.qwen_thinking else "non_thinking")},
        "mistral": {"model_id": args.mistral, "family": "Mistral Small 3.x", "param_class": "~24B"},
        "decoding": {"temperature": 0.0, "top_p": 1.0, "top_k": -1, "repetition_penalty": 1.0,
                     "seed": args.seed, "max_tokens": args.max_tokens, "dtype": "bfloat16"},
        "determinism": "greedy (temp=0), fixed seed, identical settings across all words; one fixed Qwen mode",
        "substitution_policy": "PROHIBITED",
    }
    _dump("model_manifest.json", model_manifest)
    _dump("wordlist_manifest.json", json.load(open(verify_inputs.WORDLIST_DIR / "wordlist_manifest.json", encoding="utf-8")))

    def make(model_id):
        if args.mode == "vllm":
            return backends.VLLMBackend(model_id, seed=args.seed, qwen_enable_thinking=args.qwen_thinking,
                                        max_tokens=args.max_tokens)
        base = args.qwen_base_url if "qwen" in model_id.lower() else args.mistral_base_url
        return backends.OpenAICompatBackend(model_id, base, seed=args.seed, max_tokens=args.max_tokens,
                                            qwen_enable_thinking=args.qwen_thinking)

    # ---- Run A: Qwen author -> Mistral scorer ----
    qwen = make(args.qwen)
    run_a_author = qwen
    mistral = make(args.mistral)
    run_a, st = run_direction(words, run_a_author, mistral, args.qwen, args.mistral, "A")
    if run_a is None:
        _dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL, "status": st})
        print(st); return "RUN_INVALID"

    # ---- Run B: Mistral author -> Qwen scorer (fresh; no Run-A context) ----
    run_b, st = run_direction(words, mistral, qwen, args.mistral, args.qwen, "B")
    if run_b is None:
        _dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL, "status": st})
        print(st); return "RUN_INVALID"

    # ---- emit per-run artifacts ----
    for tag, run in (("a", run_a), ("b", run_b)):
        _dump(f"run_{tag}_profiles.json", {"label": LABEL, "profiles": run["profiles"]})
        _dump(f"run_{tag}_evidence.json", {"label": LABEL, "evidence": run["evidence"]})
        _dump(f"run_{tag}_scores.json", {"label": LABEL, "scores": run["scores"]})
        _dump(f"run_{tag}_model_inputs.json", {"label": LABEL, "inputs": run["model_inputs"]})
        _jsonl(f"run_{tag}_raw_outputs.jsonl", run["raw"])

    # ---- agreement + role dependence ----
    ag = agreement(run_a, run_b)
    _dump("component_agreement.json", ag["component_agreement"])
    _dump("relationship_agreement.json", ag["relationship_agreement"])
    _dump("word_verdict_agreement.json", ag["word_verdict_agreement"])
    _dump("role_dependence_summary.json", {"role_dependence": ag["role_dependence"],
          "profile_agreement": ag["profile_agreement"],
          "component_summary": {k: ag["component_agreement"][k] for k in
              ("n_components", "exact_agreement", "within_one_step_agreement", "mean_abs_diff",
               "median_abs_diff", "signed_mean_diff_A_minus_B")},
          "verdict_summary": {"exact_verdict_agreement": ag["word_verdict_agreement"]["exact_verdict_agreement"],
                              "evaluator_sensitive_words": ag["word_verdict_agreement"]["evaluator_sensitive_words"]}})

    _dump("run_manifest.json", {"schema": "b1_12_bsr_run_manifest_v1", "label": LABEL, "status": "COMPLETED",
          "controlling_preregistration": "VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md",
          "verdict_role_freeze": "B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md",
          "wordlist_sha256": vdet["wordlist_sha256"], "role_dependence": ag["role_dependence"],
          "no_forced_consensus": True})
    print("COMPLETED role_dependence=", ag["role_dependence"])
    return "COMPLETED"

if __name__ == "__main__":
    main()
