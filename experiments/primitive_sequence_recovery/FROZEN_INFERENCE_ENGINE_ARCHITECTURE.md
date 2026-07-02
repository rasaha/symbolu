# Frozen-Inference-Engine Architecture — Evaluation (docs only)

**Architectural evaluation only. Nothing implemented, downloaded, or changed.** No code, no
assets, no schema change, no `manifest_v2`, no manifest edit, no READY, no run, no scores.
`manifest.json` stays **NOT_READY**; runner stays **NOT_RUN**; Stage A untouched.

**Framing.** This challenges the prior "confirmatory is blocked" conclusion by evaluating a
*different* architecture — **B: realize the primitive sequence to text, then score it with a
frozen, offline, hash-pinned, deterministic inference engine that is not trained on Symbol-U** —
against **A: the (blocked) opaque-concept resolver**. It does **not** try to rescue A, and it
does **not** pre-commit to preferring B.

---

## What Architecture B actually is (state it precisely first)

- **Ontology (unchanged):** word → ordered **opaque** atoms.
- **Realization (unchanged):** atoms → English gloss text, Sanskrit term text (frozen).
- **Inference (new):** the realized **text** is fed to a frozen semantic engine (static
  embedder, or an LLM) that embeds/judges it; rank the true meaning among K candidates; contrast
  **real vs scrambled assignment**.

The decisive structural fact: **the engine never sees the opaque atoms.** By the time it acts,
the atoms have been realized into text. So B is **not** a concept resolver over opaque ids — it
is a *scorer for the text realizations*. In our own taxonomy, **B is the `en_gloss` / `sa_term`
text channel with a semantic (rather than lexical) scoring function** — i.e. Track B's
text-realization experiment, whose blocker was *asset availability*, not concept-resolver
circularity.

---

## 1. Different experiment, or disguised concept-resolver?

**Genuinely different from A, but not a substitute for what A was for.** A tried to build an
*independent, non-textual* channel from opaque ids; B abandons that and tests the *text*
realizations through a general semantic engine. So B is not "the concept resolver in disguise."
But B does **not** unblock what blocked A — it addresses a *different* channel (text) that had a
*different* blocker (no offline semantic asset here). Calling B a rescue of the confirmatory
design would be false.

## 2. Remove or relocate the circularity?

**Relocated and transformed, not removed.**
- **Removed:** A's specific fatal circularity — the opaque→concept **mapping derived from
  glosses** (F1/F2) — is gone, because B has no such mapping.
- **Relocated/new:** (i) the **single frozen engine becomes the shared component** that can
  manufacture cross-realization agreement (§6); (ii) **F4 shared-source persists** — the glosses
  still come from the one vṛtti table; (iii) if the engine is an **LLM, its pretrained
  knowledge** (of Sanskrit, of word meanings, possibly of Symbol-U/Sarkar itself) is a new,
  opaque leakage path. Net: the dependence moves from "resolver built on glosses" to "engine
  interprets everything," which is arguably **harder to detect**.

## 3. What hypothesis is actually tested?

> *When each varṇa is replaced by its frozen, pre-registered vṛtti gloss and those glosses are
> composed in the word's varṇa order, a neutral frozen semantic engine recovers the word's
> independently-attested meaning better under the **real** varṇa→gloss assignment than under
> **scrambled** assignments.*

This tests the **claimed-meaning (gloss) table's compositional predictiveness of word meanings**,
mediated by the engine's semantics. It does **not** test the opaque primitives directly — they
are realized away. It is a legitimate operationalization of Symbol-U *only if* the gloss table
was frozen from an external source authored **before/independently of** this word list (else the
glosser could have retrofitted glosses — F4).

## 4. Still falsifiable?

**Yes.** real ≈ scramble → `NO_SIGNAL` (falsified); real ≫ scramble with controls → candidate
positive. The real-vs-scramble contrast under a *fixed* engine is a clean falsifiable design.
The threat to B is **validity (confounds)**, not falsifiability.

## 5. Does the relabeling-invariance theorem still apply?

**Yes, and B respects it.** The theorem forbids scoring *opaque* atoms (any permutation-invariant
function is identical for real and scrambled). B never scores opaque atoms — it scores the
**realized text**, which differs between real and scrambled. So B makes the assignment visible
*by realizing*, exactly as the theorem requires. The theorem is not an obstacle to B; it is the
reason B must realize before scoring.

## 6. Is cross-realization invariance still meaningful under one shared engine?

**Largely NO.** If a single engine interprets both the English and Sanskrit realizations —
especially a **multilingual** one that maps "hope" and "āśā" to nearby points because it knows
they are translations — then the two realizations are **not independent encoders**; they are the
same concept fed twice to one unifying model. Invariance across them then tests the *same thing
twice* and cannot separate ontological signal from engine/source artifact. **To recover meaning,
B needs multiple, genuinely independent frozen engines** (disjoint training corpora/architectures)
so that **cross-engine invariance** becomes the real independence check. With one engine,
cross-realization invariance is not a meaningful independence guarantee.

## 7. Would B justify withdrawing `concept_id` entirely?

**Consistent with withdrawing it — but B is not the reason.** `concept_id` (opaque svc/wmc +
resolver) was already withdrawn as a confirmatory channel (blocked, circular). B does not use it
and does not resurrect it. B replaces "concept-via-resolver" with "text-via-engine." So: keep
`concept_id` withdrawn as confirmatory; B changes nothing about that verdict.

## 8. New risks introduced by B

- **English leakage** — most engines are English-centric; the English channel can align via
  English distributional structure. (Mitigated *partly* by real-vs-scramble, which holds the
  engine fixed.)
- **Pretrained knowledge (severe, LLM)** — an LLM plausibly **already knows** that krodha means
  anger, knows the vṛtti glosses' meanings, and may know Sarkar's varṇa doctrine. It can then
  recover meaning from **priors**, not from the compositional signal; scrambling changes the
  presented glosses but recognition/priors still leak. "Not trained on Symbol-U" is **hard to
  guarantee** for a large pretrained model.
- **Prompt dependence (LLM)** — outputs depend on prompt wording; a large researcher degree of
  freedom that can encode the expected answer.
- **Decoding randomness (LLM)** — sampling nondeterminism; even greedy has float/hardware
  nondeterminism.
- **Model-version dependence** — results shift across versions → reproducibility risk.
- **Others** — tokenization effects; **training-data contamination** (the frozen glosses/word
  list may appear in the engine's corpus); the engine "filling in" meaning by reasoning;
  multilingual unification collapsing cross-realization independence (§6).

## 9. Mandatory controls

- **Hash-pinned weights**; **fully deterministic** execution (temperature 0 + fixed seed + pinned
  framework/hardware, or — better — a **deterministic non-LLM** engine).
- **Frozen, pre-registered prompts** (if an LLM is used at all); **prompt-permutation robustness**.
- **Real-vs-scramble assignment null** and **order-scramble null** (already pre-registered).
- **≥2 genuinely independent frozen engines** (disjoint training) → cross-engine invariance as
  the real independence axis (§6).
- **Contamination / prior-knowledge probe** — test whether the engine recovers the meaning from
  the **bare word** or from **priors** without the composed glosses; if it can, the channel is
  contaminated.
- **Random-gloss-table control** calibrated to chance; report the **chance baseline**.
- **External-provenance check** — verify the gloss table was frozen from a source authored
  independently of this word list (F4).

## 10. A vs B — honest comparison

| axis | A. opaque → concept resolver → compare | B. text realization → frozen engine → compare |
|---|---|---|
| **Scientific validity** | Would give a *non-text independent* channel **if** non-circular — but that is unachievable (F1/F2) → **blocked/moot** | Tests a real, pre-registerable hypothesis and is **runnable in principle**; validity threatened by shared-engine + pretrained-knowledge confounds |
| **Reproducibility** | High if the ontology asset were obtained (static graph) | High **only** with a deterministic non-LLM engine + pinned weights; **LLM version drift/nondeterminism is worse** |
| **Engineering simplicity** | Lower (build + audit a concept mapping) | **Higher** (embed text, compare) — but simplicity hides the engine confound |
| **Circularity** | Fatal in the gloss-derived mapping (F1/F2) | No mapping circularity, but **shared-engine + pretrained-knowledge + F4** — subtler, harder to detect |
| **Falsifiability** | Falsifiable in design | Falsifiable in design — **equal** |
| **Evidential strength** | Higher *ceiling* (non-text channel) **if it worked**; it can't | Single engine → capped at `ENGINE/REALIZATION_ARTIFACT`; **multi-independent-engine invariance could exceed A here** (A is blocked) — but needs ≥2 clean engines |

**Where B is genuinely stronger than A:** it sidesteps A's specific fatal circularity (no
opaque→concept mapping), and — uniquely — it opens a **cross-engine** independence axis (does the
signal survive two models trained on disjoint corpora?) that A never had.

**Where B is weaker / not a fix:** with a **single** engine it merely relocates the dependence
(the engine unifies realizations → cross-realization invariance dies, §6). In its **LLM** form it
is **weaker than A on reproducibility and validity** (nondeterminism, prompt dependence, version
drift, and — decisively — **pretrained-knowledge contamination**: an LLM can recover the meaning
without any compositional signal, so a positive is uninterpretable). And B never escapes **F4**:
the glosses are still one source, so even a clean multi-engine positive is *necessary, not
sufficient* for an intrinsic-varṇa claim.

---

## Recommendation

**Neither architecture yields a clean confirmatory test in the current environment; the prior
"blocked" conclusion stands, but is refined.** The true blocker is not "concept-resolver
circularity" specifically — it is the **absence of any independent, non-circular, offline
semantic channel**. B demonstrates this by *relocating* rather than *removing* the dependence.

Concretely:
- **Reject the LLM form of B for confirmatory use.** Nondeterminism, prompt dependence, version
  drift, and pretrained-knowledge/contamination make a positive uninterpretable and
  irreproducible. It is scientifically **weaker** than A on validity and reproducibility.
- **The only defensible form of B** is a **deterministic, offline, hash-pinned, non-LLM engine
  (static embeddings), with ≥2 genuinely independent such engines**, real/order/scramble nulls,
  and the §9 contamination controls. In that form B **collapses into the already-identified
  exploratory text-realization track** — runnable only with approved offline assets (Option 2),
  and **still capped below a confirmatory ontological claim** by the shared-source ceiling (F4)
  and English/Sanskrit lexical confounds.
- **B's one real contribution** over A is the **cross-engine** independence axis. If (and only
  if) ≥2 independent, deterministic, offline, verified-non-contaminated engines can be obtained
  and pass the controls, B could support a *stronger-than-single-realization* exploratory claim —
  but never a clean intrinsic-varṇa claim while F4 stands.

**Net:** B is a *different, in-principle-runnable* experiment that is **not a rescue** of the
confirmatory design. Its honest status is **exploratory**, gated on offline non-LLM assets, with
an `ENGINE/REALIZATION_ARTIFACT` ceiling. It does **not** overturn the Version-1 stopping point:
freeze the framework, publish Track A, keep Track B (now including "frozen-engine text scoring")
as **blocked/exploratory**, and pursue B — if at all — only in its deterministic multi-engine
form under explicit approval, reported without confirmatory framing.

> structure, not validated meaning.
