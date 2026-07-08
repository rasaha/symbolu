# B1.3 v3-Authoritative × L2 Validation Rulebook — Compatibility Memo

**Status:** Governing memo (docs-only). Reconciles the frozen-ready B1.3 v3-authoritative study with the
newly documented `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**It does not alter B1.3 v3 in place, declares no evidence freeze, and validates no meaning.**
**Track B remains blocked. Structure, not validated meaning.**

Related documents:
- `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` (the governing framework)
- `b1_3_revised_layer3/B1_3_CONCRETE_OBJECT_LLM_FREEZE_REVIEW_V3_AUTHORITATIVE.md`
- `b1_3_revised_layer3/B1_3_V3_AUTHORITATIVE_REBUILD.md`
- `b1_3_revised_layer3/B1_3_V3_RUNPOD_OPERATOR_SEQUENCE.md`

---

## 1. Decision

**`B1_3_V3_REQUIRES_NEW_VERSION_IF_RULEBOOK_APPLIED`**

B1.3 v3-authoritative was designed and frozen-ready **before** the L2 validation rulebook existed. It does
**not** satisfy the rulebook as-is (see §4). Therefore:

- The L2 rulebook **does not retroactively bind** B1.3 v3, and B1.3 v3 is **not** silently converted into an
  L2-rulebook study.
- If rulebook-grade semantic evidence is wanted, that requires a **new versioned study** (B1.4 / Milestone A),
  not an in-place edit of B1.3 v3.
- B1.3 v3 may still stand — and, at operator discretion, be run — as a **pre-rulebook exploratory** line,
  provided its outputs are labeled as such and are never presented as rulebook-validated.

This decision is a governance statement, not an instruction to run, freeze, or score anything.

---

## 2. What B1.3 v3 tests

**Design.** B1.3 v3-authoritative is a **concrete-object LLM judged-modulation** study. For each of a screened
set of concrete-object target words, short passages are generated across arms — `A_real` (authoritative varṇa
mapping), `R_deranged_near/mid/far` (stratified derangements), `R_scrambled`, `R_random`, `X_neutral`, and a
`semantic_only_baseline`. A blinded LLM judge panel makes forced binary A/B choices between passages; the
primary endpoint is `A_real`'s win-rate against `R_deranged_mid` (Wilson lower CI > 0.50), with near/mid/far
gradient and Holm-corrected secondary comparisons.

**Authoritative-source rebuild.** v3 was rebuilt from the **authoritative** varṇa lexicon
(`varna_lens/lexicon_authoritative_varna.json` → `b1_3_authoritative_varna_bridge_pool.json`), after the
lexicon-source audit found earlier B1.3 material had been built on a fallback pool. Pole direction is
preserved by construction; Sanskrit parentheticals are stripped from judge-facing text.

**v3 audit status.** 371 frozen stimuli
(`b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl`); style/register audit **passed**
(`GLOBAL_REGISTER_POLISH_PASS`); source audit **passed** (`V3_AUTHORITATIVE_SOURCE_AUDIT_PASS`); 16 artifacts
hash-bound in the v3 freeze manifest (self-hash `1bfeee51…faf9`).

**Runner readiness.** The judge runner (`run_b1_3_v3_with_b1_1_judges.py`) reuses the B1.1 open-weight judge
execution layer (Llama-3.1-8B, Llama-3-8B, Gemma-2-9b) with B1.3's own blinded packets, forced-A/B parser,
and the frozen B1.3 scorer. Mock tests green; freeze-check reports ready. **No EVIDENCE_FREEZE declared,
nothing run, nothing scored.**

---

## 3. What the L2 rulebook requires

The L2 rulebook (`SYMBOL_U_L2_VALIDATION_RULEBOOK.md`) sets these requirements for a validated semantic claim:

- **Gloss-independent essence table `E`.** Each varṇa's essence must be defined **independently of dictionary
  meaning**. `E` is a required foundation; a circular `E` triggers the terminal rule.
- **Codomain / semantic space `Y` (via L2 latent `z ∈ S`).** L2 forms `z = F(operators, s_0)`, where `F` must
  be gloss-independent, non-additive, operator-derived, and baseline-testable; L3 decodes `y = D(z)` into the
  human-facing codomain.
- **Probe `P`.** A probe *tests* a decoder's output against baselines. A probe is not a decoder; producing a
  plausible semantic output is not evidence.
- **Baseline suite `B` — must beat all.** Random/relabel; bag/sequence ablation; **phonological similarity**;
  length/frequency; sentiment/lexicon; **dictionary/gloss leakage**; chance/null.
- **Failure state `⊥`.** When baselines are not beaten, `⊥` ("no validated signal") is the correct output —
  not a bug, not an invitation to re-tune.
- **Terminal rule.** If `E` cannot be defined independently of dictionary meaning, the semantic-validation
  program **must stop or return `⊥`**.

---

## 4. Compatibility assessment

**Does B1.3 v3 satisfy the L2 rulebook as-is? No.** B1.3 v3 is a well-controlled *exploratory judged-modulation*
study, but it is not an L2-rulebook validation. Explicit mismatches:

- **Dictionary / gloss dependence.** B1.3 v3 stimuli and its `semantic_only_baseline` are constructed from,
  and evaluated against, word **glosses / meanings**. The rulebook requires a **gloss-independent `E`** and a
  gloss-independent formation `F`. B1.3 v3 does not define or test a gloss-independent `E`; its essence source
  is the authoritative lexicon, whose entries are meaning-bearing glosses. → **Mismatch (fails admissibility
  condition 1).**
- **Decoder / probe confusion.** B1.3 v3's judged A/B win-rate is effectively a **decoder read-out scored for
  preference**, not a **probe `P`** run against the full baseline suite. Under the rulebook, a decoder
  producing a preferred passage is *not proof*. → **Mismatch (probe ≠ decoder not separated).**
- **Baseline sufficiency.** B1.3 v3 carries strong controls (deranged near/mid/far, scrambled, random,
  neutral, semantic-only), but **not** the rulebook's full suite. Missing/underspecified relative to `B`:
  length/frequency-matched controls and an explicit dictionary/gloss-leakage control as a *first-class
  baseline the claim must beat*. → **Mismatch (partial baseline coverage).**
- **Phonological-similarity baseline.** The rulebook requires a **phonological-neighbor** baseline
  (sound-similar, meaning-unrelated) to catch sound-driven artifacts. B1.3 v3 has scrambled/random arms but
  **no phonological-similarity baseline**. Given the standing prior that sensitivity tracks **sound over
  meaning**, this omission is material. → **Mismatch (required baseline absent).**
- **Semantic baseline.** B1.3 v3 *does* include a `semantic_only_baseline` — good — but under the rulebook
  this is precisely a **gloss-leakage control the claim must beat**, not a supporting arm. Its presence is
  necessary but the framing differs: the rulebook treats it as a bar, not a companion. → **Partial (present,
  but reframed as a hurdle, not satisfied).**
- **Object-function confound.** B1.3 v3's `NULL` / `SEMANTIC_BASELINE_EXPLAINS` labels already anticipate that
  a judge can prefer `A_real` because the passage names the object's **function** (a knife cuts), independent
  of varṇa structure. The rulebook makes this dispositive: if gloss/function explains the preference, the
  result is `⊥`, not signal. → **Consistent in spirit; B1.3 v3 correctly cannot claim signal when this fires.**
- **Judge instrumentation.** B1.3 v3 depends on an open-weight judge panel callable only on a model-access
  host; in this runtime **no stable cross-vendor judge is callable**, so B1.3 v3 is instrument-blocked. The
  rulebook is instrument-agnostic but requires that a **probe** (not a preference judge) score against `B`;
  B1.3 v3's judge is a preference decoder, not a rulebook probe. → **Mismatch (instrument is a decoder, not a
  probe) + practical block.**

**Net:** B1.3 v3 is **not** L2-rulebook-compliant. The gaps are structural (gloss dependence, no
gloss-independent `E`, decoder-not-probe, missing phonological baseline), not cosmetic, and cannot be closed by
editing thresholds or re-labeling.

---

## 5. Do-not-contaminate rule

B1.3 v3-authoritative **must not be silently modified in place** to appear rulebook-compliant. Its stimuli,
scorer, thresholds, prompts, judge IDs, freeze manifest, and hashes are fixed; any post-freeze edit spawns a
new versioned study by construction.

If the L2 rulebook is to be applied, it creates a **new versioned study** — e.g. **B1.4** (gloss-independent
validation) or **Milestone A/B validation** — with its own gloss-independent `E`, formation `F`, probe `P`,
full baseline suite `B`, and freeze lineage. The rulebook governs that new line; it does not reach back into
B1.3 v3. Mixing the two (running B1.3 v3 artifacts and reporting them under rulebook terms) is prohibited.

---

## 6. Evidence-freeze implication

B1.3 v3 remains **eligible for freeze only as a clearly-labeled pre-rulebook exploratory evidence line** — and
only by explicit operator declaration, exactly as its existing operator sequence specifies. This memo does
**not** declare or authorize a freeze.

Concretely:

- If the operator chooses to run B1.3 v3, it must be frozen and reported as **pre-rulebook exploratory**: its
  terminal label (STRONG / CATEGORY_LIMITED / NULL / STYLE_CONFOUNDED / SEMANTIC_BASELINE_EXPLAINS /
  INVALID_RUN) stands on B1.3's own terms and is **not** an L2-rulebook validation regardless of outcome.
- A `NULL` or `SEMANTIC_BASELINE_EXPLAINS` result would be the **expected** outcome given the low prior and
  would remain a negative; it may **not** be upgraded by appeal to the rulebook.
- Alternatively, the operator may **park** B1.3 v3 unfrozen and route effort to the rulebook line. Both are
  legitimate; the choice is the operator's. No freeze is declared here.

---

## 7. Recommended path

**Keep both — B1.3 v3 parked (optionally runnable as pre-rulebook exploratory), L2 rulebook starts fresh.**

Rationale: B1.3 v3 is artifact-ready, source-clean, and audit-passed, so it retains value as a bounded
*exploratory* probe of judged modulation — worth running *iff* a stable judge host is available and its result
is labeled pre-rulebook. But it cannot answer the rulebook's question (gloss-independent, probe-validated
signal), so the substantive next step is a **fresh L2 line**:

1. **Park B1.3 v3** in its current frozen-ready, unfrozen state (default). Run it only as an explicitly
   labeled pre-rulebook exploratory study if/when a stable judge is available — never as rulebook evidence.
2. **Start Milestone A foundations** under the rulebook: attempt to define a **gloss-independent `E`**. If `E`
   cannot be defined independently of dictionary meaning, invoke the **terminal rule** and return `⊥`.
3. **Design B1.4** as the gloss-independent validation study (formation `F`, probe `P`, full baseline suite
   `B` including the phonological-similarity and gloss-leakage baselines B1.3 v3 lacks).

The single recommended primary action is **park B1.3 v3 and start Milestone A foundations (define/attempt
`E`)**; B1.4 follows only if a non-circular `E` survives.

---

## 8. No-rescue rule

The L2 rulebook **cannot be used to reinterpret B1.3 v3, or any prior null/negative result, as positive**. It
introduces no framing, layer, or re-scoring by which an existing negative becomes a signal. Specifically
preserved and **not** reset or upgraded:

- B1.3 v3's own future label, whatever it turns out to be (a `NULL` / `SEMANTIC_BASELINE_EXPLAINS` stays
  negative);
- B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real at 0.967;
- register-field CLOSED; vṛtti CLOSED;
- Track G `RANDOM_POLARITY_EXPLAINS`; Track F `CORRECTNESS_DEGRADED`;
- O1.5 construct-gate failure; corpus norms near-null; synonym varṇa-overlap near random; sound-over-meaning
  sensitivity; upstream grapheme→varṇa loss.

Any use of this memo or the rulebook that would have the effect of relabeling a past negative as positive is
out of scope and prohibited. **No ONTOLOGICAL_SIGNAL. No Sanskrit privilege.**

---

## 9. Boundary statement

> The L2 validation rulebook is a fresh governing framework. It does not alter B1.3 v3 in place. No evidence
> freeze declared. Nothing run or scored. Track B remains blocked. Structure, not validated meaning.
