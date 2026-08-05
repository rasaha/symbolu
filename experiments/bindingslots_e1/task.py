#!/usr/bin/env python3
"""Deterministic compositional semantic-matching task for the E1 capability probe (torch-free).

Meaning is primitive-level: an identity = an unordered pair of entity primitives; an attribute = one
attribute primitive; a fact = (identity, attribute) -> value token. Each primitive has a synonym group
of distinct surface tokens. The stored KEY renders identity+attribute in a canonical surface form
(synonym index 0); the QUERY renders the SAME identity+attribute in a different surface form (non-zero
synonyms, reordered, with filler), sharing NO surface token verbatim with its key for the matched
primitives. Success therefore requires learned synonym->primitive grouping + composition (semantic
matching), not surface-token equality.

Identities are partitioned into disjoint train / development / final(reserved) pools. Dev calibration
uses the development pool; the reserved final pool is never read during Stage 2.
"""
from __future__ import annotations

import hashlib
import random

# ---- fixed vocabulary geometry (frozen) ------------------------------------------------
ENTITY_PRIMS = 48
ATTR_PRIMS = 20
SYN = 3                 # synonyms per primitive (surface forms)
N_VALUES = 32
N_FILLER = 12
KEYS_PER_EPISODE = 32   # 32-slot density (matches the regime where anonymous slots failed)

PAD, SEP = 0, 1
_E_BASE = 2
_A_BASE = _E_BASE + ENTITY_PRIMS * SYN
_V_BASE = _A_BASE + ATTR_PRIMS * SYN
_F_BASE = _V_BASE + N_VALUES
VOCAB = _F_BASE + N_FILLER

KLEN = 4                # canonical key length: [E,E,SEP,A]
QLEN = 8                # query length (padded)


def e_tok(prim, syn):
    return _E_BASE + prim * SYN + syn


def a_tok(prim, syn):
    return _A_BASE + prim * SYN + syn


def v_tok(v):
    return _V_BASE + v


def f_tok(f):
    return _F_BASE + f


def value_of_token(tok):
    return tok - _V_BASE


# ---- identity pools (deterministic, disjoint) ------------------------------------------
def all_identities():
    return [(a, b) for a in range(ENTITY_PRIMS) for b in range(a + 1, ENTITY_PRIMS)]


def _bucket(identity, salt):
    h = hashlib.sha256(f"{salt}:{identity[0]}_{identity[1]}".encode()).hexdigest()
    return int(h[:8], 16) % 100


def identity_pools(salt="e1_pool_v1"):
    """Disjoint train (70) / dev (15) / final-reserved (15) identity partition."""
    train, dev, final = [], [], []
    for idn in all_identities():
        b = _bucket(idn, salt)
        (train if b < 70 else dev if b < 85 else final).append(idn)
    return {"train": train, "dev": dev, "final": final}


# ---- surface rendering -----------------------------------------------------------------
def render_key(identity, attr):
    """Canonical surface (synonym index 0). Deterministic; no RNG."""
    a, b = identity
    return [e_tok(a, 0), e_tok(b, 0), SEP, a_tok(attr, 0)]


def render_query(rng, identity, attr, surface_level=1):
    """Paraphrase surface: non-zero synonyms (never index 0 -> no verbatim key overlap), reordered,
    with filler. surface_level 2 = maximal variation (more filler)."""
    a, b = identity
    sa, sb = rng.choice([1, 2]), rng.choice([1, 2])
    sat = rng.choice([1, 2])
    ent = [e_tok(a, sa), e_tok(b, sb)]
    rng.shuffle(ent)
    n_fill = 2 if surface_level >= 2 else 1
    fillers = [f_tok(rng.randrange(N_FILLER)) for _ in range(n_fill)]
    toks = ent + [a_tok(attr, sat)] + fillers
    rng.shuffle(toks)
    return _pad(toks, QLEN)


def _pad(toks, n):
    return (toks + [PAD] * n)[:n]


# ---- episode construction --------------------------------------------------------------
def _distinct_identity(rng, pool, exclude, share_with=None):
    """Draw an identity from pool distinct from all in `exclude`; if share_with given, prefer one that
    shares exactly one entity primitive (hard-name negative)."""
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
    # fallback: linear scan
    for cand in pool:
        if cand not in exclude:
            return cand
    raise RuntimeError("identity pool exhausted")


# negative-composition profiles: (same_id_diff_attr, diff_id_same_attr, hard_name) counts.
# The remainder up to KEYS_PER_EPISODE is filled with random distractors.
PROFILES = {
    "balanced": (6, 6, 8),
    "hard_names": (4, 4, 18),      # G3: many negatives share an entity primitive with the target
    "same_entity": (14, 4, 6),     # G4: many same-identity different-attribute negatives
    "stable": (2, 2, 2),           # G7: mostly random distractors (easy)
}


def build_episode(seed, target_pool, no_match=False, surface_level=1, profile="balanced"):
    """One episode: KEYS_PER_EPISODE distinct facts with hard negatives + a query.

    Returns dict with: key_tokens [K][KLEN], key_values [K], query_tokens [QLEN], target_index
    (int or -1 for no-match), and meta. Deterministic in `seed`. `profile` shifts negative composition.
    """
    rng = random.Random(seed)
    n_sida, n_disa, n_hard = PROFILES[profile]
    # target fact
    tgt_id = target_pool[rng.randrange(len(target_pool))]
    tgt_attr = rng.randrange(ATTR_PRIMS)
    used = {(tgt_id, tgt_attr)}
    facts = [(tgt_id, tgt_attr)]

    def add(fact):
        if fact not in used:
            used.add(fact); facts.append(fact); return True
        return False

    # same identity, different attributes
    for _ in range(n_sida):
        add((tgt_id, rng.randrange(ATTR_PRIMS)))
    # different identity, same attribute
    for _ in range(n_disa):
        nid = _distinct_identity(rng, target_pool, {f[0] for f in facts})
        add((nid, tgt_attr))
    # hard-name: identity sharing one entity primitive with target
    for _ in range(n_hard):
        nid = _distinct_identity(rng, target_pool, {f[0] for f in facts}, share_with=list(tgt_id))
        add((nid, rng.randrange(ATTR_PRIMS)))
    # random distractors up to K
    guard = 0
    while len(facts) < KEYS_PER_EPISODE and guard < 1000:
        guard += 1
        nid = _distinct_identity(rng, target_pool, {f[0] for f in facts})
        add((nid, rng.randrange(ATTR_PRIMS)))
    facts = facts[:KEYS_PER_EPISODE]

    # values (repeat across keys; not unique identifiers)
    key_values = [rng.randrange(N_VALUES) for _ in facts]
    key_tokens = [render_key(idn, at) for (idn, at) in facts]

    # candidate order shuffle (target not always first)
    order = list(range(len(facts)))
    rng.shuffle(order)
    key_tokens = [key_tokens[i] for i in order]
    key_values = [key_values[i] for i in order]
    facts = [facts[i] for i in order]
    target_index = facts.index((tgt_id, tgt_attr))

    if no_match:
        # query an (identity, attribute) guaranteed ABSENT from the 32 keys
        for _ in range(500):
            q_id = _distinct_identity(rng, target_pool, {f[0] for f in facts})
            q_attr = rng.randrange(ATTR_PRIMS)
            if (q_id, q_attr) not in used:
                break
        query_tokens = render_query(rng, q_id, q_attr, surface_level)
        return {"key_tokens": key_tokens, "key_values": key_values,
                "query_tokens": query_tokens, "target_index": -1,
                "target_value": -1, "meta": {"no_match": True}}

    query_tokens = render_query(rng, tgt_id, tgt_attr, surface_level)
    return {"key_tokens": key_tokens, "key_values": key_values,
            "query_tokens": query_tokens, "target_index": target_index,
            "target_value": key_values[target_index], "meta": {"no_match": False}}


# ---- split builders --------------------------------------------------------------------
def build_split(pool, n_episodes, seed, no_match_frac=0.0, surface_level=1, profile="balanced"):
    eps = []
    for i in range(n_episodes):
        s = seed * 1_000_003 + i * 97 + 13
        nm = (random.Random(s ^ 0x9E3779B9).random() < no_match_frac)
        eps.append(build_episode(s, pool, no_match=nm, surface_level=surface_level, profile=profile))
    return eps


# split definitions: name -> (no_match_frac, surface_level, profile, description)
EVAL_SPLITS = {
    "G1_unseen_identity": (0.0, 1, "balanced", "target identity is a held-out (dev/final) combination"),
    "G2_paraphrase": (0.0, 2, "balanced", "maximal surface variation of the query"),
    "G3_hard_names": (0.0, 1, "hard_names", "negatives share an entity primitive with the target"),
    "G4_same_entity_diff_attr": (0.0, 1, "same_entity", "many same-identity different-attribute negatives"),
    "G5_recombined": (0.0, 1, "balanced", "unseen identity x attribute x value combinations"),
    "G6_no_match": (1.0, 1, "balanced", "queried fact absent from episode memory"),
    "G7_stable": (0.0, 1, "stable", "easy episodes (few shared primitives) — historically stable cases"),
}


def build_eval_splits(pool, n_per_split, seed_base):
    """Build all G1..G7 for a given identity pool (dev pool for calibration; final pool for reserved)."""
    out = {}
    for j, (name, (nmf, sl, prof, _desc)) in enumerate(EVAL_SPLITS.items()):
        out[name] = build_split(pool, n_per_split, seed=seed_base + j * 7919,
                                 no_match_frac=nmf, surface_level=sl, profile=prof)
    return out
