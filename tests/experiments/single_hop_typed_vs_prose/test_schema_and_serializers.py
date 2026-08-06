from __future__ import annotations

import json
import random

from experiments.single_hop_typed_vs_prose.ablations import build_ablation
from experiments.single_hop_typed_vs_prose.dataset import SyntheticEpisodeGenerator, make_pair

TEST_ONLY_SEED = 99173


def test_generator_does_not_mutate_global_rng_and_builds_all_splits():
    random.seed(1234)
    before = random.getstate()
    generator = SyntheticEpisodeGenerator(TEST_ONLY_SEED)
    episodes = generator.generate_all()
    after = random.getstate()
    assert before == after
    assert tuple(item.split for item in episodes) == tuple(f"S{i}" for i in range(1, 9))
    assert len({item.episode_id for item in episodes}) == 8


def test_b0_b1_are_deterministic_and_share_one_fact_hash():
    generator = SyntheticEpisodeGenerator(TEST_ONLY_SEED)
    for episode in generator.generate_all():
        first = make_pair(episode)
        second = make_pair(episode)
        assert first.b0_text == second.b0_text
        assert first.b1_text == second.b1_text
        assert first.fact_hash == second.fact_hash == episode.fact_hash()
        assert len(first.fact_hash) == 64


def test_b1_contains_no_answer_or_evaluator_fields():
    forbidden = {
        "answer",
        "correct",
        "expected",
        "gold",
        "label",
        "target_rank",
        "validity_result",
    }
    generator = SyntheticEpisodeGenerator(TEST_ONLY_SEED)
    for episode in generator.generate_all():
        payload = json.loads(make_pair(episode).b1_text)
        stack = [payload]
        keys: set[str] = set()
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                keys.update(str(key).lower() for key in item)
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
        assert not (keys & forbidden)


def test_all_ablation_transformations_construct_with_explicit_expectations():
    episodes = {
        item.split: make_pair(item)
        for item in SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate_all()
    }
    sources = {
        "A1": episodes["S1"],
        "A2": episodes["S2"],
        "A3": episodes["S2"],
        "A4": episodes["S5"],
        "A5": episodes["S2"],
        "A6": episodes["S1"],
    }
    expected_behaviors = {
        "A1": "MOVE_WITH_REPRESENTATION",
        "A2": "MOVE_WITH_REPRESENTATION",
        "A3": "ABSTAIN",
        "A4": "MOVE_WITH_REPRESENTATION",
        "A5": "REJECT_UNAUTHORIZED",
        "A6": "ROBUST_TO_LEXICAL_DECOY",
    }
    for code, source in sources.items():
        case = build_ablation(source, code)
        assert case.code == code
        assert case.perturbed.fact_hash != case.clean.fact_hash
        assert case.required_behavior == expected_behaviors[code]
        assert case.clean_output == source.episode.authoritative_output
