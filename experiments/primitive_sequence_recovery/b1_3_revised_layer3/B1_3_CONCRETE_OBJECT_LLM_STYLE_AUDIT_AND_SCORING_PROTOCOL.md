# B1.3 Concrete-Object LLM Judged-Modulation — Style-Audit & Scoring Protocol

## 1. Scope and status

Protocol/specification only. **No final evidence stimuli generated · no LLM judge run · no scoring · no
EVIDENCE_FREEZE · no positive label earned · prior results unchanged.** Specifies the style-audit, LLM judge
prompt, scoring plan, semantic-only baseline check, thresholds, and success/kill criteria for the
concrete-object LLM judged-modulation study whose word set (`CONCRETE_OBJECT_WORDLIST_SPEC`) and instrument
allowance (`LLM_OBJECT_MODULATION_PROTOCOL_READY`) are already drafted. **Structure, not validated meaning.**

## 2. Why the style audit is essential

If `A_real` options are longer, clearer, more fluent, warmer, more concrete, or more function-aligned **by prose
quality**, an LLM judge may pick them for **style**, not for object-function modulation-fit. The task must
isolate **object-function modulation-fit** from writing quality. Because LLMs tend to **auto-correct or
flatter weaker arms**, the stimulus format must be tightly constrained and audited *before* any evidence
judging — a style advantage in `A_real` would make a "win" uninterpretable.

## 3. Stimulus format

Constrained 4-field-tag format, identical for every arm:

> *"Within the fixed meaning, this object is modulated by [tag1], [tag2], [tag3], and [tag4]."*

The style audit must verify: **same number of tags (4)** · **similar tag length** · **similar
abstraction/concreteness** · **no visible arm markers** · **no Sanskrit/varṇa vocabulary** · **no poetic
language** · **no denotation change** · **no arm-specific explanation advantage** (no arm gets to justify
itself where others cannot).

## 4. LLM judge task wording

Primary judge wording (exact):

> *"Given the dictionary meaning of the object, which option gives a more fitting inner tendency or field around
> this object without changing what it is?"*

Plain variant:

> *"Which option is more naturally suited to the object's ordinary function?"*

**Avoid:** *which is deeper? · which is spiritual? · which is poetic? · which is Sanskritic? · which defines the
object?* — each invites style/doctrine/denotation judgment instead of modulation-fit.

## 5. LLM judge panel

- **Multiple model families** where available (no single-family dependence).
- **Fixed prompts** (both wordings above), identical across arms and items.
- **Deterministic or controlled temperature** (low, recorded).
- **No chain-of-thought required**; a short rationale is **optional, diagnostic-only** (never part of the
  scored outcome).
- **Position balancing** (each arm appears left and right equally).
- **Randomized item order**.
- **Blinded arm labels** (judge never sees A_real/R_*; private truth-map stored separately).

## 6. Primary endpoint

**A_real win-rate vs R_deranged** on the **primary concrete-object set**. `R_deranged` (another object's real
varṇa field) tests whether the modulation is **object-specific** rather than merely coherent symbolic prose —
the crux B1.1/B1.2 found null (real≈deranged).

## 7. Required comparisons

Required: **A_real vs R_deranged · A_real vs R_scrambled · A_real vs R_random · A_real vs X_neutral.**
Optional: A_real vs R_semantic_near · A_real vs R_varṇa_near.

## 8. Semantic-only baseline check (required)

Give a judge the **dictionary anchor + neutral object-function descriptors only, without any varṇa
modulation** — or compare `A_real` against a **simple object-function heuristic baseline** derived from the
dictionary meaning. **Purpose:** determine whether the LLM is merely matching **ordinary object semantics** read
off the anchor. **If the dictionary/object-function baseline performs as well as `A_real`, the Symbol-U-specific
claim fails** (the modulation adds nothing beyond ordinary semantics).

## 9. Style-tell audit

Before evidence judging, an auditor (or an LLM style-tell judge) attempts to **identify which option is
`A_real` from surface style alone**. If `A_real` is identifiable **above threshold** by style → **STOP** or
revise **globally**. **No per-item hand rescue**; only **global template-level** fixes are allowed before
freeze.

## 10. Denotation-leakage audit

Verify: **no option changes the object** · **no option introduces a function not in the anchor** · **no option
uses the target word or an obvious synonym as a field tag** · **no arm reveals the dictionary meaning more
directly than others**. Any leakage → global fix or exclusion before freeze.

## 11. Quality-parity audit

Verify: **grammar parity · length parity · tag clarity · no nonsense control arms · no `A_real` fluency
advantage · no control-arm degradation.** Controls must be *plausible*, not straw men — a degraded control
would manufacture a false `A_real` win.

## 12. Success criteria

To earn a future `LLM_OBJECT_MODULATION_SIGNAL`, **all** must hold:

1. `A_real` beats `R_deranged`.
2. `A_real` beats `R_scrambled`.
3. `A_real` beats `R_random`.
4. `A_real` beats `X_neutral`.
5. `A_real` beats **or adds beyond** the semantic-only / object-function baseline.
6. Style-tell audit passes.
7. Denotation-leakage audit passes.
8. Quality-parity audit passes.
9. Result holds on **primary concrete objects**.
10. Result is **not** driven by secondary/diagnostic words.
11. Result is **not** driven by one LLM judge family.
12. Survives multiplicity correction or the preregistered CI rule.

## 13. Kill criteria

**STOP** if any: `A_real ≈ R_deranged` · `A_real ≈ R_scrambled` · `A_real ≈ R_random` · `A_real ≈ X_neutral` ·
`R_scrambled` matches or beats `A_real` · semantic-only/object-function baseline matches `A_real` · style-tell
audit fails · denotation-leakage audit fails · controls are lower-quality or nonsensical · result appears only
in the diagnostic/high-confound set · result depends on one judge model only · thresholds are changed after
results.

## 14. Statistical plan

- **Forced-choice binary outcome** per (item, comparison, judge).
- **Aggregate win rates** per comparison, with **confidence intervals**.
- **Item-level and model-family-level reporting**.
- **Mixed-effects logistic model** (item + judge random effects) if feasible; win-rate + CI otherwise.
- **Multiplicity correction** across the required controls (Holm or equivalent).
- **Predefined invalid-response handling** (unparseable/refused/tie → predeclared rule).
- **No post-hoc exclusions** except predeclared invalid cases.

## 15. Draft thresholds

- **Primary:** `A_real vs R_deranged` **lower CI bound > 0.50**.
- `A_real` **directionally > 0.50** against all required controls.
- **Corrected significance** or a **preregistered CI rule**.
- **No single item-family dominance** (win not carried by one object family).
- **No single model-family dominance**.
- **Semantic-only baseline must not match `A_real`**.

**These are DRAFT thresholds — not EVIDENCE_FREEZE thresholds.** They are revisable until an explicit freeze.

## 16. Judge-output format

Machine-readable per judgment: `item_id` · `comparison_id` · `model_id` · `left_arm`/`right_arm` (hidden
internally, revealed only at scoring) · `selected_option` · `confidence` (optional) · `rationale` (optional,
diagnostic-only) · `parse_status` · `invalid_flag`.

## 17. No post-hoc rescue rule

**No** changing the word list after seeing judge results · **no** removing failed objects unless pre-specified ·
**no** changing thresholds · **no** rewriting stimuli after audit except **global template fixes before
freeze** · **no** treating secondary/diagnostic wins as primary evidence.

## 18. Draft JSON protocol requirements

- **Scoring JSON** (`b1_3_concrete_object_llm_scoring_protocol_draft.json`) includes: `primary_endpoint` ·
  `required_comparisons` · `semantic_baseline_check` · `draft_thresholds` · `exclusion_rules` ·
  `analysis_methods` · `allowed_future_label: LLM_OBJECT_MODULATION_SIGNAL` · `evidence_freeze_declared: false`.
- **Style-audit JSON** (`b1_3_concrete_object_llm_style_audit_protocol_draft.json`) includes: `audits_required`
  · `pass_fail_rules` · `leakage_checks` · `quality_parity_checks` · `style_tell_threshold_draft` ·
  `evidence_freeze_declared: false`.

## 19. Remaining blockers after this protocol

Final screened primary object list · final generation/arm artifacts · actual style-audit execution and result ·
semantic-baseline construction · final judge model list · final scoring script · final thresholds · manifest
hash binding · explicit EVIDENCE_FREEZE declaration.

## 20. Decision

```
DECISION: LLM_STYLE_SCORING_PROTOCOL_DRAFT_READY
```

The style-audit, judge prompts, panel, endpoint, required comparisons, semantic-only baseline, statistical
plan, draft thresholds, output format, and success/kill criteria are specified and internally consistent, with
the confounds (style, prose, ordinary semantics, scrambled≈real, control degradation, single-model dependence)
named and gated. This is not `LLM_STYLE_SCORING_PROTOCOL_HIGH_RISK_NEEDS_REVISION` (the audits and kill
criteria control the known risks) and not `LLM_OBJECT_MODULATION_STUDY_NOT_SCORABLE_CLOSE_LINE` (the study is
scorable as an LLM object-fit pilot; the semantic-only baseline makes even a positive interpretable). Draft
thresholds remain revisable until an explicit EVIDENCE_FREEZE.

## 21. Final status block

```
document:                    B1.3 concrete-object LLM style-audit & scoring PROTOCOL (specification only)
decision:                    LLM_STYLE_SCORING_PROTOCOL_DRAFT_READY
instrument:                  LLM judge panel (blinded) for objective object-function modulation-fit
primary endpoint:            A_real win-rate vs R_deranged on primary concrete objects
required comparisons:        A_real vs R_deranged / R_scrambled / R_random / X_neutral (+ optional near)
semantic-only baseline:      REQUIRED — if it matches A_real, Symbol-U-specific claim fails
draft thresholds:            primary lower CI > 0.50; directional vs all controls; corrected sig / CI rule;
                             no single item-family or model-family dominance; baseline must not match A_real
final stimuli generated:     NO
ran LLM judges / scoring:     NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
human judged-modulation:     NOT yet run
LLM_OBJECT_MODULATION_SIGNAL: NOT earned
HUMAN_PROPENSITY_MODULATION_SIGNAL / PROPENSITY_MODULATION_SIGNAL: NOT earned
LLM_PROPENSITY_FIELD_DISCRIMINATION / LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
next:                        build final artifacts, execute style audit + semantic baseline, then freeze blockers
```

**Structure, not validated meaning.** The style-audit and scoring protocols are drafted for the concrete-object
LLM judged-modulation study; no final stimuli were generated, no judges were run, nothing was scored, prior
nulls and closures stand, Track B remains BLOCKED, and EVIDENCE_FREEZE is not declared.
