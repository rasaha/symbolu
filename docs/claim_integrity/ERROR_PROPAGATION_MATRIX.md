# Error-Propagation Matrix (Phase 19)

*`claim_integrity/downstream.py::propagation_matrix`. Each row is a single-dimension corruption applied
to the ORACLE decomposition, isolating how that one error type propagates to downstream outcomes. The
question: which decomposition errors reach **unsafe delivery**, and which do downstream layers absorb?*

## Matrix (ci_corpus_v1)

| Perturbation | → unsafe delivery | → false rejection | → evidence-query altered |
|---|--:|--:|--:|
| numeric_mutation | **0.211** | 0.007 | 0.000 |
| population_broadening | **0.188** | 0.000 | 0.000 |
| negation_inversion | **0.182** | 0.000 | 0.000 |
| exception_deletion | **0.136** | 0.000 | 0.000 |
| qualifier_deletion | 0.091 | 0.000 | 0.000 |
| temporal_deletion | 0.068 | 0.000 | 0.000 |
| jurisdiction_deletion | 0.045 | 0.000 | 0.000 |
| attribution_deletion | 0.045 | 0.000 | 0.000 |
| modality_deletion | 0.045 | 0.000 | 0.000 |
| causal_inflation | 0.000 | 0.000 | 0.000 |

## The central finding: downstream cannot catch decomposition drift

Every perturbation that drops a governing dimension propagates to **unsafe delivery** — numeric
mutation, population broadening, and negation inversion each reach 0.18–0.21. **None** is caught by the
downstream layers, and that is the point: EvidenceAssurance and AssertionGate evaluate the claim they
are handed. They have no access to the original output, so an altered-but-fluent claim is governed
faithfully — against the wrong proposition. A decomposition error is, in the vocabulary of the prior
track, a **no-tell failure for the downstream layers**: there is no signal in the altered claim that it
differs from what the model said.

This is the core hypothesis (H1) confirmed at the mechanism level: **a material share of unsafe
downstream deliveries can originate in claim decomposition, before evidence evaluation, and downstream
robustness does not rescue them.** (Rejects the spirit of H0-7 and H0-8: decomposition errors *do*
change EvidenceAssurance and AssertionGate outcomes, because those layers operate on the decomposed
claim.)

## Which errors matter most

- **High propagation (≥0.13):** numeric mutation, population broadening, negation inversion, exception
  deletion. These flip a withhold into an allow with no downstream tell — the priority targets for any
  preservation check.
- **Moderate (0.045–0.091):** qualifier, temporal, jurisdiction, attribution, modality deletion. Real
  but lower-frequency in this corpus; still uncaught downstream.
- **causal_inflation → 0.000:** the one corruption that did not reach unsafe delivery here — the
  corpus's correlational claims map to a downstream consequence that the "causes" rewrite did not flip
  under this model. Reported as-is (not smoothed): it is a limit of the corpus's causal cases, not
  evidence that causal drift is downstream-safe in general. The Phase-17 adversarial `causal_direction`
  cases show triple methods drifting on causation, so the low number here is a corpus artifact to fix
  in a follow-up, flagged rather than hidden.

## Consequence for the architecture

The matrix says the *value of preservation is real and downstream-invisible* — you cannot recover it
later, so it must be protected at decomposition time. But it does **not** say a heavyweight component is
required: the same preservation is achieved by not stripping (sentence splitting), and the residual
unsafe delivery (exception under-split) is shared by the component and sentence splitting alike. The
matrix therefore points to **targeted preservation guarantees** (never drop negation/numeric/
population/exception; resolve references) rather than a large distinct stage — the reduction options
weighed in the architectural decision (Phase 28).
