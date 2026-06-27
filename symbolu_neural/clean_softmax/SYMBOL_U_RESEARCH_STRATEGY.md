# Symbol-U Research Strategy — Committee Decision Memo

**Audience:** senior ML researchers / funding committee deciding whether the Symbol-U
direction warrants a multi-year program.
**Status:** strategy only — no implementation, no code. A decision framework.
**Bottom line up front:** Do **not** authorize a multi-year build. Authorize a
**4–6 week, pre-registered measurement pilot**. The decisive question is a measurement,
not an architecture, and its most probable outcome is a clean, cheap, publishable
negative (or a deflationary phonological positive). Build only if the pilot surprises.

---

## 0. Context (what is already established)

Across many experiments, Symbol-U variables (Vritti, Aspect, Guna, Kosha, Resonance,
…) were injected into an autoregressive Transformer as heads / gates / control modules
/ supervised targets. The results were consistent: the mechanisms trained, stayed
stable, became active, and influenced generation — **but at equal compute they behaved
like additional Transformer capacity.** Capacity-/FLOP-matched controls confirmed this
across seeds. Character-level grounding failed to generalize semantically (unseen-word
accuracy collapsed). Deferred memory only helped when attention was absent.

The recurring error was **architectural and methodological, not algorithmic**: we
repeatedly built machines to *use* Symbol-U before establishing there was anything to
use, and we judged it by the wrong objective (next-token prediction).

---

## 1. The Transformer and Symbol-U are not competitors

| System | Responsibility | Status in this program |
|---|---|---|
| **BPE Transformer** | token-level language modeling: contextual representations, next-token distribution | frozen, off-the-shelf, never modified |
| **Symbol-U engine** | word/sentence-level symbolic semantic computation (deterministic descriptors from phoneme/resonance rules) | fixed, deterministic, not learned |

They operate at **different granularities** and should not be forced to compete on the
same objective. Forcing Symbol-U to improve next-token CE — a token-level objective —
was a category error: Symbol-U's claimed variables are properties of words, sentences,
and completed thoughts, not of individual token transitions.

## 2. Symbol-U must NOT be judged first by next-token prediction

"Does it lower LM loss?" confounds four independent things — is the variable real, is
the module expressive, is the objective aligned, is the backbone capable — so every
result is uninterpretable. A *perfectly real* semantic variable need not lower
next-token CE (the LLM may already encode it, or it may be orthogonal to token
prediction). **Generation utility is the LAST question, not the first.**

## 3. The first scientific question

> **Does Symbol-U compute semantic information that is *complementary* to — i.e., not
> already contained in — modern Transformer sentence representations?**

This is falsifiable with standard tools (probing, mutual information, RSA/CCA) on a
**frozen** model, in days, with no training. It tests the actual claim (Symbol-U
captures real structure), not a downstream side-effect.

**The hard constraint that frames everything (data-processing inequality).** Symbol-U
is an **endogenous, deterministic function of the same sentence** the Transformer has
already encoded. Unlike retrieval/tools/knowledge-graphs (which add **exogenous**
information the model lacks), Symbol-U cannot, in principle, contain information that is
not a function of the input the Transformer already processed. Complementarity is
therefore possible *only* if Symbol-U computes something the LLM **systematically
discards** — and the main thing BPE LLMs discard is **sub-lexical phonology**, which is
not semantics. No architecture (parallel, fused, or otherwise) can manufacture
information the input doesn't carry; architecture can only surface signal that exists.

## 4. Discovery vs Deployment (do not conflate them)

| | **Discovery experiment** | **Deployment architecture** |
|---|---|---|
| Question | *Does the Symbol-U signal exist?* | *How do we exploit a confirmed signal?* |
| Method | controlled measurement: conditional information `I(U;T\|E)`, invariance tests, RSA/probing with nulls | fusion adapter / retrieval bias / planning / memory / DHA conditioning |
| Needs training? | mostly no (frozen LLM, fixed `U`, linear probes) | yes (small adapter), but only after discovery passes |
| Sensitivity to a weak signal | **highest** (probes for `U` directly) | **lower** (a downstream loss can gate a faint feature off) |
| When to do it | **first** | **only after discovery succeeds** |

**Key correction of the recent direction:** a gated fusion adapter is a good way to
*deploy* a confirmed signal and a *suboptimal, premature* way to *discover* one. The
most sensitive detector is a direct incremental-information probe, which needs no
adapter at all. Build the fusion/retrieval/planning/DHA machinery **only after** the
discovery pilot validates the signal.

## 5. The research hierarchy (each gate must pass before the next)

```
1. EXISTENCE        Is U decodable from / aligned with frozen LLM representations
                    at all (above selectivity controls)?
        ↓ pass
2. COMPLEMENTARITY  Does U add information BEYOND E (I(U;T|E) > 0) and beyond matched
                    generic/surface/taxonomy controls?
        ↓ pass
3. SEMANTIC VALIDITY Is the added signal SEMANTIC (synonym/paraphrase-invariant,
                    survives surface partialling, not explained by phonology)?
        ↓ pass
4. CAUSALITY        Does the model USE the U-aligned direction (intervention / erasure
                    above a random-subspace control)? Decodable ≠ used.
        ↓ pass
5. UTILITY          Does conditioning on validated U improve a downstream task
                    (planning / retrieval / memory / DHA) above a capacity-matched
                    control, across seeds?
```

Most prior work jumped straight to (5). The program must run (1)→(5) in order and stop
at the first gate that fails.

## 6. Strongest adversarial risks

1. **Redundancy with the Transformer embedding** (most likely): `U` is a function of the
   input; `E` is a richer function of the same input; `I(U;T|E) ≈ 0`. Fusion gates it off.
2. **Surface/phonological, not semantic** (the trap): Symbol-U's one real niche is
   sub-lexical sound structure BPE discards. Any gain most plausibly comes from there —
   a positive result that **refutes** the semantic ontology while appearing to support
   it.
3. **Generic feature capacity:** a random/surface/second-embedding stream of equal size
   helps equally → the *fusion capacity* helped, not Symbol-U.
4. **The adapter ignores Symbol-U** (gate→0): the honest negative; likely.
5. **Fails synonym/paraphrase invariance:** if synonyms get different Vritti, `U` tracks
   sound, not meaning — colliding with the arbitrariness of the linguistic sign.
6. **Explained by known taxonomies:** `U` aligns only insofar as it correlates with
   sentiment / POS / topic / valence → real but **redundant** re-encoding of known
   semantics, not a novel primitive.
7. **Hand-crafted-feature subsumption prior:** a decade of NLP shows strong contextual
   encoders absorb hand-crafted linguistic features; Symbol-U would have to be the
   exception.
8. **Researcher degrees of freedom:** many variables × layers × models × metrics ⇒ some
   "win" by chance without pre-registered nulls.

The honest null is **not zero** — it is "weak known sound symbolism" plus "known
semantic taxonomies." Symbol-U must beat *those*, not chance.

## 7. Null models (every claim must be tested against all of these)

| Null | Controls for |
|---|---|
| **Transformer embedding alone (`E`)** | does `U` add anything at all? |
| **Shuffled Symbol-U** | is the gate/probe using content or just capacity/correlates? |
| **Random feature vector (matched dim)** | generic fusion capacity |
| **Surface features** (vowel count, length, char n-grams, orthography) | the phonology/spelling confound |
| **Known-taxonomy features** (sentiment, POS, topic, valence/arousal/concreteness) | redundancy with established semantics |
| **Phonological-only features** (sound structure without the symbolic ontology) | is the value the *ontology* or just *phonology*? |

A positive Symbol-U result must beat **every** relevant null, pre-registered.

## 8. The first pilot (4–6 weeks, mostly CPU / one small GPU)

Pre-register thresholds and nulls before running. Experiments 1–2 need **no adapter**.

1. **Synonym / paraphrase invariance of Symbol-U itself (no LLM).** Compute `U` over
   synonym sets / paraphrase pairs. Semantic ⇒ invariant; phonological ⇒ scatters.
   *The cheapest kill switch; tests the patent's premise directly.*
2. **Incremental information: `E` vs `E+U`.** Probe standard semantic tasks (STS, NLI,
   paraphrase, retrieval relevance) with `E` alone vs `E+U`. Earns nothing unless
   `E+U > E`.
3. **Surface-controlled test.** Repeat (2) with `E+`(surface) and `E+`(known taxonomy)
   and `E+`(shuffled `U`). `U` must beat all of them.
4. **Phonological-vs-semantic dissociation.** Evaluate on phonological tasks (rhyme,
   syllable count, pun/meter) *and* semantic tasks. If `U` helps phonological but not
   semantic → it supplies sound, not meaning.
5. **Cross-model check (if cheap).** Replicate the incremental-information result across
   ≥2 LLM families/scales — property of language vs one model's quirk.

## 9. Go / No-Go criteria

- **STOP (falsified):** `U` adds no information beyond `E` (gate→0; `I(U;T|E)≈0`;
  `E+U ≈ E`), or `U` fails synonym/paraphrase invariance. → Clean negative; publish; end.
- **PIVOT (deflationary positive):** `U` helps only **phonological** tasks, or is fully
  explained by surface / known taxonomies. → Real but refutes the *semantic* thesis;
  pivot to phonology / drop the ontology claim.
- **CONTINUE (earned):** `U` adds **surface-controlled, synonym-invariant semantic**
  information **beyond known taxonomies**, replicated **across models**. → A genuinely
  novel finding about sound–meaning structure (independent of the patent). *Only now*
  proceed up the hierarchy (causality → utility) and *only then* build the deployment
  architecture (fusion / retrieval / planning / memory / DHA, conditioning never
  per-token logits).

Expected-value note for the committee: the program's value is dominated by the **option
to stop cheaply at gate 1–3.** The multi-year build is a low-probability tail that is
purchased only if the pilot clears all of §8.

## 10. The corrected research claim

> **Symbol-U is not proposed as a replacement for token-level LLMs.** The BPE
> Transformer remains solely responsible for language modeling. Symbol-U is proposed as
> a **word/sentence-level symbolic semantic coordinate system** — a deterministic set of
> descriptors over a completed thought — **whose complementary value must be *measured*
> (existence → complementarity → semantic validity → causality) before any deployment
> architecture is built.** Its scientific worth is to be judged first by whether it
> carries semantic information beyond what modern Transformer representations already
> contain — not by whether it improves next-token prediction.

---

### One-line summary for the slide
*Symbol-U is endogenous, so no architecture can give it information the Transformer
lacks — measure whether it carries complementary, surface-controlled, synonym-invariant
semantic signal before building anything to exploit a signal it most likely doesn't
have; and if it ever helps, check first that the help isn't merely phonological.*
