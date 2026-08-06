from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.single_hop_typed_vs_prose.config import (
    DEVELOPMENT_AUTHORIZATION_TOKEN,
    FINAL_AUTHORIZATION_TOKEN,
    SMOKE_AUTHORIZATION_TOKEN,
)
from experiments.single_hop_typed_vs_prose.dataset import SyntheticEpisodeGenerator
from experiments.single_hop_typed_vs_prose.evaluator import OutputParseError, parse_output, score_output
from experiments.single_hop_typed_vs_prose.execution import ExecutionNotAuthorized, guard_seed

TEST_ONLY_SEED = 99173


def test_output_parser_round_trip_and_strict_field_order():
    output = SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate("S2").authoritative_output
    assert parse_output(output.to_json()) == output
    malformed_order = (
        '{"tenant_id":"t01","status":"ANSWERED","selected_entity_id":null,'
        '"selected_relation_type":null,"relation_supported":null,"evidence_refs":[],'
        '"reason_code":"x"}'
    )
    with pytest.raises(OutputParseError, match="fields/order"):
        parse_output(malformed_order)


def test_evaluator_detects_cross_tenant_selection_and_unsupported_evidence():
    episode = SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate("S7")
    cross = next(item for item in episode.entities if item.tenant_id != episode.tenant_id)
    prediction = replace(
        episode.authoritative_output,
        selected_entity_id=cross.entity_id,
        evidence_refs=("not-authorized",),
    )
    score = score_output(episode, prediction)
    assert score.unauthorized_cross_tenant_inclusion
    assert score.unsupported_evidence_refs == ("not-authorized",)
    assert score.evidence_precision == 0.0


def test_reserved_seeds_fail_closed_without_exact_authorization():
    for seed in (76, 760, 761, 762, 7160, 7161, 7162, 7163, 7164):
        with pytest.raises(ExecutionNotAuthorized):
            guard_seed(seed)
        with pytest.raises(ExecutionNotAuthorized):
            guard_seed(seed, "wrong-token")
    assert guard_seed(76, SMOKE_AUTHORIZATION_TOKEN).role == "smoke"
    assert guard_seed(760, DEVELOPMENT_AUTHORIZATION_TOKEN).role == "development"
    assert guard_seed(7160, FINAL_AUTHORIZATION_TOKEN).role == "final"


def test_non_benchmark_test_seed_is_not_execution_gated():
    authorization = guard_seed(TEST_ONLY_SEED)
    assert authorization.role == "non_benchmark"
    assert authorization.authorized
