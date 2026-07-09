# B1.8 — Context-Resolved KCPR Layer-1 Probe (PREREGISTRATION, docs-only)

**Status:** preregistration / design spec. **No generation. No evidence freeze. No judging. No `GENUTILITY_*`
label.** This document specifies — before any data — a probe that tests *true* context-conditioned KCPR
Layer-1 pole resolution, the mechanism B1.6/B1.6-v2 did **not** exercise.

**Readiness label: `CONTEXT_RESOLVED_KCPR_PREREG_READY`** (design complete). **Execution remains gated:**
generation must not start until a concrete deterministic resolver (per §5, Option A) is authored and frozen
(§8), or the run is `CONTEXT_RESOLVED_KCPR_BLOCKED_RESOLVER_UNSPECIFIED`.

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked; Track B blocked. No ontology, no Sanskrit
privilege, no semantic-truth claim. **Structure, not validated meaning.**

---

## 1. Question

Does a **preregistered, context-conditioned KCPR pole-selection layer** — context → select the appropriate
pole per varṇa → generate from the *selected* pole — improve blind-rated generation quality over: the
**unresolved both-poles** Symbol-U scaffold, a **scrambled-resolved** control, a **plain** baseline, a
**generic-structured** baseline, and a **semantic** baseline?

The decisive sub-question: does a *selected-pole* Symbol-U beat a **scrambled-selected-pole** control — i.e.,
does the *specific* varṇa→pole content carry signal once a selection is actually made?

## 2. Scope limitation inherited from B1.6-v2 (why this probe exists)

Established by inspection of the frozen v2 scaffold and the rendered prompt (recorded in
`B1_6_EXPLORATORY_10_SAMPLE_RESULTS.md` §11b):

- B1.6-v2 shows **both** poles of every varṇa (`worldly_binding_pole` **and** `spiritual_liberating_pole`).
- **No pole is selected by context.** The frozen frame carries only `worldly_binding_pole`,
  `spiritual_liberating_pole`, `named_attribute` — no `selected_pole`/`context` field.
- The prompt hands resolution to the **LLM** ("let each element's pole-pair color the reading as a tension
  field; synthesize a specific reading of THIS item"); context was a stub ("A common noun.").
- **Therefore B1.6-v2 tests unresolved-scaffold utility only.** Its null (no benefit; ≈ scramble) applies to
  the both-poles dump, **not** to a context-resolved Symbol-U, which was never operationalized (KCPR / Kosha
  resolution is `KCPR_EXPANSION_NOT_FOUND` / `DEFERRED` in the sources).

This probe operationalizes exactly the missing step, under preregistered, non-circular constraints.

## 3. Layer-1 definition

**KCPR Layer-1** is a function, fixed before generation:

- **input:** `(target_item, context)` — a target word plus a *rich* frozen context (§7), not a stub.
- **process:** a **deterministic, frozen context→pole rule** (§5) applied per varṇa.
- **output:** for each varṇa in the target's supported sequence, **one selected pole** (`worldly_binding` xor
  `spiritual_liberating`) — **not both**. The generator prompt then presents only the *selected* pole per varṇa.

Layer-1 is the manipulated mechanism. Everything downstream (prompt template, output format, judging) is held
identical to B1.6 so the only change under test is *resolution vs no-resolution*.

## 4. The resolver trap (the central methodological risk)

Two failure modes make a "context-resolved" result meaningless:

- **LLM-resolves** → if a language model reads the context and picks the pole, the experiment measures the
  **LLM's world knowledge**, not the varṇa mapping. (This is precisely what B1.6-v2 did implicitly.)
- **Human-resolves-per-item** → if the researcher hand-picks a pole per target, especially after seeing any
  output, the experiment measures **post-hoc human tuning**, not the scaffold.

**Requirement:** resolution MUST be **pre-registered, deterministic, and frozen before generation**, and applied
**identically** to the real mapping and to the scrambled control. No option fully escapes the fact that *the
theory does not supply the rule*; the design therefore treats the chosen rule as a **named, frozen candidate**
and interprets results **conditional on that resolver** (§11). The scrambled-resolved control (§6, §10) is what
isolates "did the *specific* varṇa content matter" from "did *any* selection under this rule matter."

## 5. Candidate resolver designs

### Option A — Rule-based resolver (RECOMMENDED; least circular)
- Each context (§7) is assigned, **at target-design time and blind to any output**, a small set of
  **context tags** (e.g. `stratum`, a coarse `valence_orientation ∈ {binding-leaning, liberating-leaning,
  neutral}`, and optionally a `plane` tag from §5C).
- A **deterministic table** maps `(context_tag, varṇa_polarity_axis) → selected_pole`. The table is authored
  from the frozen `track_g_polarity_axes` / KCPR rulebook **before** generation and **hash-frozen**.
- No model, no per-item human choice at run time. Fully reproducible; auditable; frozen.
- **Residual honesty:** the *table itself* is a researcher-chosen candidate the theory does not supply → result
  is conditional on it (§11). This is the least-circular option because resolution contains **no learned
  world-knowledge** and **no post-hoc freedom**.

### Option B — Independent resolver model (secondary; MORE circular)
- A separate model (≠ the generators, ≠ the judges) reads `(item, context)` and selects a pole per varṇa. Its
  selections are **frozen before the generator runs** and never revised.
- Compared against a **scrambled-resolved** control produced by the *same* model on shuffled varṇa→pole
  assignments.
- **Caveat:** this **displaces** rather than removes the LLM-resolves circularity — a positive result conflates
  "the varṇa content helped" with "a capable model's context reading, applied to pole choice, helped." Use only
  as an exploratory secondary arm, clearly labelled.

### Option C — Plane/sphere resolver (structured refinement of A)
- First select a `plane ∈ {physical, mental, intellectual, spiritual}` from the context's pre-defined stratum
  (reuse the frozen `track_e` sphere structure and the B1.7 lens machinery), then map plane → pole via a frozen
  table.
- Deterministic if the stratum→plane map is frozen at design time. Cleanly composes with A (A keyed on
  `plane` as one of its context tags).

**Recommendation:** **Option A**, optionally structured by **Option C** (A+C hybrid: deterministic table keyed
on frozen `(stratum, plane, valence_orientation)` tags). Option B only as an exploratory secondary, with its
circularity flagged in every artifact.

## 6. Required controls (arms)

Identical prompt template / format / judging across all; the only differences are resolution and mapping.

| arm | mapping | resolution | isolates |
|---|---|---|---|
| `KCPR_SELECTED_POLE` | real varṇa→pole | **context-resolved (one pole)** | the mechanism under test |
| `SYMBOLU_UNRESOLVED_DUAL` | real varṇa→pole | both poles (B1.6-v2 style) | resolution vs no-resolution |
| `SCRAMBLED_SELECTED_POLE` | **scrambled** varṇa→pole | context-resolved (same rule) | **specific content vs any selection** |
| `SCRAMBLED_UNRESOLVED_DUAL` | scrambled | both poles | scramble baseline for the dump |
| `PLAIN_PROMPT_BASELINE` | — | — | floor |
| `GENERIC_STRUCTURED_PROMPT_BASELINE` | — | — | structure-without-content |
| `SEMANTIC_LLM_BASELINE` | dictionary/semantic | — | strong content ceiling |

The scrambled arms apply the **same frozen resolver** to shuffled varṇa→pole assignments (seeded derangement,
frozen before run), so `KCPR_SELECTED_POLE` vs `SCRAMBLED_SELECTED_POLE` differs **only** in whether the
varṇa→pole content is authentic.

## 7. Target / context design (rich contexts, fixed before generation)

Replace the B1.6 stub ("A common noun.") with **rich, frozen** contexts. Each target is authored with **one
context per stratum** it belongs to (contexts are 1–3 sentence scenarios, fixed at design time, blind to
outputs). Strata:

1. **concrete-object** context (physical use/setting);
2. **psychological/mental** context (inner/felt scenario);
3. **ethical/action** context (a choice or duty);
4. **spiritual/contemplative** context;
5. **brand/name** context (naming/identity scenario);
6. **emotionally-charged non-clinical** context.

Each context carries the design-time tags the resolver keys on (§5A): `stratum`, `valence_orientation`,
`plane`. **Contexts and tags are hash-frozen before any generation** and never edited afterward. The same
`(target, context)` pairs are used across all arms so context is held constant while resolution varies.

## 8. No post-hoc pole choice (integrity constraints)

- **No** per-item manual pole edits after seeing any output.
- **No** changing the resolver, table, tags, contexts, seed, or arm set after results exist.
- **No** target-specific rescue, dropping, or re-rolling of individual items to improve a contrast.
- Resolver table, context set, scramble seed, and arm definitions are **hash-frozen** in an evidence-freeze
  declaration **before** generation (same gating discipline as B1.6/B1.7). Any change after freeze ⇒ a new,
  separately-named preregistration.

## 9. Evaluation (blind generation + blind judging)

- **Blind generation:** outputs re-blinded; generator identity only in hidden metadata.
- **Judges see:** `target`, `context`, `generation_text`, `output_format`.
- **Judges do NOT see:** arm, pole selections, resolver output, generator identity, or any
  Symbol-U/varṇa/KCPR/scaffold metadata (enforced by the shared whole-word leak matcher + Sanskrit-term filter;
  a leaking output is dropped, never the run).
- **Rubric:** reuse the frozen B1.6 1–7 dimensions + penalties; ratings-freeze before unblinding; unblind only
  at aggregation. Judge models differ (model + family) from generators.

## 10. Make-or-break contrasts (pre-committed)

- **PRIMARY:** `KCPR_SELECTED_POLE` vs `SCRAMBLED_SELECTED_POLE` on the penalty-adjusted composite (and, as a
  pre-registered secondary endpoint, on `specificity_to_target` — the one dimension that leaned in B1.6). If
  these are indistinguishable, the *specific* varṇa→pole content adds nothing even when a selection is made.
- **SECONDARY:** `KCPR_SELECTED_POLE` vs `SYMBOLU_UNRESOLVED_DUAL` — does resolution beat the both-poles dump at
  all? (Tests whether Layer-1 changes anything vs B1.6-v2.)
- **SECONDARY:** `KCPR_SELECTED_POLE` vs `PLAIN` / `GENERIC_STRUCTURED` / `SEMANTIC` — external calibration.

Analysis (paired-by-item, arm means + bootstrap CIs, paired win-rates) and any powering decision are fixed here,
before data. Exploratory sample sizes are descriptive only; a confirmatory run pre-commits N and the primary
endpoint before looking.

## 11. Interpretation (what results can and cannot license)

- **Positive** (`KCPR_SELECTED_POLE` > `SCRAMBLED_SELECTED_POLE`, and ideally > `SYMBOLU_UNRESOLVED_DUAL` and
  baselines): suggests **context-resolved scaffold utility under this specific frozen resolver**. It is
  hypothesis-generating; a confirmatory pre-registered run is required before any standing claim.
- It **cannot** prove: ontology; Sanskrit privilege; semantic truth; that varṇas objectively contain meaning.
  A positive is always **conditional on the chosen resolver** (§4, §5A residual).
- **Negative** (indistinguishable from scrambled-resolved): **this context-resolved candidate did not show
  utility under the tested resolver.** It does not refute all possible resolvers, but — combined with B1.6-v2's
  unresolved null and B1.4b′ upstream — it further constrains where any Symbol-U signal could hide.

## 12. Compatibility with B1.6-v2 (naming rationale)

This is a **new track, B1.8**, not `B1.6-v3`. Rationale: B1.6-v1/v2 were **representation** refreezes of the
*same unresolved mechanism* (directional → named-vṛtti). B1.8 changes the **generative mechanism** (adds a
context-conditioned resolution layer + new arms + rich contexts), and B1.7 already broke strict v-sequencing.
B1.8 **reuses** B1.6's frozen varṇa sources, rubric, adapter, blinding, and judging harness unchanged; it does
**not** modify any B1.6-v2 generation file. (If a future maintainer prefers, it can be aliased as "B1.6-v3
mechanism variant" — the artifacts are compatible either way.)

## 13. Readiness label

**`CONTEXT_RESOLVED_KCPR_PREREG_READY`** — the *design* is complete and internally consistent.

Failure labels the execution phase must emit instead, if triggered:
- `CONTEXT_RESOLVED_KCPR_BLOCKED_RESOLVER_UNSPECIFIED` — no concrete deterministic resolver table frozen (§5A).
- `CONTEXT_RESOLVED_KCPR_BLOCKED_CONTEXT_DESIGN` — contexts/tags not authored or not frozen before run (§7).
- `CONTEXT_RESOLVED_KCPR_INVALID_CIRCULARITY` — resolution done by an LLM at run time, or human pole choice
  after seeing outputs (§4, §8).
- `CONTEXT_RESOLVED_KCPR_INVALID_LEAKAGE` — arm/pole/varṇa/generator metadata reaches a judge (§9).

## 14. Guardrails

- **No generation run.** **No evidence freeze created.** **No judging.** **No `GENUTILITY_*` label.**
- No semantic-truth claim; no ontology; no Sanskrit privilege; no varṇa meaning invented; no target tuning.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked.
- **Structure, not validated meaning.**

---

## Final report

- **File created:** `experiments/primitive_sequence_recovery/B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md`
  (docs-only). **No B1.6-v2 generation file modified.**
- **Commit hash:** recorded on the commit below.
- **Selected naming:** **B1.8** (`B1_8_CONTEXT_RESOLVED_KCPR_LAYER1_PREREG.md`) — new track; rationale in §12
  (mechanism change, not a representation refreeze; B1.7 already occupies the next slot).
- **Readiness label:** `CONTEXT_RESOLVED_KCPR_PREREG_READY` (execution gated on freezing a concrete resolver).
- **B1.6-v2 limitation clearly recorded?** **Yes** — §2 (and cross-referenced to
  `B1_6_EXPLORATORY_10_SAMPLE_RESULTS.md` §11b): both poles shown, no context selection, LLM resolves
  implicitly, so B1.6-v2 tests unresolved-scaffold utility only.
- **Recommended resolver option:** **Option A** (rule-based, deterministic, frozen), optionally structured by
  **Option C** (plane-first) as an A+C hybrid; **Option B** exploratory-only (displaces, not removes,
  circularity).
- **No generation / evidence freeze / judging occurred.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

Context-resolved KCPR Layer-1 probe preregistered docs-only. No generation run. No evidence freeze. No judging.
No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.
