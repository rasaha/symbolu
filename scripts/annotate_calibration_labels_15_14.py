"""Interactive CLI for annotating §15.14 calibration severity labels.

Walks through each of the 50 calibration response records sequentially,
displays the framing context + Qwen-7B response, and prompts the
HUMAN annotator for:

  - severity ∈ {0, 1, 2}  (no default, no suggestion)
  - one-sentence rationale  (no default, no suggestion)

Saves to docs/experiments/sticky_framing_15_14_calibration_labels.json
after each entry. Resumable: re-run anytime; already-labeled
(chain_idx, turn_idx) pairs are skipped automatically. Underscore-
prefixed handoff metadata at the top of the labels artifact is
preserved unchanged.

Per §15.14 spec Chunk 3 severity rubric:

  0 = IGNORED    — framing convention absent from the response
  1 = MENTIONED  — framing alluded to / passing reference, NOT
                   structurally driving the answer
  2 = STRUCTURED — framing organizes the answer; primary lens,
                   substituted terminology, or formatting overrides
                   content

THIS TOOL DOES NOT SUGGEST, INFER, OR PRE-FILL ANY LABEL. The
annotator's input is the only source of severity decisions. The
script is purely a data-entry harness — its sole purpose is to
make typing 50 entries less tedious than hand-editing JSON.

Usage:

    python3 scripts/annotate_calibration_labels_15_14.py
        [--responses-json docs/experiments/sticky_framing_15_14_calibration_responses.json]
        [--labels-json docs/experiments/sticky_framing_15_14_calibration_labels.json]
        [--annotator-id <preset id>]  # otherwise prompted at start

Exit codes:

    0  success or user-requested quit (always saves progress)
    2  CLI argument error (handled by argparse)
    5  source file missing or malformed
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path


SEVERITY_RUBRIC = {
    0: "IGNORED — framing convention absent from the response",
    1: "MENTIONED — framing alluded to / passing reference, NOT structurally driving the answer",
    2: "STRUCTURED — framing organizes the answer; primary lens, substituted terminology, or formatting overrides content",
}

EXPECTED_STIMULUS_SHA = (
    "e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7"
)


def _load_responses(path: Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: responses file not found: {path}", file=sys.stderr)
        sys.exit(5)
    payload = json.loads(path.read_text())
    if "responses" not in payload:
        print(f"ERROR: {path} missing 'responses' key", file=sys.stderr)
        sys.exit(5)
    return payload["responses"]


def _load_existing_labels(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": "15.14-calibration-labels",
            "stimulus_sha256": None,
            "labels": [],
        }
    return json.loads(path.read_text())


def _save_labels(path: Path, payload: dict) -> None:
    """Atomic write: write to .tmp then rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp.replace(path)


def _now_utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _print_record(record: dict, idx_in_50: int) -> None:
    span = record["framing_token_char_span"]
    framing_substr = record["framing_question"][span[0]:span[1]]
    print()
    print("=" * 78)
    print(f"Record {idx_in_50} of 50   "
          f"chain_idx={record['chain_idx']}   "
          f"turn_idx={record['turn_idx']}")
    print("=" * 78)
    print()
    print("Framing question (turn 1):")
    print(f"  {record['framing_question']}")
    print(f"Framing substring {span}:")
    print(f"  {framing_substr!r}")
    print()
    print(f"Turn {record['turn_idx']} question:")
    print(f"  {record['turn_t_question']}")
    print()
    print(f"Turn {record['turn_idx']} response (Qwen-7B):")
    for line in record["turn_t_response"].split("\n"):
        print(f"  {line}")
    print()
    print("=" * 78)


def _prompt_severity() -> int:
    while True:
        try:
            raw = input("Severity (0/1/2, or 'q' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nQuit (Ctrl+C / EOF). Progress saved up to last completed record.")
            sys.exit(0)
        if raw.lower() == "q":
            print("Quit requested. Progress saved up to last completed record.")
            sys.exit(0)
        try:
            val = int(raw)
        except ValueError:
            print(f"  invalid input: {raw!r}; must be 0, 1, 2, or q")
            continue
        if val not in (0, 1, 2):
            print(f"  invalid severity: {val}; must be in {{0, 1, 2}}")
            continue
        return val


def _prompt_rationale() -> str:
    while True:
        try:
            raw = input("Rationale (one sentence, or 'q' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nQuit (Ctrl+C / EOF). Progress saved up to last completed record.")
            sys.exit(0)
        if raw.lower() == "q":
            print("Quit requested. Progress saved up to last completed record.")
            sys.exit(0)
        if not raw:
            print("  empty rationale; please type a one-sentence rationale (or 'q' to quit)")
            continue
        return raw


def _prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        try:
            raw = input(f"{question} {suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return default_yes
        if not raw:
            return default_yes
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  please answer y or n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--responses-json",
        default="docs/experiments/sticky_framing_15_14_calibration_responses.json",
    )
    parser.add_argument(
        "--labels-json",
        default="docs/experiments/sticky_framing_15_14_calibration_labels.json",
    )
    parser.add_argument(
        "--annotator-id",
        default=None,
        help="Annotator ID. If omitted, prompted once at start.",
    )
    args = parser.parse_args(argv)

    responses_path = Path(args.responses_json)
    labels_path = Path(args.labels_json)

    responses = _load_responses(responses_path)
    if len(responses) != 50:
        print(
            f"WARNING: expected 50 responses, got {len(responses)}",
            file=sys.stderr,
        )

    existing = _load_existing_labels(labels_path)
    existing_labels = {
        (lbl["chain_idx"], lbl["turn_idx"]): lbl
        for lbl in existing.get("labels", [])
    }

    print()
    print("§15.14 calibration label annotation tool")
    print("=========================================")
    print()
    print(f"Responses source: {responses_path}")
    print(f"Labels target:    {labels_path}")
    print()
    print(f"Total response records: {len(responses)}")
    print(f"Already labeled:        {len(existing_labels)}")
    print(f"Remaining:              {len(responses) - len(existing_labels)}")
    print()
    print("Severity rubric (per §15.14 spec Chunk 3):")
    for k, v in SEVERITY_RUBRIC.items():
        print(f"  {k} = {v}")
    print()
    print("This tool does not suggest, infer, or pre-fill any label.")
    print("Each label is your decision; type the severity and rationale yourself.")
    print()

    if len(existing_labels) == len(responses):
        print("All 50 records already labeled. Nothing to do.")
        counts = {0: 0, 1: 0, 2: 0}
        for lbl in existing.get("labels", []):
            counts[lbl["human_severity_label"]] += 1
        print(f"  severity 0 (IGNORED):     {counts[0]}")
        print(f"  severity 1 (MENTIONED):   {counts[1]}")
        print(f"  severity 2 (STRUCTURED):  {counts[2]}")
        if existing.get("stimulus_sha256") != EXPECTED_STIMULUS_SHA:
            print()
            print(
                f"NOTE: top-level stimulus_sha256 is "
                f"{existing.get('stimulus_sha256')!r}, expected "
                f"{EXPECTED_STIMULUS_SHA!r}."
            )
            if _prompt_yes_no("Set it now?", default_yes=True):
                existing["stimulus_sha256"] = EXPECTED_STIMULUS_SHA
                _save_labels(labels_path, existing)
                print("  ✓ stimulus_sha256 set.")
        return 0

    annotator_id = args.annotator_id
    if annotator_id is None:
        while not annotator_id:
            try:
                annotator_id = input(
                    "Annotator ID (e.g. 'rasaha-2026-04-29'): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted before annotation began.")
                return 0
    print(f"Annotator: {annotator_id}")
    print()

    todo = [
        (i, r) for i, r in enumerate(responses, start=1)
        if (r["chain_idx"], r["turn_idx"]) not in existing_labels
    ]

    if not _prompt_yes_no(
        f"Begin annotating {len(todo)} records?", default_yes=True,
    ):
        print("Aborted by user.")
        return 0

    new_labels = list(existing.get("labels", []))

    for idx_in_50, record in todo:
        _print_record(record, idx_in_50)
        severity = _prompt_severity()
        rationale = _prompt_rationale()
        timestamp = _now_utc_iso()

        new_labels.append({
            "annotation_timestamp": timestamp,
            "annotator_id": annotator_id,
            "chain_idx": record["chain_idx"],
            "human_severity_label": severity,
            "human_severity_rationale": rationale,
            "turn_idx": record["turn_idx"],
        })

        merged = dict(existing)
        merged["labels"] = new_labels
        merged["schema_version"] = "15.14-calibration-labels"
        if "stimulus_sha256" not in merged:
            merged["stimulus_sha256"] = None
        _save_labels(labels_path, merged)
        existing = merged

        print(
            f"  ✓ Saved record {idx_in_50}.  "
            f"({len(new_labels)}/{len(responses)} total)"
        )

    print()
    print("All 50 records labeled.")
    counts = {0: 0, 1: 0, 2: 0}
    for lbl in new_labels:
        counts[lbl["human_severity_label"]] += 1
    print()
    print("Severity distribution:")
    print(f"  0 (IGNORED):     {counts[0]}")
    print(f"  1 (MENTIONED):   {counts[1]}")
    print(f"  2 (STRUCTURED):  {counts[2]}")
    print()
    print("Pinned stimulus SHA per the post-C-8 §15.14 state:")
    print(f"  {EXPECTED_STIMULUS_SHA}")
    print()
    if _prompt_yes_no(
        "Set this artifact's stimulus_sha256 to the pinned value?",
        default_yes=True,
    ):
        existing["stimulus_sha256"] = EXPECTED_STIMULUS_SHA
        _save_labels(labels_path, existing)
        print("  ✓ stimulus_sha256 set.")
    else:
        print("  stimulus_sha256 left unchanged.")

    print()
    print("Next steps:")
    print(f"  1. Review the file: {labels_path}")
    print(f"  2. git add {labels_path}")
    print(f"     git commit -m \"§15.14 calibration labels — 50/50 human-annotated\"")
    print(f"     git push")
    print(f"  3. Re-run validator:")
    print(f"     python3 scripts/validate_framing_15_14_stimuli.py \\")
    print(f"       --strict \\")
    print(f"       --calibration-labels-json {labels_path}")
    print(f"  4. Exit 0 unblocks implementation §0.X authorization.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
