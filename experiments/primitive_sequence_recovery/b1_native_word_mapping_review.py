"""Development-only native Sanskrit word-mapping review (docs/data-only).

Parses Devanāgarī words with the frozen Stage-1 parser and resolves each atomic varṇa against the merged native
lexicon (frozen/varna_native_stage1_merged_v1.json). Displays the EXISTING binding/liberating vṛtti per unit with
its provenance + activation scope. This is a MAPPING-INSPECTION / mechanism-development step — it does NOT judge
whether any word interpretation is semantically correct, and authors NO new meaning.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. Authored vowels are DEVELOPMENT_ONLY;
no word is called 'validated'.
"""
import json
import pathlib
from collections import Counter

import sanskrit_stage1_parser as P
from b1_stage1_mapping_integration_audit import iast_to_devanagari

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
SEED = json.load(open(HERE / "frozen" / "word_list.json", encoding="utf-8"))["words"]
OUT = HERE / "b1_native_word_mapping_review"
ROW = {r["canonical_parser_unit"]: r for r in MERGED["rows"]}

SOURCE_LABEL = {"consonant": "consonant_v3_1", "vowel": "varna_lens_vowel",
                "anusvara": "varna_lens_anusvara", "visarga": "varna_lens_visarga", "candrabindu": "missing"}

# curated development subset (IAST -> Devanāgarī via the round-trip-validated helper), tagged by what it exercises
CURATED = [
    ("guru", "short vowels"), ("bala", "short a / inherent"), ("kāla", "long ā"), ("māyā", "long ā×2"),
    ("deva", "diphthong e"), ("vairāgya", "diphthong ai + conjunct"), ("moha", "vowel o"), ("gaurava", "diphthong au"),
    ("saṃskāra", "anusvāra"), ("ahaṃkāra", "anusvāra medial"), ("duḥkha", "visarga + aspirate"),
    ("namaḥ", "final visarga"), ("dharma", "aspirate + repha"), ("buddhi", "d+dh conjunct"),
    ("koṭi", "retroflex ṭa vs dental"), ("gaṇa", "retroflex ṇa"), ("śiva", "palatal ś"), ("viṣṇu", "retroflex ṣa+ṇa"),
    ("kṣamā", "kṣa conjunct"), ("jñāna", "jña conjunct + long ā"), ("sattva", "gemination t+t"),
    ("anna", "gemination n+n"), ("ṛṣi", "vocalic ṛ (MISSING)"), ("kṛṣṇa", "vocalic ṛ + conjunct"),
    ("mṛtyu", "vocalic ṛ + conjunct"), ("mokṣa", "vowel o + kṣa"), ("ātman", "long ā + final n"),
    ("ānanda", "long ā onset"), ("satya", "conjunct ty"), ("ahiṃsā", "anusvāra + long ā"),
    ("karma", "repha"), ("yoga", "vowel o"), ("bhakti", "aspirate bh + conjunct"), ("vidyā", "conjunct dy"),
    ("avidyā", "privative a + conjunct"),
]
FIXTURES = ["कमल", "शान्ति", "शक्ति", "दुःख", "संस्कृत", "बुद्धि", "क्षमा", "अग्नि"]


def resolve_unit(u):
    r = ROW.get(u["unit"])
    if r is None:
        return {"unit": u["unit"], "devanagari": u["devanagari"], "type": u["type"], "source": "unresolved",
                "binding": None, "liberating": None, "provenance": "UNRESOLVED_IDENTITY", "scope": "UNRESOLVED"}
    src = SOURCE_LABEL.get(r["category"], r["category"])
    if r["activation_scope"] == "MISSING":
        src = "missing"
    return {"unit": u["unit"], "devanagari": u["devanagari"], "type": u["type"], "source": src,
            "binding": r["binding_vritti"], "liberating": r["liberating_vritti"],
            "provenance": r["binding_pole_provenance"] if r["binding_pole_provenance"] == r["liberating_pole_provenance"]
            else f"binding={r['binding_pole_provenance']};liberating={r['liberating_pole_provenance']}",
            "scope": r["activation_scope"]}


def review_word(devanagari, iast_intended=None, exercises=None):
    rec = P.parse(devanagari)
    units = [u for u in rec["atomic_varnas"]
             if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")]
    seq = [resolve_unit(u) for u in units]
    n = len(seq)
    missing = [s["unit"] for s in seq if s["scope"] in ("MISSING", "UNRESOLVED", "OUT_OF_SCOPE")]
    n_struct = sum(1 for s in seq if s["scope"] in ("CONFIRMATORY_BACKBONE", "DEVELOPMENT_ONLY"))
    n_confirm = sum(1 for s in seq if s["scope"] == "CONFIRMATORY_BACKBONE")
    has_missing = any(s["scope"] in ("MISSING", "UNRESOLVED", "OUT_OF_SCOPE") for s in seq)
    has_contra = any(s["scope"] == "CONTRADICTORY" for s in seq)
    all_confirm = n > 0 and n_confirm == n
    all_resolved = n > 0 and n_struct == n
    if has_missing:
        status = "CONTAINS_MISSING_UNIT"
    elif has_contra:
        status = "CONTAINS_CONTRADICTORY_UNIT"
    elif all_confirm:
        status = "CONFIRMATORY_BACKBONE_ONLY"
    elif all_resolved:
        status = "FULLY_RESOLVED_DEVELOPMENT_GRADE"
    else:
        status = "PARTIALLY_RESOLVED"
    return {
        "word_devanagari": devanagari, "transliteration_iast": rec["transliteration_iast"],
        "iast_intended": iast_intended, "exercises": exercises,
        "round_trip_ok": (iast_intended is None) or (rec["transliteration_iast"] == iast_intended),
        "aksharas": [a["devanagari"] for a in rec["aksharas"]],
        "atomic_varnas": [s["unit"] for s in seq],
        "mapping_rows": seq,
        "binding_sequence": [s["binding"] for s in seq],
        "liberating_sequence": [s["liberating"] for s in seq],
        "provenance_sequence": [s["provenance"] for s in seq],
        "activation_scope_sequence": [s["scope"] for s in seq],
        "missing_units": missing,
        "structural_coverage": round(n_struct / n, 3) if n else 0,
        "confirmatory_eligible_coverage": round(n_confirm / n, 3) if n else 0,
        "word_status": status,
    }


def build():
    OUT.mkdir(exist_ok=True)
    words = []
    for deva in FIXTURES:
        words.append({"group": "parser_fixture", **review_word(deva)})
    for iast, ex in CURATED:
        words.append({"group": "curated_dev", **review_word(iast_to_devanagari(iast), iast, ex)})
    for e in SEED:
        w = review_word(iast_to_devanagari(e["spelling"]), e["spelling"], "seed_list")
        w["group"] = "seed_list"; w["word_id"] = e["word_id"]
        words.append(w)

    status_counts = Counter(w["word_status"] for w in words)
    rt = [w for w in words if w["round_trip_ok"]]
    summary = {
        "artifact_type": "native_word_mapping_review",
        "grade": "DEVELOPMENT_ONLY (authored vowels; NOT confirmatory; NOT semantically validated)",
        "merged_lexicon": "frozen/varna_native_stage1_merged_v1.json",
        "n_words": len(words), "n_round_tripped": len(rt),
        "word_status_counts": dict(status_counts),
        "mean_structural_coverage": round(sum(w["structural_coverage"] for w in rt) / len(rt), 3) if rt else 0,
        "mean_confirmatory_eligible_coverage": round(sum(w["confirmatory_eligible_coverage"] for w in rt) / len(rt), 3) if rt else 0,
        "words_with_missing_unit": sum(1 for w in words if w["word_status"] == "CONTAINS_MISSING_UNIT"),
        "note": "structural coverage includes authored-provisional vowels; it is NOT a semantic-validation claim.",
    }
    (OUT / "word_mappings.json").write_text(json.dumps({"words": words}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"words": words, "summary": summary}


if __name__ == "__main__":
    r = build()
    s = r["summary"]
    print("words:", s["n_words"], "round-tripped:", s["n_round_tripped"])
    print("status:", s["word_status_counts"])
    print(f"mean structural cov: {s['mean_structural_coverage']}  mean confirmatory-eligible cov: {s['mean_confirmatory_eligible_coverage']}")
