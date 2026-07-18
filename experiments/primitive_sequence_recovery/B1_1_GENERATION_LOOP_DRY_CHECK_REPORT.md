# B1.1 Generation Loop Dry-Check Report

## Status: `PASS_DRY_CHECK`

Local dry checks of the implemented B1.1 generation loop. **No real model call, no download, no
generation evidence, no judging, no scoring.** Run in the egress-denied prep environment, where real
generation is intentionally **refused**. **Structure, not validated meaning.**

## Allowed validations

| check | result |
|---|---|
| manifest verifier | **MANIFEST_VERIFIED** (`b1_1_freeze_manifest.json`, FROZEN) |
| freeze artifact validator | **READY_FOR_FREEZE_REVIEW** (0 blockers, 1 judge warning) |
| runner render-only | **PASS_RENDER_ONLY** (200 cores, leak_total 0, 0 empty arms) |

## Refusal-path tests (all refuse; no model contacted)

| id | case | result |
|---|---|---|
| T1 | `--execute-generation` without `B1_1_GENERATION_APPROVED=YES` | **REFUSED** |
| T2 | `--execute-generation` with approval but no `--out` | **REFUSED** |
| T3 | approval + `--out`; render/leak validated OK, then no CUDA/egress | **REFUSED** (render/leak ran first: leak_total 0, 200 cores; **no model contacted**) |
| T7 | existing output without `--resume` | **REFUSED** (never overwrites) |

## Mock loop check (MOCK_ONLY — not evidence)

The `--mock-generation` path exercises the full loop with a **deterministic non-model placeholder** (no
model, no network), written to a scratchpad `mock` path (never committed):

- **4800 rows** written (25 words × 8 arms × 6 tasks × 2 models × 2 seeds), **0 errors**.
- Arms `A/C/D/R_deranged/R_domain/R_same/S/X`; models Mistral-7B-Instruct-v0.3 + Qwen2.5-7B-Instruct;
  seeds `[1101, 2027]`; tasks `T1–T6`.
- **Schema complete** — no missing fields; every row `mock=true`, `status=MOCK_ONLY`,
  `is_b1_1_evidence=false`.
- **0 prompt-text leak rows** (generic Sanskrit/varṇa/meta/arm-label scan).
- **Resume:** re-run with `--resume` skipped **4800/4800** completed keys, wrote 0, never overwrote.

## Output JSONL schema (one row per generation)

`run_id · manifest_sha256 · manifest_path · freeze_commit · model_id · model_revision · task_id ·
target_word · arm · prompt_id · prompt_text · conditioning_text · generation_text · decoding
(temperature/top_p/max_tokens) · seed · timestamp · status · error · key · mock · is_b1_1_evidence`.
Written line-delimited, appended + flushed per row; failures write structured `status:"error"` rows
(never silently skipped); `--resume` skips completed keys.

## Safety confirmations

- real model called: **NO** · generation executed: **NO** · HuggingFace download: **NO**
- raw outputs in repo: **NO** · judging: **NO** · scoring: **NO**
- frozen artifacts modified: **NO** · manifest edited: **NO**
- default mode render-only-safe: **YES** · refuses in this environment: **YES**

## Anchors

B1 verdict `RANDOM_OR_SCRAMBLED_MATCHES` · Track B `BLOCKED` · positive cap `LIMITED_GENERATION_UTILITY`
· crux `R_deranged` · embedding gate `BLOCKED_DEPENDENCY_UNAVAILABLE` · `FALLBACK_QUALIFIED` · Track G
`RANDOM_POLARITY_EXPLAINS` (`1fe5562`).

**Structure, not validated meaning.** Loop implemented and dry-checked; no generation executed, the B1
verdict stands, and Track B remains BLOCKED.
