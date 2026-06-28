# Symbol-U — Scientific Roadmap

> **Type:** scientific foundation document (research track). No code. No implementation.
> Companion documents: `THEORY_FORMALIZATION.md`, `FALSIFICATION_STRATEGY.md`.
> Purpose: a roadmap of **scientific** milestones (tests of the theory), with engineering
> milestones removed. Each milestone is a falsifiable test, not a build.

## Milestones

| # | Milestone | Hypothesis | Expected observation if true | Falsification criterion | Confidence it is *answerable* | Depends on |
|---|---|---|---|---|---|---|
| **S0** | **Specify ρ\*** | The emergent reading can be written as a function `F` with an observable output mapping | proponents produce `F` + a pre-registered observable | proponents cannot define `F` without circular reference to its own outputs ⇒ the emergent theory is **not yet science** | unknown — **this is the gate** | none |
| **S1** | Atomic phonosemantics (pseudoword, unigram) | **Ax1**: `a(v)` predicts human sound-ratings of nonce stimuli | above-chance prediction | ≤ chance | high (standard method) | none (uses existing `a(·)`) |
| **S2** | Ontology-specificity | **Level B**: the *specific* `a(·)` matters | real ≫ random-relabel **and** ≫ generic-acoustic baseline | real ≈ relabel | high | S1 |
| **S3** | Independent attestation | **A3 / anti-circularity**: poles are not author-invented | poles match classical Sanskrit phonetic sources | no correspondence above chance | medium | none (parallel) |
| **S4** | Compositional / order | **Ax2**: order changes the reading predictably | human-predictable order effects | order effects unpredicted beyond a bag | medium | **S0** |
| **S5** | Emergence | **Ax3**: `F` beats the unigram sum | emergent predictions > additive baseline | no gain over additive | medium | S0, S4 |
| **S6** | Cross-linguistic universality | **A3 / Level C**: same sounds → same response across languages | stability beyond acoustic baselines | no cross-language stability | medium-low | S1–S2 |

## Ordering logic

- **S0 is a gate** for everything emergent (S4–S5): no defined `F`, no test of ρ\* / CSR.
- **S1–S3 are runnable now** and cheaply (pseudoword ratings + a relabel control +
  philological lookup). They decide whether the *atomic* theory survives at all: **if S1 or
  S2 fails, the program is falsified at its root regardless of ρ\*.**
- Only after **S1–S3 pass** is any implementation scientifically warranted — and any
  English / LLM application is much later still (S6-plus), not before.

## Level map (which milestone reaches which claim)

- **Level A** (useful representation): not a milestone here — already addressed (and failed)
  by the prior English work; not informative about the theory.
- **Level B** (the ontology matters): **S2** (relabel control), supported by **S3**.
- **Level C** (Sanskrit-varṇa acoustic semantics): **S6**, conditional on S1–S2 and on the
  gloss-free acoustic-only framing.

## The most important conclusion (carried from the formalization)

> **The atomic phonosemantic claim is falsifiable today, but the emergent ρ\* / CSR claim is
> not falsifiable until ρ\* is mathematically specified.**

- Atomic (Ax1): test now via S1/S2/S3.
- Emergent (Ax2/Ax3): blocked behind S0 (specify `F` + observable mapping).

## Implementation caution (binding for the research track)

**No further English LLM-controller or policy work should proceed** until either:
- **S1 / S2 / S3** provide support for the **atomic** claim, or
- **S0** specifies `ρ*` well enough to test the **emergent** claim.

Until then, build nothing. The only legitimate next scientific acts are **S0** (specify
ρ\*) in parallel with **S1–S3** (pseudoword / relabel / attestation tests), which can
proceed immediately and could falsify the theory at its root for almost no cost.

## What the prior work does and does not establish

- v3 / v4 / O1.5 / policy experiments live entirely at **Level A**, on **English**, using
  **glosses** — the three things the theory's unique claims explicitly route around.
- They established that the **English→varṇa implementation** fails as a representation of
  **English lexical meaning**, and explained the v3/v4 nulls.
- They did **not** test the Symbol-U theory (wrong input language, wrong yardstick,
  unspecified ρ\*). The theory remains neither supported nor refuted — and, for its
  distinctive claim, **not yet falsifiable**.
