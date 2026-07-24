# Scope-Carrying Conjunction Decomposition — Model & Protocol (M1)

*A small, targeted falsification study. The completed ClaimIntegrity study left a residual **0.068
unsafe-delivery rate**, concentrated in exception-bearing / scope-spanning conjunctions that both the
preservation-first splitter and sentence-splitting under-split (keeping the whole span) — because
splitting them naively detaches the governing modifier. This study asks whether a **small** scope-
carrying transformer can reduce that residual **without** trading it for invented/omitted claims,
detached qualifiers/exceptions, reference errors, or attribution/numeric/temporal drift.*

## Non-goals (hard constraints)

- Do **not** expand the general ClaimIntegrity architecture or reintroduce the rejected heavyweight
  component. The winning mechanism must remain a *small extension to the preservation-first splitter*.
- Do **not** become a general semantic parser, an OpenIE replacement, an LLM-dependent extractor, or a
  new downstream truth engine.
- Do **not** modify EvidenceAssurance, AssertionGate, AGE, ClaimIntegrity, or any frozen artifact. This
  study consumes the **frozen ClaimIntegrity downstream adapter** (`claim_integrity.downstream` /
  `claim_integrity.validation`) read-only as its scorer — so "unsafe delivery" is measured by the exact
  same machinery the prior study froze, not a new scorer built to flatter the mechanism.

## The governing-scope graph

A scope-spanning conjunction is `C1 <conj> C2` where one or more **governing elements** attach to a
scope that is not the surface clause they sit next to. The corpus records, per example, a
**governing-scope graph**: for each governing element, which conjunct(s) it governs.

Governing elements tracked:

| Class | Markers |
|---|---|
| shared subject | (grammatical subject shared across conjuncts) |
| negation | not, no, never, cannot |
| modality | may, might, can, must, should |
| uncertainty | likely, generally, typically, approximately |
| exception | except, unless, other than, unless monitored |
| condition | if, only if, provided that, when, subject to |
| temporal | as of, before, after, until, within |
| numeric | ranges, bounds, units |
| attribution | according to, reportedly |
| evidentiary status | no evidence, not recommended, not established |

A decomposition is **scope-faithful** iff every governing element is propagated to exactly the
conjuncts it governs — no more (spurious attachment), no less (detachment).

## The six variants (frozen definition)

| Variant | Behavior | Role |
|---|---|---|
| **A** | current preservation-first splitter (keeps scope-spanning conjunctions whole) | frozen baseline (the 0.068 residual) |
| **B** | naive split on coordinating conjunctions, no scope propagation | negative control |
| **C** | subject-carrying split (propagate shared subject only) | minimal |
| **D** | subject + qualifier carrying (subject, negation, modality, uncertainty, attribution, temporal, numeric) | mid |
| **E** | full scope-carrying (D + exceptions, conditions, evidentiary status) | maximal targeted |
| **F** | preserve-and-flag (do not split when attachment is not provably resolvable → `INDETERMINATE_SCOPE`) | abstention |

## Endpoints

- **Primary:** unsafe delivery rate through the frozen downstream adapter (lower is better; target
  materially below 0.068).
- **Secondary (each reported separately):** semantic-drift rate, qualifier-attachment accuracy,
  exception-attachment accuracy, subject-carry accuracy, omission rate, invention rate, atomicity,
  evidence-query alteration, INDETERMINATE rate, downstream catch rate, processing cost, deterministic
  reproducibility.

## Falsification conditions (preregistered)

The scope-carrying approach is **rejected or qualified** if any hold on the frozen corpus:

1. unsafe delivery is **not materially lower** than 0.068;
2. the improvement comes **mainly from abstention** (INDETERMINATE inflation) rather than correct
   splitting;
3. propagated qualifiers are attached to conjuncts they did **not** govern (spurious attachment);
4. subject propagation creates **unsupported/invented** claims;
5. rule complexity approaches the rejected heavyweight component;
6. results fail on **held-out** templates or domains;
7. **preserve-and-flag (F)** performs equally well at lower complexity.

## Decision options (smallest mechanism preferred)

1. adopt full scope-carrying split (E); 2. adopt only subject propagation (C); 3. adopt subject +
qualifier (D); 4. preserve-and-flag all scope-spanning conjunctions (F); 5. hybrid — split only when
attachment is provable, else preserve-and-flag; 6. reject targeted decomposition, retain 0.068.

## Honesty commitment

The corpus is constructed by us and could be built to favor the mechanism. Two guards against that:
(1) the scorer is the **frozen** ClaimIntegrity adapter, not a new one; (2) a **held-out** template/
domain split (M2) is evaluated separately, and success must survive it. **We will not claim success
merely because the synthetic corpus was constructed around the mechanism** — a win must hold on
held-out data and must not be an abstention artifact.
