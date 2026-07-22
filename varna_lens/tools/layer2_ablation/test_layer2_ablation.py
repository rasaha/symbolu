#!/usr/bin/env python3
"""Determinism / coverage / fidelity tests for the Layer-2 bridge ablation.

  python varna_lens/tools/layer2_ablation/test_layer2_ablation.py
  pytest  varna_lens/tools/layer2_ablation/test_layer2_ablation.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import ablation as AB          # noqa: E402
import run_ablation as R       # noqa: E402

WORDS = ["love", "mercy", "anger", "peace", "śānti", "ṣaṭ", "kṣamā", "compassion"]


def test_arms_deterministic_byte_identical():
    for w in WORDS:
        a = AB.render_all(w)
        b = AB.render_all(w)
        for arm in AB.ARMS:
            assert a["arms"][arm]["payload"] == b["arms"][arm]["payload"], (w, arm)


def test_legacy_bridge_is_fully_unresolved():
    for w in WORDS:
        r = AB.render_all(w)
        cov = R.coverage(r, "B_legacy")
        assert cov["coverage_pct"] == 0.0, w                 # 0/66-class collapse persists per word
        assert all(t == AB.UNRESOLVED for t in r["arms"]["B_legacy"]["pole_texts"]), w


def test_direct_full_coverage_and_fidelity():
    for w in WORDS:
        r = AB.render_all(w)
        assert R.coverage(r, "A_direct")["coverage_pct"] == 100.0, w
        f = R.fidelity(r, "A_direct")
        assert f["source_concepts_retained_pct"] == 100.0 and f["unsupported_introduced"] == 0, w
        assert f["binding_liberating_distinct"], w


def test_compression_full_fidelity_no_new_ontology_and_shorter():
    for w in WORDS:
        r = AB.render_all(w)
        assert R.coverage(r, "C_compress")["coverage_pct"] == 100.0, w
        f = R.fidelity(r, "C_compress")
        assert f["unsupported_introduced"] == 0, (w, f.get("unsupported_terms"))   # no invented labels
        assert f["source_concepts_retained_pct"] == 100.0, w
        # every content token of the compressed payload comes from the B1.12 source (subset property)
        src = set(R._content_tokens(R._pole_source_concat(r)))
        pay = set(R._content_tokens(r["arms"]["C_compress"]["payload"]))
        assert pay <= src, (w, sorted(pay - src))
        # strictly shorter than the direct payload
        assert R.tokens(r, "C_compress")["chars"] < R.tokens(r, "A_direct")["chars"], w


def test_compression_allowed_ops_only():
    # parenthetical removal + first-clause selection + max length, deterministic
    t = "kāma — worldly desire (tamasic) that grasps for wealth; the downward pull"
    c = AB.compress(t)
    assert "(" not in c and ")" not in c                     # parenthetical removed
    assert "—" not in c and ";" not in c                     # first clause only
    assert c == "kāma"                                       # head clause
    assert AB.compress(t) == AB.compress(t)                  # deterministic
    long = "a " * 100
    assert len(AB.compress(long)) <= AB.COMPRESS_MAX


def test_differentiation_split():
    payloads = {a: set() for a in AB.ARMS}
    for w in WORDS:
        r = AB.render_all(w)
        for a in AB.ARMS:
            payloads[a].add(r["arms"][a]["payload"])
    assert len(payloads["A_direct"]) == len(WORDS)           # every word distinct
    assert len(payloads["C_compress"]) == len(WORDS)         # compression preserves differentiation
    assert len(payloads["B_legacy"]) == 1                    # legacy collapses to a single payload
    assert len(payloads["D_none"]) == 1


def test_no_scoring_vocabulary_in_any_payload():
    banned = ("score", "verdict", "accuracy", "p=", "confidence", "signal", "proves", "evidence")
    for w in WORDS:
        r = AB.render_all(w)
        for a in AB.ARMS:
            low = r["arms"][a]["payload"].lower()
            assert not any(b in low for b in banned), (w, a)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = []
    for t in tests:
        try:
            t(); print(f"  [PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            fails.append((t.__name__, e)); print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\ntest_layer2_ablation: {'PASS' if not fails else 'FAIL'} ({len(tests) - len(fails)}/{len(tests)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
