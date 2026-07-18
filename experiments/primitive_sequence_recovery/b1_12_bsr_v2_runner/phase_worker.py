#!/usr/bin/env python3
"""V2 single-model INDEPENDENT judge worker: load ONE model, judge every word blind (no crossover, no other
model's output visible), write JSON, exit (frees GPU). Invoked as a subprocess by run_v2_independent.py so only
one model is resident at a time."""
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

def canon_relationships(obj, field="relationship"):
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

def call_validated(be, sysm, user, validate, raw, meta):
    reason = ""
    for attempt in range(1, MAX_RETRIES + 1):
        u = user if attempt == 1 else f"Your previous output was invalid ({reason}). Return corrected STRICT JSON only.\n\n{user}"
        out, h = be.generate(sysm, u)
        obj = extract_json(out)
        coercions = canon_relationships(obj) if obj is not None else []
        ok, reason = (False, "malformed_json") if obj is None else validate(obj)
        raw.append({**meta, "attempt": attempt, "valid": ok, "reason": reason, "coercions": coercions, **h, "raw": out})
        if ok:
            return obj
    return None

def do_judge(be, words, model_id, raw):
    profiles, scores = [], []
    for w in words:
        wo = word_occurrences(w["dev"])
        mapped = [o for o in wo["occurrences"] if o["is_mapped"]]
        occ = [o["occurrence_index"] for o in mapped]
        vn = {o["occurrence_index"]: o["varna"] for o in mapped}
        gl = {o["occurrence_index"]: o["mapping_gloss"] for o in mapped}
        sysm, user = PROMPTS.build_judge_prompt(w["iast"], w["dev"], w["gloss"], mapped)
        obj = call_validated(be, sysm, user, lambda o: R.validate_judge(o, occ), raw,
                             {"model": model_id, "word": w["iast"]})
        if obj is None:
            raise SystemExit(f"RUN_INVALID:judge_invalid:{w['iast']}")
        cs = [c["dbr_score"] for c in obj["components"]]
        agg = R.aggregate(cs)
        verdict = R.word_verdict(agg["mean"], agg["min"])
        profiles.append({"word": w["iast"], "gloss": w["gloss"], "judge_model": model_id, "profile": obj["profile"]})
        comps = []
        for c in obj["components"]:
            oi = c["occurrence_index"]
            comps.append({"word": w["iast"], "gloss": w["gloss"], "occurrence_index": oi, "varna": vn[oi],
                          "frozen_mapping": gl[oi], "relationship": c["relationship"], "dbr_score": c["dbr_score"],
                          "supporting_evidence": c["supporting_evidence"], "opposing_evidence": c["opposing_evidence"],
                          "adjudication": c["adjudication"], "judge_model": model_id})
        scores.append({"word": w["iast"], "gloss": w["gloss"], "category": w["category"], "judge_model": model_id,
                       "components": comps, "mean_dbr": agg["mean"], "min_dbr": agg["min"], "counts": agg["counts"],
                       "weak_components_le_25": agg["weak_components_le_25"], "verdict": verdict})
    return profiles, scores

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--wordlist", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-out", required=True)
    ap.add_argument("--seed", type=int, default=20260714)
    ap.add_argument("--qwen-thinking", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--gpu-mem-util", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=8192)
    a = ap.parse_args()

    words = sorted(json.load(open(a.wordlist, encoding="utf-8"))["words"], key=lambda x: x["iast"])
    be = backends.VLLMBackend(a.model, seed=a.seed, qwen_enable_thinking=a.qwen_thinking,
                              max_tokens=a.max_tokens, gpu_mem_util=a.gpu_mem_util, max_model_len=a.max_model_len)
    raw = []
    try:
        prof, sc = do_judge(be, words, a.model, raw)
        json.dump({"judge_model": a.model, "profiles": prof, "scores": sc},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    finally:
        with open(a.raw_out, "a", encoding="utf-8") as f:
            for r in raw:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("JUDGE_OK", a.model, len(words), "words")

if __name__ == "__main__":
    main()
