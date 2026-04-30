# §15.14 framing-stickiness probe — v3 outcome (ANNOTATION_FAILED, §15.14 closes across accessible judges)

## Status

§0.8-binding closure of §15.14 implementation §0.X v3 (under §15.14-A4
logit-first-token-argmax extraction) on branch
`claude/sticky-framing-spec-r6U1j`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate, stimulus + labels SHA
validation, extractions-cache reload (`--force-annotate`),
`LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition (PASSED — Llama-3.1-8B
tokenizer encodes `"0" → 15`, `"1" → 16`, `"2" → 17`), Pass C
single-forward-pass severity extraction (650 rows), and the Pass D
Cohen's κ gate. The κ gate fired at **κ = −0.0776 < 0.6 (inclusive)**,
and the script exited 9 (ANNOTATION_FAILED) before any cascade
computation. The cascade verdict was correctly NOT computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1
ANNOTATION_FAILED closure (commit `2d88be1`) and the §15.14 v2
ANNOTATION_FAILED closure (commit `198378e`).

**Per the user's Path L pre-authorization (recorded in the §15.14-A4
sign-off correspondence):**

> If A4 also fails κ, then close §15.14 as ANNOTATION_FAILED across
> accessible judges.

Accordingly, **§15.14 closes as ANNOTATION_FAILED across all four
tested judge configurations**. The cascade rule is mechanical; we
did not compute a verdict in v1, v2, or v3, and we are not asserting
one. The framing-stickiness hypothesis remains untested at the 7-8B
judge scale on the available hardware envelope.

## §15.x ledger entry (final post-§15.14)

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC=0.661 (saturated) | Single-turn |
| §15.10 | Supervised linear (Z) | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) | Multi-turn |
| §15.14 v1 | Framing-stickiness (R_framing) — JSON-judge prompt | ANNOTATION_FAILED on tested judge configurations | Multi-turn |
| §15.14 v2 (A3) | Framing-stickiness (R_framing) — single-digit prompt + 8-token cap | ANNOTATION_FAILED on Llama-3.1-8B | Multi-turn |
| **§15.14 v3 (A4)** | **Framing-stickiness (R_framing) — logit-first-token-argmax extraction** | **ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.0776)** | **Multi-turn** |

§15.14 across v1 / v2 / v3 does NOT produce a `STRONG_SIGNAL_IN_FRAMING`
/ `PARTIAL_SIGNAL_IN_FRAMING` / `NO_MATERIAL_SIGNAL_IN_FRAMING`
cascade verdict. The cascade was never computed.

## Empirical evidence (§15.14 v3 / §15.14-A4)

### Hardware envelope (runpod, identical to v1 + v2)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total

### v3 / §15.14-A4 fallback judge: meta-llama/Llama-3.1-8B-Instruct

(Effective under §15.14-A2 + §15.14-A3 + §15.14-A4.) Loaded
successfully on the A100-80. Pass C ran over 650 evaluation rows.

| Quantity | Value |
|---|---|
| Judge model | `meta-llama/Llama-3.1-8B-Instruct` |
| `judge_fallback_used` | `true` |
| `judge_extraction_method` | `logit_first_token_argmax` |
| `label_token_ids` | `0 → 15`, `1 → 16`, `2 → 17` |
| `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition | PASSED |
| Pass C extraction | 650 single-forward-pass scores; no `model.generate(...)` |
| `json_parse_failure_rate` (preserved name) | **`0.0000`** (structurally zero under §15.14-A4) |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` (vacuous under A4) |
| Pass D Cohen's κ (judge vs human, 50 calibration rows) | **`−0.0776`** |
| `KAPPA_GATE_THRESHOLD` (inclusive) | `0.6` |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v3)

The §15.14-A4 hypothesis — that removing the format-following confound
via logit-first-token-argmax extraction would yield a κ-passing judge
— is **empirically falsified** at the 7-8B judge scale on this
hardware envelope.

**Crucially, the failure mode under §15.14-A4 is structurally
different from the failure modes under v1 + v2.** Under v1 (JSON
prompt) and v2 (single-digit prompt + 8-token cap), the judge failed
the parse gate before κ could even be computed. Under v3 (A4), parse
failure is structurally zero by construction; the judge produces a
severity for every row, and the empirical question of whether those
severities agree with human labels can be answered. The answer is:
**they do not.**

Cohen's κ = −0.0776 indicates the Llama-3.1-8B-Instruct first-token
argmax over `{token_id_for_"0", token_id_for_"1", token_id_for_"2"}`
on the §15.14 judge prompt is approximately uncorrelated with the
human severity rubric (κ ≈ 0; values slightly below 0 are within
sampling noise of independence on N=50). At 7-8B scale and the
available hardware, the model's rubric-conditioned label preference
at the immediate-next-token position simply does not track the human
distinction between IGNORED / MENTIONED / STRUCTURED.

This is itself a §0.8-binding empirical finding about LLM-as-judge
reliability at this parameter scale. It is independent of any cascade
verdict.

## All judge attempts on §15.14 stimulus + labels artifact (final)

Per user authorization (Path L), this v3 closure document records all
four judge attempts to date as a single final audit-trail table:

| # | Judge configuration | Prompt | Cap | Extraction | Parse failure | κ | Outcome |
|---|---|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2 fallback) | JSON | 128 | generate-and-parse | `0.2692` | n/r | ANNOTATION_FAILED |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2 fallback) | JSON | 128 | generate-and-parse | `0.7077` | n/r | ANNOTATION_FAILED |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit | 8 | generate-and-parse | `0.8477` | n/r | ANNOTATION_FAILED |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit | n/a | logit-first-token-argmax | `0.0000` | **`−0.0776`** | **ANNOTATION_FAILED** |

`n/r` = not reached (Pass D κ gate was not computed because Pass C
parse-failure gate fired first).

**Pattern.** As the judge protocol becomes increasingly faithful to
the rubric-conditioning intent (JSON → single-digit → logit-argmax),
the parse-failure rate decreases monotonically (0.2692 → 0.7077 →
0.8477 → 0.0000). The first three configurations are dominated by
format-following failures at the 7-8B parameter scale; only the
fourth removes that confound entirely. With the format-following
confound removed, the residual κ readout is approximately zero. This
isolates the binding constraint as **rubric discrimination at 7-8B
scale**, not output formatting.

## Artifacts preserved (intact on this branch)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | preserved | v2 closure (commit `198378e`) |
| `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` | this file | v3 closure (final §15.14 closure) |
| `scripts/probe_framing_15_14.py` | ~3470 lines | end-to-end runnable; gates correctly enforced through all four configurations |

**Key preservation under §15.14 final closure:** the extraction cache
`.npz` and all locked artifacts (stimuli, labels, calibration
responses) remain intact. Any future §15.x phase that obtains a
larger judge (e.g. Qwen-2.5-72B-Instruct via 2× A100-80 or
equivalent) can run `python3 scripts/probe_framing_15_14.py
--force-annotate` and reach the cascade in single-digit minutes
without re-running Pass A + Pass B. The multi-turn extraction work,
the human calibration labels, and the §15.14 stimulus design are all
re-usable.

## Spec amendments in §15.14 lifecycle (final)

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |
| §15.14-A3 | EFFECTIVE (parse-falsified by v2) | Replace JSON judge prompt + parser with single-digit prompt + parser; `MAX_NEW_TOKENS_JUDGE: 128 → 8` | `4d18762` |
| §15.14-A4 | EFFECTIVE (κ-falsified by v3) | Replace generation-and-parse extraction with logit-first-token-argmax over `{"0", "1", "2"}` | `dc10d78` |

All four amendments stand and are §0.8-binding. None modified any
sealed threshold (severity rubric, `BINARY_LABEL_THRESHOLD`,
`KAPPA_GATE_THRESHOLD = 0.6 inclusive`, `DIRECTION_GATE_THRESHOLD =
0.5 strict`, `PARTIAL_AUC_THRESHOLD = 0.66 inclusive`,
`STRONG_AUC_THRESHOLD = 0.75 inclusive`, `STRONG_DELTA_AUC_THRESHOLD
= 0.05 inclusive`, `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`), the
cascade structure, the 52-pattern Class-3 firewall, the human
calibration labels, the locked stimulus or labels SHAs, or any
§13/§14/§15.x verdict-of-record.

## What was learned in §15.14 (independent of any cascade verdict)

Three findings stand on their own from §15.14 v1 + v2 + v3 even
without a cascade verdict:

1. **Bimodal severity distribution at the human level.** The
   calibration annotation pass (50 rows, single annotator
   `rasaha-2026-04-30`) produced severity counts of:
   - `0 (IGNORED)`: 28 rows (56%)
   - `1 (MENTIONED)`: 1 row (2%)
   - `2 (STRUCTURED)`: 21 rows (42%)

   Qwen-7B-Instruct's behavior on this stimulus set is bimodal at
   the human level: it either fully ignores the framing convention
   on the post-framing question or fully embraces it, with very
   little middle ground. This observation is independent of any
   geometric prediction by `R_framing` and is preserved across all
   three v1 + v2 + v3 closures.

2. **Format-following failure ladder at 7-8B judge scale.** Three
   pinned-prompt configurations under generation-and-parse extraction
   produced parse-failure rates of (Qwen-7B/JSON) 0.2692, (Llama-8B/
   JSON) 0.7077, (Llama-8B/single-digit-8-tokens) 0.8477. None
   cleared the 5%-inclusive gate. The single-digit instruction was
   *harder* for Llama-3.1-8B than the JSON instruction at this prompt
   complexity, contrary to a-priori expectation; the most likely
   diagnosis is that an 8-token cap (~32 chars at Llama BPE)
   exhausts before preamble-prone instruction-tuned output reaches
   the digit. This is a §0.8-binding empirical finding about LLM-
   as-judge reliability at small scale.

3. **Rubric discrimination is the binding constraint at 7-8B
   scale.** Under §15.14-A4 (logit-first-token-argmax extraction),
   the format-following confound is structurally removed (parse
   failure = 0.0000), and the residual κ readout against human
   labels is `−0.0776` — approximately uncorrelated with the human
   rubric. This isolates the binding constraint as the model's
   ability to *discriminate* IGNORED / MENTIONED / STRUCTURED
   severity levels at all (under any output protocol), rather than
   to express a discriminated judgment under instruction-following
   pressure. A larger judge model (e.g. 70B+ class) is the
   architecturally indicated next step; we are not pursuing that
   step in this §0.X by user election.

None of these findings requires the cascade verdict to be informative.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved. §15.14 v1
ANNOTATION_FAILED closure preserved (commit `2d88be1`). §15.14 v2
ANNOTATION_FAILED closure preserved (commit `198378e`).

§15.14 v3 closes with `ANNOTATION_FAILED on Llama-3.1-8B + §15.14-A4
logit-first-token-argmax extraction (κ = −0.0776 < 0.6 inclusive)`.
§15.14 closes overall with `ANNOTATION_FAILED across all four tested
judge configurations` (per user Path L pre-authorization).

The framing-stickiness hypothesis (whether residual-stream geometry
foretells inappropriate framing recurrence at later turns of a multi-
turn chat) remains **untested** at the 7-8B-judge scale on the
available hardware envelope. The §15.14 stimulus set, calibration
labels, and extraction cache are preserved for any future §0.X that
provisions a larger judge.

## §15.x cross-version status snapshot

| Aspect | Status |
|---|---|
| §15.14 stimulus design | LOCKED, preserved |
| §15.14 calibration labels | LOCKED, preserved |
| §15.14 extraction cache | INTACT, preserved (re-usable) |
| §15.14 self-test gate | PASS (12 cascade + 3 cosine + 52-firewall + disjointness) |
| §15.14 v1 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v2 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v3 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ) |
| §15.14 hypothesis status | UNTESTED across accessible judges |
| §15.14-A1 / A2 / A3 / A4 | All EFFECTIVE; all §0.8-binding |
| All §13 / §14 / §15.10–§15.13 verdicts-of-record | PRESERVED |

## Branch state advance

```
§15_14_V2_CLOSED_AS_ANNOTATION_FAILED_DEFERRED_TO_V3_VIA_§15.14-A4
            ↓ (§15.14-A4 PROPOSED → EFFECTIVE)
§15_14_V3_RUNNING_UNDER_A4_LOGIT_FIRST_TOKEN_ARGMAX
            ↓ (run completed; parse failure 0.0000; κ = −0.0776 < 0.6)
ANNOTATION_FAILED_ON_LLAMA_3_1_8B_A4_LOGIT_KAPPA
            ↓ (Path L pre-authorization; this commit)
§15_14_CLOSED_AS_ANNOTATION_FAILED_ACROSS_ALL_FOUR_TESTED_JUDGE_CONFIGURATIONS
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14 v2 OUTCOME: `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` (commit `198378e`)
- §15.14-A4 PROPOSED: commit `dc37f80`
- §15.14-A4 EFFECTIVE: commit `dc10d78`
- §15.14-A4 v3 logit-first-token-argmax run: parse failure `0.0000`, κ = `−0.0776`, exit 9
- v3 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1 + v2
- All artifacts preserved; no JSON / MD cascade output written (κ-gate fired before writers).

## End of §15.14 (final closure)
