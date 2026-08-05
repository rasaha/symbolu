#!/usr/bin/env python3
"""INDEPENDENT compositional task generator for the E1 confirmation (torch-free).

Deliberately different from the validated experiment's generator: larger entity/attribute vocabularies,
4 synonyms per primitive (vs 3), 40 values, a distinct query template (attribute-anchored, different
filler placement and ordering), a distinct hard-negative construction, a new pool salt (fresh identity
partition), and fresh seeds. Same *categories* (G1..G7) and same ~32-key density. The frozen C1 recipe
(model + hyperparameters) is reused unchanged elsewhere; only data/eval/seeds are independent.
"""
from __future__ import annotations

import hashlib
import random

# ---- new vocabulary geometry (independent content; difficulty comparable to the validated task) ----
# Independence comes from fresh tokens/identities (new counts + new pool salt), a distinct query
# template, distinct negative profiles, a separate evaluator, and fresh seeds — NOT from changing task
# difficulty. Synonyms-per-primitive (the surface-variation driver) and 32-key density match the
# validated experiment so this is a fair replication, not a harder task.
ENTITY_PRIMS = 56        # new (was 48)
ATTR_PRIMS = 22          # new (was 20)
SYN = 3                  # match validated difficulty
N_VALUES = 36            # new (was 32)
N_FILLER = 14            # new (was 12)
KEYS_PER_EPISODE = 32    # same ~32-key density

PAD, SEP = 0, 1
_E_BASE = 2
_A_BASE = _E_BASE + ENTITY_PRIMS * SYN
_V_BASE = _A_BASE + ATTR_PRIMS * SYN
_F_BASE = _V_BASE + N_VALUES
VOCAB = _F_BASE + N_FILLER

KLEN = 4                 # canonical key: [E,E,SEP,A]
QLEN = 9                 # query (padded) — distinct template, more filler


def e_tok(prim, syn):
    return _E_BASE + prim * SYN + syn


def a_tok(prim, syn):
    return _A_BASE + prim * SYN + syn


def v_tok(v):
    return _V_BASE + v


def f_tok(f):
    return _F_BASE + f


# ---- fresh identity partition (new salt) -----------------------------------------------
def all_identities():
    return [(a, b) for a in range(ENTITY_PRIMS) for b in range(a + 1, ENTITY_PRIMS)]


def _bucket(identity, salt):
    h = hashlib.sha256(f"{salt}:{identity[0]}_{identity[1]}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def identity_pools(salt="e1_conf_pool_v1"):
    train, dev, final = [], [], []
    for idn in all_identities():
        b = _bucket(idn, salt)
        (train if b < 70 else dev if b < 85 else final).append(idn)
    return {"train": train, "dev": dev, "final": final}


# ---- surface rendering (distinct query template) ---------------------------------------
def render_key(identity, attr):
    a, b = identity
    return [e_tok(a, 0), e_tok(b, 0), SEP, a_tok(attr, 0)]


def render_query(rng, identity, attr, surface_level=1):
    """Attribute-anchored paraphrase: leading filler, attribute synonym, filler, then the two entity
    synonyms (order shuffled). Synonyms drawn from {1,2,3} (never 0 -> no verbatim key overlap)."""
    a, b = identity
    syns = list(range(1, SYN))          # non-zero synonyms only (no verbatim key overlap)
    sa = rng.choice(syns)
    ents = [e_tok(a, rng.choice(syns)), e_tok(b, rng.choice(syns))]
    rng.shuffle(ents)
    lead = [f_tok(rng.randrange(N_FILLER))]
    mid = [f_tok(rng.randrange(N_FILLER))] if surface_level >= 2 else []
    tail = [f_tok(rng.randrange(N_FILLER))] if surface_level >= 2 else []
    toks = lead + [a_tok(attr, sa)] + mid + ents + tail
    return _pad(toks, QLEN)


def _pad(toks, n):
    return (toks + [PAD] * n)[:n]


# ---- negatives + episodes (distinct construction) --------------------------------------
PROFILES = {
    "balanced": (5, 7, 9),        # (same_id_diff_attr, diff_id_same_attr, hard_name)
    "hard_names": (3, 3, 20),
    "same_entity": (15, 3, 6),
    "stable": (2, 2, 3),
}


def _distinct_identity(rng, pool, exclude, share_with=None):
    for _ in range(200):
        if share_with is not None and rng.random() < 0.8:
            other = rng.randrange(ENTITY_PRIMS)
            shared = rng.choice(share_with)
            cand = tuple(sorted({shared, other})) if other != shared else None
            if cand is None or len(cand) != 2:
                continue
        else:
            cand = pool[rng.randrange(len(pool))]
        if cand not in exclude and len(cand) == 2:
            return cand
    for cand in pool:
        if cand not in exclude:
            return cand
    raise RuntimeError("identity pool exhausted")


def build_episode(seed, target_pool, no_match=False, surface_level=1, profile="balanced"):
    rng = random.Random(seed)
    n_sida, n_disa, n_hard = PROFILES[profile]
    tgt_id = target_pool[rng.randrange(len(target_pool))]
    tgt_attr = rng.randrange(ATTR_PRIMS)
    used = {(tgt_id, tgt_attr)}
    facts = [(tgt_id, tgt_attr)]

    def add(fact):
        if fact not in used:
            used.add(fact); facts.append(fact); return True
        return False

    for _ in range(n_sida):
        add((tgt_id, rng.randrange(ATTR_PRIMS)))
    for _ in range(n_disa):
        add((_distinct_identity(rng, target_pool, {f[0] for f in facts}), tgt_attr))
    for _ in range(n_hard):
        add((_distinct_identity(rng, target_pool, {f[0] for f in facts}, share_with=list(tgt_id)),
             rng.randrange(ATTR_PRIMS)))
    guard = 0
    while len(facts) < KEYS_PER_EPISODE and guard < 1000:
        guard += 1
        add((_distinct_identity(rng, target_pool, {f[0] for f in facts}), rng.randrange(ATTR_PRIMS)))
    facts = facts[:KEYS_PER_EPISODE]

    key_values = [rng.randrange(N_VALUES) for _ in facts]
    key_tokens = [render_key(idn, at) for (idn, at) in facts]
    order = list(range(len(facts))); rng.shuffle(order)
    key_tokens = [key_tokens[i] for i in order]
    key_values = [key_values[i] for i in order]
    facts = [facts[i] for i in order]
    target_index = facts.index((tgt_id, tgt_attr))

    if no_match:
        for _ in range(500):
            q_id = _distinct_identity(rng, target_pool, {f[0] for f in facts})
            q_attr = rng.randrange(ATTR_PRIMS)
            if (q_id, q_attr) not in used:
                break
        return {"key_tokens": key_tokens, "key_values": key_values,
                "query_tokens": render_query(rng, q_id, q_attr, surface_level),
                "target_index": -1, "target_value": -1, "meta": {"no_match": True}}
    return {"key_tokens": key_tokens, "key_values": key_values,
            "query_tokens": render_query(rng, tgt_id, tgt_attr, surface_level),
            "target_index": target_index, "target_value": key_values[target_index],
            "meta": {"no_match": False}}


def build_split(pool, n_episodes, seed, no_match_frac=0.0, surface_level=1, profile="balanced"):
    eps = []
    for i in range(n_episodes):
        s = seed * 1_000_003 + i * 97 + 13
        nm = (random.Random(s ^ 0x5DEECE66).random() < no_match_frac)
        eps.append(build_episode(s, pool, no_match=nm, surface_level=surface_level, profile=profile))
    return eps


EVAL_SPLITS = {
    "G1_unseen_identity": (0.0, 1, "balanced"),
    "G2_paraphrase": (0.0, 2, "balanced"),
    "G3_hard_names": (0.0, 1, "hard_names"),
    "G4_same_entity_diff_attr": (0.0, 1, "same_entity"),
    "G5_recombined": (0.0, 1, "balanced"),
    "G6_no_match": (1.0, 1, "balanced"),
    "G7_stable": (0.0, 1, "stable"),
}


def build_eval_splits(pool, n_per_split, seed_base):
    out = {}
    for j, (name, (nmf, sl, prof)) in enumerate(EVAL_SPLITS.items()):
        out[name] = build_split(pool, n_per_split, seed=seed_base + j * 6151,
                                 no_match_frac=nmf, surface_level=sl, profile=prof)
    return out
