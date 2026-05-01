# §15.14 framing-stickiness probe — v4 outcome (ANNOTATION_FAILED, §15.14-A5 H1 fix empirically falsified at 8B scale)

## Status

§0.8-binding closure of §15.14 implementation §0.X v4 (under
§15.14-A5 chat-template-render judge protocol) on branch
`claude/diagnose-framing-kappa-L6dmt`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate (4/4 PASS), stimulus + labels
SHA validation, extractions-cache reload (`--force-annotate`),
`LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition (PASSED — Llama-3.1-8B
tokenizer encodes `"0" → 15`, `"1" → 16`, `"2" → 17`), Pass C
single-forward-pass severity extraction (650 rows under §15.14-A5
chat-template render), and the Pass D Cohen's κ gate. The κ gate
fired at **κ = −0.3840 < 0.6 (inclusive)**, and the script exited 9
(ANNOTATION_FAILED) before any cascade computation. The cascade
verdict was correctly NOT computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1
ANNOTATION_FAILED closure (commit `2d88be1`), the §15.14 v2
ANNOTATION_FAILED closure (commit `198378e`), and the §15.14 v3
ANNOTATION_FAILED closure (commit `257dd24`). The §15.14-A4
diagnostic findings recovered into
`docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` on
RunPod are preserved unchanged.

**Per the user's bounded sign-off recorded in the §15.14-A5
EFFECTIVE correspondence (commit `b11b3e2`):**

> If κ < 0.6, record A5 as ANNOTATION_FAILED and treat H1 as ruled
> out for the accessible 8B judge.
> Do not reinterpret v1/v2/v3 failures.
> Do not overwrite A4 diagnostic findings.
> Do not escalate to 70B in this step.
> Do not author A6 unless separately authorized.

Accordingly, **§15.14 v4 closes as ANNOTATION_FAILED with H1
(rendering-protocol mismatch) ruled out as the binding constraint
for the accessible 8B judge.** The cascade rule is mechanical; we
did not compute a verdict in v1, v2, v3, or v4, and we are not
asserting one. The framing-stickiness hypothesis remains untested
at the 7-8B judge scale on the available hardware envelope. No
70B escalation is taken in this OUTCOME; no §15.14-A6 is authored.

## §15.x ledger entry (final post-§15.14 v4)

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC=0.661 (saturated) | Single-turn |
| §15.10 | Supervised linear (Z) | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) | Multi-turn |
| §15.14 v1 | Framing-stickiness — JSON-judge prompt | ANNOTATION_FAILED on tested judge configurations | Multi-turn |
| §15.14 v2 (A3) | Framing-stickiness — single-digit prompt + 8-token cap | ANNOTATION_FAILED on Llama-3.1-8B | Multi-turn |
| §15.14 v3 (A4) | Framing-stickiness — logit-first-token-argmax raw-string render | ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.0776) | Multi-turn |
| **§15.14 v4 (A5)** | **Framing-stickiness — logit-first-token-argmax + chat-template render (H1 fix)** | **ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.3840)** | **Multi-turn** |

§15.14 across v1 / v2 / v3 / v4 does NOT produce a
`STRONG_SIGNAL_IN_FRAMING` / `PARTIAL_SIGNAL_IN_FRAMING` /
`NO_MATERIAL_SIGNAL_IN_FRAMING` cascade verdict. The cascade was
never computed.

## Empirical evidence (§15.14 v4 / §15.14-A5)

### Hardware envelope (runpod, identical to v1 / v2 / v3)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total

### v4 / §15.14-A5 fallback judge configuration

(Effective under §15.14-A2 + §15.14-A3 + §15.14-A4 + §15.14-A5.)
Loaded successfully on the A100-80. Pass C ran over 650 evaluation
rows with the chat-template-rendered prompt protocol.

| Quantity | Value |
|---|---|
| Judge model | `meta-llama/Llama-3.1-8B-Instruct` |
| `judge_fallback_used` | `true` |
| `judge_extraction_method` | `logit_first_token_argmax` |
| `judge_prompt_render` | `apply_chat_template_user_only(add_generation_prompt=True)` (effective under §15.14-A5; was `raw_string` under §15.14-A4) |
| `label_token_ids` | `0 → 15`, `1 → 16`, `2 → 17` |
| `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition | PASSED |
| Pass C extraction | 650 single-forward-pass scores; no `model.generate(...)` |
| `json_parse_failure_rate` (preserved name) | **`0.0000`** (structurally zero; A4 inheritance) |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` (vacuous under A4 / A5) |
| Pass D Cohen's κ (judge vs human, 50 calibration rows) | **`−0.3840`** |
| `KAPPA_GATE_THRESHOLD` (inclusive) | `0.6` |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v4)

The §15.14-A5 hypothesis — that wrapping the unchanged
`JUDGE_PROMPT_TEMPLATE` through `tokenizer.apply_chat_template(...,
add_generation_prompt=True)` (placing the first-token logit
readout at the post-`<|end_header_id|>\n\n` position the model's
first-token distribution is calibrated for) would yield a
κ-passing 8B judge — is **empirically falsified**.

**Notable: the κ moved further from agreement, not closer.**
Under §15.14-A4 raw-string render, κ = `−0.0776` (approximately
uncorrelated with human rubric on N = 50). Under §15.14-A5
chat-template render, κ = `−0.3840` (systematically
anti-correlated with human rubric). The H1 fix made the judge
more confident — and that confidence is more anti-correlated with
the human distribution.

The most natural mechanistic interpretation, consistent with the
§15.14-A4 diagnostic findings recorded on RunPod via
`scripts/save_a4_annotated_cache.py` + `scripts/diagnose_a4_kappa.py`:
under raw-string render, the judge's first-token logit row at the
OOD raw-tail position carried minimal rubric-conditioned signal
(per the §15.14-A4 diagnostic block 5: median within-{0,1,2}
top-margin ≈ 1.4 logits, but the within-3 argmax distribution was
heavily class-1-biased — judge picked MENTIONED 34/50 calibration
rows where human picked MENTIONED 1/50). Under chat-template
render the judge is in-distribution; the rubric-conditioned signal
is now strong, but the model's rubric mapping at 8B scale is
systematically misaligned with the human's, and κ moves negative.
Placing the judge in-distribution **strengthens** the
miscalibration rather than correcting it.

H1 is therefore ruled out as the binding constraint at the 8B
parameter scale on this stimulus set. The remaining hypotheses for
the κ failure are:

  - **Two-token-marginal H2** (deferred to a future §15.14-A6
    PROPOSED amendment; **NOT** authorized in this OUTCOME).
  - **H3 global-vocab mass on `{15, 16, 17}` is negligible** (a
    proper test requires a partial GPU rerun with full-vocab
    log-softmax at the final position; the §15.14-A4 diagnostic
    block 5 within-3 margin probe was a proxy and noted as such).
  - **Deeper rubric-discrimination disagreement at 7-8B scale**
    (would require a 70B+ judge under separate authorization).

This is itself a §0.8-binding empirical finding-of-record about
LLM-as-judge reliability at this parameter scale: format-following
confound (v1 / v2 parse failure) is removable by logit-based
extraction; rendering-protocol confound (v3 raw-string) is
removable by chat-template wrapping; rubric-discrimination
disagreement persists across both removals, and the H1 fix amplifies
the disagreement rather than correcting it. It is independent of
any cascade verdict.

## All judge attempts on §15.14 stimulus + labels artifact (final post-v4)

Per the §15.14-A5 PROPOSED block's required-reporting clause:

| # | Judge configuration | Prompt | Cap | Render | Extraction | Parse failure | κ | Outcome |
|---|---|---|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2) | JSON | 128 | raw-string | generate-and-parse | `0.2692` | n/r | ANNOTATION_FAILED |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2) | JSON | 128 | raw-string | generate-and-parse | `0.7077` | n/r | ANNOTATION_FAILED |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit | 8 | raw-string | generate-and-parse | `0.8477` | n/r | ANNOTATION_FAILED |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit | n/a | raw-string | logit-first-token-argmax | `0.0000` | `−0.0776` | ANNOTATION_FAILED |
| 5 | meta-llama/Llama-3.1-8B-Instruct (post-A5) | single-digit | n/a | apply_chat_template | logit-first-token-argmax | `0.0000` | **`−0.3840`** | **ANNOTATION_FAILED** |

`n/r` = not reached (Pass D κ gate was not computed because Pass C
parse-failure gate fired first).

**Pattern (final).** Removing the format-following confound
(rows 1-3 → row 4) drops parse-failure rate from {0.27, 0.71, 0.85}
to structurally `0.0000` but leaves κ ≈ 0. Adding the H1
chat-template fix on top of logit-based extraction (row 4 → row 5)
places the judge in-distribution at the post-`<|end_header_id|>`
position and **increases the magnitude of κ** (`−0.0776` →
`−0.3840`) **in the negative direction**: the in-distribution 8B
judge is decisive, but its decisions are systematically
anti-correlated with the human rubric on this stimulus set. The
binding constraint is rubric discrimination at the 7-8B parameter
scale, not output formatting and not prompt-render position.

## Artifacts preserved (intact on this branch + on RunPod)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` | tens of KB | DIAGNOSTIC ONLY (preserved on RunPod from §15.14-A4 cache rescue; **not modified** by v4 run) |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | preserved | v2 closure (commit `198378e`) |
| `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` | preserved | v3 closure (commit `257dd24`) |
| `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` | this file | v4 closure (this commit) |
| `scripts/probe_framing_15_14.py` | ~3500 lines | end-to-end runnable; gates correctly enforced through five judge configurations |
| `scripts/diagnose_a4_kappa.py` | ~470 lines | DIAGNOSTIC ONLY; reads §15.14-A4 / §15.14-A5 annotated caches |
| `scripts/save_a4_annotated_cache.py` | ~430 lines | DIAGNOSTIC ONLY; rescues annotated caches when κ-gate fires upstream of writer |

**Key preservation under v4 closure.** Per the same control flow
as v3, the κ-gate exit at `scripts/probe_framing_15_14.py:3293` fires
upstream of `_save_annotated_cache` at
`scripts/probe_framing_15_14.py:3296`, so no canonical annotated
cache for v4 was written to disk. The per-row v4 severities and
3-cell `judge_logits` (under chat-template render) are recoverable
via `scripts/save_a4_annotated_cache.py` (which now operates under
the active `_judge_one_row` code path = post-§15.14-A5
chat-template render; the runtime banner explicitly warns of this).
Such a v4 diagnostic-cache rescue is **NOT** executed in this
OUTCOME and would require separate authorization, parallel to the
authorization that produced
`framing_15_14_annotated_A4_diagnostic.npz`.

**Note on segfault at run end.** The v4 run terminated with exit
code 9 (ANNOTATION_FAILED) followed by a segmentation fault during
Python interpreter shutdown ("Segmentation fault (core dumped)").
The exit code preceded the segfault; the κ-gate decision and the
outcome-of-record are both unaffected. The segfault is consistent
with HF Transformers / Llama model destructor ordering during
interpreter cleanup on this hardware envelope and does not indicate
any data-integrity issue with Pass C / Pass D.

## Spec amendments in §15.14 lifecycle (final post-v4)

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |
| §15.14-A3 | EFFECTIVE (parse-falsified by v2) | Replace JSON judge prompt + parser with single-digit prompt + parser; `MAX_NEW_TOKENS_JUDGE: 128 → 8` | `4d18762` |
| §15.14-A4 | EFFECTIVE (κ-falsified by v3) | Replace generation-and-parse extraction with logit-first-token-argmax over `{"0", "1", "2"}` | `dc10d78` |
| **§15.14-A5** | **EFFECTIVE (κ-falsified by v4)** | **Wrap unchanged `JUDGE_PROMPT_TEMPLATE` through `tokenizer.apply_chat_template(..., add_generation_prompt=True)`; argmax candidate set unchanged from A4** | **`b11b3e2`** |

All five amendments stand and are §0.8-binding. None modified any
sealed threshold (severity rubric, `BINARY_LABEL_THRESHOLD`,
`KAPPA_GATE_THRESHOLD = 0.6 inclusive`, `DIRECTION_GATE_THRESHOLD =
0.5 strict`, `PARTIAL_AUC_THRESHOLD = 0.66 inclusive`,
`STRONG_AUC_THRESHOLD = 0.75 inclusive`, `STRONG_DELTA_AUC_THRESHOLD
= 0.05 inclusive`, `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`), the
cascade structure, the 52-pattern Class-3 firewall, the human
calibration labels, the locked stimulus or labels SHAs, or any
§13/§14/§15.x verdict-of-record.

## What was learned in §15.14 (independent of any cascade verdict, post-v4)

Five findings stand on their own from §15.14 v1 + v2 + v3 + v4
even without a cascade verdict:

1. **Bimodal severity distribution at the human level.** The
   calibration annotation pass (50 rows, single annotator
   `rasaha-2026-04-30`) produced severity counts of:
   - `0 (IGNORED)`: 28 rows (56%)
   - `1 (MENTIONED)`: 1 row (2%)
   - `2 (STRUCTURED)`: 21 rows (42%)

   Qwen-7B-Instruct's behavior on this stimulus set is bimodal at
   the human level. Preserved across v1 / v2 / v3 / v4.

2. **Format-following failure ladder at 7-8B judge scale.** Three
   pinned-prompt configurations under generation-and-parse
   extraction produced parse-failure rates of (Qwen-7B/JSON)
   `0.2692`, (Llama-8B/JSON) `0.7077`, (Llama-8B/single-digit-8-tokens)
   `0.8477`. None cleared the 5%-inclusive gate. Logit-based
   extraction structurally removes parse failure to `0.0000`.
   Preserved.

3. **Rubric discrimination is the binding constraint at 7-8B
   scale, AND chat-template render strengthens not weakens that
   constraint.** Under §15.14-A4 (raw-string), κ = `−0.0776`
   (≈uncorrelated). Under §15.14-A5 (chat-template), κ = `−0.3840`
   (anti-correlated). The H1 rendering-protocol fix is empirically
   falsified as a sufficient remedy at 8B scale. The 8B judge's
   rubric-conditioned first-token preference is decisive (not
   noise: the §15.14-A4 diagnostic block 5 measured median
   within-{0,1,2} top-margin ≈ 1.4 logits) AND systematically
   misaligned with the human distribution; placing the judge
   in-distribution amplifies that misalignment.

4. **The single-token surface-variant H2 mechanism is structurally
   infeasible against the post-A2 fallback judge tokenizer.**
   `" 0"`, `" 1"`, `" 2"` each encode as `[220, X]` under
   `meta-llama/Llama-3.1-8B-Instruct`'s tiktoken-style BPE;
   `"\n0"`, `"\n1"`, `"\n2"` each encode as `[198, X]`. A future
   H2 mechanism requires two-token marginal log-probability or
   equivalent, deferred to a future §15.14-A6 PROPOSED amendment
   (NOT authorized in this OUTCOME).

5. **The §15.14-A4 diagnostic surfaced the categorical-distribution
   mismatch that v4 then confirmed.** On the 50 calibration rows
   under §15.14-A4: judge picked `MENTIONED` 34/50 times (68%)
   while human picked `MENTIONED` 1/50 times (2%); the binary-
   collapse κ on the §15.14-A4 cache was `+0.047`. v4 (§15.14-A5)
   shifted the judge's first-token distribution but did not move
   the binary κ into the agreement regime (κ_3class moved from
   `−0.0776` to `−0.3840`). This is consistent with the §15.14-A4
   block 4 NOTE that "a binary κ ≥ 0.6 would NOT change the
   §15.14 v3 ANNOTATION_FAILED closure" — the same logic applies
   to v4.

None of these findings requires the cascade verdict to be
informative.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 `PARTIAL_SIGNAL_IN_Z` preserved. §15.11
`NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` preserved. §15.12 closure
preserved. §15.13 `NO_MATERIAL_SIGNAL_IN_INERTIA` preserved.
§15.14 v1 ANNOTATION_FAILED closure preserved (commit `2d88be1`).
§15.14 v2 ANNOTATION_FAILED closure preserved (commit `198378e`).
§15.14 v3 ANNOTATION_FAILED closure preserved (commit `257dd24`).
§15.14-A4 diagnostic findings preserved unchanged
(`framing_15_14_annotated_A4_diagnostic.npz` on RunPod, with
`diagnostic_only=True` marker and full provenance string).

§15.14 v4 closes with `ANNOTATION_FAILED on Llama-3.1-8B +
§15.14-A5 chat-template-render extraction (κ = −0.3840 < 0.6
inclusive)`. §15.14 closes overall with `ANNOTATION_FAILED across
all five tested judge configurations` (per user bounded sign-off
recorded in the §15.14-A5 EFFECTIVE correspondence; commit
`b11b3e2`).

The framing-stickiness hypothesis (whether residual-stream
geometry foretells inappropriate framing recurrence at later turns
of a multi-turn chat) remains **untested** at the 7-8B-judge scale
on the available hardware envelope. The §15.14 stimulus set,
calibration labels, extraction cache, and §15.14-A4 diagnostic
annotated cache are preserved for any future §0.X that provisions
either a 70B+ judge or a §15.14-A6 mechanism amendment under
separate authorization.

## §15.x cross-version status snapshot

| Aspect | Status |
|---|---|
| §15.14 stimulus design | LOCKED, preserved |
| §15.14 calibration labels | LOCKED, preserved |
| §15.14 extraction cache | INTACT, preserved (re-usable) |
| §15.14-A4 diagnostic annotated cache (RunPod) | INTACT, preserved (re-usable for further H3 / H4 / H5 diagnostics) |
| §15.14 self-test gate | PASS (12 cascade + 3 cosine + 52-firewall + disjointness) |
| §15.14 v1 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v2 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v3 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ) |
| **§15.14 v4 cascade verdict** | **NOT COMPUTED (ANNOTATION_FAILED — κ; H1 ruled out)** |
| §15.14 hypothesis status | UNTESTED across accessible judges |
| §15.14-A1 / A2 / A3 / A4 / A5 | All EFFECTIVE; all §0.8-binding |
| All §13 / §14 / §15.10–§15.13 verdicts-of-record | PRESERVED |

## Branch state advance

```
§15_14_V3_CLOSED_AS_ANNOTATION_FAILED_DEFERRED_TO_V4_VIA_§15.14-A5
            ↓ (§15.14-A5 PROPOSED → revised → EFFECTIVE)
§15_14_V4_RUNNING_UNDER_A5_CHAT_TEMPLATE_RENDER
            ↓ (run completed; parse failure 0.0000; κ = −0.3840 < 0.6)
ANNOTATION_FAILED_ON_LLAMA_3_1_8B_A5_CHAT_TEMPLATE_KAPPA
            ↓ (user bounded sign-off; this commit)
§15_14_V4_CLOSED_AS_ANNOTATION_FAILED_WITH_H1_RULED_OUT_FOR_8B_JUDGE
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14 v2 OUTCOME: `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` (commit `198378e`)
- §15.14 v3 OUTCOME: `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` (commit `257dd24`)
- §15.14-A5 PROPOSED: commit `6aa5a7e`
- §15.14-A5 PROPOSED (revised, after H2 single-token mechanism falsified by `scripts/diagnose_a4_kappa.py --tokenizer-only`): commit `5fd1456`
- §15.14-A5 EFFECTIVE: commit `b11b3e2`
- §15.14-A5 v4 chat-template-render run: parse failure `0.0000`, κ = `−0.3840`, exit 9; segfault during interpreter shutdown post-exit (does not affect outcome)
- v4 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1 / v2 / v3
- §15.14-A4 diagnostic cache (RunPod): `framing_15_14_annotated_A4_diagnostic.npz` (`diagnostic_only=True`); produced via `scripts/save_a4_annotated_cache.py` under separate authorization; preserved unchanged through v4 run
- v4 diagnostic cache (chat-template render outputs): NOT executed in this OUTCOME; would require separate authorization parallel to the §15.14-A4 cache rescue
- All artifacts preserved; no JSON / MD cascade output written (κ-gate fired before writers).

## End of §15.14 v4 (final closure across all five tested judge configurations)
