"""Track F smoke runner (Mistral answer model) — RUNS ON RUNPOD/LOCAL-GPU ONLY.

Emits leak-scanned prompt packets for arms X/A/B/F/I/R, and — only under an explicit approval config
+ env token — runs the APPROVED answer model (Mistral) over them, optionally runs a judge pass, and
writes `track_f_smoke_outputs.json` + `TRACK_F_SMOKE_RESULT.md`. It makes NO model calls in dry-run
and is NOT runnable from the firewalled build sandbox. Nothing here fabricates scores.

Judge separation: if a distinct judge model is not provided, a single-model judge (Mistral judging
anonymized outputs) is allowed but marked **exploratory / weaker** in the output. Track B stays
BLOCKED regardless; a smoke result is exploratory triage only, never validation, never
ONTOLOGICAL_SIGNAL / Sanskrit privilege. Base smoke manifest is never edited (authorization is the
separate approved run config).

Usage on the pod:
    export TRACK_F_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_F_SMOKE
    python3 experiments/primitive_sequence_recovery/run_track_f_smoke_mistral.py --dry-check
    python3 experiments/primitive_sequence_recovery/run_track_f_smoke_mistral.py \
        --approval-config experiments/primitive_sequence_recovery/track_f_smoke_approved_run_config.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import track_f_harness as HF   # noqa: E402

APPROVAL_ENV = "TRACK_F_SMOKE_RUN_APPROVED"
APPROVAL_TOKEN = "I_APPROVE_TRACK_F_SMOKE"
CONFIG_PATH = HERE / "track_f_smoke_approved_run_config.json"
MANIFEST = HERE / "track_f_smoke_manifest.json"
OUTPUTS_JSON = HERE / "track_f_smoke_outputs.json"
RESULT_MD = HERE / "TRACK_F_SMOKE_RESULT.md"
MALFORMED_ABORT_RATE = 0.15
ANSWER_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
TEMPERATURE = 0.0
MAX_NEW_TOKENS = 256

VARNA_KEYS = tuple(json.loads((HERE / "frozen/assignment.json").read_text())["tau"].keys())
ROOT_NAMES = ("moha", "bhaya", "kama", "krodha", "sukha", "hrdaya", "shanti", "bala", "buddhi",
              "nadi", "parvata", "grha", "dharma", "trishna", "lobha", "moksha")
ANSWER_INSTRUCTIONS = ('Respond with JSON ONLY, no prose: {"answer": "...", "interpretation": "...", '
                       '"reasoning_summary": "...", "confidence": 0.0, "caveats": "...", '
                       '"selected_candidate": null}.')
_CONTAM = re.compile(r"\b(sanskrit|varna|varṇa|vrtti|vṛtti|moha|bhaya|kama|krodha|dharma|sphere)\b", re.I)


class LeakDetected(ValueError):
    pass


# ------------------------------------------------------------------ loading ---------
def _read_jsonl(p):
    return [json.loads(l) for l in pathlib.Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_bundle():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if man.get("bundle_type") != "track_f_input_bundle" or man.get("four_sphere_integrated") is not False:
        raise ValueError("bad Track F manifest")
    tasks = {t["task_id"]: t for t in _read_jsonl(HERE / "track_f_smoke_tasks.jsonl")}
    arms = _read_jsonl(HERE / "track_f_smoke_prompt_arms.jsonl")
    return {"manifest": man, "tasks": tasks, "arms": arms, "seeds": man["seeds"]}


def load_approval_config(path):
    cfg = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    bad = []
    if cfg.get("config_type") != "track_f_smoke_approved_run_config": bad.append("config_type")
    if cfg.get("run_enabled") is not True: bad.append("run_enabled!=true")
    if cfg.get("approval_status") != "APPROVED": bad.append("approval_status!=APPROVED")
    if not cfg.get("answer_model"): bad.append("answer_model unset")
    if cfg.get("four_sphere_integrated") is not False: bad.append("four_sphere_integrated!=false")
    rec = cfg.get("approval_record") or {}
    if not rec.get("date") or not rec.get("signature"): bad.append("approval signature/date")
    if bad:
        raise RuntimeError("invalid approval config: " + "; ".join(bad))
    return cfg


# ------------------------------------------------------------- dry-run packets ------
def _pid(task_id, arm, seed):
    return "fpkt_" + hashlib.sha1(f"{seed}|{task_id}|{arm}".encode()).hexdigest()[:16]


def _assemble_prompt(task, boundary_text):
    parts = [f"TASK: {task['base_prompt']}", f"CONTEXT: {task['context']}"]
    if boundary_text:
        parts.append(boundary_text)
    parts.append(ANSWER_INSTRUCTIONS)
    return "\n".join(parts)


def build_packets(bundle):
    seed = bundle["seeds"]["arm_order"]
    packets, hidden = [], []
    for a in bundle["arms"]:
        task = bundle["tasks"][a["task_id"]]
        pid = _pid(a["task_id"], a["arm"], seed)
        packets.append({"packet_id": pid, "task_id": a["task_id"],
                        "prompt": _assemble_prompt(task, a.get("boundary_text")),
                        "response_format": "json"})
        hidden.append({"packet_id": pid, "task_id": a["task_id"], "true_arm": a["arm"]})
    # deterministic packet-order shuffle so file order does not encode arm
    rng = random.Random(seed)
    idx = list(range(len(packets)))
    rng.shuffle(idx)
    packets = [packets[i] for i in idx]
    hidden = {h["packet_id"]: h for h in hidden}
    return packets, hidden


def scan_packet(packet, surface_word):
    blob = packet["prompt"].lower()
    if surface_word and re.search(r"\b" + re.escape(surface_word.lower()) + r"\b", blob):
        raise LeakDetected(f"surface leak {surface_word!r}")
    for t in ROOT_NAMES + VARNA_KEYS:
        if re.search(r"\b" + re.escape(t) + r"\b", blob):
            raise LeakDetected(f"root/varna leak {t!r}")
    if "sphere" in blob:
        raise LeakDetected("four-sphere reference")
    for lab in HF.FORBIDDEN_LABELS:
        if lab.lower() in blob:
            raise LeakDetected(f"forbidden label {lab!r}")
    # no explicit arm label / boundary_kind identifier in a scorer-facing prompt
    if re.search(r"\b(?:true_)?arm[\s_:=-]*['\"]?[abfixr]\b", blob) or "boundary_real" in blob:
        raise LeakDetected("arm-label leak")
    return True


def dry_run(preview_path=None):
    bundle = load_bundle()
    packets, hidden = build_packets(bundle)
    for p in packets:
        scan_packet(p, bundle["tasks"][p["task_id"]].get("dev_surface_word"))
    # arm randomization: packet order not grouped by arm, packet_id opaque, arm only in hidden key
    arms_in_order = [hidden[p["packet_id"]]["true_arm"] for p in packets]
    randomized = arms_in_order != sorted(arms_in_order)
    no_hidden_in_packet = all("true_arm" not in p and "arm" not in p for p in packets)
    no_sphere = not any("sphere" in p["prompt"].lower() for p in packets)
    report = {"n_packets": len(packets), "n_tasks": len(bundle["tasks"]), "arms": bundle["manifest"]["arms"],
              "leak_scan": "clean", "arm_randomized": randomized, "no_hidden_labels_in_packets": no_hidden_in_packet,
              "no_four_sphere_reference": no_sphere, "model_calls": 0, "scored": False,
              "note": "dry-run preview only; no model calls; not a run; not scoring."}
    if preview_path:
        pathlib.Path(preview_path).write_text(json.dumps({"report": report, "packets": packets},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
    return report, packets, hidden


# ------------------------------------------------------------------ gates -----------
def _gate():
    if os.environ.get(APPROVAL_ENV) != APPROVAL_TOKEN:
        raise RuntimeError(f"env {APPROVAL_ENV}={APPROVAL_TOKEN!r} required; refusing.")


# ------------------------------------------------------------- model + judge --------
def _load_model(model_id):
    import torch  # noqa: F401
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="auto", device_map="auto")
    model.eval()
    return model, tok


def _generate(model, tok, user_text):
    import torch
    prompt = tok.apply_chat_template([{"role": "user", "content": user_text}],
                                     add_generation_prompt=True, tokenize=False)
    enc = tok(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                             pad_token_id=(tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id))
    return tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object")
    return json.loads(m.group(0))


def main():
    global ANSWER_MODEL, TEMPERATURE, MAX_NEW_TOKENS
    ap = argparse.ArgumentParser()
    ap.add_argument("--approval-config", default=str(CONFIG_PATH))
    ap.add_argument("--dry-check", action="store_true")
    ap.add_argument("--judge-mode", choices=["none", "single"], default="none",
                    help="'single' = Mistral judges its own anonymized outputs (EXPLORATORY/weaker)")
    args = ap.parse_args()

    report, packets, hidden = dry_run()
    print(f"[dry-run] packets={report['n_packets']} leak={report['leak_scan']} "
          f"arm_randomized={report['arm_randomized']} no_hidden_labels={report['no_hidden_labels_in_packets']} "
          f"no_four_sphere={report['no_four_sphere_reference']} model_calls={report['model_calls']}")
    if args.dry_check:
        print("[dry-check] OK; no models, no run.")
        return

    _gate()
    cfg = load_approval_config(args.approval_config)   # base manifest untouched
    ANSWER_MODEL = cfg["answer_model"]
    TEMPERATURE = float(cfg.get("temperature", TEMPERATURE))
    MAX_NEW_TOKENS = int(cfg.get("max_tokens", MAX_NEW_TOKENS))
    if json.loads(MANIFEST.read_text())["run_enabled"] is not False:
        raise RuntimeError("base smoke manifest must stay run_enabled:false")

    model, tok = _load_model(ANSWER_MODEL)
    answers, malformed = {}, 0
    for p in packets:
        try:
            answers[p["packet_id"]] = _parse_json(_generate(model, tok, p["prompt"]))
        except Exception:
            malformed += 1
    rate = malformed / max(1, len(packets))
    judge_note = ("single-model judge (answer model judged its own anonymized outputs): EXPLORATORY / "
                  "weaker — no answer≠judge separation" if args.judge_mode == "single"
                  else "no judge pass run; answers only")
    out = {"artifact": "track_f_smoke_outputs", "exploratory_triage_only": True,
           "answer_model": ANSWER_MODEL, "temperature": TEMPERATURE, "judge_mode": args.judge_mode,
           "judge_note": judge_note, "n_packets": len(packets), "malformed": malformed,
           "malformed_rate": round(rate, 4),
           "aborted": rate > MALFORMED_ABORT_RATE,
           "primary_label": ("INCONCLUSIVE" if (rate > MALFORMED_ABORT_RATE or args.judge_mode == "none")
                             else "PENDING_JUDGE"),
           "note": ("Track F smoke, exploratory triage only. Judge scoring feeds track_f_harness for a "
                    "label from {INFERENCE_STEERING_SIGNAL, PROMPT_PRIMING_ONLY, SCRAMBLE_EQUIVALENT, "
                    "BARNUM_EQUIVALENT, CORRECTNESS_DEGRADED, NO_EFFECT, INCONCLUSIVE}. Not validation; "
                    "Track B remains blocked. No ONTOLOGICAL_SIGNAL, no Sanskrit privilege.")}
    OUTPUTS_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULT_MD.write_text(
        "# Track F Smoke — Result (exploratory triage only)\n\n"
        f"- answer_model: `{ANSWER_MODEL}` | temp {TEMPERATURE} | judge_mode: {args.judge_mode}\n"
        f"- packets: {len(packets)} | malformed_rate: {round(rate,4)} | aborted: {out['aborted']}\n"
        f"- judge_note: {judge_note}\n"
        f"- primary_label: `{out['primary_label']}`\n\n"
        "Track F smoke pilot, exploratory triage only. Track B remains blocked. "
        "Structure, not validated meaning.\n", encoding="utf-8")
    print(f"[done] malformed_rate={rate:.3f} judge_mode={args.judge_mode} -> wrote "
          f"{OUTPUTS_JSON.name} + {RESULT_MD.name}")


if __name__ == "__main__":
    main()
