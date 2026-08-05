#!/usr/bin/env python3
"""Torch-free tests for the frozen T4 error-classification rule."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import t4_error_spec as SPEC


def test_primarily_latest_selection():
    fc = {"RIGHT_ENTITY_WRONG_OLDER_STEP": 75, "WRONG_ENTITY": 15, "NULL_OR_ABSTAIN": 10}
    assert SPEC.conclude(fc, True, 100) == "T4_FAILURE_PRIMARILY_LATEST_SELECTION"


def test_primarily_entity_retrieval():
    fc = {"WRONG_ENTITY": 72, "RIGHT_ENTITY_WRONG_OLDER_STEP": 20, "NULL_OR_ABSTAIN": 8}
    assert SPEC.conclude(fc, True, 100) == "T4_FAILURE_PRIMARILY_ENTITY_RETRIEVAL"


def test_mixed():
    fc = {"RIGHT_ENTITY_WRONG_OLDER_STEP": 45, "WRONG_ENTITY": 40, "NULL_OR_ABSTAIN": 15}
    assert SPEC.conclude(fc, True, 100) == "T4_FAILURE_MIXED"


def test_inconclusive_abstention_dominated():
    # the actual observed shape: abstention-dominated -> no bucket -> inconclusive
    fc = {"NULL_OR_ABSTAIN": 78, "RIGHT_ENTITY_WRONG_OLDER_STEP": 17, "WRONG_ENTITY": 5}
    assert SPEC.conclude(fc, True, 100) == "T4_ERROR_ANALYSIS_INCONCLUSIVE"


def test_inconclusive_invalid_too_large():
    fc = {"RIGHT_ENTITY_WRONG_OLDER_STEP": 80, "INVALID_OR_OTHER": 20}
    assert SPEC.conclude(fc, True, 100) == "T4_ERROR_ANALYSIS_INCONCLUSIVE"


def test_protocol_violated_on_replay_mismatch():
    fc = {"RIGHT_ENTITY_WRONG_OLDER_STEP": 100}
    assert SPEC.conclude(fc, False, 100) == "T4_ERROR_ANALYSIS_PROTOCOL_VIOLATED"


def test_committed_conclusion_is_inconclusive():
    import json
    p = pathlib.Path(__file__).resolve().parents[1] / "results" / "t4_error_analysis.json"
    if p.exists():
        d = json.loads(p.read_text())
        assert d["conclusion"] == "T4_ERROR_ANALYSIS_INCONCLUSIVE"
        assert d["replay_byte_identical"] is True
        assert "KDA_VALIDATION_BLOCKED" in d["co_emitted"]
        assert d["existing_verdict_unchanged"] == "E1_TEMPORAL_TRANSFER_PARTIAL"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"t4-spec tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
