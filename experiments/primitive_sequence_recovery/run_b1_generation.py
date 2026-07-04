#!/usr/bin/env python3
"""B1 GENERATION RUNNER — runs the FROZEN B0 evaluation on the operator RunPod (real models).

Runs ONLY on a GPU host with the locked backend (transformers 5.13.0 / tokenizers 0.22.2) and the
two locked models available. It does NOT run in the git/prep sandbox (no torch/transformers/GPU).

Faithful to the frozen B0 baseline — this runner adds NO new experimental choices:
  * Inputs, conditioning, wrapper, tasks, arms, decode policy and seeds all come from the FROZEN
    freeze-set files (verified by sha256 against B0_FREEZE_RECORD.json before anything loads).
  * Prompts are built by the frozen harness (b1_dry_run_harness.build_prompt) with real conditioning
    (b1_real_conditioning.real_core).
  * Decode = locked DECODE; per-row seed from locked generation seeds; NO system prompt, NO
    arm-specific decoding, NO best-of-N, NO rerun-until-pass.
  * Writes RAW outputs only (JSONL). It does NOT score, build packets, compute a verdict, or unblock
    Track B. Scoring/leak-scan/packet-build are separate, separately-approved gates.

Abort conditions (fail loud, never silently continue):
  * any frozen hash mismatch  -> INVALID_POSTHOC, refuse to run
  * cuda not available         -> refuse to run
  * locked backend version mismatch (transformers/tokenizers) -> refuse to run

Usage on RunPod:
    python3 experiments/primitive_sequence_recovery/run_b1_generation.py \
        --out experiments/primitive_sequence_recovery/b1_raw_outputs.jsonl
    # optional: --limit N (smoke a few rows), --model A|B (one model), --resume (skip done row_ids)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B            # noqa: E402  frozen prompt construction
import b1_real_conditioning as RC         # noqa: E402  frozen real conditioning

FREEZE_RECORD = HERE / "B0_FREEZE_RECORD.json"
RUNTIME_LOCK = HERE / "TRACK_B_RUNTIME_MODEL_LOCK.yaml"


# ---------------------------------------------------------------- integrity gate ------------------
def verify_frozen_or_abort():
    rec = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))["B0_FREEZE_RECORD"]
    if not (rec["b0_frozen"] and rec["b0_freeze_signed"]):
        raise SystemExit("ABORT: B0 is not frozen/signed.")
    bad = []
    for a in rec["bound_artifacts"]:
        cur = hashlib.sha256((REPO / a["path"]).read_bytes()).hexdigest()
        if cur != a["sha256"]:
            bad.append(a["path"])
    if bad:
        raise SystemExit(f"ABORT INVALID_POSTHOC: frozen artifact(s) changed since freeze: {bad}")
    print(f"[ok] frozen integrity: all {len(rec['bound_artifacts'])} artifacts match B0 baseline "
          f"(freeze base {rec['freeze_base_commit'][:10]})")
    return rec


def load_locked_models():
    import yaml
    d = yaml.safe_load(RUNTIME_LOCK.read_text(encoding="utf-8"))["RUNTIME_MODEL_LOCK"]
    if d["lock_state"] != "FILLED_OPERATOR_LOCK":
        raise SystemExit("ABORT: runtime lock not in FILLED_OPERATOR_LOCK state.")
    return {
        "A": {"id": d["model_A"]["id"], "revision": str(d["model_A"]["revision_or_api_version"])},
        "B": {"id": d["model_B"]["id"], "revision": str(d["model_B"]["revision_or_api_version"])},
        "backend_version": d["model_A"]["backend_version"],
        "tokenizer_version": d["model_A"]["tokenizer_version"],
        "decode": d["decode"], "seeds": d["seeds"],
    }


# ---------------------------------------------------------------- real transformers adapter -------
class TransformersAdapter:
    """Loads a locked model at its locked revision and generates with the locked decode policy."""

    def __init__(self, model_id, revision, decode):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.model_id, self.revision, self.decode = model_id, revision, decode
        self.tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, revision=revision, torch_dtype=torch.float16, device_map="auto")
        self.model.eval()

    def generate(self, prompt, seed):
        import torch
        from transformers import set_seed
        set_seed(seed)  # deterministic per (row, seed)
        # locked chat wrapping: user turn only, NO system prompt (decode.system_prompt == none)
        msgs = [{"role": "user", "content": prompt}]
        inputs = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt"
                                              ).to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                inputs,
                do_sample=True,
                temperature=self.decode["temperature"],
                top_p=self.decode["top_p"],
                max_new_tokens=self.decode["max_tokens"],
                pad_token_id=self.tok.eos_token_id,
            )
        text = self.tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=True)
        return text.strip()


# ---------------------------------------------------------------- runner --------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "b1_raw_outputs.jsonl"))
    ap.add_argument("--limit", type=int, default=0, help="smoke: cap number of rows (0 = all 3600)")
    ap.add_argument("--model", choices=["A", "B"], default=None, help="restrict to one locked model")
    ap.add_argument("--resume", action="store_true", help="skip row_ids already present in --out")
    args = ap.parse_args(argv)

    verify_frozen_or_abort()
    locked = load_locked_models()

    # hard environment gates
    try:
        import torch
        import transformers
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"ABORT: locked backend not importable ({e}). Run on the RunPod, not the prep VM.")
    if not torch.cuda.is_available():
        raise SystemExit("ABORT: torch.cuda.is_available() is False. Fix the pod driver first.")
    if transformers.__version__ != locked["backend_version"]:
        raise SystemExit(f"ABORT: transformers {transformers.__version__} != locked "
                         f"{locked['backend_version']}.")

    decode, seeds = locked["decode"], locked["seeds"]
    print(f"[ok] cuda True | transformers {transformers.__version__} | decode {decode}")
    print(f"[ok] locked seeds {seeds['generation']} | models "
          f"A={locked['A']['id']}@{locked['A']['revision'][:10]} "
          f"B={locked['B']['id']}@{locked['B']['revision'][:10]}")

    rows = B.expand_rows()
    if args.model:
        want = "MOCK_MODEL_A" if args.model == "A" else "MOCK_MODEL_B"
        rows = [r for r in rows if r.model == want]
    if args.limit:
        rows = rows[:args.limit]
    # map the harness's nominal model slots to the two locked real models
    slot_of = {"MOCK_MODEL_A": "A", "MOCK_MODEL_B": "B"}

    out_path = pathlib.Path(args.out)
    done = set()
    if args.resume and out_path.exists():
        for ln in out_path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(ln)["row_id"])
            except Exception:  # noqa: BLE001
                pass
        print(f"[resume] {len(done)} rows already present; skipping them")

    adapters = {}
    written = 0
    with out_path.open("a", encoding="utf-8") as fh:
        for i, r in enumerate(rows, 1):
            if r.row_id in done:
                continue
            slot = slot_of[r.model]
            if slot not in adapters:
                m = locked[slot]
                print(f"[load] model {slot}: {m['id']}@{m['revision'][:10]} …")
                adapters[slot] = TransformersAdapter(m["id"], m["revision"], decode)
            cond, prompt = B.build_prompt(r.key_word, B.TASKS[r.task], r.arm, conditioning_fn=RC.real_core)
            text = adapters[slot].generate(prompt, seed=r.seed)
            rec = {
                "row_id": r.row_id, "key_word": r.key_word, "stratum": r.stratum, "task": r.task,
                "arm": r.arm, "model_slot": slot, "model_id": locked[slot]["id"],
                "model_revision": locked[slot]["revision"], "seed": r.seed,
                "conditioning": cond, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "output_text": text, "scored": False,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            written += 1
            if i % 50 == 0 or i == len(rows):
                print(f"  … {i}/{len(rows)} rows (written {written})")

    print(f"\n[done] wrote {written} raw outputs -> {out_path}")
    print("RAW GENERATION ONLY. Not scored. No packets. No verdict. Track B remains BLOCKED.")
    print("Next gate: RUN_B1_LEAK_SCAN_AND_PACKET_BUILD (separately approved).")


if __name__ == "__main__":
    main()
