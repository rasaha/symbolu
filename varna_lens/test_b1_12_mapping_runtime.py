#!/usr/bin/env python3
"""Runtime guard tests for the B1.12 varṇa-mapping substitution.

Proves the mapping-source swap is faithful and that NO B1.12 evaluator/scoring machinery entered the
PSE runtime. Fast (IAST/roman words only — no cmudict). Runnable directly or via pytest.

  python varna_lens/test_b1_12_mapping_runtime.py
  pytest  varna_lens/test_b1_12_mapping_runtime.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent
_REPO = _VL.parent
sys.path.insert(0, str(_VL))

B1_12_SOURCE = _REPO / "experiments" / "primitive_sequence_recovery" / "frozen" / "varna_native_stage1_merged_v3.json"
LEXICON = _VL / "lexicon_b1_12.json"
CANONICAL = _VL / "mapping" / "varna_mapping_b1_12_canonical.json"
PROVENANCE = _VL / "mapping" / "PROVENANCE_B1_12_MAPPING.json"
OLD_LEXICON = _VL / "lexicon_authoritative.json"

# Field-name tokens that would signal evaluator/scoring material leaking into runtime.
FORBIDDEN_TOKENS = (
    "bsr", "resonance", "score", "verdict", "agreement", "evaluator", "relationship_type",
    "no_relationship", "implication", "opposition", "consequence", "judge", "per_word", "eval_",
)


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _scan_keys(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(t in str(k).lower() for t in FORBIDDEN_TOKENS):
                hits.append(f"{path}/{k}")
            hits += _scan_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += _scan_keys(v, f"{path}[{i}]")
    return hits


# ---------------------------------------------------------------------------------------------------

def test_drives_are_verbatim_from_b1_12():
    """binding/liberating drives in BOTH runtime artifacts are byte-verbatim from the frozen B1.12 file."""
    v3 = {r["canonical_parser_unit"]: r for r in _load(B1_12_SOURCE)["rows"]}
    lex = _load(LEXICON)
    can = _load(CANONICAL)
    for pse_key, unit in (("ka", "k"), ("da", "d"), ("ssa", "ṣ"), ("sha", "ś"), ("a", "a")):
        cell = "consonants" if pse_key in lex["consonants"] else "vowels"
        assert lex[cell][pse_key]["binding_state"] == v3[unit]["binding_vritti"], pse_key
        assert lex[cell][pse_key]["liberating_state"] == v3[unit]["liberating_vritti"], pse_key
        assert can["mappings"][pse_key]["binding_drive"] == v3[unit]["binding_vritti"], pse_key


def test_no_evaluator_fields_in_runtime_artifacts():
    """No BSR/relationship/verdict/agreement/score field entered any runtime artifact."""
    for art in (LEXICON, CANONICAL, PROVENANCE):
        hits = _scan_keys(_load(art))
        assert not hits, f"{Path(art).name} carries evaluator/scoring fields: {hits}"


def test_source_has_no_evaluator_fields_either():
    """The B1.12 mapping file itself is a pure mapping (evaluator results live elsewhere as research)."""
    assert not _scan_keys(_load(B1_12_SOURCE))


def test_coverage_and_explicit_abstention():
    can = _load(CANONICAL)
    cs = can["coverage_summary"]
    assert cs["consonants_mapped"] == 33 and cs["consonants_total"] == 34
    assert cs["vowels_mapped"] == 12 and cs["vowels_total"] == 12
    assert cs["unmapped_keys"] == ["ksha"]
    assert can["unmapped"]["ksha"]["disposition"] == "EXPLICIT_ABSTENTION"


def test_ssa_glyph_join_respects_sibilant_swap():
    """Devanāgarī join must map ष→ṣ (kāma) and श→ś (artha), honoring v3's ś↔ṣ correction."""
    can = _load(CANONICAL)
    assert can["mappings"]["ssa"]["mechanical_metadata"]["v3_canonical_parser_unit"] == "ṣ"
    assert can["mappings"]["sha"]["mechanical_metadata"]["v3_canonical_parser_unit"] == "ś"
    assert "kāma" in can["mappings"]["ssa"]["binding_drive"]
    assert "artha" in can["mappings"]["sha"]["binding_drive"]


def test_engine_consumes_string_poles_and_runs():
    import varna_lens as V
    assert V.active_mapping_path().name == "lexicon_b1_12.json"
    v3 = {r["canonical_parser_unit"]: r for r in _load(B1_12_SOURCE)["rows"]}
    # engine internal CONS carries the v3 binding gloss as a plain string
    assert V.CONS["ka"]["leading_vritti"] == v3["k"]["binding_vritti"]
    d, src, warn = V.analyze("kāla", model="op", roman=True)   # IAST → no cmudict
    assert d and d["essence_short"]


def test_ksha_is_explicit_not_silent():
    import varna_lens as V
    assert "ksha" not in V.CONS                                  # unmapped in B1.12
    ph, warn = V.phonemes_roman("kṣa")                          # क्ष → ksha + a
    out = V.read(ph, model="op")
    txt = V.format_reading("kṣa", "roman", out, warn)
    assert "no lexicon entry" in txt                            # surfaced explicitly, not silent


def test_adapter_is_deterministic():
    spec = importlib.util.spec_from_file_location(
        "b1_12_adapter", _VL / "tools" / "build_varna_mapping_from_b1_12.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    c1, l1, _ = mod.build()
    c2, l2, _ = mod.build()
    assert c1 == c2 and l1 == l2


def test_provenance_sha_matches_source():
    prov = _load(PROVENANCE)
    can = _load(CANONICAL)
    real = _sha(B1_12_SOURCE)
    assert prov["source"]["sha256"] == real
    assert can["source"]["sha256"] == real


def test_no_silent_fallback():
    import varna_lens as V
    # default resolves to the B1.12 lexicon
    assert V.active_mapping_path() == (_VL / "lexicon_b1_12.json")
    # a missing explicit override is a hard error, never a fallback to the old mapping
    old = os.environ.get("VARNA_LENS_MAPPING")
    os.environ["VARNA_LENS_MAPPING"] = "/nonexistent/mapping.json"
    try:
        raised = False
        try:
            V.active_mapping_path()
        except FileNotFoundError:
            raised = True
        assert raised, "missing mapping must raise, not fall back"
    finally:
        if old is None:
            del os.environ["VARNA_LENS_MAPPING"]
        else:
            os.environ["VARNA_LENS_MAPPING"] = old


def test_old_mapping_retained_only_as_comparison_artifact():
    assert OLD_LEXICON.exists()                                 # kept on disk
    import varna_lens as V
    assert V.active_mapping_path() != OLD_LEXICON               # but never the active runtime source


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = []
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            fails.append((t.__name__, e))
            print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\ntest_b1_12_mapping_runtime: {'PASS' if not fails else 'FAIL'} "
          f"({len(tests) - len(fails)}/{len(tests)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
