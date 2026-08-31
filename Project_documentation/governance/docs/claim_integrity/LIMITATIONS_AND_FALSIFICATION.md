# Limitations & Falsification Outcomes (Phase 27)

*Every preregistered null (`FALSIFICATION_PLAN.md`, H0-1…18) reported against the frozen results, and
the Phase-27 questions answered directly. Negative and null results are reported plainly — several are
the study's main findings.*

## H0 outcomes

| H0 | Null claim | Outcome | Evidence |
|---|---|---|---|
| 1 | sentence splitting ≈ semantic decomposition | **NOT rejected (primary endpoint)** | P and B tie at 0.068 unsafe delivery in every stratum |
| 2 | dependency parsing ≈ dedicated component | **Rejected** | dependency approx causes 0.591 unsafe vs 0.068 |
| 3 | OpenIE / SRL sufficient | **Rejected** | OpenIE 0.864 unsafe; triple extraction structurally drops governing dimensions |
| 4 | LLM extraction alone sufficient | **Rejected (as simulated)** | simulated LLMs 0.08–0.15 unsafe, worse than sentence-split; higher variance |
| 5 | qualifier preservation immaterial | **Rejected** | qualifier deletion → 0.091 unsafe delivery |
| 6 | negation/modality errors too rare | **Rejected** | negation inversion → 0.182 unsafe |
| 7 | decomposition errors don't change EvidenceAssurance | **Rejected (spirit)** | drift alters the claim/evidence query; downstream evaluates the altered claim |
| 8 | decomposition errors don't change AssertionGate | **Rejected (spirit)** | every drift type propagates to delivery, uncaught |
| 9 | over-splitting safer than under-splitting | **Rejected** | over-split (clause/OpenIE) 0.57–0.86 unsafe; under-split 0.068 |
| 10 | under-splitting safer than over-splitting | **Supported (bounded)** | under-split is the safer error here, but the ambiguity policy, not a blanket rule |
| 11 | simple equivalence checks sufficient | **Rejected (for drift detection)** | per-dimension check catches inversions a similarity score accepts; but see H0-1 |
| 12 | uncertainty propagation adds no value | **Not rejected** | ambiguity/abstention preserved safety but did not beat sentence-split on the primary endpoint |
| 13 | learned extraction ≫ deterministic | **Not supported (as simulated)** | the fixed-rule "learned" comparator was worse (0.147) |
| 14 | distinct component unnecessary | **NOT rejected** | the heavyweight component is not needed; SC1 (2 probes) reproduces the primary result |
| 15 | human disagreement makes gold unstable | **Rejected** | 0.934 claim-count agreement; disagreement confined to atomicity granularity, none on semantic dimensions |
| 16 | decomposition not a major downstream contributor | **Rejected** | drift propagates to unsafe delivery at 0.09–0.21, uncaught downstream |
| 17 | "preserve original sentence" trivially safer & equally useful | **Rejected** | preserve-whole is unsafe (0.454) via ungoverned claims |
| 18 | cost of reliable decomposition outweighs value | **Partly supported** | the full 15-probe stack's cost is not justified; a ~4-probe minimal config captures the value |

**Score:** the *method-quality* nulls (2, 3, 9, 17) are firmly rejected — how you decompose matters a
lot. The *distinct-component* nulls (1, 14, 18) **survive**: a dedicated heavyweight stage is not
justified over a cheap preservation-first splitter with reference resolution.

## The Phase-27 questions, answered

- **Did sentence splitting perform as well?** On unsafe delivery, **yes** (0.068 = 0.068). It differs
  only on evidence-query integrity (dangling references).
- **Did clause splitting perform as well?** **No** — 0.568 unsafe (detaches modifiers).
- **Did LLM extraction outperform deterministic methods?** As simulated, **no** (0.08–0.15). Caveat:
  no live LLM was called; a real one may differ, and this is a labelled limitation.
- **Did self-checking help?** Marginally among the simulated LLMs (0.088 vs 0.122), still worse than
  sentence-split.
- **Were qualifier/scope errors common?** Yes, and each propagates to unsafe delivery uncaught.
- **Did decomposition errors materially change EvidenceAssurance / AssertionGate?** Yes — they change
  the claim those layers evaluate; the layers cannot see the original.
- **Did ClaimIntegrity reduce unsafe delivery?** vs triple/parser extraction, yes, dramatically. vs
  sentence splitting, **no** — it ties.
- **Did ambiguity handling / alternate decompositions help?** They kept safety (preserve-over-precision
  is ~8× safer than aggressive splitting) but did not beat sentence-split on the primary endpoint.
- **Did simple comparators match the full component?** **Yes** — SC1 (sentence + negation, 2 probes).
- **Did complexity earn its cost?** **No**, on the primary endpoint; the per-dimension modules earn
  their cost only as an *audit* of untrusted extractors.
- **Is claim decomposition a distinct governance function?** **Yes as a concern, no as a heavyweight
  component.** The function that matters is "preserve meaning + resolve references + never strip";
  it does not require a large dedicated stage.
- **Justified only for high-risk?** There was **no** high-risk subgroup where the component beat
  sentence-split (P = B in every risk tier), so even a high-risk-only heavyweight is unsupported.
- **Can downstream systems repair upstream semantic drift?** **No** — the central negative finding:
  drift is a no-tell failure downstream.
- **Does the remaining failure require human review?** The residual 0.068 (exception-bearing
  conjunction) needs subject-carrying structural parsing or human review; complexity alone does not fix
  it.

## Limitations (scope honesty)

- **Deterministic self-built corpus.** Rates (drift frequencies, propagation) are construction
  properties. Only mechanism and ordering transfer; the exact numbers will not. An externally-annotated
  corpus of real model outputs is the necessary follow-up.
- **Parsers and LLMs are simulated.** OpenIE/dependency/SRL/LLM methods are deterministic local
  approximations of their class behavior, labelled everywhere. The *direction* (triple extraction
  strips governing dimensions) is robust; a specific real system's rate is not established here.
- **The downstream adapter is a model, not the live components.** It maps dispositions to delivery via
  the corpus's `downstream_consequence`, without modifying EvidenceAssurance/AssertionGate. It captures
  the qualitative propagation; it is not a live end-to-end integration.
- **`causal_inflation → 0.000`** in the propagation matrix is a corpus artifact (the correlational
  cases' downstream mapping), flagged not smoothed.
- **The lexical detector is simple.** It handles the corpus's constructions; real NLI/coref would
  change the false-rejection and evidence-query numbers.

## What a follow-up should do

- An **externally-annotated corpus of real model outputs**, to test whether the P≈B tie survives
  natural language (it may not — real text has richer cross-sentence structure where reference
  resolution matters more).
- **Live parser/LLM extractors**, to confirm the triple-extraction danger and place real LLM extraction
  on the frontier.
- **A subject-carrying structural splitter**, to attack the residual 0.068 that every method here left
  unsolved.
