from __future__ import annotations

import torch

from experiments.single_hop_typed_vs_prose.config import ModelRecipe
from experiments.single_hop_typed_vs_prose.dataset import (
    SyntheticEpisodeGenerator,
    collate_encoded,
    encode_pair_arm,
    make_pair,
)
from experiments.single_hop_typed_vs_prose.model import build_model
from experiments.single_hop_typed_vs_prose.trainer import deterministic_batch_order, order_digest

TEST_ONLY_SEED = 99173


def _tiny_recipe() -> ModelRecipe:
    return ModelRecipe(
        d_model=16,
        n_layers=1,
        n_heads=4,
        d_ff=32,
        max_seq=400,
        max_input_tokens=384,
        max_output_tokens=128,
    )


def test_paired_models_have_identical_count_and_initial_digest():
    first = build_model(TEST_ONLY_SEED, _tiny_recipe())
    second = build_model(TEST_ONLY_SEED, _tiny_recipe())
    assert first.parameter_count() == second.parameter_count()
    assert first.parameter_digest() == second.parameter_digest()


def test_forward_loss_and_one_backward_pass():
    recipe = _tiny_recipe()
    pair = make_pair(SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate("S1"))
    examples = [
        encode_pair_arm(pair, "B0", recipe=recipe),
        encode_pair_arm(pair, "B1", recipe=recipe),
    ]
    input_ids, labels = collate_encoded(examples)
    model = build_model(TEST_ONLY_SEED, recipe)
    logits = model(input_ids)
    assert logits.shape == (*input_ids.shape, recipe.vocab_size)
    loss = model.loss(input_ids, labels)
    assert torch.isfinite(loss)
    loss.backward()
    assert any(parameter.grad is not None for parameter in model.parameters())


def test_causal_no_future_leak():
    recipe = ModelRecipe(
        d_model=16,
        n_layers=1,
        n_heads=4,
        d_ff=32,
        max_seq=130,
        max_input_tokens=64,
        max_output_tokens=64,
    )
    model = build_model(TEST_ONLY_SEED, recipe).eval()
    generator = torch.Generator().manual_seed(TEST_ONLY_SEED)
    ids = torch.randint(0, recipe.vocab_size, (2, 16), generator=generator)
    changed = ids.clone()
    changed[:, 8] = (changed[:, 8] + 1) % recipe.vocab_size
    with torch.no_grad():
        before = model(ids)[:, :8]
        after = model(changed)[:, :8]
    assert torch.equal(before, after)


def test_batch_order_is_deterministic_and_digestable():
    first = deterministic_batch_order(7, updates=4, batch_size=3, seed=TEST_ONLY_SEED)
    second = deterministic_batch_order(7, updates=4, batch_size=3, seed=TEST_ONLY_SEED)
    assert first == second
    assert len(first) == 12
    assert len(order_digest(first)) == 64
