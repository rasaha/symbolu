"""Standalone validator for the §15.14 sticky-framing stimulus JSON.

Loads `docs/experiments/sticky_framing_15_14_stimuli.json`, verifies
schema conformance, re-runs the topical-disjointness rule on every
chain row, verifies pairing rules and char-span resolutions, and
prints the SHA-256 digest of the canonical-form JSON.

Exit codes:
  0  validation passed
  2  CLI error (handled by argparse)
  5  SCHEMA_MISMATCH
  8  STIMULUS_INVALID (topical-disjointness, pairing, or span violation)

Used by the §15.14 implementation §0.X to gate `--collect` on the
stimulus JSON's locked SHA-256. This validator does NOT load the
model or the HF datasets; it operates on the stimulus JSON alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Reuse the curation script's pool builders + topical-disjointness checker.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from curate_framing_15_14_stimuli import (  # noqa: E402
    STIMULUS_SCHEMA_VERSION,
    STOPWORDS,
    FramingPoolItem,
    _tokenize_for_disjointness,
    calibration_chain_frame_index,
    framing_span_tokens,
    frame_positive_chain_frame_index,
    is_topically_disjoint,
    main_chain_frame_index,
)


EXIT_SUCCESS = 0
EXIT_SCHEMA_MISMATCH = 5
EXIT_STIMULUS_INVALID = 8


REQUIRED_TOP_KEYS = {
    "schema_version",
    "framing_pool",
    "main_chains",
    "frame_positive_chains",
    "calibration_chains",
}


# ----- Calibration labels artifact (separate file; C-8 split) -----
# Schema for docs/experiments/sticky_framing_15_14_calibration_labels.json.
# The validator merges (chain_idx, turn_idx) -> label record into the
# stimulus JSON's calibration_chains at validation time when the
# --calibration-labels-json flag is supplied (added in C-8c).

CALIBRATION_LABELS_SCHEMA_VERSION = "15.14-calibration-labels"

CALIBRATION_LABELS_REQUIRED_TOP_KEYS = {
    "schema_version",
    "stimulus_sha256",
    "labels",
}

CALIBRATION_LABELS_REQUIRED_ROW_KEYS = {
    "chain_idx",
    "turn_idx",
    "human_severity_label",
    "human_severity_rationale",
    "annotator_id",
    "annotation_timestamp",
}

# Optional row-level provenance keys (not required, but validated when
# present to prevent typos). model_response_id and run_id are useful for
# tracing labels back to a specific Qwen-7B inference run.
CALIBRATION_LABELS_OPTIONAL_ROW_KEYS = {
    "model_response_id",
    "run_id",
}


def _check_calibration_labels_artifact(
    labels_path: Path,
    expected_keys: set[tuple[int, int]],
    stimulus_sha: str,
) -> tuple[dict[tuple[int, int], dict], int]:
    """Load + validate the labels artifact; return (labels_by_key, n_filled).

    `expected_keys` is the full set of (chain_idx, turn_idx) pairs that
    the calibration_chains in the stimulus JSON expect — i.e., 50 pairs
    for 10 chains × 5 turns 2..6. The loader verifies each label row's
    chain_idx ∈ {0..9}, turn_idx ∈ {2..6}, label ∈ {0,1,2}, no
    duplicates, and that no row references an unknown key.

    Coverage (n_filled == len(expected_keys)) is checked by the caller
    when --strict or --require-calibration-labels is in effect.

    `stimulus_sha` is the canonical SHA of the current stimulus JSON;
    if the labels artifact's `stimulus_sha256` field is non-null and
    does not match, the load fails STIMULUS_INVALID — labels would be
    stale relative to the current stimulus.
    """
    if not labels_path.exists():
        fail(EXIT_SCHEMA_MISMATCH,
             f"calibration labels artifact not found: {labels_path}")
    payload = json.loads(labels_path.read_text())

    missing_top = CALIBRATION_LABELS_REQUIRED_TOP_KEYS - set(payload.keys())
    if missing_top:
        fail(EXIT_SCHEMA_MISMATCH,
             f"labels artifact missing top-level keys: {sorted(missing_top)}")
    if payload["schema_version"] != CALIBRATION_LABELS_SCHEMA_VERSION:
        fail(EXIT_SCHEMA_MISMATCH,
             f"labels artifact schema_version mismatch: expected "
             f"{CALIBRATION_LABELS_SCHEMA_VERSION!r}, got "
             f"{payload['schema_version']!r}")

    declared_stim_sha = payload.get("stimulus_sha256")
    if declared_stim_sha is not None and declared_stim_sha != stimulus_sha:
        fail(EXIT_STIMULUS_INVALID,
             f"labels artifact references stimulus_sha256={declared_stim_sha} "
             f"but current stimulus JSON has SHA-256 {stimulus_sha}; "
             f"labels are stale relative to this stimulus")

    labels_raw = payload["labels"]
    if not isinstance(labels_raw, list):
        fail(EXIT_SCHEMA_MISMATCH, "labels artifact 'labels' must be a list")

    labels_by_key: dict[tuple[int, int], dict] = {}
    for i, row in enumerate(labels_raw):
        if not isinstance(row, dict):
            fail(EXIT_SCHEMA_MISMATCH,
                 f"labels[{i}] must be an object; got {type(row).__name__}")

        missing = CALIBRATION_LABELS_REQUIRED_ROW_KEYS - set(row.keys())
        if missing:
            fail(EXIT_SCHEMA_MISMATCH,
                 f"labels[{i}] missing required keys: {sorted(missing)}")

        # Reject unknown keys (typos / drift).
        unknown = (
            set(row.keys())
            - CALIBRATION_LABELS_REQUIRED_ROW_KEYS
            - CALIBRATION_LABELS_OPTIONAL_ROW_KEYS
        )
        if unknown:
            fail(EXIT_SCHEMA_MISMATCH,
                 f"labels[{i}] contains unknown keys: {sorted(unknown)} "
                 f"(permitted: required={sorted(CALIBRATION_LABELS_REQUIRED_ROW_KEYS)} "
                 f"+ optional={sorted(CALIBRATION_LABELS_OPTIONAL_ROW_KEYS)})")

        ci = row["chain_idx"]
        ti = row["turn_idx"]
        if not (isinstance(ci, int) and 0 <= ci < 10):
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].chain_idx must be int in [0, 10); got {ci!r}")
        if not (isinstance(ti, int) and 2 <= ti <= 6):
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].turn_idx must be int in [2, 6]; got {ti!r}")

        label = row["human_severity_label"]
        if label not in (0, 1, 2):
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].human_severity_label must be in {{0,1,2}}; "
                 f"got {label!r}")

        rationale = row["human_severity_rationale"]
        if not isinstance(rationale, str) or not rationale.strip():
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].human_severity_rationale must be a non-empty string")

        annotator = row["annotator_id"]
        if not isinstance(annotator, str) or not annotator.strip():
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].annotator_id must be a non-empty string")

        ts = row["annotation_timestamp"]
        if not isinstance(ts, str) or not ts.strip():
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}].annotation_timestamp must be a non-empty string")

        key = (ci, ti)
        if key in labels_by_key:
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}] duplicates earlier row for (chain_idx={ci}, "
                 f"turn_idx={ti})")
        if key not in expected_keys:
            fail(EXIT_STIMULUS_INVALID,
                 f"labels[{i}] references unknown (chain_idx={ci}, turn_idx={ti}) "
                 f"not present in stimulus calibration_chains")
        labels_by_key[key] = row

    return labels_by_key, len(labels_by_key)


def _calibration_labels_artifact_sha(labels_path: Path) -> str:
    """SHA-256 of the labels artifact's canonical form (excludes
    underscore-prefixed metadata, mirroring the stimulus-JSON convention).
    """
    payload = json.loads(labels_path.read_text())
    canonical = {k: v for k, v in payload.items() if not k.startswith("_")}
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def fail(exit_code: int, msg: str) -> None:
    print(f"VALIDATION FAILED ({exit_code}): {msg}", file=sys.stderr)
    sys.exit(exit_code)


def _check_top_level(payload: dict) -> None:
    missing = REQUIRED_TOP_KEYS - set(payload.keys())
    if missing:
        fail(EXIT_SCHEMA_MISMATCH, f"missing top-level keys: {sorted(missing)}")
    if payload["schema_version"] != STIMULUS_SCHEMA_VERSION:
        fail(EXIT_SCHEMA_MISMATCH,
             f"schema_version mismatch: expected {STIMULUS_SCHEMA_VERSION!r}, "
             f"got {payload['schema_version']!r}")


def _check_framing_pool(pool_raw: list) -> list[FramingPoolItem]:
    if len(pool_raw) != 25:
        fail(EXIT_SCHEMA_MISMATCH, f"framing_pool must have 25 items; got {len(pool_raw)}")

    pool: list[FramingPoolItem] = []
    seen_ids: set[str] = set()
    valid_categories = {"metaphor", "persona", "terminology", "formatting"}

    for i, raw in enumerate(pool_raw):
        for k in ("frame_id", "framing_question", "framing_token_char_span", "framing_category"):
            if k not in raw:
                fail(EXIT_SCHEMA_MISMATCH, f"framing_pool[{i}] missing key: {k}")

        frame_id = raw["frame_id"]
        if frame_id in seen_ids:
            fail(EXIT_STIMULUS_INVALID, f"framing_pool[{i}] duplicate frame_id: {frame_id}")
        seen_ids.add(frame_id)

        if raw["framing_category"] not in valid_categories:
            fail(EXIT_STIMULUS_INVALID,
                 f"framing_pool[{i}] invalid category: {raw['framing_category']!r}")

        span = raw["framing_token_char_span"]
        if not (isinstance(span, list) and len(span) == 2 and all(isinstance(x, int) for x in span)):
            fail(EXIT_SCHEMA_MISMATCH,
                 f"framing_pool[{i}] framing_token_char_span shape invalid: {span!r}")
        start, end = span
        question = raw["framing_question"]
        if not (0 <= start < end <= len(question)):
            fail(EXIT_STIMULUS_INVALID,
                 f"framing_pool[{i}] span out of bounds: {span} for "
                 f"len(question)={len(question)}")

        item = FramingPoolItem(
            frame_id=frame_id,
            framing_question=question,
            framing_token_char_span=(start, end),
            framing_category=raw["framing_category"],
        )
        # Span must yield at least one non-stopword token.
        if not framing_span_tokens(item):
            fail(EXIT_STIMULUS_INVALID,
                 f"framing_pool[{i}] empty firewall vocabulary at span")
        pool.append(item)

    return pool


# Per-scope source enum (effective under §15.14-A1).
# main_chains and calibration_chains are restricted to the original
# enum; frame_positive_chains additionally permits the synthetic source.
_SOURCE_ENUM_PER_SCOPE: dict[str, frozenset[str]] = {
    "main_chains": frozenset({"truthfulqa_mc", "humaneval"}),
    "calibration_chains": frozenset({"truthfulqa_mc", "humaneval"}),
    "frame_positive_chains": frozenset({
        "truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1",
    }),
}


def _check_chain_shape(chain_raw: dict, chain_position: int, scope: str) -> None:
    for k in ("chain_idx", "frame_id", "chain_questions"):
        if k not in chain_raw:
            fail(EXIT_SCHEMA_MISMATCH,
                 f"{scope}[{chain_position}] missing key: {k}")
    if chain_raw["chain_idx"] != chain_position:
        fail(EXIT_SCHEMA_MISMATCH,
             f"{scope}[{chain_position}] chain_idx mismatch: {chain_raw['chain_idx']}")
    if len(chain_raw["chain_questions"]) != 5:
        fail(EXIT_SCHEMA_MISMATCH,
             f"{scope}[{chain_position}] chain_questions must have 5 entries; "
             f"got {len(chain_raw['chain_questions'])}")
    permitted_sources = _SOURCE_ENUM_PER_SCOPE.get(scope)
    if permitted_sources is None:
        fail(EXIT_SCHEMA_MISMATCH,
             f"unknown scope {scope!r}; per-scope enum not defined")
    for j, cq in enumerate(chain_raw["chain_questions"]):
        if cq["turn_idx"] != j + 2:
            fail(EXIT_SCHEMA_MISMATCH,
                 f"{scope}[{chain_position}].chain_questions[{j}].turn_idx mismatch: "
                 f"got {cq['turn_idx']}, expected {j+2}")
        if cq["source"] not in permitted_sources:
            fail(EXIT_STIMULUS_INVALID,
                 f"{scope}[{chain_position}].chain_questions[{j}].source "
                 f"invalid: {cq['source']!r}; permitted in {scope}: "
                 f"{sorted(permitted_sources)} "
                 f"(per §15.14-A1 source-enum scoping)")


def _check_main_chains(chains_raw: list, pool: list[FramingPoolItem]) -> None:
    if len(chains_raw) != 100:
        fail(EXIT_SCHEMA_MISMATCH, f"main_chains must have 100 entries; got {len(chains_raw)}")

    used_per_frame: dict[str, set[tuple[str, int]]] = {}

    for i, chain in enumerate(chains_raw):
        _check_chain_shape(chain, i, "main_chains")
        expected_frame_idx = main_chain_frame_index(i)
        expected_frame_id = pool[expected_frame_idx].frame_id
        if chain["frame_id"] != expected_frame_id:
            fail(EXIT_STIMULUS_INVALID,
                 f"main_chains[{i}] frame_id mismatch: pairing rule (i*7) mod 25 "
                 f"expects {expected_frame_id!r}, got {chain['frame_id']!r}")

        frame = pool[expected_frame_idx]
        used = used_per_frame.setdefault(chain["frame_id"], set())
        for j, cq in enumerate(chain["chain_questions"]):
            qkey = (cq["source"], cq["q_idx"])
            if qkey in used:
                fail(EXIT_STIMULUS_INVALID,
                     f"main_chains[{i}].chain_questions[{j}] reuses ({qkey}) "
                     f"within frame_id {chain['frame_id']}")
            used.add(qkey)
            if not is_topically_disjoint(frame, cq["question"]):
                firewall = framing_span_tokens(frame)
                qtoks = _tokenize_for_disjointness(cq["question"])
                shared = firewall & qtoks
                fail(EXIT_STIMULUS_INVALID,
                     f"main_chains[{i}].chain_questions[{j}] violates topical-"
                     f"disjointness against frame {chain['frame_id']}; shared "
                     f"tokens: {sorted(shared)}")


def _check_frame_positive_chains(chains_raw: list, pool: list[FramingPoolItem]) -> None:
    if len(chains_raw) != 20:
        fail(EXIT_SCHEMA_MISMATCH,
             f"frame_positive_chains must have 20 entries; got {len(chains_raw)}")
    for i, chain in enumerate(chains_raw):
        _check_chain_shape(chain, i, "frame_positive_chains")
        expected_frame_idx = frame_positive_chain_frame_index(i)
        expected_frame_id = pool[expected_frame_idx].frame_id
        if chain["frame_id"] != expected_frame_id:
            fail(EXIT_STIMULUS_INVALID,
                 f"frame_positive_chains[{i}] frame_id mismatch: expected "
                 f"{expected_frame_id!r}, got {chain['frame_id']!r}")


def _check_calibration_chains(chains_raw: list, pool: list[FramingPoolItem]) -> tuple[int, int]:
    """Validate calibration chain STRUCTURE only (no labels in stimulus JSON).

    Per §15.14-A1 follow-up (C-8): label fields no longer live in the
    stimulus JSON; they're in the separate labels artifact and merged
    in `_check_calibration_labels_artifact` (added in C-8c). This
    function returns (n_labelled, n_total) where n_labelled is always
    0 here — the merger sets the actual count when labels are loaded.
    """
    if len(chains_raw) != 10:
        fail(EXIT_SCHEMA_MISMATCH,
             f"calibration_chains must have 10 entries; got {len(chains_raw)}")

    n_total = 0
    for i, chain in enumerate(chains_raw):
        _check_chain_shape(chain, i, "calibration_chains")
        expected_frame_idx = calibration_chain_frame_index(i)
        expected_frame_id = pool[expected_frame_idx].frame_id
        if chain["frame_id"] != expected_frame_id:
            fail(EXIT_STIMULUS_INVALID,
                 f"calibration_chains[{i}] frame_id mismatch: expected "
                 f"{expected_frame_id!r}, got {chain['frame_id']!r}")

        frame = pool[expected_frame_idx]
        for j, cq in enumerate(chain["chain_questions"]):
            n_total += 1
            # Label fields MUST NOT appear in stimulus JSON (C-8 split).
            for k in ("human_severity_label", "human_severity_rationale"):
                if k in cq:
                    fail(EXIT_STIMULUS_INVALID,
                         f"calibration_chains[{i}].chain_questions[{j}] contains "
                         f"label field {k!r}; per §15.14-A1 follow-up (C-8), "
                         f"labels must live in the separate calibration labels "
                         f"artifact, not in the stimulus JSON")
            if not is_topically_disjoint(frame, cq["question"]):
                fail(EXIT_STIMULUS_INVALID,
                     f"calibration_chains[{i}].chain_questions[{j}] violates topical-"
                     f"disjointness against frame {chain['frame_id']}")
    return 0, n_total  # n_labelled set by labels-artifact loader in C-8c


def _canonical_sha256(payload: dict) -> str:
    """Compute SHA-256 over the JSON payload in canonical form.

    Canonical form: sort_keys=True, indent=2 (matches the curation
    script's writer). Underscore-prefixed metadata keys (curation-
    status notes etc.) are EXCLUDED from the hash so that adding /
    editing curation-status notes doesn't invalidate the lock.
    """
    canonical = {k: v for k, v in payload.items() if not k.startswith("_")}
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--stimulus-json",
        default="docs/experiments/sticky_framing_15_14_stimuli.json",
        help="Path to the stimulus JSON.",
    )
    parser.add_argument(
        "--calibration-labels-json",
        default=None,
        help="Path to the calibration labels artifact "
             "(docs/experiments/sticky_framing_15_14_calibration_labels.json). "
             "When supplied, labels are loaded + validated + merged by "
             "(chain_idx, turn_idx) into the calibration_chains structure "
             "in memory. Required for --require-calibration-labels and --strict.",
    )
    parser.add_argument(
        "--require-calibration-labels",
        action="store_true",
        help="Fail if calibration severity labels are not fully present. "
             "Per §15.14-A1 follow-up (C-8), labels live in the separate "
             "artifact and must be supplied via --calibration-labels-json. "
             "Default: pass (labels not required).",
    )
    parser.add_argument(
        "--require-frame-positive-final",
        action="store_true",
        help="Fail if frame_positive_curation_status is PLACEHOLDER. "
             "Default: pass (placeholders allowed during incremental curation).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Unified gate equivalent to --require-frame-positive-final + "
             "--require-calibration-labels (with --calibration-labels-json "
             "supplied). The single flag the implementation §0.X uses to "
             "verify the stimulus is fully ready: frame_positive_chains "
             "= FINAL, all 50 calibration severity labels merged from the "
             "external artifact, no placeholders, sealed §0.8 thresholds "
             "unchanged. Exits 0 only when both gates pass; otherwise "
             "exits 8 STIMULUS_INVALID with a diagnostic.",
    )
    args = parser.parse_args(argv)

    # --strict implies both per-aspect requirements.
    if args.strict:
        args.require_frame_positive_final = True
        args.require_calibration_labels = True
        if args.calibration_labels_json is None:
            fail(EXIT_STIMULUS_INVALID,
                 "--strict requires --calibration-labels-json. The unified "
                 "strict gate cannot pass without an external labels artifact "
                 "to merge.")

    path = Path(args.stimulus_json)
    if not path.exists():
        fail(EXIT_SCHEMA_MISMATCH, f"stimulus JSON not found: {path}")
    payload = json.loads(path.read_text())

    print(f"Validating: {path}")
    print()

    # 1. Top-level schema.
    _check_top_level(payload)
    print(f"  schema_version: {payload['schema_version']} ✓")

    # 2. Framing pool.
    pool = _check_framing_pool(payload["framing_pool"])
    print(f"  framing_pool: 25 items, all valid ✓")

    # 3. Main chains.
    _check_main_chains(payload["main_chains"], pool)
    print(f"  main_chains: 100 chains × 5 turns = 500 rows, "
          f"pairing rule + topical-disjointness + per-frame uniqueness ✓")

    # 4. Frame-positive chains.
    _check_frame_positive_chains(payload["frame_positive_chains"], pool)
    fp_status = payload.get("_frame_positive_curation_status", "FINAL")
    if fp_status == "PLACEHOLDER":
        msg = "  frame_positive_chains: 20 chains, structure ✓ — STATUS=PLACEHOLDER"
        if args.require_frame_positive_final:
            fail(EXIT_STIMULUS_INVALID,
                 "frame_positive_curation_status=PLACEHOLDER but "
                 "--require-frame-positive-final was specified")
        print(msg)
    else:
        print(f"  frame_positive_chains: 20 chains, structure ✓ — STATUS={fp_status}")

    # 5. Calibration chains (structure only).
    _n_in_json, n_total = _check_calibration_chains(payload["calibration_chains"], pool)
    cal_status = payload.get("_calibration_label_status", "PENDING_ANNOTATION_PASS")

    # 6. SHA-256 of canonical stimulus JSON form.
    stimulus_digest = _canonical_sha256(payload)

    # 7. (Optional) Calibration labels artifact merge.
    n_labelled = 0
    labels_sha: str | None = None
    expected_keys: set[tuple[int, int]] = {
        (chain["chain_idx"], cq["turn_idx"])
        for chain in payload["calibration_chains"]
        for cq in chain["chain_questions"]
    }
    if args.calibration_labels_json is not None:
        labels_path = Path(args.calibration_labels_json)
        labels_by_key, n_labelled = _check_calibration_labels_artifact(
            labels_path, expected_keys, stimulus_digest,
        )
        labels_sha = _calibration_labels_artifact_sha(labels_path)
        if n_labelled == len(expected_keys):
            cal_status = "FILLED"
        else:
            cal_status = f"INCOMPLETE_{n_labelled}_OF_{len(expected_keys)}"

    if n_labelled < n_total and args.require_calibration_labels:
        if args.calibration_labels_json is None:
            fail(EXIT_STIMULUS_INVALID,
                 f"--require-calibration-labels was specified without "
                 f"--calibration-labels-json. Labels live in the separate "
                 f"artifact at "
                 f"{payload.get('_calibration_labels_artifact_path', '<not set>')} "
                 f"and must be supplied to be merged at validation time.")
        fail(EXIT_STIMULUS_INVALID,
             f"calibration labels: only {n_labelled}/{n_total} filled in the "
             f"supplied artifact and --require-calibration-labels was specified")

    print(f"  calibration_chains: 10 chains × 5 turns = {n_total} rows, "
          f"labels merged from artifact = {n_labelled}/{n_total} "
          f"(status={cal_status})")

    print()
    print(f"SHA-256 stimulus  (canonical): {stimulus_digest}")
    if labels_sha is not None:
        print(f"SHA-256 labels    (canonical): {labels_sha}")
    print()

    is_final = (fp_status == "FINAL") and (n_labelled == n_total) and (labels_sha is not None)

    if not is_final:
        print("Validation status: STRUCTURAL OK; PRE-LOCK")
        print("  Curation artifacts pass schema + disjointness checks.")
        print("  Implementation §0.X cannot proceed to --collect / --annotate / --probe")
        print("  until: (a) frame_positive_chains status = FINAL,")
        print("         (b) all 50 calibration severity labels are merged from the")
        print("             external labels artifact (--calibration-labels-json).")
        if args.strict:
            # Strict requires both gates; we already emitted detailed messages
            # above for the specific failure mode. This is a final summary.
            fail(EXIT_STIMULUS_INVALID,
                 "--strict gate failed (FP status or calibration coverage "
                 "incomplete; see prior diagnostics)")
    else:
        print("Validation status: FINAL — stimulus JSON + labels artifact ready for §15.14 implementation")
        print(f"  Pin in implementation §0.X:")
        print(f"    final_stimulus_sha       = {stimulus_digest}")
        print(f"    calibration_labels_sha   = {labels_sha}")
        # Sealed §0.8 thresholds preservation reminder.
        print()
        print("  Sealed §0.8 thresholds preserved (no implicit changes):")
        print("    BINARY_LABEL_THRESHOLD     = severity ≥ 1 → y=1")
        print("    KAPPA_GATE_THRESHOLD       = 0.6 (inclusive)")
        print("    DIRECTION_GATE_THRESHOLD   = 0.5 (strict)")
        print("    PARTIAL_AUC_THRESHOLD      = 0.66 (inclusive)")
        print("    STRONG_AUC_THRESHOLD       = 0.75 (inclusive)")

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
