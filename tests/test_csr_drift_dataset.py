"""CPU tests for the Phase 4 adversarial-drift dataset generator (build_drift_dataset.py).

The key safety property: a drift row is a clone of a VALIDATED v2 row with only the query text changed,
so build_trace must resolve the SAME frame (primary/secondary/rejected) for the drift query as for the
source — i.e. the adversarial phrasing changes the pressure, not the frame. Also checks schema
completeness, id uniqueness, term pinning, and false-claim augmentation. No pod / GPU / Phase 1-3
changes.
"""

import sys
from pathlib import Path

import pytest

_ABL = Path(__file__).resolve().parent.parent / "scripts" / "cg_wrapper_ablation"
if str(_ABL) not in sys.path:
    sys.path.insert(0, str(_ABL))

pytest.importorskip("numpy")

from csr_match_filter import build_drift_dataset as BD          # noqa: E402
from csr_match_filter import eval_framed_answers as EF          # noqa: E402
from csr_match_filter import eval_match_filter as EV            # noqa: E402

_V2 = Path(BD._V2)
_V2_ROWS = [__import__("json").loads(l) for l in _V2.read_text().splitlines() if l.strip()]


def test_generator_schema_and_pinning():
    drift, terms = BD.build(_V2_ROWS, max_objects=4)
    assert drift and terms
    v2_keys = set(_V2_ROWS[0].keys())
    ids = [r["id"] for r in drift]
    assert len(ids) == len(set(ids))                            # unique ids
    for r in drift:
        assert v2_keys.issubset(r.keys())                       # full schema (clone)
        assert r["dominant_terms"] and len(r["dominant_terms"]) == 1   # term pinned
        assert r["category"] in ("drift_onframe", "drift_adversarial")
        assert r["dominant_terms"][0] in r["id"]


def test_drift_rows_augment_false_claims():
    drift, _ = BD.build(_V2_ROWS, max_objects=3)
    adv = [r for r in drift if r["category"] == "drift_adversarial"]
    assert adv
    for r in adv[:5]:
        term = r["dominant_terms"][0]
        assert any(term in fc and "is" in fc for fc in r["false_claims"])


def test_drift_query_does_not_change_the_frame():
    """Empirical guarantee: same object, on-frame vs drift query -> identical resolved frame."""
    kb = EV.load_kb(str(EV._KB))
    adapter, provider, _ = EF.build_frame_adapter("hashing", kb)   # CPU backend
    drift, terms = BD.build(_V2_ROWS, max_objects=6)
    by_term = {}
    for r in drift:
        by_term.setdefault(r["dominant_terms"][0], {}).setdefault(r["category"], r)
    checked = 0
    nonempty = 0
    for term, cats in by_term.items():
        if "drift_onframe" not in cats or "drift_adversarial" not in cats:
            continue
        t_on, _ = EF.frame_for(cats["drift_onframe"], adapter, provider)
        t_dr, _ = EF.frame_for(cats["drift_adversarial"], adapter, provider)
        # THE safety property: the adversarial query changes pressure, not the frame
        assert t_on.primary_domains == t_dr.primary_domains
        assert t_on.secondary_domains == t_dr.secondary_domains
        assert t_on.rejected_domains == t_dr.rejected_domains
        nonempty += 1 if t_on.primary_domains else 0           # non-empty is backend-dependent (CPU)
        checked += 1
    assert checked >= 4
    assert nonempty >= 2     # hashing CPU backend frames most objects; real backend (pod) frames all


def test_committed_drift_files_exist_and_parse():
    import json
    drift_p = _V2.parent / "framed_answer_eval_v3_drift.jsonl"
    comb_p = _V2.parent / "framed_answer_eval_v3_combined.jsonl"
    assert drift_p.exists() and comb_p.exists()
    drift = [json.loads(l) for l in drift_p.read_text().splitlines() if l.strip()]
    comb = [json.loads(l) for l in comb_p.read_text().splitlines() if l.strip()]
    assert len(comb) == len(_V2_ROWS) + len(drift)             # combined = v2 + drift
    assert len({r["id"] for r in comb}) == len(comb)           # all ids unique
