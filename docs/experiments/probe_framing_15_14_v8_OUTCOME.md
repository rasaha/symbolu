# §15.14 framing-stickiness probe — v8 outcome (ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 + §15.14-A8 two-stage binary judging; κ = −0.1788; accessible-small-judge path exhausted)

## Status

§0.8-binding closure of §15.14 implementation §0.X v8 (under
§15.14-A6 Mistral-7B fallback judge with §15.14-A4 + §15.14-A5 +
§15.14-A7 + §15.14-A8 mechanics) on branch
`claude/diagnose-framing-kappa-L6dmt`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate (4/4 PASS), stimulus +
labels SHA validation, extractions-cache reload (`--force-annotate`,
`--judge-fallback`), `LABEL_TOKEN_ENCODING_EMPTY` precondition
extended across both stages (PASSED — all 12 surface strings of
`{N, Y, M, S} × ("", " ", "\n")` encoded to ≥1 token under
Mistral SentencePiece), Pass C two-stage sequence-logprob
extraction over 650 rows, and the Pass D Cohen's κ gate. The
κ gate fired at **κ = −0.1788 < 0.6 (inclusive)**, and the
script exited 9 (ANNOTATION_FAILED) before any cascade
computation. The cascade verdict was correctly NOT computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1 / v2
/ v3 / v4 / v6 / v7 ANNOTATION_FAILED closures.

**Per the user's bounded sign-off recorded in the §15.14-A8
EFFECTIVE correspondence (commit `af7f30f`):**

> If κ < 0.6, record A8 as ANNOTATION_FAILED and close the
> accessible-small-judge path. At that point, the only remaining
> serious options are 70B-class judge / hardware or closing
> §15.14 as untestable under accessible judges.

Accordingly, **§15.14 v8 closes as ANNOTATION_FAILED on
Mistral-7B-Instruct-v0.3 + §15.14-A8 chat-template two-stage
sequence-logprob extraction (κ = −0.1788 < 0.6 inclusive); the
accessible-small-judge path is exhausted.** §15.14 v1 / v2 / v3 /
v4 / v6 / v7 closures are preserved verbatim. §15.14-A4 diagnostic
findings preserved unchanged. No 70B escalation, no
hardware/quantization amendment, no §15.14-A9 authorship in this
OUTCOME. The §15.14-A1 / A2 / A3 / A4 / A5 / A6 / A7 / A8
amendments all remain EFFECTIVE; §15.14-A8 is preserved as
EFFECTIVE (κ-falsified by v8), parallel to §15.14-A4 / A5 / A7's
"(κ-falsified)" qualifiers and §15.14-A6's
"(precondition-falsified)" qualifier.

## §15.x ledger entry (final post-§15.14 v8)

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC=0.661 (saturated) | Single-turn |
| §15.10 | Supervised linear (Z) | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) | Multi-turn |
| §15.14 v1 | Framing-stickiness — JSON judge prompt | ANNOTATION_FAILED on tested judge configurations | Multi-turn |
| §15.14 v2 (A3) | Framing-stickiness — single-digit prompt + 8-token cap | ANNOTATION_FAILED on Llama-3.1-8B | Multi-turn |
| §15.14 v3 (A4) | Framing-stickiness — logit-first-token-argmax raw-string render | ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.0776) | Multi-turn |
| §15.14 v4 (A5) | Framing-stickiness — logit-first-token-argmax + chat-template render | ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.3840) | Multi-turn |
| §15.14 v6 (A6) | Framing-stickiness — Mistral-7B fallback under inherited A4 + A5 mechanics | ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 via LABEL_TOKEN_ENCODING_AMBIGUOUS (no κ produced) | Multi-turn |
| §15.14 v7 (A7) | Framing-stickiness — Mistral-7B + tokenizer-agnostic sequence-logprob logsumexp extraction | ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 (κ = −0.0976) | Multi-turn |
| **§15.14 v8 (A8)** | **Framing-stickiness — Mistral-7B + two-stage binary sequence-logprob (rubric-redesign diagnostic)** | **ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 (κ = −0.1788)** | **Multi-turn** |

§15.14 across v1 / v2 / v3 / v4 / v6 / v7 / v8 does NOT produce a
cascade verdict.

## Empirical evidence (§15.14 v8 / §15.14-A8)

### Hardware envelope (runpod, identical to v1 / v2 / v3 / v4 / v6 / v7)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace`
- **Host RAM:** 944 GiB total
- **HF cache:** redirected via `HF_HOME=/workspace/.hf_cache`

### v8 / §15.14-A8 fallback judge configuration

| Quantity | Value |
|---|---|
| Judge model | `mistralai/Mistral-7B-Instruct-v0.3` |
| `judge_fallback_used` | `true` |
| `judge_extraction_method` | `two_stage_sequence_logprob_logsumexp` (effective under §15.14-A8) |
| `judge_prompt_render` | `apply_chat_template_user_only(add_generation_prompt=True)` (§15.14-A5 inherit) |
| `judge_label_variants` | `("", " ", "\n")` (§15.14-A7 inherit) |
| `judge_label_aggregation` | `"logsumexp"` (§15.14-A7 inherit) |
| `judge_stage1_labels` | `("N", "Y")` (§15.14-A8 pinned) |
| `judge_stage2_labels` | `("M", "S")` (§15.14-A8 pinned) |
| Pinned mapping | N → 0; Y, M → 1; Y, S → 2 |
| Mistral-7B model load (cached from v7) | ~2 sec |
| Self-test gate (12 cascade + 3 cosine + 52 firewall + disjointness) | 4/4 PASS |
| `LABEL_TOKEN_ENCODING_EMPTY` precondition (12 surface strings) | PASSED |
| Pass C extraction | 650 rows; 6-12 forward passes per row depending on stage 1 outcome |
| `json_parse_failure_rate` (preserved name) | **`0.0000`** (structurally zero; §15.14-A4 inherit) |
| Pass D Cohen's κ (judge vs human, 50 calibration rows) | **`−0.1788`** |
| `KAPPA_GATE_THRESHOLD` (inclusive) | `0.6` |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v8)

The §15.14-A8 rubric-redesign hypothesis — that the unstable
middle class `MENTIONED` in the direct 3-class rubric is the
binding constraint at 7-8B judge scale, and that decomposing the
3-class decision into two binary stages would yield κ-passing
agreement with the bimodal human distribution — is **empirically
falsified**.

**Notable: the κ moved further from agreement than A7, not
closer.** Under §15.14-A7 (single-stage 3-class sequence-logprob)
on the same Mistral-7B judge, κ = `−0.0976`. Under §15.14-A8
(two-stage binary sequence-logprob with the pinned `_map_two_stage`
mapping), κ = `−0.1788`. The two-stage decomposition made the
judge more decisive, and the more-decisive judge is more
anti-correlated with the human rubric on this stimulus + labels.

**This is the second time in §15.14's history that "make the
judge more decisive" produced a more negative κ.** §15.14-A5
(chat-template render on Llama-8B with single-token argmax)
shifted κ from `−0.0776` (A4 raw-string) to `−0.3840` — a similar
"more decisive → more anti-correlated" pattern. §15.14-A8 (two-
stage decomposition on Mistral-7B with sequence-logprob) shifted
κ from `−0.0976` (A7 single-stage) to `−0.1788` — same direction,
smaller magnitude.

**Pattern across all completed-κ readouts (final, post-v8):**

  | Family       | Scale | Mechanism                                     | Render        | Rubric    | κ        |
  |--------------|-------|------------------------------------------------|---------------|-----------|----------|
  | Llama-3.1    | 8B    | A4 single-token argmax                         | raw-string    | direct 3  | `−0.0776` |
  | Llama-3.1    | 8B    | A5 single-token argmax                         | chat-template | direct 3  | `−0.3840` |
  | Mistral-0.3  | 7B    | A7 sequence-logprob logsumexp                  | chat-template | direct 3  | `−0.0976` |
  | Mistral-0.3  | 7B    | **A8 two-stage sequence-logprob logsumexp**    | **chat-template** | **2-stage binary** | **`−0.1788`** |

All four completed κ readouts fall in the range `[−0.4, 0]`. None
is positive. None approaches the `0.6` κ-gate threshold. The two
"more decisive" excursions (A5 chat-template on Llama, A8 two-
stage on Mistral) are both more negative than their less-decisive
counterparts (A4 raw-string on Llama, A7 single-stage on Mistral).

**The accessible-small-judge path is empirically exhausted.**
Across:

  - **3 model families:** Qwen-2.5, Llama-3.1, Mistral
  - **4 extraction protocols:** generate-and-parse, single-token
    argmax (raw + chat), single-stage sequence-logprob logsumexp,
    two-stage sequence-logprob logsumexp
  - **2 rubric designs:** direct 3-class, two-stage binary
  - **3 judge prompt protocols:** JSON, single-digit, single-letter
    binary
  - **2 prompt render protocols:** raw-string, chat-template

no 7-8B-class judge has produced a κ approaching `0.6`. Four
completed κ readouts span `[−0.4, 0]`; the two binary-collapse κ
side-metrics (recorded in §15.14-A4 diagnostic) are both `≤ +0.05`.
The hypothesis class "an accessible 7-8B-class instruction-tuned
judge can produce calibrated severity readouts on the §15.14
stimulus + rubric + locked human labels" is empirically falsified.

**Two structurally orthogonal forward paths remain (none
authorized in this OUTCOME; each requires a separate amendment
cycle):**

  1. **70B-class judge / hardware amendment.** Authorize either:
     - Hardware expansion (e.g., 2× A100-80 = 160 GB VRAM +
       expanded workspace) to host a true 70B-class judge at bf16,
       or
     - Quantization (currently §0.8-prohibited under §15.14-A4 /
       A5 / A6 / A7 / A8; would itself need a meta-amendment to
       lift the prohibition).

     This tests whether **scale of judge** is the binding
     constraint that sub-70B parameters cannot solve under any
     accessible rubric or extraction mechanism. **NOT authorized
     in this OUTCOME.**

  2. **Close §15.14 as ANNOTATION_FAILED across accessible
     judges.** The framing-stickiness hypothesis is recorded as
     untestable at 7-8B scale on this stimulus + rubric. The
     §15.14 stimulus, calibration labels, extraction cache, and
     §15.14-A4 diagnostic annotated cache are preserved for any
     future §0.X that provisions a larger judge. §15.x ledger
     entry locks. Forward §0.X work moves on to a different
     mechanism class (§15.15+) or to a future amendment cycle
     opening 70B+. **NOT authorized in this OUTCOME.**

A third option that was previously open — a rubric-redesign
amendment on the existing 7-8B envelope — is **closed** by v8's
empirical readout: rubric-redesign at 7-8B does not rescue κ.

This is itself a §0.8-binding empirical finding-of-record about
LLM-as-judge reliability at the 7-8B parameter scale: across the
seven structural degrees of freedom enumerated above (family,
extraction protocol, rubric, prompt protocol, render), the
achieved κ on this stimulus + labels remains structurally
bounded away from `0.6`. The remaining degree of freedom is
parameter scale.

## All judge attempts on §15.14 stimulus + labels artifact (final post-v8)

| # | Judge configuration | Prompt | Render | Extraction | Rubric | Outcome |
|---|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2) | JSON | raw-string | generate-and-parse | direct 3 | ANNOTATION_FAILED (parse 0.2692) |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2) | JSON | raw-string | generate-and-parse | direct 3 | ANNOTATION_FAILED (parse 0.7077) |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit | raw-string | generate-and-parse | direct 3 | ANNOTATION_FAILED (parse 0.8477) |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit | raw-string | logit-first-token-argmax | direct 3 | ANNOTATION_FAILED (κ = −0.0776) |
| 5 | meta-llama/Llama-3.1-8B-Instruct (post-A5) | single-digit | apply_chat_template | logit-first-token-argmax | direct 3 | ANNOTATION_FAILED (κ = −0.3840) |
| 6 | mistralai/Mistral-7B-Instruct-v0.3 (post-A6) | single-digit | apply_chat_template | logit-first-token-argmax | direct 3 | ANNOTATION_FAILED (LABEL_TOKEN_ENCODING_AMBIGUOUS; no κ) |
| 7 | mistralai/Mistral-7B-Instruct-v0.3 (post-A7) | single-digit | apply_chat_template | sequence-logprob logsumexp over variants | direct 3 | ANNOTATION_FAILED (κ = −0.0976) |
| 8 | **mistralai/Mistral-7B-Instruct-v0.3 (post-A8)** | **single-letter binary, two stages** | **apply_chat_template** | **two-stage sequence-logprob logsumexp** | **two-stage binary (N/Y, M/S)** | **ANNOTATION_FAILED (κ = −0.1788)** |

**Pattern (final post-v8).** Across eight tested judge
configurations spanning the full known-tractable subspace of
accessible 7-8B-class judges × extraction protocols × rubric
designs × prompt protocols × render protocols, the §15.14 cascade
has not been computed once. The four completed κ readouts (A4,
A5, A7, A8) all fall in `[−0.4, 0]`; none approaches the `0.6`
κ-gate. The accessible-small-judge path is empirically exhausted;
no further amendment within the 7-8B envelope has any reasonable
prior of changing this readout.

## Artifacts preserved (intact on this branch + on RunPod)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` | tens of KB | DIAGNOSTIC ONLY (preserved on RunPod from §15.14-A4 cache rescue) |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | preserved | v2 closure (commit `198378e`) |
| `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` | preserved | v3 closure (commit `257dd24`) |
| `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` | preserved | v4 closure (commit `2bf65b7`) |
| `docs/experiments/probe_framing_15_14_v6_OUTCOME.md` | preserved | v6 closure (commit `c321e16`) |
| `docs/experiments/probe_framing_15_14_v7_OUTCOME.md` | preserved | v7 closure (commit `933459d`) |
| `docs/experiments/probe_framing_15_14_v8_OUTCOME.md` | this file | v8 closure (this commit) |
| `scripts/probe_framing_15_14.py` | ~3900 lines | end-to-end runnable; gates correctly enforced through eight judge configurations |

**Key preservation under v8 closure.** Per the same control flow
as v3 / v4 / v6 / v7, the κ-gate exit fires upstream of
`_save_annotated_cache`, so no canonical annotated cache for v8
was written to disk. Per-row v8 severities, per-stage per-variant
sequence logprobs ((n, 12) matrix; stage-2 cells NaN for stage-1=N
rows), per-stage aggregated logsumexp scores ((n, 4) matrix;
stage-2 NaN for skipped rows), and per-row stage1_pick / stage2_pick
columns are recoverable via `scripts/save_a4_annotated_cache.py`
under the active code path = §15.14-A8 two-stage extraction. Such
a v8 diagnostic-cache rescue is **NOT** executed in this OUTCOME
and would require separate authorization.

## Spec amendments in §15.14 lifecycle (final post-v8)

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | source enum extension | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Llama-3.1-8B fallback judge | `34912e3` |
| §15.14-A3 | EFFECTIVE (parse-falsified by v2) | single-digit prompt + 8-token cap | `4d18762` |
| §15.14-A4 | EFFECTIVE (κ-falsified by v3; precondition-falsified by v6) | logit-first-token-argmax extraction | `dc10d78` |
| §15.14-A5 | EFFECTIVE (κ-falsified by v4) | chat-template prompt render | `b11b3e2` |
| §15.14-A6 | EFFECTIVE (precondition-falsified by v6) | Mistral-7B fallback (family-control test) | `1d1c520` |
| §15.14-A7 | EFFECTIVE (κ-falsified by v7) | tokenizer-agnostic sequence-logprob logsumexp | `13bc074` |
| **§15.14-A8** | **EFFECTIVE (κ-falsified by v8)** | **rubric-redesign diagnostic: two-stage binary judging** | **`af7f30f`** |

All eight amendments stand and are §0.8-binding. None modified
any sealed threshold (severity rubric at the κ-evaluation surface,
`BINARY_LABEL_THRESHOLD`, `KAPPA_GATE_THRESHOLD = 0.6 inclusive`,
`DIRECTION_GATE_THRESHOLD = 0.5 strict`,
`PARTIAL_AUC_THRESHOLD = 0.66 inclusive`,
`STRONG_AUC_THRESHOLD = 0.75 inclusive`,
`STRONG_DELTA_AUC_THRESHOLD = 0.05 inclusive`,
`ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`), the cascade
structure, the 52-pattern Class-3 firewall, the human calibration
labels, the locked stimulus or labels SHAs, or any §13/§14/§15.x
verdict-of-record.

## What was learned in §15.14 (independent of any cascade verdict, post-v8)

Eight findings stand on their own from §15.14 v1 + v2 + v3 + v4 +
v6 + v7 + v8 even without a cascade verdict:

1. **Bimodal severity distribution at the human level** (28/1/21).
   Preserved across all eight runs. Second-eyes review identified
   the lone MENTIONED label as a probable clerical slip; the
   underlying human judgment is essentially binary. Confirmed by
   the two §15.14-A4 diagnostic block-1 / block-4 readouts.

2. **Format-following failure ladder at 7-8B judge scale.**
   Qwen-7B/JSON `0.2692`, Llama-8B/JSON `0.7077`,
   Llama-8B/single-digit `0.8477`. Logit-based extraction
   structurally removes parse failure to `0.0000`. Preserved.

3. **Rubric discrimination is the binding constraint at 7-8B
   Llama scale under single-token extraction, AND chat-template
   render strengthens not weakens that constraint.** §15.14-A4
   raw-string κ = `−0.0776` → §15.14-A5 chat-template κ = `−0.3840`.
   Preserved.

4. **The single-token surface-variant H2 mechanism is structurally
   infeasible against the Llama-3.1 tokenizer.** Preserved.

5. **The §15.14-A4 diagnostic surfaced the categorical-distribution
   mismatch.** Preserved.

6. **The §15.14-A4 single-token extraction mechanism is
   structurally incompatible with the Mistral-7B-Instruct-v0.3
   SentencePiece tokenizer** (bare digits encode as 2-token
   `[29473, X]`). Preserved.

7. **The 7-8B-class family-control hypothesis is empirically
   falsified** (Llama-8B/A4: κ = −0.0776; Mistral-7B/A7: κ =
   −0.0976 — within `0.02` of each other, both ≈ 0). Preserved.

8. **The 7-8B-class rubric-design hypothesis is empirically
   falsified (NEW — recorded in this v8 OUTCOME).** The two-stage
   binary rubric (§15.14-A8) on Mistral-7B did not rescue κ;
   readout was κ = `−0.1788`, more negative than A7's `−0.0976`.
   The "more decisive judge → more anti-correlated κ" pattern
   recurred (A4 → A5 was the first instance; A7 → A8 is the
   second). Across three families × four extraction protocols ×
   two rubric designs × two render protocols × multiple prompt
   protocols, no 7-8B-class judge has produced a κ approaching
   `0.6` on this stimulus + labels. The accessible-small-judge
   path is empirically exhausted. The remaining structural
   degree of freedom is **parameter scale** (70B-class judge
   under hardware/quantization amendment) or **closing §15.14**
   as untestable under accessible judges.

None of these findings requires the cascade verdict to be
informative.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 `PARTIAL_SIGNAL_IN_Z` preserved. §15.11
`NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` preserved. §15.12 closure
preserved. §15.13 `NO_MATERIAL_SIGNAL_IN_INERTIA` preserved.
§15.14 v1 / v2 / v3 / v4 / v6 / v7 ANNOTATION_FAILED closures
preserved verbatim. §15.14-A4 diagnostic findings preserved
unchanged.

§15.14 v8 closes with `ANNOTATION_FAILED on
Mistral-7B-Instruct-v0.3 + §15.14-A8 two-stage sequence-logprob
extraction (κ = −0.1788 < 0.6 inclusive); accessible-small-judge
path exhausted across 3 families × 4 extraction protocols × 2
rubric designs`.

§15.14 closes overall with `ANNOTATION_FAILED across all eight
tested judge configurations` (per user bounded sign-off recorded
in the §15.14-A8 EFFECTIVE correspondence; commit `af7f30f`).

The framing-stickiness hypothesis remains **untested** at the
7-8B-judge scale on the available hardware envelope and the
locked §15.14 stimulus + labels artifact. The §15.14 stimulus,
calibration labels, extraction cache, and §15.14-A4 diagnostic
annotated cache are preserved for any future §0.X that provisions
a larger judge under a hardware/quantization amendment, or for
the §15.x ledger to record §15.14 as ANNOTATION_FAILED across
accessible judges per option (2) above.

## §15.x cross-version status snapshot

| Aspect | Status |
|---|---|
| §15.14 stimulus design | LOCKED, preserved |
| §15.14 calibration labels | LOCKED, preserved |
| §15.14 extraction cache | INTACT, preserved (re-usable) |
| §15.14-A4 diagnostic annotated cache (RunPod) | INTACT, preserved |
| §15.14 self-test gate | PASS (12 cascade + 3 cosine + 52-firewall + disjointness) |
| §15.14 v1 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v2 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v3 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ) |
| §15.14 v4 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ; H1 ruled out) |
| §15.14 v6 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — LABEL_TOKEN_ENCODING_AMBIGUOUS) |
| §15.14 v7 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ; family-control falsified) |
| **§15.14 v8 cascade verdict** | **NOT COMPUTED (ANNOTATION_FAILED — κ; rubric-design falsified; accessible-small-judge path exhausted)** |
| §15.14 hypothesis status | UNTESTED across accessible judge scales (7-8B exhausted) |
| §15.14-A1 / A2 / A3 / A4 / A5 / A6 / A7 / A8 | All EFFECTIVE; all §0.8-binding |
| All §13 / §14 / §15.10–§15.13 verdicts-of-record | PRESERVED |

## Branch state advance

```
§15_14_V7_CLOSED_AS_ANNOTATION_FAILED_FAMILY_CONTROL_FALSIFIED
            ↓ (§15.14-A8 PROPOSED → EFFECTIVE)
§15_14_V8_RUNNING_UNDER_A8_TWO_STAGE_BINARY_ON_MISTRAL_7B
            ↓ (run completed; parse failure 0.0000; κ = −0.1788 < 0.6)
ANNOTATION_FAILED_ON_MISTRAL_7B_A8_KAPPA_RUBRIC_REDESIGN_FALSIFIED
            ↓ (user bounded sign-off; this commit)
§15_14_V8_CLOSED_AS_ANNOTATION_FAILED_ACCESSIBLE_SMALL_JUDGE_PATH_EXHAUSTED
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14 v2 OUTCOME: `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` (commit `198378e`)
- §15.14 v3 OUTCOME: `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` (commit `257dd24`)
- §15.14 v4 OUTCOME: `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` (commit `2bf65b7`)
- §15.14 v6 OUTCOME: `docs/experiments/probe_framing_15_14_v6_OUTCOME.md` (commit `c321e16`)
- §15.14 v7 OUTCOME: `docs/experiments/probe_framing_15_14_v7_OUTCOME.md` (commit `933459d`)
- §15.14-A8 PROPOSED: commit `60263b5`
- §15.14-A8 EFFECTIVE: commit `af7f30f`
- §15.14-A8 v8 Mistral-7B two-stage run: parse failure `0.0000`, κ = `−0.1788`, exit 9
- v8 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1 / v2 / v3 / v4 / v6 / v7
- §15.14-A4 diagnostic cache (RunPod): preserved unchanged through v8 run
- v8 diagnostic cache (two-stage binary outputs): NOT executed in this OUTCOME
- All artifacts preserved; no JSON / MD cascade output written (κ-gate fired before writers)

## End of §15.14 v8 (closure across all eight tested judge configurations; accessible-small-judge path empirically exhausted; forward paths require either 70B-class judge / hardware amendment or closing §15.14 as untestable under accessible judges, neither authorized in this OUTCOME)
