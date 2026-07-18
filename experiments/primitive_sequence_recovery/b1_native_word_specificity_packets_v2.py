"""Corrected v2 packet-authoring-and-freeze for the native Sanskrit word-specificity study (docs/data-only).

Corrects the two defects found by the pre-run audit (commit 73030960):
  1. STRUCTURAL SHORTCUT — the v1 candidate order left the correct-answer POSITION arm-confounded (T 50% at W6
     vs R uniform). v2 replaces the sequential shuffle with a deterministic COUNTERBALANCED ROTATION schedule:
     every base trial is presented in REPEATS=6 rotations, so its correct answer visits each of W1..W6 exactly
     once. Aggregated over the full set, every arm's correct-position distribution is exactly uniform and matched.
  2. AUTHORING ISOLATION — the 17 paraphrases were re-authored by a genuinely context-isolated agent that saw only
     opaque row IDs + source vṛtti text (no consonant identity, no Devanāgarī/IAST, no words/sets/glosses, no bridge,
     no prior paraphrases, no leak findings). Their output is frozen at native_word_specificity_packets_v2/
     paraphrase_table_v2_authored.json and loaded verbatim here.

Everything else (parser, merged lexicon, consonant mappings, Set A/B membership, glosses, dual-pole render, arm
definitions, primary endpoint, controls) is UNCHANGED. No evaluator run, no judge, no result. Confirmatory
consonant backbone only; no authored vowel/marker enters a packet.
"""
import hashlib
import json
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
V1 = HERE / "native_word_specificity_packets"                          # v1 freeze (read-only inputs: bridge, glosses)
OUT = HERE / "native_word_specificity_packets_v2"
EVAL = OUT / "evaluator_facing"
INTERNAL = OUT / "internal"

# used consonants (17) — identical set to v1
SET_A = {"aśva": ["ś", "v"], "bala": ["b", "l"], "bhaya": ["bh", "y"], "duḥkha": ["d", "kh"],
         "gaja": ["g", "j"], "megha": ["gh", "m"]}
SET_B = {"bīja": ["b", "j"], "sukha": ["s", "kh"], "deha": ["d", "h"], "lavaṇa": ["l", "v", "ṇ"],
         "yoga": ["y", "g"], "vṛkṣa": ["v", "k", "ṣ"]}
USED = {c for seq in list(SET_A.values()) + list(SET_B.values()) for c in seq}
CB = {r["canonical_parser_unit"]: (r["binding_vritti"], r["liberating_vritti"]) for r in MERGED["rows"]
      if r["category"] == "consonant" and r.get("source_key") and r["activation_scope"] == "CONFIRMATORY_BACKBONE"
      and r["canonical_parser_unit"] in USED}

# private bridge (consonant -> opaque row id) reused from the v1 freeze; NEVER emitted to evaluator-facing
RID = json.load(open(V1 / "internal" / "rowid_to_consonant_map.json", encoding="utf-8"))   # consonant -> rowid
# candidate glosses — UNCHANGED from v1 (byte-identical dictionary senses)
CANDIDATES = json.load(open(V1 / "candidate_gloss_table.json", encoding="utf-8"))
# v2 isolated-author paraphrases, keyed by opaque row id
AUTHORED = json.load(open(OUT / "paraphrase_table_v2_authored.json", encoding="utf-8"))
# consonant -> (binding_paraphrase, liberating_paraphrase)
PARA = {c: (AUTHORED[RID[c]]["binding_paraphrase"], AUTHORED[RID[c]]["liberating_paraphrase"]) for c in USED}

# word-agnostic generic dual-pole rows (arm G) — UNCHANGED from v1
GENERIC = [
    ("a contingent unease that depends on shifting outside conditions",
     "a steady inner poise that does not depend on outside conditions"),
    ("a grasping tension that keeps reaching for more",
     "a settled sufficiency that no longer needs to reach"),
    ("a narrowing fixation that closes around one concern",
     "an open, unforced attention that stays broad"),
    ("a reactive push discharged outward under pressure",
     "a contained composure that holds under pressure"),
]

IAST_DIACRITICS = set("āīūēōṛṝḷḹṭḍṇṅñśṣḥṃ")
SEEDS = {"derangement": 20260901, "random_assignment": 20260902, "generic": 20260903,
         "base_order": 20260906}
REPEATS = 6                                                    # counterbalanced rotations per base trial
POSITIONS = 6
# the four source-intrinsic semantic-adjacency words (pre-flagged; NOT removed from the primary endpoint)
FLAGGED_WORDS = ["bhaya", "duḥkha", "sukha", "deha"]


def feature(cons):
    b, l = PARA[cons]
    return {"binding": b, "liberating": l}


def word_packet(seq):
    return [feature(c) for c in seq]


def derangement(words, seed):
    rng = random.Random(seed)
    n = len(words)
    while True:
        perm = list(range(n)); rng.shuffle(perm)
        if all(perm[i] != i for i in range(n)):
            return {words[i]: words[perm[i]] for i in range(n)}


def base_orders(words, setname):
    """One deterministic base candidate ordering per base-trial index (rotations counterbalance position)."""
    rng = random.Random(SEEDS["base_order"] + (0 if setname == "A" else 1000))
    return rng


def build_arms(wordset, setname):
    """Emit base trials for every arm, then expand each into REPEATS rotations (position counterbalanced)."""
    words = list(wordset)
    der = derangement(words, SEEDS["derangement"])
    rng_R = random.Random(SEEDS["random_assignment"])
    rng_G = random.Random(SEEDS["generic"])
    rng_ord = base_orders(words, setname)
    all_cons = sorted(PARA)

    base = []                          # each: dict(packet | packet_metadata_only, target_word, arm, instance)
    for w in words:
        seq = wordset[w]; n = len(seq)
        base.append({"packet": word_packet(seq), "target": w, "arm": "T", "instance": 0})
        base.append({"packet": word_packet(wordset[der[w]]), "target": w, "arm": "X", "instance": 0})
        if n > 1:
            sseq = seq[:]; random.Random(SEEDS["base_order"] + len(base)).shuffle(sseq)
            base.append({"packet": word_packet(sseq), "target": w, "arm": "S", "instance": 0})
        for inst in range(5):
            rseq = [rng_R.choice([c for c in all_cons if c not in seq]) for _ in seq]
            base.append({"packet": word_packet(rseq), "target": w, "arm": "R", "instance": inst})
        gsel = [GENERIC[rng_G.randrange(len(GENERIC))] for _ in range(n)]
        base.append({"packet": [{"binding": b, "liberating": l} for b, l in gsel],
                     "target": w, "arm": "G", "instance": 0})
        base.append({"packet_metadata_only": {"n_features": n, "length_band": "short" if n <= 2 else "medium"},
                     "target": w, "arm": "F", "instance": 0})

    trials, key = [], []
    for bseq, bt in enumerate(base):
        # one deterministic base ordering of the six candidate words for this base trial
        order0 = words[:]; rng_ord.shuffle(order0)
        b_index = order0.index(bt["target"])
        for r in range(REPEATS):
            # left-rotate the candidate order by r → target's position = (b_index - r) mod 6, cycles all positions
            order = order0[r:] + order0[:r]
            labelled = [{"label": f"W{i+1}", "gloss": CANDIDATES[w]["gloss"], "_word": w} for i, w in enumerate(order)]
            correct_label = next(x["label"] for x in labelled if x["_word"] == bt["target"])
            tid = f"{setname}_b{bseq:03d}_r{r}"
            item = {"trial_id": tid,
                    "candidates": [{"label": x["label"], "gloss": x["gloss"]} for x in labelled]}
            if "packet" in bt:
                item["packet"] = bt["packet"]
                item["instruction"] = "One of the six options is the word this packet describes. Choose exactly one label."
            else:
                item["packet_metadata_only"] = bt["packet_metadata_only"]
                item["instruction"] = "Only structural metadata is given (no descriptions). Choose exactly one label."
            trials.append(item)
            key.append({"trial_id": tid, "set": setname, "arm": bt["arm"], "instance": bt["instance"],
                        "repeat": r, "base_seq": bseq, "target_word": bt["target"], "correct_label": correct_label})
    return trials, key


def leakage_audit():
    # broad semantic neighborhoods (synonym / hypernym / hyponym / association), not just exact synonyms
    NEIGH = {
        "horse": ["horse", "equine", "steed", "gallop", "mare", "stallion", "pony"],
        "strength": ["strength", "strong", "power", "might", "mighty", "vigor", "vigour", "force", "robust", "sturdy", "potent", "muscle"],
        "fear": ["fear", "afraid", "dread", "terror", "fright", "scare", "panic", "alarm", "anxious", "anxiety", "phobia", "timid"],
        "pain": ["pain", "suffer", "ache", "hurt", "agony", "anguish", "misery", "distress", "torment", "affliction"],
        "elephant": ["elephant", "tusk", "trunk", "pachyderm"],
        "cloud": ["cloud", "rain", "sky", "mist", "vapor", "vapour", "storm", "fog", "overcast"],
        "seed": ["seed", "germ", "sprout", "grain", "kernel", "embryo"],
        "happiness": ["happy", "happiness", "joy", "glad", "delight", "pleasure", "bliss", "ease", "serene", "serenity", "peace", "calm", "cheer"],
        "body": ["body", "bodily", "flesh", "corporeal", "physique", "skin", "surface", "outward", "visible", "physical", "material"],
        "salt": ["salt", "saline", "brine", "sodium"],
        "union": ["union", "unite", "unity", "merge", "merger", "join", "yoke", "bond", "together", "oneness"],
        "tree": ["tree", "wood", "timber", "branch", "leaf", "root", "forest", "bark", "foliage"]}
    import re
    flags = []
    for cons in sorted(PARA):
        using_words = [w for S in (SET_A, SET_B) for w in S if cons in S[w]]
        for pole, text in (("binding", PARA[cons][0]), ("liberating", PARA[cons][1])):
            low = text.lower()
            if any(ch in text for ch in IAST_DIACRITICS):
                flags.append({"row": RID[cons], "pole": pole, "issue": "iast_diacritic_leak", "in_set_exploitable": True,
                              "source_intrinsic_preflagged": False})
            for gl, stems in NEIGH.items():
                # exploitable only if this gloss is an in-set candidate of a word USING this consonant
                hit_words = [w for w in using_words if gl == CANDIDATES[w]["gloss"]]
                in_set = bool(hit_words)
                # source-intrinsic pre-flagged: the using word is one of the four FLAGGED_WORDS and its gloss matches
                preflag = any(w in FLAGGED_WORDS for w in hit_words)
                for s in stems:
                    if re.search(r"\b" + re.escape(s), low):
                        flags.append({"row": RID[cons], "pole": pole, "issue": f"gloss_neighborhood:{gl}:{s}",
                                      "gloss": gl, "in_set_exploitable": in_set,
                                      "source_intrinsic_preflagged": preflag, "text": text})
    return flags


def position_bias_simulation(key):
    """Fixed-position / first / last agents must yield NO T-vs-control advantage (Δ<=0)."""
    from collections import defaultdict
    arms = ["T", "X", "S", "R", "G", "F"]
    out = {}
    for policy, pos in (("fixed_W3", "W3"), ("first_option_W1", "W1"), ("last_option_W6", "W6")):
        acc = {}
        for arm in arms:
            rows = [k for k in key if k["arm"] == arm]
            hit = sum(1 for k in rows if k["correct_label"] == pos)
            acc[arm] = hit / len(rows) if rows else 0.0
        controls = max(acc["X"], acc["R"], acc["G"], acc["F"])
        out[policy] = {"per_arm_accuracy": {a: round(acc[a], 4) for a in arms},
                       "primary_contrast_delta": round(acc["T"] - controls, 4)}
    return out


def build():
    for d in (OUT, EVAL, INTERNAL):
        d.mkdir(exist_ok=True)

    para_table = {RID[c]: {"binding_paraphrase": PARA[c][0], "liberating_paraphrase": PARA[c][1]} for c in USED}
    (OUT / "paraphrase_table.json").write_text(json.dumps(para_table, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "candidate_gloss_table.json").write_text(json.dumps(CANDIDATES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    flags = leakage_audit()
    exploitable = [f for f in flags if f.get("in_set_exploitable")]
    new_exploitable = [f for f in exploitable if not f.get("source_intrinsic_preflagged")]
    (OUT / "leakage_audit.json").write_text(json.dumps(
        {"n_flags": len(flags), "n_exploitable_in_set": len(exploitable),
         "n_new_exploitable_not_preflagged": len(new_exploitable), "flags": flags,
         "method": "each paraphrase vs BROAD candidate-gloss neighborhoods (synonym/hypernym/hyponym/association) + "
                   "IAST-diacritic check; a hit is exploitable ONLY if the gloss is an in-set candidate of a word "
                   "using that consonant; source-intrinsic pre-flagged hits (the four flagged words) are carried by "
                   "the precommitted flagged-word sensitivity analysis, not counted as new packet leakage"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    trials, key = [], []
    for name, ws in (("A", SET_A), ("B", SET_B)):
        t, k = build_arms(ws, name)
        trials += t; key += k

    # opaque evaluator-facing IDs: deterministic shuffle decouples presentation order/ID from set/arm/word/base/repeat
    structured_ids = [t["trial_id"] for t in trials]
    shuffled = structured_ids[:]
    random.Random(SEEDS["base_order"] + 424242).shuffle(shuffled)
    opaque_of = {sid: f"t{ i+1:04d}" for i, sid in enumerate(shuffled)}
    eval_trials = []
    for t in sorted(trials, key=lambda x: opaque_of[x["trial_id"]]):
        item = {k2: v for k2, v in t.items() if k2 != "trial_id"}
        eval_trials.append({"trial_id": opaque_of[t["trial_id"]], **item})
    for k in key:
        k["opaque_trial_id"] = opaque_of[k["trial_id"]]
        k["structured_trial_id"] = k.pop("trial_id")
    key = sorted(key, key=lambda x: x["opaque_trial_id"])
    (EVAL / "trials.json").write_text(json.dumps({"trials": eval_trials}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (INTERNAL / "answer_key.json").write_text(json.dumps({"key": key}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # position balance ledger
    from collections import Counter, defaultdict
    per = defaultdict(Counter)
    for k in key:
        per[(k["set"], k["arm"])][k["correct_label"]] += 1
    def chi2(counter, n):
        exp = n / POSITIONS
        return sum((counter.get(f"W{i+1}", 0) - exp) ** 2 / exp for i in range(POSITIONS))
    balance = {}
    for (s, a), cnt in per.items():
        n = sum(cnt.values())
        balance[f"{s}/{a}"] = {"dist": [cnt.get(f"W{i+1}", 0) for i in range(POSITIONS)], "chi2": round(chi2(cnt, n), 6)}
    global_cnt = Counter(k["correct_label"] for k in key)
    balance["GLOBAL"] = {"dist": [global_cnt.get(f"W{i+1}", 0) for i in range(POSITIONS)],
                         "chi2": round(chi2(global_cnt, len(key)), 6)}
    sim = position_bias_simulation(key)
    (OUT / "position_balance.json").write_text(json.dumps(
        {"repeats": REPEATS, "per_set_arm": balance, "position_bias_simulation": sim,
         "max_delta_across_position_policies": max(v["primary_contrast_delta"] for v in sim.values())},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    counts = Counter((k["set"], k["arm"]) for k in key)
    counts_out = {f"{s}/{a}": n for (s, a), n in sorted(counts.items())}

    all_balanced = all(v["chi2"] == 0 for v in balance.values())
    pos_agents_no_edge = all(v["primary_contrast_delta"] <= 0 for v in sim.values())
    packet_verdict = ("V2_PACKETS_REFROZEN_AND_BALANCED"
                      if all_balanced and pos_agents_no_edge and len(new_exploitable) == 0
                      else "V2_REFREEZE_BLOCKED_BY_POSITION_BALANCE" if not (all_balanced and pos_agents_no_edge)
                      else "V2_REFREEZE_BLOCKED_BY_LEAKAGE")
    readiness = "READY_FOR_FOCUSED_V2_PRERUN_AUDIT" if packet_verdict == "V2_PACKETS_REFROZEN_AND_BALANCED" \
        else "NOT_READY_FOR_EVALUATORS"

    freeze_files = ["paraphrase_table.json", "paraphrase_table_v2_authored.json", "candidate_gloss_table.json",
                    "leakage_audit.json", "position_balance.json", "evaluator_facing/trials.json",
                    "internal/answer_key.json", "isolated_authoring/authoring_input.json",
                    "isolated_authoring/equivalence_review.json", "isolated_authoring/leakage_review.json",
                    "evaluator_protocol.json", "analysis_plan_flagged_words.json"]
    freeze = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in freeze_files if (OUT / f).exists()}
    report = {"artifact_type": "word_specificity_packet_freeze_v2", "corrects_audit_commit": "73030960",
              "n_confirmatory_rows_paraphrased": len(CB), "repeats_per_base_trial": REPEATS,
              "packet_counts_per_set_arm_presentations": counts_out, "n_trials_evaluator_facing": len(trials),
              "position_all_arms_uniform_chi2_zero": all_balanced,
              "position_agents_no_primary_edge": pos_agents_no_edge,
              "leakage_flags_total": len(flags), "leakage_flags_in_set_exploitable": len(exploitable),
              "leakage_flags_new_not_preflagged": len(new_exploitable),
              "flagged_words_source_intrinsic": FLAGGED_WORDS,
              "seeds": SEEDS, "packet_verdict": packet_verdict, "readiness_verdict": readiness,
              "frozen_hashes": freeze,
              "guardrails": "no evaluator run; no result; confirmatory backbone only; no vowel in packets; "
                            "evaluator-facing exposes no Devanāgarī/IAST/consonant/rowid/arm/word/path"}
    (OUT / "packet_freeze_index.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build()
    print("rows paraphrased:", r["n_confirmatory_rows_paraphrased"], "| repeats:", r["repeats_per_base_trial"])
    print("evaluator-facing presentations:", r["n_trials_evaluator_facing"])
    print("counts:", r["packet_counts_per_set_arm_presentations"])
    print("all-arms position chi2==0:", r["position_all_arms_uniform_chi2_zero"],
          "| position agents no edge:", r["position_agents_no_primary_edge"])
    print("leakage flags:", r["leakage_flags_total"], "| in-set exploitable:", r["leakage_flags_in_set_exploitable"])
    print("PACKET VERDICT:", r["packet_verdict"])
    print("READINESS   :", r["readiness_verdict"])
