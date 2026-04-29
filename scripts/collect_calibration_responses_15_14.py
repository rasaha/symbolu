"""Collect Qwen calibration responses for §15.14 calibration chains.

Narrow pre-implementation script authorized as "Option A" in the
§15.14 curation thread. This script is NOT the full §15.14
implementation §0.X (`scripts/probe_framing_15_14.py`, not yet
authorized). It performs ONLY the model-response-collection step
for the 10 calibration chains so that a human annotator can
subsequently assign severity labels in
`docs/experiments/sticky_framing_15_14_calibration_labels.json`.

Sealed parameters (pinned identical to §15.14 spec Chunk 6):
  MODEL_ID            = "Qwen/Qwen2.5-7B-Instruct"
  DECODE_TEMPERATURE  = 0.0   (greedy)
  MAX_NEW_TOKENS      = 64
  K_CHAIN_LENGTH      = 6
  CHAT_TEMPLATE       = tokenizer.apply_chat_template

Inputs (pinned):
  STIMULUS_JSON_PATH    = docs/experiments/sticky_framing_15_14_stimuli.json
  EXPECTED_STIMULUS_SHA = e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7

Output (pinned):
  RESPONSES_ARTIFACT_PATH =
      docs/experiments/sticky_framing_15_14_calibration_responses.json

Output shape: 50 records (10 calibration chains × 5 turns 2..6).
Each record contains: chain_idx, turn_idx, calibration_chain_id,
framing_question, framing_token_char_span, turn_t_question,
turn_t_response, model_response_id, response_timestamp, and a
shared run_metadata block.

What this script does NOT do:
  - Compute hidden states (s_t, f_1, q_t, a_{t-1}).
  - Compute R_framing, R_topic_to_framing, R_recency, or any AUC.
  - Load the LLM-judge (Qwen-72B or fallback).
  - Apply the severity rubric or assign any label.
  - Modify the labels artifact, the stimulus JSON, or any spec.
  - Touch any §0.8-binding threshold or any §15.x verdict-of-record.

CLI modes:
  --dry-run        Validate inputs + SHA, enumerate the 50 (chain,
                    turn) slots, build prompts for inspection, write
                    a structurally-valid responses artifact with
                    `turn_t_response = null` and `_dry_run: true`.
                    Does NOT import torch / transformers; suitable
                    for sandbox verification.
  (default)         Load Qwen-7B and run inference. Requires GPU.

Exit codes:
  0  success
  2  CLI / argument error (handled by argparse)
  5  SCHEMA_MISMATCH (stimulus SHA mismatch, missing fields, or
                       calibration_chains shape invalid)
  6  EXTRACTION_FAILED (model load or inference failure;
                         actionable diagnostic to stderr)
  7  WRITE_FAILED (output write failure)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path


# ---------------------------------------------------------------------------
# Pinned constants (§15.14 spec Chunk 6 sealed parameters)
# ---------------------------------------------------------------------------

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
DECODE_TEMPERATURE = 0.0
MAX_NEW_TOKENS = 64
K_CHAIN_LENGTH = 6
CHAT_TEMPLATE_METHOD = "tokenizer.apply_chat_template"

STIMULUS_JSON_PATH = Path("docs/experiments/sticky_framing_15_14_stimuli.json")
EXPECTED_STIMULUS_SHA = (
    "e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7"
)
RESPONSES_ARTIFACT_PATH = Path(
    "docs/experiments/sticky_framing_15_14_calibration_responses.json"
)
RESPONSES_SCHEMA_VERSION = "15.14-calibration-responses"

EXIT_SUCCESS = 0
EXIT_SCHEMA_MISMATCH = 5
EXIT_EXTRACTION_FAILED = 6
EXIT_WRITE_FAILED = 7


# ---------------------------------------------------------------------------
# Stimulus loading + SHA validation
# ---------------------------------------------------------------------------


def _canonical_stimulus_sha(payload: dict) -> str:
    """Mirror the validator's canonical-form SHA (excludes underscore-prefixed)."""
    canonical = {k: v for k, v in payload.items() if not k.startswith("_")}
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _load_stimulus_and_verify_sha(path: Path, expected_sha: str) -> dict:
    if not path.exists():
        print(f"SCHEMA_MISMATCH: stimulus JSON not found: {path}", file=sys.stderr)
        sys.exit(EXIT_SCHEMA_MISMATCH)
    payload = json.loads(path.read_text())

    actual_sha = _canonical_stimulus_sha(payload)
    if actual_sha != expected_sha:
        print(
            f"SCHEMA_MISMATCH: stimulus JSON SHA mismatch.\n"
            f"  expected: {expected_sha}\n"
            f"  actual:   {actual_sha}\n"
            f"  This script is pinned to a specific stimulus state. If the\n"
            f"  stimulus has been intentionally updated, the EXPECTED_STIMULUS_SHA\n"
            f"  constant must be updated under fresh authorization.",
            file=sys.stderr,
        )
        sys.exit(EXIT_SCHEMA_MISMATCH)

    if "framing_pool" not in payload or "calibration_chains" not in payload:
        print(
            "SCHEMA_MISMATCH: stimulus JSON missing 'framing_pool' or "
            "'calibration_chains'",
            file=sys.stderr,
        )
        sys.exit(EXIT_SCHEMA_MISMATCH)
    if len(payload["calibration_chains"]) != 10:
        print(
            f"SCHEMA_MISMATCH: expected 10 calibration_chains; "
            f"got {len(payload['calibration_chains'])}",
            file=sys.stderr,
        )
        sys.exit(EXIT_SCHEMA_MISMATCH)

    return payload


def _build_frame_lookup(framing_pool: list[dict]) -> dict[str, dict]:
    return {item["frame_id"]: item for item in framing_pool}


# ---------------------------------------------------------------------------
# Inference (lazy-imported only when not in --dry-run mode)
# ---------------------------------------------------------------------------


def _load_model_and_tokenizer():
    """Load Qwen/Qwen2.5-7B-Instruct via transformers (GPU expected)."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:
        print(
            f"EXTRACTION_FAILED: torch/transformers not available: {e}",
            file=sys.stderr,
        )
        sys.exit(EXIT_EXTRACTION_FAILED)

    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype="auto",
            device_map="auto",
        )
        model.eval()
    except Exception as e:
        print(f"EXTRACTION_FAILED: model load failed: {e}", file=sys.stderr)
        sys.exit(EXIT_EXTRACTION_FAILED)

    return tokenizer, model


def _greedy_decode(tokenizer, model, messages: list[dict]) -> str:
    """Apply chat template + greedy decode MAX_NEW_TOKENS, return decoded text."""
    import torch

    prompt_ids = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
    )
    if hasattr(model, "device"):
        prompt_ids = prompt_ids.to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            prompt_ids,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            temperature=DECODE_TEMPERATURE,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0, prompt_ids.shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# Calibration response collection (per-chain K=6 multi-turn loop)
# ---------------------------------------------------------------------------


def _collect_calibration_responses(
    payload: dict,
    *,
    dry_run: bool,
    run_id: str,
    runpod_id: str | None,
) -> list[dict]:
    """Run K=6 chains on the 10 calibration stimuli; return 50 turn-2..6 records."""
    frame_lookup = _build_frame_lookup(payload["framing_pool"])
    cal_chains = payload["calibration_chains"]
    expected_records = 50  # 10 chains × 5 evaluation turns

    if dry_run:
        tokenizer = model = None
    else:
        tokenizer, model = _load_model_and_tokenizer()

    records: list[dict] = []
    script_commit = _git_head_commit()
    started_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    for chain in cal_chains:
        chain_idx = chain["chain_idx"]
        frame_id = chain["frame_id"]
        frame = frame_lookup[frame_id]

        # Build the K=6 multi-turn message sequence iteratively.
        framing_question = frame["framing_question"]
        framing_span = frame["framing_token_char_span"]

        messages: list[dict] = [{"role": "user", "content": framing_question}]

        # Turn 1: produce assistant response to the framing question.
        if dry_run:
            turn_1_response = (
                f"[DRY_RUN_TURN_1_RESPONSE for frame {frame_id}; not a real model output]"
            )
        else:
            try:
                turn_1_response = _greedy_decode(tokenizer, model, messages)
            except Exception as e:
                print(
                    f"EXTRACTION_FAILED: chain {chain_idx} turn 1 inference: {e}",
                    file=sys.stderr,
                )
                sys.exit(EXIT_EXTRACTION_FAILED)
        messages.append({"role": "assistant", "content": turn_1_response})

        # Turns 2..6 (the 5 evaluation turns we record).
        for cq in chain["chain_questions"]:
            turn_idx = cq["turn_idx"]
            turn_t_question = cq["question"]

            messages.append({"role": "user", "content": turn_t_question})

            if dry_run:
                turn_t_response = None
            else:
                try:
                    turn_t_response = _greedy_decode(tokenizer, model, messages)
                except Exception as e:
                    print(
                        f"EXTRACTION_FAILED: chain {chain_idx} turn {turn_idx} "
                        f"inference: {e}",
                        file=sys.stderr,
                    )
                    sys.exit(EXIT_EXTRACTION_FAILED)
                messages.append({"role": "assistant", "content": turn_t_response})

            records.append({
                "chain_idx": chain_idx,
                "turn_idx": turn_idx,
                "calibration_chain_id": f"calibration_{chain_idx:02d}",
                "framing_question": framing_question,
                "framing_token_char_span": framing_span,
                "turn_t_question": turn_t_question,
                "turn_t_response": turn_t_response,
                "model_response_id": (
                    f"qwen7b_calibration_{chain_idx:02d}_t{turn_idx}_{run_id[:8]}"
                ),
                "response_timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            })

            # In dry-run we do not append a model response to messages, so
            # subsequent turns build on the user-provided turn_t_question
            # alone. This is acceptable for structural verification.

    if len(records) != expected_records:
        print(
            f"EXTRACTION_FAILED: expected {expected_records} records; "
            f"got {len(records)}",
            file=sys.stderr,
        )
        sys.exit(EXIT_EXTRACTION_FAILED)

    return records


def _git_head_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "<git-unavailable>"


# ---------------------------------------------------------------------------
# Output writer + SHA computation
# ---------------------------------------------------------------------------


def _canonical_responses_sha(payload: dict) -> str:
    canonical = {k: v for k, v in payload.items() if not k.startswith("_")}
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _write_responses_artifact(
    records: list[dict],
    *,
    dry_run: bool,
    run_id: str,
    runpod_id: str | None,
    output_path: Path,
) -> str:
    payload = {
        "schema_version": RESPONSES_SCHEMA_VERSION,
        "stimulus_sha256": EXPECTED_STIMULUS_SHA,
        "responses": records,
        "run_metadata": {
            "model_id": MODEL_ID,
            "decode_temperature": DECODE_TEMPERATURE,
            "max_new_tokens": MAX_NEW_TOKENS,
            "k_chain_length": K_CHAIN_LENGTH,
            "chat_template_method": CHAT_TEMPLATE_METHOD,
            "stimulus_sha256": EXPECTED_STIMULUS_SHA,
            "script_commit": _git_head_commit(),
            "run_id": run_id,
            "runpod_id": runpod_id,
        },
        "_dry_run": dry_run,
        "_artifact_status": (
            "DRY_RUN_PLACEHOLDER" if dry_run else "RESPONSES_COLLECTED"
        ),
        "_next_step": (
            "Annotator: review each response, assign severity ∈ {0,1,2} per "
            "the §15.14 spec Chunk 3 rubric, write labels into "
            "docs/experiments/sticky_framing_15_14_calibration_labels.json. "
            "Set the labels artifact's stimulus_sha256 field to "
            f"{EXPECTED_STIMULUS_SHA}. Then re-run the validator with "
            "--strict --calibration-labels-json <path> and confirm exit 0 "
            "before authorizing the implementation §0.X."
        ),
    }
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    except Exception as e:
        print(f"WRITE_FAILED: {e}", file=sys.stderr)
        sys.exit(EXIT_WRITE_FAILED)

    return _canonical_responses_sha(payload)


# ---------------------------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs + SHA, enumerate the 50 (chain, turn) slots, "
             "and write a structurally-valid responses artifact with "
             "turn_t_response = null. Does NOT import torch / transformers; "
             "suitable for sandbox verification.",
    )
    parser.add_argument(
        "--stimulus-json",
        default=str(STIMULUS_JSON_PATH),
        help="Override the pinned stimulus JSON path (rare).",
    )
    parser.add_argument(
        "--output-path",
        default=str(RESPONSES_ARTIFACT_PATH),
        help="Override the pinned responses artifact path (rare).",
    )
    parser.add_argument(
        "--runpod-id",
        default=None,
        help="Optional runpod identifier recorded in run_metadata.runpod_id.",
    )
    args = parser.parse_args(argv)

    print(f"§15.14 calibration response collection")
    print(f"  mode:       {'DRY_RUN' if args.dry_run else 'INFERENCE'}")
    print(f"  model:      {MODEL_ID}")
    print(f"  K chains:   {K_CHAIN_LENGTH}")
    print(f"  decode:     greedy (T={DECODE_TEMPERATURE}, max_new_tokens={MAX_NEW_TOKENS})")
    print(f"  stimulus:   {args.stimulus_json}")
    print(f"  expected SHA: {EXPECTED_STIMULUS_SHA}")
    print()

    payload = _load_stimulus_and_verify_sha(
        Path(args.stimulus_json), EXPECTED_STIMULUS_SHA,
    )
    print("  stimulus SHA verified ✓")
    print(f"  calibration_chains: {len(payload['calibration_chains'])} (expect 10)")
    print()

    run_id = str(uuid.uuid4())
    print(f"  run_id: {run_id}")
    if args.runpod_id is not None:
        print(f"  runpod_id: {args.runpod_id}")
    print()

    records = _collect_calibration_responses(
        payload,
        dry_run=args.dry_run,
        run_id=run_id,
        runpod_id=args.runpod_id,
    )
    print(f"  collected: {len(records)} records (expect 50)")

    output_sha = _write_responses_artifact(
        records,
        dry_run=args.dry_run,
        run_id=run_id,
        runpod_id=args.runpod_id,
        output_path=Path(args.output_path),
    )
    print()
    print(f"  wrote: {args.output_path}")
    print(f"  responses artifact SHA-256 (canonical): {output_sha}")
    print()

    if args.dry_run:
        print("DRY_RUN COMPLETE — turn_t_response is null on all 50 records.")
        print("Re-run on a GPU host without --dry-run to collect real responses.")
    else:
        print("INFERENCE COMPLETE — 50 responses collected.")
        print()
        print("Next step (human annotation, NOT automated):")
        print(f"  1. Review each response in {args.output_path}.")
        print(f"  2. Assign severity ∈ {{0, 1, 2}} per the §15.14 spec rubric.")
        print(f"  3. Write labels to "
              f"docs/experiments/sticky_framing_15_14_calibration_labels.json.")
        print(f"  4. Set the labels artifact's stimulus_sha256 to "
              f"{EXPECTED_STIMULUS_SHA}.")
        print(f"  5. Re-run validator: python3 scripts/validate_framing_15_14_stimuli.py "
              f"--strict --calibration-labels-json <path>.")
        print(f"  6. Only if --strict exits 0: pin final_stimulus_sha and "
              f"calibration_labels_sha in the implementation §0.X commit metadata.")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
