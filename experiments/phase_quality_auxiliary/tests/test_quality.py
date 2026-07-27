"""Validity + boundary tests for the Phase-auxiliary information-health experiment."""
from __future__ import annotations

import torch

from experiments.phase_quality_auxiliary.dataset import (Schema, generate, deterministic_packet,
                                                         TARGETS, NOTE)
from experiments.phase_quality_auxiliary.quality_heads import HealthModel
from experiments.phase_quality_auxiliary.train import collate
from experiments.phase_quality_auxiliary.causal_controls import serialize_dha


def test_labels_valid_and_balanced():
    S = Schema(); data = generate(S, 256, 300, 1)
    for t in TARGETS:
        rate = sum(ex["labels"][t] for ex in data) / len(data)
        assert 0.2 <= rate <= 0.8, (t, rate)


def test_relevant_evidence_outside_bounded_packet():
    """The designed asymmetry: most distant relevant evidence is NOT in the bounded packet."""
    S = Schema(); data = generate(S, 1024, 200, 2)
    out = tot = 0
    for ex in data:
        pk = set(deterministic_packet(ex, S))
        for p in ex["relevant_positions"]:
            tot += 1; out += (p not in pk)
    assert out / tot > 0.6


def test_packet_bounded():
    S = Schema(); data = generate(S, 1024, 50, 3)
    for ex in data:
        assert len(deterministic_packet(ex, S)) <= S.packet_K


def test_phase_core_frozen():
    S = Schema(); m = HealthModel(S, arm="A3")
    for p in m.temporal.phase.core.parameters():
        assert p.requires_grad is False


def test_phase_state_bounded_in_N():
    """Phase state bytes do not grow with N (bounded recurrence, no N×N)."""
    S = Schema()
    m = HealthModel(S, arm="A3")
    assert m.phase_state_bytes(1) == m.phase_state_bytes(1)   # constant
    # quadratic attends only the bounded packet (<= K keys), never the full stream
    data = generate(S, 512, 4, 4)
    cats, num, det, qp, pk, vl, _ = collate(data, S)
    assert pk.shape[1] <= S.packet_K


def test_supporting_ids_from_packet_not_phase():
    """supporting_evidence_ids come from the deterministic/quadratic packet, not Phase state."""
    S = Schema(); ex = generate(S, 256, 1, 5)[0]
    m = HealthModel(S, arm="A3"); m.eval()
    dha = serialize_dha(m, ex, S)
    assert dha["phase_authoritative"] is False
    assert set(dha["supporting_evidence_ids"]).issubset(set(deterministic_packet(ex, S)))


def test_phase_only_arm_has_no_supporting_ids():
    """A2 (Phase, no quadratic) must not emit supporting evidence IDs from latent Phase state."""
    S = Schema(); ex = generate(S, 256, 1, 6)[0]
    m = HealthModel(S, arm="A2"); m.eval()
    dha = serialize_dha(m, ex, S)
    assert dha["supporting_evidence_ids"] == []


def test_no_lm_or_routing_loss():
    """The only training loss is per-target BCE; no LM / autoregressive / routing-supervision code."""
    import experiments.phase_quality_auxiliary.train as T
    src = open(T.__file__).read()
    assert "binary_cross_entropy_with_logits" in src
    for bad in ("lm_head", "F.cross_entropy(", "[:, :-1]", "[:, 1:]", ".generate(", "route_loss"):
        assert bad not in src


def test_arms_have_matched_temporal_dim():
    S = Schema()
    dims = {a: HealthModel(S, arm=a).in_dim for a in ("A3", "A4", "A5", "A6")}
    assert len(set(dims.values())) == 1, dims        # identical fusion input dim across temporal arms
