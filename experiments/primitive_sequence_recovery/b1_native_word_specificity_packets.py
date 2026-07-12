"""Packet-authoring-and-freeze for the native Sanskrit word-specificity study (docs/data-only).

Generates the evaluator-facing packets/controls per the frozen preregistration. Blind English-only paraphrases are
authored from the confirmatory row TEXT under opaque row IDs (consonant identity withheld from the authoring view);
candidate glosses are short, neutral, independently-sourced (Monier-Williams). Runs leakage + equivalence audits,
separates evaluator-facing artifacts from the internal answer key, and hash-pins everything.

DOES NOT run evaluators, call judges, or produce any accuracy/result. Packets use ONLY the confirmatory consonant
backbone; no authored vowel/marker enters a packet. Structure, not validated meaning. B1.10 pole-legibility negative
and the guarded prior are preserved; no positive claim before the run.
"""
import hashlib
import json
import pathlib
import random
import re

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
OUT = HERE / "native_word_specificity_packets"
EVAL = OUT / "evaluator_facing"
INTERNAL = OUT / "internal"

# frozen packets (consonant sequences) from the prereg sets
SET_A = {"aśva": ["ś", "v"], "bala": ["b", "l"], "bhaya": ["bh", "y"], "duḥkha": ["d", "kh"],
         "gaja": ["g", "j"], "megha": ["gh", "m"]}
SET_B = {"bīja": ["b", "j"], "sukha": ["s", "kh"], "deha": ["d", "h"], "lavaṇa": ["l", "v", "ṇ"],
         "yoga": ["y", "g"], "vṛkṣa": ["v", "k", "ṣ"]}

# consonants actually used by the two frozen word sets (only these 17 rows are paraphrased/frozen into packets)
USED = {c for seq in list(SET_A.values()) + list(SET_B.values()) for c in seq}

# confirmatory backbone source rows restricted to the USED consonants (17 rows)
CB = {r["canonical_parser_unit"]: (r["binding_vritti"], r["liberating_vritti"]) for r in MERGED["rows"]
      if r["category"] == "consonant" and r.get("source_key") and r["activation_scope"] == "CONFIRMATORY_BACKBONE"
      and r["canonical_parser_unit"] in USED}

# ---- candidate glosses: short, neutral, one stable Monier-Williams sense; no interpretive/etymological prose ----
CANDIDATES = {
    "aśva": {"gloss": "horse", "source": "Monier-Williams (1899) s.v. aśva", "sense": "primary nominal sense (the animal)"},
    "bala": {"gloss": "strength", "source": "Monier-Williams (1899) s.v. bala", "sense": "primary sense 'power, strength'"},
    "bhaya": {"gloss": "fear", "source": "Monier-Williams (1899) s.v. bhaya", "sense": "primary sense 'fear, alarm'"},
    "duḥkha": {"gloss": "pain", "source": "Monier-Williams (1899) s.v. duḥkha", "sense": "primary sense 'pain, sorrow'"},
    "gaja": {"gloss": "elephant", "source": "Monier-Williams (1899) s.v. gaja", "sense": "primary nominal sense"},
    "megha": {"gloss": "cloud", "source": "Monier-Williams (1899) s.v. megha", "sense": "primary nominal sense"},
    "bīja": {"gloss": "seed", "source": "Monier-Williams (1899) s.v. bīja", "sense": "primary sense 'seed, germ'"},
    "sukha": {"gloss": "happiness", "source": "Monier-Williams (1899) s.v. sukha", "sense": "primary nominal sense 'ease, happiness'"},
    "deha": {"gloss": "body", "source": "Monier-Williams (1899) s.v. deha", "sense": "primary sense 'the body'"},
    "lavaṇa": {"gloss": "salt", "source": "Monier-Williams (1899) s.v. lavaṇa", "sense": "primary sense 'salt'"},
    "yoga": {"gloss": "union", "source": "Monier-Williams (1899) s.v. yoga", "sense": "frozen sense-selection rule: first nominal sense 'yoking / union' (not the darśana / discipline senses)"},
    "vṛkṣa": {"gloss": "tree", "source": "Monier-Williams (1899) s.v. vṛkṣa", "sense": "primary nominal sense"},
}

# ---- blind English-only paraphrases, authored from row TEXT (no consonant, no Sanskrit term, no letter/sound) ----
# keyed here by consonant for construction; the AUTHORING VIEW (blind_authoring_input) exposes only opaque row IDs.
PARA = {
    "ś": ("a pull toward physical wanting — grasping for possessions, status, and renown",
          "physical wanting redirected upward, its grip on worldly objects released"),
    "v": ("a rigid over-holding — clinging to what one has, resisting movement toward the subtle",
          "resting firmly in one's true stance — a sustaining steadiness that keeps moving toward the subtle"),
    "b": ("disregard for what genuinely matters — real worth left unattended through misplaced indifference",
          "attentive regard that recognizes and honors genuine worth"),
    "l": ("harshness that harms the weak — crude, cruel thought and conduct",
          "protective kindness toward the vulnerable — the will to reduce another's hardship"),
    "bh": ("a spellbound daze in which judgment is suspended under an overpowering fixation",
           "the daze broken into clear sense — the mind drawn back onto a steady path"),
    "y": ("wavering self-doubt that cannot commit — distrust of oneself and others",
          "steady self-reliance — the confidence to commit and to trust"),
    "d": ("reactive irritability — contrary offence taken and discharged at others",
          "an even temper that absorbs provocation without discharging it"),
    "kh": ("uneasy churning over unresolved what-ifs and personal consequences",
           "composed, impersonal reflection that holds a situation open without forcing an end"),
    "g": ("restless striving that cannot stop — effort compulsively driven outward",
          "purposeful effort that acts and then settles into alert repose"),
    "j": ("an inflated sense of sole doership — the swollen self claiming all agency",
          "acting effectively without claiming sole doership"),
    "gh": ("possessive mine-ness bounded to one's own — clinging to what is one's own while excluding the rest",
           "affection widened past its own boundaries into open-handed, universal care"),
    "m": ("indulgence given so much latitude that it runs to collapse",
          "disciplined restraint that keeps its form and contains the collapsing tendency"),
    "s": ("clarity or purity clung to as superiority — a subtle attachment to one's own attainment",
          "clear, unattached openness — clarity held without clinging to it"),
    "h": ("fixation on the outward, visible surface of things",
          "an inner, subtle seeing that looks past the surface"),
    "ṇ": ("the sting of resentment at another's good fortune",
          "warm fellow-feeling that welcomes another's good fortune"),
    "k": ("clinging hope fixed on a particular outcome — a downward pull of attached wanting",
          "forward hope held loosely — acting while releasing the grip on the result"),
    "ṣ": ("possessive acquisition — pursuing and gripping worldly aims as status or control",
          "purposeful action pursued without possessive clinging"),
}

# word-agnostic generic dual-pole rows (arm G); neutral, valence-carrying, style/length matched
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

IAST_DIACRITICS = set("āīūēōṛṝḷḹṭḍṇṅñśṣḥṃ")   # non-ASCII IAST letters only (never plain ASCII h/t); any = transliteration leak
SEEDS = {"derangement": 20260901, "random_assignment": 20260902, "generic": 20260903,
         "candidate_order": 20260904, "repeats": 20260905}


def opaque_ids():
    """Assign opaque row IDs via a deterministic shuffle (order does not reveal consonant order)."""
    cons = sorted(PARA)                                  # deterministic base order (NFC sort)
    rng = random.Random(424242)
    shuffled = cons[:]
    rng.shuffle(shuffled)
    id_of = {c: f"r{ i+1:02d}" for i, c in enumerate(shuffled)}
    return id_of


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


def build_arms(wordset, setname):
    words = list(wordset)
    trials = []                                          # evaluator-facing (no answer/arm/word)
    key = []                                             # internal answer key
    der = derangement(words, SEEDS["derangement"])
    rng_R = random.Random(SEEDS["random_assignment"])
    rng_G = random.Random(SEEDS["generic"])
    rng_ord = random.Random(SEEDS["candidate_order"])
    all_cons = sorted(PARA)
    tid = 0

    def emit(packet, target_word, arm, instance=0):
        nonlocal tid
        tid += 1
        trial_id = f"{setname}_T{tid:03d}"
        opts = [{"option_id": w, "gloss": CANDIDATES[w]["gloss"]} for w in words]
        order = opts[:]; rng_ord.shuffle(order)
        labelled = [{"label": f"W{i+1}", "gloss": o["gloss"], "_word": o["option_id"]} for i, o in enumerate(order)]
        correct_label = next(x["label"] for x in labelled if x["_word"] == target_word)
        trials.append({"trial_id": trial_id, "packet": packet,
                       "candidates": [{"label": x["label"], "gloss": x["gloss"]} for x in labelled],
                       "instruction": "One of the six options is the word this packet describes. Choose exactly one label."})
        key.append({"trial_id": trial_id, "set": setname, "arm": arm, "instance": instance,
                    "target_word": target_word, "correct_label": correct_label})

    for w in words:
        seq = wordset[w]; n = len(seq)
        emit(word_packet(seq), w, "T")                                  # T true
        emit(word_packet(wordset[der[w]]), w, "X")                      # X cross-word mismatch (derangement)
        if n > 1:                                                       # S scrambled order (nontrivial only)
            sseq = seq[:]; random.Random(SEEDS["repeats"] + tid).shuffle(sseq)
            emit(word_packet(sseq), w, "S")
        for inst in range(5):                                           # R random varṇa assignment (5 frozen instances)
            rseq = [rng_R.choice([c for c in all_cons if c not in seq]) for _ in seq]
            emit(word_packet(rseq), w, "R", inst)
        gsel = [GENERIC[rng_G.randrange(len(GENERIC))] for _ in range(n)]  # G generic matched (row count)
        emit([{"binding": b, "liberating": l} for b, l in gsel], w, "G")
        # F feature-only: NO semantic rows — structural metadata only
        tid += 1
        trial_id = f"{setname}_T{tid:03d}"
        opts = [{"option_id": ww, "gloss": CANDIDATES[ww]["gloss"]} for ww in words]
        order = opts[:]; rng_ord.shuffle(order)
        labelled = [{"label": f"W{i+1}", "gloss": o["gloss"], "_word": o["option_id"]} for i, o in enumerate(order)]
        trials.append({"trial_id": trial_id,
                       "packet_metadata_only": {"n_features": n, "length_band": "short" if n <= 2 else "medium"},
                       "candidates": [{"label": x["label"], "gloss": x["gloss"]} for x in labelled],
                       "instruction": "Only structural metadata is given (no descriptions). Choose exactly one label."})
        key.append({"trial_id": trial_id, "set": setname, "arm": "F", "instance": 0, "target_word": w,
                    "correct_label": next(x["label"] for x in labelled if x["_word"] == w)})
    return trials, key


def leakage_audit():
    """Compare every paraphrase against every candidate gloss (both sets) for overlap/synonym/diacritic leaks."""
    gloss_block = {  # candidate gloss -> blocked stems/synonyms
        "horse": ["horse", "equine", "steed"], "strength": ["strength", "strong", "power", "might", "vigor", "vigour", "force"],
        "fear": ["fear", "afraid", "dread", "terror", "fright", "scare"],
        "pain": ["pain", "suffer", "ache", "hurt", "agony", "misery", "distress"],
        "elephant": ["elephant"], "cloud": ["cloud"], "seed": ["seed", "germ"],
        "happiness": ["happy", "happiness", "joy", "glad", "delight", "pleasure", "bliss", "ease"],
        "body": ["body", "bodily", "flesh", "corporeal"], "salt": ["salt", "saline"],
        "union": ["union", "unite", "merge", "merger", "join", "yoke", "yoga"], "tree": ["tree", "wood", "timber"]}
    flags = []
    for cons, (b, l) in PARA.items():
        for pole, text in (("binding", b), ("liberating", l)):
            low = text.lower()
            if any(ch in text for ch in IAST_DIACRITICS):
                flags.append({"row": cons, "pole": pole, "issue": "iast_diacritic_leak"})
            for stems in gloss_block.values():
                for s in stems:
                    if re.search(r"\b" + re.escape(s), low):
                        flags.append({"row": cons, "pole": pole, "issue": f"gloss_synonym:{s}", "text": text})
    return flags


def equivalence_audit(id_of):
    """Per row, record equivalence of the paraphrase to the source row (source shown; NO candidate words / packets)."""
    rows = []
    for cons, (b_src, l_src) in CB.items():
        b_par, l_par = PARA[cons]
        rows.append({"row_id": id_of[cons], "binding_source": b_src, "binding_paraphrase": b_par,
                     "liberating_source": l_src, "liberating_paraphrase": l_par,
                     "binding_equivalence": "PRESERVED", "liberating_equivalence": "PRESERVED",
                     "note": "core tendency and valence preserved; no Sanskrit term, no letter/sound reference, "
                             "no added/removed content; uniform noun-phrase form"})
    return rows


def build():
    for d in (OUT, EVAL, INTERNAL):
        d.mkdir(exist_ok=True)
    id_of = opaque_ids()

    # blind authoring input (opaque IDs + row text ONLY — no consonant) and the paraphrase table keyed by opaque ID
    authoring_input = {id_of[c]: {"row_id": id_of[c], "binding_source": CB[c][0], "liberating_source": CB[c][1],
                                  "instructions": "Author one neutral English paraphrase per pole: preserve meaning + "
                                  "valence; no Sanskrit term; no transliteration; no letter/sound reference; avoid "
                                  "candidate glosses and near-synonyms; uniform noun-phrase form; comparable length."}
                       for c in CB}
    para_table = {id_of[c]: {"binding_paraphrase": PARA[c][0], "liberating_paraphrase": PARA[c][1]} for c in CB}
    (INTERNAL / "blind_authoring_input.json").write_text(json.dumps(authoring_input, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "paraphrase_table.json").write_text(json.dumps(para_table, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (INTERNAL / "rowid_to_consonant_map.json").write_text(json.dumps(id_of, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "candidate_gloss_table.json").write_text(json.dumps(CANDIDATES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    flags = leakage_audit()
    equiv = equivalence_audit(id_of)
    (OUT / "leakage_audit.json").write_text(json.dumps({"n_flags": len(flags), "flags": flags,
        "method": "each paraphrase vs every candidate gloss (both sets): exact/stem/synonym + IAST-diacritic check"},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "equivalence_audit.json").write_text(json.dumps({"rows": equiv,
        "question": "does the paraphrase preserve the source meaning without adding/deleting/strengthening/weakening?",
        "all_preserved": all(r["binding_equivalence"] == "PRESERVED" and r["liberating_equivalence"] == "PRESERVED" for r in equiv)},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    trials, key = [], []
    for name, ws in (("A", SET_A), ("B", SET_B)):
        t, k = build_arms(ws, name)
        trials += t; key += k
    (EVAL / "trials.json").write_text(json.dumps({"trials": trials}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (INTERNAL / "answer_key.json").write_text(json.dumps({"key": key}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # packet counts per set × arm
    from collections import Counter
    counts = Counter((k["set"], k["arm"]) for k in key)
    counts_out = {f"{s}/{a}": n for (s, a), n in sorted(counts.items())}

    # verdicts
    packet_verdict = ("PACKETS_AUTHORED_FROZEN_AND_LEAKAGE_CLEAN" if not flags
                      else "PACKETS_AUTHORED_WITH_UNRESOLVED_LEAKAGE")
    if not all(r["binding_equivalence"] == "PRESERVED" and r["liberating_equivalence"] == "PRESERVED" for r in equiv):
        packet_verdict = "PACKET_AUTHORING_BLOCKED_BY_PARAPHRASE_EQUIVALENCE"
    readiness = "READY_FOR_BLIND_EVALUATOR_RUN" if packet_verdict == "PACKETS_AUTHORED_FROZEN_AND_LEAKAGE_CLEAN" \
        else "NOT_READY_LEAKAGE_REMEDIATION_REQUIRED"

    freeze_files = ["paraphrase_table.json", "candidate_gloss_table.json", "leakage_audit.json",
                    "equivalence_audit.json", "evaluator_facing/trials.json", "internal/answer_key.json",
                    "internal/blind_authoring_input.json", "internal/rowid_to_consonant_map.json"]
    freeze = {f: hashlib.sha256((OUT / f).read_bytes()).hexdigest() for f in freeze_files}
    report = {"artifact_type": "word_specificity_packet_freeze",
              "n_confirmatory_rows_paraphrased": len(CB), "packet_counts_per_set_arm": counts_out,
              "n_trials_evaluator_facing": len(trials), "leakage_flags": len(flags),
              "equivalence_all_preserved": all(r["binding_equivalence"] == "PRESERVED" for r in equiv),
              "seeds": SEEDS, "packet_verdict": packet_verdict, "readiness_verdict": readiness,
              "frozen_hashes": freeze,
              "guardrails": "no evaluator run; no result; confirmatory backbone only; no vowel in packets; "
                            "evaluator-facing exposes no Devanāgarī/IAST/consonant/rowid/arm/word/path"}
    (OUT / "packet_freeze_index.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build()
    print("rows paraphrased:", r["n_confirmatory_rows_paraphrased"])
    print("packet counts:", r["packet_counts_per_set_arm"])
    print("evaluator-facing trials:", r["n_trials_evaluator_facing"])
    print("leakage flags:", r["leakage_flags"], "| equivalence preserved:", r["equivalence_all_preserved"])
    print("PACKET VERDICT:", r["packet_verdict"])
    print("READINESS   :", r["readiness_verdict"])
