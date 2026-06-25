# Validity Assessment — Information-Theoretic Test for Independent Acoustic Information

> **Task:** decide, before implementing, whether `I(A ; Y | L, C) > 0` (does the varṇa acoustic latent A
> carry task-information beyond lexical L and CSR C?) is a valid, distinguishable experiment, with the
> decisive control S2 (real A) vs S3 (scrambled A). **Verdict: it COLLAPSES — and in the strongest form
> yet. Conditional mutual information is invariant under the relabeling bijection, so when A is encoded
> as gloss identity/structure, `I(A_real;Y|L,C) = I(A_scr;Y|L,C)` *exactly*, for every task Y and every
> estimator. S2 ≡ S3 by theorem. The only way to break the tie is to encode A by gloss *semantics*,
> which is the falsified sound→meaning channel (= the already-assessed fusion test). Proof + 8
> deliverables below; then stop.**

---

## 0. Headline

There are exactly two ways to encode A, and both are dead:

- **A = gloss identity / structure** (token IDs, polarity sequence, dissolution mask, whole-word-essence
  token). Scrambling is a fixed bijection π on the gloss alphabet, so `A_scr = Φ(A_real)` for a bijection
  Φ. **Mutual information is invariant under bijections** ⇒ `I(A_scr;Y|L,C) = I(A_real;Y|L,C)` for *all*
  Y, L, C. S2 ≡ S3 exactly — degenerate, for every estimator you listed (CMI, hierarchical regression,
  LRT, Bayesian comparison all target this one invariant quantity).
- **A = gloss semantics** (embeddings/meanings of "Patience", "Vitality"). Breaks the bijection (escapes
  invariance) — but then `I(A;Y|L,C)>0` asks "does sound-derived *meaning* add to L and C," i.e. the
  sound→meaning channel falsified in #1–3/#5 and analyzed in `ACOUSTIC_SEMANTIC_FUSION_VALIDITY.md`.

So: identity ⇒ degenerate (S2≡S3); semantics ⇒ falsified channel. No third encoding exists.

## 1. Distinguishable from prior experiments?

**Framing: yes (information-content, not meaning-recovery). Admissible outcome: no.** The decisive
S2-vs-S3 contrast is mathematically forced to zero (identity encoding) or is the fusion/sound→meaning
test (semantic encoding). It is a new *question* but resolves on the same wall. It is not a new testable
claim.

## 2. Can A's independent contribution be measured without reintroducing sound→meaning?

**No.** Measuring the contribution *of the mapping* requires real and scrambled to differ in the
information-relevant variable. Under identity encoding they are bijection-equivalent, so they carry
identical information — the mapping is *invisible* to any information measure. The only variable that
distinguishes them is the glosses' meaning, and conditioning that on L,C and asking for a positive
residual is exactly the sound→meaning hypothesis. Independence of A from L,C cannot be established
without the very channel the program rejected.

## 3. Best mathematical formulation (and why it is still degenerate)

Population target: conditional mutual information `I(A;Y | L,C) = H(Y|L,C) − H(Y|L,C,A)`. Practical
estimators: hierarchical/nested model ΔR² (S1=L,C vs S2=L,C,A), or a likelihood-ratio test of nested
models, or Bayesian model comparison (Bayes factor S2/S1). The **control** is to compute the *same*
ΔR²/LRT/BF with A_scrambled (S3). Decisive statistic: `Δ = score(S2) − score(S3)`.

> **MI relabeling-invariance theorem.** Let Φ be a bijection on the support of A (measurable, invertible).
> Then `I(Φ(A) ; Y | Z) = I(A ; Y | Z)`. *Proof.* A bijection induces a one-to-one correspondence of
> events with equal probabilities; entropies `H(·)` are functionals of the probability mass/density only
> and are unchanged by relabeling outcomes, so `H(Y|Z) − H(Y|Z,Φ(A)) = H(Y|Z) − H(Y|Z,A)`. ∎
>
> **Application.** A lexicon scramble replaces the sound→gloss map g by g∘π, π a bijection on the gloss
> alphabet (worldly/counter pairs permuted among consonants; essences among vowels). For each word,
> `A_scr(w)` = tokenwise-π applied to `A_real(w)`; thus `A_scr = Φ(A_real)` for the single bijection Φ
> that relabels the token alphabet. Therefore, **for every task Y and every conditioning (L,C):**
> `I(A_scr ; Y | L,C) = I(A_real ; Y | L,C).`
> Hence the population value of ΔR²/LRT/Bayes-factor is **identical** for S2 and S3:
> `E[Δ] = 0`, with no dependence on task, model class, or sample. ∎

This is *stronger* than the earlier topology collapse: that was about one distance matrix; this is about
the information functional itself, so it kills **all** the proposed estimators simultaneously — none can
recover a contribution from the mapping, because there is none to recover (the mapping is a relabeling,
and information cannot see relabelings).

*(The lexicon-independent structural features — polarity sequence, dissolution mask, length, C/V pattern,
whole-word-essence sign — are not merely bijection-equivalent across S2/S3; they are byte-identical, since
they come from the position rules, not the lexicon. They may carry some `I(·;Y|L,C)` (phonotactics), but
contribute it identically to S2 and S3, so again `Δ=0`. And that information is phonetic, not "varṇa-
dictionary," information.)*

## 4. Leakage risks

1. **Pretrained gloss embeddings.** If A is vectorized with a pretrained embedder of the gloss *strings*,
   that injects semantics ⇒ the semantic horn (escapes invariance but is the falsified channel). A
   from-scratch / one-hot categorical encoding keeps A identity-based ⇒ invariance holds ⇒ Δ=0.
2. **Estimator non-equivariance / finite-sample noise.** A neural estimator with random init may show
   tiny S2≠S3 from optimization variance or label-collision quirks; this is artifact, averages to 0 over
   seeds, and must not be read as signal.
3. **Word recoverable from A.** A is a near-invertible function of the word's sounds, so it can lift S2
   and S3 *equally* over S1 — never S2 over S3 (protected by the S2-vs-S3 contrast).
4. **Multiplicity.** 9th probe; without Holm + preregistration a spurious cell is likely.

## 5. Appropriate datasets

Word/utterance sets with task labels (naming preference, counseling phrasing, reflective fit). Adequate
to build — but moot: the decisive contrast is degenerate regardless of dataset.

## 6. Tasks that genuinely need residual information beyond semantics

The honest ones are **aesthetic/expressive** (naming, poetry, stylistic consistency) — there, residual-
beyond-meaning information truly exists. But that residual is **phonetic** (euphony, rhythm), which is
(a) gloss-invariant, so S2≡S3, and (b) a property of phonemes, not of the varṇa gloss dictionary. So even
the tasks with real residual information cannot route that information through A's *mapping*. The
dictionary remains invisible to the measure.

## 7. Does this design avoid relabeling-invariance?

**No — it is maximally exposed to it.** Mutual information is the quantity *most* perfectly invariant under
relabeling (exactly, not approximately). Framing the test information-theoretically does not escape the
theorem; it states it in its purest form: `I` cannot distinguish a code from a relabeling of that code.

## 8. Probability of detecting a genuine independent acoustic contribution

P(legitimate, identity-encoded S2>S3, post-control): **≈ 0** — structurally impossible (`E[Δ]=0` by
theorem; any nonzero is estimator noise/leakage). P(via the semantic horn): nonzero only by re-running the
falsified sound→meaning channel, which is inadmissible. **P(defensible independent acoustic information) ≈
0.**

---

## Conclusion — collapses; proof complete; stop

The experiment is **not** scientifically distinguishable in outcome from the closed set. By the MI
relabeling-invariance theorem, the decisive S2-vs-S3 comparison has population value exactly zero for any
identity/structure encoding of A and any task or estimator; the only encoding that breaks the tie (gloss
semantics) reinstates the falsified sound→meaning hypothesis. Therefore `I(A ; Y | L,C)` cannot be shown
> 0 for the *varṇa mapping* without the forbidden channel. **Per the task instruction: it collapses —
proven above — stop.**

> One-line intuition: information cannot tell a cipher from its key-swap. Scrambling the lexicon is a
> key-swap; `I(A;Y|L,C)` is blind to it. The thing that would make real ≠ scrambled is the glosses'
> meanings — which is the one channel six tests have closed.
