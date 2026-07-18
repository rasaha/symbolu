"""Validator for the B1.1 experimental contrastive lexicon JSON draft (binding/liberating schema v2).

Read-only. NO model, NO generation, NO scoring, NO bridge pool. Asserts structure/contrastivity of
b1_1_experimental_contrastive_lexicon_draft.json. All 34 consonants are RESOLVED (no deferred set, no
human_review_required, no null counter-poles) per the theory-owner resolution.

    python3 experiments/primitive_sequence_recovery/test_b1_1_experimental_lexicon_draft.py
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"

THEORY_OWNER_RESOLVED = {"Ra", "Sa", "Śa", "Ha", "Kṣa"}
EXCEPTION_PROTECTED = {"Ca", "Va"}
ALLOWED_STATUS = {"source_preserved_counter_rewritten", "exception_protected", "theory_owner_resolved"}
REQUIRED_TOP = ["lexicon_key", "varna", "transliteration", "source_attested_pole", "source_note",
                "binding_expression", "liberating_expression", "functional_operation",
                "contrast_boundary", "rewrite_status", "b1_1_use_status"]
VOWELS = {"a", "aa", "i", "ii", "u", "uu", "e", "ai", "o", "au", "am", "ah"}
TEXT_FIELDS = ("binding_expression", "liberating_expression", "functional_operation", "contrast_boundary")


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def main():
    doc = json.loads(DRAFT.read_text(encoding="utf-8"))
    _check("1. JSON parses", isinstance(doc, dict) and "entries" in doc)
    entries = doc["entries"]
    by_varna = {e["varna"]: e for e in entries}

    _check("2. contains 34 consonant entries", len(entries) == 34)
    _check("3. no vowels present",
           doc.get("vowels_out_of_scope") is True
           and not (VOWELS & {e["lexicon_key"] for e in entries}))
    _check("4. every entry has required fields",
           all(all(f in e for f in REQUIRED_TOP) for e in entries))

    # 5. binding/liberating schema: all four text fields non-empty for EVERY entry (no deferrals)
    def full(e):
        return all(bool((e.get(f) or "").strip()) for f in TEXT_FIELDS)
    _check("5. all 34 entries: binding/liberating/operation/boundary all non-empty", all(full(e) for e in entries))

    # 6. no per-entry deferral flags / null fields / deferred set (checked on entries, not a blob substring)
    _check("6. no per-entry human_review flags / null fields; deferred_count=0, resolved=34",
           all("human_review_required" not in e and "deferral_reason" not in e for e in entries)
           and all(e.get(f) is not None for e in entries for f in TEXT_FIELDS)
           and doc.get("deferred_count") == 0 and doc.get("resolved_count") == 34)

    # 7. every entry b1_1_use_status == resolved
    _check("7. all b1_1_use_status == 'resolved'",
           all(e["b1_1_use_status"] == "resolved" for e in entries))

    # 8. rewrite_status values in allowed set
    _check("8. rewrite_status all in allowed set",
           all(e["rewrite_status"] in ALLOWED_STATUS for e in entries))

    # 9. theory-owner-resolved set exactly {Ra,Sa,Śa,Ha,Kṣa}
    tor = {e["varna"] for e in entries if e["rewrite_status"] == "theory_owner_resolved"}
    _check("9. theory_owner_resolved == {Ra,Sa,Śa,Ha,Kṣa}", tor == THEORY_OWNER_RESOLVED)

    # 10. exception-protected set exactly {Ca,Va}
    exc = {e["varna"] for e in entries if e["rewrite_status"] == "exception_protected"}
    _check("10. exception_protected == {Ca,Va}", exc == EXCEPTION_PROTECTED)

    # 11. exactly 27 ordinary (source_preserved_counter_rewritten) with classical_side binding
    ordn = [e for e in entries if e["rewrite_status"] == "source_preserved_counter_rewritten"]
    _check("11. 27 ordinary, each classical_side='binding' + classical_attested",
           len(ordn) == 27
           and all(e["source_attested_pole"]["classical_side"] == "binding"
                   and e["source_attested_pole"]["source_status"] == "classical_attested" for e in ordn))

    # 12. Ra preserves BOTH classical attestations in source_note (dual, not dropped)
    ra_note = by_varna["Ra"]["source_note"].lower()
    _check("12. Ra source_note preserves prāṇaśakti AND sarvanāśa",
           "prāṇaśakti" in ra_note and "sarvanāśa" in ra_note
           and by_varna["Ra"]["source_attested_pole"]["classical_side"] == "dual")

    # 13. Na liberating_expression + functional_operation avoid generic 'viveka'/'clarity'
    na = by_varna["Na"]
    na_txt = (na["liberating_expression"] + " " + na["functional_operation"]).lower()
    _check("13. Na avoids generic 'viveka'/'clarity'", "viveka" not in na_txt and "clarity" not in na_txt)

    # 14. Na and Bha differ (liberating_expression + functional_operation)
    bha = by_varna["Bha"]
    _check("14. Na and Bha differ",
           na["liberating_expression"] != bha["liberating_expression"]
           and na["functional_operation"] != bha["functional_operation"])

    # 15-17. no exact duplicate strings across all 34
    def dups(field):
        vals = [e[field] for e in entries]
        return len(vals) != len(set(vals))
    _check("15. no duplicate liberating_expression", not dups("liberating_expression"))
    _check("16. no duplicate functional_operation", not dups("functional_operation"))
    _check("17. no duplicate contrast_boundary", not dups("contrast_boundary"))

    # 18. no bridge pool file emitted
    _check("18. no bridge pool file present",
           not (HERE / "b1_1_bridge_pool.json").exists()
           and not (HERE / "b1_1_experimental_bridge_pool.json").exists())

    print("\nAll B1.1 lexicon draft tests passed (binding/liberating schema; 34 resolved, deferred_count=0). "
          "Draft NOT frozen, NOT approved for generation.")


if __name__ == "__main__":
    main()
