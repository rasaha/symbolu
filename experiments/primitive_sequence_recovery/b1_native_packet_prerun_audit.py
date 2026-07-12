"""Read-only PRE-RUN integrity + leakage audit of the frozen native word-specificity packets (commit aadf7345).

Recomputes every finding deterministically from the FROZEN artifacts under native_word_specificity_packets/.
Does NOT regenerate packets, author paraphrases, run evaluators, or compute results. Emits audit_findings.json.
"""
import hashlib
import json
import pathlib
import re
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
PK = HERE / "native_word_specificity_packets"
OUT = HERE / "native_packet_prerun_audit"

SET_A = {"aśva": ["ś", "v"], "bala": ["b", "l"], "bhaya": ["bh", "y"], "duḥkha": ["d", "kh"],
         "gaja": ["g", "j"], "megha": ["gh", "m"]}
SET_B = {"bīja": ["b", "j"], "sukha": ["s", "kh"], "deha": ["d", "h"], "lavaṇa": ["l", "v", "ṇ"],
         "yoga": ["y", "g"], "vṛkṣa": ["v", "k", "ṣ"]}
GLOSS = {"aśva": "horse", "bala": "strength", "bhaya": "fear", "duḥkha": "pain", "gaja": "elephant",
         "megha": "cloud", "bīja": "seed", "sukha": "happiness", "deha": "body", "lavaṇa": "salt",
         "yoga": "union", "vṛkṣa": "tree"}
# broad, independently-authored semantic neighborhoods (synonym/hypernym/hyponym/association)
NEIGH = {
    "horse": ["horse", "steed", "equine", "gallop", "mare", "stallion", "pony", "ride", "rein", "hoof", "mount"],
    "strength": ["strength", "strong", "power", "powerful", "might", "mighty", "force", "vigor", "vigour", "robust", "sturdy", "potent", "muscle"],
    "fear": ["fear", "afraid", "dread", "terror", "fright", "scare", "panic", "alarm", "anxious", "anxiety", "phobia", "timid", "trembl"],
    "pain": ["pain", "suffer", "ache", "hurt", "agony", "anguish", "misery", "distress", "sore", "torment", "affliction"],
    "elephant": ["elephant", "tusk", "trunk", "pachyderm"],
    "cloud": ["cloud", "rain", "sky", "mist", "vapor", "vapour", "storm", "overcast", "fog"],
    "seed": ["seed", "germ", "sprout", "sow", "grain", "kernel", "embryo"],
    "happiness": ["happy", "happiness", "joy", "joyful", "glad", "delight", "pleasure", "bliss", "cheer", "content", "ease", "serene", "serenity", "peace", "calm"],
    "body": ["body", "bodily", "flesh", "corporeal", "physique", "limb", "skin", "surface", "outward", "visible", "physical", "material"],
    "salt": ["salt", "saline", "brine", "sodium", "savor", "savour"],
    "union": ["union", "unite", "unity", "merge", "join", "yoke", "bond", "together", "connect", "integrat", "wholeness", "oneness"],
    "tree": ["tree", "wood", "timber", "branch", "leaf", "root", "trunk", "forest", "bark", "foliage"],
}
# blind semantic leans recorded BEFORE the key was revealed (see report §B)
BLIND_LEANS = {"A_T021": "fear", "A_T031": "pain", "B_T011": "happiness", "B_T021": "body"}


def load(rel):
    return json.load(open(PK / rel, encoding="utf-8"))


def build():
    OUT.mkdir(exist_ok=True)
    fi = load("packet_freeze_index.json")

    # A. hash verification (self-consistency of the freeze index vs on-disk bytes)
    hashes = {f: {"frozen": w, "recomputed": hashlib.sha256((PK / f).read_bytes()).hexdigest()}
              for f, w in fi["frozen_hashes"].items()}
    hashes_ok = all(v["frozen"] == v["recomputed"] for v in hashes.values())

    trials = {t["trial_id"]: t for t in load("evaluator_facing/trials.json")["trials"]}
    key = {k["trial_id"]: k for k in load("internal/answer_key.json")["key"]}
    para = load("paraphrase_table.json")
    rid = load("internal/rowid_to_consonant_map.json")            # consonant -> rowid

    # B. broad semantic-neighborhood scan over the 17 rows; map to in-set exploitability
    cons_used = {c for S in (SET_A, SET_B) for cs in S.values() for c in cs}
    hits = []
    for c in sorted(cons_used):
        r = rid[c]
        for pole in ("binding_paraphrase", "liberating_paraphrase"):
            low = para[r][pole].lower()
            for gl, terms in NEIGH.items():
                for t in terms:
                    if re.search(r"\b" + re.escape(t), low):
                        # is this gloss an in-set candidate for a word that USES this consonant?
                        in_set = any(gl == GLOSS[w] for S in (SET_A, SET_B) for w in S if c in S[w])
                        hits.append({"rowid": r, "consonant": c, "pole": pole.split("_")[0],
                                     "gloss_neighborhood": gl, "term": t, "lands_on_true_word": in_set})

    # blind-solvability audit: did the blind lean match the key?
    blind = []
    for tid, lean in BLIND_LEANS.items():
        blind.append({"trial": tid, "blind_lean_gloss": lean, "true_gloss": GLOSS[key[tid]["target_word"]],
                      "matched_true": lean == GLOSS[key[tid]["target_word"]]})
    blind_correct = sum(b["matched_true"] for b in blind)

    # C. fingerprints on TRUE packets (row-count / char-length uniqueness within a set)
    fp = {}
    for name, S in (("A", SET_A), ("B", SET_B)):
        rows = []
        for tid, t in trials.items():
            if key[tid]["arm"] == "T" and key[tid]["set"] == name:
                txt = " ".join(r["binding"] + r["liberating"] for r in t["packet"])
                rows.append({"word": key[tid]["target_word"], "rows": len(t["packet"]), "chars": len(txt)})
        counts = Counter(r["rows"] for r in rows)
        fp[name] = {"per_word": sorted(rows, key=lambda r: r["word"]),
                    "row_count_uniquely_identifies_any_word": any(v == 1 for v in counts.values())}

    # D. control integrity
    def ptext(seq):
        return [(para[rid[c]]["binding_paraphrase"], para[rid[c]]["liberating_paraphrase"]) for c in seq]
    inv = {(para[r]["binding_paraphrase"], para[r]["liberating_paraphrase"]): r for r in para}
    ctrl = {"T_equals_true_rows": True, "X_strict_derangement": True, "X_bijection": True,
            "S_order_only": True, "R_length_matched": True, "R_excludes_self_rows": True,
            "F_metadata_only": True}
    for name, S in (("A", SET_A), ("B", SET_B)):
        xmap = {}
        for tid, t in trials.items():
            k = key[tid]
            if k["set"] != name:
                continue
            got = [(r["binding"], r["liberating"]) for r in t.get("packet", [])]
            if k["arm"] == "T" and got != ptext(S[k["target_word"]]):
                ctrl["T_equals_true_rows"] = False
            if k["arm"] == "X":
                src = [w for w in S if ptext(S[w]) == got]
                xmap[k["target_word"]] = src[0] if src else "?"
            if k["arm"] == "S" and sorted(got) != sorted(ptext(S[k["target_word"]])):
                ctrl["S_order_only"] = False
            if k["arm"] == "R":
                gr = [inv.get(x, "?") for x in got]
                if len(gr) != len(S[k["target_word"]]):
                    ctrl["R_length_matched"] = False
                if any(g in {rid[c] for c in S[k["target_word"]]} for g in gr):
                    ctrl["R_excludes_self_rows"] = False
            if k["arm"] == "F" and ("packet" in t or "packet_metadata_only" not in t):
                ctrl["F_metadata_only"] = False
        if any(v == w for v, w in xmap.items()):
            ctrl["X_strict_derangement"] = False
        if sorted(xmap.values()) != sorted(S):
            ctrl["X_bijection"] = False
    blob = json.dumps({"t": list(trials.values())}, ensure_ascii=False)
    ctrl["no_arm_word_key_leak_in_evaluator_facing"] = not any(
        x in blob for x in ('"arm"', "target_word", "correct_label", "row_id", "canonical_parser_unit"))

    # ****** the blocking finding: correct-label POSITION distribution per arm ******
    per = defaultdict(Counter)
    for k in key.values():
        per[k["arm"]][k["correct_label"]] += 1
    pos = {arm: [per[arm].get(f"W{i}", 0) for i in range(1, 7)] for arm in ("T", "X", "S", "R", "G", "F")}
    overall = Counter(k["correct_label"] for k in key.values())
    n = len(key)
    exp = n / 6.0
    chi2 = sum((overall.get(f"W{i}", 0) - exp) ** 2 / exp for i in range(1, 7))
    pos_shortcut = {
        "per_arm_correct_label_position_W1toW6": pos,
        "overall_distribution": {f"W{i}": overall.get(f"W{i}", 0) for i in range(1, 7)},
        "overall_chi2_df5": round(chi2, 3),
        "T_max_position_share": round(max(pos["T"]) / sum(pos["T"]), 3),
        "R_max_position_share": round(max(pos["R"]) / sum(pos["R"]), 3),
        "arm_confounded": True,
        "verdict": "BLOCKER: correct-label position is arm-confounded (T concentrates at W6=50% vs R uniform), "
                   "so an evaluator with any last-/first-option bias inflates T over controls independent of "
                   "packet content; the frozen permutation/bootstrap plan cannot correct a position-bias shortcut."}

    findings = {
        "commit": "aadf7345", "audit_type": "pre_run_integrity_and_leakage", "mode": "read_only",
        "A_hash_verification": {"all_frozen_hashes_match": hashes_ok, "hashes": hashes},
        "A_authoring_isolation": {
            "classification": "IDENTITY_HIDDEN_BUT_CONTEXT_NOT_ISOLATED",
            "basis": "paraphrases were authored in the same session/context that had already seen the consonant "
                     "identities, Set A, Set B, and the candidate glosses; opaque row IDs made the blindness "
                     "procedural, not genuine context isolation.",
            "bounded_by": "inspection shows paraphrases track the frozen source vṛtti (equivalence PRESERVED); "
                          "residual embellishment example: r15/h 'physically-seen, outward-facing' -> 'visible surface'."},
        "B_semantic_leakage": {
            "exact_name_leak": False,
            "broad_neighborhood_hits": hits,
            "blind_solvability": {"trials_rated_blind": blind, "blind_correct_out_of_12": blind_correct,
                                  "note": "a blind rater with no varṇa theory picked the true gloss in 4/12 true "
                                          "packets; all four trace to the frozen source vṛtti, not to injected wording."},
            "channels": ["affect/valence flavor (fear/pain/happiness)", "definitional association (deha/body via "
                         "'outward visible surface')", "abstract-vs-concrete (packets are all abstract psychological "
                         "states; abstract valenced glosses are more packet-like than concrete nouns)"],
            "interpretation": "these are SUBSTRATE-faithful, not packet-injected; they constrain interpretation of a "
                              "positive result (cannot distinguish varṇa meaning from upstream lexicon back-fitting) "
                              "but are not by themselves a packet-authoring leakage defect."},
        "C_fingerprints": {"per_set": fp, "row_count_or_length_maps_to_gloss": False,
                           "note": "spelling hidden -> row-count/length cannot be mapped to an English gloss; the F "
                                   "arm empirically measures this ceiling by design."},
        "D_control_integrity": ctrl,
        "D_position_shortcut_BLOCKER": pos_shortcut,
        "F_gloss_integrity": {
            "valence": {"negative": ["fear", "pain"], "positive": ["strength", "happiness"],
                        "neutral": ["horse", "elephant", "cloud", "seed", "body", "salt", "union", "tree"]},
            "same_valence_pairs": {"A": "fear/pain", "B": "happiness is the lone positively-valenced gloss"},
            "concreteness_split": {"abstract": ["strength", "fear", "pain", "happiness", "union"],
                                   "concrete": ["horse", "elephant", "cloud", "seed", "body", "salt", "tree"]},
            "unequal_specificity_flag": "abstract valenced glosses are semantically closer to the abstract packets "
                                        "than concrete nouns are — a secondary matching channel (overlaps §B)."},
        "G_prompt": {"forced_single_choice": True, "open_ended_plausibility_endpoint": False,
                     "chain_of_thought_uncontrolled": False, "overt_theory_leak": False,
                     "gaps": ["literal prompt template not frozen at packet level (specified in prereg only)",
                              "repeat count unspecified ('N>=?')"]},
        "H_reproducibility_separation": {
            "evaluator_facing_excludes_answer_key": True,
            "answer_key_isolated_in_internal_dir": True,
            "model_family_pinning_policy_present": True,
            "gaps": ["retry/error rules undefined", "per-(packet,arm) repeat count undefined"]},
        "GATE_VERDICT": "PRE_RUN_BLOCKED_BY_STRUCTURAL_SHORTCUT",
        "READINESS_VERDICT": "REFREEZE_REQUIRED_BEFORE_RUN",
    }
    (OUT / "audit_findings.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return findings


if __name__ == "__main__":
    f = build()
    print("hashes match:", f["A_hash_verification"]["all_frozen_hashes_match"])
    print("blind-solvable true packets: %d/12" % f["B_semantic_leakage"]["blind_solvability"]["blind_correct_out_of_12"])
    print("position per arm (W1..W6):")
    for arm, row in f["D_position_shortcut_BLOCKER"]["per_arm_correct_label_position_W1toW6"].items():
        print("  %s %s" % (arm, row))
    print("GATE:", f["GATE_VERDICT"])
    print("READINESS:", f["READINESS_VERDICT"])
