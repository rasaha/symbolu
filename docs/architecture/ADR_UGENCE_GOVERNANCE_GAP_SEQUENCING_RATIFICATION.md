# Ugence governance-gap sequencing brief and ratification record

**Status:** ratified 2026-09-04 by the repository owner. Read-only for package code:
this record amends no package ADR, port, test or manifest. Each wave below still
needs its own package-level implementation authority before code changes.

## The question

In what order should the eighteen recommendations from the external governance-gap
assessment be built? **Close the seams existing packages already reserve on the
minimum production path first; create a new package only where no package owns the
noun.** Five of the thirteen recommended "new" packages are existing milestones under
other names, so the capability count grows by seven, plus one partial, not thirteen.

## Count

Of the assessment's twenty items (thirteen new packages, seven extensions):

| Disposition | Items | Count |
|---|---|---|
| New capability package | approval workflow, authority directory, portfolio registry (contracts-only), incident orchestrator, privacy and egress, vendor risk, adversarial assurance | 7 |
| Partly new | lifecycle authority: only the promotion state machine is new; Model Selection's `ExecutableRegistry` and the Agent Constitution lifecycle already hold the registries | 1 |
| Folded into an existing milestone | credential broker, execution lease, control plane, audit ledger, integration hub, benchmark authority, Policy Authority persistence, live attestation, signed effects, value attribution, agent-runtime pilot, regulatory obligation mapping | 12 |

Capability count moves from 45 to 52, or 53 if the lifecycle state machine ships
separately. Physical package count may rise by up to three more without adding a
capability, because the cloud-scaling ladder ships one integration package per phase
(5A, 5B-0A and 5B-0B each did `[V]`): a Phase 5X package, the execution ledger that
`NEXT_PHASES.md` names as owner of phase G with no package behind it, and the
control-plane composition root.

## Ratified owner decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Is the Kubernetes infrastructure-agent wedge still v1? | **Yes.** Productization roadmap §4 stands. The Credential Broker is built as cloud-scaling Phase 5X, not as a general-purpose package, and generalizes only after 5D. |
| D-2 | Where does approval-workflow state live? | **In Ugence.** Ugence owns the canonical approval artifact and state machine; ServiceNow and Jira are notification and task mirrors, never the record. Decision Authority 1.0.0 stays frozen and consumes the artifact. |
| D-3 | Policy Authority §15.7 persistence posture | **Adopt D-22 Posture B**: single-node durable persistence on stdlib `sqlite3`, copying the shape of `packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py`, never importing it. Distributed consistency stays disclaimed. |
| D-4 | Home of the unified audit ledger | **Extension, not a new package.** Contract gap G4 lands a neutral `AuditRef`/`EvidenceRef` in governance-contracts; the ledger service composes the durable-audit shape under the control plane. |
| D-5 | Portfolio registry in v1? | **Contracts-only slice in v1**; the operational registry and systems-of-record connectors stay post-v1 per roadmap §4. |

## Recommendation-to-milestone map

Evidence labels: `[V]` verified against the cited file, `[I]` inferred.

| Recommendation | Home | Milestone | Wave |
|---|---|---|---|
| Credential Broker | existing phase ladder | cloud-scaling Phase 5X, `packages/integration/cloud-scaling-authorization-contracts/README.md:225` `[V]` | 1 |
| Execution lease, one-time consumption | existing | Action Clearance phases E and G, `packages/capabilities/action-clearance/docs/NEXT_PHASES.md` `[V]` | 1 |
| Idempotency and expiry contracts | existing | governance-contracts evolution phase, gaps G7 and G8 `[V]` | 1 |
| Durable Policy Authority | existing | ADR_UGENCE_POLICY_AUTHORITY §15.7 under D-3 `[V]` | 1 |
| Envelope issuance, ActionGate admission | existing | Risk Authority Phase 5; cloud-scaling 5B-2 and 5C `[V]` | 1 |
| Human approval and exception workflow | **new package** | feeds Decision Authority under D-2; reuses the Policy Workflow Compiler `HumanApprovalRecord` shape, which records approval but runs no queue or state machine `[V]` | 2 |
| Organizational authority directory | **new package** | consumed by approval workflow and Risk Authority; identity proof stays with the IdP | 2 |
| AI portfolio registry | **new package** | contracts-only slice under D-5 | 2 |
| Unified audit ledger | existing | gap G4 plus durable-audit shape under D-4 `[V]` | 3 |
| Governance control plane | roadmap | productization roadmap §3 shared services and console; no package until wave 1 seams exist `[V]` | 3 |
| Incident and remediation orchestrator | **new package** | extends RA-6 revoke; kill-switch shape from `products/code-governance` pilot_operator; compensation is a new proposal, never automatic rollback `[V]` | 3 |
| Enterprise integration hub | roadmap | roadmap §3 connector framework `[V]` | 3 |
| Data privacy and egress authority | **new package** | contracts first; evaluates data use independently of action authorization | 4 |
| Model, prompt and agent lifecycle authority | existing plus new | Model Selection `ExecutableRegistry` and Agent Constitution lifecycle already cover parts; new package only for the promotion state machine `[I]` | 4 |
| Third-party AI and vendor risk | **new package** | contracts first, linked to Policy Authority | 4 |
| Agent security and adversarial assurance | **new package** | evidence provider to TAP and Risk Authority; never a decision authority | 4 |
| Benchmark Registry Authority operational | existing | BR-2C, BR-2D under D-22, BR-2E `[V]` | 5 |
| Signed external-effect verification | existing | RA-8 successor milestone; Trusted Evidence Authority DD-10b custody `[V]` | 5 |
| Live agent attestation | existing | Agent Constitution Conformance reference-map gap `[V]` | 5 |
| Value baseline and attribution | existing | Governed Value GV-2 evidence and GV-4 authority layers `[V]` | 5 |
| Agent Runtime production validation | existing | README names pilot and production validation as the next step `[V]` | 5 |
| Regulatory obligation mapping | existing | Policy Workflow Compiler extension; not in its `NEXT_PHASES.md`, so it needs a package-level scoping first `[V]` | 4 |
| Maturity ledger | already exists | pipeline document Appendix B; keep it current, add nothing `[V]` | — |
| Research capabilities as controls | no action | research lane stays outside the pilot band `[V]` | — |

## Wave logic

1. **Wave 1** is the A.6 minimum production path. Every item is a declared seam
   with tests already asserting its absence. Order inside the wave: G7/G8
   contracts, then the clearance execution ledger, then Policy Authority
   persistence, then 5B-2, 5C and 5X in ladder order.
2. **Wave 2** starts once the ledger exists, because approvals must consume and be
   consumed atomically.
3. **Wave 3** composes; it mints no authority of its own.
4. **Wave 4** ships contracts before engines, matching the repository's own pattern.
5. **Wave 5** hardens existing packages and never blocks waves 1 to 3.

One prohibition: no new package may be created for a noun that an existing README or
NEXT_PHASES already reserves.

## Next step

Implement gap G7 and G8 as additive contracts in governance-contracts. It is the
smallest unblocked item on the critical path and the execution ledger depends on it.
