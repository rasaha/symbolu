"""Tests for the structured-field prediction phase."""
from __future__ import annotations

import torch

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from experiments.enterprise_slots_quadratic.models import working_set
from experiments.enterprise_slots_quadratic.dataset import _policy_table
from experiments.enterprise_output_mapping.workflows import build_outcome
from experiments.enterprise_output_mapping.outcome_contract import decide
from experiments.enterprise_field_prediction.deterministic_fields import extract_finding
from experiments.enterprise_field_prediction.field_masks import field_mask, masked_slots
from experiments.enterprise_field_prediction.field_contracts import CONTRACTS, DETERMINISTIC_FIELDS
from experiments.enterprise_field_prediction.causal_controls import leak_audit


def _ho(n=60, seed=820000):
    cfg = DomainCfg()
    return cfg, [build_outcome(cfg, 256, "streaming", torch.Generator().manual_seed(seed + i),
                               list(range(32, 48)), list(range(8, 12))) for i in range(n)]


def test_deterministic_extraction_matches_outcome_at_K8():
    cfg, data = _ho()
    table = _policy_table(cfg); ok = 0
    for ex in data:
        id_of = {e.evidence_id: e for e in ex["events"]}
        slots = [id_of[i] for i in working_set(ex, "S3", 8, "P5")["ids"] if i in id_of]
        ok += int(max(decide(extract_finding(slots, ex["req"], table)), 0) == ex["outcome"])
    assert ok / len(data) >= 0.95           # deterministic extraction ≈ oracle at K=8


def test_field_masks_leak_free():
    cfg, data = _ho(40)
    assert leak_audit(data, cfg, 8)["label_invariant_routing"] is True


def test_masks_are_subset_of_slots():
    cfg, data = _ho(20)
    for ex in data:
        id_of = {e.evidence_id: e for e in ex["events"]}
        slots = [id_of[i] for i in working_set(ex, "S3", 8, "P5")["ids"] if i in id_of]
        for f in CONTRACTS:
            assert set(id(x) for x in masked_slots(f, slots, ex["req"])).issubset(set(id(x) for x in slots))


def test_every_field_has_unknown_state():
    for f, c in CONTRACTS.items():
        assert "UNKNOWN" in c.vocab and c.unknown_index == c.vocab.index("UNKNOWN")


def test_deterministic_fields_do_not_call_quadratic():
    import experiments.enterprise_field_prediction.deterministic_fields as D
    src = open(D.__file__).read()
    for bad in ("SlotSelfAttention", "reason(", "field_logits", "nn.Linear", "forward("):
        assert bad not in src


def test_frozen_packages_untouched():
    import experiments.enterprise_slots_quadratic.admission_policies as A
    import experiments.enterprise_output_mapping.outcome_contract as O
    assert "query_subjects" in open(A.__file__).read()
    assert "def decide" in open(O.__file__).read()
