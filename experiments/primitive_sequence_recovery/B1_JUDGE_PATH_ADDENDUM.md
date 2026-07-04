# B1 Judge-Path Addendum — BINDING PRE-RUN DECLARATION

**Status:** `JUDGE_PATH_DECLARED_D1_LLAMA_PANEL`
**Declared (UTC):** 2026-07-04T07:53:48Z — recorded **before** any judgment is produced (pre-run; avoids `INVALID_POSTHOC`).
**Not an edit to any frozen B0 artifact.** The frozen prereg is one of the 11 hashed files and is left
untouched; this addendum declares only the field B0 left open — the **judge identity**.

Provenance: freeze record `04cdd9d` · packet build `611e5d8` · raw outputs sha256 `e2930149…` ·
judge_view sha256 `f795707a…` · draft `45fd69f`.

---

## Declaration

- **judge_path:** `LLM_JUDGE`
- **panel_type:** `D1_DISTINCT_LLAMA_CHECKPOINTS`
- **n_judges:** `3`
- **judge checkpoints (Llama family; distinct from generation families Mistral + Qwen):**
  - `meta-llama/Llama-3.1-8B-Instruct`
  - `meta-llama/Meta-Llama-3-8B-Instruct`
  - `meta-llama/Llama-3.2-3B-Instruct`
- **Mistral and Qwen MUST NOT be used as judges** (self-preference / family-bias guard).

### Decode (locked)
- **greedy / deterministic**
- **temperature:** `0`
- **top_p:** `1`
- **max_tokens:** enough for the structured JSON response only (no prose budget)
- **no chain-of-thought output** — the judge returns a **structured JSON response only**

### What the judge sees (blinding)
- Only the blinded `b1_judge_view.jsonl` (`display_id`, `key_word`, `task_text`, two neutrally-labelled
  outputs).
- The judge **must not** see: arm labels, model IDs, seeds, conditioning text, raw/full packet
  metadata, or internal packet IDs.

### Response schema (structured JSON only)
```json
{"choice": "<one of: output_1_better | output_2_better | tie_no_preference | both_bad>",
  "reason": "<optional short reason>"}
```
- **choices:** `output_1_better`, `output_2_better`, `tie_no_preference`, `both_bad`
- **Scoring uses ONLY the `choice` field.** `tie_no_preference` and `both_bad` → 0.5 (both-bad also
  separately flagged). A short `reason` MAY be recorded for audit but is **not** used for scoring.
- Unparseable / schema-violating reply → `tie_no_preference` (0.5) and flagged.
- Position bias is mitigated by the **frozen** left/right randomization (seed `50513`) already applied
  per packet.

### Frozen protocol carried over (unchanged, from B0)
- Pairwise forced choice A vs each of D/R/S/C/X; `n_judges = 3`; tie = 0.5; both-bad = 0.5 and flagged.
- Attention-check exclusion: exclude a judge failing **>1** OR **>25%** of attention checks (stricter),
  applied **before** outcome analysis; inter-judge agreement reported.
- Aggregation: item-clustered win-rate → paired bootstrap (`n_boot=2000`, seed `60617`) →
  Holm–Bonferroni across the 5 co-primaries → CI lower bound > 0.5 each. A must beat **all five**.

### Evidence status (honest scope)
- These are **8B/3B-class** judges. The result is an **internal LLM-judge evaluation**, NOT
  final human-validated evidence.
- **If the outcome is positive, human replication is required before any strong claim.**
- Does not unblock Track B. Prior stands: Track G `RANDOM_POLARITY_EXPLAINS`, Track F
  `CORRECTNESS_DEGRADED`; the judge is not tuned to rescue A.

## Operator prerequisites (pod, before the run)
- Accept the Meta Llama licenses on Hugging Face and `huggingface-cli login` with an authorized token.

`B0 FROZEN · B1 generation complete · packets blinded · NOT judged · NOT scored · Track B BLOCKED.`
Structure, not validated meaning.
