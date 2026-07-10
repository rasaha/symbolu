"""Tests for the /θ,ð/ fidelity fix CANDIDATE. Deterministic; no model, no network. Candidate NOT applied —
these tests also assert the frozen v1 bridge, bridge v2, and v3 table are UNCHANGED. B1.4b' = NULL_RETURN_BOTTOM."""
import json

import varna_bridge_thfix as TF
import varna_bridge_v2 as B2
import stage_a_prime_coverage as A

MP = B2.base_mapping()
ASPIRATES = {"tha", "kha", "pha", "ttha", "ddha", "jha", "gha", "cha", "bha", "dha"}


def _phon(w):
    phs = []
    for tok in w.split("-"):
        phs += A.normalize(tok, "A_PRIME_EN")["phonemes"]
    return phs


def _v1(w):
    return [MP[p] for p in _phon(w) if p in MP]


# ---- /θ/ voiceless: thin, thought, path, faith ---------------------------------------
def test_theta_moves_off_tha_to_ta():
    assert TF.word_to_varnas("thin") == ["ta", "na"]
    assert TF.word_to_varnas("thought") == ["ta", "ga", "ta"]
    assert TF.word_to_varnas("path") == ["pa", "ta"]
    assert TF.word_to_varnas("faith") == ["ta"]


# ---- /ð/ voiced: this, that, other, mother -------------------------------------------
def test_eth_moves_off_tha_to_ta():
    assert TF.word_to_varnas("this") == ["ta", "sa"]
    assert TF.word_to_varnas("that") == ["ta", "ta"]
    assert TF.word_to_varnas("other") == ["ta", "ra"]
    assert TF.word_to_varnas("mother") == ["ma", "ta", "ra"]
    assert TF.word_to_varnas("the") == ["ta"]


def test_no_aspirate_introduced_and_tha_removed():
    for w in ["thin", "thought", "path", "faith", "this", "that", "other", "mother", "the", "three"]:
        out = TF.word_to_varnas(w)
        assert "tha" not in out                                   # mis-map removed
        assert not (set(out) & ASPIRATES)                          # no accidental aspiration anywhere
    # the override targets are the UNaspirated dental stops only
    assert TF.THFIX_OVERRIDE == {"th": "ta", "dh": "da"}


# ---- composes with the retroflex rule; th+r is NOT retroflex --------------------------
def test_composes_with_retroflex_v2():
    assert TF.word_to_varnas("drum") == ["dda", "ra", "ma"]        # retroflex still fires
    assert TF.word_to_varnas("train") == ["tta", "ra", "na"]
    assert TF.word_to_varnas("three") == ["ta", "ra"]             # θr -> ta,ra (NOT retroflex tta)


# ---- IMPACT: zero change to any frozen item ------------------------------------------
def test_zero_impact_on_frozen_items():
    for path, key in [("frozen/b1_9_pole_did_items.json", "items"),
                      ("frozen/b1_9_targets.json", "targets"),
                      ("frozen/b1_9_pole_sanity_items.json", "items")]:
        for it in json.load(open(path))[key]:
            w = it["target_text"]
            # th-fix WITHOUT retroflex == v1 for every frozen item (none contain 'th' or t/d+r)
            assert TF.word_to_varnas(w, retroflex=False) == _v1(w), w


# ---- regression: nothing is applied --------------------------------------------------
def test_v1_bridge_unchanged():
    m = json.load(open("frozen/b1_6_phoneme_to_varna_bridge_manifest.json"))["bridge_table"]["mapping"]
    assert m["th"] == "tha" and m["dh"] == "dha"                   # frozen v1 STILL buggy (not applied)


def test_bridge_v2_unchanged_by_thfix():
    # bridge v2 (retroflex) is a separate module; it still maps a bare 'th' word to tha (it does NOT do the fix)
    assert B2.word_to_varnas("drum") == ["dda", "ra", "ma"]
    assert B2.word_to_varnas("three") == ["tha", "ra"]            # v2 leaves 'th' as tha; the fix lives in TF only


def test_v3_table_unchanged():
    tha = json.load(open("frozen/varna_polarity_table_v3_classical_DRAFT.json"))["varnas"]["tha"]
    assert "Viṣāda" in tha["sanskrit_label"]                       # v3 polarity table untouched by the phoneme fix
    assert tha["worldly_binding_distortion"].startswith("viśāda")
