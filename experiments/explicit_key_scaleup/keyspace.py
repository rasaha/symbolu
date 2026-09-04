"""Enterprise-shaped explicit-key task for E1-S (torch-free, deterministic, process-independent).

A memory = (subject_type, subject_id, relation_type, object_type) -> value. Types and relations come from
experiments/enterprise_slots_quadratic/schema.py vocabularies and are rendered through synonym groups
(canonical synonym 0 in the stored KEY; synonyms 1/2 in the QUERY => zero verbatim overlap on those
tokens). A subject_id is an ORDERED PAIR of opaque id primitives that appears VERBATIM in key and query
(it is the thing to be matched, not paraphrased); id primitives are a reserved token range that appears
nowhere else (BTRR F16). Identity pools are an invisible sha256 partition of the pair space (F14). Nothing
here uses the salted builtin hash() (F11).
"""
from __future__ import annotations

import hashlib
import random

from experiments.enterprise_slots_quadratic.schema import OBJECT_TYPES, RELATION_TYPES, SUBJECT_TYPES

# ---- frozen vocabulary geometry ---------------------------------------------------------------
N_ST, N_REL, N_OT = len(SUBJECT_TYPES), len(RELATION_TYPES), len(OBJECT_TYPES)   # 10, 10, 8
SYN = 3                      # synonyms per type/relation primitive (surface forms)
ID_PRIMS = 96                # opaque id primitives; subject_id = ordered pair (p1 != p2) => 9120 ids
N_VALUES = 32                # value tokens (repeat across keys; not identifiers)
N_FILLER = 12

PAD, SEP = 0, 1              # identical to E1's task.PAD / task.SEP (E1._masked_mean masks on PAD == 0)
_ST_BASE = 2
_REL_BASE = _ST_BASE + N_ST * SYN
_OT_BASE = _REL_BASE + N_REL * SYN
_ID_BASE = _OT_BASE + N_OT * SYN
_V_BASE = _ID_BASE + ID_PRIMS
_F_BASE = _V_BASE + N_VALUES
VOCAB = _F_BASE + N_FILLER   # 226

KLEN = 6                     # [ST, ID1, ID2, SEP, REL, OT]
QLEN = 9                     # paraphrased ST/REL/OT + verbatim ID1 ID2 + up to 2 fillers (+ pad)

DENSITIES = (32, 128, 512)   # frozen ladder; 32 = replication anchor, 512 = primary

# ---- tokens --------------------------------------------------------------------------------------
def st_tok(p, syn): return _ST_BASE + p * SYN + syn
def rel_tok(p, syn): return _REL_BASE + p * SYN + syn
def ot_tok(p, syn): return _OT_BASE + p * SYN + syn
def id_tok(p): return _ID_BASE + p
def v_tok(v): return _V_BASE + v
def f_tok(f): return _F_BASE + f


def token_class(t: int) -> str:
    if t == PAD: return "pad"
    if t == SEP: return "sep"
    if _ST_BASE <= t < _REL_BASE: return "subject_type"
    if _REL_BASE <= t < _OT_BASE: return "relation_type"
    if _OT_BASE <= t < _ID_BASE: return "object_type"
    if _ID_BASE <= t < _V_BASE: return "id"
    if _V_BASE <= t < _F_BASE: return "value"
    if _F_BASE <= t < VOCAB: return "filler"
    raise ValueError(t)


def value_of_token(t): return t - _V_BASE


# ---- stable hashing + invisible partitions ------------------------------------------------------
def _stable(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def all_subject_ids():
    return [(a, b) for a in range(ID_PRIMS) for b in range(ID_PRIMS) if a != b]


def identity_pools(salt: str = "e1s_pool_v1") -> dict:
    """Disjoint train (70%) / dev (15%) / final (15%) partition of ordered id pairs by stable hash. No
    marker: every id primitive occurs in every pool at both positions."""
    train, dev, final = [], [], []
    for sid in all_subject_ids():
        b = _stable(f"{salt}:id:{sid[0]}_{sid[1]}") % 100
        (train if b < 70 else dev if b < 85 else final).append(sid)
    return {"train": train, "dev": dev, "final": final}


def st_rel_pairs(salt: str = "e1s_pool_v1") -> dict:
    """(subject_type, relation_type) combinations: 80% train-visible, 20% HELD OUT (G8). Held-out pairs
    never appear in any training episode, as target or as negative."""
    seen, held = [], []
    for st in range(N_ST):
        for rel in range(N_REL):
            (seen if _stable(f"{salt}:pair:{st}_{rel}") % 100 < 80 else held).append((st, rel))
    return {"seen": seen, "held_out": held}


# ---- rendering -------------------------------------------------------------------------------------
def render_key(fact) -> list:
    """Canonical surface: [ST(syn0), ID1, ID2, SEP, REL(syn0), OT(syn0)]. Deterministic."""
    st, sid, rel, ot = fact
    return [st_tok(st, 0), id_tok(sid[0]), id_tok(sid[1]), SEP, rel_tok(rel, 0), ot_tok(ot, 0)]


def render_query(rng: random.Random, fact, surface_level: int = 1) -> list:
    """Paraphrased surface: non-zero synonyms for ST/REL/OT (never verbatim), ids verbatim, 1-2 fillers,
    shuffled (E1's encoder is a masked mean, so order is cosmetic; the shuffle removes positional cues)."""
    st, sid, rel, ot = fact
    toks = [st_tok(st, rng.choice((1, 2))), id_tok(sid[0]), id_tok(sid[1]),
            rel_tok(rel, rng.choice((1, 2))), ot_tok(ot, rng.choice((1, 2)))]
    toks += [f_tok(rng.randrange(N_FILLER)) for _ in range(2 if surface_level >= 2 else 1)]
    rng.shuffle(toks)
    return (toks + [PAD] * QLEN)[:QLEN]


# ---- near-miss profiles (fractions of K; at K=32 they reproduce E1's PROFILES exactly) ------------
PROFILES = {
    # (same_subject_diff_relation, diff_subject_same_relation, shared_id_primitive)
    "balanced": (0.1875, 0.1875, 0.25),      # K=32 -> (6, 6, 8)
    "hard_names": (0.125, 0.125, 0.5625),    # K=32 -> (4, 4, 18)
    "same_entity": (0.4375, 0.125, 0.1875),  # K=32 -> (14, 4, 6)
    "stable": (0.0625, 0.0625, 0.0625),      # K=32 -> (2, 2, 2)
}


def profile_counts(profile: str, K: int) -> tuple:
    return tuple(int(K * f) for f in PROFILES[profile])


def _distinct_sid(rng, pool, exclude, share_with=None):
    for _ in range(400):
        if share_with is not None and rng.random() < 0.8:
            shared = rng.choice(share_with)
            other = rng.randrange(ID_PRIMS)
            if other == shared:
                continue
            cand = (shared, other) if rng.random() < 0.5 else (other, shared)
        else:
            cand = pool[rng.randrange(len(pool))]
        if cand not in exclude:
            return cand
    for cand in pool:
        if cand not in exclude:
            return cand
    raise RuntimeError("subject-id pool exhausted")


def _same_subject(rng, pairs, sid):
    st, rel = pairs[rng.randrange(len(pairs))]
    return (st, sid, rel, rng.randrange(N_OT))


def build_episode(seed: int, sid_pool: list, K: int, *, no_match: bool = False, surface_level: int = 1,
                  profile: str = "balanced", pairs: list | None = None, target_pairs: list | None = None) -> dict:
    """One episode: K distinct facts (near-miss negatives per `profile`) + one query.

    `pairs`: allowed (ST, REL) combinations for every fact; `target_pairs`: combinations the TARGET may use
    (G8 draws targets from held-out pairs; training never sees them). Deterministic in `seed`."""
    rng = random.Random(int(seed))
    pairs = pairs if pairs is not None else st_rel_pairs()["seen"]
    target_pairs = target_pairs if target_pairs is not None else pairs
    n_sida, n_disa, n_hard = profile_counts(profile, K)

    def new_fact(sid, st_rel=None):
        st, rel = st_rel if st_rel is not None else pairs[rng.randrange(len(pairs))]
        return (st, sid, rel, rng.randrange(N_OT))

    tgt_sid = sid_pool[rng.randrange(len(sid_pool))]
    tgt_st, tgt_rel = target_pairs[rng.randrange(len(target_pairs))]
    tgt = (tgt_st, tgt_sid, tgt_rel, rng.randrange(N_OT))
    facts, used = [tgt], {tgt}

    def add(f):
        if f not in used:
            used.add(f); facts.append(f); return True
        return False

    def add_n(n, make):                                        # reach the profile count despite dedup collisions
        got = 0
        for _ in range(50 * max(1, n)):
            if got >= n:
                break
            got += add(make())
        return got

    add_n(n_sida, lambda: _same_subject(rng, pairs, tgt_sid))          # same subject, different relation
    add_n(n_disa, lambda: new_fact(_distinct_sid(rng, sid_pool, {f[1] for f in facts}), (tgt_st, tgt_rel)))
    add_n(n_hard, lambda: new_fact(_distinct_sid(rng, sid_pool, {f[1] for f in facts}, share_with=list(tgt_sid))))
    guard = 0
    while len(facts) < K and guard < 20 * K:
        guard += 1
        add(new_fact(_distinct_sid(rng, sid_pool, {f[1] for f in facts})))
    if len(facts) < K:
        raise RuntimeError(f"could not fill {K} distinct facts")
    facts = facts[:K]
    values = [rng.randrange(N_VALUES) for _ in facts]
    order = list(range(K)); rng.shuffle(order)
    facts = [facts[i] for i in order]; values = [values[i] for i in order]
    key_tokens = [render_key(f) for f in facts]
    target_index = facts.index(tgt)
    if no_match:
        for _ in range(500):
            q_sid = _distinct_sid(rng, sid_pool, {f[1] for f in facts})
            st, rel = target_pairs[rng.randrange(len(target_pairs))]
            q = (st, q_sid, rel, rng.randrange(N_OT))
            if q not in used:
                break
        return {"key_tokens": key_tokens, "key_values": values, "query_tokens": render_query(rng, q, surface_level),
                "target_index": -1, "target_value": -1, "K": K, "meta": {"no_match": True, "profile": profile}}
    return {"key_tokens": key_tokens, "key_values": values, "query_tokens": render_query(rng, tgt, surface_level),
            "target_index": target_index, "target_value": values[target_index], "K": K,
            "meta": {"no_match": False, "profile": profile}}


def build_split(sid_pool, n_episodes, seed, K, *, no_match_frac=0.0, surface_level=1, profile="balanced",
                pairs=None, target_pairs=None):
    eps = []
    for i in range(n_episodes):
        s = int(seed) * 1_000_003 + i * 97 + 13 + K * 7_919
        nm = (random.Random(s ^ 0x9E3779B9).random() < no_match_frac)
        eps.append(build_episode(s, sid_pool, K, no_match=nm, surface_level=surface_level, profile=profile,
                                 pairs=pairs, target_pairs=target_pairs))
    return eps


# split name -> (no_match_frac, surface_level, profile, target_pair_set, description)
EVAL_SPLITS = {
    "G1_unseen_identity": (0.0, 1, "balanced", "seen", "target subject id is a held-out pair (dev/final pool)"),
    "G2_paraphrase": (0.0, 2, "balanced", "seen", "maximal surface variation of the query"),
    "G3_hard_names": (0.0, 1, "hard_names", "seen", "negatives share an id primitive with the target"),
    "G4_same_entity_diff_attr": (0.0, 1, "same_entity", "seen", "many same-subject different-relation negatives"),
    "G5_recombined": (0.0, 1, "balanced", "seen", "unseen subject x relation x object-type x value combinations"),
    "G6_no_match": (1.0, 1, "balanced", "seen", "queried fact absent from memory"),
    "G7_stable": (0.0, 1, "stable", "seen", "few near-miss negatives"),
    "G8_unseen_composition": (0.0, 1, "balanced", "held_out", "target (subject_type, relation_type) never seen in training"),
}


def build_eval_splits(sid_pool, n_per_split, seed_base, K):
    pairs = st_rel_pairs()
    out = {}
    for j, (name, (nmf, sl, prof, tp, _d)) in enumerate(EVAL_SPLITS.items()):
        out[name] = build_split(sid_pool, n_per_split, seed_base + j * 7_919, K, no_match_frac=nmf,
                                surface_level=sl, profile=prof, pairs=pairs["seen"] + pairs["held_out"],
                                target_pairs=pairs[tp])
    return out


def build_train_split(n_episodes, seed, K, no_match_frac):
    """Training uses the TRAIN id pool and ONLY train-visible (ST, REL) pairs (held-out pairs excluded)."""
    return build_split(identity_pools()["train"], n_episodes, seed, K, no_match_frac=no_match_frac,
                       pairs=st_rel_pairs()["seen"])
