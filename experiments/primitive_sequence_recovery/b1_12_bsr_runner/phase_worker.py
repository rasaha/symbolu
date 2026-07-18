#!/usr/bin/env python3
"""Single-model worker: load ONE model (offline vLLM), run author and/or score jobs, write JSON, exit (frees GPU).

Invoked as a subprocess by run_sequential.py so that only one model is resident at a time (single-GPU friendly).
"""
from __future__ import annotations
import argparse, json, re, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bsr_rubric as R
import prompts as PROMPTS
from mappings import word_occurrences
import backends

MAX_RETRIES = 3

def extract_json(text):
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    s = t.find("{")
    if s < 0:
        return None
    depth = 0
    for i in range(s, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[s:i + 1])
                except Exception:
                    return None
    return None

def canon_relationships(obj, field):
    """Canonicalize orthographic typos in the controlled-vocab relationship token, in place.
    Returns a list of coercion records (empty if none) for transparent logging."""
    notes = []
    if not isinstance(obj, dict):
        return notes
    for c in obj.get("components", []) or []:
        if isinstance(c, dict) and field in c:
            canon, coerced = R.canonicalize_relationship(c[field])
            if coerced:
                notes.append({"occurrence_index": c.get("occurrence_index"), "field": field,
                              "from": c[field], "to": canon})
                c[field] = canon
    return notes

def call_validated(be, sysm, user, validate, raw, meta, rel_field=None):
    reason = ""
    for attempt in range(1, MAX_RETRIES + 1):
        u = user if attempt == 1 else f"Your previous output was invalid ({reason}). Return corrected STRICT JSON only.\n\n{user}"
        out, h = be.generate(sysm, u)
        obj = extract_json(out)
        coercions = canon_relationships(obj, rel_field) if (obj is not None and rel_field) else []
        ok, reason = (False, "malformed_json") if obj is None else validate(obj)
        raw.append({**meta, "attempt": attempt, "valid": ok, "reason": reason,
                    "coercions": coercions, **h, "raw": out})
        if ok:
            return obj
    return None

def do_author(be, words, model_id, run_id, raw):
    profiles, evidence = [], []
    for w in words:
        wo = word_occurrences(w["dev"])
        mapped = [o for o in wo["occurrences"] if o["is_mapped"]]
        occ = [o["occurrence_index"] for o in mapped]
        gl = {o["occurrence_index"]: o["mapping_gloss"] for o in mapped}
        vn = {o["occurrence_index"]: o["varna"] for o in mapped}
        sysm, user = PROMPTS.build_author_prompt(w["iast"], w["dev"], w["gloss"], mapped)
        obj = call_validated(be, sysm, user, lambda o: R.validate_author(o, occ), raw,
                             {"run": run_id, "role": "author", "model": model_id, "word": w["iast"]},
                             rel_field="proposed_relationship")
        if obj is None:
            raise SystemExit(f"RUN_INVALID:author_invalid:{w['iast']}")
        profiles.append({"run": run_id, "word": w["iast"], "gloss": w["gloss"],
                         "author_model": model_id, "profile": obj["profile"]})
        comps = [{"occurrence_index": c["occurrence_index"], "varna": vn[c["occurrence_index"]],
                  "mapping": gl[c["occurrence_index"]], "supporting_evidence": c["supporting_evidence"],
                  "opposing_evidence": c["opposing_evidence"], "proposed_relationship": c["proposed_relationship"]}
                 for c in obj["components"]]
        evidence.append({"run": run_id, "word": w["iast"], "author_model": model_id, "components": comps})
    return profiles, evidence

def do_score(be, words, model_id, run_id, author_data, raw):
    prof = {p["word"]: p for p in author_data["profiles"]}
    ev = {e["word"]: e for e in author_data["evidence"]}
    wl = {w["iast"]: w for w in words}
    scores = []
    for word in [p["word"] for p in author_data["profiles"]]:
        w = wl[word]
        acomps = ev[word]["components"]
        occ = [c["occurrence_index"] for c in acomps]
        gl = {c["occurrence_index"]: c["mapping"] for c in acomps}
        amap = {c["occurrence_index"]: c for c in acomps}
        sysm, user = PROMPTS.build_scorer_prompt(word, w["gloss"], prof[word]["profile"], acomps)
        obj = call_validated(be, sysm, user, lambda o: R.validate_scorer(o, occ, gl), raw,
                             {"run": run_id, "role": "score", "model": model_id, "word": word},
                             rel_field="final_relationship")
        if obj is None:
            raise SystemExit(f"RUN_INVALID:scorer_invalid:{word}")
        cs = [c["bsr_score"] for c in obj["components"]]
        agg = R.aggregate(cs)
        verdict = R.word_verdict(agg["mean"], agg["min"])
        cr = obj.get("combined_reconciliation")
        comps_out = []
        for c in obj["components"]:
            oi = c["occurrence_index"]; a = amap[oi]
            comps_out.append({"run_id": run_id, "word_id": word, "word": word, "gloss": w["gloss"],
                              "occurrence_index": oi, "varna": a["varna"], "frozen_mapping": a["mapping"],
                              "supporting_evidence": a["supporting_evidence"], "opposing_evidence": a["opposing_evidence"],
                              "proposed_relationship": a["proposed_relationship"], "final_relationship": c["final_relationship"],
                              "bsr_score": c["bsr_score"], "adjudication": c["adjudication"],
                              "evidence_author_model": author_data.get("author_model"), "scorer_model": model_id})
        scores.append({"run": run_id, "word": word, "gloss": w["gloss"], "category": w["category"],
                       "author_model": author_data.get("author_model"), "scorer_model": model_id,
                       "components": comps_out, "mean_bsr": agg["mean"], "min_bsr": agg["min"], "counts": agg["counts"],
                       "weak_components_le_25": agg["weak_components_le_25"], "combined_reconciliation": cr,
                       "holistic_only_resonance": R.holistic_only(cr, agg["mean"]), "verdict": verdict})
    return scores

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--jobs", required=True, help="JSON file: list of {run, role(author|score), author_file?, out}")
    ap.add_argument("--wordlist", required=True)
    ap.add_argument("--raw-out", required=True)
    ap.add_argument("--seed", type=int, default=20260714)
    ap.add_argument("--qwen-thinking", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--gpu-mem-util", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=8192)
    a = ap.parse_args()

    words = sorted(json.load(open(a.wordlist, encoding="utf-8"))["words"], key=lambda x: x["iast"])
    jobs = json.load(open(a.jobs, encoding="utf-8"))
    be = backends.VLLMBackend(a.model, seed=a.seed, qwen_enable_thinking=a.qwen_thinking,
                              max_tokens=a.max_tokens, gpu_mem_util=a.gpu_mem_util, max_model_len=a.max_model_len)
    raw = []
    try:
        for job in jobs:
            if job["role"] == "author":
                prof, ev = do_author(be, words, a.model, job["run"], raw)
                json.dump({"author_model": a.model, "profiles": prof, "evidence": ev},
                          open(job["out"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            else:
                ad = json.load(open(job["author_file"], encoding="utf-8"))
                sc = do_score(be, words, a.model, job["run"], ad, raw)
                json.dump({"scorer_model": a.model, "scores": sc},
                          open(job["out"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    finally:
        # always flush the raw log — even when a job aborts with RUN_INVALID — so failures are diagnosable
        with open(a.raw_out, "a", encoding="utf-8") as f:
            for r in raw:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("PHASE_OK", a.model, [j["role"] + ":" + j["run"] for j in jobs])

if __name__ == "__main__":
    main()
