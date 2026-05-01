# §15.14 framing-stickiness probe — v6 outcome (ANNOTATION_FAILED via LABEL_TOKEN_ENCODING_AMBIGUOUS; Mistral-7B tokenizer empirically incompatible with §15.14-A4 single-token extraction)

## Status

§0.8-binding closure of §15.14 implementation §0.X v6 (under
§15.14-A6 Mistral-7B-Instruct-v0.3 fallback judge with §15.14-A4 +
§15.14-A5 mechanics) on branch
`claude/diagnose-framing-kappa-L6dmt`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
through its self-test gate (4/4 PASS), stimulus + labels SHA
validation, and extractions-cache reload (`--force-annotate`,
`--judge-fallback`). The `LABEL_TOKEN_ENCODING_AMBIGUOUS`
precondition (introduced under §15.14-A4) **fired at judge-load**
and the script exited 9 (ANNOTATION_FAILED) **before Pass C ran**.
No κ readout was produced. The cascade verdict was correctly NOT
computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record, including the §15.14 v1
ANNOTATION_FAILED closure (commit `2d88be1`), the §15.14 v2
ANNOTATION_FAILED closure (commit `198378e`), the §15.14 v3
ANNOTATION_FAILED closure (commit `257dd24`), and the §15.14 v4
ANNOTATION_FAILED closure (commit `2bf65b7`). The §15.14-A4
diagnostic findings recovered into
`docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` on
RunPod are preserved unchanged.

**Per the user's bounded sign-off recorded in the §15.14-A6
EFFECTIVE correspondence (commit `1d1c520`):**

> Do NOT authorize Mixtral-8x7B; do NOT authorize 70B; do NOT
> authorize quantization; do NOT draft or implement §15.14-A7;
> do NOT modify any §15.14 v1 / v2 / v3 / v4 verdict-of-record.

Accordingly, **§15.14 v6 closes as ANNOTATION_FAILED via the
§15.14-A4 LABEL_TOKEN_ENCODING_AMBIGUOUS structural precondition
on the post-§15.14-A6 fallback judge tokenizer
(meta-llama/Llama-3.1-8B retired; mistralai/Mistral-7B-Instruct-v0.3
empirically incompatible with the A4 single-token extraction
mechanism).** §15.14 v1 / v2 / v3 / v4 closures are preserved
verbatim. §15.14-A4 diagnostic findings preserved unchanged. No
70B escalation, no quantization, no §15.14-A7 authorship. The
§15.14-A1 / A2 / A3 / A4 / A5 / A6 amendments all remain
EFFECTIVE; A6's empirical failure was via the inherited A4
precondition, not via any A6 mechanism (the A6 amendment
correctly swapped the fallback identity; the structural
incompatibility is between the Mistral tokenizer and the A4
extraction protocol, both of which are §0.8-binding sealed).

## §15.x ledger entry (final post-§15.14 v6)

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
| **§15.14 v6 (A6)** | **Framing-stickiness — Mistral-7B fallback (family-control test) under inherited A4 + A5 mechanics** | **ANNOTATION_FAILED on Mistral-7B-Instruct-v0.3 via LABEL_TOKEN_ENCODING_AMBIGUOUS structural precondition (no κ produced)** | **Multi-turn** |

§15.14 across v1 / v2 / v3 / v4 / v6 does NOT produce a
`STRONG_SIGNAL_IN_FRAMING` / `PARTIAL_SIGNAL_IN_FRAMING` /
`NO_MATERIAL_SIGNAL_IN_FRAMING` cascade verdict. The cascade was
never computed.

(There is no v5 in this ledger. The §15.14-A5 EFFECTIVE flip
applied at commit `b11b3e2` and the run that produced κ = −0.3840
is recorded in v4 OUTCOME for editorial reasons — A4 / A5 are both
EFFECTIVE under the same v4 run; the A5 mechanism produced the v4
κ readout. The A6 fallback-identity swap produced the next fresh
cascade-eligible run, which is recorded here as v6 by the same
versioning convention used for the four prior closures.)

## Empirical evidence (§15.14 v6 / §15.14-A6)

### Hardware envelope (runpod, identical to v1 / v2 / v3 / v4)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total
- **HF cache:** redirected via `HF_HOME=/workspace/.hf_cache` (counts against workspace quota)

### Operational cleanup performed before run

Before the §15.14-A6 v6 run could complete its judge-load, the HF
cache directory required cleanup of two artifacts that had
accumulated over the §15.14 lifecycle and consumed the workspace
quota:

  1. `~/.hf_cache/hub/models--meta-llama--Llama-3.1-8B-Instruct`
     (~15 GB): retired under §15.14-A6; removed.
  2. `~/.hf_cache/hub/models--Qwen--Qwen2.5-72B-Instruct`
     (~31 GB of `.incomplete` blob fragments from §15.14 v1's
     failed download attempts plus subsequent resume attempts):
     pure waste; removed.

These cleanups freed ~46 GB and brought the workspace usage down
from ~48 GB (at quota) to ~15 GB (HF cache after cleanup) plus
~2.5 GB elsewhere = ~17.5 GB. Sufficient margin for Mistral-7B's
~14.5 GB download. The cleanups did not modify any §0.8-binding
artifact (no spec, no labels, no stimulus, no extraction `.npz`,
no diagnostic `.npz`, no verdict-of-record, no script source).

### v6 / §15.14-A6 fallback judge configuration

(Effective under §15.14-A2 + A3 + A4 + A5 + A6.) Loaded
successfully on the A100-80 after cleanup. Ran for ~22 seconds
total before the precondition fired.

| Quantity | Value |
|---|---|
| Judge model | `mistralai/Mistral-7B-Instruct-v0.3` |
| `judge_fallback_used` | `true` (Qwen-72B default skipped via `--judge-fallback` flag) |
| `judge_extraction_method` | `logit_first_token_argmax` (§15.14-A4 inherit) |
| `judge_prompt_render` | `apply_chat_template_user_only(add_generation_prompt=True)` (§15.14-A5 inherit) |
| Mistral-7B download | 14.5 GB at ~729 MB/s (one-time) |
| Mistral-7B model load | 291 weight shards in ~3 sec |
| Self-test gate (12 cascade + 3 cosine + 52 firewall + disjointness) | 4/4 PASS |
| Stimulus + labels SHA validation | PASS (`stimulus_sha256 = e56cfe8c…`, `calibration_labels_sha256 = e9776ff2…`) |
| Extractions cache reload | 130 chains loaded |
| `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition | **FAILED** |
| Per-label tokenization on Mistral tokenizer | `'0' → [29473, 29502]`, `'1' → [29473, 29508]`, `'2' → [29473, 29518]` (each 2-token; shared prefix 29473) |
| Pass C extraction | not reached |
| Pass D κ-gate | not reached |
| Cascade computation | not reached |
| Script exit code | `9` (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v6)

**Mistral-7B-Instruct-v0.3 is structurally incompatible with the
§15.14-A4 logit-first-token-argmax single-token extraction
mechanism on the §15.14 judge prompt.** Each bare digit (`'0'`,
`'1'`, `'2'`) encodes as a 2-token sequence under the Mistral
SentencePiece tokenizer, with all three digits sharing a common
first token (id `29473`) and differing only in their second
token. The §15.14-A4 precondition was designed precisely to catch
this case: rather than silently mis-locate the candidate logits
(which would produce a meaningless argmax), the script exits 9
with the diagnostic `LABEL_TOKEN_ENCODING_AMBIGUOUS`.

**The §15.14-A6 hypothesis — that the v3 / v4 κ failure was
Llama-3.1-family-specific rather than general across accessible
7B-class judges — is empirically untestable on this stimulus + this
extraction protocol.** The post-§15.14-A6 fallback judge
(Mistral-7B-Instruct-v0.3) cannot enter Pass C under the inherited
§15.14-A4 mechanics, so no κ comparison against v4's −0.3840 is
possible. The family-control test was not run; the family-effect
hypothesis remains unresolved at the 7B-class scale on this
stimulus.

**Three structurally orthogonal forward paths are now isolated by
v6's empirical readout (none authorized in this OUTCOME; each
requires a separate amendment cycle):**

  1. **Extraction-mechanism redesign** — a future §15.14-A7
     PROPOSED amendment that supports multi-token-encoded labels
     (e.g., compute `P(first = 29473) × P(second ∈ {29502, 29508,
     29518} | first = 29473)` over Mistral, and the analogous
     two-token marginal for Llama's space-prefixed forms). This
     is mechanistically straightforward (~10 LoC; one extra
     forward pass per row, conditioned on the bare-digit prefix
     token) but constitutes a real change to the §15.14-A4
     extraction protocol. **NOT authorized in this OUTCOME.**
  2. **Hardware / quantization amendment** — a future amendment
     that opens 70B-class judges by either expanding the A100-80
     envelope (e.g., 2× A100-80) or by quantizing (the §0.8
     prohibition under §15.14-A4 / A5 / A6 against quantization
     would itself need to be amended). **NOT authorized in this
     OUTCOME.**
  3. **Judge-rubric redesign** — a future amendment that replaces
     the 3-class IGNORED / MENTIONED / STRUCTURED rubric with a
     binary or two-stage rubric that the human distribution
     (28/1/21 ≈ binary IGNORED-vs-STRUCTURED) actually matches.
     **NOT authorized in this OUTCOME.**

This is itself a §0.8-binding empirical finding-of-record about
LLM-as-judge reliability at this parameter scale: under the
sealed §15.14-A4 single-token extraction protocol, only the Llama
tokenizer family (out of Qwen, Llama, Mistral tested) admits the
extraction at all, and within that family the 8B scale produces
κ ≈ 0 (raw-string render, v3) or κ ≈ −0.4 (chat-template render,
v4). The §15.14-A6 v6 result identifies the **extraction protocol
× tokenizer combination** as a binding constraint on the
family-control hypothesis test, independent of the κ gate.

## All judge attempts on §15.14 stimulus + labels artifact (final post-v6)

| # | Judge configuration | Prompt | Render | Extraction | Outcome |
|---|---|---|---|---|---|
| 1 | Qwen/Qwen2.5-7B-Instruct (pre-A2) | JSON | raw-string | generate-and-parse | ANNOTATION_FAILED (parse failure 0.2692) |
| 2 | meta-llama/Llama-3.1-8B-Instruct (post-A2) | JSON | raw-string | generate-and-parse | ANNOTATION_FAILED (parse failure 0.7077) |
| 3 | meta-llama/Llama-3.1-8B-Instruct (post-A3) | single-digit, 8-token | raw-string | generate-and-parse | ANNOTATION_FAILED (parse failure 0.8477) |
| 4 | meta-llama/Llama-3.1-8B-Instruct (post-A4) | single-digit | raw-string | logit-first-token-argmax | ANNOTATION_FAILED (parse failure 0.0; κ = −0.0776) |
| 5 | meta-llama/Llama-3.1-8B-Instruct (post-A5) | single-digit | apply_chat_template | logit-first-token-argmax | ANNOTATION_FAILED (parse failure 0.0; κ = −0.3840) |
| 6 | **mistralai/Mistral-7B-Instruct-v0.3 (post-A6)** | **single-digit** | **apply_chat_template** | **logit-first-token-argmax** | **ANNOTATION_FAILED (LABEL_TOKEN_ENCODING_AMBIGUOUS at judge-load; no κ produced)** |

**Pattern (final post-v6).** Across six tested judge configurations
spanning three model families (Qwen-2.5, Llama-3.1, Mistral) at
the 7-8B parameter scale, the §15.14 cascade has not been
computed once. The failure modes have proceeded in a structurally
clean ladder:

  - Rows 1–3: format-following confound (parse failure rate
    monotonically increases with simpler prompts and tighter
    output caps).
  - Row 4: format-following confound removed via logit extraction
    (parse failure structurally 0.0); residual κ ≈ 0.
  - Row 5: rendering-protocol confound removed via chat-template
    wrap; residual κ shifts to −0.38 (more negative, not less).
  - Row 6: family-control test attempted via Mistral fallback;
    structural incompatibility between Mistral SentencePiece
    tokenizer and the §15.14-A4 single-token extraction
    mechanism; the precondition correctly fires; no κ is
    measurable under the locked extraction protocol.

The binding constraint on whether the §15.14 cascade is
computable at all has shifted from format-following (v1 / v2) →
rendering-protocol (v3 closure) → rubric discrimination (v4
closure) → tokenizer × extraction-protocol compatibility (v6
closure). Each successive amendment removed one confound and
exposed the next. The forward path now requires either an
amendment to the extraction protocol (path 1 above), an amendment
to the hardware envelope (path 2), or an amendment to the judge
rubric (path 3).

## Artifacts preserved (intact on this branch + on RunPod)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/framing_15_14_annotated_A4_diagnostic.npz` | tens of KB | DIAGNOSTIC ONLY (preserved on RunPod from §15.14-A4 cache rescue; **not modified** by v6 run) |
| `docs/experiments/probe_framing_15_14_OUTCOME.md` | preserved | v1 closure (commit `2d88be1`) |
| `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` | preserved | v2 closure (commit `198378e`) |
| `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` | preserved | v3 closure (commit `257dd24`) |
| `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` | preserved | v4 closure (commit `2bf65b7`) |
| `docs/experiments/probe_framing_15_14_v6_OUTCOME.md` | this file | v6 closure (this commit) |
| `scripts/probe_framing_15_14.py` | ~3500 lines | end-to-end runnable; gates correctly enforced through six judge configurations |
| `scripts/diagnose_a4_kappa.py` | ~470 lines | DIAGNOSTIC ONLY; reads §15.14-A4 / A5 annotated caches |
| `scripts/save_a4_annotated_cache.py` | ~430 lines | DIAGNOSTIC ONLY; rescues annotated caches when κ-gate fires upstream of writer |

**Key preservation under v6 closure.** The `LABEL_TOKEN_ENCODING_AMBIGUOUS`
exit fires inside `_load_judge_model` (precondition check at
`scripts/probe_framing_15_14.py:1700`), which is upstream of the
`_save_annotated_cache` writer at `scripts/probe_framing_15_14.py:3296`.
No annotated cache for v6 was written. No per-row severities or
logits exist for the Mistral judge under the locked extraction
protocol — the script never reached Pass C. The 18 MB extraction
cache, the §15.14-A4 diagnostic annotated cache, and all locked
artifacts (stimuli, labels, calibration responses) remain intact
and re-usable for any future §15.14 amendment.

**Note on segfault at run end.** Per the same pattern as v3 / v4
runs, the v6 run terminated with exit code 9 (ANNOTATION_FAILED)
followed by a segmentation fault during Python interpreter
shutdown (consistent with HF Transformers / model destructor
ordering on this hardware envelope). The exit code preceded the
segfault; the LABEL_TOKEN_ENCODING_AMBIGUOUS decision and the
outcome-of-record are both unaffected.

## Spec amendments in §15.14 lifecycle (final post-v6)

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |
| §15.14-A3 | EFFECTIVE (parse-falsified by v2) | Replace JSON judge prompt + parser with single-digit prompt + parser; `MAX_NEW_TOKENS_JUDGE: 128 → 8` | `4d18762` |
| §15.14-A4 | EFFECTIVE (κ-falsified by v3; precondition-falsified by v6 against Mistral) | Replace generation-and-parse extraction with logit-first-token-argmax over `{"0", "1", "2"}` | `dc10d78` |
| §15.14-A5 | EFFECTIVE (κ-falsified by v4) | Wrap unchanged `JUDGE_PROMPT_TEMPLATE` through `tokenizer.apply_chat_template(..., add_generation_prompt=True)` | `b11b3e2` |
| **§15.14-A6** | **EFFECTIVE (precondition-falsified by v6)** | **Replace `JUDGE_MODEL_ID_FALLBACK`: `meta-llama/Llama-3.1-8B-Instruct` → `mistralai/Mistral-7B-Instruct-v0.3` (non-Llama 7B-class family-control test)** | **`1d1c520`** |

All six amendments stand and are §0.8-binding. None modified any
sealed threshold (severity rubric, `BINARY_LABEL_THRESHOLD`,
`KAPPA_GATE_THRESHOLD = 0.6 inclusive`, `DIRECTION_GATE_THRESHOLD =
0.5 strict`, `PARTIAL_AUC_THRESHOLD = 0.66 inclusive`,
`STRONG_AUC_THRESHOLD = 0.75 inclusive`,
`STRONG_DELTA_AUC_THRESHOLD = 0.05 inclusive`,
`ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`), the cascade
structure, the 52-pattern Class-3 firewall, the human calibration
labels, the locked stimulus or labels SHAs, or any §13/§14/§15.x
verdict-of-record.

§15.14-A6's "EFFECTIVE (precondition-falsified)" qualifier is
analogous to §15.14-A3's "EFFECTIVE (parse-falsified)" and
§15.14-A4 / A5's "EFFECTIVE (κ-falsified)": the amendment was
correctly applied per its sealed scope, and its empirical readout
falsifies a specific hypothesis class. A6 itself is preserved as
an EFFECTIVE amendment and is not retracted; the empirical
finding is a separate §0.8-binding result-of-record.

## What was learned in §15.14 (independent of any cascade verdict, post-v6)

Six findings stand on their own from §15.14 v1 + v2 + v3 + v4 + v6
even without a cascade verdict:

1. **Bimodal severity distribution at the human level.** 28/1/21
   over IGNORED/MENTIONED/STRUCTURED. Preserved across v1 / v2 /
   v3 / v4 / v6. The single MENTIONED label was reviewed in
   second-eyes correspondence and is plausibly a typographical
   slip; the underlying human judgment is essentially binary.

2. **Format-following failure ladder at 7-8B judge scale.**
   Qwen-7B/JSON `0.2692`, Llama-8B/JSON `0.7077`,
   Llama-8B/single-digit `0.8477`. Logit-based extraction
   structurally removes parse failure to `0.0000`. Preserved.

3. **Rubric discrimination is the binding constraint at 7-8B
   Llama scale, AND chat-template render strengthens not weakens
   that constraint.** §15.14-A4 raw-string κ = `−0.0776` →
   §15.14-A5 chat-template κ = `−0.3840`. The H1 rendering-
   protocol fix is empirically falsified as a sufficient remedy
   at 8B Llama scale.

4. **The single-token surface-variant H2 mechanism is structurally
   infeasible against the Llama-3.1 tokenizer.** `" 0"` /
   `" 1"` / `" 2"` each encode as `[220, X]` under
   meta-llama/Llama-3.1-8B-Instruct's tiktoken-style BPE.

5. **The §15.14-A4 diagnostic surfaced the categorical-distribution
   mismatch that v4 then confirmed.** Judge picks MENTIONED
   34/50 calibration rows; human picks MENTIONED 1/50. Binary-
   collapse κ on §15.14-A4 cache `+0.047`. v4 (§15.14-A5) shifted
   the judge's first-token distribution but did not move the
   binary κ into the agreement regime.

6. **The §15.14-A4 single-token extraction mechanism is
   structurally incompatible with the Mistral-7B-Instruct-v0.3
   SentencePiece tokenizer (NEW — recorded in this v6 OUTCOME).**
   Each bare digit `'0'` / `'1'` / `'2'` encodes as a 2-token
   sequence under Mistral, with shared prefix token `29473` and
   differing second tokens `{29502, 29508, 29518}`. The §15.14-A4
   precondition `LABEL_TOKEN_ENCODING_AMBIGUOUS` correctly
   detected this at judge-load and exited 9 ANNOTATION_FAILED
   before Pass C. The §15.14-A6 family-control test cannot be
   completed under the locked extraction protocol; the
   family-effect hypothesis at 7-8B scale on this stimulus
   remains empirically unresolved.

None of these findings requires the cascade verdict to be
informative.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved. §15.10
`PARTIAL_SIGNAL_IN_Z` preserved. §15.11
`NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` preserved. §15.12 closure
preserved. §15.13 `NO_MATERIAL_SIGNAL_IN_INERTIA` preserved.
§15.14 v1 ANNOTATION_FAILED closure preserved (commit `2d88be1`).
§15.14 v2 ANNOTATION_FAILED closure preserved (commit `198378e`).
§15.14 v3 ANNOTATION_FAILED closure preserved (commit `257dd24`).
§15.14 v4 ANNOTATION_FAILED closure preserved (commit `2bf65b7`).
§15.14-A4 diagnostic findings preserved unchanged
(`framing_15_14_annotated_A4_diagnostic.npz` on RunPod, with
`diagnostic_only=True` marker and full provenance string).

§15.14 v6 closes with `ANNOTATION_FAILED via §15.14-A4
LABEL_TOKEN_ENCODING_AMBIGUOUS structural precondition on
Mistral-7B-Instruct-v0.3 tokenizer (no κ produced)`. §15.14
closes overall with `ANNOTATION_FAILED across all six tested
judge configurations` (per user bounded sign-off recorded in the
§15.14-A6 EFFECTIVE correspondence; commit `1d1c520`).

The framing-stickiness hypothesis (whether residual-stream
geometry foretells inappropriate framing recurrence at later
turns of a multi-turn chat) remains **untested** at the 7-8B-judge
scale on the available hardware envelope and the locked §15.14-A4
extraction protocol. The §15.14 stimulus set, calibration labels,
extraction cache, and §15.14-A4 diagnostic annotated cache are
preserved for any future §0.X that provisions any of:

  - a §15.14-A7 PROPOSED extraction-mechanism amendment supporting
    multi-token-encoded labels;
  - a hardware / quantization amendment opening 70B-class judges;
  - a judge-rubric amendment replacing the 3-class rubric with
    binary or two-stage.

None of these are authorized in this OUTCOME and each requires a
separate amendment cycle.

## §15.x cross-version status snapshot

| Aspect | Status |
|---|---|
| §15.14 stimulus design | LOCKED, preserved |
| §15.14 calibration labels | LOCKED, preserved |
| §15.14 extraction cache | INTACT, preserved (re-usable) |
| §15.14-A4 diagnostic annotated cache (RunPod) | INTACT, preserved (re-usable for further H3 / H4 / H5 diagnostics on Llama-8B) |
| §15.14 self-test gate | PASS (12 cascade + 3 cosine + 52-firewall + disjointness) |
| §15.14 v1 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v2 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — parse) |
| §15.14 v3 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ) |
| §15.14 v4 cascade verdict | NOT COMPUTED (ANNOTATION_FAILED — κ; H1 ruled out) |
| **§15.14 v6 cascade verdict** | **NOT COMPUTED (ANNOTATION_FAILED — LABEL_TOKEN_ENCODING_AMBIGUOUS; family-control test not completed)** |
| §15.14 hypothesis status | UNTESTED across accessible judges + accessible extraction protocols |
| §15.14-A1 / A2 / A3 / A4 / A5 / A6 | All EFFECTIVE; all §0.8-binding |
| All §13 / §14 / §15.10–§15.13 verdicts-of-record | PRESERVED |

## Branch state advance

```
§15_14_V4_CLOSED_AS_ANNOTATION_FAILED_WITH_H1_RULED_OUT_FOR_8B_JUDGE
            ↓ (§15.14-A6 PROPOSED → EFFECTIVE)
§15_14_V6_RUNNING_UNDER_A6_MISTRAL_FALLBACK_FAMILY_CONTROL_TEST
            ↓ (run reached judge-load; LABEL_TOKEN_ENCODING_AMBIGUOUS fired)
ANNOTATION_FAILED_ON_MISTRAL_7B_VIA_A4_PRECONDITION_NO_KAPPA_PRODUCED
            ↓ (user bounded sign-off; this commit)
§15_14_V6_CLOSED_AS_ANNOTATION_FAILED_WITH_FAMILY_CONTROL_TEST_NOT_COMPLETED
```

## Provenance

- §15.14 v1 OUTCOME: `docs/experiments/probe_framing_15_14_OUTCOME.md` (commit `2d88be1`)
- §15.14 v2 OUTCOME: `docs/experiments/probe_framing_15_14_v2_OUTCOME.md` (commit `198378e`)
- §15.14 v3 OUTCOME: `docs/experiments/probe_framing_15_14_v3_OUTCOME.md` (commit `257dd24`)
- §15.14 v4 OUTCOME: `docs/experiments/probe_framing_15_14_v4_OUTCOME.md` (commit `2bf65b7`)
- §15.14-A6 PROPOSED: commit `980ba53`
- §15.14-A6 EFFECTIVE: commit `1d1c520`
- §15.14-A6 v6 Mistral-7B run: judge-load reached; `LABEL_TOKEN_ENCODING_AMBIGUOUS` fired with diagnostic `'0' → [29473, 29502]`, `'1' → [29473, 29508]`, `'2' → [29473, 29518]`; exit 9; segfault during interpreter shutdown post-exit (does not affect outcome)
- v6 run hardware: runpod A100-80; same `framing_15_14_extractions.npz` cache as v1 / v2 / v3 / v4
- §15.14-A4 diagnostic cache (RunPod): `framing_15_14_annotated_A4_diagnostic.npz` (`diagnostic_only=True`); preserved unchanged through v6 run
- All artifacts preserved; no JSON / MD cascade output written (LABEL_TOKEN_ENCODING_AMBIGUOUS fired before writers).

## End of §15.14 v6 (closure across all six tested judge configurations; family-control test not completed under locked A4 extraction)
