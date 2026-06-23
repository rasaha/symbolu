"""CPU tests for the Kosha K2 depth-varied dataset + deterministic conformance scorer.
Pre-reg: docs/KOSHA_K2_QUALITY_EVAL_PREREG.md. No GPU, no embeddings, no model.
"""
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))
_CSR = _SCR / "cg_wrapper_ablation"
if str(_CSR) not in sys.path:
    sys.path.insert(0, str(_CSR))

from conscious_generation import build_k2_dataset as DS          # noqa: E402
from conscious_generation import kosha_conformance as C          # noqa: E402
from csr_match_filter import registry as R                       # noqa: E402
from csr_match_filter.kosha import KoshaLevel                    # noqa: E402

LEVELS = ("annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya")


# ---- dataset ------------------------------------------------------------------------------------
def test_dataset_size_and_power():
    rows = DS.build()
    assert len(rows) >= 100
    from collections import Counter
    by_level = Counter(r["intended_depth"] for r in rows)
    for lvl in LEVELS:
        assert by_level[lvl] >= 8, f"{lvl} underpowered: {by_level[lvl]}"


def test_dataset_domains_all_in_registry():
    vocab = set(R.DOMAIN_REGISTRY)
    used = set()
    for r in DS.build():
        used.add(r["primary_domain"]); used.update(r["secondary_domains"]); used.update(r["rejected_domains"])
    assert used <= vocab, f"OOV domains: {sorted(used - vocab)}"


def test_dataset_has_required_slices_and_labels():
    rows = DS.build()
    slices = {r["slice"] for r in rows}
    assert {"annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya",
            "mixed", "negative_control"} <= slices
    for r in rows:
        assert r["intended_depth"] in LEVELS and r["query"] and r["term"]
        assert r["primary_domain"] and "high_stakes" in r


def test_dataset_no_forbidden_fields():
    import json
    blob = json.dumps(DS.build()).lower()
    for bad in ("guna", "vritti", "bhava"):
        assert bad not in blob


# ---- conformance scorer -------------------------------------------------------------------------
def test_conformance_each_level_matches():
    assert C.score_depth_conformance("A doctor treats illness and keeps people healthy.", "annamaya") == 1.0
    assert C.score_depth_conformance("1. Book it. 2. Bring records. 3. Ask questions.", "pranamaya") == 1.0
    assert C.score_depth_conformance("I understand; it is normal to feel worried here.", "manomaya") == 1.0
    assert C.score_depth_conformance("A is broad; however B is deeper. The tradeoff is cost.",
                                     "vijnanamaya") == 1.0
    assert C.score_depth_conformance("Ultimately the underlying principle connects everything.",
                                     "anandamaya") == 1.0


def test_conformance_cross_level_is_zero():
    # a step list is NOT comparison/synthesis; a long answer is NOT surface
    assert C.score_depth_conformance("1. do this 2. do that 3. done", "vijnanamaya") == 0.0
    assert C.score_depth_conformance("word " * 120, "annamaya") == 0.0          # too long for surface
    assert C.score_depth_conformance("A doctor treats illness.", "pranamaya") == 0.0  # no steps


def test_conformance_accepts_enum_and_string():
    assert C.score_depth_conformance("1. step one 2. step two", KoshaLevel.PRANAMAYA) == 1.0
    assert C.score_depth_conformance("1. step one 2. step two", "pranamaya") == 1.0


def test_guardrail_flags():
    assert C.terse_rate_flag("too short") == 1.0
    assert C.terse_rate_flag("this answer has clearly more than the minimum number of words here ok") == 0.0
    assert C.over_framing_flag("The primary frame is medicine and the rejected domain is finance.") == 1.0
    assert C.over_framing_flag("A doctor diagnoses and treats illness.") == 0.0


def test_conformance_features_bundle():
    f = C.conformance_features("1. first 2. second 3. third steps here", "pranamaya")
    assert set(f) == {"depth_conformance", "terse", "over_framing", "word_count"}
    assert f["depth_conformance"] == 1.0 and f["over_framing"] == 0.0
