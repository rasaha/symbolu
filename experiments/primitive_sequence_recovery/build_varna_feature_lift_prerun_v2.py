#!/usr/bin/env python3
"""Varṇa Feature-Lift pre-run data assembly & freeze (docs/data only).

Assembles an attested-Sanskrit candidate pool, applies the FROZEN eligibility of
VARNA_FEATURE_LIFT_PREREG_V1.md, links each controlling English gloss to the pinned Warriner (2013) affective
norms, applies dependence controls, and freezes a grouped train/dev/test split + the shuffle-control and
base-representation specs. NO embeddings, NO model training, NO real-vs-shuffled comparison, NO lift metric.

Outcome-blind: candidate glosses/categories/ambiguity are decided on LINGUISTIC grounds before any target value
is used to select words; inclusion takes ALL words passing the frozen rules (never target-selected). Recording
raw target values is required (independent label), not a lift metric.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
from collections import Counter, OrderedDict

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "varna_feature_lift_prerun_v2"
NORM_CSV = HERE / "varna_feature_lift_prerun_v1" / "_norm_src" / "Ratings_Warriner_et_al.csv"
LEXICON = HERE / "frozen" / "varna_native_stage1_merged_v3.json"

# ---- frozen constants (set BEFORE viewing any target distribution) ----
N_INCLUDED_FLOOR = 30          # readiness gate; include ALL eligible, never a target-selected subset
SPLIT_SEED = 20260101
TEST_FRACTION = 0.30
DEV_FRACTION = 0.15
SHUFFLE_K = 1000
SHUFFLE_MASTER_SEED = 20260101
# 33 confirmatory-backbone consonants (mapped); consonant-only primary feature (prereg §2/§4)
LEX = {r["canonical_parser_unit"]: r for r in json.loads(LEXICON.read_text(encoding="utf-8"))["rows"]}
MAPPED_CONSONANTS = {u for u, r in LEX.items()
                     if r.get("activation_scope") == "CONFIRMATORY_BACKBONE" and r.get("binding_vritti")}

FAIL = {  # taxonomy
    "NO_EXACT_NORM_MATCH", "TRANSLATION_AMBIGUITY", "MULTIWORD_GLOSS_REQUIRED", "MATERIAL_GLOSS_VALENCE_CONFLICT",
    "PARSER_INVALID", "NO_MAPPED_CONSONANTS", "INSUFFICIENT_MAPPING_COVERAGE", "DUPLICATE_ENGLISH_GLOSS",
    "SANSKRIT_MORPHOLOGICAL_DUPLICATE", "NEAR_SYNONYM_DEPENDENCE", "PROPER_NAME_OR_TECHNICAL_TERM",
    "UNSUPPORTED_AFFECTIVE_TARGET", "GROUP_SPLIT_CONFLICT", "OTHER_PREDECLARED_EXCLUSION",
}

# ---------------------------------------------------------------------------------------------------------------
# Candidate list — attested Monier-Williams headwords. Fields decided on LINGUISTIC grounds only (no target peek).
# (devanāgarī, IAST, controlling_gloss, [alt_glosses], category, root_family, ambiguity, ambiguity_reason_or_"")
# ambiguity in {"clear","ambiguous","technical"}; ambiguous/technical are pre-declared exclusions.
# ---------------------------------------------------------------------------------------------------------------
C = [
 # emotions / states
 ("क्रोध","krodha","anger",["wrath","rage"],"emotion","√krudh","clear",""),
 ("भय","bhaya","fear",["dread"],"emotion","√bhī","clear",""),
 ("लोभ","lobha","greed",["avarice"],"emotion","√lubh","clear",""),
 ("मोह","moha","delusion",["confusion","infatuation"],"emotion","√muh","clear",""),
 ("शान्ति","śānti","peace",["calm","tranquility"],"emotion","√śam","clear",""),
 ("सुख","sukha","happiness",["pleasure","ease"],"emotion","sukha","clear",""),
 ("दुःख","duḥkha","sorrow",["suffering","pain"],"emotion","duḥkha","clear",""),
 ("हर्ष","harṣa","joy",["delight"],"emotion","√hṛṣ","clear",""),
 ("शोक","śoka","grief",["mourning"],"emotion","√śuc","clear",""),
 ("लज्जा","lajjā","shame",["modesty"],"emotion","√lajj","clear",""),
 ("द्वेष","dveṣa","hatred",["aversion"],"emotion","√dviṣ","clear",""),
 ("ईर्ष्या","īrṣyā","envy",["jealousy"],"emotion","√īrṣy","clear",""),
 ("मद","mada","pride",["intoxication"],"emotion","√mad","ambiguous","pride vs intoxication — materially different"),
 ("काम","kāma","desire",["love","lust"],"emotion","√kam","ambiguous","desire vs love vs lust — materially different"),
 ("भक्ति","bhakti","devotion",["worship"],"emotion","√bhaj","clear",""),
 ("रोग","roga","disease",["illness"],"state","√ruj","clear",""),
 ("मृत्यु","mṛtyu","death",[],"state","√mṛ","clear",""),
 ("निद्रा","nidrā","sleep",[],"state","√nid","clear",""),
 ("स्वप्न","svapna","dream",[],"state","√svap","clear",""),
 ("स्मृति","smṛti","memory",[],"cognitive","√smṛ","clear",""),
 ("बुद्धि","buddhi","intellect",["intelligence"],"cognitive","√budh","clear",""),
 ("मनस्","manas","mind",[],"cognitive","√man","clear",""),
 ("युद्ध","yuddha","war",["battle"],"action","√yudh","clear",""),
 ("वीर","vīra","hero",[],"person","vīra","clear",""),
 ("यशस्","yaśas","fame",["glory"],"abstract","yaśas","clear",""),
 ("धन","dhana","wealth",["money","riches"],"abstract","dhana","clear",""),
 ("क्षुधा","kṣudhā","hunger",[],"state","√kṣudh","clear",""),
 ("पाप","pāpa","sin",["evil"],"abstract","pāpa","clear",""),
 ("बल","bala","strength",["power"],"abstract","bala","clear",""),
 ("सत्य","satya","truth",[],"abstract","sat","clear",""),
 ("ज्ञान","jñāna","knowledge",[],"cognitive","√jñā","clear",""),
 ("धर्म","dharma","virtue",["duty","law","religion"],"abstract","√dhṛ","ambiguous","virtue/duty/law/religion — materially different"),
 ("शत्रु","śatru","enemy",["foe"],"person","śatru","clear",""),
 ("मित्र","mitra","friend",[],"person","mitra","clear",""),
 # animals
 ("गज","gaja","elephant",[],"animal","gaja","clear",""),
 ("अश्व","aśva","horse",[],"animal","aśva","clear",""),
 ("मृग","mṛga","deer",["antelope"],"animal","mṛga","clear",""),
 ("सिंह","siṃha","lion",[],"animal","siṃha","clear",""),
 ("व्याघ्र","vyāghra","tiger",[],"animal","vyāghra","clear",""),
 ("सर्प","sarpa","snake",["serpent"],"animal","√sṛp","clear",""),
 ("मीन","mīna","fish",[],"animal","mīna","clear",""),
 ("अज","aja","goat",[],"animal","aja","clear",""),
 ("गो","go","cow",["ox","earth","ray"],"animal","go","ambiguous","cow/earth/ray/speech — materially different"),
 ("हंस","haṃsa","swan",["goose"],"animal","haṃsa","clear",""),
 ("खग","khaga","bird",[],"animal","kha+ga","clear",""),
 ("वृक","vṛka","wolf",[],"animal","vṛka","clear",""),
 ("गर्दभ","gardabha","donkey",["ass"],"animal","gardabha","clear",""),
 ("कपि","kapi","monkey",["ape"],"animal","kapi","clear",""),
 ("वानर","vānara","monkey",["ape"],"animal","vānara","clear",""),
 ("मार्जार","mārjāra","cat",[],"animal","mārjāra","clear",""),
 # body
 ("अस्थि","asthi","bone",[],"body","asthi","clear",""),
 ("दन्त","danta","tooth",[],"body","danta","clear",""),
 ("केश","keśa","hair",[],"body","keśa","clear",""),
 ("हस्त","hasta","hand",[],"body","hasta","clear",""),
 ("कर","kara","hand",["ray","tax","doer"],"body","√kṛ","ambiguous","hand/ray/tax — materially different"),
 ("पाद","pāda","foot",[],"body","pāda","clear",""),
 ("नेत्र","netra","eye",[],"body","netra","clear",""),
 ("कर्ण","karṇa","ear",[],"body","karṇa","clear",""),
 ("मुख","mukha","face",["mouth"],"body","mukha","ambiguous","face vs mouth — materially different"),
 ("जिह्वा","jihvā","tongue",[],"body","jihvā","clear",""),
 ("शिरस्","śiras","head",[],"body","śiras","clear",""),
 ("हृदय","hṛdaya","heart",[],"body","hṛd","clear",""),
 ("रक्त","rakta","blood",["red"],"body","√rañj","ambiguous","blood (noun) vs red (adj) — materially different"),
 ("ग्रीवा","grīvā","neck",[],"body","grīvā","clear",""),
 # nature / objects
 ("अग्नि","agni","fire",[],"nature","agni","clear",""),
 ("वह्नि","vahni","fire",[],"nature","vahni","clear",""),
 ("जल","jala","water",[],"nature","jala","clear",""),
 ("वायु","vāyu","wind",["air"],"nature","vāyu","clear",""),
 ("सूर्य","sūrya","sun",[],"nature","sūrya","clear",""),
 ("चन्द्र","candra","moon",[],"nature","candra","clear",""),
 ("मेघ","megha","cloud",[],"nature","megha","clear",""),
 ("नदी","nadī","river",[],"nature","nadī","clear",""),
 ("गिरि","giri","mountain",[],"nature","giri","clear",""),
 ("पर्वत","parvata","mountain",[],"nature","parvata","clear",""),
 ("वृक्ष","vṛkṣa","tree",[],"nature","vṛkṣa","clear",""),
 ("पुष्प","puṣpa","flower",[],"nature","puṣpa","clear",""),
 ("फल","phala","fruit",[],"nature","phala","clear",""),
 ("बीज","bīja","seed",[],"nature","bīja","clear",""),
 ("तृण","tṛṇa","grass",[],"nature","tṛṇa","clear",""),
 ("लता","latā","creeper",["vine"],"nature","latā","clear",""),
 ("अश्म","aśma","stone",["rock"],"nature","aśman","clear",""),
 ("मणि","maṇi","jewel",["gem"],"object","maṇi","clear",""),
 ("सुवर्ण","suvarṇa","gold",[],"object","suvarṇa","clear",""),
 ("हिम","hima","snow",["frost"],"nature","hima","clear",""),
 ("तारा","tārā","star",[],"nature","tārā","clear",""),
 ("वर्ष","varṣa","rain",["year"],"nature","√vṛṣ","ambiguous","rain vs year — materially different"),
 ("विद्युत्","vidyut","lightning",[],"nature","vi+√dyut","clear",""),
 ("रथ","ratha","chariot",[],"object","ratha","clear",""),
 ("गृह","gṛha","house",[],"object","gṛha","clear",""),
 ("घट","ghaṭa","pot",["jar"],"object","ghaṭa","clear",""),
 ("धूम","dhūma","smoke",[],"nature","dhūma","clear",""),
 ("समुद्र","samudra","sea",["ocean"],"nature","samudra","clear",""),
 ("वन","vana","forest",[],"nature","vana","clear",""),
 ("क्षेत्र","kṣetra","field",["body","land"],"object","kṣetra","ambiguous","field/body/sacred-place — materially different"),
 ("पुस्तक","pustaka","book",[],"object","pustaka","clear",""),
 ("खड्ग","khaḍga","sword",[],"object","khaḍga","clear",""),
 ("यज्ञ","yajña","sacrifice",["worship"],"abstract","√yaj","technical","ritual technical term"),
 ("देव","deva","god",["deity"],"abstract","deva","technical","religious technical term"),
 ("आत्मन्","ātman","self",["soul"],"abstract","ātman","technical","philosophical technical term"),
 # actions / processes
 ("गति","gati","motion",[],"action","√gam","clear",""),
 ("गमन","gamana","going",[],"action","√gam","clear",""),
 ("नृत्य","nṛtya","dance",[],"action","√nṛt","clear",""),
 ("हास","hāsa","laughter",[],"action","√has","clear",""),
 ("दान","dāna","gift",["giving","donation"],"action","√dā","clear",""),
 ("क्रीडा","krīḍā","play",["sport"],"action","√krīḍ","clear",""),
 ("भोजन","bhojana","food",["meal","eating"],"action","√bhuj","ambiguous","food vs eating vs meal — materially different"),
]


def sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_norms():
    d = {}
    with open(NORM_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d[row["Word"].strip().lower()] = row
    return d


def parse_word(dev):
    r = P.parse(dev)
    av = r.get("atomic_varnas", [])
    cons = [u["unit"] for u in av if u["type"] == "consonant"]
    warnings = list(r.get("warnings", []))
    unmapped = [c for c in cons if c not in MAPPED_CONSONANTS]
    return {"n_atomic": len(av), "consonants": cons, "n_consonants": len(cons),
            "unmapped_consonants": sorted(set(unmapped)), "warnings": warnings,
            "mapped_coverage": (len([c for c in cons if c in MAPPED_CONSONANTS]) / len(cons)) if cons else 0.0}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    norms = load_norms()
    norm_sha = hashlib.sha256(NORM_CSV.read_bytes()).hexdigest()

    considered = []
    for i, (dev, iast, gloss, alts, cat, root, amb, ambr) in enumerate(sorted(C, key=lambda x: x[1]), 1):
        rec = {"candidate_id": f"S{i:03d}", "devanagari": dev, "iast": iast, "controlling_gloss": gloss,
               "alt_glosses": alts, "category": cat, "root_family": root, "attestation": "Monier-Williams",
               "ambiguity_status": amb, "ambiguity_reason": ambr,
               "excluded": False, "failure_reason": None, "failure_stage": None,
               "extra_failures": []}
        # STAGE 1 — source-list scope exclusions (ambiguity / technical / multiword controlling gloss)
        if amb == "ambiguous":
            rec.update(excluded=True, failure_reason="MATERIAL_GLOSS_VALENCE_CONFLICT"
                       if "materially different" in ambr else "TRANSLATION_AMBIGUITY", failure_stage=1)
        elif amb == "technical":
            rec.update(excluded=True, failure_reason="PROPER_NAME_OR_TECHNICAL_TERM", failure_stage=1)
        elif len(gloss.split()) > 1:
            rec.update(excluded=True, failure_reason="MULTIWORD_GLOSS_REQUIRED", failure_stage=1)
        # STAGE 2 — parser / mapping
        pinfo = parse_word(dev)
        rec["parser"] = pinfo
        if not rec["excluded"]:
            if pinfo["warnings"]:
                rec.update(excluded=True, failure_reason="PARSER_INVALID", failure_stage=2)
            elif pinfo["n_consonants"] == 0:
                rec.update(excluded=True, failure_reason="NO_MAPPED_CONSONANTS", failure_stage=2)
            elif pinfo["mapped_coverage"] < 1.0:
                rec.update(excluded=True, failure_reason="INSUFFICIENT_MAPPING_COVERAGE", failure_stage=2)
        # STAGE 3/4 — gloss linkage + norm coverage (exact lemma match)
        entry = norms.get(gloss.lower())
        rec["exact_norm_match"] = entry is not None
        if not rec["excluded"]:
            if entry is None:
                rec.update(excluded=True, failure_reason="NO_EXACT_NORM_MATCH", failure_stage=4)
            else:
                rec["target"] = {"arousal_A_mean_sum": float(entry["A.Mean.Sum"]),
                                 "valence_V_mean_sum": float(entry["V.Mean.Sum"]),
                                 "dominance_D_mean_sum": float(entry["D.Mean.Sum"]),
                                 "match": "exact_lemma", "lookup": "lowercase exact",
                                 "raw_entry_index": entry[""]}
        considered.append(rec)

    # STAGE 5 — dependence controls: dedupe identical controlling gloss (keep first IAST-asc), keep root groups
    survivors = [r for r in considered if not r["excluded"]]
    seen_gloss = {}
    for r in sorted(survivors, key=lambda r: r["iast"]):
        g = r["controlling_gloss"].lower()
        if g in seen_gloss:
            r.update(excluded=True, failure_reason="DUPLICATE_ENGLISH_GLOSS", failure_stage=5,
                     duplicate_of=seen_gloss[g])
        else:
            seen_gloss[g] = r["candidate_id"]
    included = [r for r in considered if not r["excluded"]]

    # dependency groups (for grouped split): group by root_family
    for r in considered:
        r["group_id"] = r["root_family"]
    groups = OrderedDict()
    for r in sorted(included, key=lambda r: r["iast"]):
        groups.setdefault(r["group_id"], []).append(r["candidate_id"])

    # STAGE 6 — deterministic grouped split (hash-ordered; no target used)
    def gkey(gid):
        return hashlib.sha256(f"{SPLIT_SEED}:{gid}".encode()).hexdigest()
    ordered_groups = sorted(groups, key=gkey)
    n_words = len(included)
    n_test_target = round(TEST_FRACTION * n_words)
    n_dev_target = round(DEV_FRACTION * n_words)
    split = {}
    cnt = Counter()
    for gid in ordered_groups:
        members = groups[gid]
        if cnt["test"] < n_test_target:
            part = "test"
        elif cnt["dev"] < n_dev_target:
            part = "dev"
        else:
            part = "train"
        for cid in members:
            split[cid] = part
        cnt[part] += len(members)
    for r in included:
        r["split"] = split[r["candidate_id"]]

    # ---- write artifacts ----
    def W(name, obj):
        (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    W("candidate_source_list.json", {"schema": "varna_lift_candidate_source_list_v1", "n": len(considered),
                                     "rows": considered})
    W("excluded_word_manifest.json", {"schema": "varna_lift_excluded_v1",
                                      "rows": [r for r in considered if r["excluded"]]})
    W("included_word_manifest.json", {"schema": "varna_lift_included_v1", "n": len(included),
                                      "rows": [{k: r[k] for k in ("candidate_id", "devanagari", "iast",
                                               "controlling_gloss", "alt_glosses", "category", "root_family",
                                               "group_id", "split", "parser", "target")} for r in included]})
    W("word_target_table.json", {"schema": "varna_lift_word_target_v1",
                                 "target_fields": {"primary": "arousal_A_mean_sum",
                                                   "secondary": ["valence_V_mean_sum", "dominance_D_mean_sum"]},
                                 "transform": "NONE (raw Warriner Mean.Sum; no transform frozen)",
                                 "rows": [{"candidate_id": r["candidate_id"], "iast": r["iast"],
                                           "gloss": r["controlling_gloss"], **r["target"]} for r in included]})
    W("affective_norm_source_manifest.json", {
        "schema": "varna_lift_norm_source_v1", "dataset": "Warriner, Kuperman & Brysbaert (2013) VAD ratings",
        "version": "original (13,915 lemmas)", "source_url":
        "https://raw.githubusercontent.com/JULIELab/XANEW/master/Ratings_Warriner_et_al.csv",
        "license": "research use (Behavior Research Methods 2013 supplementary; XANEW mirror)",
        "sha256": norm_sha, "n_lemmas": len(norms), "score_range": "1..9 (Likert mean)",
        "primary_field": "A.Mean.Sum (arousal/activation)",
        "secondary_fields": ["V.Mean.Sum (valence)", "D.Mean.Sum (dominance)"],
        "normalization": "raw mean; no transform frozen", "lookup": "lowercase exact lemma; fuzzy PROHIBITED",
        "committed_to_repo": False, "note": "raw CSV pinned by checksum, not committed (size/license); per-word "
        "targets extracted into word_target_table.json"})
    W("dependency_groups.json", {"schema": "varna_lift_dep_groups_v1", "grouping": "root_family (splits never "
                                 "cross a group); English-gloss deduped (DUPLICATE_ENGLISH_GLOSS)",
                                 "groups": {g: m for g, m in groups.items()}})
    split_ids = {p: sorted(r["candidate_id"] for r in included if r["split"] == p) for p in ("train", "dev", "test")}
    W("split_manifest.json", {"schema": "varna_lift_split_v1", "seed": SPLIT_SEED,
                              "policy": "grouped by root_family; hash-ordered; target NOT used; no manual "
                              "reassignment; test untouched until final run",
                              "fractions": {"test": TEST_FRACTION, "dev": DEV_FRACTION},
                              "sizes": {p: len(v) for p, v in split_ids.items()},
                              "assignments": split_ids, "assignments_sha256": sha(split_ids)})
    real_assign = sorted([(c, LEX[c]["binding_vritti"]) for c in sorted(MAPPED_CONSONANTS)])
    W("shuffle_control_manifest.json", {"schema": "varna_lift_shuffle_v1",
        "mapped_consonant_inventory": sorted(MAPPED_CONSONANTS), "n_mapped": len(MAPPED_CONSONANTS),
        "real_consonant_to_gloss_sha256": sha(real_assign),
        "procedure": "global bijective permutation of the 33 consonant->gloss assignments; recompute features; "
        "identical encoder+pooling for real & shuffled; preserves gloss inventory, dimensionality, word lengths, "
        "multiplicity, missingness — only the consonant->gloss identity changes",
        "K_permutation_seeds": SHUFFLE_K, "master_seed": SHUFFLE_MASTER_SEED,
        "derangement_required": False, "fixed_points": "allowed and recorded per seed",
        "note": "NO permutation executed here; procedure frozen for the run"})
    W("base_representation_manifest.json", {"schema": "varna_lift_base_rep_v1",
        "primary_base_input": "controlling English gloss text (lowercased lemma)",
        "secondary_base_input": "Sanskrit IAST form (weaker base; reported separately)",
        "encoder_class": "frozen sentence-embedding model", "recommended_id": "sentence-transformers/all-mpnet-base-v2",
        "encoder_revision": "PIN_AT_RUN (id+revision+hash fixed before any metric; encoder never tuned)",
        "pooling": "mean", "dimensionality": 768, "normalization": "L2",
        "feature_encoder": "SAME frozen sentence encoder applied to each varṇa's binding gloss; f(w)=mean-pool, "
        "multiplicity preserved, order-free (prereg §4)",
        "base_must_not_receive_varna_packet": True, "executed": False})

    funnel = [("considered", len(considered)),
              ("scope_valid (stage1 pass)", sum(1 for r in considered if not (r["failure_stage"] == 1))),
              ("parser_valid", sum(1 for r in considered if r["failure_stage"] not in (1, 2))),
              ("gloss_frozen", sum(1 for r in considered if r["failure_stage"] not in (1, 2))),  # gloss frozen at scope
              ("exact_norm_match", sum(1 for r in considered if r.get("exact_norm_match") and r["failure_stage"] not in (1, 2))),
              ("dependence_clean", sum(1 for r in considered if not r["excluded"] or r["failure_reason"] == "DUPLICATE_ENGLISH_GLOSS") - sum(1 for r in considered if r["failure_reason"] == "DUPLICATE_ENGLISH_GLOSS")),
              ("included", len(included))]
    reason_counts = Counter(r["failure_reason"] for r in considered if r["excluded"])
    stage_counts = Counter(r["failure_stage"] for r in considered if r["excluded"])
    cat_incl = Counter(r["category"] for r in included)
    W("sample_failure_funnel.json", {"schema": "varna_lift_funnel_v1", "funnel": funnel,
                                     "exclusion_counts_by_reason": dict(reason_counts),
                                     "exclusion_counts_by_stage": {str(k): v for k, v in stage_counts.items()},
                                     "included_category_distribution": dict(cat_incl)})

    readiness = ("READY_FOR_FEATURE_EXTRACTION_AND_LIFT_RUN" if len(included) >= N_INCLUDED_FLOOR
                 else "BLOCKED_INSUFFICIENT_EXACT_NORM_MATCHES")
    manifest = {"schema": "varna_lift_prerun_freeze_v1",
                "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
                "controlling_prereg": "VARNA_FEATURE_LIFT_PREREG_V1.md",
                "parser_sha256": hashlib.sha256((HERE / "sanskrit_stage1_parser.py").read_bytes()).hexdigest(),
                "lexicon_sha256": hashlib.sha256(LEXICON.read_bytes()).hexdigest(),
                "norm_sha256": norm_sha, "n_included": len(included), "n_included_floor": N_INCLUDED_FLOOR,
                "split_sizes": {p: len(v) for p, v in split_ids.items()},
                "no_embeddings_or_metrics_computed": True, "no_target_informed_selection": True,
                "artifact_hashes": {}, "readiness": readiness}
    for fn in ("candidate_source_list.json", "included_word_manifest.json", "excluded_word_manifest.json",
               "word_target_table.json", "affective_norm_source_manifest.json", "dependency_groups.json",
               "split_manifest.json", "shuffle_control_manifest.json", "base_representation_manifest.json",
               "sample_failure_funnel.json"):
        manifest["artifact_hashes"][fn] = hashlib.sha256((OUT / fn).read_bytes()).hexdigest()
    W("prerun_freeze_manifest.json", manifest)
    return {"n_considered": len(considered), "n_included": len(included), "readiness": readiness,
            "reason_counts": dict(reason_counts), "split": {p: len(v) for p, v in split_ids.items()},
            "cat": dict(cat_incl), "funnel": funnel, "included": included}


if __name__ == "__main__":
    r = build()
    print(json.dumps({k: r[k] for k in ("n_considered", "n_included", "readiness", "reason_counts", "split", "cat", "funnel")},
                     ensure_ascii=False, indent=2))
