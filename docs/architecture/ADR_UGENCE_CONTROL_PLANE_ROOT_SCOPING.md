# Ugence control-plane root — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 3,
"Governance control plane", line 57). Wave 3's own logic is that it **composes and
mints no authority of its own** (line 81), and this record is the strictest reading
of that sentence: the artifact scoped here is a composition root and nothing else.

## The question

The wave 3 rows assume a control plane. Twelve items were folded into existing
milestones rather than made packages (line 23), the control plane among them, and
the audit-ledger service was placed "under the control plane" (D-4, line 39) — so a
row already half-shipped is waiting on a thing nobody has defined. **What is the
control plane, given that three shipped packages each disclaim the noun?**

It is a composition root: a package that wires capabilities which already exist,
holds no state, and adds no capability to the count. That is the only shape
compatible with what the repository already says about itself.

## What the repository already fixed

| Finding | Where |
|---|---|
| Control plane and integration hub are **folded into an existing milestone**, not new packages — twelve such items `[V]` | `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:23` |
| Both wave 3 rows are marked `roadmap`, unlike the four rows marked **new package** `[V]` | ibid. `:57`, `:59` |
| The sequencing ADR anticipates exactly one physical artifact here: "the control-plane composition root", among up to three packages that may appear **without adding a capability** `[V]` | ibid. `:26-30` |
| One prohibition governs new packages: none may take a noun an existing README or NEXT_PHASES reserves `[V]` | ibid. `:85-86` |
| "AI Control Plane" is disclaimed as **someone else's** territory by three shipped packages `[V]` | `packages/governance-provider-framework/README.md:23`; `packages/capabilities/decision-authority/README.md:16`; `packages/capabilities/model-selection/README.md:102` |
| The composition-root pattern is established and has a worked example: one package, one act, no authority minted `[V]` | `packages/integration/cloud-scaling-envelope-issuance/README.md:3-11` |
| G4's contract half shipped: `AuditReference` points at one entry in one store without unifying, moving or merging any store `[V]` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/audit.py:1-16` (0.5.0) |
| The durable append-only shape to copy — SQLite, hash-linked, tenant-partitioned, tamper-**evident** not tamper-proof — already exists and is explicitly a reference implementation `[V]` | `packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py:1-16` |
| Seven audit stores exist today: the kernel's `AuditRepository` port, storygraph's durable log, and append-only tables in policy-authority, risk_authority, execution-reservation, approval-workflow and authority-directory `[V]` | `.../contracts/audit.py:9-13` |
| Wave 1 seams all have packages: credential broker (5X), execution reservation (phases E and G), G7/G8 contracts, `SqlitePolicyRegistry`, envelope issuance, 5C admission `[V]` | `packages/integration/cloud-scaling-credential-broker`, `.../execution-reservation`, `.../cloud-scaling-envelope-issuance`, `.../cloud-scaling-action-admission`, `packages/policy-authority/README.md:244` |
| Several of those are **reference-grade** and one is explicitly "shadow-only, not enforcement-ready" `[V]` | `packages/integration/execution-reservation/README.md:3`; `packages/policy-authority/README.md:228` |
| Risk Authority does not declare its own maturity in its README; it **fails closed on any reference-grade or missing dependency**, which makes the maturity of what a root composes an operational input rather than a label `[V]` | `packages/risk_authority/README.md:109` |
| The cited authority for both wave 3 roadmap rows — "productization roadmap §3" — **is not in this repository** `[G]` | repository-wide search: the phrase occurs only in the sequencing ADR itself (`:36`, `:40`, `:57`) |
| No package owns connectors; every package that mentions them disclaims them `[G]` | `packages/integration/ai-system-registry/README.md:18,22,132`; `packages/tooling/policy-workflow-compiler/docs/KNOWN_LIMITATIONS.md:22-25`; `packages/products/procurement/docs/PRODUCT_BOUNDARY.md:31,44` |

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | What "wave 1 seams exist" required | **Packages exist with their declared seams closed** — not enforcement-readiness. Reference-grade maturity does not block wave 3. The gate at line 57 is therefore **met**, and the maturity of what the root composes is disclosed by each composed package's own README, never restated or upgraded here. A root over reference-grade parts is itself reference-grade. |
| D-2 | What the artifact is | **A composition root, not a capability.** It wires packages that already exist, mints no authority, owns no domain vocabulary, and adds nothing to the capability count (line 26-30). It may **not** take the "AI Control Plane" noun that `governance-provider-framework`, `decision-authority` and `model-selection` each disclaim — the prohibition at line 85-86 is dispositive. Name: `packages/integration/control-plane-root`, distribution `ugence-control-plane-root`. |
| D-3 | Where the audit-ledger service lives | **Under this root, per D-4 of the sequencing ADR.** The service composes the durable-audit shape (copied from storygraph, never imported, as D-3 of that ADR already ruled for Policy Authority) and mints `AuditReference`s into it. It **unifies no existing store**: the seven stores stay where they are, and G4's contract remains the only thing that correlates them. |
| D-4 | What the root may never own | **No policy, no decision, no envelope, no revocation, no credential, no queue, no clock of its own beyond a single injected instant per act, and no second copy of any vocabulary.** It refuses; it does not decide. Every authority it touches is exercised by the package that already owns it. |
| D-5 | Scope of the first slice | **The audit-ledger service and nothing else.** The console, the shared services of the missing roadmap §3, and the integration hub are **out of scope** and stay unscoped until that roadmap is in-repo (`[G]` above). A root that grew a console would stop being a root. |

## What the root composes

Following the worked example at `cloud-scaling-envelope-issuance`:

| Input | From | What it establishes |
|---|---|---|
| `AuditReference`, `Validity` | governance-contracts 0.5.0 (G4, G8) | the neutral pointer a record cites, and the window it is valid in |
| the durable append-only shape | storygraph `durable_audit` — **copied, never imported** | SQLite, hash-linked, tenant-partitioned, schema-versioned, tamper-evident |
| the one record family that already cites the ledger | `incident-response` — the **only** package carrying `AuditReference` today `[V]` | an incident names where to read what was observed, and holds no store of its own |
| the wave 2 records that do **not** cite it yet | approval-workflow, authority-directory, ai-system-registry — zero `AuditReference` uses between them `[V]` | they shipped before G4 landed, so adopting the reference is **their** future change, not something this root may do on their behalf |

**The act:** append one entry, at one caller-supplied instant, into one tenant's
chain; return the `AuditReference` that names it. Nothing else. The ledger neither
reads the entries back for interpretation nor decides anything about them.

One consequence worth stating, because it bounds the first slice's value: the only
package that would use this on day one is `incident-response`. The three wave 2
packages shipped before G4 and cite no `AuditReference` at all `[V]`, so the ledger
starts with one consumer. That is an argument for keeping the slice small, not for
widening it to create demand.

## The boundary the tests must enforce

The prohibitions above are only real if they are mechanical. The first slice ships
with, at minimum:

* an **import allowlist over the AST** — governance-contracts and stdlib only, with
  every capability package the root composes injected rather than imported, so the
  root cannot acquire an authority by reaching for it;
* a **naming prohibition** — no class named `…Authority`, `…ControlPlane`,
  `Orchestrator`, or `…Console`, and no module named `policy`, `decision`,
  `envelope`, `credential` or `connector`;
* a **no-clock assertion**, as wave 2 and wave 3 already ship: every instant is a
  caller input;
* a **no-second-vocabulary pin** — an exact field-set assertion against the
  contracts it consumes, so the root cannot fork `AuditReference` or `Validity`;
* `scripts/mutation_sweep.py`, copied from `incident-response`, so the coverage
  claim is checkable rather than asserted.

## Gaps stated up front

* The productization roadmap §3 is not in this repository `[G]`. Everything the
  control-plane row promised beyond the audit ledger — shared services, the console
  — is therefore unscopeable, and D-5 defers it rather than guessing.
* The integration hub stays deferred `[G]`. Every package that mentions connectors
  disclaims them, so the hub has no home milestone that plans to build it.
* This root composes reference-grade packages, so it inherits that maturity `[V]`
  (D-1). Nothing here is production-ready, and no slice of it should be described
  as such.
* Nothing here observes, detects, or notifies. The ledger records what a caller
  already decided to record.
