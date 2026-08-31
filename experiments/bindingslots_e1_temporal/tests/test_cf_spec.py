#!/usr/bin/env python3
"""Torch-free tests for the frozen counterfactual attribution rule."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import cf_spec as SPEC


def _m(**kw):
    base = {"byte_identical": True, "oracle_valid": True, "d1_rec": 0.0, "d2_rec": 0.0, "d3_rec": 0.0,
            "d4_fail_rate": 0.0, "abstention_component": 0.0, "entity_component": 0.0,
            "latest_component": 0.0, "within_entity_latest_d3": 1.0,
            "entity_recovered_from_wrongentity_majority": False, "latest_older_majority_in_residual": False}
    base.update(kw); return base


def test_protocol_violated_on_replay_mismatch():
    assert SPEC.conclude(_m(byte_identical=False))[0] == "T4_COUNTERFACTUAL_PROTOCOL_VIOLATED"


def test_primarily_abstention():
    c, _ = SPEC.conclude(_m(d1_rec=0.7, d2_rec=0.71, d3_rec=0.72,
                            abstention_component=0.7, entity_component=0.02, latest_component=0.28))
    assert c == "T4_SHORTFALL_PRIMARILY_ABSTENTION", c


def test_primarily_latest_ranking():
    c, _ = SPEC.conclude(_m(d1_rec=0.30, d3_rec=0.65, abstention_component=0.30, entity_component=0.35,
                            latest_component=0.35, latest_older_majority_in_residual=True))
    assert c == "T4_SHORTFALL_PRIMARILY_LATEST_RANKING", c


def test_mixed_matches_observed_shape():
    # observed: abstention .463, entity .218, latest .320; d1_rec .463, d3_rec .680
    c, sec = SPEC.conclude(_m(d1_rec=0.463, d2_rec=0.014, d3_rec=0.680,
                              abstention_component=0.463, entity_component=0.218, latest_component=0.320,
                              within_entity_latest_d3=0.875))
    assert c == "T4_SHORTFALL_MIXED", c
    assert sec is False


def test_value_path_primary_only_if_majority():
    assert SPEC.conclude(_m(d4_fail_rate=0.6))[0] == "T4_SHORTFALL_VALUE_PATH"
    c, sec = SPEC.conclude(_m(d4_fail_rate=0.2, d1_rec=0.463, d3_rec=0.680,
                              abstention_component=0.463, entity_component=0.218, latest_component=0.320))
    assert c == "T4_SHORTFALL_MIXED" and sec is True


def test_committed_conclusion_is_mixed():
    import json
    p = pathlib.Path(__file__).resolve().parents[1] / "results" / "t4_counterfactual.json"
    if p.exists():
        d = json.loads(p.read_text())
        assert d["conclusion"] == "T4_SHORTFALL_MIXED"
        assert d["byte_identical_param_hashes"] is True and d["d0_reproduces_committed_T4_addressing"] is True
        assert "E1_TEMPORAL_TRANSFER_PARTIAL" in d["preserved"]
        for forbidden in ("E1_TEMPORAL_TRANSFER_VALIDATED", "E1_STRUCTURAL_TRANSFER_CONFIRMED", "E1_FOLLOW_ON_RESEARCH_ELIGIBLE"):
            assert forbidden not in json.dumps(d)


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"cf-spec tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
