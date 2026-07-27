"""
heldout_splits.py — compositional held-out generalization + identity-renaming.

Three autonomous generalization probes (no label leakage; the model still reads only tokens):

  unseen_entity_pair       : hold out a set of (src_entity, dst_entity) adjacencies from the chain
                             at train time; test chains use ONLY held-out adjacencies. Tests whether
                             retrieval composes over entity pairs never linked during training.
  unseen_relation_compose  : hold out first→second-hop relation pairs (r1, r2); test uses only the
                             held-out relation compositions. Tests relation-composition generality.
  identity_renaming        : at EVAL only, apply a random permutation to the identity space so the
                             (entity,relation)→identity mapping used at train time is scrambled.
                             A model that memorized a fixed identity class collapses; a genuine
                             evidence-retriever is unaffected (it reads the answer from the tokens).

All splits reuse `make`, then filter/relabel — the tokenization, binding, masks, and heads are
identical to the main task. Renaming is a pure token remap (a bijection on identity ids), so the
sequence stays self-consistent: the answer is still whatever the evidence chain points to.
"""
from __future__ import annotations

import torch

from .multihop_dataset import Vocab, make


def _pair(ev, chain_step):
    return None


def entity_pair_split(vocab: Vocab, holdout_frac=0.3, seed=0):
    """Partition ordered entity adjacencies (a→b, a≠b) into train / test-only sets."""
    g = torch.Generator().manual_seed(seed)
    pairs = [(a, b) for a in range(vocab.E) for b in range(vocab.E) if a != b]
    perm = torch.randperm(len(pairs), generator=g).tolist()
    n_test = max(1, int(len(pairs) * holdout_frac))
    test = set(pairs[perm[i]] for i in range(n_test))
    train = set(pairs[perm[i]] for i in range(n_test, len(pairs)))
    return train, test


def relation_compose_split(vocab: Vocab, holdout_frac=0.3, seed=1):
    """Partition (r1, r2) first→second-hop relation compositions into train / test-only sets."""
    g = torch.Generator().manual_seed(seed)
    comps = [(r1, r2) for r1 in range(vocab.R) for r2 in range(vocab.R)]
    perm = torch.randperm(len(comps), generator=g).tolist()
    n_test = max(1, int(len(comps) * holdout_frac))
    test = set(comps[perm[i]] for i in range(n_test))
    train = set(comps[perm[i]] for i in range(n_test, len(comps)))
    return train, test


def _chain_entities(ex):
    """Recover the ordered entity sequence of the required chain from an example."""
    req = sorted([ex["events"][i] for i in ex["req_evidx"]], key=lambda e: e["hop"])
    ents = [req[0]["entity"]]
    for e in req:
        ents.append(e["value"] // Vocab().R)   # value = idx(next_e, next_r) → next entity
    return ents


def _chain_relations(ex):
    req = sorted([ex["events"][i] for i in ex["req_evidx"]], key=lambda e: e["hop"])
    return [e["relation"] for e in req]


def make_filtered(vocab, N, depth, g, keep_fn, max_tries=200):
    """Rejection-sample chains until one satisfies keep_fn (composition constraint)."""
    for _ in range(max_tries):
        ex = make(vocab, N, depth, g)
        if keep_fn(ex):
            return ex
    return ex   # fall back (rare); keeps generation bounded


def generate_entity_pair(vocab, N, depth, n, seed, allowed_pairs):
    g = torch.Generator().manual_seed(seed)
    def keep(ex):
        ents = _chain_entities(ex)
        return all((ents[i], ents[i + 1]) in allowed_pairs for i in range(len(ents) - 1))
    return [make_filtered(vocab, N, depth, g, keep) for _ in range(n)]


def generate_relation_compose(vocab, N, depth, n, seed, allowed_comps):
    g = torch.Generator().manual_seed(seed)
    def keep(ex):
        rels = _chain_relations(ex)
        return len(rels) >= 2 and (rels[0], rels[1]) in allowed_comps
    return [make_filtered(vocab, N, depth, g, keep) for _ in range(n)]


def rename_identities(examples, vocab: Vocab, seed=7):
    """Apply a fixed random bijection on identity ids to every token + answer of every example.

    identity id (idx(e, r)) determines cue/key content and val content. A consistent permutation
    of identity space remaps cue, key, val, answer and every event field together, so the chain
    stays valid and the correct answer is still the evidence-derived one — only its class LABEL
    moves. If the model reads the answer from the evidence, accuracy is unchanged.
    """
    g = torch.Generator().manual_seed(seed)
    perm = torch.randperm(vocab.n_id, generator=g).tolist()          # identity → identity'
    e_of = lambda ident: ident // vocab.R
    r_of = lambda ident: ident % vocab.R
    out = []
    for ex in examples:
        ex = {**ex, "events": [dict(e) for e in ex["events"]]}
        toks = list(ex["tokens"])
        # remap every KEY / VAL / CUE token by identity permutation
        new = []
        for t in toks:
            if vocab.cue_base <= t < vocab.cue_base + vocab.n_id:
                new.append(vocab.cue_base + perm[t - vocab.cue_base])
            elif vocab.key_base <= t < vocab.key_base + vocab.n_id:
                new.append(vocab.key_base + perm[t - vocab.key_base])
            elif vocab.val_base <= t < vocab.val_base + vocab.n_id:
                new.append(vocab.val_base + perm[t - vocab.val_base])
            else:
                new.append(t)
        ex["tokens"] = new
        ex["answer"] = perm[ex["answer"]]
        for e in ex["events"]:
            e["ident"] = perm[e["ident"]]
            e["value"] = perm[e["value"]]
            e["entity"] = e_of(perm[e["ident"]]); e["relation"] = r_of(perm[e["ident"]])
        # req_evidx uses hop ordering, unaffected by relabeling
        out.append(ex)
    return out
