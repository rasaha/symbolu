# Final Verdict (v0.1)

Relationship Claim Validation Experiment v0.1 — "Claim Truth Layer".

---

## 0. The binding scope statement

This is a **new, self-contained** research track. The frozen substrate the brief
assumes — SEEB v1.0.0, a resolver series v0.1–v0.5, a hidden relationship corpus, a
frozen proposal-validation / governance / packet pipeline, and prior experiment
locks — **does not exist in this repository** (verified by exhaustive search). The
experiment was therefore run:

- over a **self-authored synthetic corpus** (not the referenced hidden corpus);
- with **deterministic, span-grounded judges** (not LLMs), for reproducibility;
- as a **stand-alone** layer that modifies no resolver/governance/packet/corpus
  (none exist here to modify).

Because the deterministic judges implement the same grounding logic the gold
encodes, **V4's perfect precision/recall/status-accuracy is by construction.** The
scientific content is the **ablation decomposition** (each judge removes a distinct
failure class), not the headline perfection. Nothing here is evidence of real-world
error reduction.

## 1. Final questions (answered separately)

**Did claim validation reduce unsupported relationships?**
Yes, on this synthetic corpus: false acceptances fell from **28 (V0) to 0 (V4)**;
all 28 unsupported/contradicted/insufficient/unknown claims the baseline retained
were correctly dropped or flagged.

**Did it preserve supported relationships?**
Yes: recall **1.0**, **0 false removals** — all 20 gold-retained relationships (12
supported + 8 partially-supported) were kept.

**Did Judge A and Judge B disagree meaningfully?**
Yes. B contributed contradiction detection A lacked (8 contradictions), and A and B
disagreed on a predicate in **4** equally-explicit direction-conflict cases — the
only genuine semantic disagreements, all routed to adjudication.

**Did Judge C improve over two judges alone?**
Yes, measurably: on the 4 equally-explicit conflicts, V3 (no C) accepts them as
SUPPORTED (4 false acceptances); V4 (with C) routes them to UNKNOWN / manual review.
Precision **0.8333 → 1.0000**, status accuracy **0.9167 → 1.0000**.

**Did deterministic validation remove relationships before adjudication?**
Yes: **6** claims were resolved by the deterministic layer before the judges — 3
removed (illegal type, duplicate, self-loop) and 3 abstained (missing document,
missing span, no citation). (Adjudication here is by deterministic judges, not
LLMs.)

**Were governance and packet unchanged?**
Yes — vacuously. No governance or packet implementation exists in this repository;
this track adds a stand-alone package and modifies nothing else (`git status`
confirms additions only).

**Should Claim Validation become a permanent stage before governance?**
**Not established.** There is no real governance pipeline or real corpus here to
justify permanence. The layer is a **candidate** worth evaluating **if and when** a
real proposal→governance pipeline and a real (or independently-annotated) corpus
exist. Recommending permanence now would overstate synthetic, construction-driven
evidence.

**Is there sufficient evidence for production deployment?**
**NO.**

## 2. Verdict

- **On the primary hypothesis, on this synthetic corpus:** supported — an
  evidence-grounded claim-validation layer reduced unsupported relationship
  assertions (fp 28→0) without removing supported ones (recall 1.0), net **+28**,
  bootstrap 95% CI **[0.4375, 0.7083]**.
- **On generalization:** nothing established. The result is corpus-internal and
  construction-driven.

## 3. Interpretation boundary

This experiment supports only: *"a relationship-claim-validation layer reduced
unsupported relationship assertions on a self-authored synthetic corpus, using
deterministic judges, and its components each removed a distinct failure class."*

It does **not** establish: general hallucination elimination · production
readiness · broad factual correctness · enterprise certification · that the layer
helps any real resolver/governance system.

## 4. What would make this real (future work, separate instruction)

A real proposal→governance pipeline to sit before; a real or independently-annotated
relationship corpus (not self-authored); genuine LLM judges with measured
inter-judge reliability; paraphrastic/implicit/multi-hop/adversarial cases; and a
preregistered evaluation with a held-out hidden lock. None of these exist yet, and
none were fabricated here.
