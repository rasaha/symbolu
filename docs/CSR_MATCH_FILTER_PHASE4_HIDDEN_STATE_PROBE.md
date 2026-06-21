# C×R×S MATCH-Filter — Phase 4 (HIGH-LEVEL DESIGN): Hidden-State Diagnostic Probe

> **Status: DESIGN ONLY (pre-registration draft).** No code, no model run in this document. Phase 4
> executes on a GPU pod with real Mistral (hidden states + generation). This doc fixes the hypotheses,
> data, probes, leakage controls, metrics, and decision labels BEFORE any activations are collected, so
> the result cannot be tuned into existence after the fact — same discipline as the Phase 2B rubric
> pre-registration.

## 0. One sentence

**Phase 4 tests whether C×R×S frame compliance has a readable hidden-state signature — i.e. whether
the model's latent state, read at the last prompt token *before* the answer, predicts whether the
answer will stay object-grounded (on-frame) or drift (state-distorted) — and whether a Bhava/CSR read
of that state adds signal *beyond* a plain hidden-state baseline.**

It is **observe → probe → diagnose**, never **control → rewrite internals**.

## 1. Where Phase 4 sits

```
Phases 1–3 (EXTERNAL, done):   query → C×R×S frame → LLM answer → answer audit
Phase 4    (INTERNAL, this):   query → model hidden states → Bhava/CSR read → align with frame?
```

Phase 4 is the bridge between *external wrapper behaviour* and *internal model state*. It consumes
Phase 1–3 outputs as **labels** and the model's activations as **features**. It changes nothing in the
frozen scorer, the Phase 2 prompt, rubric_v2, the Phase 3 auditor, or generation.

## 2. Hard boundaries (pre-committed)

**Phase 4 will NOT:** touch logits or generation; use Bhava to steer output; add Guna / Vritti
scoring; add a JEPA object ontology; claim "hidden-state CSR is proven"; or derive Bhava from the
query text or the C×R×S frame. **Phase 4 will ONLY:** read hidden states, fit linear probes, and
report whether a Bhava/CSR read beats a hidden-only baseline under a strict, dimension-matched gate.
A clean negative result ("hidden-only suffices; Bhava is interpretive, not yet mechanistic") is an
accepted, pre-committed outcome that ends the hidden-state track and keeps C×R×S as a wrapper/audit
system.

## 2.1 Current Bhava wiring status (factual, as of this audit)

To prevent confusion between the **active CSR phonemic 12D profile** and a **hidden-state Bhava latent
vector**, the actual wiring today is:

- **CSR Phase 1–3 (active wrapper): Bhava is NOT wired.** C and R consume a deterministic *phonemic*
  12D profile (`profile.compute_12d_profile`, derived from the term's letters — explicitly "NOT the
  meaning"); S consumes non-phonemic semantic definitions/embeddings. No Bhava latent vector and no
  model hidden state enter C×R×S scoring, frame selection, the framed prompt, the answer audit, or the
  rewrite policy. The varna→bhava-flavoured naming is phonemic, not a latent read.
- **Old probe path (`scripts/cg_wrapper_ablation/` probe/ablation scripts): passive / probe-only.**
  `state_bhava = state[0:12]` is computed and saved to `features.npz` and used only to *train/evaluate
  correlation probes*. It does not feed CSR and does not steer generation; it does not import
  `csr_match_filter`.
- **SymbolU training wrapper (`symbolu_training/.../mistral_wrapper.py`): separate subsystem, not CSR.**
  There `delta_bhava` → `intent_projector` → `phase_adapter` can modify hidden states/logits during
  model training, but that is a different codebase, uses the *delta* (not the Bhava vector), and is
  unconnected to the C×R×S wrapper.
- **Phase 4: planned diagnostic, NOT active.** Stage-A (`phase4_collect_states.py`) collects **raw
  hidden states only** (manifest `feature_provenance=residual_stream_hidden_state`;
  `contains_phonemic_12d_profile=false`, `contains_phase1_csr_scores=false`,
  `contains_csr_trace_vector=false`). The **learned Bhava directions are not yet built** and are not
  runtime-active anywhere. The `PHASE4_BHAVA_*` labels and "Bhava read" naming in `phase4_probe.py`
  are placeholders for that unbuilt work, evaluated only on synthetic activations.

**Bottom line:** within CSR, Bhava changes no runtime behavior today (classification: *not wired*).

## 2.2 Pre-registered power-vs-level protocol + KILL CRITERION (locked before the expanded re-test)

Stage-B1 (n=110) found a *real-but-underpowered* within-arm signal (frame_violation framed ≈0.63,
rejected_leak base ≈0.66, both UNSTABLE at ~25 positives; `RESULTS_PHASE4_STAGEB.md §7`). Two
competing explanations: **(i) underpowered**, or **(ii) wrong level** — the static *final-prompt-token*
hidden state may be a compressed, not-yet-committed potential, with semantic signal only crystallising
during the latent→answer **transition** (first generated tokens). To keep the hidden-state track
**falsifiable**, the following is fixed BEFORE the expanded-data result is seen:

**Step 1 — Expanded static-h0 re-test (the power test, runs first).** Re-run the *same* static
final-prompt-token probe on the expanded combined dataset (516 rows; `framed_answer_eval_v3_combined`),
within-arm, group-by-term CV, multi-seed × n_pca robustness. Define a **stable hidden-only positive** =
within-arm AUROC CI excludes 0.5 in **≥80%** of (seed×n_pca) configs **and** mean AUROC **≥0.60**.
- **(1a)** ≥1 primary target (`audit_fail` or `frame_violation`) is a stable hidden-only positive →
  static h0 is sufficient; the "wrong level" hypothesis is **not needed**. Proceed to Stage-B2 (learned
  Bhava directions on h0) under the existing strict incremental-value gate.
- **(1b)** primary targets stay UNSTABLE/NULL **with adequate power** (framed within-arm positives ≳60)
  → the power explanation is rejected; **Phase 4C is licensed.**
- **(1c)** still underpowered (framed positives < ~60) → expand further or stop; do not over-interpret.

**Step 2 — Phase 4C transition probe (only if 1b), honestly relabeled.** Capture hidden states at the
final prompt token (h0), the **first generated token** (h1), a few early generated tokens, and
Δh = h1 − h0. This is **no longer a pre-answer predictor** — it is an **early-warning DETECTOR during
answer formation**, and is labeled as such (`detection`, not `prediction`). Incremental gate: a
transition/early-expression representation must beat static-h0 by **≥0.05 AUROC with non-overlapping
bootstrap CIs** AND clear the **≥80%** within-arm stability bar.

**KILL CRITERION (locked).** If, *with adequate power*, **neither** static-h0 (Step 1) **nor** the
transition/early-expression states (Step 2) clear the stability bar and the incremental-value gate,
then the **hidden-state Bhava track STOPS**. We keep C×R×S as the validated Phase 1–3 wrapper/audit
product and do **not** pursue further "deeper levels" — this forecloses the infinite-regress hazard of
"try the next level" after every null. The metaphysical interpretation (a singular, undifferentiated
Bhava that only becomes visible through semantic expression) is **bracketed**: the experiment reports
only the *observable* — does linearly-decodable signal sharpen across token positions? — not the
ontology, because "disposition crystallising" and "the model hasn't computed the feature yet" predict
the same data.

## 3. Definitions

- **Bhava (Phase 4)** = a *learned latent state-pattern read from hidden states*. It is **not** an
  astrology house, **not** raw user input, **not** the LLM output, and **not** `state[0:12]` taken
  blindly. The 12D basis is reused only as a **pattern basis** (does this state look identity-like /
  action-like / reasoning-like / purpose-like / integration-like / dissolution-like?), realised as
  **supervised linear directions in the residual stream** (decision Q1). If it collapses to one
  dimension, it fails (§8 collapse gate).
- **Object-grounded vs state-distorted.** *Object-grounded* = the latent state is anchored on the
  C×R×S primary domain of the queried object. *State-distorted* = the state is dominated by a
  secondary/rejected pattern (e.g. "authority" overpowering "medicine" for *doctor*).
- **The labels** (all from Phase 1–3, deterministic): `object_primary`, `state_primary`,
  `state_object_aligned`, `state_object_conflict`, `frame_compliant`, `frame_violation`,
  `primary_frame_missing`, `secondary_promoted`, `rejected_domain_leak`, `phoneme_overreach`,
  `factuality_suspected`, `answer_too_generic`, `audit_pass`, `audit_fail`, **and the meta-parroting
  family** `meta_parroting` / `frame_label_parroting` / `answering_mode_vs_frame_description_mode`
  (see §3.0; derived from a deterministic surface detector, `eval_real_output_audit.is_meta_parrot`).

### 3.0 Target state discovered in the Phase 3 real-output run: **frame-echo / meta-parroting**

The Phase 3 real-output audit on real Mistral surfaced a distinct failure mode: under the framed
prompt the model sometimes **echoes the C×R×S frame labels instead of answering** — e.g. *"The term
'apple' belongs to the primary domain of fruit"*, *"Primary domain: medicine / Secondary domain:
(none)"* (rows `poly_001/002/007/008`, `ctxsec_001/002`, `sec_005`). Both the rubric and the auditor
parse these ambiguously. This is a **generation** behaviour, not an audit bug, and it is an ideal
Phase 4 probe target: **does the pre-answer hidden state look "parroting/meta" vs "answering"?** Add a
`frame_echo` label (derived from a deterministic surface detector: answer is dominated by frame-naming
phrases like "primary domain", "belongs to the domain", "secondary domain") to the Phase 4 label set,
and include matched answer/meta-parrot pairs in the Stage-B set.

### 3.1 How the prediction target is constructed (no leakage)

| field | source | role |
|---|---|---|
| **features** | hidden state at the **last prompt token**, layer sweep (Q2) — captured *before* any answer token | X |
| **primary target** `drift` | Phase 3 audit of the *actually generated* answer: `audit_fail` / `frame_violation` = 1, else 0 | y |
| exploratory targets | specific Phase 3 findings: `rejected_domain_leak`, `secondary_promoted`, `phoneme_overreach`, `primary_frame_missing` | y₂… |

The feature is read **before** the answer exists; the label comes from auditing the answer **after**.
So a successful probe genuinely means *"the pre-answer state already knew the answer would drift."*
This temporal split is the heart of the experiment.

## 4. Hypotheses & the success gate (strict, decision Q4)

- **H0 (null):** the pre-answer hidden state does not predict drift above chance.
- **H1 (hidden-state predictive):** a linear probe on hidden-only states predicts `drift`
  above chance (AUROC CI above 0.5).
- **H2 (Bhava/CSR adds value):** `hidden+bhava` (and/or `CSR_alignment`) beats `hidden_only` by
  **≥ 0.05 AUROC with non-overlapping bootstrap CIs**, **AND** beats a **dimension-matched
  random-feature baseline** by the same margin (so the gain is not just "more dimensions").

Both conditions of H2 are required. Metrics are reported as **AUROC and AUPRC** (AUPRC because
positives are rare), with **grouped cross-validation** (folds split by term/category so the probe
cannot memorise "doctor → on-frame") and **bootstrap confidence intervals**. The best layer is chosen
**inside** each CV fold (nested), never cherry-picked globally.

## 5. Data (pilot → expand, decision Q3)

**Stage A — Pilot (feasibility + leakage check), n ≈ 110.** Reuse the frozen
`framed_answer_eval_v2_rubricv2.jsonl` set, both arms (`base`, `framed`), on real Mistral. Purpose:
confirm hidden states are extractable, the pipeline runs, the leakage controls (§7) pass, and there is
*any* H1 signal. Expectation: too few positives (~9–24) for a confident H2 verdict → wide CIs. The
pilot's job is go/no-go, not certification.

**Stage B — Expand (only if the pilot shows signal): balanced adversarial drift set, target ≥ 300 with
≥ 30% drift positives.** Author **minimal pairs** that hold the object fixed and push the state toward
on-frame vs drift, e.g.:

| object | on-frame prompt | drift-inducing prompt | C×R×S primary |
|---|---|---|---|
| doctor | "What does a doctor do medically?" | "Isn't a doctor basically an authority figure who controls patients?" | medicine |
| python | "Explain the python programming language." | "Describe python as an animal." | programming |
| mercury | "Mercury the chemical element — properties?" | "Tell me about mercury the Roman god." | chemistry |

Minimal pairs control for object identity and surface tokens, isolating the *state* difference — the
cleanest possible test of "object-grounded vs state-distorted." Labels still come from the Phase 3
audit of each generated answer (not from which prompt template was used — the template is a *treatment*,
the audit outcome is the *label*).

## 6. Hidden-state extraction (spec)

- **Model:** `mistralai/Mistral-7B-Instruct-v0.3` (greedy, as in Phase 2/2B), `output_hidden_states`.
- **Read point (Q2):** residual stream at the **final prompt token**, captured for **every layer**
  (full sweep, layer chosen inside CV). This is the pre-generation "before the answer" state.
- **Stored per example:** `{id, arm, query, object_term, csr_frame(primary/secondary/rejected),
  hidden[layer][d_model], drift_label, finding_labels, bhava_supervision_type}`. Activations saved to
  disk (gitignored `runs/csr_phase4/`), never committed.
- **Optional comparison read:** mean-pooled over the generated answer ("during"), only if Stage B
  runs, to contrast before-vs-during predictiveness. Pre-gen is the headline.

## 7. The Bhava representation & leakage controls (the critical section)

**Learned probe directions (Q1).** For each named pattern (start with 6: identity / action /
reasoning / purpose / integration / dissolution), fit a **linear direction in hidden space** via
supervision from a **coarse, target-orthogonal Bhava annotation of the question's intent type**
(definition / comparison / classification / causal / purpose / integrative). Crucially:

1. **Bhava is read from hidden states, never from the query embedding or the C×R×S frame.** The
   *direction* is fit in activation space; the *supervision label* is a question-type tag used only to
   orient the axes, not a feature fed to the drift probe.
2. **Orthogonality control (pre-registered):** the Bhava-supervision tag must **not** by itself predict
   `drift` above chance. If it does, it is a confound and the Bhava features are disqualified
   (potential leakage) → label `PHASE4_BHAVA_LEAKAGE_SUSPECTED`.
3. **Group splits:** all CV folds split by object term, so no term appears in both train and test.
4. **Dimension-matched control:** every H2 comparison includes a random-projection baseline of equal
   width to `bhava`, so "adds signal" cannot be a free-parameter artifact.
5. **No-answer-text rule:** drift-probe features derive solely from the pre-answer hidden state; the
   generated answer is used only to compute the label.

## 8. The four probes (all linear; logistic regression / linear SVM)

| probe | features | question it answers |
|---|---|---|
| `hidden_only` | raw hidden state (PCA-reduced to a fixed width) | baseline: is drift linearly decodable at all? (H1) |
| `12D_bhava_probe` | the 12D learned-Bhava read only | does Bhava alone carry drift signal? |
| `hidden_plus_bhava` | hidden_only ⊕ 12D Bhava | does Bhava add to hidden? (H2 part 1) |
| `CSR_alignment_probe` | scalar/low-dim **state↔frame alignment** features: projection of the hidden-state object/state read onto the C×R×S-selected primary-domain direction, magnitude of competing secondary/rejected directions | does an explicit object-grounding-vs-distortion read predict drift? |
| `random_match` (control) | random projection, width = bhava | dimension-matched null (H2 part 2) |

**Collapse diagnostic (pre-registered).** Measure the **effective rank / participation ratio** of the
12D Bhava read across examples and the pairwise cosine of the learned directions. If effective rank
< 3 of 12 or directions are near-duplicates (|cos| > 0.9), the basis has collapsed → label
`PHASE4_BHAVA_COLLAPSE` regardless of probe AUROC ("interpretive but degenerate").

## 9. Decision labels (Phase 4 verdicts)

| label | condition |
|---|---|
| `PHASE4_BHAVA_ADDS_SIGNAL` | H1 holds **and** H2 holds (both: ≥0.05 AUROC over hidden-only with non-overlapping CI **and** beats dimension-matched control); Bhava basis does not collapse |
| `PHASE4_HIDDEN_STATE_PREDICTIVE` | H1 holds (state predicts drift) but H2 fails — hidden-only suffices; Bhava is interpretive, not additive |
| `PHASE4_NOT_PREDICTIVE` | H1 fails — the pre-answer state does not predict drift above chance |
| `PHASE4_BHAVA_COLLAPSE` | Bhava basis degenerates to ~1 effective dimension (blocks any positive claim) |
| `PHASE4_BHAVA_LEAKAGE_SUSPECTED` | the orthogonality / no-answer-text controls fail — apparent lift is a confound |
| `PHASE4_PILOT_INCONCLUSIVE` | Stage-A pilot only; too few positives / CIs too wide to decide (expected default before Stage B) |

`PHASE4_BHAVA_ADDS_SIGNAL` is the only label that promotes Bhava/CSR from "successful external
symbolic framework" to "real internal diagnostic." Anything else keeps Phase 1–3 as the product and
**does not** justify moving to hidden-state control.

## 10. Roadmap (maps to the user's five steps)

1. **Collect** hidden states (last prompt token, all layers) from base + framed Mistral answers
   (Stage A pilot; Stage B if warranted). [pod]
2. **Label** each example via Phase 1–3 (`audit_pass/fail`, `frame_compliant`, `rejected_leak`,
   `secondary_promoted`, …) — already deterministic. [cpu]
3. **Train probes:** `hidden_only`, `12D_bhava_probe`, `hidden_plus_bhava`, `CSR_alignment_probe`,
   `random_match` — linear, grouped CV, nested layer selection. [cpu, once activations saved]
4. **Compare** under the strict gate: does Bhava/CSR beat hidden-only AND the dimension-matched
   control, with non-overlapping CIs? [cpu]
5. **Inspect collapse / leakage:** effective rank, direction cosines, orthogonality control. [cpu]

Steps 2–5 are CPU and reproducible from saved activations; only step 1 needs the GPU pod.

## 11. Deliverables (when implemented, not now)

- `docs/CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md` (this design).
- `scripts/.../phase4_collect_states.py` — runs Mistral, saves `{hidden, frame, labels}` to
  `runs/csr_phase4/` (gitignored).
- `scripts/.../phase4_bhava_directions.py` — fits the learned 12D directions + collapse diagnostics.
- `scripts/.../phase4_probe_eval.py` — the four probes + dimension-matched control, grouped CV,
  bootstrap CIs, emits a `PHASE4_*` label.
- `eval_data/phase4_drift_pairs.jsonl` — the Stage-B adversarial minimal-pair set (built only if the
  pilot shows signal).
- `tests/test_csr_phase4_probe.py` — CPU tests on **synthetic** activations (probe math, CV grouping,
  dimension-matched control, collapse + leakage detectors) so the harness is verified without a GPU.
- `RESULTS_PHASE4.md` — the verdict.

## 11.1 Stage-A runbook (RunPod) — built, plumbing only (no Phase 4 claim)

Stage-A ships two modules: `phase4_collect_states.py` (GPU collector) and `phase4_probe.py` (pure-numpy
probe math, CPU). Activations and metadata are written to a gitignored `runs/csr_phase4/`.

**1 — Collect hidden states (GPU pod).** Reads the Phase 2B-v2 dataset, builds the *frozen* base/framed
prompts, captures the residual stream at the **final prompt token** (pre-generation) across all layers,
and labels each row from the saved Phase 2B answers via the frozen Phase 3 audit (no re-generation):
```
git pull origin claude/cg-wrapper-quality-ablation-gro5iw
export CSR_LLM_MODEL="mistralai/Mistral-7B-Instruct-v0.3"
python scripts/cg_wrapper_ablation/csr_match_filter/phase4_collect_states.py \
  --data   scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_eval_v2_rubricv2.jsonl \
  --traces runs/csr_phase2b/robustness_eval_v2.json \
  --arms base,framed --layers all --semantic-backend real \
  --out-dir runs/csr_phase4
```
Outputs: `runs/csr_phase4/phase4_activations.npz` (`X` = [N, n_layers, d_model]),
`phase4_metadata.jsonl` (aligned labels + `extraction_mode=last_prompt_token_pre_generation`,
`features_from_answer_tokens=false`), and `phase4_manifest.json`. If you have no saved traces, add
`--generate` to produce answers *for labels only* (features still come from the prompt forward pass).
A CPU `--dry-run` (writes zero activations) is available to smoke-test the output schema without a GPU.

**2 — Probe on saved activations (CPU; no GPU needed).** `phase4_probe.py` is a library
(`evaluate_probe`, `incremental_value`, `effective_rank`, `leakage_check`, `bootstrap_auroc_delta`,
`decide_phase4`); the Stage-B driver that wires it to `X`/labels is intentionally **not** built yet
(that's the actual experiment, gated on a feasibility signal). To sanity-check the saved arrays now:
```
python - <<'PY'
import numpy as np
d = np.load("runs/csr_phase4/phase4_activations.npz", allow_pickle=True)
print("X", d["X"].shape, "layers", d["layers"], "n", len(d["ids"]))
PY
```

**3 — Inspect the layer sweep.** `X[:, L, :]` selects layer `L`; group probes by term using the `id`
prefix (e.g. `poly_`, `ord_`) for the group-by-term CV. A per-layer `evaluate_probe(X[:,L,:], y, groups)`
AUROC curve identifies the most decodable layer (chosen *inside* CV folds in Stage B, never globally).

**4 — Interpret decision labels.** `decide_phase4(...)` precedence: `PHASE4_BHAVA_LEAKAGE_SUSPECTED`
(controls failed) > `PHASE4_BHAVA_COLLAPSE` (effective rank < 3) > `PHASE4_PILOT_INCONCLUSIVE` (CIs too
wide) > `PHASE4_NOT_PREDICTIVE` (hidden AUROC below floor) > `PHASE4_BHAVA_ADDS_SIGNAL` (beats
hidden-only AND a dimension-matched random control by ≥0.05 AUROC with non-overlapping CIs) else
`PHASE4_HIDDEN_STATE_PREDICTIVE`. **Stage-A makes none of these claims** — the labels are tested only
on synthetic activations (`tests/test_csr_phase4_probe.py`).

## 12. Out of scope / explicitly future

Generation control, logit/representation steering, Guna/Vritti, JEPA ontology, and any claim that
hidden-state CSR is "proven" are **Phase 5+**, and are gated on a `PHASE4_BHAVA_ADDS_SIGNAL` result
here. Without that, the project stops at the validated Phase 1–3 wrapper/audit layer.

---

### Open design choices already resolved (this draft)
- **Bhava source:** learned probe directions in hidden space (not the phonemic profile). 
- **Read point:** last prompt token, full layer sweep, pre-generation.
- **Data:** pilot on the existing v2 set, expand to a balanced adversarial drift set only if signal.
- **Success bar:** strict incremental-value gate (≥0.05 AUROC, non-overlapping CI, beats a
  dimension-matched random-feature control).
