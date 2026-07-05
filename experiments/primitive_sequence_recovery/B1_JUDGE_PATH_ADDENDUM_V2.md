# B1 Judge-Path Addendum V2 — PANEL AMENDMENT (binding, pre-run for the new judge)

**Status:** `JUDGE_PATH_AMENDED_V2`
**Declared (UTC):** 2026-07-04T12:52:32Z — recorded **before** the replacement judge sees any packet (pre-run; avoids `INVALID_POSTHOC`).
**Supersedes** the panel in `B1_JUDGE_PATH_ADDENDUM.md` (V1, `b13ac74`). Frozen prereg still untouched.
Selection of the replacement is on **blind competence only** (parse rate + planted attention checks),
never on how any judge rules A vs controls — so it cannot bias the outcome.

Provenance: freeze `04cdd9d` · packets `611e5d8` · V1 declaration `b13ac74` · brace-repair fix `400f7af`.

---

## Why the panel changed (full, honest trail)

The V1 panel was three Llama checkpoints. The first judging run produced two exclusions. Investigation
(raw judge text was saved) showed **two different causes**:

1. **`meta-llama/Meta-Llama-3-8B-Instruct` — HARNESS bug, not the judge.** Its replies were complete,
   correct JSON verdicts **missing only the final closing brace** (the model stopped one token early).
   The parser wrongly rejected them → fallback ties → attention-check failures. Fixed with a **narrow
   safe repair** (`400f7af`): strict parse first; repair *only* a missing final brace when all required
   keys are present exactly once with valid values; raw preserved; repairs flagged. Re-smoke: **98%
   parse, 0/24 attention fails → RETAINED as a competent judge.**

2. **`meta-llama/Llama-3.2-3B-Instruct` — GENUINE QC failure, not the parser.** Even after the fix it
   still failed (~40% parse, 21/24 attention). Its raw shows it **echoing the entire option-list as its
   answer** (choice set to `output_1_better|output_2_better|tie_no_preference|both_bad` rather than one
   value) — a real instruction-following failure of a 3B model (J1 and J2 handle the same prompt fine).
   **Not repaired** (repairing would fabricate a pick the model never made). **DROPPED.**

## Amended panel (n = 3)

- **judge_path:** `LLM_JUDGE`
- **panel_type:** `D1_V2_MIXED_FAMILY` (two distinct Llama generations + one Gemma)
- **n_judges:** `3`
- **judges:**
  - `meta-llama/Llama-3.1-8B-Instruct`    (retained; competent)
  - `meta-llama/Meta-Llama-3-8B-Instruct` (retained; competent after the brace-repair fix)
  - `google/gemma-2-9b-it`   **(replacement for Llama-3.2-3B)** — capable instruction-follower,
    **distinct family** (Gemma), which also improves inter-rater diversity over the all-Llama V1 panel.
- **Bias guard unchanged:** the judge family must be **distinct from the generation families Mistral and
  Qwen**; Mistral and Qwen remain barred as judges. Gemma satisfies this.

## Everything else unchanged (from B0 + V1)
- Decode: greedy / temperature 0 / top_p 1; structured JSON only; no chain-of-thought.
  (`max_new_tokens` raised 96→384 as headroom; still JSON-only.)
- Blinding: judge sees only `b1_judge_view.jsonl` (task + two neutral outputs).
- Choices `output_1_better | output_2_better | tie_no_preference | both_bad`; **scoring uses only
  `choice`**; tie/both_bad → 0.5 (both_bad flagged). Unparseable/invalid → tie (0.5), flagged.
- Attention-check exclusion (fail >1 OR >25%, stricter), applied before analysis; inter-judge agreement
  reported. Aggregation: item-clustered win-rate → paired bootstrap (`n_boot=2000`, seed `60617`) →
  Holm–Bonferroni across the 5 co-primaries; A must beat **all five**.

## Execution note
- All earlier judge runs (old parser) are **discarded**. The final panel is produced by a **full
  re-judge under the fixed parser** (`400f7af`, `--tag v2`, fresh files) so all three judges run under
  identical conditions.
- **Gemma is gated on HF** — accept its license + `huggingface-cli login`. It is **smoke-tested first**;
  if it fails blind QC, it is replaced (next candidate: `microsoft/Phi-3.5-mini-instruct`) via a further
  pre-run amendment — never patched to pass.

## Evidence status (unchanged, honest scope)
8B/9B-class judges → **internal LLM-judge evaluation**, not human-validated evidence. If positive, human
replication required before any strong claim. Does **not** unblock Track B. Prior stands: Track G
`RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`; judges are not tuned to rescue A.

`B0 FROZEN · packets blinded · panel amended pre-run · NOT judged (final) · NOT scored · Track B BLOCKED.`
Structure, not validated meaning.
