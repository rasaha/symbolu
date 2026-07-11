"""Validation for the qualitative mechanism review. NO network, NO model.

Confirms: selected list fixed before classification; every word under every view; no mapping row changed; no
polarity mixing within a fixed view; provenance preserved; deterministic; verdict from the allowed set.
"""
import hashlib
import json
import pathlib

import b1_native_mechanism_qualitative_review as Q

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "b1_native_mechanism_qualitative_review"
SRC = {w["transliteration_iast"]: w for w in
       json.load(open(HERE / "b1_native_word_mapping_review" / "word_mappings.json", encoding="utf-8"))["words"]}
ALLOWED_VERDICT = {"ONE_COMPOSITION_CANDIDATE_READY_FOR_PREREGISTRATION",
                   "MULTIPLE_CANDIDATES_REQUIRE_DEVELOPMENT_COMPARISON",
                   "MAPPINGS_TOO_GENERIC_FOR_COMPOSITION_PREREGISTRATION",
                   "MAPPINGS_CONTRADICT_NATIVE_WORDS", "REVIEW_BLOCKED_BY_MISSING_UNITS"}


def test_selection_fixed_before_classification():
    # the manifest hash is a pure function of the selected words (no fit categories leak into it)
    Q.build()
    man = json.load(open(OUT / "selected_word_manifest.json", encoding="utf-8"))
    assert man["manifest_hash"] == hashlib.sha256(json.dumps(sorted(Q.SELECTED), ensure_ascii=False).encode()).hexdigest()
    blob = json.dumps(man, ensure_ascii=False)
    for fit in Q.FIT:
        assert fit not in blob                       # no classification appears in the fixed manifest


def test_every_word_under_every_view():
    pw = json.load(open(OUT / "per_word_classification.json", encoding="utf-8"))["words"]
    assert len(pw) == len(Q.SELECTED)
    for w in pw:
        assert set(w["view_fit"]) == set(Q.VIEWS)
        for v in Q.VIEWS:
            assert w["view_fit"][v] in Q.FIT


def test_no_mapping_row_changed():
    pw = json.load(open(OUT / "per_word_classification.json", encoding="utf-8"))["words"]
    for w in pw:
        src = SRC[w["iast"]]
        assert w["binding_sequence"] == [r["binding"] for r in src["mapping_rows"]]
        assert w["liberating_sequence"] == [r["liberating"] for r in src["mapping_rows"]]
        assert w["atomic_varnas"] == src["atomic_varnas"]


def test_no_polarity_mixing_within_view():
    pw = json.load(open(OUT / "per_word_classification.json", encoding="utf-8"))["words"]
    for w in pw:
        src = SRC[w["iast"]]
        # binding views draw ONLY from binding; liberating views ONLY from liberating
        assert w["binding_sequence"] == [r["binding"] for r in src["mapping_rows"]]
        assert w["consonant_only_binding"] == [r["binding"] for r in src["mapping_rows"] if r["type"] == "consonant"]
        assert w["consonant_only_liberating"] == [r["liberating"] for r in src["mapping_rows"] if r["type"] == "consonant"]


def test_provenance_preserved():
    pw = json.load(open(OUT / "per_word_classification.json", encoding="utf-8"))["words"]
    for w in pw:
        assert w["provenance_sequence"] == SRC[w["iast"]]["provenance_sequence"]
        assert w["activation_scope_sequence"] == SRC[w["iast"]]["activation_scope_sequence"]


def test_verdict_and_no_confirmatory_claim():
    r = Q.build()
    assert r["development_verdict"] in ALLOWED_VERDICT
    assert r["grade"] == "DEVELOPMENT_ONLY"
    blob = (OUT / "review_summary.json").read_text()
    for banned in ("SIGNAL_PRESENT", "SEMANTICALLY_VALIDATED", "CONFIRMATORY_PASS", "GENUTILITY"):
        assert banned not in blob
    assert "NO_SIGNAL" in blob                        # prior null preserved


def test_missing_r_words_uninterpretable_all_views():
    pw = json.load(open(OUT / "per_word_classification.json", encoding="utf-8"))["words"]
    for w in pw:
        if "ṛ" in w["atomic_varnas"]:
            assert all(w["view_fit"][v] == "UNINTERPRETABLE_DUE_TO_MISSING_UNIT" for v in Q.VIEWS)


def test_deterministic():
    Q.build(); h1 = hashlib.sha256((OUT / "per_word_classification.json").read_bytes()).hexdigest()
    Q.build(); h2 = hashlib.sha256((OUT / "per_word_classification.json").read_bytes()).hexdigest()
    assert h1 == h2
