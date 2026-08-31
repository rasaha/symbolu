# FAILURE_ATTRIBUTION — One Failure, One Stage

Every incorrect case is attributed to **exactly one** stage, in pipeline order,
so responsibilities never double-count. This is what makes "is the residual a
retrieval, relationship, governance, or packet problem?" answerable per case.

## Stages, in attribution order
1. **extraction** — a gold-required node's span is absent from the evidence
   (mode-dependent), OR the case is a pure-coverage matter (OCR/scan) handled by
   SEEB's upstream safety gate, not the resolver.
2. **relationship** — evidence present, but a gold typed edge is missing/incorrect.
3. **governance** — edges correct, but the governing / abstain decision is wrong.
4. **packet_construction** — governance correct, but the derived answer is wrong.
5. **safety_gate** — reserved for pipeline-gate interactions.
6. **unknown** — none of the above explains it.

The first stage that fails (in this order) owns the failure. A relationship
failure is never also charged to governance; a governance failure is never also
charged to packet construction.

## Attribution results (Mode A; Mode B identical)

| Resolver | correct | extraction | relationship | governance | packet_construction |
|---|---|---|---|---|---|
| frozen | 6/16 | 1 | 8 | 0 | 1 |
| rule | 9/16 | 1 | 1 | 3 | 2 |
| graph_traversal | 13/16 | 1 | 0 | 0 | 2 |

## Reading the ladder
- **FrozenResolver** fails mostly at **relationship** (8): it cannot build the
  typed edges at all, so downstream stages never get a correct graph.
- **RuleResolver** moves failures downstream: it builds the edges (relationship
  drops to 1) but, lacking abstention, fails **governance** (3: version, cycle,
  dangling reference).
- **GraphTraversalResolver** clears relationship and governance entirely. Its
  only residual is **packet_construction** (2) — two precedence cases where
  governance is correct but the deterministic answer-deriver cannot infer
  "allowed" from "termination for convenience requires N days notice" — plus one
  **extraction** case (OCR corruption, an upstream coverage matter).

The key methodological result: the attribution framework shows the residual for
the strongest deterministic resolver is **not** relationship or governance — it is
a narrow packet-construction (surface-phrasing) gap and an upstream extraction
matter. Relationship reasoning on SEEB v1 is deterministically solvable; the
framework locates the remaining slivers precisely, and is ready to attribute a
future resolver's failures the same way.
