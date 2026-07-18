# Design Memo — Layer 2 as the Scored Representation (future formal experiment)

**Proposal only. Docs — no code, no implementation, no scorer, no model, no experiment, no result.** This is a scoring-architecture note. Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B **BLOCKED**; no ontology, no Sanskrit privilege, no semantic-truth claim.

**Governing reality (null prior).** Layer 2 is a *deterministic function of Layer 1*. Real-vs-scramble at Layer 1 already returned **NO_SIGNAL** in the committed `varna_lens` tests, and the archetype tests already scored transformation ARCs (essentially Layer-2-style renderings) → **NO_ARCHETYPE_SIGNAL**. So scoring Layer 2 makes the test **cleaner and more legible, not more likely to be positive**; the added X/D/C controls are hurdles, not opportunities. This is a **rigor upgrade to an already-negative line, not a rescue**, with a **null prior; most likely outcome remains NO_SIGNAL**.

## Labels
- **Sample inspection Layer 2** (current, `sample_text_rule_harness.py` + `H2_LAYER2_SYNTHESIS_MODE.md`) stays:
  `INTERPRETIVE_SYNTHESIS_ONLY — not scored, not evidence`
- **Future formal scored Layer 2** (this memo) would be:
  `FROZEN_SCORED_REPRESENTATION`
  — and even then, Layer 2 itself is not evidence; evidence exists only if A beats all control arms under blinded scoring.

## Architecture
- **Layer 1** remains the raw frozen varṇa/pole emission (per an arm's mapping). Opaque Sanskrit fragments — **never scored directly**.
- **Layer 2** is the deterministic, frozen, gloss-backed paraphrase of Layer 1 (fixed templates + frozen bridge table + "no unsupported term" validator, per `H2_LAYER2_SYNTHESIS_MODE.md`).
- **Scoring judges Layer 2 only.** The judge matches the anonymized paraphrase to a frozen target; Layer 1 is internal, never shown.

## All arms through one generator
Every arm's mapping is fed through the **same frozen Layer 2 generator** — identical templates, identical bridge table, identical output shape/length distribution. The **only** difference between arms is the mapping feeding Layer 1; the prose machinery is constant. **No arm receives handcrafted prose.**
- **A** real mapping · **R** random mapping · **S** scrambled mapping · **F** sign/role-flipped · **C** surface/cluster/coda-only (structure, no varṇa identity).
- **X** context-only and **D** dictionary/gloss-only have no varṇa poles, so they get **format-matched Layer-2-equivalent renderings** (a context paraphrase / a gloss paraphrase produced by an analogous fixed template) so the judge sees the *same shape* of item and cannot distinguish arms by format. Their role is the incremental-utility ceiling.

## Blinding
Scorer sees the **anonymized Layer 2 synthesis only** — no source word, no dictionary meaning, no target label, no answer key, no arm label. A leak scanner rejects any Layer 2 output that (a) names/reconstructs the source word, (b) contains a term not in the frozen bridge vocabulary, or (c) reveals the arm by format/length.

## Freeze + validator
- Bridge vocabulary and templates **frozen and committed before any scoring** (authored blind to targets). Post-hoc edits → `INVALID_POSTHOC`.
- The **"no unsupported term" validator** rejects any synthesis token not traceable to an emitted gloss of *that item* — this blocks target-fitted words ("trust/bonding/preference") and keeps all arms on equal prose footing. **No dictionary lookup; no target-fitting.**

## Evidence semantics
- **Layer 2 is not evidence.** It becomes evidence *only* through **A vs controls under blinded scoring**.
- **Success requires A to beat R, S, F, C, X, D.**
- If A only *sounds* meaningful but doesn't beat controls → **NO_SIGNAL**.
- If scrambled/random Layer 2 reads equally apt → **NO_SIGNAL** (the expected outcome).

## Recommended scoring target type
**Pseudoword forced-choice** as primary. Pseudowords carry no dictionary meaning, so the judge can't leak the answer from lexical knowledge — any A-vs-controls gap is attributable to the rule, not word recognition. Use **forced-choice** (match the Layer 2 synthesis to one of K frozen texture/transformation targets), **not** a soft rating (the committed `archetype_signal` found soft ratings let readers project, so they moved to forced-choice `archetype_recovery`, which returned NO). Real-word onset-matched synonym pairs may run as a secondary arm but inherit context/dictionary dominance (`like/love` is TOY_ONLY).

## Leakage risks (Layer-2-specific)
1. **Prose reverse-engineers the word** — anonymize; scan.
2. **Fluency tells the arms apart** — identical generator + validator so all arms use the same templates/bridge distribution; add a **surface-parity null judge** (must land at chance).
3. **Bridge table correlated with targets** — author blind, freeze first.
4. **X/D format mismatch** — context/dictionary items must match A's shape/length or the judge distinguishes by form.
5. **Target inventory mirrors the vṛtti axes** → circular; the target dimensions must come from an **independent, pre-registered inventory** (the `PREREG_VARNA_BOUNDARIES` caveat).

## Required controls
A / R / S / F / C / X / D **plus** a **random null judge** and a **surface-parity null judge** (both must land at chance), and a **relabeling-invariance** check (arm labels permuted → verdict unchanged), mirroring the committed `CRS_PSEUDOWORD_B` control ladder.

## Success criteria
- A beats **R, S, F, C, X, D**, each by predeclared **CI-lower-bound > 0** over N items.
- **Co-primary (predeclared): A_vs_R, A_vs_S, A_vs_X, A_vs_C.**
- Null judges at chance; relabeling-invariant.
- **Human-review subset required before any positive claim** (LLM-only stays exploratory).
- One-shot; no re-run-until-pass; malformed/leakage abort thresholds fixed in advance.

## Kill criteria
- A ≈ R or A ≈ S → **NO_SIGNAL**.
- X or D matches/beats A → **NO_INCREMENTAL_UTILITY**.
- A ≈ C → **structure confound** (identity added nothing).
- Synthesis needs handcrafted prose or unsupported terms to read → **void**.
- Result disappears across seeds/models → **artifact**.
- Null/parity judges show a systematic preference → **machinery leak; discard**.
- Any ontology / Sanskrit-privilege / semantic-truth / Track-B / Track-G-rescue claim → **stop**.

## Recommendation: docs-only first
**DOCS_ONLY.** This is a scoring-architecture spec and should be reviewed as a doc before any code, because scoring Layer 2 is precisely where a cleaner-looking harness can smuggle in a signal-hunt. Implement later **only** as a full pre-registration, with **explicit approval**, a **null prior**, framed as the *rigor-complete version of the already-negative archetype/synonym line* — **not** a rescue. When built, it should **reuse the existing `varna_lens` harness** (scramble/random machinery, control ladder) rather than start fresh. Honest expectation: it **confirms NO_SIGNAL** more cleanly. Running it stays gated on a separate explicit go.

---

Guardrails: no ontology, no Sanskrit privilege, no semantic-truth claim, no Track B unblock, no rescue of Track G; Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`).

Structure, not validated meaning.
