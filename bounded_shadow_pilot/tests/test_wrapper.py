"""Phase 6-7 tests. The read-only orchestrator wrapper composes the frozen pipeline + native
ActionGate + derivation provenance into an extended audit record, never enforces, and is deterministic.
"""
import json
import os

from bounded_shadow_pilot import orchestrator_wrapper as ow
from bounded_shadow_pilot import case_builder

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "natural_pilot_v1")


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    gts = {g["artifact_id"]: g for g in gt["labels"]}
    return corpus["artifacts"], gts


def test_wrapper_never_enforces():
    arts, gts = _load()
    recs = ow.run_batch(arts[:12], gts)
    assert all(r.enforced is False for r in recs)


def test_wrapper_produces_replayable_record():
    arts, gts = _load()
    recs = ow.run_batch(arts[:12], gts)
    assert all(r.replay_signature for r in recs)          # frozen trace signature carried through
    assert all(r.final_shadow_disposition for r in recs)


def test_wrapper_deterministic():
    arts, gts = _load()
    a = [ow.replay_signature(r) for r in ow.run_batch(arts[:20], gts)]
    b = [ow.replay_signature(r) for r in ow.run_batch(arts[:20], gts)]
    assert a == b


def test_derivation_is_documented_and_carried():
    arts, gts = _load()
    r = ow.run_batch(arts[:1], gts)[0]
    assert r.derivation_version == case_builder.DERIVATION_VERSION
    assert r.derived_evidence_state
    assert r.derived_risk_tier in ("low", "medium", "high", "critical")


def test_derived_action_carries_native_outcome():
    # find an artifact whose text derives an action; its native outcome must be one of the six.
    arts, gts = _load()
    recs = ow.run_batch(arts, gts)
    with_action = [r for r in recs if r.action_derived]
    for r in with_action:
        assert r.native_action_outcome in (
            "ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
            "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", "GATE_ERROR")
        assert r.native_action_permits is not None
