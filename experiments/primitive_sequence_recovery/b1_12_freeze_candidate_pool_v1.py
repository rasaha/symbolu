#!/usr/bin/env python3
"""B1.12 — developmental candidate pool v1 — CURATOR freeze (deterministic; no G0 metrics).

Curator role only (V1.1 §13). Selection is BLIND to all structural metrics: words are chosen from
attestation / meaning / category / morphology / parser-validity ONLY. The parser is run solely to decide
per-word eligibility (completes, no warnings, no unsupported unit, atomic-varṇa length in [2,6]); the ordered
atomic-varṇa SEQUENCES are NOT emitted into any artifact (sealed for the later G0-auditor step). No pairwise
distance, order-distinctness, n-gram, endpoint, subset, or eligibility-for-G0 computation is performed.

Deterministic selection rule (predeclared, outcome-blind): per-category targets, then canonical IAST ascending
(Unicode NFC code-point order) within each category; stable IDs assigned in global IAST order after selection.

Outputs (into b1_12_candidate_pool_v1/): b1_12_candidate_source_list.json, b1_12_candidate_pool_v1.json,
b1_12_candidate_pool_manifest.json. The report B1_12_CANDIDATE_POOL_V1_REPORT.md is authored separately.

EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import unicodedata

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "b1_12_candidate_pool_v1"

LENGTH_BAND = (2, 6)                       # V1.1 §5 (frozen)
FORBIDDEN_UNIT_TYPES = {"unsupported", "missing"}
# predeclared per-category selection targets (outcome-blind; midpoints of V1.1 §12 suggested ranges)
CATEGORY_TARGET = {"ANIMAL": 7, "NATURAL_OBJECT": 6, "BODY": 6, "PHENOMENON": 6, "ACTION": 5, "ABSTRACT": 5}

# ---------------------------------------------------------------------------------------------------------------
# Curated source list. Chosen by MEANING / CATEGORY / MORPHOLOGY / ATTESTATION only — NOT by varṇa sequence.
# attestation: MW = Monier-Williams headword (primary, per V1.1/V1.2); all are standard classical lexemes.
# Each: iast, devanagari, gloss (one controlling ordinary sense), category, root/lemma, morphology note, rationale.
# ---------------------------------------------------------------------------------------------------------------
SOURCE = [
    # ---- ANIMALS / living beings ----
    ("gaja", "गज", "elephant", "ANIMAL", "gaja", "underived noun", "common concrete animal"),
    ("aja", "अज", "goat", "ANIMAL", "aja", "underived noun", "common concrete animal"),
    ("aśva", "अश्व", "horse", "ANIMAL", "aśva", "underived noun", "common concrete animal"),
    ("mṛga", "मृग", "deer", "ANIMAL", "mṛga", "underived noun", "common concrete animal"),
    ("siṃha", "सिंह", "lion", "ANIMAL", "siṃha", "underived noun", "common concrete animal"),
    ("haṃsa", "हंस", "goose/swan", "ANIMAL", "haṃsa", "underived noun", "common concrete bird"),
    ("sarpa", "सर्प", "snake", "ANIMAL", "√sṛp", "agent noun, lexicalized", "common concrete animal"),
    ("mīna", "मीन", "fish", "ANIMAL", "mīna", "underived noun", "common concrete animal"),
    ("khaga", "खग", "bird", "ANIMAL", "kha+ga", "lexicalized compound 'sky-goer'", "common concrete animal"),
    ("vṛka", "वृक", "wolf", "ANIMAL", "vṛka", "underived noun", "common concrete animal"),
    ("nara", "नर", "man", "ANIMAL", "nara", "underived noun", "basic human/living being"),
    # ---- PLANTS / elements / natural objects ----
    ("jala", "जल", "water", "NATURAL_OBJECT", "jala", "underived noun", "basic natural substance"),
    ("vana", "वन", "forest", "NATURAL_OBJECT", "vana", "underived noun", "common natural object"),
    ("vṛkṣa", "वृक्ष", "tree", "NATURAL_OBJECT", "vṛkṣa", "underived noun", "common concrete plant"),
    ("puṣpa", "पुष्प", "flower", "NATURAL_OBJECT", "puṣpa", "underived noun", "common concrete plant part"),
    ("phala", "फल", "fruit", "NATURAL_OBJECT", "phala", "underived noun", "common concrete plant part"),
    ("giri", "गिरि", "mountain", "NATURAL_OBJECT", "giri", "underived noun", "common natural object"),
    ("maṇi", "मणि", "jewel", "NATURAL_OBJECT", "maṇi", "underived noun", "common concrete object"),
    ("aśma", "अश्म", "stone", "NATURAL_OBJECT", "aśman", "consonant-stem noun", "common natural object"),
    ("latā", "लता", "creeper", "NATURAL_OBJECT", "latā", "underived noun", "common concrete plant"),
    ("bīja", "बीज", "seed", "NATURAL_OBJECT", "bīja", "underived noun", "common concrete plant part"),
    ("tṛṇa", "तृण", "grass", "NATURAL_OBJECT", "tṛṇa", "underived noun", "common concrete plant"),
    # ---- BODY / ordinary physical objects ----
    ("kara", "कर", "hand", "BODY", "√kṛ, lexicalized", "underived noun 'hand'", "basic body part"),
    ("pāda", "पाद", "foot", "BODY", "pāda", "underived noun", "basic body part"),
    ("mukha", "मुख", "face/mouth", "BODY", "mukha", "underived noun", "basic body part"),
    ("danta", "दन्त", "tooth", "BODY", "danta", "underived noun", "basic body part"),
    ("keśa", "केश", "hair", "BODY", "keśa", "underived noun", "basic body part"),
    ("nakha", "नख", "nail", "BODY", "nakha", "underived noun", "basic body part"),
    ("asthi", "अस्थि", "bone", "BODY", "asthi", "underived noun", "basic body part"),
    ("nayana", "नयन", "eye", "BODY", "√nī +ana, lexicalized", "deverbal noun 'eye'", "basic body part"),
    ("karṇa", "कर्ण", "ear", "BODY", "karṇa", "underived noun (distinct lexeme from kara)", "basic body part"),
    ("grīvā", "ग्रीवा", "neck", "BODY", "grīvā", "underived noun", "basic body part"),
    # ---- NATURAL FORCES / phenomena ----
    ("agni", "अग्नि", "fire", "PHENOMENON", "agni", "underived noun", "basic natural force"),
    ("vāyu", "वायु", "wind", "PHENOMENON", "vāyu", "underived noun", "basic natural force"),
    ("sūrya", "सूर्य", "sun", "PHENOMENON", "sūrya", "underived noun", "basic natural body"),
    ("candra", "चन्द्र", "moon", "PHENOMENON", "candra", "underived noun", "basic natural body"),
    ("megha", "मेघ", "cloud", "PHENOMENON", "megha", "underived noun", "common natural phenomenon"),
    ("varṣa", "वर्ष", "rain", "PHENOMENON", "√vṛṣ, lexicalized", "noun 'rain/year'", "common natural process"),
    ("hima", "हिम", "snow", "PHENOMENON", "hima", "underived noun", "common natural phenomenon"),
    ("tārā", "तारा", "star", "PHENOMENON", "tārā", "underived noun", "basic natural body"),
    ("nadī", "नदी", "river", "PHENOMENON", "nadī", "underived noun", "common natural object"),
    ("vidyut", "विद्युत्", "lightning", "PHENOMENON", "vi+√dyut", "consonant-final noun", "natural phenomenon"),
    # ---- ORDINARY ACTIONS / motions / processes ----
    ("gati", "गति", "motion", "ACTION", "√gam +ti", "action noun", "ordinary process"),
    ("nṛtya", "नृत्य", "dance", "ACTION", "√nṛt", "action noun", "ordinary action"),
    ("hāsa", "हास", "laughter", "ACTION", "√has", "action noun", "ordinary action"),
    ("dāna", "दान", "gift/giving", "ACTION", "√dā +ana", "action noun (root √dā)", "ordinary action"),
    ("pāna", "पान", "drinking", "ACTION", "√pā +ana", "action noun (root √pā, distinct)", "ordinary action"),
    ("snāna", "स्नान", "bathing", "ACTION", "√snā +ana", "action noun (root √snā, distinct)", "ordinary action"),
    # ---- BASIC STATES / abstract concepts (kept a minority per V1.1 §12) ----
    ("sukha", "सुख", "happiness", "ABSTRACT", "su+kha", "basic state noun", "basic familiar state"),
    ("bhaya", "भय", "fear", "ABSTRACT", "√bhī", "state noun", "basic familiar state"),
    ("bala", "बल", "strength", "ABSTRACT", "bala", "underived noun", "basic familiar quality"),
    ("satya", "सत्य", "truth", "ABSTRACT", "sat+ya", "abstract noun", "basic familiar concept"),
    ("jñāna", "ज्ञान", "knowledge", "ABSTRACT", "√jñā +ana", "abstract noun", "basic familiar concept"),
    ("śakti", "शक्ति", "power", "ABSTRACT", "√śak +ti", "abstract noun", "basic familiar concept"),
]

# Words CONSIDERED but excluded BEFORE parsing, on morphology / ambiguity grounds only (never sequence).
PRE_EXCLUDED = [
    ("hasta", "हस्त", "hand", "BODY", "near-synonym of 'kara' (hand); avoid redundant near-synonym"),
    ("gamana", "गमन", "going", "ACTION", "same root √gam as 'gati'; avoid same-root family"),
    ("duḥkha", "दुःख", "suffering", "ABSTRACT", "prefix-variant of 'kha' paired with 'sukha'; avoid prefix pair"),
    ("go", "गो", "cow", "ANIMAL", "homograph (cow/ray/speech/earth); ambiguous controlling gloss"),
]


def iast_key(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def parse_validity(devanagari: str) -> dict:
    """Run the frozen parser for ELIGIBILITY ONLY. Returns validity + length + warnings; NOT the sequence."""
    try:
        r = P.parse(devanagari)
    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "length": None, "warnings": [f"parser_exception:{type(exc).__name__}"],
                "reason": "parser_did_not_complete"}
    av = r.get("atomic_varnas", [])
    warnings = list(r.get("warnings", []))
    bad_units = sorted({u.get("type") for u in av if u.get("type") in FORBIDDEN_UNIT_TYPES})
    n = len(av)
    reasons = []
    if warnings:
        reasons.append("parser_warning")
    if bad_units:
        reasons.append("unsupported_unit:" + ",".join(bad_units))
    if not (LENGTH_BAND[0] <= n <= LENGTH_BAND[1]):
        reasons.append(f"length_out_of_band:{n}")
    valid = not reasons
    return {"valid": valid, "length": n, "warnings": warnings,
            "reason": None if valid else ";".join(reasons)}


def build():
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- source list (all considered) with parser-validity for the non-pre-excluded ----
    source_rows = []
    for iast, dev, gloss, cat, root, morph, rationale in SOURCE:
        v = parse_validity(dev)
        source_rows.append({
            "iast": iast, "devanagari": dev, "gloss": gloss, "category": cat,
            "lemma_or_root": root, "morphology_notes": morph, "inclusion_rationale": rationale,
            "attestation_source": "Monier-Williams",
            "status": "considered",
            "parser_valid": v["valid"], "atomic_unit_count": v["length"],
            "parser_warnings": v["warnings"], "eligibility_reason": v["reason"],
        })
    for iast, dev, gloss, cat, reason in PRE_EXCLUDED:
        source_rows.append({
            "iast": iast, "devanagari": dev, "gloss": gloss, "category": cat,
            "lemma_or_root": None, "morphology_notes": None, "inclusion_rationale": None,
            "attestation_source": "Monier-Williams",
            "status": "excluded_pre_parse", "exclusion_reason": reason,
            "parser_valid": None, "atomic_unit_count": None, "parser_warnings": None,
            "eligibility_reason": None,
        })
    source_rows.sort(key=lambda r: (r["category"], iast_key(r["iast"])))

    # ---- deterministic selection: per-category target, IAST ascending within category ----
    eligible = [r for r in source_rows if r["status"] == "considered" and r["parser_valid"]]
    selected = []
    per_cat_selected = {}
    for cat, target in CATEGORY_TARGET.items():
        cat_words = sorted([r for r in eligible if r["category"] == cat], key=lambda r: iast_key(r["iast"]))
        take = cat_words[:target]
        per_cat_selected[cat] = len(take)
        selected.extend(take)

    # global IAST order + stable IDs
    selected.sort(key=lambda r: iast_key(r["iast"]))
    pool = []
    for i, r in enumerate(selected, 1):
        pool.append({
            "id": f"W{i:02d}",
            "iast": r["iast"], "devanagari": r["devanagari"], "gloss": r["gloss"],
            "category": r["category"], "lemma_or_root": r["lemma_or_root"],
            "morphology_notes": r["morphology_notes"], "inclusion_rationale": r["inclusion_rationale"],
            "attestation_source": r["attestation_source"],
            "parser_valid": True, "atomic_unit_count": r["atomic_unit_count"],
            "parser_warnings": r["parser_warnings"],
            # NOTE: ordered atomic-varṇa SEQUENCE intentionally SEALED (curator/auditor separation, V1.1 §13)
        })

    # ---- write source list + pool (canonical) ----
    (OUT / "b1_12_candidate_source_list.json").write_text(
        json.dumps({"schema": "b1_12_source_list_v1",
                    "note": "all considered words; selection blind to structural metrics",
                    "length_band": list(LENGTH_BAND), "rows": source_rows},
                   ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    pool_doc = {"schema": "b1_12_candidate_pool_v1",
                "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
                "length_band": list(LENGTH_BAND), "pool_size": len(pool),
                "sequences_sealed": True, "words": pool}
    pool_bytes = json.dumps(pool_doc, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    (OUT / "b1_12_candidate_pool_v1.json").write_bytes(pool_bytes)
    pool_sha = hashlib.sha256(pool_bytes).hexdigest()

    # ---- manifest ----
    parser_path = HERE / "sanskrit_stage1_parser.py"
    parser_sha = hashlib.sha256(parser_path.read_bytes()).hexdigest()
    length_dist = {}
    for w in pool:
        length_dist[str(w["atomic_unit_count"])] = length_dist.get(str(w["atomic_unit_count"]), 0) + 1
    cat_counts = {}
    for w in pool:
        cat_counts[w["category"]] = cat_counts.get(w["category"], 0) + 1
    n_considered = sum(1 for r in source_rows if r["status"] == "considered")
    n_pre_excl = sum(1 for r in source_rows if r["status"] == "excluded_pre_parse")
    n_invalid = sum(1 for r in source_rows if r["status"] == "considered" and not r["parser_valid"])
    manifest = {
        "schema": "b1_12_candidate_pool_manifest_v1",
        "label": "EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE",
        "controlling_preregistrations": [
            {"artifact": "B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md", "commit": "2c613f4"},
            {"artifact": "B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_1.md", "commit": "6f197fd"},
            {"artifact": "B1_12_ORDERED_VARNA_COMPOSITION_PREREG_V1_2.md", "commit": "7935f48"},
        ],
        "role": "CURATOR (V1.1 §13) — NOT the G0 auditor",
        "pool_size": len(pool),
        "deterministic_selection_rule": (
            "per-category target then canonical IAST ascending (Unicode NFC code-point) within category; "
            "stable IDs assigned in global IAST-ascending order after selection"),
        "category_targets": CATEGORY_TARGET,
        "category_counts_selected": cat_counts,
        "attestation_source_policy": "primary Monier-Williams; Apte permitted secondary (V1.1 §12)",
        "parser_path": "sanskrit_stage1_parser.py",
        "parser_spec_version": P.SPEC_VERSION,
        "parser_sha256": parser_sha,
        "length_band": list(LENGTH_BAND),
        "length_distribution": length_dist,
        "counts": {"source_considered": n_considered, "pre_excluded_morphology_or_ambiguity": n_pre_excl,
                   "parser_invalid_or_out_of_band": n_invalid, "eligible": len(eligible),
                   "selected_into_pool": len(pool)},
        "pool_file": "b1_12_candidate_pool_v1.json",
        "pool_sha256": pool_sha,
        "ordered_sequences_sealed": True,
        "no_structural_metrics_computed": True,
        "no_preferred_subset_selected": True,
        "readiness": "CANDIDATE_POOL_V1_FROZEN" if len(pool) >= 30 else
                     "BLOCKED_INSUFFICIENT_ELIGIBLE_ATTESTED_WORDS",
    }
    (OUT / "b1_12_candidate_pool_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build()
    print(json.dumps({k: m[k] for k in ("pool_size", "category_counts_selected", "length_distribution",
                                        "counts", "pool_sha256", "parser_sha256", "readiness")},
                     ensure_ascii=False, indent=2))
