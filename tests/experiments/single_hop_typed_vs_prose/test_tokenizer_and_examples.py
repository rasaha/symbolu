from __future__ import annotations

import pytest

from experiments.single_hop_typed_vs_prose.config import BOS_ID, EOS_ID, PAD_ID, VOCAB_SIZE, ModelRecipe
from experiments.single_hop_typed_vs_prose.dataset import (
    SyntheticEpisodeGenerator,
    encode_pair_arm,
    make_pair,
)
from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

TEST_ONLY_SEED = 99173


def test_tokenizer_is_fixed_reversible_and_uses_stable_special_ids():
    tokenizer = LexicalTokenizer()
    text = 'Within tenant t01, the relation_type is "belongs_to_contract".\n'
    ids = tokenizer.encode(text, add_bos=True, add_eos=True)
    assert ids[0] == BOS_ID
    assert ids[-1] == EOS_ID
    assert PAD_ID not in ids
    assert max(ids) < VOCAB_SIZE
    assert tokenizer.decode(ids) == text


def test_tokenizer_rejects_non_ascii_instead_of_normalizing():
    with pytest.raises(ValueError, match="7-bit ASCII"):
        LexicalTokenizer().encode("café")


def test_all_primary_pairs_fit_common_budget_without_truncation():
    generator = SyntheticEpisodeGenerator(TEST_ONLY_SEED)
    for episode in generator.generate_all():
        pair = make_pair(episode)
        b0 = encode_pair_arm(pair, "B0")
        b1 = encode_pair_arm(pair, "B1")
        assert b0.fact_hash == b1.fact_hash
        assert b0.prompt_tokens <= 512
        assert b1.prompt_tokens <= 512
        assert b0.output_tokens == b1.output_tokens
        assert len(b0.input_ids) == len(b0.labels)
        assert len(b1.input_ids) == len(b1.labels)


def test_loss_mask_starts_at_first_output_target():
    pair = make_pair(SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate("S1"))
    encoded = encode_pair_arm(pair, "B1")
    assert all(label == -100 for label in encoded.labels[: encoded.prompt_tokens])
    assert encoded.labels[encoded.prompt_tokens] != -100
    assert encoded.labels[-1] == EOS_ID


def test_budget_failure_is_fail_closed():
    pair = make_pair(SyntheticEpisodeGenerator(TEST_ONLY_SEED).generate("S1"))
    tiny_budget = ModelRecipe(max_input_tokens=10, max_output_tokens=384, max_seq=396)
    with pytest.raises(ValueError, match="input has"):
        encode_pair_arm(pair, "B0", recipe=tiny_budget)
