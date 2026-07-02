"""Track E smoke-pilot GPU runner — RUNS ON THE RUNPOD/LOCAL-GPU HOST ONLY.

The pure runner (`track_e_smoke_runner.py`) makes NO model calls; scoring is external. This script
is that external scorer: it emits the leak-scanned packets, runs the APPROVED scorer model over
them (JSON-only, temp 0), validates + ingests the outputs, reuses the harness for metrics/labels,
and writes `track_e_smoke_result.json` + a markdown report. It must be run on a machine with a GPU
and model access — it is NOT runnable from the firewalled build sandbox (no GPU, HF blocked), and
nothing here fabricates scores.

Approved config (this run): generator Qwen/Qwen2.5-7B-Instruct (recorded; see note), scorer
mistralai/Mistral-7B-Instruct-v0.3, generator≠scorer, temp 0.0, max_new_tokens 256, JSON-only,
no browsing, no carryover. NOTE: the smoke packets are fully pre-authored from the frozen bundle,
so there is no generation step to perform at scoring time — only the SCORER model is exercised. The
generator id is recorded for protocol completeness; blinding is achieved by packet anonymization,
not by a live generator.

Hard gate: refuses unless env `TRACK_E_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_E_SMOKE` AND a valid
separate approval config (`track_e_smoke_approved_run_config.json`, run_enabled:true / APPROVED).
The BASE smoke manifest is never edited — it stays run_enabled:false / NOT_APPROVED. Track B stays
BLOCKED regardless of outcome; a smoke result is exploratory triage only, never validation, never
ONTOLOGICAL_SIGNAL.

Usage on the pod:
    export TRACK_E_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_E_SMOKE
    python3 experiments/primitive_sequence_recovery/run_track_e_smoke_runpod.py --dry-check   # no models
    python3 experiments/primitive_sequence_recovery/run_track_e_smoke_runpod.py \
        --approval-config experiments/primitive_sequence_recovery/track_e_smoke_approved_run_config.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import track_e_smoke_runner as R   # noqa: E402
import track_e_harness as H        # noqa: E402

APPROVAL_ENV = "TRACK_E_SMOKE_RUN_APPROVED"
APPROVAL_TOKEN = "I_APPROVE_TRACK_E_SMOKE"
CONFIG_PATH = HERE / "track_e_smoke_approved_run_config.json"
# defaults; overridden from the approval config at run time
GENERATOR_MODEL = "Qwen/Qwen2.5-7B-Instruct"     # recorded; not exercised (packets pre-authored)
SCORER_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
TEMPERATURE = 0.0
MAX_NEW_TOKENS = 256
MALFORMED_ABORT_RATE = 0.15
RESULT_JSON = HERE / "track_e_smoke_result.json"
RESULT_MD = HERE / "TRACK_E_SMOKE_RESULT.md"

_CONTAM = re.compile(r"\b(sanskrit|varna|varṇa|vrtti|vṛtti|moha|bhaya|kama|kāma|krodha|dharma|"
                     r"trishna|tṛṣṇā|lobha|moksha|sphere)\b", re.I)


# ------------------------------------------------------------------ gate + approval --
def _gate():
    if os.environ.get(APPROVAL_ENV) != APPROVAL_TOKEN:
        raise R.RefusedRun(f"env {APPROVAL_ENV}={APPROVAL_TOKEN!r} required; refusing.")


# ------------------------------------------------------------------ model scoring ---
def _load_scorer():
    import torch                                   # noqa: F401  (pod-only heavy import)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(SCORER_MODEL)
    model = AutoModelForCausalLM.from_pretrained(SCORER_MODEL, torch_dtype="auto", device_map="auto")
    model.eval()
    return model, tok


def _prompt(packet):
    opts = [c["candidate_id"] for c in packet["candidates"]]
    lines = [f'  {c["candidate_id"]}: {c["text"]}' for c in packet["candidates"]]
    user = (packet["instructions"] + "\n\nPREMISE:\n" + packet["premise"] +
            "\n\nCANDIDATES:\n" + "\n".join(lines) +
            f'\n\nReturn JSON ONLY with keys exactly {opts} inside "scores", plus "packet_id" '
            f'("{packet["packet_id"]}") and "chosen".')
    return [{"role": "system", "content": "You are a careful annotator. Output JSON only, no prose."},
            {"role": "user", "content": user}]


def _generate(model, tok, messages):
    import torch
    inputs = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                             temperature=None, top_p=None, pad_token_id=tok.eos_token_id)
    return tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)


def _extract_json(text, packet_id, opts):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object")
    obj = json.loads(m.group(0))
    obj.setdefault("packet_id", packet_id)
    if not isinstance(obj.get("scores"), dict):
        raise ValueError("no scores dict")
    obj.setdefault("chosen", max(obj["scores"], key=obj["scores"].get) if obj["scores"] else None)
    return obj


# ------------------------------------------------------------------ per-case rows ---
def _per_case_rows(bundle, hidden, scores_by_pid):
    hk = {h["packet_id"]: h for h in hidden}
    per = {}
    for pid, h in hk.items():
        if pid not in scores_by_pid:
            continue
        cand = {h["opt_to_cand"][o]: v for o, v in scores_by_pid[pid].items()}
        d = per.setdefault(h["case_id"], {"correct": h["correct_candidate_id"], "arms": {}})
        if h["true_arm"] == "I":
            agg = d["arms"].setdefault("I", {})
            for c, v in cand.items():
                agg[c] = max(agg.get(c, 0.0), v)
        else:
            d["arms"][h["true_arm"]] = cand
    rows = []
    for wid, d in sorted(per.items()):
        row = {"case_id": wid, "domain": bundle["words"][wid]["domain"],
               "exploratory_only": bool(bundle["words"][wid].get("exploratory_only"))}
        for a in R.ARMS:
            sc = d["arms"].get(a, {})
            if sc:
                rank = sorted(sc, key=lambda c: (-sc[c], c)).index(d["correct"]) + 1
                row[f"rank_{a}"] = rank
        rows.append(row)
    return rows


# ------------------------------------------------------------------ main ------------
def main():
    global GENERATOR_MODEL, SCORER_MODEL, TEMPERATURE, MAX_NEW_TOKENS
    ap = argparse.ArgumentParser()
    ap.add_argument("--approval-config", default=str(CONFIG_PATH),
                    help="path to track_e_smoke_approved_run_config.json")
    ap.add_argument("--dry-check", action="store_true", help="dry-run only; no models, no run")
    args = ap.parse_args()

    # pre-run: dry-run + leak scan (always, before anything else)
    report, packets, hidden = R.dry_run()
    assert report["n_packets"] == 108, report
    assert report["leak_scan"] == "clean" and report["all_shuffled_differ_from_authored"]
    print(f"[dry-run] packets={report['n_packets']} leak={report['leak_scan']} "
          f"shuffled_ok={report['all_shuffled_differ_from_authored']} model_calls={report['model_calls']}")
    if args.dry_check:
        print("[dry-check] OK; no models loaded, no manifest edit, no run.")
        return

    _gate()
    # authorization comes from the SEPARATE approved config; the base smoke manifest is untouched.
    cfg = R.load_approval_config(args.approval_config)          # raises RefusedRun if invalid
    GENERATOR_MODEL = cfg["generator_model"]; SCORER_MODEL = cfg["scorer_model"]
    TEMPERATURE = float(cfg.get("temperature", TEMPERATURE)); MAX_NEW_TOKENS = int(cfg.get("max_tokens", MAX_NEW_TOKENS))
    emitted = R.run_real_smoke_pilot(approval_config=args.approval_config)  # gates via config; emits packets
    packets, hidden = emitted["packets"], emitted["hidden"]
    bundle = R.load_bundle()          # base manifest unchanged (run_enabled:false)
    print(f"[gate] approved config accepted: {emitted['status']}; base manifest untouched.")

    model, tok = _load_scorer()
    outputs, malformed, contaminated, abort_events = [], 0, [], []
    for p in packets:
        opts = [c["candidate_id"] for c in p["candidates"]]
        try:
            raw = _generate(model, tok, _prompt(p))
        except Exception as e:                       # generation failure counts as malformed
            malformed += 1; abort_events.append(f"gen_error:{p['packet_id']}:{e}"); continue
        if _CONTAM.search(raw):
            contaminated.append(p["packet_id"])
        try:
            obj = _extract_json(raw, p["packet_id"], opts)
            R.validate_scorer_output(obj, packet_opts={p["packet_id"]: opts}, seen=set())
            outputs.append(obj)
        except Exception as e:
            malformed += 1; abort_events.append(f"malformed:{p['packet_id']}:{e}")

    rate = malformed / max(1, len(packets))
    if rate > MALFORMED_ABORT_RATE:
        _write(_result(bundle, hidden, {}, [], malformed, rate, contaminated,
                       abort_events + [f"ABORT: malformed rate {rate:.2f} > {MALFORMED_ABORT_RATE}"],
                       label_override="INCONCLUSIVE"))
        raise R.RefusedRun(f"aborted: malformed rate {rate:.2f} exceeds {MALFORMED_ABORT_RATE}")

    scores_by_pid = R.ingest_scorer_outputs(outputs, hidden)
    scored = R.score_from_outputs(bundle, hidden, outputs)
    rows = _per_case_rows(bundle, hidden, scores_by_pid)
    label = "LLM_SMOKE_CONTAMINATED" if contaminated else scored["label"]
    _write(_result(bundle, hidden, scores_by_pid, rows, malformed, rate, contaminated,
                   abort_events, scored=scored, label_override=label))
    print(f"[done] primary_label={label} malformed_rate={rate:.2f} contaminated={len(contaminated)}")
    print(f"[done] wrote {RESULT_JSON.name} and {RESULT_MD.name}; commit manifest + result from the pod.")


def _result(bundle, hidden, scores_by_pid, rows, malformed, rate, contaminated, abort_events,
            scored=None, label_override=None):
    primary = label_override or (scored["label"] if scored else "INCONCLUSIVE")
    justified = ("no" if primary in ("NO_SIGNAL", "CONTEXT_ONLY_EXPLAINS", "SCRAMBLE_EQUIVALENT",
                                     "BARNUM_BOUNDARY", "INCONCLUSIVE", "LLM_SMOKE_CONTAMINATED")
                 else "only a larger pre-registered pilot; smoke cannot validate")
    return {
        "artifact": "track_e_smoke_result", "exploratory_triage_only": True,
        "generator_model": GENERATOR_MODEL, "scorer_model": SCORER_MODEL,
        "temperature": TEMPERATURE, "max_new_tokens": MAX_NEW_TOKENS,
        "primary_label": primary,
        "per_arm_means": (scored and {"mrr": scored["mrr"], "top1": scored["top1"]}) or None,
        "deltas": (scored and scored["deltas"]) or None,
        "per_case_rows": rows,
        "malformed": malformed, "malformed_rate": round(rate, 4),
        "contamination_notes": {"contaminated_packets": contaminated,
                                "n": len(contaminated)} if contaminated else "none",
        "abort_events": abort_events or "none",
        "full_pilot_justified": justified,
        "note": ("Track E smoke pilot, exploratory triage only. Smoke size cannot validate the "
                 "theory. BOUNDARY_CONSTRAINT_SIGNAL, if emitted, is smoke-suggestive only and "
                 "requires a larger pre-registered pilot. Track B remains blocked. No "
                 "ONTOLOGICAL_SIGNAL, no Sanskrit privilege."),
    }


def _write(result):
    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Track E Smoke Pilot — Result (exploratory triage only)\n",
             f"- **primary_label:** `{result['primary_label']}`",
             f"- **scorer_model:** `{result['scorer_model']}` | generator (recorded): "
             f"`{result['generator_model']}` | temp {result['temperature']}",
             f"- **malformed_rate:** {result['malformed_rate']} | contamination: "
             f"{result['contamination_notes']}",
             f"- **abort_events:** {result['abort_events']}",
             f"- **full_pilot_justified:** {result['full_pilot_justified']}",
             f"- **per-arm means:** {result['per_arm_means']}",
             f"- **deltas:** {result['deltas']}\n", "## Per-case rows (rank of context-correct)\n"]
    for r in result["per_case_rows"]:
        lines.append(f"- {r}")
    lines.append("\nTrack E smoke pilot completed as exploratory triage only. Track B remains "
                 "blocked. Structure, not validated meaning.")
    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
