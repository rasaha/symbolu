# ACP Product-Core Separation & Canonical-Package Readiness Audit

This is the top-level audit document. It links the companion reports and records the Section-1 live
starting point, the disambiguation, the boundary, and the readiness conclusion. All findings are drawn
**directly from the live repository** at the verified default HEAD; the ACP freeze digest was recomputed
and verified against live code as part of this audit.

## Companion documents

| Area | Document |
|---|---|
| Verdict + baseline | `EXECUTIVE_SUMMARY.md`, `BASELINE.md` |
| Acronym disambiguation & scope | `TERMINOLOGY_AND_SCOPE.md` |
| File inventory | `FILE_INVENTORY.md`, `acp_file_inventory.json` |
| Candidates & selection | `IMPLEMENTATION_CANDIDATES.md`, `CANONICAL_SOURCE_DECISION.md`, `acp_candidate_matrix.json` |
| Public API & contracts | `PUBLIC_API_INVENTORY.md`, `REQUEST_RESULT_CONTRACTS.md`, `acp_api_inventory.json` |
| Authority & integration | `AUTHORITY_BOUNDARY.md`, `ACTIONGATE_INTEGRATION.md`, `SIGNAL_OWNERSHIP_MATRIX.md` |
| Consumers & imports | `CONSUMER_MAP.md`, `IMPORT_GRAPH.md`, `acp_consumer_map.json` |
| Duplication | `DUPLICATION_DISPOSITION.md` |
| State & determinism | `STATE_AND_PERSISTENCE.md`, `DETERMINISM_AND_EQUIVALENCE.md` |
| Dependencies & maturity | `DEPENDENCY_DIRECTION.md`, `MATURITY_ASSESSMENT.md`, `acp_maturity_matrix.json` |
| Packaging | `PACKAGE_READINESS.md`, `COMPATIBILITY_STRATEGY.md`, `FREEZE_IMPLICATIONS.md` |
| Planning | `MIGRATION_SEQUENCE.md`, `RISK_REGISTER.md`, `OPEN_QUESTIONS.md`, `ROLLBACK.md`, `acp_migration_manifest.json` |

## Section 1 — Verified live starting point

```text
DEFAULT_BRANCH            claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF
DEFAULT_HEAD             3ec11e4ecbc209eabc69d3c0d8a75ecaa10f6def  (Merge PR #1273, Code Governance design spec)
WORKTREE_STATUS         clean
PYTHON_VERSION          3.11.15 (Linux, /usr/local/bin/python3)
ENVIRONMENT             remote CCR container; pytest 9.1.1 / pydantic 2.13.4 / numpy 2.4.6 pip-installed to
                        run the baseline (no repository file changed)
ACP_RELATED_OPEN_PRS    none  (PR search returned 8 closed, 0 open, touching ACP)
ACP_RELATED_RECENT_BRANCHES  none matching acp/clearance among 241 remote branches; the task branch
                        claude/acp-product-core-separation-audit-qrwlxv previously existed on origin and
                        was deleted during fetch — recreated locally from the default tip
```

Additional Section-1 determinations:

- **Model Selection canonical migration & closure integrated?** **Yes** — PR #1271 (`952d8fe2`) is an
  ancestor of the default tip; `packages/capabilities/model-selection` (`ugence_model_selection`) is present
  and green.
- **Latest Code Governance design & competitive documents integrated?** **Yes** — PR #1273 is the default
  HEAD; `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`, `…_COMPETITIVE_POSITIONING.md`, `…_BATTLECARD.md` present.
- **Any ACP audit/packaging/migration/redesign/implementation branch already?** **No.**
- **Did the default branch advance after the last Model Selection closure?** **Yes** — `952d8fe2`
  (MS closure) → `3ec11e4e` (via Code Governance design-spec merges). The previously reported
  `952d8fe2` is **not** current; this audit is anchored to `3ec11e4e`.

The repository state was established reliably; the audit proceeds.

## Section 2 — Disambiguation (summary; full detail in `TERMINOLOGY_AND_SCOPE.md`)

"ACP" is overloaded across **four distinct concepts** and one shared vocabulary word ("clearance" =
CLEAR/HOLD). The authoritative governance meaning the audit intends — *evaluate whether an already-authorized
action remains valid and operationally permissible immediately before execution* — is matched by the
**cloud/console** framing of ACP but **contradicted** by the **robotics V1** framing (which authorizes).
The live code therefore only **partially** agrees with the intended definition.

## Section 5 — Authority boundary (frozen for this audit)

```text
Decision Authority   : who may make the binding decision, and was it validly recorded?
ActionGate           : is THIS exact proposed action authorized under the decision + policy?
ACP (clearance)      : is the already-authorized action still clear to execute NOW?
Execution provider   : performs the already-authorized, cleared operation.
```

Intended sequence:
`DecisionRecord → ContextEnvelopeRecord → ActionGovernanceRequest → ActionGovernanceResult → ACP clearance
→ execution dispatch → observation & reconciliation`.

The live code **preserves** this boundary in the cloud/console framing (ACP is orthogonal to ActionGate,
narrow-only, never executes) and **contradicts** it in the robotics V1 framing (ACP mints an execution
grant). See `AUTHORITY_BOUNDARY.md` for the evidence and `SIGNAL_OWNERSHIP_MATRIX.md` for input ownership.

## Readiness conclusion

- **Canonical source:** `NO_STABLE_PRODUCT_CORE_EXISTS` for a governance Action-Clearance product (secondary
  reading: `MULTIPLE_PARTIAL_SOURCES_REQUIRE_CONSOLIDATION`). The robotics core is real and frozen but
  robotics/cloud-domain-shaped and shadow-only; it does not span the console or governance-chain framings.
- **Maturity:** `SHADOW_ONLY` (frozen deterministic core; authored/synthetic fixtures; no production use).
- **Freeze:** not in the platform freeze; **is** under a local ACP V1 digest freeze that an import rewrite
  would break.
- **Verdict:** **ACP NOT READY — do not package.** Prerequisites in `MIGRATION_SEQUENCE.md`.

No runtime, package, contract, API-snapshot, freeze-manifest, or behavior change was made in this phase.
