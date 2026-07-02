"""Track G smoke scorer (Mistral) — RUNS ON RUNPOD/LOCAL-GPU ONLY.

Adds the missing scorer step to Track G: it emits the leak-scanned polarity packets (arms
A/R/B/I/X/D), runs the APPROVED scorer model over them (JSON-only, temp 0), ingests the scores into
`track_g_harness`, and writes `track_g_smoke_outputs.json` + `TRACK_G_SMOKE_RESULT.md` with one of
the 8 allowed labels. It makes NO model call in dry-run/gate paths and is NOT runnable from the
firewalled build sandbox. Nothing here fabricates scores.

Gate: refuses unless env `TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE` AND a valid separate
approved run config (base smoke manifest stays run_enabled:false / NOT_APPROVED, never edited).
`A_vs_R` (does sign matter) and `A_vs_X` (incremental over context) are co-primary. The varṇa
polarity table is researcher-authored / high-DOF, so a positive is architecture-bound utility only,
never ontology. Track B stays BLOCKED. Honest prior: NEGATIVE — the derived A vectors mostly do not
match the pre-registered poles, so RANDOM_POLARITY_EXPLAINS / CONTEXT_ONLY_EXPLAINS / NO_SIGNAL are
the expected outcomes.

Usage on the pod:
    export TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE
    python3 experiments/primitive_sequence_recovery/run_track_g_smoke_mistral.py --dry-check
    python3 experiments/primitive_sequence_recovery/run_track_g_smoke_mistral.py \
        --approval-config experiments/primitive_sequence_recovery/track_g_smoke_approved_run_config.json \
        --judge-mode single
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import track_g_smoke_runner as GR   # gates, dry_run, build_packets, load_bundle, RefusedRun
import track_g_harness as HG        # arm_metrics, deltas, decide, labels, _posthoc_invalid

ARMS = HG.ARMS_REQUIRED
DEFAULT_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
TEMPERATURE = 0.0
MAX_NEW_TOKENS = 256
MALFORMED_ABORT_RATE = 0.15
OUTPUTS_JSON = HERE / "track_g_smoke_outputs.json"
RESULT_MD = HERE / "TRACK_G_SMOKE_RESULT.md"
DEBUG_DUMP = HERE / "track_g_smoke_malformed_debug.jsonl"   # diagnostic only; gitignored, not committed

SCORER_INSTRUCTIONS = ('For each candidate meaning, output a score in [0,1] for how well it fits the '
                       'premise. Respond with JSON ONLY, no prose: {"packet_id": "<id>", "scores": '
                       '{"opt_1": 0.0, ...}, "chosen": "opt_k"}.')


# ---------------------------------------------------------------- scorer prompt -----
def _prompt(packet):
    # single user turn (Mistral-safe); packet is already anonymized/leak-scanned by the runner.
    opts = [c["candidate_id"] for c in packet["candidates"]]
    lines = [f'  {c["candidate_id"]}: {c["gloss"]}' for c in packet["candidates"]]
    user = ("You are a careful annotator. Output exactly one JSON object, no prose.\n\n"
            + packet["premise"] + "\n\nCANDIDATES:\n" + "\n".join(lines) +
            f'\n\nReturn JSON ONLY. "scores" must be a JSON object keyed by the option id '
            f'(an object like {{"opt_1": 0.7, ...}}, NOT an array), with keys exactly {opts}. '
            f'Also include "packet_id" ("{packet["packet_id"]}") and "chosen" (one of {opts}).')
    return [{"role": "user", "content": user}]


def _coerce_score(v):
    """Coerce one score to a finite float in [0,1]; raise ValueError otherwise. Accepts a real
    number or a numeric string it happened to quote (e.g. "0.4"); rejects bools, non-numeric
    strings, and NaN/inf. Never invents a value."""
    if isinstance(v, bool):
        raise ValueError(f"boolean is not a score: {v!r}")
    if isinstance(v, str):
        try:
            v = float(v.strip())
        except ValueError:
            raise ValueError(f"non-numeric score string {v!r}")
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"non-finite/non-numeric score {v!r}")
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"out-of-range score {v!r}")
    return float(v)


def _normalize_scores(scores, opts):
    """Return {opt: float} for opts. Accepts `scores` as EITHER a keyed object with the exact opt
    keys, OR a positional list/tuple of the same length mapped in packet-option order to
    opt_1..opt_N. Strict: no extra/missing keys, no wrong-length arrays, no invented values.
    Raises ValueError on any shape/length/key/type mismatch."""
    if isinstance(scores, dict):
        if set(scores) != set(opts):
            raise ValueError("scores keys must equal packet opts")
        return {o: _coerce_score(scores[o]) for o in opts}
    if isinstance(scores, (list, tuple)):
        if len(scores) != len(opts):
            raise ValueError(f"positional scores length {len(scores)} != {len(opts)} opts")
        return {o: _coerce_score(scores[i]) for i, o in enumerate(opts)}
    raise ValueError("scores must be an object keyed by option id or a positional array")


def parse_scorer_json(text, opts):
    """Validate one scorer output. Accepts `scores` as a keyed object OR a positional array of the
    same length (mapped in packet-option order to opt_1..opt_N); coerces quoted numbers. Strict
    AFTER normalization: every opt present exactly once, numeric & finite & in range, `chosen` a
    valid opt (else argmax). Contamination scan preserved. Reads only what the model returned; never
    invents a score. Raises ValueError on any malformed/contaminated content."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object")
    obj = json.loads(m.group(0))
    scores = _normalize_scores(obj.get("scores"), opts)
    chosen = obj.get("chosen") if obj.get("chosen") in set(opts) else max(scores, key=scores.get)
    for s in (str(v) for v in obj.values() if isinstance(v, str)):
        low = s.lower()
        if any(b.lower() in low for b in HG.BANNED_REAL + HG.FORBIDDEN_LABELS) or "sphere" in low:
            raise ValueError(f"contamination text: {s!r}")
    return {"scores": scores, "chosen": chosen}


def score_packets(packets, hidden, generate_fn, debug_records=None):
    """Run each packet through generate_fn + parse_scorer_json. PURE w.r.t. scoring semantics:
    returns (scores_by_pid, malformed_count) identically whether or not debug_records is passed.
    If debug_records is a list, append one diagnostic record per MALFORMED generation only —
    this is observability, it does not alter scores, the malformed count, labels, assembly, or the
    frozen polarity. generate_fn(packet) -> raw model text (injected so this is model-agnostic)."""
    scores_by_pid, malformed = {}, 0
    for p in packets:
        opts = [c["candidate_id"] for c in p["candidates"]]
        raw = ""
        try:
            raw = generate_fn(p)
            scores_by_pid[p["packet_id"]] = parse_scorer_json(raw, opts)["scores"]
        except Exception as e:                        # malformed / contaminated -> counted, captured
            malformed += 1
            if debug_records is not None:
                h = hidden.get(p["packet_id"], {})
                err = f"{type(e).__name__}: {e}"
                debug_records.append({
                    "packet_id": p["packet_id"], "case_id": h.get("case_id"),
                    "arm": h.get("true_arm"), "n_opts": len(opts),
                    "parser_error": err,
                    "contamination_detected": "contamination" in err.lower(),
                    "raw_text": raw[:2000]})
    return scores_by_pid, malformed


# ---------------------------------------------------------- assemble + label --------
def assemble_and_score(bundle, hidden, scores_by_pid, malformed=0, malformed_rate=0.0):
    """PURE (no model): reassemble per-case arm scores, apply the frozen-polarity gate, reuse the
    Track G harness for metrics + one of the 8 allowed labels. Returns the result dict."""
    # frozen-polarity gate: any post-hoc/non-frozen assignment invalidates the run
    for cid, a in bundle["assignments"].items():
        if HG._posthoc_invalid(a):
            return _result("INVALID_POSTHOC_POLARITY", None, None, 0, list(bundle["assignments"]),
                           malformed, malformed_rate,
                           note="a polarity assignment was not frozen/assigned_before_scoring")
    by_case = {}
    for pid, scores in scores_by_pid.items():
        h = hidden[pid]
        cand_scores = {h["opt_to_cand"][opt]: v for opt, v in scores.items()}
        d = by_case.setdefault(h["case_id"], {})
        if h["true_arm"] == "I":                        # arm I = max over Barnum variants
            agg = d.setdefault("I", {})
            for c, v in cand_scores.items():
                agg[c] = max(agg.get(c, 0.0), v)
        else:
            d[h["true_arm"]] = cand_scores
    items, dropped = [], []
    for cid, cand_rec in bundle["candidates"].items():
        d = by_case.get(cid, {})
        if not all(a in d for a in ARMS):
            dropped.append(cid); continue
        cids = [c["candidate_id"] for c in cand_rec["candidates"]]
        items.append({"candidates": [{"candidate_id": c} for c in cids],
                      "target": cand_rec["target"], "arm_scores": d})
    if not items:
        return _result("INCONCLUSIVE", None, None, 0, dropped, malformed, malformed_rate,
                       note="no complete cases after dropping malformed packets")
    metrics = HG.arm_metrics(items)
    label = HG.decide(metrics)
    assert label in HG.ALLOWED_LABELS and label not in HG.FORBIDDEN_LABELS, label
    per_mrr = {a: round(metrics[a]["mrr"], 4) for a in ARMS}
    per_top1 = {a: round(metrics[a]["top1"], 4) for a in ARMS}
    return _result(label, per_mrr, per_top1, len(items), dropped, malformed, malformed_rate,
                   deltas={k: round(v, 4) for k, v in HG.deltas(metrics).items()})


def _result(label, per_mrr, per_top1, n_judged, dropped, malformed, rate, deltas=None, note=""):
    return {"artifact": "track_g_smoke_outputs", "exploratory_triage_only": True,
            "primary_label": label, "deltas": deltas, "per_arm_mrr": per_mrr, "per_arm_top1": per_top1,
            "A_vs_R_and_A_vs_X_are_co_primary": True,
            "tasks_judged": n_judged, "tasks_dropped_by_judge": dropped,
            "malformed": malformed, "malformed_rate": round(rate, 4),
            "polarity_derived_from_varna_table": True,
            "note": (note or ("Track G polarity-boundary smoke, exploratory triage only. A derived "
                     "from a researcher-authored high-DOF varṇa table -> even a positive is "
                     "architecture-bound utility, never ontology. Not validation; Track B remains "
                     "blocked. No ONTOLOGICAL_SIGNAL, no Sanskrit privilege."))}


def _write(result, model_id):
    OUTPUTS_JSON.write_text(json.dumps({**result, "scorer_model": model_id, "temperature": TEMPERATURE},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULT_MD.write_text(
        "# Track G Smoke — Result (exploratory triage only)\n\n"
        f"- scorer_model: `{model_id}` | temp {TEMPERATURE}\n"
        f"- primary_label: `{result['primary_label']}`\n"
        f"- deltas (A_vs_R & A_vs_X co-primary): {result['deltas']}\n"
        f"- per_arm_mrr: {result['per_arm_mrr']}\n"
        f"- per_arm_top1: {result['per_arm_top1']}\n"
        f"- tasks_judged: {result['tasks_judged']} | dropped: {result['tasks_dropped_by_judge']} | "
        f"malformed_rate: {result['malformed_rate']}\n\n"
        "Track G polarity-boundary smoke, exploratory triage only. A is varṇa-table-derived "
        "(researcher-authored, high-DOF). Not validation, no varṇa truth. Track B remains blocked. "
        "Structure, not validated meaning.\n", encoding="utf-8")


# ------------------------------------------------------------------- model ----------
def _load_model(model_id):
    import torch  # noqa: F401  (pod-only heavy import)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto", device_map="auto")
    model.eval()
    return model, tok


def _generate(model, tok, messages):
    import torch
    prompt = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    enc = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                             pad_token_id=(tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id))
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


def main():
    global TEMPERATURE, MAX_NEW_TOKENS
    ap = argparse.ArgumentParser()
    ap.add_argument("--approval-config", default=None)
    ap.add_argument("--dry-check", action="store_true")
    ap.add_argument("--judge-mode", choices=["single"], default="single",
                    help="Track G scoring is candidate-ranking by a single scorer model")
    ap.add_argument("--model-id", default=None)
    ap.add_argument("--max-new-tokens", type=int, default=None)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--debug-dump", nargs="?", const=str(DEBUG_DUMP), default=None,
                    help="Write raw text of MALFORMED scorer generations to a JSONL file for "
                         "diagnosis (diagnostic only; NOT a score artifact; not committed). "
                         "Bare flag uses the default filename; pass a path to override.")
    args = ap.parse_args()

    report, _, _ = GR.dry_run()                     # always dry-run first; no model
    print(f"[dry-run] packets={report['n_packets']} leak={report['leak_scan']} "
          f"arm_randomized={report['arm_randomized']} no_hidden_labels={report['no_hidden_labels_in_packets']} "
          f"no_four_sphere={report['no_four_sphere_reference']} model_calls={report['model_calls']}")
    if args.dry_check:
        print("[dry-check] OK; no models, no run.")
        return

    # gates (env + separate approved config); emits packets; base manifest untouched. No model yet.
    emitted = GR.run_real_smoke_pilot(approval_config=args.approval_config)
    packets, hidden = emitted["packets"], emitted["hidden"]
    bundle = GR.load_bundle()
    cfg = GR.load_approval_config(args.approval_config)
    model_id = args.model_id or cfg.get("scorer_model") or DEFAULT_MODEL
    TEMPERATURE = args.temperature if args.temperature is not None else float(cfg.get("temperature", TEMPERATURE))
    MAX_NEW_TOKENS = args.max_new_tokens or int(cfg.get("max_tokens", MAX_NEW_TOKENS))

    model, tok = _load_model(model_id)              # only after gates pass
    debug_records = [] if args.debug_dump else None
    scores_by_pid, malformed = score_packets(
        packets, hidden, lambda p: _generate(model, tok, _prompt(p)), debug_records)
    if args.debug_dump and debug_records:
        pathlib.Path(args.debug_dump).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in debug_records) + "\n",
            encoding="utf-8")
        print(f"[debug] captured {len(debug_records)} malformed generation(s) -> {args.debug_dump} "
              "(diagnostic only; not a score artifact)")
    rate = malformed / max(1, len(packets))
    if rate > MALFORMED_ABORT_RATE:
        result = _result("INCONCLUSIVE", None, None, 0, [], malformed, rate,
                         note=f"aborted: malformed rate {rate:.2f} > {MALFORMED_ABORT_RATE}")
    else:
        result = assemble_and_score(bundle, hidden, scores_by_pid, malformed, rate)
    _write(result, model_id)
    print(f"[done] primary_label={result['primary_label']} malformed_rate={rate:.3f} "
          f"judged={result['tasks_judged']} dropped={len(result['tasks_dropped_by_judge'])} "
          f"-> wrote {OUTPUTS_JSON.name} + {RESULT_MD.name}")


if __name__ == "__main__":
    main()
