#!/usr/bin/env python3
"""B1.1 judge run — THIN WRAPPER around the committed B1 judge (`run_b1_llm_judge.py`).

Reuses the FROZEN B1 judge **verbatim**: JUDGE_PROMPT, strict parser (missing-final-brace repair only),
`build_attention_checks` (n=24, seed 90311), the attention-exclusion rule, `LlamaJudgeAdapter`, and the
declared 3-model panel. It ONLY overrides the two module paths so the frozen judge reads the B1.1 blinded
view and writes to a SEPARATE B1.1 output dir (no collision with B1's `b1_judge_responses_*`). **No judge
logic is changed.** Does not modify `run_b1_llm_judge.py`, any frozen artifact, or the freeze manifest, and
does not score or emit a verdict — Track B stays BLOCKED. Structure, not validated meaning.

Usage (on a model-access host, in tmux):
    # 1) smoke first (recommended) — MockJudgeAdapter, NO model, proves the frozen judge consumes the view:
    python3 experiments/primitive_sequence_recovery/run_b1_1_judge.py --mock --limit 5
    # 2) real run (multi-hour, 3 models × ~4224 items, sequential; resumes by default):
    python3 experiments/primitive_sequence_recovery/run_b1_1_judge.py --judge all
Pass-through flags are the frozen judge's own: --judge all|<id> · --mock · --limit N · --no-resume · --tag S
"""
from __future__ import annotations
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_llm_judge as J          # noqa: E402  the FROZEN B1 judge (prompt/parser/attention/panel)

PKTDIR = HERE / "b1_1_judge_packets"
B1_1_VIEW = PKTDIR / "b1_1_judge_view.jsonl"
B1_1_VIEW_MANIFEST = PKTDIR / "b1_1_judge_view_manifest.json"
B1_1_OUT_DIR = HERE / "b1_1_judge_outputs"

# --- the ONLY change vs the frozen B1 judge: point it at the B1.1 view + a separate B1.1 output dir ---
J.JUDGE_VIEW = B1_1_VIEW
J.OUT_DIR = B1_1_OUT_DIR


def _preflight():
    """Wrapper-only integrity guard (does not touch judge logic): the view must exist and match the
    converter's recorded sha256/line-count, so we never judge a stale or edited view."""
    if not B1_1_VIEW.exists():
        raise SystemExit(f"ABORT: {B1_1_VIEW} not found. Run run_b1_1_packets_to_judge_view.py first.")
    if B1_1_VIEW_MANIFEST.exists():
        rec = json.loads(B1_1_VIEW_MANIFEST.read_text(encoding="utf-8"))["B1_1_JUDGE_VIEW_MANIFEST"]
        cur = hashlib.sha256(B1_1_VIEW.read_bytes()).hexdigest()
        if cur != rec.get("judge_view_sha256"):
            raise SystemExit(f"ABORT: judge-view sha256 {cur[:16]} != manifest "
                             f"{str(rec.get('judge_view_sha256'))[:16]} (stale/edited view — re-run the "
                             "converter run_b1_1_packets_to_judge_view.py).")
        n = sum(1 for ln in B1_1_VIEW.read_text(encoding="utf-8").splitlines() if ln.strip())
        if n != rec.get("n_views"):
            raise SystemExit(f"ABORT: view line count {n} != manifest n_views {rec.get('n_views')}.")
        if rec.get("leak_total"):
            raise SystemExit(f"ABORT: view manifest records leak_total {rec.get('leak_total')} — refuse to "
                             "judge a leaked view.")
    else:
        print("[b1.1 judge] WARNING: no view manifest found; skipping sha/line-count integrity guard.")
    B1_1_OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[b1.1 judge] view = {B1_1_VIEW}")
    print(f"[b1.1 judge] out  = {B1_1_OUT_DIR}")
    print("[b1.1 judge] reusing the FROZEN B1 judge verbatim (prompt/parser/attention/panel); "
          "ONLY the input/output paths are overridden. NOT scoring; Track B BLOCKED.")


if __name__ == "__main__":
    _preflight()
    J.main()          # pass-through argv (--judge/--mock/--limit/--no-resume/--tag). Prints provenance.
