# Falsification Assessment & Complexity Comparison (M6)

*The seven preregistered falsification conditions (`SCOPE_MODEL_AND_PROTOCOL.md`) checked against the
frozen results, and the complexity of the winning mechanism versus the rejected heavyweight component.*

## Falsification conditions

| # | Condition (reject/qualify if…) | Status | Evidence |
|---|---|---|---|
| 1 | unsafe delivery not materially lower than 0.068 | **Passed** (gated only) | gated extension: general corpus **0.068 → 0.000**; scope corpus 0.333 → 0.148 |
| 2 | improvement mainly from abstention | **Passed** | the extension actively splits provable cases (splits more than the current splitter on >100 examples); it preserves-and-flags only the non-provable ambiguous families |
| 3 | qualifiers attached where they don't govern (spurious) | **Partly triggered — bounded** | spurious attachment 0.077 on the scope corpus; but exception-attachment accuracy is 1.000 and every spurious case causes *conservative* false-rejection, never unsafe delivery |
| 4 | subject propagation creates unsupported/invented claims | **Passed** | no invented-claim increase (general false-rejection unchanged at 0.068; unsafe 0.000); ablation shows subject-carry is not even load-bearing (reference resolution covers it) |
| 5 | rule complexity approaches the heavyweight component | **Passed** | the mechanism is a gate + postposed-exception carry over the frozen splitter's output — a handful of regexes (see below) |
| 6 | fails on held-out templates/domains | **Passed** | held-out scope slice 0.395 → 0.186; and the entire general corpus is effectively held-out (not built for this mechanism) — 0.068 → 0.000 there |
| 7 | preserve-and-flag (F) performs equally well at lower complexity | **Passed** | F is competitive on the *scope* corpus (0.074) but **undeployable on the general corpus (0.218)**; only the gated extension is safe generally |

**No condition rejects the mechanism, provided it is the tightly-gated extension.** Two conditions
carry honest qualifications: (3) the mechanism does over-propagate on ~7.7% of scope cases, but only
into conservative false-rejection; (1) the "0.000" on the general corpus is a best case on the frozen
deterministic corpus, where the 78 residual cases all match the detected pattern.

## The critical honesty result

On the **purpose-built scope corpus**, the ungated variants (E full-scope, F preserve-flag, G hybrid)
score **best** (0.074 unsafe). On the **frozen general corpus** — which was not constructed for this
mechanism — those same ungated variants are **catastrophic** (0.218–0.472), and only the gated
extension is safe (0.000). The scope corpus flatters the aggressive variants because it is *all*
conjunctions; the general corpus is the deployment reality. **We do not claim success from the scope
corpus** — the claim rests on the un-rigged general-corpus cross-check.

## Minimum load-bearing rule set (ablation)

For the actual residual (general corpus):

- **`postposed-exception carry` is the single load-bearing element** — removing it reverts the general
  corpus to 0.068. Distributing a spanning `unless/except` clause across the split conjuncts is what
  eliminates the residual.
- **subject-carry, qualifier-prefix, exception-prefix, and the spanning-modifier gate are not
  load-bearing** for the general residual (each removal leaves 0.000) — reference resolution already
  supplies the subject.
- The one indispensable safety property is **operating on the frozen splitter's output**, not raw text.

The other propagation elements matter only for *other* scope structures (preposed exceptions, temporal
prefixes) that appear on the concentrated corpus but not in the actual residual.

## Complexity comparison

| Mechanism | Rules / footprint |
|---|---|
| Rejected ClaimIntegrity heavyweight component | full per-dimension checkers + parsing + validation + audit (~15 probes, many modules) |
| **This mechanism (gated extension)** | 1 gate predicate + `_parse` (3 regexes) + postposed-exception carry, over the frozen splitter's output; reference resolution reused. `re.compile` count in `variants.py` < 15, and the *load-bearing* subset is ~4 patterns. |

The winning mechanism is a genuine **small extension**, not a re-introduction of the heavyweight
component. It adds no model dependence, no general parser, no new downstream engine.

## What remains unresolved

- **The ambiguous residual (scope corpus 0.148).** Nested exceptions, multiple subjects, and adversarial
  punctuation are genuinely ambiguous; the extension correctly preserves-and-flags them rather than
  guessing, so they remain as flagged whole spans for human/whole-span evaluation. Splitting them safely
  needs attachment resolution the small mechanism deliberately does not attempt.
- **The general "0.000" is corpus-bounded.** On the frozen synthetic corpus every residual case matches
  the detected pattern. On real text, pattern detection would be imperfect; the honest transferable
  claim is *directional* (postposed-exception distribution eliminates the exception-under-split
  residual), not the exact rate.
- **Spurious over-propagation (0.077)** trades a small amount of conservative false-rejection for the
  safety gain. Whether that trade is acceptable is a policy choice, surfaced here, not hidden.
