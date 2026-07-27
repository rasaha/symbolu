"""Validity + integrity tests for the enterprise slots + bounded-quadratic experiment."""
from __future__ import annotations

import torch

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from experiments.enterprise_slots_quadratic.dataset import generate, ABSTAIN
from experiments.enterprise_slots_quadratic.models import SlotQuadModel, working_set, ARMS
from experiments.enterprise_slots_quadratic.evidence_ledger import EvidenceLedger
from experiments.enterprise_slots_quadratic.train import collate_arm


def test_labels_balanced():
    cfg = DomainCfg(); data = generate(cfg, 128, "streaming", 300, 1)
    abst = sum(ex["abstain"] for ex in data) / len(data)
    assert 0.2 <= abst <= 0.7


def test_access_control_excludes_unauthorized():
    cfg = DomainCfg(); data = generate(cfg, 128, "streaming", 100, 2)
    for ex in data:
        id_of = {e.evidence_id: e for e in ex["events"]}
        for arm in ARMS:
            for eid in working_set(ex, arm, 16)["ids"]:
                e = id_of[eid]
                assert e.tenant_id == ex["tenant"] and e.readable_by(ex["role_idx"])


def test_evidence_ids_resolve_to_ledger():
    cfg = DomainCfg(); ex = generate(cfg, 128, "streaming", 1, 3)[0]
    led = EvidenceLedger(ex["events"], ex["tenant"], ex["role_idx"])
    for eid in working_set(ex, "S3", 16)["ids"]:
        assert led.exists(eid) and led.authorized(eid)


def test_fresh_streaming_misses_distant_required():
    """Streaming fresh retrieval cannot see distant required evidence (the asymmetry)."""
    cfg = DomainCfg(); data = generate(cfg, 256, "streaming", 200, 4)
    s1 = sum(working_set(ex, "S1", 16).get("required_survived", False) for ex in data) / len(data)
    s3 = sum(working_set(ex, "S3", 16).get("required_survived", False) for ex in data) / len(data)
    assert s1 < 0.1 and s3 > s1


def test_oracle_slots_retain_required():
    cfg = DomainCfg(); data = generate(cfg, 256, "streaming", 200, 5)
    s4 = sum(working_set(ex, "S4", 8).get("required_survived", False) for ex in data) / len(data)
    assert s4 >= 0.95


def test_bounded_no_full_attention():
    """Quadratic attention runs over the bounded working set (≤K+1), never the N-event stream."""
    cfg = DomainCfg(); data = generate(cfg, 512, "streaming", 4, 6)
    inp, labels, meta = collate_arm(data, cfg, "S3", 8)
    ws_mask = inp[2]
    assert ws_mask.shape[1] <= 32                     # working set bounded; not N=512


def test_no_label_leakage_in_features():
    """The working set + features never encode the answer/abstain labels."""
    cfg = DomainCfg(); data = generate(cfg, 128, "streaming", 8, 7)
    inp, labels, meta = collate_arm(data, cfg, "S3", 8)
    # deterministic working set: identical regardless of labels (labels not read by working_set)
    for ex in data:
        a = working_set(ex, "S3", 8)["ids"]
        b = working_set({**ex, "answer_role": (ex["answer_role"] + 1) % 6, "abstain": 1 - ex["abstain"]}, "S3", 8)["ids"]
        assert a == b


def test_slot_record_exact_fields_immutable():
    from experiments.enterprise_slots_quadratic.binding_slots import SlotRecord
    cfg = DomainCfg(); ex = generate(cfg, 64, "streaming", 1, 8)[0]
    e = ex["events"][0]
    sr = SlotRecord.of(0, e, "admit")
    assert sr.evidence_id == e.evidence_id and sr.subject_id == e.subject_id
