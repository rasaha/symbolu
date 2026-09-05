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
row already half-shipped is waiting on something this repository has never given a
package shape. **What, in package terms, is the control plane?**

The AI Control Plane is a *product*, with its own tracked documentation tree and its
own console plan. What wave 3 needs is not that product but the one thing under it
this repository can actually compose today: a root that wires capabilities which
already exist, holds no state of its own beyond the ledger it appends to, and adds
no capability to the count. The sequencing ADR already anticipates exactly that
artifact (line 26-30), which is what settles the shape.

## What the repository already fixed

| Finding | Where |
|---|---|
| Control plane and integration hub are **folded into an existing milestone**, not new packages — twelve such items `[V]` | `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:23` |
| Both wave 3 rows are marked `roadmap`; the wave's one **new package** row is the incident orchestrator, already shipped `[V]` | ibid. `:57`, `:59`, `:58` |
| The sequencing ADR anticipates exactly one physical artifact here: "the control-plane composition root", among up to three packages that may appear **without adding a capability** `[V]` | ibid. `:26-30` |
| One prohibition governs new packages: none may take a noun an existing README or NEXT_PHASES reserves `[V]` | ibid. `:85-86` |
| "AI Control Plane" is disclaimed as **someone else's** territory by three shipped packages `[V]` | `packages/governance-provider-framework/README.md:23`; `packages/capabilities/decision-authority/README.md:16`; `packages/capabilities/model-selection/README.md:102` |
| The composition-root pattern is established and has a worked example: one package, one act, no authority minted `[V]` | `packages/integration/cloud-scaling-envelope-issuance/README.md:3-11` |
| G4's contract half shipped: `AuditReference` points at one entry in one store without unifying, moving or merging any store `[V]` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/audit.py:1-16` (0.5.0) |
| The durable append-only shape to copy — SQLite, hash-linked, tenant-partitioned, tamper-**evident** not tamper-proof — already exists and is explicitly a reference implementation `[V]` | `packages/capabilities/storygraph/src/ugence_storygraph/durable_audit.py:1-16` |
| Seven audit stores exist today: the kernel's `AuditRepository` port, storygraph's durable log, and append-only tables in policy-authority, risk_authority, execution-reservation, approval-workflow and authority-directory `[V]` | `.../contracts/audit.py:9-13` |
| Wave 1's own criterion is stronger than package existence: "every item is a declared seam **with tests already asserting its absence**" `[V]` | `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:75-76` |
| Wave 1 seams all have packages: credential broker (5X), execution reservation (phases E and G), G7/G8 contracts, `SqlitePolicyRegistry`, envelope issuance, 5C admission `[V]` | `packages/integration/cloud-scaling-credential-broker`, `.../execution-reservation`, `.../cloud-scaling-envelope-issuance`, `.../cloud-scaling-action-admission`, `packages/policy-authority/README.md:244` |
| Several of those are **reference-grade** and one is explicitly "shadow-only, not enforcement-ready" `[V]` | `packages/integration/execution-reservation/README.md:3`; `packages/policy-authority/README.md:228` |
| `RiskEvaluationSeam.production(...)` **fails closed on any reference-grade or missing dependency** `[V]`; that the maturity of what a root composes is therefore an operational input rather than a label is an inference from it `[I]` | `packages/risk_authority/README.md:109` |
| The productization roadmap **is** in this repository, and its §3 names exactly what the sequencing ADR attributes to it: an "Evidence & audit service — durable, tamper-evident, replayable records", a "Console — operator UI", and a "Connector framework" `[V]` | `Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md:75-87` |
| Its §4 puts durable tamper-evident audit **and** the console **in v1**, and defers only *additional systems-of-record* connectors — two runtime connectors and one Kubernetes execution-target connector also ship in v1 `[V]` | ibid. `:91-102` |
| "AI Control Plane" is not an unclaimed noun: it names an existing product with its own tracked documentation tree **and a shipped console** `[V]` | `Project_documentation/control_plane/` (104 tracked files); `.../aicp_v3_research/UGENCE_AI_CONTROL_PLANE_PRODUCTIZATION_PLAN.md:23-24`; `ugence_console_api/README.md:1-4` |
| Every package **under `packages/`** that mentions connectors disclaims owning one `[V]` | `packages/integration/ai-system-registry/README.md:18,22,132`; `packages/tooling/policy-workflow-compiler/docs/KNOWN_LIMITATIONS.md:22-25`; `packages/products/procurement/docs/PRODUCT_BOUNDARY.md:31,44` |
| But one connector **does** exist, outside `packages/`: a read-only, fixture-backed GitHub *evidence* connector that "owns no governance authority" and "emits neutral product records, never mutations" `[V]` | `products/code-governance/src/ugence_code_governance/github/__init__.py:1-6` — note root-level `products/` is a **different tree** from `packages/products/`; both exist |
| The console is not a plan: it is built and classified `CANONICAL_IMPLEMENTATION`, and is already "the unified AI Control Plane console" `[V]` | `ugence_console_api/README.md:1-4`; `apps/console/`; `Project_documentation/repository/restructuring/UGENCE_REPOSITORY_RESTRUCTURING_PLAN.md:228,232` |

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | What "wave 1 seams exist" required | **Packages exist with their declared seams closed** — not enforcement-readiness. Reference-grade maturity does not block wave 3, and the maturity of what the root composes is disclosed by each composed package's own README, never restated or upgraded here: a root over reference-grade parts is itself reference-grade. **What is verified here is package existence, not the wave's own criterion** — line 75-76 requires "a declared seam with tests already asserting its absence", and this record cites directories, not test results `[G]`. The gate is therefore ruled met **on this reading of it**, and confirming the per-seam tests is the first task of the implementation slice, not an assumption it may inherit. |
| D-2 | What the artifact is | **A composition root, not a capability.** It wires packages that already exist, mints no authority, owns no domain vocabulary, and adds nothing to the capability count — which is what line 26-30 anticipates, and it is that line, not the noun argument, that settles the shape. **On the name, the prohibition at line 85-86 is not dispositive and this record does not claim it is**: that rule protects a noun an existing README *reserves*, and the three packages cited *disclaim* "AI Control Plane" rather than reserving it — the opposite move `[I]`. The noun is nevertheless unavailable, for a stronger reason: it already names a product with its own tracked documentation tree and its own console plan `[V]`, so a package taking it would collide with that product, not with the three disclaimers. Name: `packages/integration/control-plane-root`, distribution `ugence-control-plane-root` — a root *under* the AI Control Plane, never the thing itself. |
| D-3 | Where the audit-ledger service lives | **Under this root, per D-4 of the sequencing ADR.** The service composes the durable-audit shape (copied from storygraph, never imported, as D-3 of that ADR already ruled for Policy Authority) and mints `AuditReference`s into it. It **unifies no existing store**: the seven stores stay where they are, and G4's contract remains the only thing that correlates them. |
| D-4 | What the root may never own | **No policy, no decision, no envelope, no revocation, no credential, no queue, no clock of its own beyond a single injected instant per act, and no second copy of any vocabulary.** It refuses; it does not decide. Every authority it touches is exercised by the package that already owns it. |
| D-5 | Scope of the first slice | **The audit-ledger service and nothing else.** Not because the rest is unscoped, and not because it is unbuilt: roadmap §3 exists, §4 puts the console and two runtime connectors **in v1**, the console is already shipped and classified `CANONICAL_IMPLEMENTATION`, and a read-only GitHub evidence connector already exists `[V]`. The reason is that the ledger is the only §3 service **with no single owner** — the one that has to be *composed* rather than merely used. The walk below establishes that service by service rather than asserting it. |

## Why the ledger, service by service

Roadmap §3 names six shared services (`UGENCE_PRODUCTIZATION_ROADMAP.md:79-87`). A
root in `packages/integration/` can only compose packages under `packages/`, so the
question for each is: does one already own it, and if not, is it composable here?

| §3 service | Who owns it | Composable by this root? |
|---|---|---|
| Identity & tenancy | The IdP, deliberately. `authority-directory` answers "what may a principal do"; the IdP answers "who is this", and "a role grant never substitutes for that" `[V]` (`packages/integration/authority-directory/README.md:53-60`) | **No** — the owner is outside the repository entirely |
| Policy service | `packages/policy-authority`: "There is exactly **one** Policy Authority in Ugence; this is it" `[V]` (`:5`) | **No need** — a single package already is the service |
| Canonical contract layer | `packages/governance-contracts` — the contracts are the layer `[V]` | **No need** — likewise |
| **Evidence & audit service** | **Nobody.** Seven stores exist and none is the service; G4 gave them a way to be *pointed at* without unifying them `[V]` | **Yes** — this is the one that must be composed |
| Console | `ugence_console_api/` + `apps/console/`, already built and classified `CANONICAL_IMPLEMENTATION` `[V]` | **No** — it is a running service outside `packages/`, and already *the* AI Control Plane console |
| Connector framework | Split: a read-only evidence connector in `products/code-governance`, execution-target connectors being built phase by phase by the cloud-scaling ladder `[V]` | **No** — neither half is a composition of `packages/` members, and the hub question is open (`[R]` below) |

So the ledger is not chosen because it is the most valuable §3 service. It is chosen
because it is the only one that is both unowned and composable here — the other five
each fail one of those two tests, for the reasons above.

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

* **D-1's evidence is thinner than wave 1's own criterion** `[G]`. That criterion is
  "a declared seam with tests already asserting its absence" (`:75-76`); what this
  record verified is that a package exists for each item. Confirming the per-seam
  tests is the implementation slice's first task, and if any seam turns out to have
  no such test, D-1 is the ruling to revisit — not something to work around.
* **The integration hub is deferred, but not for want of a plan** `[R]`. Roadmap §4
  ships two runtime connectors and one Kubernetes execution-target connector in v1
  and defers only *additional systems-of-record* connectors. One connector already
  exists — read-only, fixture-backed, evidence-only, in `products/code-governance`
  `[V]` — and the cloud-scaling ladder is building execution-target connectors phase
  by phase without calling itself a hub. Whether the hub is a real gap or an
  already-owned milestone under another name needs the owner's ruling; it is not
  this root's to answer.
* **Two earlier drafts of this record asserted absences that a wider search
  falsified**, and both corrections are recorded here rather than applied silently,
  because D-5's rationale rested on each in turn. The first claimed the
  productization roadmap was absent; it is at
  `Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md`.
  The second claimed no package owns a connector and implied the console was
  unbuilt; `products/code-governance` owns a read-only evidence connector, and
  `ugence_console_api/` is a shipped, classified console. Both came from searching
  `docs/` and `packages/` and treating the result as repository-wide.
  A third review then caught the *fix itself* carrying an unlabelled "the ledger is
  the only §3 service…" — a repository-wide claim checked against none of the other
  five services. It is now the per-service walk above, which shows the reasoning
  instead of asserting it.
  **The methodological point outlives the three facts**: this repository has major
  trees outside `packages/` — `products/` (distinct from `packages/products/`),
  `ugence_console_api/`, `apps/`, `Project_documentation/` — so an absence claimed
  from `packages/` alone is not a repository-wide absence, and no `[V]` or `[G]` in
  any successor record should be granted on that basis.
* This root composes reference-grade packages, so it inherits that maturity `[V]`
  (D-1). Nothing here is production-ready, and no slice of it should be described
  as such.
* Nothing here observes, detects, or notifies. The ledger records what a caller
  already decided to record.
