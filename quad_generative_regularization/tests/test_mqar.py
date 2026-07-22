"""MQAR generation, labels, candidates, splits (spec section 22 items 1-6)."""
import torch
from qgr.mqar import MQARConfig, generate_batch, split_seed, iter_batches, IGNORE_INDEX


def test_deterministic_generation():
    """Item 1: same (cfg, seed, batch_size) -> identical batch."""
    cfg = MQARConfig(num_kv=8, num_queries=4, vocab_size=64)
    b1 = generate_batch(cfg, seed=42, batch_size=8)
    b2 = generate_batch(cfg, seed=42, batch_size=8)
    assert torch.equal(b1.tokens, b2.tokens)
    assert torch.equal(b1.targets, b2.targets)
    assert torch.equal(b1.key_pos, b2.key_pos)
    assert torch.equal(b1.cand_mask, b2.cand_mask)
    # Different seed -> different data (with overwhelming probability).
    b3 = generate_batch(cfg, seed=43, batch_size=8)
    assert not torch.equal(b1.tokens, b3.tokens)


def test_kv_and_query_labels():
    """Item 2: query targets equal the value of the matching key; query token == key token."""
    cfg = MQARConfig(num_kv=6, num_queries=3, vocab_size=48)
    b = generate_batch(cfg, seed=1, batch_size=4)
    for bi in range(4):
        for t in range(b.tokens.shape[1]):
            kp = int(b.key_pos[bi, t])
            if kp < 0:
                assert b.targets[bi, t] == IGNORE_INDEX
                continue
            # query token equals the key token it points to
            assert b.tokens[bi, t] == b.tokens[bi, kp]
            # target equals the value token = token immediately after the key
            assert b.targets[bi, t] == b.tokens[bi, kp + 1]


def test_positive_relation_is_earlier_key():
    """Item 3: correct positive is an earlier KEY position (strictly before the query)."""
    cfg = MQARConfig(num_kv=8, num_queries=4, vocab_size=64)
    b = generate_batch(cfg, seed=7, batch_size=6)
    q = b.key_pos >= 0
    idx = q.nonzero(as_tuple=False)
    for bi, t in idx.tolist():
        kp = int(b.key_pos[bi, t])
        assert kp < t                      # earlier
        assert b.cand_mask[bi, t, kp]      # the positive is in the candidate set


def test_negative_candidates_present():
    """Item 4: candidate set contains the positive plus earlier distractor keys."""
    cfg = MQARConfig(num_kv=8, num_queries=4, vocab_size=64)
    b = generate_batch(cfg, seed=3, batch_size=6)
    q = b.key_pos >= 0
    counts = b.cand_mask[q].sum(dim=1)
    assert (counts >= 2).all()             # at least positive + 1 negative
    # positive is a subset; negatives are the rest
    for row_idx, (bi, t) in enumerate(q.nonzero(as_tuple=False).tolist()):
        kp = int(b.key_pos[bi, t])
        negs = b.cand_mask[bi, t].clone()
        negs[kp] = False
        assert int(negs.sum()) >= 1


def test_all_candidates_precede_query():
    """Item 5: every candidate position is strictly before the query position."""
    cfg = MQARConfig(num_kv=8, num_queries=4, num_distractors=4, vocab_size=64)
    b = generate_batch(cfg, seed=9, batch_size=8)
    N = b.tokens.shape[1]
    q = b.key_pos >= 0
    for bi, t in q.nonzero(as_tuple=False).tolist():
        cand_positions = b.cand_mask[bi, t].nonzero(as_tuple=False).flatten().tolist()
        assert all(c < t for c in cand_positions)


def test_split_disjointness():
    """Item 6: train/val/test seed streams are disjoint (no identical sequences)."""
    cfg = MQARConfig(num_kv=8, num_queries=4, vocab_size=64)
    seeds = set()
    for split in ("train", "val", "test"):
        for i in range(50):
            seeds.add(split_seed(1234, split, i))
    # 150 distinct seeds -> disjoint streams
    assert len(seeds) == 150
    # And the generated token tensors differ across splits.
    tb = next(iter_batches(cfg, 1234, "train", 1, 8))
    vb = next(iter_batches(cfg, 1234, "val", 1, 8))
    xb = next(iter_batches(cfg, 1234, "test", 1, 8))
    assert not torch.equal(tb.tokens, vb.tokens)
    assert not torch.equal(vb.tokens, xb.tokens)
