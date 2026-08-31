# E1 gate rationale (B0 baseline + minimum effect size + non-reserved evidence)

Gates are **absolute competence bars**, not thresholds set at observed development performance. Each is
justified below by (a) the frozen B0 baseline, (b) a meaningful minimum effect size, and (c) why a
partially-generalizing or shortcut model would **fail** it. None is set to "observed dev minus epsilon"
(observed dev G1 addressing ≈ 0.99; the G1 gate is 0.80 — a competence floor, not a shave off the top),
and none references the reserved cohort.

## Baseline facts (frozen, non-reserved)
- The task has **32 candidate keys per episode**, so **chance addressing = 1/32 ≈ 0.031**.
- **B0** (frozen anonymous slots) is at chance on every held-out generalization split (dev e2e ≈
  0.02–0.06) and has **no abstention** (no-match false-accept ≡ 1.0 by construction).
- The leakage suite proves a **surface-token-overlap matcher is at chance** — so any accuracy materially
  above chance requires *learned semantic composition*, which is exactly the capability under test.

## Generalization gates (min correct-key top-1 addressing)
- G1 unseen-identity **0.80**, G2 paraphrase **0.80**, G3 hard-names **0.80**, G5 recombined **0.80**,
  G4 same-entity/diff-attribute **0.75**.
- **Rationale:** 0.80 on **unseen** compositional identities among 32 hard candidates is a demanding
  absolute bar — ~26× chance (0.031). A model that memorized training identities, exploited a surface
  shortcut, or only partially composed primitives would land far below 0.80 on held-out combinations. The
  bar encodes "clearly competent semantic addressing," not "marginally above chance." G4 is 0.75 because
  same-entity/different-attribute discrimination is intrinsically harder (the entity primitives are
  shared), so a slightly lower but still-demanding bar is justified.

## Minimum effect size vs B0 (end-to-end)
- **min improvement over B0 = 0.50** absolute; **min ordinary retrieval accuracy = 0.70**.
- **Rationale:** since B0 ≈ chance (~0.03–0.06), a 0.50 absolute improvement is a **large effect**
  (roughly an order of magnitude), and 0.70 absolute retrieval is well above any partial-learning
  regime. These encode "explicit keys enable semantic addressing that anonymous slots cannot," the exact
  claim. A model that only weakly beat B0 (e.g., +0.30, or 0.55 absolute) would **fail**.

## No-match gates (learned null key)
- max false-accept **0.30**, min recall **0.70**, min precision **0.70**, max confident-false-accept
  **0.20**, max valid false-reject **0.15**, min answer-availability **0.80**.
- **Rationale:** B0 has no abstention (false-accept 1.0). A learned null key that collapsed (always pick
  a key) would score false-accept ≈ 1.0 and **fail**; one that over-abstained would fail false-reject /
  availability. Requiring correct abstention on ≥70% of no-match queries **and** answering ≥80% of valid
  ones is a genuine open-set-rejection bar that a naive model does not meet. (This is the weakest part of
  the capability, deliberately gated as primary.)

## Diagnostic / regression gates
- min oracle-key value accuracy **0.99** (E1's value read is a lookup; this checks the value path is
  intact — a broken value path fails), max oracle-to-predicted gap **0.30** (limits how much addressing
  error alone degrades end-to-end), min G7-stable addressing **0.90** (no catastrophic regression on
  easy cases).

## Fresh-seed reliability
- 5 fresh reserved seeds; **≥4 must pass all primary gates**; worst-seed G1 ≥ **0.70**.
- **Rationale:** a single lucky seed cannot carry the verdict; the worst-seed floor prevents averaging a
  strong seed with failures. 4/5 tolerates one unlucky seed while still requiring broad reliability.

## Non-triviality
These bars are **failable**: a shortcut model fails the leakage suite; a memorizer fails held-out G1/G5;
a weak learner fails the 0.50 effect-size and 0.70 absolute bars; a collapsed or over-abstaining null key
fails the no-match gates; an unstable model fails the fresh-seed floor. Passing requires genuine,
reliable, held-out semantic addressing with working abstention.
