#!/usr/bin/env python3
"""Temporal Event Memory task generator (torch-free) — a structurally different family for the E1
transfer test. Each episode holds ~32 event records; a record = (entity, event-type, step, status).
The stored KEY encodes entity + event-type + step surface tokens (never the status); the VALUE is the
status. Queries reference an entity plus a temporal predicate (a specific step, or "latest", or an
after/before successor) using DIFFERENT surface synonyms than the key (no verbatim overlap).

Structural novelty vs the original compositional-lookup family: an entity has MULTIPLE ordered events,
so retrieval requires resolving temporal position (latest / at-step / successor), not just identity.
All position/predicate tokens are bounded synthetic vocabulary rendered through the existing C1 input
representation — no new tokenizer, embedding model, recurrent/attention/positional architecture.
"""
from __future__ import annotations

import hashlib
import random

# ---- bounded synthetic vocabulary ------------------------------------------------------
ENTITY_PRIMS = 40
EVENT_TYPES = 8
SYN = 3                  # surface synonyms per entity/event/step primitive
STATUS_VALUES = 10       # the answers (values); repeat across keys; never inside a key
STEPS = 16               # step_01..step_16 (each with SYN surface forms)
N_FILLER = 12
KEYS_PER_EPISODE = 32

PAD, SEP = 0, 1
_E = 2
_EV = _E + ENTITY_PRIMS * SYN
_ST = _EV + EVENT_TYPES * SYN          # status (value) tokens
_P = _ST + STATUS_VALUES               # step surface tokens
_LAT = _P + STEPS * SYN                # "latest" predicate synonyms
_AFT = _LAT + SYN                      # "after" / "before" predicate tokens
_BEF = _AFT + 1
_F = _BEF + 1
VOCAB = _F + N_FILLER

KLEN = 4                 # [E,E,EV,P]
QLEN = 7


def e_tok(p, s): return _E + p * SYN + s
def ev_tok(p, s): return _EV + p * SYN + s
def st_tok(v): return _ST + v
def p_tok(step, s): return _P + step * SYN + s
def lat_tok(s): return _LAT + s
def aft_tok(): return _AFT
def bef_tok(): return _BEF
def f_tok(f): return _F + f
def status_of(tok): return tok - _ST


# ---- fresh identity partition ----------------------------------------------------------
def all_identities():
    return [(a, b) for a in range(ENTITY_PRIMS) for b in range(a + 1, ENTITY_PRIMS)]


def identity_pools(salt="e1_temporal_pool_v1"):
    train, dev, final = [], [], []
    for idn in all_identities():
        b = int(hashlib.sha256(f"{salt}:{idn[0]}_{idn[1]}".encode()).hexdigest()[:8], 16) % 100
        (train if b < 70 else dev if b < 85 else final).append(idn)
    return {"train": train, "dev": dev, "final": final}


def _pad(toks, n): return (toks + [PAD] * n)[:n]

def render_key(identity, ev, step):
    a, b = identity
    return [e_tok(a, 0), e_tok(b, 0), ev_tok(ev, 0), p_tok(step, 0)]

def _ent_surface(rng, identity):
    a, b = identity
    ents = [e_tok(a, rng.choice([1, 2])), e_tok(b, rng.choice([1, 2]))]
    rng.shuffle(ents)
    return ents

def render_query(rng, identity, kind, step=None, surface_level=1):
    """kind in {'latest','at_step','after','before'}. Uses non-zero synonyms for entity/step."""
    ents = _ent_surface(rng, identity)
    fills = [f_tok(rng.randrange(N_FILLER)) for _ in range(2 if surface_level >= 2 else 1)]
    if kind == "latest":
        pred = [lat_tok(rng.randrange(SYN))]
    elif kind == "at_step":
        pred = [p_tok(step, rng.choice([1, 2]))]
    elif kind == "after":
        pred = [aft_tok(), p_tok(step, rng.choice([1, 2]))]
    else:  # before
        pred = [bef_tok(), p_tok(step, rng.choice([1, 2]))]
    toks = ents + pred + fills
    rng.shuffle(toks)
    return _pad(toks, QLEN)


# ---- episode construction --------------------------------------------------------------
def _draw_identity(rng, pool, exclude, share_with=None):
    for _ in range(200):
        if share_with is not None and rng.random() < 0.8:
            other = rng.randrange(ENTITY_PRIMS)
            cand = tuple(sorted({rng.choice(share_with), other}))
            if len(cand) != 2:
                continue
        else:
            cand = pool[rng.randrange(len(pool))]
        if cand not in exclude and len(cand) == 2:
            return cand
    for c in pool:
        if c not in exclude:
            return c
    raise RuntimeError("pool exhausted")


def _build_records(rng, pool, split, target_single=False):
    """Return (records, target_entity, target_events). records: list of (identity, ev, step, status).
    Each entity gets several events at increasing steps. For 'stable' the target has a single event."""
    n_entities = 9
    hard = (split in ("T7_confusable",))
    ents = []
    seen = set()
    tgt = _draw_identity(rng, pool, seen); seen.add(tgt); ents.append(tgt)
    for _ in range(n_entities - 1):
        e = _draw_identity(rng, pool, seen, share_with=list(tgt) if hard else None)
        seen.add(e); ents.append(e)
    records = []
    ent_events = {}
    for e in ents:
        ev = rng.randrange(EVENT_TYPES)
        if e == tgt and target_single:
            m = 1
        else:
            m = rng.randint(2, 4)
        steps = sorted(rng.sample(range(STEPS), m))
        evs = [(s, rng.randrange(STATUS_VALUES)) for s in steps]
        ent_events[e] = (ev, evs)
        for (s, st) in evs:
            records.append((e, ev, s, st))
    # pad with extra entities' events up to KEYS_PER_EPISODE
    guard = 0
    while len(records) < KEYS_PER_EPISODE and guard < 500:
        guard += 1
        e = _draw_identity(rng, pool, seen); seen.add(e)
        ev = rng.randrange(EVENT_TYPES)
        for s in sorted(rng.sample(range(STEPS), rng.randint(2, 3))):
            if len(records) < KEYS_PER_EPISODE:
                records.append((e, ev, s, rng.randrange(STATUS_VALUES)))
        ent_events[e] = (ev, None)
    records = records[:KEYS_PER_EPISODE]
    return records, tgt, ent_events


def build_episode(seed, pool, split):
    rng = random.Random(seed)
    surface = 2 if split == "T6_paraphrase" else 1
    stable = (split == "T9_stable")
    records, tgt, ent_events = _build_records(rng, pool, split, target_single=stable)
    # ensure target has enough events for the split's predicate
    tgt_recs = [(i, r) for i, r in enumerate(records) if r[0] == tgt]
    key_tokens = [render_key(r[0], r[1], r[2]) for r in records]
    key_values = [st_tok(r[3]) for r in records]
    order = list(range(len(records))); rng.shuffle(order)
    key_tokens = [key_tokens[i] for i in order]
    key_values = [key_values[i] for i in order]
    records = [records[i] for i in order]
    tgt_recs = [(i, r) for i, r in enumerate(records) if r[0] == tgt]

    def out(qtok, tidx):
        return {"key_tokens": key_tokens, "key_values": key_values, "query_tokens": qtok,
                "target_index": tidx, "target_value": (key_values[tidx] if tidx >= 0 else -1),
                "meta": {"split": split}}

    if split == "T8_no_match":
        # query an entity/step absent from the episode
        for _ in range(300):
            q = _draw_identity(rng, pool, {r[0] for r in records})
            if q not in {r[0] for r in records}:
                break
        return out(render_query(rng, q, "latest", surface_level=surface), -1)

    if split == "T4_latest":
        # latest-state: correct = target entity's max-step record (query says "latest", no step given)
        idx = max(tgt_recs, key=lambda ir: ir[1][2])[0]
        return out(render_query(rng, tgt, "latest", surface_level=surface), idx)

    if split == "T9_stable":
        # stable direct retrieval: target has a SINGLE event; query fully specifies its step (unambiguous)
        i, r = tgt_recs[0]
        return out(render_query(rng, tgt, "at_step", step=r[2], surface_level=surface), i)

    if split in ("T3_temporal_order", "T1_unseen_entity", "T2_unseen_combo", "T6_paraphrase", "T7_confusable"):
        # at-step: pick one of the target's events (not necessarily latest)
        i, r = tgt_recs[rng.randrange(len(tgt_recs))]
        return out(render_query(rng, tgt, "at_step", step=r[2], surface_level=surface), i)

    if split == "T5_pred_succ":
        # within-entity successor: status immediately AFTER a reference step (diagnostic)
        steps_sorted = sorted(tgt_recs, key=lambda ir: ir[1][2])
        if len(steps_sorted) >= 2:
            k = rng.randrange(len(steps_sorted) - 1)
            ref_step = steps_sorted[k][1][2]
            succ_idx = steps_sorted[k + 1][0]
            return out(render_query(rng, tgt, "after", step=ref_step, surface_level=surface), succ_idx)
        # fallback: latest
        idx = max(tgt_recs, key=lambda ir: ir[1][2])[0]
        return out(render_query(rng, tgt, "latest", surface_level=surface), idx)

    raise ValueError(split)


# ---- split registry --------------------------------------------------------------------
SPLITS = ["T1_unseen_entity", "T2_unseen_combo", "T3_temporal_order", "T4_latest",
          "T5_pred_succ", "T6_paraphrase", "T7_confusable", "T8_no_match", "T9_stable"]


def build_split(pool, n, seed, split):
    return [build_episode(seed * 1_000_003 + i * 97 + 13, pool, split) for i in range(n)]


def build_eval_splits(pool, n_per_split, seed_base):
    return {name: build_split(pool, n_per_split, seed_base + j * 6151, name)
            for j, name in enumerate(SPLITS)}


def build_train_episodes(pool, n, seed, no_match_frac):
    """Training mixes all query kinds + no-match, so the frozen recipe sees the temporal predicates."""
    eps = []
    kinds = ["T3_temporal_order", "T4_latest", "T4_latest", "T3_temporal_order", "T5_pred_succ"]
    for i in range(n):
        s = seed * 1_000_003 + i * 97 + 13
        r = random.Random(s ^ 0x5DEECE66)
        if r.random() < no_match_frac:
            eps.append(build_episode(s, pool, "T8_no_match"))
        else:
            eps.append(build_episode(s, pool, r.choice(kinds)))
    return eps
