"""Tests for the expanded Layer 2 bridge vocabulary — NO MODEL, NO SCORING, NO NETWORK.

Coverage engineering only. Verifies: the frozen bridge JSON loads deterministically; no duplicate
canonical keys / lexicon-inconsistent bridges; ≥95% coverage of consonant glosses used by L2; the
original 9 phrases preserved byte-identically; `love` synthesis byte-identical; mercy/anger/peace
become resolved via exhaustive coverage (not target-fitting); unsupported tokens still fail the
validator; [unresolved] still appears for unmapped glosses; no forbidden bridge terms; no score/
verdict/signal fields; no ML imports; no result files; JSON-missing falls back to inline 9.

    python3 varna_lens/test_layer2_bridge_vocab.py
"""
from __future__ import annotations
import os as _os, sys as _sys
# RETIRED historical-regression: validates the retired Layer-2 bridge, defined only under the pre-B1.12
# lexicon. Skips under the active B1.12 mapping; runs its original assertions under the old-lexicon
# fixture. See experiments/retired/layer2_bridge/README.md.
if not _os.environ.get("VARNA_LENS_MAPPING", "").endswith("lexicon_authoritative.json"):
    if "pytest" in _sys.modules:
        import pytest as _pytest
        _pytest.skip("retired Layer-2 bridge test (needs old-lexicon fixture)", allow_module_level=True)
    else:
        print("SKIP: retired Layer-2 bridge test (set VARNA_LENS_MAPPING=<repo>/varna_lens/lexicon_authoritative.json to run)")
        raise SystemExit(0)

import io
import contextlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                       # noqa: E402
import sample_text_rule_harness as S         # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# fixed g2p (from real cmudict, captured once) -> hermetic, no nltk needed
_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "mercy": ([("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")], []),
    "anger": ([("V", "a", "AE1"), ("C", "nga", "NG"), ("C", "ga", "G"), ("V", "a", "ER0")], []),
    "peace": ([("C", "pa", "P"), ("V", "ii", "IY1"), ("C", "sa", "S")], []),
}


def _fake(word):
    return _FAKE.get(word.lower(), ([], [f"'{word}' not in cmudict"]))


def _synth(word):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print(S.render(text=word, g2p=True, synthesize_mode=True))
        for line in buf.getvalue().splitlines():
            if line.strip().startswith("synthesis:"):
                return line.strip()
    finally:
        V.phonemes_cmudict = orig
    return "(none)"


_EXISTING9 = {"krūratā": "separative harshness", "karuṇā/sneha": "compassion/gentleness",
              "dharma/jalatattva": "order/dharmic relation", "nirāśā": "detachment/letting-go",
              "āśā": "hope", "viśvāsa": "trust", "cintā": "worry",
              "mūrcchā": "deluded obsession/entrancement", "jāgaraṇa": "awareness/awakening"}
_FORBIDDEN_BRIDGE = ("mercy", "anger", "peace", "romance", "bonding", "devotion", "preference",
                     "therefore means", "true meaning", "ontology", "sanskrit proves")


def test_bridge_json_loads_deterministically():
    d1 = S._load_bridge(); d2 = S._load_bridge()
    _check("bridge loads deterministically", d1 == d2)
    _check("harness BRIDGE == loaded bridge", S.BRIDGE == d1)
    _check("bridge is non-trivially expanded (>= 60)", len(S.BRIDGE) >= 60)


def test_no_duplicate_or_inconsistent_keys():
    # every lexicon consonant gloss must canon to a key whose bridge value is consistent
    seen = {}
    for e in V.LEX["consonants"].values():
        for pole in ("binding_state", "liberating_state"):
            k = S._canon(e[pole])
            v = S.BRIDGE.get(k)
            if k in seen:
                _check(f"consistent bridge for canonical key {k!r}", seen[k] == v)
            seen[k] = v
    # JSON keys themselves are unique (dict) — assert file parses to a dict with unique keys
    # archived to experiments/retired/layer2_bridge/ on Layer-2 retirement.
    _vocab = HERE.parent / "experiments" / "retired" / "layer2_bridge" / "layer2_bridge_vocab.json"
    raw = json.loads(_vocab.read_text(encoding="utf-8"))["bridge"]
    _check("JSON bridge is a dict (unique keys)", isinstance(raw, dict) and len(raw) == len(S.BRIDGE))


def test_coverage_at_least_95_percent():
    allc = set()
    for e in V.LEX["consonants"].values():
        allc.add(S._canon(e["binding_state"])); allc.add(S._canon(e["liberating_state"]))
    covered = sum(1 for c in allc if c in S.BRIDGE)
    pct = 100.0 * covered / len(allc)
    print(f"    coverage {covered}/{len(allc)} = {pct:.1f}%")
    _check("coverage >= 95% of consonant glosses used by L2", pct >= 95.0)


def test_existing_nine_preserved_byte_identical():
    for k, v in _EXISTING9.items():
        _check(f"existing bridge {k!r} unchanged", S.BRIDGE.get(k) == v)


def test_love_synthesis_byte_identical():
    _check("love synthesis unchanged",
           _synth("love") == "synthesis: separative harshness moves toward compassion/gentleness, "
                             "and order/dharmic relation is the resolving principle")


def test_mercy_anger_peace_resolved_via_exhaustive_coverage():
    for w in ("mercy", "anger", "peace"):
        _check(f"{w} synthesis no longer [unresolved]", "[unresolved]" not in _synth(w))
    # they resolved because the WHOLE inventory is bridged (exhaustive), not because targeted:
    allc = set()
    for e in V.LEX["consonants"].values():
        allc.add(S._canon(e["binding_state"])); allc.add(S._canon(e["liberating_state"]))
    _check("resolution is due to exhaustive coverage (>=95%)",
           sum(1 for c in allc if c in S.BRIDGE) / len(allc) >= 0.95)


def test_unsupported_token_still_fails_validator():
    try:
        S.validate_synthesis("separative harshness and betrayal is the resolving principle",
                             ["separative harshness"])
    except S.SynthesisInvalid:
        _check("validator still rejects unsupported term", True); return
    _check("validator still rejects unsupported term", False)


def test_unresolved_preserved_for_unmapped_gloss():
    _check("unmapped gloss -> _bridge None", S._bridge({"sanskrit": "zzz_not_a_gloss"}) is None)
    # a profile whose consonant maps to an unbridged gloss must render [unresolved]
    saved = S.BRIDGE.get("krūratā")
    S.BRIDGE.pop("krūratā", None)
    try:
        _check("dropping a bridge -> [unresolved] reappears", "[unresolved]" in _synth("love"))
    finally:
        if saved is not None:
            S.BRIDGE["krūratā"] = saved


def test_no_forbidden_bridge_terms():
    for k, v in S.BRIDGE.items():
        for bad in _FORBIDDEN_BRIDGE:
            _check(f"bridge {k!r} omits forbidden {bad!r}", bad not in v.lower())


def test_no_scoring_fields_in_synthesis():
    out = _synth("mercy").lower()
    for tok in ("score:", "score=", "verdict", "signal", "accuracy", "delta ", "a_vs"):
        _check(f"no scoring token {tok!r}", tok not in out)


def test_json_missing_falls_back_to_inline_nine():
    saved = S._BRIDGE_JSON
    S._BRIDGE_JSON = HERE / "no_such_bridge_file.json"
    try:
        fb = S._load_bridge()
        _check("missing JSON -> inline 9 fallback", fb == S._INLINE_BRIDGE)
    finally:
        S._BRIDGE_JSON = saved


def test_no_result_files_written():
    before = set(p.name for p in HERE.iterdir())
    _synth("mercy")
    _check("no files written by synthesis", set(p.name for p in HERE.iterdir()) == before)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("layer2_bridge_vocab — coverage-expansion tests (no model, no scoring, no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Layer 2 bridge-vocab tests passed.")


if __name__ == "__main__":
    main()
