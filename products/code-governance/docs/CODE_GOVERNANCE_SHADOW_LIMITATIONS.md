# Code Governance MVP 1A — Explicit Limitations

This phase is deliberately bounded. Read this before drawing any conclusion about
what the product guarantees.

## Scope limits

- **Code Governance does not discover every hidden bug.** It *governs* evidence;
  it does not itself detect defects.
- **Change Intelligence analyzers are not implemented** in MVP 1A. No mutation,
  fuzz, taint, dead-code, complexity, duplication, or performance-analysis engine
  exists here. The product accepts normalized external evidence and orchestrates
  risk-scoped, non-compensatory claims over it.
- **The product governs evidence produced by external validators.** Evidence
  quality is bounded by those validators.
- **AI-generated tests alone are insufficient for high-risk policy profiles.**
  HIGH-tier policy requires independent review and security evidence; same-agent
  tests do not satisfy a mandatory independent-review claim.

## Authority limits (never collapsed)

- **A TAP result is not authorization.** Per-claim `evidence_coverage` is
  descriptive, never an aggregate authorization or quality score.
- **A recommendation is not a binding decision.** `GovernanceRecommendation`
  (`is_binding = False`) can never be a `DecisionRecord`.
- **ActionGate authorization is not live execution clearance.** The result is
  recorded `SHADOW_ONLY` and is never acted on.
- **Action Clearance is not implemented in this phase.** The chain records
  `ACTION_CLEARANCE_NOT_EVALUATED`.
- **Execution reservation is not implemented.**
- **GitHub execution is disabled.** There is no GitHub write path, no merge
  credential, and no execution provider. `execution_status()` returns `DISABLED`.

## Persistence limits

- Records are held in **in-memory tenant-isolated immutable reference stores**.
  This is **not** the production durable store. No production database is
  introduced. A durable, append-only, hash-chained store is a later-phase item
  (StoryGraph `DurableAuditLog` / `agentic/ledger` are viable reference patterns).

## Determinism caveat

Product content-derived fingerprints are replay-stable. Upstream
Decision-Authority-minted ids (`decision_id`, `cer_id`) and the CER
`content_hash` (which stamps an issue time) legitimately vary across runs; they
are bound as provenance fields but excluded from identity fingerprints.

## The product is shadow / recommendation only.

Nothing in this phase merges, approves, dispatches, closes, labels, or otherwise
mutates a pull request.
