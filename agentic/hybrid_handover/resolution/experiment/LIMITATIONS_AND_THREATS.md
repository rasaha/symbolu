# LIMITATIONS_AND_THREATS — Exploratory Resolver Study v0.1

Read this before quoting any number from the study.

## Statistical / sample limitations
- **n = 60 is a pilot.** The primary endpoint has adequate power to detect the
  aggregate macro effect (CI excludes zero), but the per-slice tables (capability,
  difficulty, edge-type) have 2–13 cases per cell and are **descriptive only** — no
  per-slice significance is claimed, and individual cell deltas can flip with a single
  case.
- **One corpus, one author lineage.** Seed and pilot are two families, but both were
  produced through the same curation pipeline and the same underlying legal-document
  vocabulary. "Generalizes across families" means *these two families*, not the world.
- **Bootstrap assumptions.** The paired bootstrap resamples cases i.i.d.; genuine
  clustering (e.g. templates shared across cases) would understate variance. The
  curation pipeline quarantined near-duplicates, which mitigates but does not eliminate
  this.

## Construct / measurement limitations
- **Multi-edge-per-pair collapse.** The frozen classification metric keys edges by
  (src, dst) and keeps one type per pair; a case with two gold edges on the same pair
  (e.g. `same_as` + `supersedes`) can register an apparent mismatch even when the
  resolver emits both. This affected the visible corpus and is a property of the frozen
  metric, deliberately not changed here.
- **Discovery precision is pair-level, not semantics-level.** Over-proposal is counted
  as any predicted pair absent from gold; it does not distinguish a harmful spurious
  governance edge from a harmless extra reference. The negative-control slice (hybrid
  0.70 vs 0.47) is the check that over-proposal is not translating into unsafe answers.

## Internal-validity threats and how they were controlled
- **Hidden-set leakage / tuning.** Controlled by the preregistration + content-hash
  lock: thresholds and lexicon were frozen before any hidden inspection; the two
  post-lock-discovered regressions were left unfixed on purpose.
- **Governance/packet confound.** Controlled by composition: the hybrid reuses the
  frozen governance + packet builder unchanged, so Mode G / Mode P are identical to
  GraphTraversal (verified: McNemar n=0 discordant).
- **Researcher degrees of freedom.** Single primary endpoint fixed in advance; Holm
  correction over the secondary stage family; run order and bootstrap seed in the
  manifest; two byte-identical repetitions required.

## External-validity threats
- The evidence is **synthetic**. Real contracts have OCR noise, cross-references across
  hundreds of pages, and adversarial drafting the pilot only gestures at.
- The resolver is **deterministic symbolic** code; a learned or LLM-backed proposal
  layer would have entirely different failure modes (this study says nothing about
  those).

## What this study explicitly does NOT support
- Any production or certification claim.
- Any statement of broad generalization (Q6 = NO).
- Any comparison to systems outside the six preregistered comparators.
- Promotion to RRB v1.0 or a "production-ready" label.

The honest scope: *a richer deterministic relationship layer shows a real, isolated,
reproducible capability signal on a 60-case synthetic pilot, at the cost of precision
that must be fixed before the architecture is worth promoting.*
