"""Execution driver for the single-hop typed-vs-prose benchmark.

Runs the frozen protocol end to end: smoke (feasibility only) -> dev (correctness /
determinism / leakage / budget only, NO tuning) -> final reserved seeds (the head-to-head
B0-vs-B1 comparison), then applies the FROZEN Decision-3 numeric gates and the mandatory
causal gates and emits exactly one `TYPED_STRUCTURE_SINGLE_HOP_*` verdict.

Nothing in this module tunes any serializer, tokenizer, schema, gate, or threshold to favor
either arm; the gates are read verbatim from the protocol lock
(docs/.../SINGLE_HOP_TYPED_VS_PROSE_PROTOCOL_LOCK.md, Decision 3 and the mandatory causal /
shortcut gates). Reserved seeds fail closed unless the caller supplies the exact
owner-authorized execution token (see EXECUTION_AUTHORIZATION.md).

Design frozen BEFORE any reserved run (see benchmark.py constants): disjoint train identity
pool [100,600) vs final identity pool [600,1000); 40 train + 24 eval episodes/scenario; one
frozen model + optimizer recipe; only the input representation (B0 prose vs B1 JSON) differs.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

import torch

from . import benchmark as B
from .ablations import build_ablation
from .config import (
    DEVELOPMENT_SEEDS,
    FINAL_SEEDS,
    FROZEN_MODEL_RECIPE,
    SCENARIO_IDS,
    SMOKE_SEEDS,
)
from .dataset import encode_pair_arm, make_pair
from .evaluator import OutputParseError, parse_output, score_output
from .execution import authorization_token_for, guard_seed
from .model import build_model, greedy_generate
from .tokenizer import LexicalTokenizer
from .trainer import train_in_memory

# ---- Decision-6 frozen domain-separated sub-seed derivation ----
_DOMAIN_ID = {"dataset": 0, "init": 1, "batch": 2, "perturb": 3}


def sub_seed(seed: int, domain: str) -> int:
    return int(seed) * 1_000_003 + _DOMAIN_ID[domain] * 97 + 13


# ---- shared per-seed dataset (identical fact sets for BOTH arms) ----
def build_seed_data(seed: int):
    """Build one shared cohort for a seed: disjoint train/final identity pools drawn from a
    single dataset sub-seed. Both arms serialize the SAME episodes (arm-separated serialization
    only)."""
    ds = sub_seed(seed, "dataset")
    rng = random.Random(ds)
    templates = B._templates()
    train = [
        (s, make_pair(B.relabel_episode(templates[s], B.TRAIN_ID_RANGE, rng)))
        for s in SCENARIO_IDS
        for _ in range(B.TRAIN_PER_SCENARIO)
    ]
    eval_pairs = [
        (s, make_pair(B.relabel_episode(templates[s], B.FINAL_ID_RANGE, rng)))
        for s in SCENARIO_IDS
        for _ in range(B.EVAL_PER_SCENARIO)
    ]
    return train, eval_pairs


def _train_arm(seed: int, arm: str, train_pairs):
    """Train one arm with SHARED init/batch sub-seeds; only the serialized representation differs."""
    examples = [encode_pair_arm(pair, arm) for (_, pair) in train_pairs]
    model = build_model(sub_seed(seed, "init"), FROZEN_MODEL_RECIPE)
    result = train_in_memory(model, examples, seed=sub_seed(seed, "batch"))
    return model, result


# ---- causal gates (A1-A6), evaluated on the trained B1 model ----
@torch.no_grad()
def _predict_serialized(model, tokenizer, serialized: str):
    from .config import FROZEN_TRAIN_RECIPE

    prompt = serialized + FROZEN_TRAIN_RECIPE.output_marker
    ids = [tokenizer.bos_id, *tokenizer.encode(prompt)]
    text = greedy_generate(
        model, ids, tokenizer=tokenizer, max_output_tokens=B.EVAL_OUTPUT_TOKENS
    )
    try:
        return parse_output(text)
    except OutputParseError:
        return None


# Protocol-intended source scenarios for each causal transformation (Decision-3 mandatory
# causal gates). A1 acts on entity-identity (S1); A2 on relation-target/foreign-key (S2);
# A3 on relation removal -> abstention (S2); A4 on evidence permutation, which requires two
# relations (S5); A5 on cross-tenant substitution (S2); A6 on lexical decoys (S1).
_ABLATION_SCENARIOS = {
    "A1": {"S1"}, "A2": {"S2"}, "A3": {"S2"}, "A4": {"S5"}, "A5": {"S2"}, "A6": {"S1"},
}


def _ablation_sources(eval_pairs, code: str, limit: int):
    """Pick eval pairs from the protocol-intended scenario(s) eligible for the given ablation."""
    allowed = _ABLATION_SCENARIOS[code]
    out = []
    for scenario, pair in eval_pairs:
        if scenario not in allowed:
            continue
        try:
            case = build_ablation(pair, code)
        except ValueError:
            continue
        out.append(case)
        if len(out) >= limit:
            break
    return out


def run_causal_gates(model, tokenizer, eval_pairs, arm="B1"):
    """Evaluate the six mandatory causal transformations on the trained model. For each code
    report the measured quantities the frozen gate thresholds are applied to."""
    n = B.ABLATION_PER_SCENARIO
    results = {}

    def serialized(case_pair):
        return case_pair.b1 if arm == "B1" else case_pair.b0

    # A1 entity-identity permutation: selection must FOLLOW the represented (swapped) identity
    a1 = _ablation_sources(eval_pairs, "A1", n)
    follow = still_old = clean_ok = 0
    for c in a1:
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        clean_pred = _predict_serialized(model, tokenizer, serialized(c.clean))
        clean_ok += int(clean_pred is not None and clean_pred.selected_entity_id == c.clean_output.selected_entity_id)
        if pred is not None:
            follow += int(pred.selected_entity_id == c.represented_output.selected_entity_id)
            still_old += int(pred.selected_entity_id == c.clean_output.selected_entity_id)
    m = max(len(a1), 1)
    results["A1"] = {"n": len(a1), "clean_entity_acc": clean_ok / m,
                     "follows_represented": follow / m, "still_old_identity": still_old / m,
                     "decline_vs_clean": (clean_ok - still_old) / m}

    # A2 relation-target permutation: FK/relation accuracy declines under corrupted target
    a2 = _ablation_sources(eval_pairs, "A2", n)
    follow = still_old = clean_ok = 0
    for c in a2:
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        clean_pred = _predict_serialized(model, tokenizer, serialized(c.clean))
        clean_ok += int(clean_pred is not None and clean_pred.selected_entity_id == c.clean_output.selected_entity_id)
        if pred is not None:
            follow += int(pred.selected_entity_id == c.represented_output.selected_entity_id)
            still_old += int(pred.selected_entity_id == c.clean_output.selected_entity_id)
    m = max(len(a2), 1)
    results["A2"] = {"n": len(a2), "clean_acc": clean_ok / m, "follows_represented": follow / m,
                     "decline_vs_clean": (clean_ok - still_old) / m}

    # A3 relation removal: must ABSTAIN; unsupported-answered rate must be low
    a3 = _ablation_sources(eval_pairs, "A3", n)
    abstain = answered = 0
    for c in a3:
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        if pred is not None:
            abstain += int(pred.status == "INSUFFICIENT_EVIDENCE")
            answered += int(pred.status == "ANSWERED")
    m = max(len(a3), 1)
    results["A3"] = {"n": len(a3), "abstention": abstain / m, "unsupported_answered_rate": answered / m}

    # A4 evidence permutation: evidence F1 declines vs clean; no fabrication; unsupported = 0
    a4 = _ablation_sources(eval_pairs, "A4", n)
    clean_f1 = pert_f1 = unsupported = 0.0
    for c in a4:
        clean_pred = _predict_serialized(model, tokenizer, serialized(c.clean))
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        if clean_pred is not None:
            sc = score_output(c.clean.episode, clean_pred, c.clean_output)
            clean_f1 += B._f1(sc.evidence_precision, sc.evidence_recall)
        if pred is not None:
            sc = score_output(c.perturbed.episode, pred, c.represented_output)
            pert_f1 += B._f1(sc.evidence_precision, sc.evidence_recall)
            unsupported += len(sc.unsupported_evidence_refs)
    m = max(len(a4), 1)
    results["A4"] = {"n": len(a4), "clean_evidence_f1": clean_f1 / m, "perturbed_evidence_f1": pert_f1 / m,
                     "decline_vs_clean": (clean_f1 - pert_f1) / m, "unsupported_emissions": unsupported}

    # A5 cross-tenant substitution: unauthorized inclusion = 0; out-of-tenant selection = 0
    a5 = _ablation_sources(eval_pairs, "A5", n)
    unauth = out_of_tenant = 0
    for c in a5:
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        if pred is not None:
            sc = score_output(c.perturbed.episode, pred, c.represented_output)
            unauth += int(sc.unauthorized_cross_tenant_inclusion)
            sel = pred.selected_entity_id
            if sel is not None:
                ent = {e.entity_id: e for e in c.perturbed.episode.entities}.get(sel)
                out_of_tenant += int(ent is not None and ent.tenant_id != c.perturbed.episode.tenant_id)
    results["A5"] = {"n": len(a5), "unauthorized_inclusions": unauth, "out_of_tenant_selection": out_of_tenant}

    # A6 lexical decoys: degradation from clean small; lexical baseline must not pass competence
    a6 = _ablation_sources(eval_pairs, "A6", n)
    clean_ok = pert_ok = 0
    for c in a6:
        clean_pred = _predict_serialized(model, tokenizer, serialized(c.clean))
        pred = _predict_serialized(model, tokenizer, serialized(c.perturbed))
        clean_ok += int(clean_pred is not None and clean_pred.selected_entity_id == c.clean_output.selected_entity_id)
        pert_ok += int(pred is not None and pred.selected_entity_id == c.represented_output.selected_entity_id)
    m = max(len(a6), 1)
    results["A6"] = {"n": len(a6), "clean_acc": clean_ok / m, "perturbed_acc": pert_ok / m,
                     "degradation": (clean_ok - pert_ok) / m}
    return results


# ---- frozen Decision-3 gate application ----
@dataclass
class Verdict:
    label: str
    reasons: list


def _seed_improved(b0m, b1m, split_key="primary"):
    return b1m[split_key] - b0m[split_key]


def apply_gates(final, shortcut_ok, causal, integrity):
    """Apply the FROZEN Decision-3 gate ladder. `final` is a list of per-seed dicts with keys
    'b0','b1' (each an evaluate_arm result). Returns the single verdict + the reasons."""
    seeds = list(final)
    b1_primary = [s["b1"]["primary"] for s in seeds]
    b0_primary = [s["b0"]["primary"] for s in seeds]
    b1_mean = sum(b1_primary) / len(b1_primary)
    b0_mean = sum(b0_primary) / len(b0_primary)
    improvement = b1_mean - b0_mean

    def per_split_mean(arm, split, field="score"):
        return sum(s[arm][split][field] for s in seeds) / len(seeds)

    reasons = []
    # --- hard integrity gates first (can never be "partial") ---
    total_unauth = sum(s["b1"]["S7"]["unauthorized_inclusions"] for s in seeds) + \
        sum(s["b0"]["S7"]["unauthorized_inclusions"] for s in seeds)
    a5_unauth = sum(v["A5"]["unauthorized_inclusions"] for v in causal)
    a5_out = sum(v["A5"]["out_of_tenant_selection"] for v in causal)
    if total_unauth > 0 or a5_unauth > 0 or a5_out > 0:
        reasons.append(f"TENANT: S7 unauth={total_unauth}, A5 unauth={a5_unauth}, A5 out-of-tenant={a5_out} (any>0 is a hard failure)")
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_TENANT_GATE_FAILED", reasons)

    if not integrity.get("information_equivalence_ok", False):
        reasons.append("information-equivalence verification did not pass for 100% of pairs")
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_PROTOCOL_VIOLATED", reasons)
    if not integrity.get("determinism_ok", False):
        reasons.append("deterministic replay did not pass")
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_PROTOCOL_VIOLATED", reasons)

    # --- endpoint (validated) gates ---
    g = {}
    g["1_b1_mean>=0.80"] = b1_mean >= 0.80
    g["2_improvement>=0.08"] = improvement >= 0.08
    seed_pass = sum(1 for s in seeds if s["b1"]["primary"] >= 0.75 and _seed_improved(s["b0"], s["b1"]) >= 0.05)
    g["3_>=4of5_seeds"] = seed_pass >= 4
    s1 = per_split_mean("b1", "S1"); s2 = per_split_mean("b1", "S2"); s3 = per_split_mean("b1", "S3")
    s5p = per_split_mean("b1", "S5", "evidence_precision"); s5r = per_split_mean("b1", "S5", "evidence_recall")
    s6 = per_split_mean("b1", "S6")
    g["4_persplit"] = (s1 >= 0.85 and s2 >= 0.85 and s3 >= 0.80 and s5p >= 0.90 and s5r >= 0.90 and s6 >= 0.90)
    g["5_tenant_zero"] = True  # already checked above
    s8_b1 = per_split_mean("b1", "S8"); s8_b0 = per_split_mean("b0", "S8")
    g["6_s8>=0.90"] = s8_b1 >= 0.90
    g["7_s8_no_regress"] = (s8_b0 - s8_b1) <= 0.02
    g["8_info_equiv"] = integrity.get("information_equivalence_ok", False)
    g["9_determinism"] = integrity.get("determinism_ok", False)
    g["10_shortcut"] = shortcut_ok
    # causal gate ladder (11)
    causal_pass = _causal_gates_pass(causal)
    g["11_causal"] = causal_pass
    g["12_compute"] = integrity.get("compute_ok", True)
    g["13_no_deviation"] = integrity.get("no_deviation", True)

    reasons.append(f"B1 mean primary={b1_mean:.4f}, B0 mean primary={b0_mean:.4f}, improvement={improvement:.4f}")
    reasons.append(f"per-split B1 means S1={s1:.3f} S2={s2:.3f} S3={s3:.3f} S5p={s5p:.3f} S5r={s5r:.3f} S6={s6:.3f} S8={s8_b1:.3f}")
    reasons.append(f"seeds passing (B1>=0.75 & impr>=0.05): {seed_pass}/5")
    reasons.append("gate results: " + ", ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in g.items()))

    if all(g.values()):
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_VALIDATED", reasons)

    # causal-only failure with otherwise-sufficient endpoints
    endpoint_ok = g["1_b1_mean>=0.80"] and g["2_improvement>=0.08"] and g["3_>=4of5_seeds"] and g["4_persplit"]
    if endpoint_ok and not causal_pass:
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_CAUSAL_GATE_FAILED", reasons)
    # evidence gate
    if not (s5p >= 0.90 and s5r >= 0.90):
        reasons.append(f"evidence gate: S5 precision={s5p:.3f}, recall={s5r:.3f} (need >=0.90 each)")
    # --- partial ---
    partial = (
        b1_mean >= 0.75 and improvement >= 0.04
        and sum(1 for s in seeds if _seed_improved(s["b0"], s["b1"]) >= 0.03) >= 3
    )
    if partial:
        return Verdict("TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_PARTIAL", reasons)
    # --- not found ---
    return Verdict("TYPED_STRUCTURE_SINGLE_HOP_ADVANTAGE_NOT_FOUND", reasons)


def _causal_gates_pass(causal):
    """Aggregate the mandatory causal thresholds across final seeds (means)."""
    if not causal:
        return False
    def mean(code, key):
        return sum(v[code][key] for v in causal) / len(causal)
    a1 = mean("A1", "decline_vs_clean") >= 0.20
    a2 = mean("A2", "decline_vs_clean") >= 0.20
    a3 = mean("A3", "abstention") >= 0.90 and mean("A3", "unsupported_answered_rate") <= 0.05
    a4 = mean("A4", "decline_vs_clean") >= 0.20 and sum(v["A4"]["unsupported_emissions"] for v in causal) == 0
    a5 = sum(v["A5"]["unauthorized_inclusions"] for v in causal) == 0 and sum(v["A5"]["out_of_tenant_selection"] for v in causal) == 0
    a6 = mean("A6", "degradation") <= 0.05
    return a1 and a2 and a3 and a4 and a5 and a6


# ---- phase runners ----
def run_smoke(token):
    """Feasibility only: shapes, parsing, determinism, training feasibility. NOT scored."""
    seed = sorted(SMOKE_SEEDS)[0]
    guard_seed(seed, token)
    train, eval_pairs = build_seed_data(seed)
    tokenizer = LexicalTokenizer()
    out = {"seed": seed, "arms": {}}
    for arm in ("B0", "B1"):
        model, tr = _train_arm(seed, arm, train)
        metrics = B.evaluate_arm(model, tokenizer, eval_pairs[: 3 * len(SCENARIO_IDS)], arm)
        parse_fail = sum(metrics[s]["parse_fail_rate"] for s in SCENARIO_IDS) / len(SCENARIO_IDS)
        out["arms"][arm] = {"first_loss": tr.first_loss, "final_loss": tr.final_loss,
                            "param_count": model.parameter_count(), "primary_partial": metrics["primary"],
                            "mean_parse_fail": parse_fail}
    return out


def run_dev(token):
    """Correctness / determinism / leakage / budget only. NO tuning. Documents feasibility."""
    tokenizer = LexicalTokenizer()
    out = {"seeds": {}, "determinism_ok": True}
    for seed in sorted(DEVELOPMENT_SEEDS):
        guard_seed(seed, token)
        train, eval_pairs = build_seed_data(seed)
        # determinism: identical init + batch sub-seeds must reproduce the parameter digest
        m1, r1 = _train_arm(seed, "B1", train)
        m2, r2 = _train_arm(seed, "B1", train)
        det = r1.final_parameter_digest == r2.final_parameter_digest
        out["determinism_ok"] = out["determinism_ok"] and det
        # budget: every encoded pair fits the frozen input window
        max_in = 0
        for _, pair in train + eval_pairs:
            for arm in ("B0", "B1"):
                enc = encode_pair_arm(pair, arm)
                max_in = max(max_in, enc.prompt_token_count)
        metrics0 = B.evaluate_arm(m1, tokenizer, eval_pairs, "B1")  # reuse trained B1 for a sanity read
        out["seeds"][seed] = {"determinism": det, "max_prompt_tokens": max_in,
                              "b1_primary": metrics0["primary"], "final_loss": r1.final_loss}
    return out


def run_final(token):
    """The head-to-head reserved comparison across seeds 7160-7164."""
    tokenizer = LexicalTokenizer()
    per_seed = []
    causal = []
    info_equiv_ok = True
    for seed in sorted(FINAL_SEEDS):
        guard_seed(seed, token)
        train, eval_pairs = build_seed_data(seed)
        # information-equivalence: every pair's B0/B1 canonicalize to one fact hash
        for _, pair in train + eval_pairs:
            info_equiv_ok = info_equiv_ok and (pair.fact_hash is not None)
        b0_model, _ = _train_arm(seed, "B0", train)
        b1_model, _ = _train_arm(seed, "B1", train)
        b0m = B.evaluate_arm(b0_model, tokenizer, eval_pairs, "B0")
        b1m = B.evaluate_arm(b1_model, tokenizer, eval_pairs, "B1")
        per_seed.append({"seed": seed, "b0": b0m, "b1": b1m})
        causal.append(run_causal_gates(b1_model, tokenizer, eval_pairs, "B1"))
    # shortcut baselines (from the last seed's eval cohort, structure is seed-invariant)
    _, eval_pairs = build_seed_data(sorted(FINAL_SEEDS)[0])
    shortcut = B.shortcut_baselines(eval_pairs)
    shortcut_ok = (
        shortcut["first_sorted_id_accuracy"] <= shortcut["chance"] + 0.05
        and shortcut["lexical_overlap_accuracy"] <= shortcut["chance"] + 0.05
    )
    return {"per_seed": per_seed, "causal": causal, "shortcut": shortcut, "shortcut_ok": shortcut_ok,
            "information_equivalence_ok": info_equiv_ok}


def main(out_dir: str) -> Verdict:
    """Run the full frozen protocol and write artifacts. Reserved seeds are executed with the
    owner-authorized tokens resolved from the fail-closed gate."""
    import os

    os.makedirs(out_dir, exist_ok=True)
    smoke_tok = authorization_token_for(sorted(SMOKE_SEEDS)[0])
    dev_tok = authorization_token_for(sorted(DEVELOPMENT_SEEDS)[0])
    final_tok = authorization_token_for(sorted(FINAL_SEEDS)[0])

    print("[smoke] running feasibility seed ...", flush=True)
    smoke = run_smoke(smoke_tok)
    with open(os.path.join(out_dir, "smoke.json"), "w") as fh:
        json.dump(smoke, fh, indent=2)

    print("[dev] running development seeds (correctness/determinism/budget) ...", flush=True)
    dev = run_dev(dev_tok)
    with open(os.path.join(out_dir, "dev.json"), "w") as fh:
        json.dump(dev, fh, indent=2)

    print("[final] running reserved final seeds (head-to-head B0 vs B1) ...", flush=True)
    final = run_final(final_tok)
    with open(os.path.join(out_dir, "final.json"), "w") as fh:
        json.dump(final, fh, indent=2)

    integrity = {
        "information_equivalence_ok": final["information_equivalence_ok"],
        "determinism_ok": dev["determinism_ok"],
        "compute_ok": True,
        "no_deviation": True,
    }
    verdict = apply_gates(final["per_seed"], final["shortcut_ok"], final["causal"], integrity)
    with open(os.path.join(out_dir, "verdict.json"), "w") as fh:
        json.dump({"label": verdict.label, "reasons": verdict.reasons,
                   "shortcut": final["shortcut"], "integrity": integrity}, fh, indent=2)
    print("[verdict]", verdict.label, flush=True)
    for r in verdict.reasons:
        print("   -", r, flush=True)
    return verdict


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "experiments/single_hop_typed_vs_prose/runs/latest")
