"""BTRR smoke/experiment runner: train -> freeze -> P0 -> R1-R12 -> score -> report.

Split into a torch-FREE scoring/report path (`assemble_report`, testable with gold predictions) and a
torch path (`generate_predictions`, `run_experiment`) that is lazy-imported and fail-closed on reserved
seeds. Enforces the single-checkpoint invariant: P0 and R1-R12 are evaluated on the byte-identical frozen
checkpoint with no optimizer step between them; if P0 is not established the R1-R12 results are stamped
NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION and excluded from the reasoning verdict.
"""
from __future__ import annotations

import json
import pathlib

from . import gates as G
from . import manifest as MAN
from . import metrics as M
from . import shortcuts as SC
from . import verdict as V
from .base_capability import p0_gate
from .config import MAX_SEQ_LEN, OUTPUT_MARKER, OUTPUT_TOKEN_LIMIT
from .eval import NON_ADMISSIBLE
from .execution import assert_generation_allowed
from .serializer import serialize_input
from .output import is_valid_output, parse_output, serialize_output


def _safe(text: str):
    try:
        return parse_output(text)
    except Exception:
        return None


def p0_accuracy(preds: list) -> float:
    if not preds:
        return 0.0
    ok = 0
    for ctx, text in preds:
        p = _safe(text); g = ctx.authoritative_output
        if p is not None and p.answer == g.answer and p.status == g.status:
            ok += 1
    return ok / len(preds)


def answer_accuracy(preds: list) -> float:
    if not preds:
        return 0.0
    ok = sum(1 for ctx, text in preds
             if (_safe(text) is not None and _safe(text).answer == ctx.authoritative_output.answer))
    return ok / len(preds)


def p0_failure_profile(preds: list) -> dict:
    """Categorize each P0 prediction (diagnostic; not a gate): invalid / abstained / copied_query_root /
    in_context_wrong (answer is some other visible id or token) / correct / other."""
    prof = {"correct": 0, "invalid": 0, "abstained": 0, "copied_query_root": 0, "in_context_wrong": 0,
            "other": 0}
    for ctx, text in preds:
        p = _safe(text); g = ctx.authoritative_output
        if p is None:
            prof["invalid"] += 1
        elif p.answer == g.answer and p.status == g.status:
            prof["correct"] += 1
        elif p.answer is None:
            prof["abstained"] += 1
        elif p.answer == ctx.query.root_entity_id:
            prof["copied_query_root"] += 1
        elif p.answer in set(serialize_input(ctx).replace("\n", " ").split(" ")):
            prof["in_context_wrong"] += 1
        else:
            prof["other"] += 1
    return prof


def assemble_report(*, seed: int, role: str, checkpoint_digest: str,
                    p0_predictions: dict, r_predictions: dict, protocol_valid: bool = True, arm: str = "ABS",
                    training: dict | None = None, environment: dict | None = None,
                    git_sha: str | None = None, replay_verified: bool | None = None) -> dict:
    """Score predictions into the full smoke report. Torch-free (works on any predicted-text source)."""
    p0_acc = {sub: p0_accuracy(preds) for sub, preds in p0_predictions.items()}
    p0_profile = {sub: p0_failure_profile(preds) for sub, preds in p0_predictions.items()}
    p0 = p0_gate(p0_acc)
    established = p0["established"]

    flat = [pair for preds in r_predictions.values() for pair in preds]
    m = M.compute(flat)
    per_split = {s: answer_accuracy(preds) for s, preds in r_predictions.items()}
    all_ctx = [ctx for preds in r_predictions.values() for ctx, _ in preds]

    suite = SC.run_suite(all_ctx, m.get("final_answer_accuracy", 0.0))
    le = SC.latest_event_effect(all_ctx, m.get("latest_event", 0.0))
    length = SC.length_shortcut_control(all_ctx)
    gres = G.evaluate_gates(m, per_split, latest_event_baseline=le["global_most_recent_baseline"])
    gg = gres["gates"]

    def passed(name: str) -> bool:
        x = gg.get(name)
        return bool(x and x.get("pass"))

    discovery_ok = passed("R4_path_discovery_multihop") and passed("R7_path_discovery_temporal")
    composite_ok = passed("R9_composite_final_answer") and passed("R9_full_chain_correct")

    vd = V.decide(protocol_valid=protocol_valid, base_capability_established=established,
                  shortcut_detected=suite["shortcut_detected"], resource_ok=True,
                  gates=gg, discovery_ok=discovery_ok, composite_ok=composite_ok)

    report = {
        "schema": "btrr/smoke_report/v1",
        "environment": environment, "git_sha": git_sha,
        "arm": arm, "arm_name": MAN.C.ARMS[arm]["name"], "arm_ratified": bool(MAN.C.ARMS[arm]["ratified"]),
        "seed": seed, "role": role, "checkpoint_digest": checkpoint_digest,
        "config_digest": MAN.config_digest(arm), "tokenizer_vocab_digest": MAN.tokenizer_vocab_digest(),
        "schema_serializer_version": MAN.SCHEMA_SERIALIZER_VERSION,
        "provenance": MAN.PROVENANCE,
        "training": training or {}, "protocol_valid": protocol_valid, "replay_verified": replay_verified,
        "p0": {"per_subtask": p0_acc, "gate": p0, "failure_profile": p0_profile},
        "reasoning_admissible": established,
        "structured_output_validity": m.get("structured_output_validity"),
        "per_split_answer_accuracy": per_split,
        "discovery": {"R4": per_split.get("R4"), "R7": per_split.get("R7"), "ok": discovery_ok},
        "r9": {"final_answer": per_split.get("R9"), "full_chain": m.get("r9_full_chain_correct"),
               "decomposition": m.get("r9_decomposition"), "ok": composite_ok},
        "R12_confusable": per_split.get("R12"),
        "latest_event": {"accuracy": m.get("latest_event"), **le},
        "policy_condition": m.get("policy_condition"),
        "evidence": {"precision": m.get("evidence_precision"), "recall": m.get("evidence_recall")},
        "abstention": m.get("abstention_accuracy"),
        "false_abstention_on_answerable": m.get("false_abstention_on_answerable"),
        "hallucination": {"entity": m.get("hallucinated_entity"), "relation": m.get("hallucinated_relation"),
                          "evidence": m.get("hallucinated_evidence")},
        "structure_blind_baselines": suite["baselines"], "shortcut_detected": suite["shortcut_detected"],
        "length_control": length,
        "gates": gg, "gates_all_pass": gres["all_pass"], "verdict": vd,
    }
    if not established:
        report["admissibility_stamp"] = NON_ADMISSIBLE
        report["note"] = ("P0 base capability not established -> R1-R12 results are "
                          "NON_ADMISSIBLE_FOR_REASONING_INTERPRETATION and excluded from the verdict")
    return report


def write_report(report: dict, out_dir: str | pathlib.Path) -> str:
    d = pathlib.Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"report_{report['role']}_{report['seed']}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return str(path)


# ---------------- torch path (lazy) ----------------

def generate_predictions(frozen, contexts, tokenizer=None) -> list:
    """Greedy-generate a structured-output string per context on the frozen checkpoint. Requires torch."""
    import torch
    from .tokenizer import BTRRTokenizer
    tok = tokenizer or BTRRTokenizer()
    model = frozen.model.eval()
    dev = getattr(frozen, "device", "cpu")
    from .serializer import serialize_input
    preds = []
    with torch.no_grad():
        for ctx in contexts:
            ids = tok.encode(serialize_input(ctx) + OUTPUT_MARKER, add_bos=True)
            gen: list[int] = []
            for _ in range(OUTPUT_TOKEN_LIMIT):
                nxt = int(model(torch.tensor([ids[-MAX_SEQ_LEN:]], device=dev))[0, -1].argmax())
                if nxt == tok.eos_id:
                    break
                gen.append(nxt); ids.append(nxt)
                if len(ids) >= MAX_SEQ_LEN:
                    break
            preds.append((ctx, tok.decode(gen)))
    return preds


def run_experiment(seed: int, *, role_train: str = "train", role_eval: str = "final",
                   authorization_token: str | None = None, n_train: int = 6, n_eval: int = 12,
                   max_updates: int | None = None, out_dir: str | None = None,
                   git_sha: str | None = None, arm: str = "ABS") -> dict:
    """Full train->freeze->P0->R1-R12->score->report for a seed. Fail-closed; requires torch.

    Guards BEFORE any torch import or cohort materialization. Reserved seeds run only with valid two-key
    authorization; fixture seeds (883000-883004) run ungated for implementation smoke of the pipeline.
    """
    assert_generation_allowed(seed, authorization_token)   # fail-closed before anything
    from .config import frozen_run_params
    n_train, max_updates = frozen_run_params(arm, seed, n_train, max_updates)   # admissibility, per arm
    import torch
    from . import dataset as DS
    from .replay import replay_matches
    from .tokenizer import BTRRTokenizer
    from .trainer import train_checkpoint

    tok = BTRRTokenizer()
    examples = (DS.build_examples(seed, n_train, role_train, authorization_token)
                + DS.build_p0_examples(seed, n_train, role_train, authorization_token))
    loss_log: list = []
    frozen = train_checkpoint(seed, examples, authorization_token=authorization_token,
                              max_updates=max_updates, loss_log=loss_log, arm=arm)
    d0 = frozen.digest()

    p0_cohorts = DS.eval_cohorts_p0(seed, n_eval, role_eval, authorization_token)
    p0_predictions = {sub: generate_predictions(frozen, ctxs, tok) for sub, ctxs in p0_cohorts.items()}
    assert frozen.digest() == d0, "checkpoint mutated during P0 evaluation"

    r_cohorts = DS.eval_cohorts_r(seed, n_eval, role_eval, authorization_token)
    r_predictions = {s: generate_predictions(frozen, ctxs, tok) for s, ctxs in r_cohorts.items()}
    assert frozen.digest() == d0, "checkpoint mutated during R1-R12 evaluation"

    # deterministic-replay integrity on the eval pool (uses the same authorization path)
    protocol_valid = all(replay_matches(s, seed, 0, role_eval) for s in ("R1", "R5", "R9"))

    env = {"torch": torch.__version__, "cuda": torch.cuda.is_available(),
           "device": (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")}
    report = assemble_report(seed=seed, role=_role_for(seed), checkpoint_digest=d0, arm=arm,
                             p0_predictions=p0_predictions, r_predictions=r_predictions,
                             protocol_valid=protocol_valid,
                             training={"completed": True, "max_updates": max_updates,
                                       "n_train_per_split": n_train, "n_eval_per_split": n_eval,
                                       "n_train_examples": len(examples),
                                       "loss_curve": [(s, round(l, 4)) for s, l in loss_log]},
                             environment=env, git_sha=git_sha, replay_verified=protocol_valid)
    if out_dir:
        report["report_path"] = write_report(report, out_dir)
        report["predictions_path"] = write_predictions(
            {**p0_predictions, **r_predictions}, out_dir, role=_role_for(seed), seed=seed)
    return report


def write_predictions(cohorts: dict, out_dir: str | pathlib.Path, *, role: str, seed: int) -> str:
    """One JSON line per evaluated example: split, query, gold, and the raw generated text (diagnostic)."""
    d = pathlib.Path(out_dir); d.mkdir(parents=True, exist_ok=True)
    path = d / f"predictions_{role}_{seed}.jsonl"
    with path.open("w") as fh:
        for key, preds in cohorts.items():
            for ctx, text in preds:
                fh.write(json.dumps({"cohort": key, "split": ctx.split, "context_id": ctx.context_id,
                                     "query_root": ctx.query.root_entity_id,
                                     "gold": serialize_output(ctx.authoritative_output),
                                     "pred": text, "valid": is_valid_output(text)}) + "\n")
    return str(path)


def overfit_diagnostic(*, seed: int = 883000, per_split: int = 2, updates: int = 4000,
                       role: str = "unit", arm: str = "ABS") -> dict:
    """Learnability check (FIXTURES ONLY): train on a tiny set and evaluate on the SAME episodes.

    Decides bug-vs-scale for a 0.0-validity smoke. If eval-on-train structured validity climbs toward 1.0,
    the train+generate machinery works and low held-out performance is scale/task-difficulty (scale up for
    dev/final). If it stays ~0, there is a generation/training defect to fix before any evidence run.
    Uses only fixture seeds (ungated); consumes no reserved scientific seed.
    """
    assert_generation_allowed(seed)  # fixture -> ungated; reserved seeds still raise here
    from . import dataset as DS
    from .base_capability import P0_SUBTASKS, generate_p0
    from .generator import generate_split
    from .output import is_valid_output
    from .tokenizer import BTRRTokenizer
    from .trainer import train_checkpoint

    tok = BTRRTokenizer()
    r_cohorts = {s: list(generate_split(s, seed, per_split, role)) for s in ("R1", "R2", "R5", "R8")}
    p0_cohorts = {sub: list(generate_p0(sub, seed, 1, role)) for sub in P0_SUBTASKS}
    examples = ([DS.example_from_ctx(c) for cs in r_cohorts.values() for c in cs]
                + [DS.example_from_ctx(c) for cs in p0_cohorts.values() for c in cs])
    frozen = train_checkpoint(seed, examples, max_updates=updates, arm=arm)

    r_ctx = [c for cs in r_cohorts.values() for c in cs]
    p0_ctx = [c for cs in p0_cohorts.values() for c in cs]
    r_preds = generate_predictions(frozen, r_ctx, tok)
    p0_preds = generate_predictions(frozen, p0_ctx, tok)
    allp = r_preds + p0_preds
    return {
        "mode": "eval_on_train (memorization/learnability)", "arm": arm,
        "seed": seed, "n_train_examples": len(examples), "updates": updates,
        "structured_output_validity": sum(is_valid_output(t) for _, t in allp) / len(allp),
        "answer_accuracy": answer_accuracy(r_preds),
        "p0_answer_accuracy": answer_accuracy(p0_preds),
        "checkpoint_digest": frozen.digest(),
        "interpretation": ("validity -> ~1.0 means train+generate works (0.0 held-out is scale/difficulty); "
                           "validity stuck ~0 means a generation/training defect to fix before dev/final"),
    }


def _role_for(seed: int) -> str:
    from .config import arm_of_seed
    owner = arm_of_seed(seed)
    return owner[1] if owner is not None else "fixture"
