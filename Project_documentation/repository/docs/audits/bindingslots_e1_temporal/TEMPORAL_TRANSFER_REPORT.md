# E1 Temporal Event Memory transfer — report

**Primary verdict: `E1_TEMPORAL_TRANSFER_PARTIAL`.**
**Always co-emitted: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.**
`E1_STRUCTURAL_TRANSFER_CONFIRMED` and `E1_FOLLOW_ON_RESEARCH_ELIGIBLE` are **not** emitted (transfer was
not validated). KDA remains blocked.

One bounded B0-vs-E1 test of whether the **exact frozen C1 recipe** transfers, **without retuning**, to a
structurally different Temporal Event Memory task at comparable scale. Verdict reconstructs mechanically;
artifact hashes match; frozen `abc.json` (`b31989a3…`) unchanged. **No gate was weakened and nothing was
retuned after observing results.**

## Result summary (mean across the 5 fresh reserved seeds 6140–6144)

| split | E1 | gate | pass |
|---|---|---|---|
| T1 unseen entities | 0.867 | ≥0.80 | ✅ |
| T2 unseen combinations | 0.897 | ≥0.80 | ✅ |
| T3 temporal-order | 0.871 | ≥0.80 | ✅ |
| **T4 latest-state** | **0.789** | **≥0.85** | **❌** |
| T6 paraphrase | 0.875 | ≥0.80 | ✅ |
| T7 confusable | 0.849 | ≥0.80 | ✅ |
| T9 stable direct | 0.981 | ≥0.90 | ✅ |
| improvement over B0 (macro T3,T4) | +0.736 | ≥0.50 | ✅ |
| no-match false-accept | 0.105 | ≤0.30 | ✅ |
| no-match false-reject | 0.000 | ≤0.15 | ✅ |
| no-match recall | 0.895 | ≥0.70 | ✅ |
| **T5 predecessor/successor (diagnostic)** | **0.392** | — reported only | — |

B0 (frozen anonymous slots) is at chance on every split (~0.05–0.10). Worst-seed `min(T3,T4)` = 0.753.
**Full-pass seeds: 0/5** — the *only* unmet primary gate is **T4 latest-state** (0.75–0.83 across seeds,
never ≥0.85); every other primary gate passes on all 5 seeds, so the mechanical verdict is **PARTIAL**
(not FAILED, not NO_MATCH_FAILED).

## Interpretation (honest, bounded)
The frozen E1 mechanism **substantially transfers** to the temporal family: it resolves entities and
retrieves the correct record for **position-indexed** queries (a specific step: T3), generalizes to
unseen entities/combinations/paraphrases/confusable sets (T1/T2/T6/T7), keeps the easy direct case
strong (T9 0.981), abstains well (no-match), and **beats anonymous B0 by ~0.74** — far above the 0.50
effect-size bar.

It **falls short on latest-state inference** (T4 0.789 < 0.85): choosing the **highest-position** record
among an entity's several events is not reliably learned by the frozen mean-pool cosine matcher. The
leakage suite rules out a shortcut — a "pick the globally-newest record" heuristic scores at chance
(0.093), so T4 genuinely requires combining entity identity with a learned *latest* preference, which
the frozen recipe only partially acquires. The **relational T5 predecessor/successor** is low (0.392,
diagnostic-only), consistent with the preregistered expectation that multi-event relational reasoning is
a distinct capability not required for the primary verdict.

## What this supports / does not support
Supports **only**: "the frozen E1 recipe transferred to the preregistered Temporal Event Memory task for
identity- and position-indexed retrieval, but did not clear the latest-state gate at comparable scale;
relational successor retrieval was not achieved." It does **not** establish full structural transfer,
does **not** attribute results to any component, does **not** address whether a larger E1 could do
latest-state or real NL (a separate, later capacity track — deliberately not run), and does **not**
unblock KDA. Anonymous BindingSlots routing remains unresolved.

## Next-step note (named, not run)
The bottleneck is latest-state / relational temporal inference, not identity retrieval. Any follow-up
(e.g., whether a modestly larger E1 or an order-aware read clears T4/T5) is out of scope here and would
require its own preregistration and authorization. Nothing is started.
