"""Native Sanskrit word-specificity PREREGISTRATION freeze generator (docs/data-only).

Freezes the study design controlled by the native Gate-G0 pass (commit 794ecaa4). This authors NO experiment, calls
NO judge, generates NO result. It fixes the two word sets, renders the TRUE confirmatory packets (vṛtti glosses
only — NO consonant symbols, NO Devanāgarī/IAST — to block letter matching), and pins the renderer / arm / evaluator
/ randomization / analysis / outcome specifications. Packets use ONLY confirmatory consonant rows; authored vowels/
markers are excluded. Structure, not validated meaning. B1.10 pole-legibility negative and the qualitative guarded
prior are preserved; no positive word-specificity claim exists before the run.
"""
import hashlib
import itertools
import json
import pathlib

import b1_native_gate_g0 as G

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
OUT = HERE / "native_word_specificity_prereg"
CB = {r["canonical_parser_unit"]: (r["binding_vritti"], r["liberating_vritti"]) for r in MERGED["rows"]
      if r["category"] == "consonant" and r.get("source_key") and r["activation_scope"] == "CONFIRMATORY_BACKBONE"}

SET_A = ["aśva", "bala", "bhaya", "duḥkha", "gaja", "megha"]
# independently-sourced conventional dictionary glosses (NOT derived from the varṇa mapping)
GLOSS = {"aśva": "a horse", "bala": "strength / power", "bhaya": "fear", "duḥkha": "suffering / pain",
         "gaja": "an elephant", "megha": "a cloud",
         "bīja": "a seed", "sukha": "happiness / ease", "deha": "the body", "lavaṇa": "salt",
         "yoga": "union / disciplined practice", "vṛkṣa": "a tree"}


def select_set_B():
    """Deterministic Set-B rule: from eligible words NOT in Set A, the alphabetically/overlap-first six-word set with
    0 < max_jaccard <= 0.34, length-non-identifying, a same-valence pair, no rare-only unique feature."""
    elig = G.eligible()
    for r in elig:
        r["mean_overlap"] = sum(G.jac(r["cons_set"], o["cons_set"]) for o in elig if o is not r) / max(1, len(elig) - 1)
    by = {r["iast"]: r for r in elig}
    pool = [r["iast"] for r in sorted((r for r in elig if r["iast"] not in SET_A),
                                      key=lambda r: (r["mean_overlap"], r["iast"]))[:30]]
    best = None
    for combo in itertools.combinations(pool, 6):
        ev = G.evaluate_set([by[w] for w in combo])
        if (ev["eligible"] and 0 < ev["max_jaccard"] <= 0.34 and ev["c56_length_not_identifying"]
                and ev["c8_same_valence_pair"] and not ev["rare_only_unique_words"]):
            key = (round(ev["max_jaccard"], 3), round(ev["mean_jaccard"], 3), combo)
            if best is None or key < best[0]:
                best = (key, list(combo), ev)
    return best[1], best[2], by


def render_packet(cons_seq):
    """FIXED renderer: per consonant in source order, both poles (binding + liberating) — NO consonant symbol."""
    feats = []
    for i, c in enumerate(cons_seq):
        b, l = CB[c]
        feats.append({"feature_index": i, "binding": b, "liberating": l})  # NO 'unit'/consonant symbol
    return feats


def word_packet(iast, by):
    seq = by[iast]["cons_seq"]
    return {"iast": iast, "gloss": GLOSS[iast], "n_features": len(seq), "packet_features": render_packet(seq),
            "consonant_count": len(set(seq)), "missing_r_consonant_only": by[iast]["missing_r_but_consonant_only"],
            "valence_balance": by[iast]["valence"]}


def build():
    OUT.mkdir(exist_ok=True)
    set_b, ev_b, by = select_set_B()

    packets_A = {w: word_packet(w, by) for w in SET_A}
    packets_B = {w: word_packet(w, by) for w in set_b}

    # freeze manifests
    (OUT / "set_A_manifest.json").write_text(json.dumps(
        {"set": "A_maximally_distinct_feasibility", "source": "Gate-G0 selected set (commit 794ecaa4)",
         "words": SET_A, "packets": packets_A,
         "properties": {"max_jaccard": 0.0, "mean_jaccard": 0.0, "length_non_identifying": True,
                        "same_valence_pair": ["bhaya", "duḥkha"], "disjoint_consonant_packets": True}},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "set_B_manifest.json").write_text(json.dumps(
        {"set": "B_harder_replication",
         "selection_rule": "from eligible words NOT in Set A, the deterministic (overlap-then-alphabetical) six-word "
                           "set with 0 < max_jaccard <= 0.34, length-non-identifying, >=1 same-valence pair, no "
                           "rare-only unique feature; fixed BEFORE any evaluator sees packets; not selected by fit.",
         "words": set_b, "packets": packets_B,
         "properties": {"max_jaccard": ev_b["max_jaccard"], "mean_jaccard": ev_b["mean_jaccard"],
                        "length_non_identifying": ev_b["c56_length_not_identifying"],
                        "same_valence_pair": [w for w in set_b if by[w]["valence"] == "pos"][:2],
                        "bounded_nonzero_overlap": True}},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # renderer spec
    (OUT / "packet_rendering_spec.json").write_text(json.dumps({
        "renderer_id": "confirmatory_dual_pole_v1",
        "rules": ["one fixed renderer for all words and arms",
                  "per consonant, in SOURCE order, emit BOTH binding and liberating rows (fixed dual-pole schema)",
                  "NEVER choose polarity per word; NEVER paraphrase rows per word (identical paraphrase table across words); NO bespoke prose synthesis",
                  "preserve packet length (feature count == consonant count)",
                  "NO consonant symbol, NO Devanāgarī, NO IAST in the rendered packet (leakage block)",
                  "EVALUATOR-FACING render is ENGLISH-ONLY: strip/paraphrase every Sanskrit vṛtti proper-name "
                  "(e.g. 'avajñā', 'kruratā', 'karuṇā') so no source-language term that could be reverse-mapped to a "
                  "consonant appears; authored blind at the packet-authoring-and-freeze step and hash-pinned",
                  "identical formatting across words and arms",
                  "row order fixed to source order; order tested only via the secondary S / O arms"],
        "raw_mapped_rows_note": "the SET manifests freeze the RAW mapped rows (provenance). The evaluator-facing "
                                "English-only render is a fixed, blind, table-driven paraphrase of those rows, "
                                "authored + frozen at the next step (that is why readiness is PACKET_AUTHORING_AND_FREEZE).",
        "example_raw_packet_bala": packets_A["bala"]["packet_features"],
        "leakage_guarantee": "evaluator sees English-only descriptive vṛtti content; NO consonant symbol, NO Sanskrit "
                             "vṛtti proper-name, NO spelling — identity is never directly shown"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # explicit leakage controls
    (OUT / "leakage_controls.json").write_text(json.dumps({
        "blocked_shortcuts": {
            "direct_orthographic_matching": "no Devanāgarī shown to evaluator",
            "direct_iast_consonant_matching": "no IAST / consonant symbol shown; candidates are English glosses only",
            "packet_length_identification": "sets are length-non-identifying (each length shared by >=2 words)",
            "unique_word_length_identification": "same as above",
            "rare_consonant_singleton_lookup": "sets have no rare-only unique feature; and consonant symbols are hidden",
            "valence_only_matching": "dual-pole render shows BOTH poles per feature; G/R controls carry matched valence; primary contrast nets valence out",
            "dictionary_gloss_sentiment_matching": "candidate glosses are neutral dictionary definitions; F/G controls estimate sentiment shortcut",
            "sanskrit_vritti_name_reverse_map": "evaluator-facing render is ENGLISH-ONLY (Sanskrit vṛtti proper-names stripped/paraphrased)",
            "evaluator_knowledge_of_set_construction": "evaluators blind to set-construction, arm identity, mapping keys, repository"},
        "set_A_disjoint_note": "Set A packets are fully disjoint consonants, but consonant identity is NEVER shown; the "
                               "English-only vṛtti render + English-gloss candidates prevent inferring identity from visible names",
        "residual_vectors_to_resolve_at_authoring": [
            "author the fixed English-only paraphrase table (blind) and hash-pin it",
            "verify no paraphrase row accidentally names its word's referent or a near-synonym of the gloss"]},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # arm / control spec
    (OUT / "arm_control_spec.json").write_text(json.dumps({"arms": {
        "T_true": "the correct frozen packet for the target word",
        "X_cross_word_mismatch": "a packet from another word in the SAME six-word set, assigned by a frozen derangement (seed 20260901)",
        "S_scrambled_order": "the correct packet's rows in a permuted order (membership preserved); informative only for >1-consonant words; NOT overinterpreted for disjoint Set A",
        "R_random_varna_assignment": "structure-preserving randomized consonant→row assignment; preserve feature count, consonant-class distribution where possible, marginal pole-gloss valence, frequency band; K=200 frozen randomizations (seed 20260902)",
        "G_generic_matched": "a generic packet matched for feature count, gloss length, valence, formatting; not tied to any word (seed 20260903)",
        "F_feature_only": "structural metadata only (feature count / frequency class), NO semantic rows — estimates the shortcut ceiling",
        "O_order_ablation_optional": "bag-of-consonants vs ordered sequence; only if the renderer preserves order meaningfully; SECONDARY"},
        "control_arms_in_primary_contrast": ["X_cross_word_mismatch", "R_random_varna_assignment", "G_generic_matched", "F_feature_only"]},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # evaluator prompt spec
    (OUT / "evaluator_prompt_spec.json").write_text(json.dumps({
        "task": "closed six-way forced-choice word identification",
        "candidate_representation": "anonymized ID (W1..W6, order randomized per trial by frozen seed) + independently-sourced ENGLISH dictionary gloss ONLY",
        "candidate_representation_rationale": "no Devanāgarī / IAST / spelling shown → the task cannot be solved by matching visible phonemes; the packet shows vṛtti glosses, never consonant symbols",
        "trial": ["present ONE rendered packet", "present the six candidate IDs + glosses in frozen-seed-randomized order",
                  "ask which candidate the packet belongs to", "require exactly ONE choice", "NO open-ended plausibility prose as the endpoint"],
        "evaluators": {"policy": "at least 3 FAMILY-DIVERSE, blind LLM evaluators; family-disjoint from any authoring model; human evaluation deferred per project policy",
                       "temperature": 0, "repeats": "N>=? per (packet,arm) with candidate order reshuffled per frozen seed",
                       "blind_to": ["arm identity", "mapping keys", "repository", "which packet is 'true'", "Devanāgarī/IAST/consonant symbols"]},
        "determinism": "fixed prompt template, fixed seeds for candidate order and repeats"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # randomization manifest schema (seeds pinned; packets generated at freeze/author time, not here)
    (OUT / "randomization_manifest_schema.json").write_text(json.dumps({
        "fields": ["derangement_seed", "random_assignment_seed", "n_random_assignments", "generic_seed",
                   "candidate_order_seed", "repeat_seed", "per_trial_candidate_order", "per_arm_packet_map"],
        "pinned_seeds": {"derangement": 20260901, "random_varna_assignment": 20260902, "generic": 20260903,
                         "candidate_order": 20260904, "repeats": 20260905},
        "note": "seeds + methods are pinned here; the actual randomized packets are generated at the separate "
                "packet-authoring-and-freeze step and hash-pinned then."},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # analysis plan
    (OUT / "analysis_plan.json").write_text(json.dumps({
        "primary_endpoint": "six-way forced-choice accuracy by arm (chance = 1/6 ≈ 0.1667)",
        "primary_contrast": "Delta = Accuracy(T) - max(Accuracy(X), Accuracy(R), Accuracy(G), Accuracy(F))",
        "primary_statistic": "paired CLUSTER bootstrap over WORDS (resample words with replacement, 10000 resamples), BCa 95% CI on Delta",
        "per_arm_ci": "exact binomial (Clopper-Pearson) 95% CI on each arm's accuracy",
        "confirmatory_test": "permutation test over packet↔word assignment (>=10000 permutations) → p-value for Delta",
        "secondary_model": "mixed-effects logistic (correct ~ arm + (1|word) + (1|evaluator_family)) IF sample size supports; else omitted",
        "minimum_effect_margin": {"delta_point": ">= 0.15", "delta_ci_lower": "> 0"},
        "multiplicity": "secondary endpoints labelled exploratory or Holm-corrected; primary is the single Delta",
        "no_rescue": "no selecting best evaluator/set/polarity/metric post hoc; primary is fixed"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # outcome taxonomy
    (OUT / "outcome_taxonomy.json").write_text(json.dumps({
        "NO_WORD_SPECIFIC_SIGNAL": "Set A Delta CI lower bound <= 0 (T not above strongest control)",
        "IDEAL_SET_ONLY_NOT_REPLICATED": "Set A passes all criteria but Set B Delta CI lower bound <= 0",
        "STRUCTURAL_SHORTCUT_EXPLAINS": "F (feature-only) accuracy ~ T accuracy (length/frequency explains it)",
        "RANDOM_ASSIGNMENT_EXPLAINS": "R accuracy ~ T accuracy (the specific assignment adds nothing)",
        "VALENCE_EXPLAINS": "same-valence-subset accuracy ~ chance while cross-valence drives any effect",
        "ORDER_NOT_INFORMATIVE": "S/O ablation shows no ordered-vs-bag difference",
        "WORD_SPECIFIC_SIGNAL_REPLICATES": "all conjunctive success criteria met in BOTH sets across families"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # success criteria (conjunctive)
    (OUT / "success_criteria.json").write_text(json.dumps({"conjunctive_all_required": [
        "Set A true accuracy above chance (binomial CI lower > 1/6)",
        "Set A true accuracy above ALL controls (Delta point >= 0.15 and CI lower > 0)",
        "Set B true accuracy above chance",
        "Set B true accuracy above all controls, or at minimum above the strongest random/mismatch control (CI lower > 0)",
        "effect direction consistent across >=3 evaluator families",
        "same-valence-subset discrimination above chance",
        "no evidence that phoneme rarity or length explains performance (F and length-matched controls ~ chance)"]},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest_files = ["set_A_manifest.json", "set_B_manifest.json", "packet_rendering_spec.json",
                      "leakage_controls.json", "arm_control_spec.json", "evaluator_prompt_spec.json",
                      "randomization_manifest_schema.json", "analysis_plan.json", "outcome_taxonomy.json",
                      "success_criteria.json"]
    freeze = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in manifest_files}
    (OUT / "freeze_index.json").write_text(json.dumps({
        "controlling_gate": "native Gate-G0 PASS (commit 794ecaa4)",
        "packet_source": "confirmatory consonant backbone only (source consonant_v3_1, scope CONFIRMATORY_BACKBONE)",
        "readiness_verdict": "READY_FOR_PACKET_AUTHORING_AND_FREEZE",
        "frozen_artifact_hashes": freeze,
        "guardrails": "no experiment run; no judge; no result; no mapping/parser/vowel change; no per-word polarity; "
                      "no raw consonant-name leakage; B1.10 negative preserved; feasibility-only prior"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"set_A": SET_A, "set_B": set_b, "freeze": freeze, "readiness": "READY_FOR_PACKET_AUTHORING_AND_FREEZE"}


if __name__ == "__main__":
    r = build()
    print("Set A:", r["set_A"])
    print("Set B:", r["set_B"])
    print("readiness:", r["readiness"])
    print("frozen artifacts:", len(r["freeze"]))
