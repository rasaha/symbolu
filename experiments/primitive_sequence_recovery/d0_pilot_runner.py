"""Track D — Stage D0 REAL pilot runner (RunPod GPU, local LLM). EXPLORATORY TRIAGE ONLY.

Runs the real D0 LLM-scored pilot with a LOCAL GPU model. HARD-GATED: refuses unless
D0_RUN_APPROVED=yes AND a frozen config bundle is provided. Emits ONLY LLM_PILOT_* labels;
never EXPERIENTIAL_WEATHER_SIGNAL / ONTOLOGICAL_SIGNAL / Sanskrit privilege. Does NOT touch
frozen/manifest.json, the readiness gate, the runner, or Stage A. A positive means only
"D1 human-blind validation may be worth funding" — never validation of Symbol-U.

Blinding: Stage 1 (profile generation) sees the dictionary MEANING only; Stage 2 (scoring) sees
anonymized comp_*/prof_* only; hidden keys never enter a prompt. Cross-model: generator ≠ scorer
(unless explicitly waived). Deterministic decoding. See TRACK_D_D0_* docs.

NOT runnable in the build sandbox (no GPU, no approval). This file is the RunPod executable.

Usage (on RunPod, after completing the approval checklist):
    D0_RUN_APPROVED=yes \
    D0_CONFIG=/workspace/d0_config.json \
    D0_GENERATOR_MODEL=<hf-id-A> D0_SCORER_MODEL=<hf-id-B> \
    python3 experiments/primitive_sequence_recovery/d0_pilot_runner.py --out /workspace/d0_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import re
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from track_d_d0_harness import (  # noqa: E402  (pure, data-agnostic helpers)
    validate_response, detect_contamination, score_case, LABELS, FORBIDDEN_LABELS, _ARMS, _BARNUM)

PRIMARY_DOMAINS = ("abstract_primary", "concrete_control")


# ----------------------------------------------------------------- hard gate --------
def _gate(config_path):
    if os.environ.get("D0_RUN_APPROVED", "").lower() not in ("yes", "true", "1"):
        sys.exit("REFUSED: D0_RUN_APPROVED != yes. Complete TRACK_D_D0_RUN_APPROVAL_CHECKLIST.md "
                 "and set D0_RUN_APPROVED=yes to run the real pilot.")
    if not config_path or not pathlib.Path(config_path).exists():
        sys.exit("REFUSED: D0_CONFIG missing. Provide the frozen input bundle (see "
                 "TRACK_D_D0_SCHEMAS.md); this runner does not fabricate inputs.")
    gen, sco = os.environ.get("D0_GENERATOR_MODEL", ""), os.environ.get("D0_SCORER_MODEL", "")
    if not gen or not sco:
        sys.exit("REFUSED: set D0_GENERATOR_MODEL and D0_SCORER_MODEL.")
    if gen == sco and os.environ.get("D0_WAIVE_CROSS_MODEL", "").lower() not in ("yes", "true", "1"):
        sys.exit("REFUSED: generator == scorer. Use distinct models or set "
                 "D0_WAIVE_CROSS_MODEL=yes (records a waiver; weakens the control).")
    return gen, sco


# ------------------------------------------------------------- local LLM adapter ----
def _load(model_id):
    import torch                                       # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto", device_map="auto")
    model.eval()
    return model, tok


def _chat(model, tok, system, user, max_new=512):
    import torch
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**ids, max_new_tokens=max_new, do_sample=False,   # deterministic
                             temperature=None, top_p=None, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ------------------------------------------------------ prompts (see TRACK_D_D0_PROMPTS) --
_SYS_GEN = ("You produce an experiential profile for an English word-meaning: the emotional "
            "atmosphere a person associates with it. Use ONLY descriptors from the controlled "
            "vocabulary. Choose 8-20. Avoid vague universals (energy, flow, resonance, life "
            "force). You are given ONLY an English meaning; do not guess any source language or "
            "word. Output STRICT JSON only: {\"descriptors\":[...]}")
_SYS_SCORE = ("You are given short token-strings ('compositions') and descriptor lists "
              "('profiles'). For each composition and profile output a match score in [0,1]. Do "
              "NOT identify, name, translate, or guess the language/origin of any composition. No "
              "commentary. Output STRICT JSON only: {\"scores\":{\"comp_1\":{\"prof_1\":0.0}}}")
_SYS_PROBE = ("You will see anonymized token-strings. Do you recognize what any of them is (a "
              "specific word, language, or concept)? Answer honestly. Output STRICT JSON only: "
              "{\"identified\":true|false,\"details\":[{\"comp_id\":\"\",\"guess\":\"\"}]}")


# -------------------------------------------------------- real packet builder -------
def build_packet_real(word, seed):
    """Anonymize a word's real/scrambled/decoy compositions + (target + I1..I4) profiles.
    `word` already carries rendered compositions and its Stage-1 profile + the barnum family."""
    rng = random.Random(seed)
    comps = [(a, word["compositions"][a]) for a in _ARMS]      # A/B/C already rendered upstream
    rng.shuffle(comps)
    comp_key, pcomps = {}, []
    for i, (arm, text) in enumerate(comps, 1):
        comp_key[f"comp_{i}"] = arm
        pcomps.append({"comp_id": f"comp_{i}", "text": text})
    profs = [("target", word["profile"])] + [(k, word["barnum"][k]) for k in _BARNUM]
    rng.shuffle(profs)
    prof_key, pprofs = {}, []
    for i, (name, desc) in enumerate(profs, 1):
        prof_key[f"prof_{i}"] = name
        pprofs.append({"profile_id": f"prof_{i}", "descriptors": desc})
    return {"compositions": pcomps, "profiles": pprofs}, {"comp": comp_key, "prof": prof_key}


# ------------------------------------------------------------------- pipeline --------
def stage1_profiles(cfg, gen_id):
    model, tok = _load(gen_id)
    vocab = cfg["controlled_vocabulary"]
    for w in cfg["words"]:
        # BLIND: meaning + pos only; never spelling / varṇa / glosses
        user = (f"meaning: \"{w['dictionary_meaning']}\"\npart_of_speech: \"{w.get('pos','')}\"\n"
                f"controlled_vocabulary: {vocab}\nReturn 8-20 descriptors from the vocabulary.")
        js = _extract_json(_chat(model, tok, _SYS_GEN, user)) or {}
        w["profile"] = [d for d in js.get("descriptors", []) if d in set(vocab)][:20]
    del model
    _free()
    return cfg


def stage2_and_probe(cfg, sco_id, seed):
    model, tok = _load(sco_id)
    for w in cfg["words"]:
        w["barnum"] = cfg["barnum"]
        packet, keys = build_packet_real(w, seed)
        w["_keys"] = keys
        # Stage 2 scoring (anonymized)
        user = json.dumps({"compositions": packet["compositions"], "profiles": packet["profiles"]})
        resp = _extract_json(_chat(model, tok, _SYS_SCORE, user, max_new=800))
        if resp is None:                                # one repair attempt
            fix = _chat(model, tok, "Reformat into valid JSON only; change no numbers.",
                        _chat(model, tok, _SYS_SCORE, user, max_new=800))
            resp = _extract_json(fix)
        # contamination probe (separate call, anonymized compositions only)
        probe = _extract_json(_chat(model, tok, _SYS_PROBE,
                                    json.dumps({"compositions": packet["compositions"]}))) or {}
        if resp is not None and probe.get("identified"):
            resp["contamination_identified"] = True
        w["_packet"], w["_response"] = packet, resp
    del model
    _free()
    return cfg


def _free():
    try:
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        pass


# ------------------------------------------------------------- metrics + labels -----
def _bootstrap_ci(vals, n=2000, seed=0):
    import numpy as np
    if not vals:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    a = np.array(vals, dtype=float)
    bs = [rng.choice(a, size=len(a), replace=True).mean() for _ in range(n)]
    return (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))


def analyze(cfg):
    per_word, errors_tax = [], {}
    for w in cfg["words"]:
        rec = {"word_id": w["word_id"], "domain": w["domain"],
               "contamination_tier": w.get("contamination_tier", "unknown")}
        packet, resp, keys = w.get("_packet"), w.get("_response"), w.get("_keys")
        verr = validate_response(resp, packet) if resp is not None else ["no response"]
        contaminated, creasons = detect_contamination(resp if isinstance(resp, dict) else {})
        rec["malformed"] = bool(verr)
        rec["contaminated"] = contaminated
        rec["contamination_reasons"] = creasons
        rec["metrics"] = None if verr else score_case(resp, keys)
        per_word.append(rec)
    return per_word


def _tax(per_word):
    """Diagnostic error taxonomy (see TRACK_D_D0_ERROR_TAXONOMY.md). Diagnostic only."""
    prim = [r for r in per_word if r["domain"] in PRIMARY_DOMAINS and r["metrics"]]
    absr = [r for r in prim if r["domain"] == "abstract_primary"]
    conc = [r for r in prim if r["domain"] == "concrete_control"]
    fam = [r for r in per_word if r["domain"] == "famous_exploratory" and r["metrics"]]
    tax = {}

    def mean(rs, k):
        xs = [r["metrics"][k] for r in rs]
        return sum(xs) / len(xs) if xs else float("nan")

    if absr and mean(absr, "A_vs_maxBarnum") <= 0:
        tax["BARNUM_OVERMATCH"] = True
    if absr and abs(mean(absr, "A_vs_B")) < 0.02:
        tax["SCRAMBLE_EQUIVALENT"] = True
    if absr and abs(mean(absr, "A_vs_C")) < 0.02:
        tax["DECOY_EQUIVALENT"] = True
    if conc and absr and mean(conc, "A_vs_maxBarnum") >= mean(absr, "A_vs_maxBarnum") - 0.02:
        tax["CONCRETE_OVERMATCH"] = True
    if fam and absr and mean(fam, "A_vs_maxBarnum") > 0 >= mean(absr, "A_vs_maxBarnum"):
        tax["FAMOUS_WORD_CONTAMINATION"] = True
    if any(r["contaminated"] for r in per_word):
        tax["SCORER_CONTAMINATION"] = True
    return tax


def assign_primary_label(per_word):
    prim_abs = [r for r in per_word
                if r["domain"] == "abstract_primary" and r["metrics"] and not r["malformed"]]
    conc = [r for r in per_word
            if r["domain"] == "concrete_control" and r["metrics"] and not r["malformed"]]
    # contamination on the PRIMARY set overrides
    if any(r["contaminated"] for r in per_word if r["domain"] in PRIMARY_DOMAINS):
        return "LLM_PILOT_CONTAMINATED"
    drop = sum(1 for r in per_word if r["domain"] in PRIMARY_DOMAINS and r["malformed"])
    total_primary = sum(1 for r in per_word if r["domain"] in PRIMARY_DOMAINS)
    if not prim_abs or (total_primary and drop / total_primary > 0.34):
        return "LLM_PILOT_INCONCLUSIVE"
    d_b = [r["metrics"]["A_vs_B"] for r in prim_abs]
    d_c = [r["metrics"]["A_vs_C"] for r in prim_abs]
    d_k = [r["metrics"]["A_vs_maxBarnum"] for r in prim_abs]
    ci_b, ci_c, ci_k = (_bootstrap_ci(d_b), _bootstrap_ci(d_c), _bootstrap_ci(d_k))
    # concrete control must NOT show a comparable positive
    conc_k = [r["metrics"]["A_vs_maxBarnum"] for r in conc]
    conc_ci = _bootstrap_ci(conc_k) if conc_k else (float("nan"), float("nan"))
    beats_all = ci_b[0] > 0 and ci_c[0] > 0 and ci_k[0] > 0
    concrete_clean = (not conc_k) or (conc_ci[0] <= 0)
    if beats_all and concrete_clean:
        return "LLM_PILOT_SUGGESTIVE"
    if (ci_k[1] <= 0) or (ci_b[1] <= 0):
        return "LLM_PILOT_NO_SIGNAL"
    return "LLM_PILOT_INCONCLUSIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="d0_report.json")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    gen, sco = _gate(os.environ.get("D0_CONFIG"))
    cfg = json.loads(pathlib.Path(os.environ["D0_CONFIG"]).read_text(encoding="utf-8"))

    cfg = stage1_profiles(cfg, gen)
    cfg = stage2_and_probe(cfg, sco, a.seed)
    per_word = analyze(cfg)
    label = assign_primary_label(per_word)
    assert label in LABELS and label not in FORBIDDEN_LABELS, label

    report = {"track": "D0_exploratory_pilot", "note": "TRIAGE ONLY; profiles are LLM-generated; "
              "not validation; never ONTOLOGICAL_SIGNAL; Track B remains BLOCKED.",
              "generator_model": gen, "scorer_model": sco, "models_distinct": gen != sco,
              "seed": a.seed, "primary_label": label,
              "error_taxonomy": _tax(per_word),
              "famous_subset_is_exploratory_only": True,
              "per_word": [{k: v for k, v in r.items() if not k.startswith("_")} for r in per_word]}
    pathlib.Path(a.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"primary_label": label, "error_taxonomy": report["error_taxonomy"],
                      "out": a.out}, indent=2))
    print("\nD0 real pilot: exploratory triage only. No validation. Track B remains blocked. "
          "Structure, not validated meaning.")


if __name__ == "__main__":
    main()
