# Routing retention and the two failure families

## The interventions retained routing

The persistence phase set out to stop the address-routing decay diagnosed earlier (correct-slot
routing forming near step 600 then decaying by 1200). On that **narrow** objective — measured on the
**fixed routing diagnostic** — several interventions retained a strong written-slot preference after
scaffold withdrawal: at step 1200 the correct-slot probability is retained across the persistence
arms — O1R 0.78/0.82 (on its non-quality-failed seeds), H1 0.84/0.97/0.99, H2 0.95–0.97 — versus plain
O1's decay to 0.17–0.25. This demonstrates that *diagnostic routing decay can be mitigated* ("persist
the address supervision / consolidate the addressing parameters / distill the read distribution" keeps
the addressing metric alive). It did **not**, however, produce reliable, quality-preserving
end-to-end retrieval across the evaluation distribution (next section).

## But retrieval still failed — via two distinct families

Clean-stable retrieval nonetheless did not reach ≥ 4/5 for any arm, because retention of *addressing*
is not sufficient. Two separable failure families appear:

### Family 1 — quality interference (optimization cost of persistent supervision)
O1R s24/s25, H1 s25, H2 s25 (and R0 s25) fail the **quality** gate (ppl > 1.20×A+) while retrieval is
present. The persistent auxiliary / teacher / just longer effective pressure competes with language
modeling. This is an optimization-balance failure, not a memory-path failure.

### Family 2 — downstream value/readout collapse
**H2 seed23** is the clean exemplar: correct-slot prob retained **0.96** at step 1200 and quality
passes, yet needle collapses **1.00 (step 700) → 0.00 (step 1200)**. The model still routes to the
right slot on the diagnostic probe, but end-to-end retrieval is gone — the loss is **downstream of
address selection** (stored value, read reconstruction, fusion, or decoder).

## Corrected interpretation (important)

- The evidence for Family 2 is the **dissociation between the routing diagnostic probe (prob 0.96,
  measured on a fixed internal probe) and the eval needle (0.00)** — NOT a causal-ablation result.
- The correct-slot probability ≈ 0.96 for H2 seed23 was measured on the **fixed routing diagnostic**;
  task retrieval on a **separate evaluation distribution** collapsed to zero.
- On seed23 the causal ablations at the terminal checkpoint are **non-informative**: the post-train
  baseline needle is already 0.00, so slots-off (0.00) and randomized-address (0.05) collapse nothing.
  A collapsed seed cannot be called "causally clean." This is labeled `NON_INFORMATIVE_BASELINE_ABSENT`
  in the analysis and must not be cited as causal evidence.
- This is a **routing-probe-versus-evaluation-retrieval dissociation**. It **motivates** oracle-address
  and value-path diagnostics (localizing where usable information is lost) but **does not prove causally
  clean retrieval on the failed evaluation examples** — establishing that requires the controlled
  bypasses of the next diagnostic phase.

## Why this narrows the problem

The program has moved from "BindingSlots sometimes collapses" to: **address routing can be retained
strong (and, where measurable, causally clean) while the memory's usable information disappears later
in the value/readout/decoder pathway — and, separately, persistent supervision can regress language
quality.** These are two potentially independent problems and should be localized independently, with
probes and controlled bypasses (not another intervention sweep). That is the next preregistered phase.

## Conservative bounds

Single-trajectory reads on five reserved seeds; one downstream-collapse exemplar (H2 s23) and a small
set of quality-failure exemplars. The mechanistic split is a strong, testable hypothesis — the value
integrity / readout isolation phase is designed to confirm or refute it mechanically.
