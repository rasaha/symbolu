#!/usr/bin/env python3
"""Contract tests for the canonical Symbolic Profile (varna_lens/symbolic_profile.py).

Covers: determinism, transliteration convergence, sibilant correctness, mapping authority, no-fallback,
no-evaluator-leakage, renderer invariance, renderer non-mutation, consumer compatibility, serialization
stability (frozen fixture).

  python varna_lens/test_symbolic_profile.py
  pytest  varna_lens/test_symbolic_profile.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent
_REPO = _VL.parent
sys.path.insert(0, str(_VL))
import varna_lens as V                       # noqa: E402
import pse_renderer as R                     # noqa: E402
import symbolic_profile as SP                # noqa: E402

B1_12_SOURCE = _REPO / "experiments" / "primitive_sequence_recovery" / "frozen" / "varna_native_stage1_merged_v3.json"
FIXTURE = _VL / "symbolic_profile_fixture.json"


def build(w, **kw):
    return SP.build_symbolic_profile(source_text=w, **kw)


# 1 — determinism
def test_determinism_byte_identical():
    for w in ("compassion", "kṣamā", "śānti", "ṣaṭ", "dama"):
        assert build(w).to_json() == build(w).to_json(), w


# 2 — transliteration convergence (parser policy: kṣ / ksh / x / kSh)
def test_transliteration_convergence_canonical_sequence():
    seqs = {form: build(form, by="spelling").decomposition["varna_keys"]
            for form in ("kṣa", "ksha", "xa", "kSha")}
    assert all(s == ["ka", "ssa", "a"] for s in seqs.values()), seqs


# 3 — sibilant correctness (ś / ṣ corrected rows; dental s distinct)
def test_sibilant_rows_and_dental_distinct():
    v3 = {r["canonical_parser_unit"]: r for r in json.loads(B1_12_SOURCE.read_text(encoding="utf-8"))["rows"]}
    ps = build("śa", by="spelling").poles["binding"][0]      # ś
    ss = build("ṣa", by="spelling").poles["binding"][0]      # ṣ
    ds = build("sa", by="spelling").poles["binding"][0]      # dental s
    assert ps["text"] == v3["ś"]["binding_vritti"] and "artha" in ps["text"]
    assert ss["text"] == v3["ṣ"]["binding_vritti"] and "kāma" in ss["text"]
    assert ds["text"] == v3["s"]["binding_vritti"]
    assert ps["text"] != ss["text"] != ds["text"] and ps["text"] != ds["text"]
    assert ps["source_mapping_id"] == "varna.sha.binding"
    assert ss["source_mapping_id"] == "varna.ssa.binding"


# 4 — mapping authority (every pole comes from the active B1.12 artifact)
def test_every_pole_from_active_b1_12_mapping():
    assert V.active_mapping_path().name == "lexicon_b1_12.json"
    for w in ("compassion", "kṣamā", "śānti", "dama", "yoga"):
        p = build(w)
        for pole_name, poles in p.poles.items():
            state = "binding_state" if pole_name == "binding" else "liberating_state"
            for cell in poles:
                assert cell["text"] == V.LEX["consonants"][cell["varna_key"]][state], (w, cell)
        # provenance pins the authoritative source hash
        assert p.provenance["mapping_sha256"] == (V.LEX["_mapping_source"]["drives_sha256"])


# 5 — no fallback (missing mapping abstains explicitly; never reads the old lexicon)
def test_abstains_when_no_mapped_consonant():
    p = build("aeiou", by="spelling")                        # vowels only → no mapped consonant
    assert p.status["complete"] is False
    assert any(a["code"] == "NO_MAPPED_VARNA" for a in p.status["abstentions"])
    assert p.poles["binding"] == [] and p.poles["liberating"] == []


# 6 — no evaluator leakage
def test_rejects_evaluator_fields():
    p = build("compassion")
    SP.assert_no_evaluator_fields(p)                         # clean profile passes
    tampered = SP.SymbolicProfile(
        schema_version=p.schema_version, profile_id=p.profile_id, input=p.input,
        decomposition=p.decomposition, poles=p.poles,
        trajectory={**p.trajectory, "resonance_score": 0.8},  # inject a forbidden field
        provenance=p.provenance, status=p.status)
    try:
        SP.assert_no_evaluator_fields(tampered)
        raised = False
    except ValueError:
        raised = True
    assert raised, "profile with a resonance_score field must be rejected"


# 7 — renderer invariance (deterministic render of the same profile)
def test_renderer_invariance():
    p = build("compassion")
    for m in R.MODES:
        a = R.render_from_profile(p, m)["layer3_reflection"]
        b = R.render_from_profile(p, m)["layer3_reflection"]
        assert a == b, m


# 8 — renderer non-mutation
def test_renderer_does_not_mutate_profile():
    p = build("temple")
    before = p.to_json()
    for m in R.MODES:
        R.render_from_profile(p, m)
    assert p.to_json() == before


# 9 — consumer compatibility (profile-routed render == legacy trajectory→fallback path, byte-identical)
def test_consumer_compatibility_render_byte_identical():
    for w in ("river", "kill", "compassion", "kṣamā", "śānti"):
        for m in R.MODES:
            traj = R.trajectory(w)
            legacy_text = R._fallback(w, traj, m)
            new_text = R.render(w, mode=m)["layer3_reflection"]
            assert new_text == legacy_text, (w, m)


# 10 — serialization stability (frozen fixture)
def test_frozen_fixture_matches():
    assert FIXTURE.exists(), "run: python varna_lens/symbolic_profile.py --emit-fixture"
    expected = FIXTURE.read_text(encoding="utf-8")
    got = build("compassion").to_json() + "\n"
    assert got == expected, "canonical profile serialization drifted from the frozen fixture"


def test_schema_versioned_and_immutable():
    p = build("dama")
    assert p.schema_version == SP.SCHEMA_VERSION
    d = p.to_dict()
    assert set(d) == {"schema_version", "profile_id", "input", "decomposition", "poles", "trajectory",
                      "provenance", "status"}
    try:
        p.profile_id = "x"; frozen_ok = False                # frozen dataclass → attribute set raises
    except Exception:
        frozen_ok = True
    assert frozen_ok


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = []
    for t in tests:
        try:
            t(); print(f"  [PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            fails.append((t.__name__, e)); print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\ntest_symbolic_profile: {'PASS' if not fails else 'FAIL'} ({len(tests) - len(fails)}/{len(tests)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
