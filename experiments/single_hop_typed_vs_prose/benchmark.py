"""Real single-hop typed-vs-prose benchmark: pooled episode generation with DISJOINT
train/final identities (so evaluation requires copying the answer from context, not
memorizing IDs), paired B0/B1 training on one frozen model recipe, greedy structured-output
decoding, per-split scoring, causal ablations, shortcut baselines, and the frozen gates/verdict.

Frozen design constants (set BEFORE any reserved run; do not tune on results):
  TRAIN identities: numeric suffix [100,600); FINAL identities: [600,1000) -> disjoint.
  TRAIN episodes/scenario = 40 (320 total); EVAL episodes/scenario = 24 (192 total).
  Model + optimizer = FROZEN_MODEL_RECIPE / FROZEN_TRAIN_RECIPE (2000 updates, batch 8).
Only the input representation (B0 prose vs B1 JSON) differs between the two arms.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, replace

import torch

from .config import FROZEN_MODEL_RECIPE, FROZEN_TRAIN_RECIPE, SCENARIO_IDS, UNIT_TEST_SEED
from .dataset import SyntheticEpisodeGenerator, make_pair, encode_pair_arm
from .evaluator import OutputParseError, parse_output, score_output
from .execution import guard_seed
from .model import build_model, greedy_generate
from .schema import CanonicalEpisode
from .tokenizer import LexicalTokenizer
from .trainer import train_in_memory

# ---- frozen design constants ----
TRAIN_ID_RANGE = (100, 600)
FINAL_ID_RANGE = (600, 1000)
TRAIN_PER_SCENARIO = 40
EVAL_PER_SCENARIO = 24
ABLATION_PER_SCENARIO = 12
TEMPLATE_SEED = UNIT_TEST_SEED  # non-benchmark seed used only to build fixed structural templates

PRIMARY_SPLITS = ("S1", "S2", "S3", "S5", "S6")

# Arm-neutral evaluation generation cap. Every valid gold output is <=38 tokens and every
# ablation represented-output is <=62 tokens, so 96 never truncates a correct/parseable answer
# for either arm; it only bounds the length of a degenerate non-terminating decode. This is an
# evaluation-efficiency bound, NOT the model's training output allowance (which stays frozen at
# FROZEN_MODEL_RECIPE.max_output_tokens and is identical for both arms).
EVAL_OUTPUT_TOKENS = 96

# per-split scored field (how each scenario is graded)
SPLIT_FIELD = {
    "S1": "entity", "S2": "entity", "S3": "relation_support", "S4": "entity",
    "S5": "evidence_f1", "S6": "abstention", "S7": "abstention", "S8": "relation_support",
}


def _templates():
    gen = SyntheticEpisodeGenerator(TEMPLATE_SEED)
    return {s: gen.build(s) for s in SCENARIO_IDS}


def relabel_episode(ep: CanonicalEpisode, id_range, rng: random.Random) -> CanonicalEpisode:
    """Remap every entity_id / evidence_ref to a fresh distinct id from id_range (prefix preserved),
    consistently across entities, relations, evidence, query, and the authoritative output. Tenants,
    names, types, relation types, and reason codes are unchanged."""
    lo, hi = id_range
    used: set[str] = set()
    mapping: dict[str, str] = {}

    def fresh(old: str) -> str:
        prefix = old[0]
        for _ in range(10000):
            cand = f"{prefix}{rng.randrange(lo, hi)}"
            if cand not in used:
                used.add(cand)
                return cand
        raise RuntimeError("identity pool exhausted")

    for e in ep.entities:
        mapping.setdefault(e.entity_id, fresh(e.entity_id))
    for ev in ep.evidence:
        mapping.setdefault(ev.evidence_ref, fresh(ev.evidence_ref))

    def m(x):
        return mapping.get(x, x)

    entities = tuple(replace(e, entity_id=m(e.entity_id)) for e in ep.entities)
    relations = tuple(
        replace(r, source_entity_id=m(r.source_entity_id), target_entity_id=m(r.target_entity_id),
                evidence_ref=(m(r.evidence_ref) if r.evidence_ref is not None else None))
        for r in ep.relations
    )
    evidence = tuple(replace(ev, evidence_ref=m(ev.evidence_ref)) for ev in ep.evidence)
    query = replace(ep.query, entity_id=m(ep.query.entity_id))
    out = ep.authoritative_output
    out = replace(
        out,
        selected_entity_id=(m(out.selected_entity_id) if out.selected_entity_id is not None else None),
        evidence_refs=tuple(m(r) for r in out.evidence_refs),
    )
    return replace(
        ep, episode_id=f"{ep.episode_id}-{rng.randrange(10 ** 9)}",
        entities=entities, relations=relations, evidence=evidence, query=query,
        authoritative_output=out,
    )


def build_pairs(seed: int, id_range, n_per_scenario: int, templates):
    rng = random.Random(seed)
    pairs = []
    for s in SCENARIO_IDS:
        for _ in range(n_per_scenario):
            pairs.append((s, make_pair(relabel_episode(templates[s], id_range, rng))))
    return pairs


@torch.no_grad()
def _predict(model, tokenizer, serialized: str):
    prompt = serialized + FROZEN_TRAIN_RECIPE.output_marker
    prompt_ids = [tokenizer.bos_id, *tokenizer.encode(prompt)]
    text = greedy_generate(model, prompt_ids, tokenizer=tokenizer,
                           max_output_tokens=EVAL_OUTPUT_TOKENS)
    try:
        return parse_output(text), None
    except OutputParseError as exc:
        return None, str(exc)


def _f1(p: float, r: float) -> float:
    return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)


def evaluate_arm(model, tokenizer, eval_pairs, arm: str):
    """Return per-split metrics dict for one trained arm."""
    per_split: dict[str, dict] = {s: {"n": 0, "hits": 0.0, "prec": 0.0, "rec": 0.0,
                                      "abstain_ok": 0, "unauth": 0, "exact": 0, "parse_fail": 0}
                                  for s in SCENARIO_IDS}
    for scenario, pair in eval_pairs:
        serialized = pair.b0 if arm == "B0" else pair.b1
        pred, err = _predict(model, tokenizer, serialized)
        d = per_split[scenario]
        d["n"] += 1
        if pred is None:
            d["parse_fail"] += 1
            continue
        sc = score_output(pair.episode, pred)
        d["exact"] += int(sc.exact_output)
        d["prec"] += sc.evidence_precision
        d["rec"] += sc.evidence_recall
        d["abstain_ok"] += int(sc.abstention_correct)
        d["unauth"] += int(sc.unauthorized_cross_tenant_inclusion)
        field = SPLIT_FIELD[scenario]
        if field == "entity":
            d["hits"] += int(sc.entity_correct)
        elif field == "relation_support":
            d["hits"] += int(sc.relation_support_correct)
        elif field == "abstention":
            d["hits"] += int(sc.abstention_correct)
        elif field == "evidence_f1":
            d["hits"] += _f1(sc.evidence_precision, sc.evidence_recall)
    out = {}
    for s, d in per_split.items():
        n = max(d["n"], 1)
        out[s] = {
            "n": d["n"], "score": d["hits"] / n, "exact": d["exact"] / n,
            "evidence_precision": d["prec"] / n, "evidence_recall": d["rec"] / n,
            "abstention_accuracy": d["abstain_ok"] / n, "unauthorized_inclusions": d["unauth"],
            "parse_fail_rate": d["parse_fail"] / n,
        }
    out["primary"] = sum(out[s]["score"] for s in PRIMARY_SPLITS) / len(PRIMARY_SPLITS)
    return out


def run_arm(seed: int, arm: str, train_pairs, eval_pairs):
    tokenizer = LexicalTokenizer()
    examples = [encode_pair_arm(pair, arm) for (_, pair) in train_pairs]
    model = build_model(seed, FROZEN_MODEL_RECIPE)
    train_result = train_in_memory(model, examples, seed=seed)
    metrics = evaluate_arm(model, tokenizer, eval_pairs, arm)
    return {"metrics": metrics, "final_loss": train_result.final_loss,
            "first_loss": train_result.first_loss, "param_count": model.parameter_count()}


def shortcut_baselines(eval_pairs):
    """Non-learned baselines that must stay near chance on the GRADED, genuinely ambiguous
    target-selection splits (entity is the scored field AND at least two same-type candidates
    exist, so a correct pick requires reading the relation/evidence structure rather than the
    entity list alone). Splits with a single same-type candidate are excluded: there 'pick the
    only same-type entity' is the correct answer, not a shortcut, and entity is not their graded
    field anyway. Two structure-blind heuristics are reported:
      first_sorted_id  -- pick the lexically first same-type id (positional shortcut)
      lexical_overlap  -- pick the same-type id sharing the most characters with the query id
    Both should sit at chance (~1/candidates); a value materially above chance would mean the
    disambiguation splits are solvable without reading the typed/prose structure at all."""
    first_hits = lex_hits = scored_n = 0
    candidate_counts: list[int] = []
    for scenario, pair in eval_pairs:
        if SPLIT_FIELD.get(scenario) != "entity":
            continue
        ep = pair.episode
        gold = ep.authoritative_output
        if gold.selected_entity_id is None:
            continue
        gold_ent = next(e for e in ep.entities if e.entity_id == gold.selected_entity_id)
        same_type = [e for e in ep.entities if e.entity_type == gold_ent.entity_type]
        if len(same_type) < 2:
            continue  # no disambiguation to game
        candidate_counts.append(len(same_type))
        first_pick = sorted(same_type, key=lambda e: e.entity_id)[0].entity_id
        first_hits += int(first_pick == gold.selected_entity_id)
        q = ep.query.entity_id
        lex_pick = max(
            same_type, key=lambda e: (len(set(e.entity_id) & set(q)), e.entity_id)
        ).entity_id
        lex_hits += int(lex_pick == gold.selected_entity_id)
        scored_n += 1
    n = max(scored_n, 1)
    mean_candidates = (sum(candidate_counts) / len(candidate_counts)) if candidate_counts else 0.0
    return {
        "first_sorted_id_accuracy": first_hits / n,
        "lexical_overlap_accuracy": lex_hits / n,
        "chance": (1.0 / mean_candidates) if mean_candidates else 0.0,
        "n_scored": scored_n,
    }
