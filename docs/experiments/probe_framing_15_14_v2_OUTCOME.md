# §15.14 framing-stickiness probe — v2 outcome (ANNOTATION_FAILED, deferred to v3)

## Status

§0.8-binding closure of §15.14 implementation §0.X v2 (under §15.14-A3
single-digit judge prompt) on branch `claude/sticky-framing-spec-r6U1j`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate, stimulus + labels SHA
validation, extraction-cache reload (`--force-annotate`), and Pass C
judge inference under the §15.14-A3 single-digit prompt with
`MAX_NEW_TOKENS_JUDGE = 8`. The `ANNOTATION_FAILURE_RATE_THRESHOLD =
0.05` gate fired at `json_parse_failure_rate = 0.8477`, and the
script exited 9 (ANNOTATION_FAILED) before the Pass D κ-gate could
be computed. The cascade verdict was correctly NOT computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1
ANNOTATION_FAILED closure (commit `2d88be1`). §15.14 v2 closes here
with the empirical falsification of the single-digit-judge prompt
hypothesis at the 7-8B parameter scale; cascade computation is
deferred to a v3 §0.X under a new judge architecture (§15.14-A4
authorized, draft PROPOSED in this commit cycle).

**Read-back discipline (per user authorization, this commit):** The
§15.14-A3 single-digit prompt with `MAX_NEW_TOKENS_JUDGE = 8` is
empirically falsified at `json_parse_failure_rate = 0.8477 > 0.05`.
This result is not to be reinterpreted, overwritten, or recharacterized
as a pass.

## §15.x ledger entry

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC=0.661 (saturated) | Single-turn |
| §15.10 | Supervised linear (Z) | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) | Multi-turn |
| §15.14 v1 | Framing-stickiness (R_framing) | ANNOTATION_FAILED on tested judge configurations (JSON prompt) | Multi-turn |
| **§15.14 v2 (§15.14-A3)** | **Framing-stickiness (R_framing) — single-digit-judge prompt** | **ANNOTATION_FAILED on Llama-3.1-8B at 8-token cap** | **Multi-turn** |

§15.14 v2 does NOT produce a `STRONG_SIGNAL_IN_FRAMING` /
`PARTIAL_SIGNAL_IN_FRAMING` / `NO_MATERIAL_SIGNAL_IN_FRAMING` cascade
verdict. The cascade was never computed; the implementation's
ANNOTATION_FAILED gate (exit 9) fired in protocol-compliant order.

## Empirical evidence

### Hardware envelope (runpod, identical to v1)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total

### v2 / §15.14-A3 fallback judge: meta-llama/Llama-3.1-8B-Instruct

(Effective under §15.14-A2 + §15.14-A3.) Loaded successfully on the
A100-80. Pass C ran over 650 evaluation rows.

| Quantity | Value |
|---|---|
| Judge model | `meta-llama/Llama-3.1-8B-Instruct` |
| `judge_fallback_used` | `true` |
| Judge prompt | §15.14-A3 single-digit ("Return EXACTLY ONE CHARACTER: 0, 1, or 2") |
| `MAX_NEW_TOKENS_JUDGE` | `8` (effective under §15.14-A3) |
| Parser | `_try_parse_judge_severity` (first 0/1/2 in first 32 chars) |
| `json_parse_failure_rate` | **`0.8477`** |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` |
| Pass D κ-gate | not reached (Pass C gate fired first) |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v2)

The §15.14-A3 hypothesis — that asking the judge for a single digit
(0/1/2) instead of JSON would lower the parse-failure rate below 5%
— is **empirically falsified**.

Most likely diagnosis: with `MAX_NEW_TOKENS_JUDGE = 8`, Llama-3.1-8B-
Instruct emits ~32 chars (~8 BPE tokens) of natural-language preamble
(e.g. "Based on the framing convention,") and is truncated before
reaching the digit. The parser's "first 0/1/2 in first 32 chars" window
matches the truncation length, so any non-trivial preamble produces a
parse failure. The single-digit instruction is an out-of-distribution
output format for an instruction-tuned model whose RLHF / SFT
distribution favors discursive answers.

This result is consistent with v1 in direction: the parse-failure
rate moved upward (0.7077 → 0.8477) under the simpler-output
instruction. The sub-5% gate is not achievable on Llama-3.1-8B with
generation-and-parse severity extraction, regardless of output-format
simplification.

## All judge attempts on §15.14 stimulus + labels artifact

Per user authorization, this v2 closure document records all judge
attempts to date as a single audit-trail table:

| # | Judge configuration | Prompt | Cap | Parse failure | Gate | Outcome |
|---|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2 fallback) | JSON | 128 | `0.2692` | > 0.05 | ANNOTATION_FAILED |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2 fallback) | JSON | 128 | `0.7077` | > 0.05 | ANNOTATION_FAILED |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit | 8 | `0.8477` | > 0.05 | ANNOTATION_FAILED |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit (logit-first-token) | n/a | `0` (structurally) | κ-gate-only | TBD (v3) |

Row 4 is authorized but not yet executed. The §15.14-A4 amendment
(PROPOSED in the same commit cycle as this document) replaces
generation-and-parse severity extraction with logit-based first-token
scoring, which makes parse-failure rate structurally zero. The Pass D
κ-gate (Cohen's κ ≥ 0.6 inclusive vs human labels) remains binding
under §15.14-A4.

## Artifacts preserved (intact on this branch)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | this file | v2 closure |
| `scripts/probe_framing_15_14.py` | ~3370 lines | end-to-end runnable; gates correctly enforced |

**Key preservation:** the extraction cache `.npz` remains the
expensive artifact and is shared across v1 / v2 / future v3. A v3 §0.X
under §15.14-A4 (logit-first-token judge) can run
`python3 scripts/probe_framing_15_14.py --force-annotate` and reach
the cascade in single-digit minutes (no generation; just per-row
forward pass to logits).

## Spec amendments in §15.14 lifecycle

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |
| §15.14-A3 | EFFECTIVE (falsified by v2) | Replace JSON judge prompt + parser with single-digit prompt + parser; `MAX_NEW_TOKENS_JUDGE: 128 → 8` | `4d18762` |
| §15.14-A4 | PROPOSED (this commit cycle) | Replace generation-and-parse severity extraction with logit-based first-token argmax over `{"0", "1", "2"}` | (this commit) |

§15.14-A3 stands as EFFECTIVE in the spec and is preserved in the
audit trail; the empirical observation is that A3's pinned
configuration (single-digit prompt + 8-token cap) does not pass the
5% failure-rate gate on Llama-3.1-8B-Instruct, which is itself a
§0.8-binding result-of-record. A3 is not retracted; v3 supersedes its
operative path via §15.14-A4 only.

None of these amendments modified any sealed threshold (severity
rubric, `BINARY_LABEL_THRESHOLD`, `KAPPA_GATE_THRESHOLD`,
`DIRECTION_GATE_THRESHOLD`, `PARTIAL_AUC_THRESHOLD`,
`STRONG_AUC_THRESHOLD`, `STRONG_DELTA_AUC_THRESHOLD`,
`ANNOTATION_FAILURE_RATE_THRESHOLD`), the cascade structure, the
52-pattern Class-3 firewall, or any §13/§14/§15.x verdict-of-record.

## What was learned in §15.14 v2 (independent of any cascade verdict)

1. **The single-digit-output instruction is harder for Llama-3.1-8B-
   Instruct than the JSON-output instruction at this prompt
   complexity.** This is the opposite of the §15.14-A3 hypothesis. The
   parse-failure rate moved from 0.7077 (JSON) to 0.8477 (single-digit
   with 8-token cap), a +0.14 increase. This suggests instruction-
   tuned models at this scale produce natural-language preamble even
   when explicitly instructed not to, and that an 8-token cap is
   insufficient to reach the digit through the preamble.

2. **Format-following confounds at small scale.** Across three
   pinned-prompt configurations (Qwen-7B/JSON, Llama-8B/JSON,
   Llama-8B/single-digit-8-tokens), no 7-8B-class instruction-tuned
   judge has cleared the 5% parse-failure gate on the §15.14 prompt.
   The binding constraint at this hardware/parameter scale is
   format-following reliability, not rubric understanding. This is
   the structural motivation for §15.14-A4 (move to logit-based
   scoring, which has no format-following step).

3. **Zero risk of confound contamination.** The Pass D κ-gate (judge
   vs human Cohen's κ ≥ 0.6 inclusive) was never reached on either v1
   or v2. No cascade verdict has been observed; no spurious or
   reinterpreted positive result is present in the §15.14 audit trail.

## v3 path authorized: §15.14-A4 (logit-first-token judge)

By user authorization recorded in this commit cycle, §15.14-A4 is
PROPOSED for v3 only. Its operative content:

- Replace generation-and-parse severity extraction with logit-based
  first-token scoring over candidates `{"0", "1", "2"}`.
- At the first decoder step, compute logits/logprobs for token IDs
  corresponding to those three labels under the active tokenizer.
- `severity = argmax` over those three candidates only.
- Record per-row `(logit_0, logit_1, logit_2)` triples for audit.
- Parse-failure rate is structurally zero by construction.
- The Pass D κ-gate (Cohen's κ ≥ 0.6 inclusive) remains binding;
  failure → exit 9 ANNOTATION_FAILED.
- All sealed thresholds, the cascade structure, the firewall, and
  every prior verdict-of-record are unchanged.

Required reporting under v3 (per user instruction): the v3 outcome
document must list all four judge attempts side-by-side (the three
above + the v3 logit-first-token result).

If §15.14-A4 also fails the κ-gate, §15.14 closes as
ANNOTATION_FAILED across all accessible judge configurations; if it
passes the κ-gate, the cascade verdict is computed without changing
any threshold.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved. §15.14 v1
ANNOTATION_FAILED closure preserved (commit `2d88be1`).

§15.14 v2 closes with `ANNOTATION_FAILED on tested judge
configuration (Llama-3.1-8B + §15.14-A3 single-digit prompt + 8-token
cap)`. The cascade rule is mechanical; we did not compute a verdict
in v2, and we are not asserting one. The framing-stickiness
hypothesis remains untested; v3 under §15.14-A4 is the next attempt.

## Branch state advance

```
§15_14_V1_CLOSED_AS_ANNOTATION_FAILED_ON_TESTED_JUDGES_DEFERRED_TO_V2
            ↓ (§15.14-A3 PROPOSED, then EFFECTIVE)
§15_14_V2_RUNNING_UNDER_A3_SINGLE_DIGIT_PROMPT
            ↓ (run completed; gate fired at 0.8477 > 0.05)
ANNOTATION_FAILED_ON_LLAMA_3_1_8B_A3_SINGLE_DIGIT
            ↓ (user election of Path L; this commit)
§15_14_V2_CLOSED_AS_ANNOTATION_FAILED_DEFERRED_TO_V3_VIA_§15.14-A4
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14-A3 PROPOSED: commit `83e26ee`
- §15.14-A3 EFFECTIVE: commit `4d18762`
- §15.14-A3 single-digit-judge run: `json_parse_failure_rate = 0.8477`, exit 9
- v2 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1
- All artifacts preserved; no JSON / MD cascade output written (gate fired before writers).

## End of §15.14 v2
