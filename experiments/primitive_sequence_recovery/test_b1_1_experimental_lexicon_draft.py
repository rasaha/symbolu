"""Validator for the B1.1 experimental contrastive lexicon JSON draft.

Read-only. NO model, NO generation, NO scoring, NO bridge pool. Asserts structure/contrastivity of
b1_1_experimental_contrastive_lexicon_draft.json only. Deferred entries (Ra, Śa) are exempted from the
non-deferred field/duplicate checks per the open-item resolution (5c851d3).

    python3 experiments/primitive_sequence_recovery/test_b1_1_experimental_lexicon_draft.py
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DRAFT = HERE / "b1_1_experimental_contrastive_lexicon_draft.json"

EXCEPTIONS = {"Ca", "Va", "Sa", "Ha", "Kṣa", "Ra", "Śa"}      # 7 source-attested-elsewhere consonants
DEFERRED = {"Ra", "Śa"}                                        # counter-pole deferred to human review
REQUIRED_TOP = ["lexicon_key", "varna", "transliteration", "source_attested_pole",
                "experimental_counter_pole", "rewrite_status", "b1_1_use_status"]
VOWELS = {"a", "aa", "i", "ii", "u", "uu", "e", "ai", "o", "au", "am", "ah"}


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def main():
    # 1. parses
    doc = json.loads(DRAFT.read_text(encoding="utf-8"))
    _check("1. JSON parses", isinstance(doc, dict) and "entries" in doc)
    entries = doc["entries"]
    by_varna = {e["varna"]: e for e in entries}
    nondef = [e for e in entries if e["varna"] not in DEFERRED]
    defer = [e for e in entries if e["varna"] in DEFERRED]

    # 2. 34 consonant entries
    _check("2. contains 34 consonant entries", len(entries) == 34)

    # 3. no vowels
    _check("3. no vowels present",
           doc.get("vowels_out_of_scope") is True
           and not (VOWELS & {e["lexicon_key"] for e in entries}))

    # 4. required top-level fields on every entry
    _check("4. every entry has required fields",
           all(all(f in e for f in REQUIRED_TOP) for e in entries))

    # 5. non-deferred (32) counter-pole fully specified
    def full(cp):
        return (bool((cp.get("english_rendering") or "").strip())
                and bool((cp.get("functional_operation") or "").strip())
                and bool((cp.get("contrast_boundary") or "").strip())
                and cp.get("experimental_interpretive_rendering") is True
                and cp.get("human_review_required") is False)
    _check("5. 32 non-deferred entries: counter-pole complete + experimental=True + review=False",
           len(nondef) == 32 and all(full(e["experimental_counter_pole"]) for e in nondef))

    # 6. deferred (Ra, Śa) placeholders
    def is_deferred(cp):
        return (cp.get("english_rendering") is None
                and cp.get("functional_operation") is None
                and cp.get("contrast_boundary") is None
                and cp.get("experimental_interpretive_rendering") is False
                and cp.get("human_review_required") is True
                and bool(cp.get("deferral_reason")))
    _check("6. Ra & Śa: deferred null counter-pole + review=True + deferral_reason",
           len(defer) == 2 and all(is_deferred(e["experimental_counter_pole"]) for e in defer))

    # 7. source-attested poles preserved (classical) for the 7 exceptions
    _check("7. 7 exceptions have classical_attested source pole",
           all(by_varna[v]["source_attested_pole"]["source_status"] == "classical_attested"
               and by_varna[v]["source_attested_pole"]["polarity_role"] in
               ("liberated", "neutral", "source_complex")
               for v in EXCEPTIONS))

    # 8. ordinary 27 preserve the binding/worldly source pole
    ordinary = [e for e in entries if e["varna"] not in EXCEPTIONS]
    _check("8. ordinary 27 preserve binding source pole (classical)",
           len(ordinary) == 27
           and all(e["source_attested_pole"]["polarity_role"] == "binding"
                   and e["source_attested_pole"]["source_status"] == "classical_attested"
                   for e in ordinary))

    # 9. Ra marked source_complex_human_review
    _check("9. Ra = source_complex_human_review",
           by_varna["Ra"]["rewrite_status"] == "source_complex_human_review"
           and by_varna["Ra"]["b1_1_use_status"] == "human_review_required")

    # 10. Śa marked neutral_principle_human_review
    _check("10. Śa = neutral_principle_human_review",
           by_varna["Śa"]["rewrite_status"] == "neutral_principle_human_review"
           and by_varna["Śa"]["b1_1_use_status"] == "human_review_required")

    # 11. Na counter-pole does not USE generic 'Viveka'/'clarity' (english + operation; boundary may negate them)
    na = by_varna["Na"]["experimental_counter_pole"]
    na_txt = (na["english_rendering"] + " " + na["functional_operation"]).lower()
    _check("11. Na counter-pole avoids generic 'viveka'/'clarity'",
           "viveka" not in na_txt and "clarity" not in na_txt)

    # 12. Na and Bha counter-poles differ
    bha = by_varna["Bha"]["experimental_counter_pole"]
    _check("12. Na and Bha counter-poles differ (english + operation)",
           na["english_rendering"] != bha["english_rendering"]
           and na["functional_operation"] != bha["functional_operation"])

    # 13-15. no exact duplicate strings among non-deferred entries
    def dups(field):
        vals = [e["experimental_counter_pole"][field] for e in nondef]
        return len(vals) != len(set(vals))
    _check("13. no duplicate english_rendering (non-deferred)", not dups("english_rendering"))
    _check("14. no duplicate functional_operation (non-deferred)", not dups("functional_operation"))
    _check("15. no duplicate contrast_boundary (non-deferred)", not dups("contrast_boundary"))

    # 16. no bridge pool file created by this gate
    _check("16. no bridge pool file emitted by this gate",
           not (HERE / "b1_1_bridge_pool.json").exists()
           and not (HERE / "b1_1_experimental_bridge_pool.json").exists())

    print("\nAll B1.1 experimental-lexicon draft tests passed "
          "(structure + contrastivity; deferred Ra/Śa exempted). Draft NOT frozen, NOT approved for generation.")


if __name__ == "__main__":
    main()
