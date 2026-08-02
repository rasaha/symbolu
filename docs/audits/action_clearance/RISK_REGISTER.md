# ACP Risk Register

Priority: **P0** (must resolve before any packaging) · **P1** (resolve during) · **P2** (monitor).
Class: MIGRATION_BLOCKER · PREREQUISITE · PILOT_RISK · PRODUCTION_RISK · FUTURE_ENHANCEMENT.

| # | Pri | Risk | Class | Evidence | Mitigation |
|---|---|---|---|---|---|
| R1 | P0 | **ACP↔ActionGate boundary ambiguity** — robotics V1 mints an authorization grant while cloud/console never authorizes | **MIGRATION_BLOCKER** | `acp/ACP_ARCHITECTURE.md:20,110` vs `operational_safety.py:11-12` | Decide one meaning before naming a package "clearance" |
| R2 | P0 | **No stable request/result contract** — three divergent shapes; consumers couple to enum `.value` | **MIGRATION_BLOCKER** | `REQUEST_RESULT_CONTRACTS.md` | Define one `Clearance*`/reuse `ActionGovernance*` family |
| R3 | P0 | **No single product core** — discipline split across robotics core, console reimpl, DA seam | **MIGRATION_BLOCKER** | `CANONICAL_SOURCE_DECISION.md` | Choose the served world; factor a neutral kernel |
| R4 | P0 | **Shadow-only maturity presented as production** — overstated readiness risk | **PRODUCTION_RISK** | `ACP_V2_1_RESULTS.md:117-118`; live path on a stub | Keep shadow discipline; no "validated/production" claims |
| R5 | P0 | **Frozen-source movement breaks the ACP V1 digest** on import rewrite | **PREREQUISITE** | `FREEZE_IMPLICATIONS.md`; digest `8f8660e2…` verified | Freeze-amendment plan + update `acp_k8s_integrated` pin |
| R6 | P1 | **Duplicate clearance logic** in ≥3 places (robotics, `acp_db`, console) | **PREREQUISITE** | `DUPLICATION_DISPOSITION.md` | Consolidate onto one kernel during migration |
| R7 | P1 | **Consumer deep imports** of unfrozen `.cloud.*` bypass the curated API | **PREREQUISITE** | `IMPORT_GRAPH.md`; `CONSUMER_MAP.md` | Curated public API + identity-preserving shim |
| R8 | P1 | **Unclear one-time-use ownership / missing replay prevention** | **PREREQUISITE** | `STATE_AND_PERSISTENCE.md` | Model prior-consumption as a received signal; ledger stays downstream |
| R9 | P1 | **Missing durable clearance references** — no clearance ID store, no supersession | **PREREQUISITE** | `STATE_AND_PERSISTENCE.md` | Define durable references owned by the execution ledger, referenced by ACP |
| R10 | P1 | **Stale-authorization acceptance** if freshness not enforced end-to-end | **PRODUCTION_RISK** | robotics revalidator + DA `EXPIRED` cover it today | Preserve fail-closed freshness in any consolidation |
| R11 | P1 | **Incompatible result enums** across framings (`ActionDecision` vs `CloudRecommendation` vs disposition vs `ActionGovernanceOutcome`) | **PREREQUISITE** | `PUBLIC_API_INVENTORY.md` | Map to one status enum in the contract family |
| R12 | P1 | **Target-specific logic leaking into the core** | **PRODUCTION_RISK** | today correctly in adapters (`cloud/constraints.py`) | Keep target checks in adapters; core stays neutral |
| R13 | P1 | **Fail-open paths** | **PRODUCTION_RISK** | none found — fail-closed is pervasive | Add fail-closed tests to the package suite |
| R14 | P2 | **External signal trust** — ACP trusting unverified operational signals | **PILOT_RISK** | signals injected by adapters | Define signal-provenance contracts (`SIGNAL_OWNERSHIP_MATRIX.md`) |
| R15 | P2 | **Dependency inversion** | **FUTURE_ENHANCEMENT** | none present (clean leaf) | Add layered dependency rules to the package |
| R16 | P2 | **Live-clock nondeterminism** | **FUTURE_ENHANCEMENT** | none in core (injected time; `perf_counter` telemetry only) | Keep injected-time discipline |
| R17 | P2 | **Missing controls** (actor identity, credentials, incidents, duplicate dispatch) | **FUTURE_ENHANCEMENT** | `MATURITY_ASSESSMENT.md` | Add as received-signal adapters, not owned systems |
| R18 | P2 | **Acronym collision** (`ACP/` vs `acp/`; robotics vs console "Autonomous Control Plane") | **FUTURE_ENHANCEMENT** | `TERMINOLOGY_AND_SCOPE.md` | Name the product distinctly; update terminology rules |

## Blocker summary

Three **MIGRATION_BLOCKER** risks (R1 authority ambiguity, R2 no stable contract, R3 no single core) plus
one **PREREQUISITE** freeze risk (R5) are individually sufficient to justify **do not package now**. None is
a code defect — the code is clean and fail-closed — they are product-definition and architecture-resolution
gaps.
