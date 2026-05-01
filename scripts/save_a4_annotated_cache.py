"""§15.14-A4 annotated-cache rescue — DIAGNOSTIC ONLY.

Single-purpose recovery script authorized by the user solely to
recover the per-row §15.14-A4 judge outputs that existed in memory
during the v3 run but were never persisted to disk because the
Pass D κ-gate (κ = −0.0776 < 0.6 inclusive) fired at
`scripts/probe_framing_15_14.py:3293`, which is upstream of the
`_save_annotated_cache(...)` call at `scripts/probe_framing_15_14.py:3296`.

Authorized scope (read this before running):

  - Reads the existing extraction cache
    `docs/experiments/framing_15_14_extractions.npz` (18 MB,
    INTACT per the §15.14 v3 OUTCOME doc).
  - Loads the same A4 fallback judge `meta-llama/Llama-3.1-8B-Instruct`
    via `_load_judge_model(force_fallback=True)`.
  - Runs the same `logit_first_token_argmax` Pass C extraction over
    all 650 rows.
  - Persists the annotated cache to a NON-CANONICAL path
    `docs/experiments/framing_15_14_annotated_A4_diagnostic.npz`
    with a top-level `diagnostic_only=True` marker. The canonical
    annotated path remains absent.
  - Prints severity histograms (overall + calibration), 3-class
    Cohen's κ, binary-collapse κ, and the 3×3 confusion matrix.
  - Does NOT compute the cascade.
  - Does NOT write JSON / MD verdict reports.
  - Does NOT modify `scripts/probe_framing_15_14.py`, the spec,
    the calibration labels artifact, the locked SHAs, the
    extraction cache, or any §13/§14/§15.x verdict-of-record.
  - Does NOT change the §15.14 v3 ANNOTATION_FAILED closure.

Determinism: greedy logits over a fixed prompt + fixed model are
bitwise-identical (modulo trivial floating-point order in batched
ops). The expected κ readout is `−0.0776 ± float64 noise`,
matching the §15.14 v3 OUTCOME closure. The diagnostic value lies
in the per-row severities and per-row 3-cell logits, NOT in the κ
value itself (which we already have on record).

Wall time target: ~5 min on a single A100-80 (650 single forward
passes against Llama-3.1-8B-Instruct at fp16/bf16 auto-cast).

Usage:

    python3 scripts/save_a4_annotated_cache.py
    python3 scripts/save_a4_annotated_cache.py \
        --extraction-cache  docs/experiments/framing_15_14_extractions.npz \
        --stimulus-json     docs/experiments/sticky_framing_15_14_stimuli.json \
        --labels-json       docs/experiments/sticky_framing_15_14_calibration_labels.json \
        --out-path          docs/experiments/framing_15_14_annotated_A4_diagnostic.npz
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# This script intentionally imports the pinned probe module. It does NOT
# modify it; it only re-uses tested code paths (loader, judge loader,
# Pass C, Pass D κ).
import probe_framing_15_14 as P  # type: ignore  # noqa: E402


DEFAULT_OUT_PATH = Path(
    "docs/experiments/framing_15_14_annotated_A4_diagnostic.npz"
)


def _save_diagnostic_annotated_cache(
    severities_by_key: dict[tuple[str, int, int], dict],
    annotation_failure_rate: float,
    calibration_kappa: float,
    judge_model_id: str,
    judge_fallback_used: bool,
    judge_extraction_method: str,
    label_token_ids: dict[str, int],
    out_path: Path,
) -> None:
    """Atomic .npz parallel to `_save_annotated_cache` BUT marked
    `diagnostic_only=True` so the artifact is unambiguously not an
    artifact-of-record. Schema is otherwise identical to
    `15.14-A4-annotated` so that `scripts/diagnose_a4_kappa.py` can
    read it without modification.
    """
    import numpy as np  # local import to mirror probe module's lazy style

    keys = list(severities_by_key.keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)

    severity_vals = np.array(
        [
            (-1 if severities_by_key[k]["severity"] is None
             else int(severities_by_key[k]["severity"]))
            for k in keys
        ],
        dtype=np.int8,
    )
    logits_matrix = np.array(
        [
            [
                float(severities_by_key[k]["judge_logits"][ch])
                for ch in P.LABEL_TOKEN_CHARS
            ]
            for k in keys
        ],
        dtype=np.float64,
    )

    np.savez_compressed(
        tmp_path,
        schema_version=np.array(["15.14-A4-annotated"], dtype=object),
        chain_scope=np.array([k[0] for k in keys], dtype=object),
        chain_idx=np.array([k[1] for k in keys], dtype=np.int64),
        turn_idx=np.array([k[2] for k in keys], dtype=np.int64),
        severity=severity_vals,
        judge_rationale=np.array(
            [severities_by_key[k]["judge_rationale"] or "" for k in keys],
            dtype=object,
        ),
        judge_logits=logits_matrix,
        annotation_failure_rate=np.array([annotation_failure_rate], dtype=np.float64),
        calibration_kappa=np.array([calibration_kappa], dtype=np.float64),
        judge_model_id=np.array([judge_model_id], dtype=object),
        judge_fallback_used=np.array([bool(judge_fallback_used)], dtype=bool),
        judge_extraction_method=np.array([judge_extraction_method], dtype=object),
        label_token_chars=np.array(list(P.LABEL_TOKEN_CHARS), dtype=object),
        label_token_ids=np.array(
            [label_token_ids[ch] for ch in P.LABEL_TOKEN_CHARS], dtype=np.int64,
        ),
        # ---- diagnostic-only markers (NOT in the canonical schema) ----
        diagnostic_only=np.array([True], dtype=bool),
        diagnostic_provenance=np.array(
            [
                "Produced by scripts/save_a4_annotated_cache.py to recover "
                "per-row A4 judge outputs lost when the v3 κ-gate fired at "
                "probe_framing_15_14.py:3293 upstream of the cache writer. "
                "NOT an artifact-of-record. The §15.14 v3 ANNOTATION_FAILED "
                "closure is preserved unchanged."
            ],
            dtype=object,
        ),
    )
    tmp_path.replace(out_path)


def _three_class_kappa(j: list[int], h: list[int]) -> float:
    if not j:
        return float("nan")
    cohen_kappa_score, _ = P._lazy_import_sklearn()
    return float(cohen_kappa_score(h, j))


def _binary_collapse_kappa(j: list[int], h: list[int]) -> float:
    if not j:
        return float("nan")
    cohen_kappa_score, _ = P._lazy_import_sklearn()
    j_bin = [1 if int(x) >= 1 else 0 for x in j]
    h_bin = [1 if int(x) >= 1 else 0 for x in h]
    return float(cohen_kappa_score(h_bin, j_bin))


def _print_summary(
    severities_by_key: dict[tuple[str, int, int], dict],
    labels_by_key: dict[tuple[int, int], dict],
    failure_rate: float,
    cached_kappa: float,
) -> None:
    print()
    print("=" * 78)
    print("  Diagnostic summary (DIAGNOSTIC ONLY; not an artifact-of-record)")
    print("=" * 78)

    # Severity histograms
    overall: Counter[int] = Counter()
    by_scope: dict[str, Counter[int]] = {
        "main": Counter(), "calibration": Counter(), "frame_positive": Counter(),
    }
    for (scope, _ci, _ti), row in severities_by_key.items():
        sev = row["severity"]
        sev_int = -1 if sev is None else int(sev)
        overall[sev_int] += 1
        by_scope.setdefault(scope, Counter())[sev_int] += 1

    def _hist_line(label: str, c: Counter[int]) -> None:
        n = sum(c.values())
        none_n = c.get(-1, 0)
        valid = n - none_n
        f = lambda v: f"{v:>3} ({(v/valid):.2%})" if valid > 0 else f"{v:>3} (---)"
        print(
            f"  {label:<16} N={n:<3}  "
            f"sev=0:{f(c.get(0,0))}  "
            f"sev=1:{f(c.get(1,0))}  "
            f"sev=2:{f(c.get(2,0))}  "
            f"None:{none_n}"
        )

    print()
    print("Block 1 — severity histograms")
    _hist_line("ALL ROWS",       overall)
    _hist_line("calibration",    by_scope.get("calibration", Counter()))
    _hist_line("main",           by_scope.get("main",        Counter()))
    _hist_line("frame_positive", by_scope.get("frame_positive", Counter()))

    # Pair calibration rows with human labels
    j: list[int] = []
    h: list[int] = []
    for (ci, ti), human_row in labels_by_key.items():
        key = ("calibration", ci, ti)
        jr = severities_by_key.get(key)
        if jr is None or jr["severity"] is None:
            continue
        j.append(int(jr["severity"]))
        h.append(int(human_row["human_severity_label"]))
    n_paired = len(j)

    print()
    print("Block 2 — calibration pairing")
    print(f"  paired (judge, human) rows: {n_paired}/{len(labels_by_key)}")

    # Confusion matrix
    print()
    print("Block 3 — confusion matrix on calibration (judge × human)")
    if n_paired == 0:
        print("  (no paired rows)")
    else:
        cm = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for ja, hb in zip(j, h):
            if 0 <= ja <= 2 and 0 <= hb <= 2:
                cm[ja][hb] += 1
        print(f"           h=0   h=1   h=2   row_sum")
        for i in range(3):
            row = cm[i]
            print(f"  j={i}    {row[0]:>3}   {row[1]:>3}   {row[2]:>3}    {sum(row):>3}")
        col_sums = [sum(cm[r][c] for r in range(3)) for c in range(3)]
        total = sum(col_sums)
        diag = sum(cm[i][i] for i in range(3))
        print(f"  col_sum  {col_sums[0]:>3}   {col_sums[1]:>3}   {col_sums[2]:>3}    {total:>3}")
        print(f"  diagonal agreement: {diag}/{total} = {diag/max(total,1):.2%}")

    # κ
    k3 = _three_class_kappa(j, h)
    kbin = _binary_collapse_kappa(j, h)
    print()
    print("Block 4 — Cohen's κ (3-class) on calibration")
    print(f"  recomputed 3-class κ:    {k3:+.4f}")
    print(f"  cached calibration_kappa:{cached_kappa:+.4f}  (from this run; mirrored in v3 OUTCOME)")
    print(f"  delta (recomputed - cached): {(k3 - cached_kappa):+.6f}")
    print(f"  KAPPA_GATE_THRESHOLD (sealed, inclusive): 0.6 — "
          f"{'PASS' if not (k3 != k3) and k3 >= 0.6 else 'FAIL'}")

    print()
    print("Block 5 — binary-collapse κ on calibration  (y = 1 iff severity ≥ 1)")
    print(f"  binary κ: {kbin:+.4f}")
    print("  NOTE: side metric only. The sealed Pass D κ-gate is over the 3-class")
    print("        rubric and is NOT changed by anything in this script.")

    print()
    print(f"Block 6 — provenance")
    print(f"  judge parse-failure rate (structurally 0.0 under §15.14-A4): {failure_rate:.4f}")
    print(f"  artifact written:    DIAGNOSTIC_ONLY")
    print(f"  v3 closure preserved:                                        YES")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "§15.14-A4 annotated-cache rescue (DIAGNOSTIC ONLY). "
            "Re-runs deterministic A4 Pass C from the existing extraction "
            "cache and persists the annotated cache unconditionally. "
            "Does NOT change any §15.14 verdict-of-record."
        )
    )
    parser.add_argument(
        "--extraction-cache",
        default=str(P.DEFAULT_EXTRACTIONS_NPZ_PATH),
        help="Path to the existing extraction cache .npz (default: %(default)s).",
    )
    parser.add_argument(
        "--stimulus-json",
        default=str(P.DEFAULT_STIMULUS_JSON_PATH),
        help="Path to the locked stimulus JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--labels-json",
        default=str(P.DEFAULT_LABELS_JSON_PATH),
        help="Path to the locked calibration labels JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--out-path",
        default=str(DEFAULT_OUT_PATH),
        help=(
            "Path for the diagnostic annotated cache .npz (default: "
            "%(default)s). Must be a non-canonical path; the canonical "
            "annotated path is reserved for artifact-of-record use."
        ),
    )
    parser.add_argument(
        "--force-fallback-judge",
        action="store_true",
        default=True,
        help=(
            "Force the post-§15.14-A2 fallback judge "
            "(meta-llama/Llama-3.1-8B-Instruct). Default ON for parity "
            "with the v3 run; pass --no-force-fallback-judge to disable."
        ),
    )
    parser.add_argument(
        "--no-force-fallback-judge",
        dest="force_fallback_judge",
        action="store_false",
        help="Disable forced fallback (try the default Qwen-72B first).",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out_path)
    canonical = Path("docs/experiments/framing_15_14_annotated.npz")
    if out_path.resolve() == canonical.resolve():
        sys.stderr.write(
            "[save-a4] REFUSING to write to the canonical annotated path "
            f"({canonical}). This script writes only to a clearly non-"
            "canonical diagnostic path. Pass a different --out-path.\n"
        )
        return 2

    print("=" * 78)
    print("  §15.14-A4 annotated-cache rescue (DIAGNOSTIC ONLY)")
    print("=" * 78)
    print(f"  extraction cache:  {args.extraction_cache}")
    print(f"  stimulus JSON:     {args.stimulus_json}")
    print(f"  labels JSON:       {args.labels_json}")
    print(f"  out path:          {args.out_path}  (DIAGNOSTIC ONLY)")
    print(f"  force fallback:    {args.force_fallback_judge}")
    print(f"  judge extraction:  {P.JUDGE_EXTRACTION_METHOD}  (§15.14-A4)")

    print()
    print("[save-a4] validating stimulus + labels (lock pin) ...")
    payload, stim_sha = P._validate_stimulus_json(Path(args.stimulus_json))
    _labels_payload, labels_sha, labels_by_key = P._validate_calibration_labels_json(
        Path(args.labels_json),
        expected_sha=P.EXPECTED_LABELS_SHA,
        stimulus_sha=stim_sha,
    )
    print(f"  stimulus_sha256:           {stim_sha}")
    print(f"  calibration_labels_sha256: {labels_sha}")

    print()
    print(f"[save-a4] loading extraction cache → {args.extraction_cache} ...")
    extractions = P.load_extractions_cache(
        Path(args.extraction_cache), expected_stimulus_sha=stim_sha,
    )
    print(f"  loaded {len(extractions)} chains "
          f"(expected {P.N_MAIN_CHAINS + P.N_FRAME_POSITIVE_CHAINS + P.N_CALIBRATION_CHAINS})")

    print()
    print("[save-a4] loading judge model (post-§15.14-A2 fallback) ...")
    tokenizer, model, judge_id_used, used_fallback, label_token_ids = P._load_judge_model(
        force_fallback=args.force_fallback_judge,
    )
    print(f"  judge_model_id:           {judge_id_used!r}")
    print(f"  judge_fallback_used:      {used_fallback}")
    print(f"  judge_extraction_method:  {P.JUDGE_EXTRACTION_METHOD!r}")
    print(f"  label_token_ids:          "
          + ", ".join(f"{ch}→{label_token_ids[ch]}" for ch in P.LABEL_TOKEN_CHARS))

    print()
    print("[save-a4] running Pass C (logit-first-token-argmax over 650 rows) ...")
    severities_by_key, failure_rate = P.run_pass_c_judge(
        tokenizer, model, extractions, payload, label_token_ids,
    )
    print(f"  Pass C complete; rows = {len(severities_by_key)}; "
          f"parse-failure rate = {failure_rate:.4f} (structurally 0.0 under §15.14-A4)")

    print()
    print("[save-a4] running Pass D (Cohen's κ on 50 calibration rows) — observation only ...")
    kappa = P.run_pass_d_kappa_gate(severities_by_key, labels_by_key)
    print(f"  κ = {kappa:.4f}  (§15.14 v3 OUTCOME doc records κ = -0.0776; expected match modulo float64 noise)")
    print("  NOTE: this script does NOT enforce the κ-gate. The cache is")
    print("        saved unconditionally for diagnostic recovery. The §15.14")
    print("        v3 ANNOTATION_FAILED closure is preserved unchanged.")

    print()
    print(f"[save-a4] saving diagnostic annotated cache → {out_path} ...")
    _save_diagnostic_annotated_cache(
        severities_by_key=severities_by_key,
        annotation_failure_rate=failure_rate,
        calibration_kappa=kappa,
        judge_model_id=judge_id_used,
        judge_fallback_used=used_fallback,
        judge_extraction_method=P.JUDGE_EXTRACTION_METHOD,
        label_token_ids=label_token_ids,
        out_path=out_path,
    )
    print(f"  wrote {out_path}  (diagnostic_only=True)")

    _print_summary(severities_by_key, labels_by_key, failure_rate, kappa)

    print()
    print("=" * 78)
    print("  Recovery complete. No spec / labels / thresholds / cascade /")
    print("  firewall / verdict-of-record modified. §15.14 v3 ANNOTATION_FAILED")
    print("  closure preserved unchanged. Next step: run")
    print("    python3 scripts/diagnose_a4_kappa.py \\")
    print(f"      --annotated-cache {out_path} \\")
    print(f"      --labels-json     {args.labels_json} \\")
    print(f"      --tokenizer-id    meta-llama/Llama-3.1-8B-Instruct")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    # Ensure scripts/ is on sys.path so `import probe_framing_15_14` works
    # when the script is invoked from the repo root.
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    raise SystemExit(main())
