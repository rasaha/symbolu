"""Superseding native-merged Stage-1 integration audit (docs/data-only).

Supersedes b1_stage1_mapping_integration_audit.py (which remains historically correct RELATIVE TO its v3.1-only
source). This audit resolves the parser against the operator-ruled MERGED lexicon
(frozen/varna_native_stage1_merged_v1.json): consonants from v3.1, vowels/anusvāra/visarga from the varṇa-lens.

Reports TWO distinct coverage concepts:
  - structurally_resolvable_coverage: any mapping present (INCLUDES authored-provisional vowels)
  - confirmatory_eligible_coverage: EXCLUDES DEVELOPMENT_ONLY / authored-provisional mappings
98.8% structural coverage does NOT imply semantic validation. Structure, not validated meaning.
"""
import json
import pathlib
from collections import Counter

import sanskrit_stage1_parser as P
from b1_stage1_mapping_integration_audit import iast_to_devanagari  # reuse the validated IAST->Devanāgarī helper

HERE = pathlib.Path(__file__).resolve().parent
MERGED = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
SEED = json.load(open(HERE / "frozen" / "word_list.json", encoding="utf-8"))["words"]
OUT = HERE / "stage1_native_merged_audit"
ROW = {r["canonical_parser_unit"]: r for r in MERGED["rows"]}


def resolve(unit_type, unit):
    r = ROW.get(unit)
    if r is None:
        return {"status": "UNRESOLVED_IDENTITY", "scope": None, "source": None}
    if r["activation_scope"] == "CONFIRMATORY_BACKBONE":
        return {"status": "EXACT_CONFIRMATORY", "scope": r["activation_scope"], "source": r["source_artifact"]}
    if r["activation_scope"] == "DEVELOPMENT_ONLY":
        return {"status": "EXISTS_DEVELOPMENT_ONLY", "scope": r["activation_scope"], "source": r["source_artifact"]}
    if r["activation_scope"] == "MISSING":
        return {"status": "MISSING_TABLE_ENTRY", "scope": "MISSING", "source": None}
    return {"status": "OUT_OF_SCOPE", "scope": "OUT_OF_SCOPE", "source": None}


def build():
    OUT.mkdir(exist_ok=True)
    # ---- unit-level coverage ----
    cats = Counter(r["category"] for r in MERGED["rows"])
    unit_level = {
        "total_rows": len(MERGED["rows"]),
        "consonants_from_v31": sum(1 for r in MERGED["rows"] if r["category"] == "consonant" and r["source_key"]),
        "consonant_out_of_scope": sum(1 for r in MERGED["rows"] if r["category"] == "consonant" and not r["source_key"]),
        "vowels_existing": sum(1 for r in MERGED["rows"] if r["category"] == "vowel" and r["source_key"]),
        "vowels_missing": sum(1 for r in MERGED["rows"] if r["category"] == "vowel" and not r["source_key"]),
        "anusvara_existing": sum(1 for r in MERGED["rows"] if r["category"] == "anusvara" and r["source_key"]),
        "visarga_existing": sum(1 for r in MERGED["rows"] if r["category"] == "visarga" and r["source_key"]),
        "candrabindu": "MISSING",
        "remaining_missing_units": [r["canonical_parser_unit"] for r in MERGED["rows"]
                                    if r["activation_scope"] == "MISSING"],
        "category_counts": dict(cats),
    }

    # ---- token + word coverage over the seed corpus ----
    tok_struct, tok_confirm, tok_total = 0, 0, 0
    tok_status = Counter()
    word_rows = []
    for e in SEED:
        deva = iast_to_devanagari(e["spelling"])
        rec = P.parse(deva)
        if rec["transliteration_iast"] != e["spelling"]:
            word_rows.append({"iast": e["spelling"], "round_trip_ok": False})
            continue
        units = [u for u in rec["atomic_varnas"]
                 if u["type"] in ("consonant", "vowel", "anusvara", "visarga", "nasalization")]
        n = len(units)
        struct_ok = confirm_ok = True
        for u in units:
            res = resolve(u["type"], u["unit"])
            tok_status[res["status"]] += 1
            tok_total += 1
            structurally = res["status"] in ("EXACT_CONFIRMATORY", "EXISTS_DEVELOPMENT_ONLY")
            confirm = res["status"] == "EXACT_CONFIRMATORY"
            tok_struct += structurally
            tok_confirm += confirm
            struct_ok = struct_ok and structurally
            confirm_ok = confirm_ok and confirm
        word_rows.append({"iast": e["spelling"], "round_trip_ok": True, "n_units": n,
                          "structurally_fully_mappable": struct_ok, "confirmatory_fully_mappable": confirm_ok})

    rt = [w for w in word_rows if w.get("round_trip_ok")]
    coverage = {
        "structurally_resolvable_coverage": {
            "note": "INCLUDES authored-provisional vowel/marker mappings; NOT a semantic-validation claim.",
            "token_pct": round(100 * tok_struct / tok_total, 1) if tok_total else 0,
            "word_full_pct": round(100 * sum(w["structurally_fully_mappable"] for w in rt) / len(rt), 1) if rt else 0,
        },
        "confirmatory_eligible_coverage": {
            "note": "EXCLUDES DEVELOPMENT_ONLY / authored-provisional (vowels, anusvāra, visarga). Consonant backbone only.",
            "token_pct": round(100 * tok_confirm / tok_total, 1) if tok_total else 0,
            "word_full_pct": round(100 * sum(w["confirmatory_fully_mappable"] for w in rt) / len(rt), 1) if rt else 0,
        },
        "total_phonological_tokens": tok_total,
        "token_status_breakdown": dict(tok_status),
        "n_seed_words": len(word_rows),
    }

    supersedes = {
        "supersedes": "b1_stage1_mapping_integration_audit.py (preserved as historically correct vs its v3.1-only source)",
        "resolves_against": "frozen/varna_native_stage1_merged_v1.json",
        "corrections_vs_prior": {
            "common_vowels": "NOW EXISTING (a ā i ī u ū e ai o au) — previously MISSING because the prior audit read v3.1 only",
            "anusvara_visarga": "NOW EXISTING (am / ah)",
            "still_missing": ["ṛ", "ṝ", "l̥", "l̥̄", "candrabindu"],
            "consonant_identity": "from v3.1 (unchanged); no wholesale authority to the stale lens consonant portion",
        },
        "prior_no_signal_linkage": ("vowel/marker mappings carry NOT_EMPIRICALLY_VALIDATED; the varṇa-lens semantic "
                                    "content returned NO_SIGNAL (twice) — referenced, not treated as deletion."),
    }
    report = {"artifact_type": "stage1_native_merged_integration_audit", "supersession": supersedes,
              "unit_level_coverage": unit_level, "coverage": coverage,
              "integration_verdict": "NATIVE_STAGE1_MERGED_LEXICON_CREATED",
              "readiness_verdict": "READY_FOR_NATIVE_WORD_MAPPING_REVIEW_WITH_PROVENANCE_LIMITS"}
    (OUT / "native_merged_coverage.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "native_merged_word_resolution.json").write_text(json.dumps({"words": word_rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    r = build()
    ul, cov = r["unit_level_coverage"], r["coverage"]
    print("integration verdict:", r["integration_verdict"])
    print("readiness verdict  :", r["readiness_verdict"])
    print(f"unit-level: consonants={ul['consonants_from_v31']} vowels_existing={ul['vowels_existing']} "
          f"anusvara={ul['anusvara_existing']} visarga={ul['visarga_existing']} missing={ul['remaining_missing_units']}")
    print(f"structural coverage : token {cov['structurally_resolvable_coverage']['token_pct']}%  "
          f"word-full {cov['structurally_resolvable_coverage']['word_full_pct']}%")
    print(f"confirmatory coverage: token {cov['confirmatory_eligible_coverage']['token_pct']}%  "
          f"word-full {cov['confirmatory_eligible_coverage']['word_full_pct']}%")
