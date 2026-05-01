# §15.14 framing-stickiness probe — v7 outcome (ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 + §15.14-A7 sequence-logprob logsumexp; κ = −0.0976; 7-8B-class family-control hypothesis empirically falsified)

## Status

§0.8-binding closure of §15.14 implementation §0.X v7 (under
§15.14-A6 Mistral-7B fallback judge with §15.14-A4 + §15.14-A5 +
§15.14-A7 mechanics) on branch
`claude/diagnose-framing-kappa-L6dmt`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate (4/4 PASS), stimulus +
labels SHA validation, extractions-cache reload (`--force-annotate`),
`LABEL_TOKEN_ENCODING_EMPTY` precondition (PASSED — every
(label, variant) surface string encoded to ≥1 token under
Mistral SentencePiece), Pass C tokenizer-agnostic sequence-logprob
extraction over 650 rows × 9 surface variants per row, and the
Pass D Cohen's κ gate. The κ gate fired at **κ = −0.0976 < 0.6
(inclusive)**, and the script exited 9 (ANNOTATION_FAILED) before
any cascade computation. The cascade verdict was correctly NOT
computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1
ANNOTATION_FAILED closure (commit `2d88be1`), the §15.14 v2
ANNOTATION_FAILED closure (commit `198378e`), the §15.14 v3
ANNOTATION_FAILED closure (commit `257dd24`), the §15.14 v4
ANNOTATION_FAILED closure (commit `2bf65b7`), or the §15.14 v6
ANNOTATION_FAILED closure (commit `c321e16`). The §15.14-A4
diagnostic findings recovered into
`docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` on
RunPod are preserved unchanged.

**Per the user's bounded sign-off recorded in the §15.14-A7
EFFECTIVE correspondence (commit `13bc074`):**

> If κ < 0.6, exit 9 ANNOTATION_FAILED.
> Do not change ... prior v1 / v2 / v3 / v4 / v6 verdict records ...

Accordingly, **§15.14 v7 closes as ANNOTATION_FAILED on
Mistral-7B-Instruct-v0.3 + §15.14-A7 chat-template
sequence-logprob logsumexp extraction (κ = −0.0976 < 0.6
inclusive)**. §15.14 v1 / v2 / v3 / v4 / v6 closures are
preserved verbatim. §15.14-A4 diagnostic findings preserved
unchanged. No 70B escalation, no §15.14-A8 (rubric redesign)
authorship, no quantization, no Mixtral. The §15.14-A1 / A2 / A3
/ A4 / A5 / A6 / A7 amendments all remain EFFECTIVE; §15.14-A7
is preserved as EFFECTIVE (κ-falsified by v7), parallel to
§15.14-A4 / A5 (κ-falsified by v3 / v4) and §15.14-A6
(precondition-falsified by v6).

## §15.x ledger entry (final post-§15.14 v7)

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
| §15.14 v4 (A5) | Framing-stickiness — logit-first-token-argmax + chat-template render | ANNOTATION_FAILED on Llama-3.1-8B (κ = −0.3840) | Multi-turn |
| §15.14 v6 (A6) | Framing-stickiness — Mistral-7B fallback (family-control) under inherited A4 + A5 mechanics | ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 via LABEL_TOKEN_ENCODING_AMBIGUOUS (no κ produced) | Multi-turn |
| **§15.14 v7 (A7)** | **Framing-stickiness — Mistral-7B fallback + tokenizer-agnostic sequence-logprob logsumexp extraction** | **ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 (κ = −0.0976)** | **Multi-turn** |

§15.14 across v1 / v2 / v3 / v4 / v6 / v7 does NOT produce a
`STRONG_SIGNAL_IN_FRAMING` / `PARTIAL_SIGNAL_IN_FRAMING` /
`NO_MATERIAL_SIGNAL_IN_FRAMING` cascade verdict. The cascade was
never computed.

## Empirical evidence (§15.14 v7 / §15.14-A7)

### Hardware envelope (runpod, identical to v1 / v2 / v3 / v4 / v6)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total
- **HF cache:** redirected via `HF_HOME=/workspace/.hf_cache`

### v7 / §15.14-A7 fallback judge configuration

(Effective under §15.14-A2 + A3 + A4 + A5 + A6 + A7.) Mistral-7B
already cached from the v6 attempt; loaded in ~2 sec.

| Quantity | Value |
|---|---|
| Judge model | `mistralai/Mistral-7B-Instruct-v0.3` |
| `judge_fallback_used` | `true` (Qwen-72B default skipped via `--judge-fallback` flag) |
| `judge_extraction_method` | `sequence_logprob_logsumexp_over_variants` (effective under §15.14-A7; was `logit_first_token_argmax` under §15.14-A4 / A5 / A6) |
| `judge_prompt_render` | `apply_chat_template_user_only(add_generation_prompt=True)` (§15.14-A5 inherit) |
| `judge_label_variants` | `("", " ", "\n")` (§15.14-A7 pinned) |
| `judge_label_aggregation` | `"logsumexp"` (§15.14-A7 pinned) |
| `label_token_ids` | `0 → -1`, `1 → -1`, `2 → -1` (multi-token sentinel; not used by §15.14-A7 extraction) |
| `LABEL_TOKEN_ENCODING_EMPTY` precondition | PASSED (every (label, variant) surface string encoded to ≥1 token under Mistral) |
| Pass C extraction | 650 rows × 9 forward passes per row = 5850 short forward passes; ~10 min wall |
| `json_parse_failure_rate` (preserved name) | **`0.0000`** (structurally zero; §15.14-A4 inheritance) |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` (vacuous) |
| Pass D Cohen's κ (judge vs human, 50 calibration rows) | **`−0.0976`** |
| `KAPPA_GATE_THRESHOLD` (inclusive) | `0.6` |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v7)

The §15.14-A7 mechanism (tokenizer-agnostic sequence-logprob
logsumexp scoring under §15.14-A5 chat-template render) ran
end-to-end on the post-§15.14-A6 Mistral-7B-Instruct-v0.3 judge
and produced **κ = −0.0976**. This is approximately uncorrelated
with the human rubric (within float noise of zero on N = 50).

The §15.14-A6 family-control hypothesis — that the v3 / v4 κ
failure on Llama-3.1-8B was Llama-3.1-family-specific rather than
general across accessible 7-8B-class judges — is **empirically
falsified**.

**Pattern across all three families × tested mechanisms:**

  | Family       | Scale | Mechanism                                              | κ        |
  |--------------|-------|--------------------------------------------------------|----------|
  | Qwen-2.5     | 7B    | A1 JSON / generate-and-parse                           | n/r      |
  | Llama-3.1    | 8B    | A2 JSON / generate-and-parse                           | n/r      |
  | Llama-3.1    | 8B    | A3 single-digit / generate-and-parse                   | n/r      |
  | Llama-3.1    | 8B    | A4 raw-string / single-token logit-argmax              | −0.0776  |
  | Llama-3.1    | 8B    | A5 chat-template / single-token logit-argmax           | −0.3840  |
  | Mistral-0.3  | 7B    | A6 chat-template / single-token logit-argmax           | n/r (LABEL_TOKEN_ENCODING_AMBIGUOUS) |
  | **Mistral-0.3** | **7B**    | **A7 chat-template / sequence-logprob logsumexp**          | **−0.0976** |

(`n/r` = κ not reached; Pass C parse-gate or A4-precondition gate
fired upstream of κ computation.)

The two completed κ readouts on Llama-3.1-8B (A4 raw-string =
−0.0776; A5 chat-template = −0.3840) and the one completed κ
readout on Mistral-7B (A7 chat-template + seq-logprob = −0.0976)
all fall in the range `[−0.4, 0]`. None is positive. None is
within `0.6` of the κ-gate threshold. The Llama-8B-under-chat-
template excursion (κ = −0.38) was the outlier; A4 on Llama and
A7 on Mistral both land within ~0.02 of each other near zero.

**Two natural mechanistic interpretations of the v7 result, both
consistent with the data:**

  1. **Scale is the binding constraint.** At 7-8B parameter scale,
     LLM judges produce severity readouts essentially uncorrelated
     with the human rubric on this stimulus. Family of judge does
     not matter materially; extraction protocol does not matter
     materially (modulo the chat-template-on-Llama anomaly which
     concentrates anti-correlated mass). A 70B+ judge is the
     architecturally indicated next step.
  2. **Rubric design is the binding constraint.** The 3-class
     IGNORED / MENTIONED / STRUCTURED rubric is poorly matched to
     the human's effectively-binary distribution (28/1/21 ≈
     binary IGNORED-vs-STRUCTURED, with the lone MENTIONED label
     plausibly a clerical slip per second-eyes review). 7-8B
     judges are sufficient for the underlying signal but
     mismatched to the rubric's middle class. A binary-collapse
     or two-stage rubric (§15.14-A8 candidate) is the
     architecturally indicated next step.

**These two interpretations are not mutually exclusive.** A
clean disambiguation would require either:
  - **§15.14-A8 PROPOSED** (rubric redesign on the existing 7-8B
    judges) — cheap to test (~5 min wall on the existing
    envelope; no new model download); discriminates rubric-design
    from scale.
  - **A future amendment provisioning a 70B-class judge** under
    hardware expansion or quantization authorization —
    discriminates scale from rubric-design.
  - **Both, in sequence**: A8 first (cheap), then 70B+ if A8
    fails too.

This is itself a §0.8-binding empirical finding-of-record about
LLM-as-judge reliability at this parameter scale: **across two
families (Llama-3.1, Mistral) at 7-8B scale and across three
extraction protocols (raw-string single-token, chat-template
single-token, chat-template sequence-logprob), the achieved κ
on this stimulus + labels remains structurally bounded away from
the 0.6 inclusive κ-gate, all within the range `[−0.4, 0]`**.
This is independent of any cascade verdict.

## All judge attempts on §15.14 stimulus + labels artifact (final post-v7)

| # | Judge configuration | Prompt | Render | Extraction | Outcome |
|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2) | JSON | raw-string | generate-and-parse | ANNOTATION_FAILED (parse 0.2692) |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2) | JSON | raw-string | generate-and-parse | ANNOTATION_FAILED (parse 0.7077) |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit, 8-token | raw-string | generate-and-parse | ANNOTATION_FAILED (parse 0.8477) |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit | raw-string | logit-first-token-argmax | ANNOTATION_FAILED (parse 0.0; κ = −0.0776) |
| 5 | meta-llama/Llama-3.1-8B-Instruct (post-A5) | single-digit | apply_chat_template | logit-first-token-argmax | ANNOTATION_FAILED (parse 0.0; κ = −0.3840) |
| 6 | mistralai/Mistral-7B-Instruct-v0.3 (post-A6) | single-digit | apply_chat_template | logit-first-token-argmax | ANNOTATION_FAILED (LABEL_TOKEN_ENCODING_AMBIGUOUS at judge-load; no κ) |
| 7 | **mistralai/Mistral-7B-Instruct-v0.3 (post-A7)** | **single-digit** | **apply_chat_template** | **sequence_logprob_logsumexp_over_variants** | **ANNOTATION_FAILED (parse 0.0; κ = −0.0976)** |

**Pattern (final post-v7).** Across seven tested judge
configurations spanning three model families (Qwen-2.5,
Llama-3.1, Mistral) at the 7-8B parameter scale, four extraction
protocols (generate-and-parse, single-token argmax raw-string,
single-token argmax chat-template, sequence-logprob logsumexp
chat-template), and two completed-κ measurements on different
families (Llama-8B / A4: −0.0776; Mistral-7B / A7: −0.0976), the
§15.14 cascade has not been computed once. The four completed-κ
readouts (A4, A5, A7) all fall in `[−0.4, 0]`; none approaches
the 0.6 κ-gate. The 7-8B-class family-control hypothesis (A6)
is empirically falsified by v7's Mistral readout being
indistinguishable from Llama-8B / A4's readout.

The remaining hypotheses for a κ-passing readout on this
stimulus + labels artifact are:

  - **Scale.** A 70B-class judge under hardware/quantization
    amendment.
  - **Rubric.** A binary or two-stage rubric (§15.14-A8 candidate)
    on the existing 7-8B envelope.
  - **Both.** A 70B-class judge with a redesigned rubric.

None is authorized in this OUTCOME.

## Artifacts preserved (intact on this branch + on RunPod)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` | tens of KB | DIAGNOSTIC ONLY (preserved on RunPod from §15.14-A4 cache rescue; **not modified** by v7 run) |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | preserved | v2 closure (commit `198378e`) |
| `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` | preserved | v3 closure (commit `257dd24`) |
| `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` | preserved | v4 closure (commit `2bf65b7`) |
| `docs/experiments/probe_framing_15_14_v6_OUTCOME.md` | preserved | v6 closure (commit `c321e16`) |
| `docs/experiments/probe_framing_15_14_v7_OUTCOME.md` | this file | v7 closure (this commit) |
| `scripts/probe_framing_15_14.py` | ~3650 lines | end-to-end runnable; gates correctly enforced through seven judge configurations |
| `scripts/diagnose_a4_kappa.py` | ~480 lines | DIAGNOSTIC ONLY; reads §15.14-A4 / A5 / A7 annotated caches |
| `scripts/save_a4_annotated_cache.py` | ~450 lines | DIAGNOSTIC ONLY; rescues annotated caches when κ-gate fires upstream of writer |

**Key preservation under v7 closure.** Per the same control
flow as v3 / v4 / v6, the κ-gate exit at
`scripts/probe_framing_15_14.py:3474` fires upstream of
`_save_annotated_cache` at `scripts/probe_framing_15_14.py:3477`,
so no canonical annotated cache for v7 was written to disk. The
per-row v7 severities, per-variant logprobs (`(n, 9)` matrix),
and per-label aggregated logsumexp scores (`(n, 3)` matrix) are
recoverable via `scripts/save_a4_annotated_cache.py` (which now
operates under the active `_judge_one_row` code path = post-A7
sequence-logprob logsumexp; the runtime banner explicitly warns
of this). Such a v7 diagnostic-cache rescue is **NOT** executed
in this OUTCOME and would require separate authorization
parallel to the §15.14-A4 cache rescue authorization.

## Spec amendments in §15.14 lifecycle (final post-v7)

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |
| §15.14-A3 | EFFECTIVE (parse-falsified by v2) | Replace JSON judge prompt + parser with single-digit prompt + parser; `MAX_NEW_TOKENS_JUDGE: 128 → 8` | `4d18762` |
| §15.14-A4 | EFFECTIVE (κ-falsified by v3; precondition-falsified by v6) | Replace generation-and-parse extraction with logit-first-token-argmax over `{"0", "1", "2"}` | `dc10d78` |
| §15.14-A5 | EFFECTIVE (κ-falsified by v4) | Wrap unchanged `JUDGE_PROMPT_TEMPLATE` through `tokenizer.apply_chat_template(..., add_generation_prompt=True)` | `b11b3e2` |
| §15.14-A6 | EFFECTIVE (precondition-falsified by v6) | Replace `JUDGE_MODEL_ID_FALLBACK`: `meta-llama/Llama-3.1-8B-Instruct` → `mistralai/Mistral-7B-Instruct-v0.3` (non-Llama 7B-class family-control test) | `1d1c520` |
| **§15.14-A7** | **EFFECTIVE (κ-falsified by v7)** | **Replace single-token argmax with tokenizer-agnostic sequence-logprob logsumexp scoring over `JUDGE_LABEL_VARIANTS = ("", " ", "\n")` per label** | **`13bc074`** |

All seven amendments stand and are §0.8-binding. None modified
any sealed threshold (severity rubric, `BINARY_LABEL_THRESHOLD`,
`KAPPA_GATE_THRESHOLD = 0.6 inclusive`, `DIRECTION_GATE_THRESHOLD
= 0.5 strict`, `PARTIAL_AUC_THRESHOLD = 0.66 inclusive`,
`STRONG_AUC_THRESHOLD = 0.75 inclusive`,
`STRONG_DELTA_AUC_THRESHOLD = 0.05 inclusive`,
`ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`), the cascade
structure, the 52-pattern Class-3 firewall, the human calibration
labels, the locked stimulus or labels SHAs, or any §13/§14/§15.x
verdict-of-record.

§15.14-A7's "EFFECTIVE (κ-falsified by v7)" qualifier is
analogous to §15.14-A4 / A5's "EFFECTIVE (κ-falsified)" and
§15.14-A6's "EFFECTIVE (precondition-falsified)": the amendment
was correctly applied per its sealed scope, and its empirical
readout falsifies a specific hypothesis class. A7 itself is
preserved as an EFFECTIVE amendment and is not retracted; the
empirical finding is a separate §0.8-binding result-of-record.

## What was learned in §15.14 (independent of any cascade verdict, post-v7)

Seven findings stand on their own from §15.14 v1 + v2 + v3 + v4
+ v6 + v7 even without a cascade verdict:

1. **Bimodal severity distribution at the human level.** 28/1/21
   over IGNORED/MENTIONED/STRUCTURED. Preserved across v1 / v2 /
   v3 / v4 / v6 / v7. Second-eyes review (correspondence record)
   identified the lone MENTIONED label as a probable clerical
   slip; underlying human judgment is essentially binary.

2. **Format-following failure ladder at 7-8B judge scale.**
   Qwen-7B/JSON `0.2692`, Llama-8B/JSON `0.7077`,
   Llama-8B/single-digit `0.8477`. Logit-based extraction
   structurally removes parse failure to `0.0000`. Preserved.

3. **Rubric discrimination is the binding constraint at 7-8B
   Llama scale, AND chat-template render strengthens not weakens
   that constraint** (under single-token extraction). §15.14-A4
   raw-string κ = `−0.0776` → §15.14-A5 chat-template κ =
   `−0.3840`. The H1 rendering-protocol fix is empirically
   falsified as a sufficient remedy at 8B Llama scale **under
   single-token extraction**. Preserved.

4. **The single-token surface-variant H2 mechanism is structurally
   infeasible against the Llama-3.1 tokenizer.** `" 0"` /
   `" 1"` / `" 2"` each encode as `[220, X]` under
   meta-llama/Llama-3.1-8B-Instruct's tiktoken-style BPE.
   Preserved.

5. **The §15.14-A4 diagnostic surfaced the categorical-distribution
   mismatch that v4 then confirmed.** Judge picks MENTIONED
   34/50 calibration rows; human picks MENTIONED 1/50.
   Binary-collapse κ on §15.14-A4 cache `+0.047`. Preserved.

6. **The §15.14-A4 single-token extraction mechanism is
   structurally incompatible with the Mistral-7B-Instruct-v0.3
   SentencePiece tokenizer.** Each bare digit `'0'` / `'1'` /
   `'2'` encodes as a 2-token sequence `[29473, X]` with shared
   prefix token `29473`. The §15.14-A4 precondition correctly
   detected this at judge-load (v6 closure). Preserved.

7. **The 7-8B-class family-control hypothesis is empirically
   falsified (NEW — recorded in this v7 OUTCOME).** Across
   Llama-3.1-8B (A4 raw-string: κ = −0.0776) and Mistral-7B
   (A7 chat-template + sequence-logprob logsumexp: κ = −0.0976),
   the achieved κ on this stimulus + labels is approximately
   uncorrelated with the human rubric in both families, with
   readouts within `0.02` of each other and both within float
   noise of zero. The chat-template + Llama-8B + single-token
   excursion to κ = −0.38 (v4) was a single-cell anomaly within
   the broader pattern; replacing the family OR the extraction
   mechanism brings κ back to ≈ 0. The binding constraint at
   7-8B scale is therefore NOT family-of-judge specific. The
   remaining hypotheses are (a) parameter scale (7-8B insufficient
   regardless of family or mechanism) and (b) rubric design
   (3-class rubric mismatched to the bimodal human distribution).
   These two are not pre-disambiguated by v7's empirical readout
   alone; subsequent §15.14-A8 (rubric redesign) or
   hardware/quantization amendment (70B-class judge) cycles are
   the indicated next steps.

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
§15.14 v4 ANNOTATION_FAILED closure preserved (commit `2bf65b7`).
§15.14 v6 ANNOTATION_FAILED closure preserved (commit `c321e16`).
§15.14-A4 diagnostic findings preserved unchanged
(`framing_15_14_annotated_A4_diagnostic.npz` on RunPod).

§15.14 v7 closes with `ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3
+ §15.14-A7 sequence-logprob logsumexp extraction (κ = −0.0976 < 0.6
inclusive); 7-8B-class family-control hypothesis empirically
falsified`. §15.14 closes overall with `ANNOTATION_FAILED across
all seven tested judge configurations` (per user bounded sign-off
recorded in the §15.14-A7 EFFECTIVE correspondence; commit
`13bc074`).

The framing-stickiness hypothesis (whether residual-stream
geometry foretells inappropriate framing recurrence at later
turns of a multi-turn chat) remains **untested** at the 7-8B-judge
scale on the available hardware envelope and the locked §15.14
stimulus + 3-class rubric. The §15.14 stimulus set, calibration
labels, extraction cache, and §15.14-A4 diagnostic annotated
cache are preserved for any future §0.X that provisions either:

  - a §15.14-A8 PROPOSED rubric-redesign amendment (binary
    collapse or two-stage on existing 7-8B envelope);
  - a hardware / quantization amendment opening 70B-class judges;
  - or both, in sequence (A8 first, then 70B+ if A8 fails too).

None are authorized in this OUTCOME and each requires a separate
amendment cycle.

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
| §15.14 v6 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — LABEL_TOKEN_ENCODING_AMBIGUOUS; family-control test not completed under single-token extraction) |
| **§15.14 v7 cascade verdict** | **NOT COMPUTED (ANNOTATION_FAILED — κ; family-control test EMPIRICALLY FALSIFIED at 7-8B scale)** |
| §15.14 hypothesis status | UNTESTED across accessible judge scales + extraction protocols + rubrics |
| §15.14-A1 / A2 / A3 / A4 / A5 / A6 / A7 | All EFFECTIVE; all §0.8-binding |
| All §13 / §14 / §15.10–§15.13 verdicts-of-record | PRESERVED |

## Branch state advance

```
§15_14_V6_CLOSED_AS_ANNOTATION_FAILED_FAMILY_CONTROL_TEST_NOT_COMPLETED
            ↓ (§15.14-A7 PROPOSED → EFFECTIVE)
§15_14_V7_RUNNING_UNDER_A7_TOKENIZER_AGNOSTIC_SEQUENCE_LOGPROB_ON_MISTRAL_7B
            ↓ (run completed; parse failure 0.0000; κ = −0.0976 < 0.6)
ANNOTATION_FAILED_ON_MISTRAL_7B_A7_KAPPA_FAMILY_CONTROL_FALSIFIED
            ↓ (user bounded sign-off; this commit)
§15_14_V7_CLOSED_AS_ANNOTATION_FAILED_WITH_7_8B_FAMILY_CONTROL_HYPOTHESIS_EMPIRICALLY_FALSIFIED
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14 v2 OUTCOME: `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` (commit `198378e`)
- §15.14 v3 OUTCOME: `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` (commit `257dd24`)
- §15.14 v4 OUTCOME: `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` (commit `2bf65b7`)
- §15.14 v6 OUTCOME: `docs/experiments/probe_framing_15_14_v6_OUTCOME.md` (commit `c321e16`)
- §15.14-A7 PROPOSED: commit `1285631`
- §15.14-A7 EFFECTIVE: commit `13bc074`
- §15.14-A7 v7 Mistral-7B sequence-logprob run: parse failure `0.0000`, κ = `−0.0976`, exit 9
- v7 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1 / v2 / v3 / v4 / v6
- §15.14-A4 diagnostic cache (RunPod): `framing_15_14_annotated_A4_diagnostic.npz` (`diagnostic_only=True`); preserved unchanged through v7 run
- v7 diagnostic cache (sequence-logprob outputs): NOT executed in this OUTCOME; would require separate authorization parallel to §15.14-A4 cache rescue
- All artifacts preserved; no JSON / MD cascade output written (κ-gate fired before writers).

## End of §15.14 v7 (closure across all seven tested judge configurations; 7-8B-class family-control hypothesis empirically falsified; forward paths require either §15.14-A8 rubric redesign or a hardware/quantization amendment for 70B+, neither authorized in this OUTCOME)
