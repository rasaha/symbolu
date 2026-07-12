"""Native Gate-G0 recomputation for the Sanskrit word-specificity arm (docs/data-only).

Determines whether the native Sanskrit CONFIRMATORY consonant backbone supports a clean word-specificity
experiment that was previously blocked at the old 11-varṇa prose-packet Gate G0. This is NOT a polarity test and
NOT an experiment: no judges, no semantic scoring, no prose authoring, no preregistration. Packets are built ONLY
from confirmatory consonant rows (source consonant_v3_1, scope CONFIRMATORY_BACKBONE) of the merged native lexicon;
authored-provisional vowels / anusvāra / visarga are excluded. Selection uses ONLY structural distinctness (never
semantic fit). Deterministic. Structure, not validated meaning.

Preserves: B1.10 pole-legibility negative (−2.78); the qualitative guarded prior. No mapping/parser/lexicon edit.
"""
import itertools
import json
import pathlib
from collections import Counter

import sanskrit_stage1_parser as P
from b1_stage1_mapping_integration_audit import iast_to_devanagari

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
SEED = [e["spelling"] for e in json.load(open(HERE / "frozen" / "word_list.json", encoding="utf-8"))["words"]]
OUT = HERE / "native_gate_g0"

# ---- frozen gate constants (preserved from old Gate G0; K, caps) ----
K = 6
MAX_JACCARD_CAP = 0.34
MEAN_JACCARD_CAP = 0.20
POOL_SIZE = 20          # distinctness-core pool (parallels the old 16-word valid pool), chosen by LOW mean-overlap
MIN_CONS, MAX_CONS = 2, 4

# confirmatory consonant backbone: unit -> (binding, liberating)
CB = {r["canonical_parser_unit"]: (r["binding_vritti"], r["liberating_vritti"]) for r in MERGED["rows"]
      if r["category"] == "consonant" and r.get("source_key") and r["activation_scope"] == "CONFIRMATORY_BACKBONE"}
RARE = {"ṅ", "ñ", "ṭ", "ṭh", "ḍ", "ḍh", "ṇ", "ch", "jh", "gh", "bh", "kh", "ph", "ṣ"}  # low-frequency consonants

# structural valence labels (BALANCE constraint only — NOT selection-by-fit; from prior review + common glosses)
VALENCE = {
    "śānti": "pos", "sukha": "pos", "bala": "pos", "jñāna": "pos", "kṣamā": "pos", "sattva": "pos", "mokṣa": "pos",
    "ahiṃsā": "pos", "satya": "pos", "dharma": "pos", "yoga": "pos", "ānanda": "pos", "deva": "pos", "prema": "pos",
    "bhakti": "pos", "vidyā": "pos", "guru": "pos", "ātman": "pos",
    "duḥkha": "neg", "bhaya": "neg", "krodha": "neg", "moha": "neg", "kāma": "neg", "māyā": "neg", "lobha": "neg",
    "avidyā": "neg", "asura": "neg", "hiṃsā": "neg",
    "agni": "neut", "jala": "neut", "nara": "neut", "vana": "neut", "aśva": "neut", "gṛha": "neut", "nadī": "neut",
    "vāyu": "neut", "sūrya": "neut", "candra": "neut", "parvata": "neut", "puṣpa": "neut",
}


def cons_seq(iast):
    r = P.parse(iast_to_devanagari(iast))
    ok = r["transliteration_iast"] == iast
    seq = [u["unit"] for u in r["atomic_varnas"] if u["type"] == "consonant"]
    has_missing_r = "ṛ" in [u["unit"] for u in r["atomic_varnas"]]
    return seq, ok, has_missing_r


def eligible():
    rows = []
    for w in sorted(set(SEED)):
        seq, ok, miss = cons_seq(w)
        cset = set(seq)
        if not ok:                                    # deterministic round-trip required
            continue
        if not cset or not cset.issubset(set(CB)):    # complete confirmatory consonant packet, no non-CB unit
            continue
        if not (MIN_CONS <= len(cset) <= MAX_CONS):
            continue
        rows.append({"iast": w, "devanagari": iast_to_devanagari(w), "cons_seq": seq, "cons_set": sorted(cset),
                     "n_distinct": len(cset), "n_tokens": len(seq), "repeated": len(seq) != len(cset),
                     "missing_r_but_consonant_only": miss, "valence": VALENCE.get(w, "unknown")})
    return rows


def jac(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 0.0


def evaluate_set(sub):
    """sub: list of eligible rows. Apply the native distinctiveness criteria."""
    sets = {r["iast"]: set(r["cons_set"]) for r in sub}
    names = list(sets)
    # C1 per-word >=1 unique feature (consonant no other member has)
    uniq = {}
    for w in names:
        others = set().union(*[sets[o] for o in names if o != w])
        uniq[w] = sets[w] - others
    c1 = all(len(uniq[w]) >= 1 for w in names)
    # C2/C3 no identical / trivially-equivalent packets
    frozen = [frozenset(sets[w]) for w in names]
    c23 = len(set(frozen)) == len(frozen)
    # C4 pairwise Jaccard caps
    pj = [jac(sets[a], sets[b]) for a, b in itertools.combinations(names, 2)]
    max_j, mean_j = (max(pj), sum(pj) / len(pj)) if pj else (0, 0)
    c4 = max_j <= MAX_JACCARD_CAP and mean_j <= MEAN_JACCARD_CAP
    # C5/C6 length not identifying: no word uniquely holds its distinct-consonant count
    lc = Counter(r["n_distinct"] for r in sub)
    c56 = all(lc[r["n_distinct"]] >= 2 for r in sub)
    # C10 rare-only uniqueness: flag words whose unique feature is a SINGLE rare consonant
    rare_only = [w for w in names if len(uniq[w]) == 1 and uniq[w].issubset(RARE)]
    # C8 same-valence inclusion: >=1 same-valence pair among known-valence members
    vals = [r["valence"] for r in sub if r["valence"] != "unknown"]
    c8 = any(v >= 2 for v in Counter(vals).values())
    eligible_set = c1 and c23 and c4
    return {"eligible": eligible_set, "c1_per_word_unique": c1, "c23_no_identical": c23, "c4_jaccard_caps": c4,
            "c56_length_not_identifying": c56, "c8_same_valence_pair": c8, "max_jaccard": round(max_j, 3),
            "mean_jaccard": round(mean_j, 3), "rare_only_unique_words": rare_only,
            "unique_features": {w: sorted(uniq[w]) for w in names}}


def build():
    OUT.mkdir(exist_ok=True)
    elig = eligible()
    # distinctness-core pool: rank by LOW mean pairwise overlap with all other eligibles (structural, non-semantic)
    for r in elig:
        r["mean_overlap_vs_all"] = round(sum(jac(r["cons_set"], o["cons_set"]) for o in elig if o is not r)
                                         / max(1, len(elig) - 1), 4)
    pool = sorted(elig, key=lambda r: (r["mean_overlap_vs_all"], r["iast"]))[:POOL_SIZE]
    pool_names = [r["iast"] for r in pool]

    # systematic enumeration over the core pool (parallels old G0's exhaustive C(16,6))
    eligible_sets = []
    by_name = {r["iast"]: r for r in pool}
    for combo in itertools.combinations(sorted(pool_names), K):
        sub = [by_name[w] for w in combo]
        ev = evaluate_set(sub)
        if ev["eligible"]:
            # rank key: prefer length-non-identifying + same-valence + low overlap; deterministic
            eligible_sets.append({"words": list(combo), **ev})
    # deterministic ranking: (not c56, not c8, max_jaccard, mean_jaccard, has-rare-only, alphabetical)
    eligible_sets.sort(key=lambda s: (not s["c56_length_not_identifying"], not s["c8_same_valence_pair"],
                                      s["max_jaccard"], s["mean_jaccard"], len(s["rare_only_unique_words"]),
                                      s["words"]))

    selected = eligible_sets[0] if eligible_sets else None

    # pairwise matrix over the pool
    matrix = {a: {b: round(jac(by_name[a]["cons_set"], by_name[b]["cons_set"]), 3) for b in pool_names}
              for a in pool_names}

    # ---- control feasibility (structural; can each arm be constructed cleanly?) ----
    controls = {
        "true_packet_arm": {"feasible": True, "note": "the frozen consonant-backbone packets themselves"},
        "cross_word_mismatch_arm": {"feasible": bool(selected), "note": "pair each word with another member's packet"},
        "scrambled_packet_arm": {"feasible": True, "note": "reassign packets across words / permute feature order"},
        "random_varna_assignment_arm": {"feasible": True,
                                        "note": "structure-preserving permutation of the 33 consonant→pole assignment"},
        "packet_length_matched_controls": {"feasible": bool(selected and selected["c56_length_not_identifying"]),
                                           "note": "requires >=2 words per length in the set (criterion C5/C6)"},
        "same_valence_comparisons": {"feasible": bool(selected and selected["c8_same_valence_pair"]),
                                     "note": "requires >=1 same-valence pair; valence is a balance label, not fit"},
        "consonant_frequency_matched": {"feasible": True, "note": "corpus consonant frequencies computable + matchable"},
        "no_per_word_polarity_selection": {"feasible": True, "note": "both poles fixed per word by construction"},
        "blind_word_identity_matching": {"feasible": bool(selected), "note": "forced-choice match packet→word among the set"},
        "no_open_ended_plausibility_endpoint": {"feasible": True, "note": "endpoint is forced-choice accuracy, not 'sounds plausible?'"},
    }
    controls_ok = all(c["feasible"] for c in controls.values())

    # ---- gate verdict ----
    if not eligible_sets:
        verdict = "NATIVE_GATE_G0_FAIL_INSUFFICIENT_PACKET_DISTINCTIVENESS"
    elif not controls_ok:
        verdict = "NATIVE_GATE_G0_FAIL_CONTROL_CONSTRUCTION"
    elif selected and selected["c56_length_not_identifying"] and selected["c8_same_valence_pair"] \
            and not selected["rare_only_unique_words"]:
        verdict = "NATIVE_GATE_G0_PASS"
    else:
        verdict = "NATIVE_GATE_G0_PASS_WITH_RESTRICTED_WORD_SET"

    report = {
        "artifact_type": "native_gate_g0_recompute", "not_a_polarity_test": True,
        "packet_source": "frozen/varna_native_stage1_merged_v1.json :: CONFIRMATORY_BACKBONE consonants only",
        "old_gate": {
            "criteria": "K=6; per-word >=1 unique discriminating facet; max facet-Jaccard <= 0.34; mean <= 0.20; "
                        "no best-effort set; caps not relaxed",
            "why_failed": "facet render map covered ONLY 11 varṇas; 21/37 candidates invalid; no size-6 subset had "
                          "per-word unique facet (ra alone in 9/16 valid words)",
            "old_renderable_units": 11, "old_status": "G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS",
            "preserved": "K, Jaccard caps, per-word-uniqueness, no-cap-relaxation, exhaustive-pool enumeration, "
                         "facet↔varṇa bijection (Jaccard on consonant sets == facet-Jaccard)",
            "revised": "substrate = native Devanāgarī consonant backbone (33 confirmatory units, not 11 rendered); "
                       "added strengthened controls C5/C6 length-non-identifying, C8 same-valence, C10 rare-only flag",
        },
        "native_renderable_units": len(CB),
        "old_blocker_removed": len(CB) > 11,
        "constants": {"K": K, "MAX_JACCARD_CAP": MAX_JACCARD_CAP, "MEAN_JACCARD_CAP": MEAN_JACCARD_CAP,
                      "POOL_SIZE": POOL_SIZE, "cons_len_range": [MIN_CONS, MAX_CONS]},
        "n_eligible_candidates": len(elig), "n_core_pool": len(pool), "core_pool": pool_names,
        "n_eligible_sets": len(eligible_sets),
        "selected_set": selected, "control_feasibility": controls, "controls_all_feasible": controls_ok,
        "gate_verdict": verdict,
        "guardrails": "Consonant backbone only; no vowel/marker pole in packets; no semantic fit in selection; no "
                      "judges/scoring/prereg. B1.10 pole-legibility negative and the qualitative guarded prior preserved.",
    }
    (OUT / "native_gate_g0_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "candidate_inventory.json").write_text(json.dumps({"candidates": elig}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "pairwise_distinctiveness_matrix.json").write_text(json.dumps({"pool": pool_names, "jaccard": matrix}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "candidate_set_ranking.json").write_text(json.dumps({"ranked_sets": eligible_sets[:25]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if selected:
        (OUT / "selected_set_manifest.json").write_text(json.dumps(
            {"selected_words": selected["words"], "packets": {w: by_name[w]["cons_set"] for w in selected["words"]},
             "cons_sequences": {w: by_name[w]["cons_seq"] for w in selected["words"]},
             "valence_balance": {w: by_name[w]["valence"] for w in selected["words"]},
             "distinctiveness": {k: selected[k] for k in ("max_jaccard", "mean_jaccard", "unique_features",
                                                          "c56_length_not_identifying", "c8_same_valence_pair",
                                                          "rare_only_unique_words")},
             "verdict": verdict}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build()
    print("verdict:", r["gate_verdict"])
    print(f"native renderable units: {r['native_renderable_units']} (old: 11) — blocker removed: {r['old_blocker_removed']}")
    print(f"eligible candidates: {r['n_eligible_candidates']}  core pool: {r['n_core_pool']}  eligible sets: {r['n_eligible_sets']}")
    if r["selected_set"]:
        s = r["selected_set"]
        print("selected set:", s["words"])
        print(f"  max_jaccard={s['max_jaccard']} mean_jaccard={s['mean_jaccard']} length_non_id={s['c56_length_not_identifying']} same_valence={s['c8_same_valence_pair']} rare_only={s['rare_only_unique_words']}")
    print("controls all feasible:", r["controls_all_feasible"])
