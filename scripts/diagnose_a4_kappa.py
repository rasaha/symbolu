"""§15.14-A4 κ-failure diagnostic — DIAGNOSTIC ONLY.

Authorization scope: this script does NOT touch the §15.14 spec, the
sealed thresholds, the calibration labels artifact, the locked
stimulus, the extraction cache, the annotated cache, or any
§13/§14/§15.x verdict-of-record. It reads the existing §15.14-A4
annotated cache (`framing_15_14_annotated.npz`, schema
`15.14-A4-annotated`) and the locked calibration labels JSON, plus
optionally instantiates the active fallback judge tokenizer (no
model load), and emits six diagnostic blocks to stdout that
mechanistically separate the leading hypotheses for the §15.14 v3
κ ≈ 0 outcome (commit `257dd24`).

Wall time target: <5 s.

The six blocks:

  1. Severity histograms (overall, calibration, main, frame_positive)
     — directly probes H4 (constant judge bias).
  2. Confusion matrix on the 50 calibration rows (judge × human).
  3. Three-class Cohen's κ on calibration (cross-check vs the cached
     `calibration_kappa` field; should match `−0.0776` from v3).
  4. Binary-collapse κ on calibration under
     `BINARY_LABEL_THRESHOLD: y = 1 iff severity ≥ 1` — H5 probe.
  5. Per-row triple-logit margin distribution from `judge_logits`
     — H3 proxy (true global-vs-{0,1,2} comparison requires GPU
     rerun and is OUT OF SCOPE).
  6. Tokenizer-form asymmetry probe over the active fallback judge
     tokenizer — H2 diagnostic, no model load.

Exit code is unconditionally 0 (the diagnostic does not gate any
verdict). The script is idempotent and writes nothing.

Usage:

    python3 scripts/diagnose_a4_kappa.py
    python3 scripts/diagnose_a4_kappa.py --tokenizer-only
    python3 scripts/diagnose_a4_kappa.py \
        --annotated-cache docs/experiments/framing_15_14_annotated.npz \
        --labels-json    docs/experiments/sticky_framing_15_14_calibration_labels.json \
        --tokenizer-id   meta-llama/Llama-3.1-8B-Instruct
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_ANNOTATED_NPZ_PATH = Path(
    "docs/experiments/framing_15_14_annotated.npz"
)
DEFAULT_LABELS_JSON_PATH = Path(
    "docs/experiments/sticky_framing_15_14_calibration_labels.json"
)
JUDGE_TOKENIZER_ID = "meta-llama/Llama-3.1-8B-Instruct"  # post-§15.14-A2
LABEL_CHARS = ("0", "1", "2")


def _print_banner(title: str) -> None:
    bar = "=" * 78
    print()
    print(bar)
    print(f"  {title}")
    print(bar)


def _print_section(title: str) -> None:
    print()
    print(f"-- {title} " + "-" * (74 - len(title)))


def _five_number_summary(arr: np.ndarray) -> dict[str, float]:
    if arr.size == 0:
        return {"min": float("nan"), "p25": float("nan"),
                "p50": float("nan"), "p75": float("nan"),
                "max": float("nan"), "mean": float("nan")}
    return {
        "min":  float(np.min(arr)),
        "p25":  float(np.percentile(arr, 25)),
        "p50":  float(np.percentile(arr, 50)),
        "p75":  float(np.percentile(arr, 75)),
        "max":  float(np.max(arr)),
        "mean": float(np.mean(arr)),
    }


_ACCEPTED_ANNOTATED_SCHEMAS = (
    "15.14-A4-annotated",  # pre-§15.14-A5 (raw-string judge prompt render; (n,3) single-token logits)
    "15.14-A5-annotated",  # post-§15.14-A5 EFFECTIVE (chat-template render; (n,3) single-token logits)
    "15.14-A7-annotated",  # post-§15.14-A7 EFFECTIVE (sequence-logprob; (n,9) per-variant + (n,3) per-label aggregated)
    "15.14-A8-annotated",  # post-§15.14-A8 EFFECTIVE (two-stage seq-logprob; (n,12) per-variant + (n,4) per-stage-aggregated)
)


def _load_annotated_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = np.load(path, allow_pickle=True)
    sv = str(data["schema_version"][0])
    if sv not in _ACCEPTED_ANNOTATED_SCHEMAS:
        sys.stderr.write(
            f"[diagnose] WARNING: annotated cache schema_version is "
            f"{sv!r}, expected one of {_ACCEPTED_ANNOTATED_SCHEMAS!r}. "
            f"Diagnostics may be off; proceeding anyway.\n"
        )
    n = len(data["chain_scope"])
    out: dict[str, Any] = {
        "n":            n,
        "chain_scope":  np.array([str(x) for x in data["chain_scope"]]),
        "chain_idx":    np.array(data["chain_idx"]),
        "turn_idx":     np.array(data["turn_idx"]),
        "severity":     np.array(data["severity"]),
        "judge_logits": np.array(data["judge_logits"]),
        "calibration_kappa":          float(data["calibration_kappa"][0]),
        "annotation_failure_rate":    float(data["annotation_failure_rate"][0]),
        "judge_model_id":             str(data["judge_model_id"][0]),
        "judge_fallback_used":        bool(data["judge_fallback_used"][0]),
        "judge_extraction_method":    str(data["judge_extraction_method"][0]),
        "label_token_chars": [str(x) for x in data["label_token_chars"]],
        "label_token_ids":   [int(x)  for x in data["label_token_ids"]],
        "schema_version":             sv,
    }
    # §15.14-A7 cache widens judge_logits to (n, 9) and adds a (n, 3)
    # judge_label_aggregated matrix. Block 5 (margin distribution) needs
    # a (n, 3) array of per-label scores; pre-A7 caches expose it directly
    # in `judge_logits`, while A7 exposes it in `judge_label_aggregated`.
    # Carry both fields through; downstream blocks pick the right one.
    if "judge_label_aggregated" in data.files:
        out["judge_label_aggregated"] = np.array(data["judge_label_aggregated"])
    if "judge_label_variants" in data.files:
        out["judge_label_variants"] = [str(v) for v in data["judge_label_variants"]]
    if "judge_label_aggregation" in data.files:
        out["judge_label_aggregation"] = str(data["judge_label_aggregation"][0])
    return out


def _load_human_labels(path: Path) -> dict[tuple[int, int], int]:
    if not path.exists():
        sys.stderr.write(
            f"[diagnose] WARNING: labels JSON not found at {path}; "
            f"calibration-row blocks (2-4) will be skipped.\n"
        )
        return {}
    with path.open() as f:
        payload = json.load(f)
    if "labels" not in payload:
        sys.stderr.write(
            f"[diagnose] WARNING: labels JSON has no 'labels' key; "
            f"calibration-row blocks (2-4) will be skipped.\n"
        )
        return {}
    out: dict[tuple[int, int], int] = {}
    for rec in payload["labels"]:
        ci = int(rec["chain_idx"])
        ti = int(rec["turn_idx"])
        sev = int(rec["human_severity_label"])
        out[(ci, ti)] = sev
    return out


def _cohen_kappa(y1: np.ndarray, y2: np.ndarray) -> float:
    """Cohen's κ over discrete labels; matches sklearn's default."""
    if y1.shape != y2.shape or y1.size == 0:
        return float("nan")
    labels = sorted(set(np.concatenate([y1, y2]).tolist()))
    L = len(labels)
    idx = {lbl: i for i, lbl in enumerate(labels)}
    n = y1.size
    cm = np.zeros((L, L), dtype=np.float64)
    for a, b in zip(y1, y2):
        cm[idx[int(a)], idx[int(b)]] += 1.0
    p_o = float(np.trace(cm)) / n
    p_e = float((cm.sum(axis=0) @ cm.sum(axis=1)) / (n * n))
    if abs(1.0 - p_e) < 1e-12:
        return float("nan")
    return (p_o - p_e) / (1.0 - p_e)


def _block_1_histograms(cache: dict[str, Any]) -> None:
    _print_section("Block 1 — severity histograms (H4 probe: constant judge bias)")
    scopes = cache["chain_scope"]
    sev = cache["severity"]
    for label, mask in (
        ("ALL ROWS",        np.ones_like(sev, dtype=bool)),
        ("calibration",     scopes == "calibration"),
        ("main",            scopes == "main"),
        ("frame_positive",  scopes == "frame_positive"),
    ):
        s = sev[mask]
        n = int(s.size)
        if n == 0:
            print(f"  {label:<16} N=0 (empty)")
            continue
        c = Counter(int(x) for x in s)
        none_n = c.get(-1, 0)
        zeros = c.get(0, 0)
        ones  = c.get(1, 0)
        twos  = c.get(2, 0)
        valid = n - none_n
        if valid > 0:
            f0 = zeros / valid
            f1 = ones / valid
            f2 = twos / valid
            top = max(f0, f1, f2)
            flag = "  <-- LIKELY_CONSTANT_JUDGE" if top >= 0.95 else ""
        else:
            f0 = f1 = f2 = float("nan")
            top = float("nan")
            flag = ""
        print(
            f"  {label:<16} N={n:<3}  "
            f"sev=0:{zeros:>3} ({f0:.2%})  "
            f"sev=1:{ones:>3} ({f1:.2%})  "
            f"sev=2:{twos:>3} ({f2:.2%})  "
            f"None:{none_n}{flag}"
        )


def _calibration_pairs(
    cache: dict[str, Any], labels_by_key: dict[tuple[int, int], int]
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int]]]:
    """Return (judge_arr, human_arr, keys) over the calibration rows for
    which BOTH a judge severity AND a human label exist. Drops any row
    whose judge severity is None (-1)."""
    mask = cache["chain_scope"] == "calibration"
    chain_idxs = cache["chain_idx"][mask]
    turn_idxs  = cache["turn_idx"][mask]
    sev        = cache["severity"][mask]

    pairs_judge: list[int] = []
    pairs_human: list[int] = []
    pairs_keys:  list[tuple[int, int]] = []
    for ci, ti, jv in zip(chain_idxs, turn_idxs, sev):
        if int(jv) == -1:
            continue
        key = (int(ci), int(ti))
        if key not in labels_by_key:
            continue
        pairs_judge.append(int(jv))
        pairs_human.append(int(labels_by_key[key]))
        pairs_keys.append(key)
    return (
        np.array(pairs_judge, dtype=np.int64),
        np.array(pairs_human, dtype=np.int64),
        pairs_keys,
    )


def _block_2_confusion(j: np.ndarray, h: np.ndarray) -> None:
    _print_section("Block 2 — confusion matrix on 50 calibration rows (judge × human)")
    if j.size == 0:
        print("  (no paired rows; skipped)")
        return
    cm = np.zeros((3, 3), dtype=np.int64)
    for a, b in zip(j, h):
        if 0 <= int(a) <= 2 and 0 <= int(b) <= 2:
            cm[int(a), int(b)] += 1
    print(f"  rows = judge severity ; cols = human severity ; N = {j.size}")
    print(f"           h=0   h=1   h=2   row_sum")
    for i in range(3):
        row = cm[i]
        print(f"  j={i}    {row[0]:>3}   {row[1]:>3}   {row[2]:>3}    {int(row.sum()):>3}")
    col_sums = cm.sum(axis=0)
    print(f"  col_sum  {int(col_sums[0]):>3}   {int(col_sums[1]):>3}   {int(col_sums[2]):>3}    {int(cm.sum()):>3}")
    diag = int(np.trace(cm))
    print(f"  diagonal agreement: {diag}/{int(cm.sum())} = {diag/max(cm.sum(),1):.2%}")


def _block_3_kappa_3class(j: np.ndarray, h: np.ndarray, cached_kappa: float) -> None:
    _print_section("Block 3 — 3-class Cohen's κ on calibration (cross-check vs cached)")
    if j.size == 0:
        print("  (no paired rows; skipped)")
        return
    k = _cohen_kappa(j, h)
    print(f"  recomputed 3-class κ:    {k:+.4f}")
    print(f"  cached calibration_kappa:{cached_kappa:+.4f}  (from annotated .npz)")
    print(f"  delta (recomputed - cached): {(k - cached_kappa):+.6f}")
    if not np.isnan(k):
        print(f"  KAPPA_GATE_THRESHOLD (sealed, inclusive): 0.6 — "
              f"{'PASS' if k >= 0.6 else 'FAIL'}")


def _block_4_kappa_binary(j: np.ndarray, h: np.ndarray) -> None:
    _print_section("Block 4 — binary-collapse κ (y = 1 iff severity ≥ 1)  [H5 probe]")
    if j.size == 0:
        print("  (no paired rows; skipped)")
        return
    j_bin = (j >= 1).astype(np.int64)
    h_bin = (h >= 1).astype(np.int64)
    k_bin = _cohen_kappa(j_bin, h_bin)
    j_pos = int(j_bin.sum())
    h_pos = int(h_bin.sum())
    print(f"  judge positives:  {j_pos}/{j_bin.size} ({j_pos/j_bin.size:.2%})")
    print(f"  human positives:  {h_pos}/{h_bin.size} ({h_pos/h_bin.size:.2%})")
    print(f"  binary-collapse κ: {k_bin:+.4f}")
    if not np.isnan(k_bin):
        print(
            f"  NOTE: the sealed Pass D κ-gate is over the 3-class rubric, "
            f"NOT the binary collapse. Reported here as a side metric only "
            f"(H5 diagnostic). A binary κ ≥ 0.6 would NOT change the §15.14 "
            f"v3 ANNOTATION_FAILED closure; it would, however, route a "
            f"future amendment toward an A6 binary-rubric proposal vs. a "
            f"70B+ judge escalation."
        )


def _block_5_triple_margins(cache: dict[str, Any]) -> None:
    _print_section("Block 5 — per-row decision-margin distribution (H3 PROXY)")
    print("  NOTE: this block computes margin diagnostics on the per-label")
    print("        score vector that drives the argmax. Layout depends on")
    print("        the cache schema:")
    print("          - A4 / A5 / A6: (n, 3) single-token 3-class logits")
    print("          - A7:           (n, 3) 3-class logsumexp scores")
    print("          - A8:           (n, 4) per-stage binary logsumexp scores")
    print("                            (stage1_N, stage1_Y, stage2_M, stage2_S)")
    print("        A true global-top vs {label}-mass comparison still requires a")
    print("        partial GPU rerun and is OUT OF SCOPE for this diagnostic.")

    sv = cache.get("schema_version", "")
    if sv == "15.14-A8-annotated":
        # §15.14-A8: per-stage binary margins. judge_label_aggregated is
        # (n, 4) in column order (stage1_N, stage1_Y, stage2_M, stage2_S);
        # stage 2 cells carry NaN for rows where stage 1 picked N.
        m = cache.get("judge_label_aggregated")
        if m is None or m.ndim != 2 or m.shape[1] != 4:
            print(f"  (unexpected A8 judge_label_aggregated shape: "
                  f"{None if m is None else m.shape}; skipped)")
            return
        print(f"  source: judge_label_aggregated  (per-stage logsumexp; A8 schema {sv!r})")
        n = m.shape[0]
        # Stage 1 margin = |Y - N| (both always present)
        s1_margin = np.abs(m[:, 1] - m[:, 0])
        # Stage 2 margin = |S - M|, masked to rows where stage 1 picked Y
        # (i.e., rows where stage 2 entries are not NaN).
        s2_valid = ~np.isnan(m[:, 2])
        s2_margin = np.abs(m[s2_valid, 3] - m[s2_valid, 2])

        print()
        print(f"  stage1 |Y - N| margin  (always-run; n={n}):")
        s = _five_number_summary(s1_margin)
        print(f"    min={s['min']:.4f}  p25={s['p25']:.4f}  median={s['p50']:.4f}  "
              f"p75={s['p75']:.4f}  max={s['max']:.4f}  mean={s['mean']:.4f}")
        print()
        print(f"  stage2 |S - M| margin  (conditional on stage1=Y; n={int(s2_valid.sum())}):")
        if s2_margin.size == 0:
            print("    (no rows; stage 1 never picked Y)")
        else:
            s = _five_number_summary(s2_margin)
            print(f"    min={s['min']:.4f}  p25={s['p25']:.4f}  median={s['p50']:.4f}  "
                  f"p75={s['p75']:.4f}  max={s['max']:.4f}  mean={s['mean']:.4f}")

        print()
        print("  stage1 margin-floor counts (suggestive of indecisive stage 1):")
        for thr in (0.10, 0.50, 1.00, 2.00):
            c = int(np.sum(s1_margin < thr))
            print(f"    rows with |Y-N| < {thr:>5.2f}: {c:>4}/{n}  ({c/n:.2%})")
        if s2_margin.size > 0:
            print()
            print("  stage2 margin-floor counts (conditional on stage1=Y):")
            n2 = s2_margin.size
            for thr in (0.10, 0.50, 1.00, 2.00):
                c = int(np.sum(s2_margin < thr))
                print(f"    rows with |S-M| < {thr:>5.2f}: {c:>4}/{n2}  ({c/n2:.2%})")
        return

    # Pre-A8 path: 3-class margin diagnostic on (n, 3) score matrix.
    if "judge_label_aggregated" in cache:
        triples = cache["judge_label_aggregated"]
        print(f"  source: judge_label_aggregated  (per-label logsumexp; A7 schema {sv!r})")
    else:
        triples = cache["judge_logits"]
        print(f"  source: judge_logits  (single-token logits; pre-A7 schema {sv!r})")
    if triples.ndim != 2 or triples.shape[1] != 3:
        print(f"  (unexpected per-label score shape: {triples.shape}; skipped)")
        return
    sorted_desc = np.sort(triples, axis=1)[:, ::-1]
    spread     = sorted_desc[:, 0] - sorted_desc[:, 2]   # max - min
    top_margin = sorted_desc[:, 0] - sorted_desc[:, 1]   # max - second_max

    print()
    print("  spread = max - min          (within-3 dispersion)")
    s = _five_number_summary(spread)
    print(f"    min={s['min']:.4f}  p25={s['p25']:.4f}  median={s['p50']:.4f}  "
          f"p75={s['p75']:.4f}  max={s['max']:.4f}  mean={s['mean']:.4f}")

    print()
    print("  top_margin = max - second_max  (winner-vs-runner-up)")
    s = _five_number_summary(top_margin)
    print(f"    min={s['min']:.4f}  p25={s['p25']:.4f}  median={s['p50']:.4f}  "
          f"p75={s['p75']:.4f}  max={s['max']:.4f}  mean={s['mean']:.4f}")

    n = top_margin.size
    print()
    print("  margin-floor counts (suggestive of H3 noise-driven argmax):")
    for thr in (0.10, 0.50, 1.00, 2.00):
        c = int(np.sum(top_margin < thr))
        print(f"    rows with top_margin <{thr:>5.2f}: {c:>4}/{n}  ({c/n:.2%})")


def _block_6_tokenizer_asymmetry(tokenizer_id: str) -> None:
    _print_section(f"Block 6 — tokenizer-form asymmetry probe (H2 diagnostic)")
    print(f"  tokenizer_id: {tokenizer_id}")
    try:
        from transformers import AutoTokenizer  # type: ignore
    except Exception as exc:  # pragma: no cover - transformers is required upstream
        print(f"  (could not import transformers: {exc}; skipped)")
        return
    try:
        tok = AutoTokenizer.from_pretrained(tokenizer_id)
    except Exception as exc:
        print(f"  (could not load tokenizer {tokenizer_id!r}: {exc}; skipped)")
        return

    print()
    print(f"  {'label':<10} {'iso ID(s)':<14} {'sp ID(s)':<14} {'nl ID(s)':<14} {'iso=sp?':<8}")
    for ch in LABEL_CHARS:
        iso = tok.encode(ch,        add_special_tokens=False)
        sp  = tok.encode(" " + ch,  add_special_tokens=False)
        nl  = tok.encode("\n" + ch, add_special_tokens=False)
        same = "yes" if (len(iso) == 1 and len(sp) == 1 and iso[0] == sp[0]) else "no"
        print(f"  {ch!r:<10} {str(iso):<14} {str(sp):<14} {str(nl):<14} {same:<8}")

    print()
    print("  Interpretation: under §15.14-A4 the argmax candidate set is the")
    print("  three iso IDs only. After a chat template, the model's natural")
    print("  first-token continuation often lives at the space-prefixed IDs.")
    print("  If iso=sp? is 'no' for any label (it will be, on Llama-3.1's")
    print("  tiktoken-style BPE), §15.14-A5's H2 fix path is empirically")
    print("  motivated. If sp len > 1 for any label, A5's space-prefixed")
    print("  precondition would correctly fire LABEL_TOKEN_ENCODING_AMBIGUOUS_")
    print("  SPACE_PREFIXED at judge-load on this tokenizer.")


def _print_provenance(cache: dict[str, Any] | None,
                      labels_by_key: dict[tuple[int, int], int]) -> None:
    _print_section("Provenance (read-only inputs to this diagnostic)")
    if cache is None:
        print("  annotated cache:    NOT FOUND (block 1-5 skipped)")
    else:
        print(f"  annotated cache:    OK  (schema={cache['schema_version']!r}, "
              f"N={cache['n']})")
        print(f"    judge_model_id:           {cache['judge_model_id']!r}")
        print(f"    judge_fallback_used:      {cache['judge_fallback_used']}")
        print(f"    judge_extraction_method:  {cache['judge_extraction_method']!r}")
        print(f"    label_token_chars / IDs:  "
              f"{list(zip(cache['label_token_chars'], cache['label_token_ids']))}")
        print(f"    annotation_failure_rate:  {cache['annotation_failure_rate']:.4f}")
        print(f"    cached calibration_kappa: {cache['calibration_kappa']:+.4f}")
    print(f"  human labels:       "
          f"{'OK ('+str(len(labels_by_key))+' entries)' if labels_by_key else 'NOT FOUND (blocks 2-4 skipped)'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="§15.14-A4 κ-failure diagnostic (DIAGNOSTIC ONLY)."
    )
    parser.add_argument(
        "--annotated-cache",
        "--annotated-cache-path",
        dest="annotated_cache",
        default=str(DEFAULT_ANNOTATED_NPZ_PATH),
        help="Path to §15.14-A4 annotated cache .npz (default: %(default)s).",
    )
    parser.add_argument(
        "--labels-json",
        "--labels-path",
        dest="labels_json",
        default=str(DEFAULT_LABELS_JSON_PATH),
        help="Path to calibration labels JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--tokenizer-id",
        default=JUDGE_TOKENIZER_ID,
        help="HF tokenizer to instantiate for block 6 (default: %(default)s).",
    )
    parser.add_argument(
        "--tokenizer-only",
        action="store_true",
        help="Skip cache-driven blocks 1-5; run only block 6 (tokenizer probe).",
    )
    parser.add_argument(
        "--no-tokenizer",
        action="store_true",
        help="Skip block 6 (no transformers / tokenizer load).",
    )
    args = parser.parse_args(argv)

    _print_banner(
        "§15.14-A4 κ-failure diagnostic (DIAGNOSTIC ONLY; reads only; "
        "modifies nothing)"
    )
    print("  Hypotheses probed:")
    print("    H1 chat-template missing      — NOT addressed here (needs model rerun)")
    print("    H2 label-token locus mismatch — block 6 (tokenizer asymmetry)")
    print("    H3 negligible {0,1,2} mass    — block 5 (within-3 margin proxy)")
    print("    H4 constant judge bias        — block 1 (severity histograms)")
    print("    H5 binary-collapse κ          — block 4")

    cache = None if args.tokenizer_only else _load_annotated_cache(
        Path(args.annotated_cache)
    )
    labels_by_key: dict[tuple[int, int], int] = (
        {} if args.tokenizer_only else _load_human_labels(Path(args.labels_json))
    )

    _print_provenance(cache, labels_by_key)

    if cache is not None:
        _block_1_histograms(cache)

        if labels_by_key:
            j, h, _keys = _calibration_pairs(cache, labels_by_key)
            _block_2_confusion(j, h)
            _block_3_kappa_3class(j, h, cache["calibration_kappa"])
            _block_4_kappa_binary(j, h)
        else:
            _print_section("Blocks 2-4 — calibration κ (skipped; labels not found)")

        _block_5_triple_margins(cache)

    if not args.no_tokenizer:
        _block_6_tokenizer_asymmetry(args.tokenizer_id)

    _print_banner(
        "Diagnostic complete. No spec / labels / thresholds / verdicts modified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
