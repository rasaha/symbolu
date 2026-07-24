# ClaimIntegrity — Evaluation Report (Phase 26)

*Synthesis against the frozen protocol (`EVALUATION_PROTOCOL.md`). All numbers come from the
hash-pinned artifacts (`verify_frozen.py`). Corpus: `ci_corpus_v1`, 832 examples, 1144 gold claims,
806 unsafe-allow claims. Simulated methods (parsers/LLMs) make zero live calls and are labelled.*

## 1. Headline

**The decomposition *method* dominates downstream safety, but the heavyweight component does not beat a
2-probe sentence splitter on the primary endpoint.**

- Triple/parser extraction (OpenIE/SPO) causes **0.864** unsafe delivery; sentence splitting and the
  component both cause **0.068**. Method choice moves the safety endpoint by an order of magnitude.
- On unsafe delivery, **the reference component ties sentence splitting (0.068 = 0.068)** in every
  partition and every risk tier. Its only distinct benefit is evidence-query integrity (dangling-
  reference resolution, 0.091 → 0.000) — a secondary endpoint.
- Decomposition drift **reaches** unsafe delivery (0.09–0.21 per error type) and **downstream never
  catches it** — confirming the core hypothesis at the mechanism level.

## 2. Primary & co-primary endpoints

| Method | unsafe delivery ↓ | material drift ↓ | evidence-query ↓ | cost |
|---|--:|--:|--:|--:|
| Q_oracle | 0.000 | 0.000 | 0.000 | — |
| **P_claim_integrity** | **0.068** | 0.136 | **0.000** | 15 |
| **B_sentence_split** | **0.068** | 0.136 | 0.091 | 2 |
| SC1 sentence+negation | 0.068 | — | 0.091 | 2 |
| L_hybrid (sim) | 0.080 | — | 0.091 | — |
| I_llm_simple (sim) | 0.122 | — | 0.091 | — |
| R_learned_comparator (sim) | 0.147 | — | 0.091 | — |
| N_minimal_split | 0.250 | — | 0.000 | — |
| A_preserve_whole | 0.454 | 0.545 | 0.000 | 0 |
| C_clause / O_aggressive | 0.568 | — | 0.091 | — |
| D_dependency / E_srl (sim) | 0.591 | — | 0.091 | — |
| F_openie / G_rule_spo (sim) | 0.864 | 0.705 | 0.091 | — |

## 3. Stratification (component vs sentence-split vs OpenIE, unsafe delivery)

| Stratum | P | B | OpenIE |
|---|--:|--:|--:|
| SIMPLE_ATOMIC | 0.000 | 0.000 | 1.077* |
| QUALIFIED_COMPLEX | 0.000 | 0.000 | 1.429* |
| MULTI_CLAIM | 0.000 | 0.000 | 1.000* |
| CROSS_SENTENCE | 0.000 | 0.000 | 0.125 |
| ADVERSARIAL_SCOPE | 0.500 | 0.500 | 0.500 |
| risk = high | 0.068 | 0.068 | 0.864 |
| risk = medium | 0.068 | 0.068 | 0.864 |
| risk = low | 0.068 | 0.068 | 0.864 |

`*` OpenIE rates exceed 1.0 where over-splitting invents multiple drifting fragments per example
(rate = unsafe events / gold claims). **P equals B in every stratum, including every risk tier** — there
is no high-risk subgroup where the component's extra machinery reduces unsafe delivery. The only
non-zero P/B cell is ADVERSARIAL_SCOPE, and there they are equal.

## 4. Error propagation — the mechanism behind H1

| Perturbation | → unsafe delivery |
|---|--:|
| numeric_mutation | 0.211 |
| population_broadening | 0.188 |
| negation_inversion | 0.182 |
| exception_deletion | 0.136 |
| qualifier_deletion | 0.091 |
| temporal / jurisdiction / attribution / modality deletion | 0.045–0.068 |

Every dimension-dropping error reaches unsafe delivery, and **none is caught downstream**: the gate
evaluates the altered claim faithfully because it cannot see the original. This is the study's positive
result — a decomposition error is a *no-tell* failure for EvidenceAssurance and AssertionGate.

## 5. Ablation & complexity

- **Load-bearing mechanism: reference resolution only** (evidence-query 0.091 → 0.000). The non-
  assertive filter is redundant on the main corpus; safe-split merely trades unsafe-omission for a
  dangling-reference harm.
- **SC1 (2 probes) ties the full component (15 probes) on unsafe delivery.** The extra 13 probes buy
  only reference resolution. The per-dimension checker modules do not earn their cost in the component's
  own output — preservation is free from not-stripping — but they are valuable as an **audit** of
  untrusted extractors (they are what quantified OpenIE at 0.864).

## 6. Verdict against the frozen decision rules

| Decision rule | Outcome |
|---|---|
| Heavyweight layer justified only if it beats sentence-split on the **primary** endpoint | **Not met** — ties at 0.068 |
| Recommend against triple/parser extraction | **Met** — 0.864 vs 0.068 |
| Reduce to minimal sufficient config if a simple comparator reproduces the primary result | **Triggered** — SC1 reproduces 0.068 |
| No production-readiness claim | Honored — deterministic self-built corpus |

## 7. The claims this study licenses

1. **Decomposition is a real, downstream-invisible failure surface.** A material share of unsafe
   deliveries can originate before evidence evaluation, and no downstream layer recovers them. (H1 —
   supported; H0-7/H0-8 — rejected in spirit.)
2. **How you decompose matters far more than whether you add a dedicated component.** Never strip
   modifiers (triple extraction is dangerous at 0.864); a preservation-first splitter is essential.
3. **The heavyweight component is not justified on the primary endpoint.** Sentence-splitting ties it;
   its distinct value is reference resolution, a secondary endpoint. (H0-1 — not rejected on unsafe
   delivery; H0-14/H0-18 — the distinct-component-necessity and cost-justification nulls survive.)
4. **The unsolved residual** (0.068 unsafe, the exception-bearing conjunction) needs subject-carrying
   structural parsing, which neither the component nor any simple baseline provides — complexity is not
   the missing ingredient.

Everything here is reproducible from the frozen artifacts and asserted in the Phase-24 tests.
