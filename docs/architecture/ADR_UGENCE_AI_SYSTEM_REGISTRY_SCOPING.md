# Ugence AI system registry — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2, "AI
portfolio registry", line 55) and ruled **contracts-only** by its decision D-5
(line 40): the operational registry and systems-of-record connectors stay post-v1.
It is the last row of wave 2; the other two shipped in PR #1600.

## The question

Which package answers *what AI systems does this organization run, who owns each,
and under what declared classification* — and how does that not become a second
system identity, a second portfolio ledger, or a lifecycle authority? **A
contracts-only registration record over the system identity governance-contracts
already owns.** The registry records; it resolves nothing, gates nothing and
attests to nothing.

## What the repository already fixed

| Finding | Where |
|---|---|
| The identity half already exists: `AssessedSystemBinding` answers "which exact system, at which version, in which configuration" over platform-neutral scalars — `system_id`, `system_version`, `configuration_id`/`configuration_digest`, `system_manifest_ref`/`_digest`, `deployment_environment_ref`, `effective_from`/`_to` `[V]` | `packages/governance-contracts/src/ugence_governance_contracts/contracts/system_identity.py:277-290` |
| That module **explicitly disclaims being this package**: "It is not a system registry, a deployment authority, an attestation service, a verifier, or a policy authority. It grants no permission and mints no authority." `[V]` | same, `:9-11` |
| And it fixes the direction of reuse: engines bind the same identity "rather than minting a parallel one. Consumers re-export it; they never redefine it." `[V]` | same, `:17-18` |
| A binding proves internal consistency and digest-bound identity only — never that the system was deployed, that the configuration digest was computed over the real configuration, or that a manifest ref resolves; `authenticity_status` is permanently unverified `[V]` | same, `:36-45`, `:339` |
| "Portfolio" is already taken, in the orchestration sense: `WorkflowPortfolio` is scheduling metadata that "decides nothing about governance" `[V]` | `packages/runtime/agent-runtime/src/ugence_agent_runtime/orchestration/portfolio.py:1-19`, `:130` |
| RA-7 rejected a competing ledger precisely because it "duplicates the authoritative Agent Runtime portfolio ledger" `[V]` | `docs/architecture/ADR_RISK_AUTHORITY_RA7_RUNTIME_TRAJECTORY_ASSURANCE.md:99` |
| "Registry" is domain-scoped, never exclusive: the Benchmark Registry registers benchmarks; Model Selection's `ExecutableRegistry` tracks model execution-verification for selection `[V]` | `packages/benchmark-registry-authority/README.md:3-5`; `packages/capabilities/model-selection/src/ugence_model_selection/registry.py:19-40` |
| The contracts-first shape has a precedent in this repository: BR-2A shipped "Registry and exact-resolution **contracts**", and BR-2B is explicit that a kernel with "no store, no verifier, no clock, no append path" cannot admit, register, revoke or resolve `[V]` | `packages/benchmark-registry-authority/README.md:49-50` |
| The promotion state machine is wave 4, not this package `[V]` | `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:61` |
| No README or NEXT_PHASES reserves an organizational inventory of AI systems `[G]` | repository-wide search over `README.md` and `NEXT_PHASES.md` |

The sequencing ADR's one prohibition (line 85) is therefore satisfied: the package
takes no reserved noun, provided it is named for what it inventories rather than
for the portfolio sense already in use.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Package, home and name | **`packages/integration/ai-system-registry`, distribution `ugence-ai-system-registry`.** Named for what it inventories. Not "portfolio" — that noun is `WorkflowPortfolio`'s in the runtime, and RA-7 already refused to duplicate that ledger. Not `…Authority` — it decides nothing. |
| D-2 | Risk classification in v1 | **An uninterpreted label.** The package records the classification an administrator declared and reasons about it never. A validated enum would require ratifying a risk taxonomy first, and would make the registry a classifier — a thing that judges rather than records. A refusal reason exists for a blank label, not for an unrecognized one. |
| D-3 | One binding or a lineage | **Exactly one `AssessedSystemBinding` per registration.** A new system version is a **new** registration carrying `supersedes`; the prior one is not edited. This is the digest-binding rule the approval workflow already applies to its subject — a changed system never inherits a standing registration. |
| D-4 | Port surface in v1 | **One read-only `SystemRegistryPort` Protocol and no implementation.** A Protocol is a seam, not an adapter; declaring it lets a composition root type against a stable surface while D-5's line holds, because there is nothing shipped that could cross it. |
| D-5 | Does it gate? | **It records and never gates.** No admission, no approval, no promotion, no eligibility, no resolution. A registration is an input to somebody else's decision. |

## Contracts-only, and how the post-v1 line is held

The package ships record types, refusal reasons and one Protocol. **No store, no
adapter, no connector, no admission engine, no clock.** The line D-5 draws is held
structurally rather than by discipline: there is nothing in the distribution that
could reach a system of record, so "the operational registry stays post-v1" is not
a promise the package could break.

The shape follows BR-2A/BR-2B, which shipped registry contracts and then a kernel
that explicitly "cannot admit, register, revoke or resolve"
(`benchmark-registry-authority/README.md:49-50`).

## The registration record

A `SystemRegistration` binds:

* one `AssessedSystemBinding`, **re-exported from governance-contracts, never
  redefined** — the direction that module itself fixes (`system_identity.py:17-18`);
* an `owner_ref` — a non-secret directory handle, never a credential, and never an
  authenticated identity;
* a declared `classification_label` (D-2), uninterpreted;
* a `Validity` window;
* an optional `supersedes` naming the registration this one replaces (D-3).

**Bounded by `Validity`, evaluated with `status_at(as_of)` at a caller-supplied
instant: a registration outside its window is absent from every answer**, not
reported with a flag — the same rule the authority directory applies to role
grants, and for the same reason. Nothing reads a clock; every instant is a caller
input, and a test asserts it over the AST as both wave 2 packages already do.

## What it inherits, and cannot exceed

A registration cannot prove more than the binding inside it, and that binding
proves neither deployment nor configuration truth (`system_identity.py:36-45`).
So the registry records **what an administrator asserted**, exactly as the
authority directory records what an administrator loaded. It attests nothing about
whether the system exists, runs, or matches its description, and
`authenticity_status` stays permanently unverified. Any stronger claim belongs to
an attestation service that does not exist.

## What it is not

* **Not a portfolio ledger.** It holds no scheduling metadata, no budget, no
  fairness or priority state. `WorkflowPortfolio` in
  `packages/runtime/agent-runtime` remains the only one, and RA-7 keeps reading it.
* **Not a second system identity.** It re-exports `AssessedSystemBinding` and mints
  no parallel spelling.
* **Not a lifecycle authority.** Promotion is wave 4
  (`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:61`); this package never
  promotes, approves or gates.
* **Not a resolver.** It answers no "is this system allowed" question, because it
  ships nothing that can answer anything.

## Dependencies

`ugence-governance-contracts>=0.4.0` and the Python standard library. Nothing else:
no Decision Authority, no Risk Authority, no Policy Authority, no approval
workflow, no authority directory, no agent-runtime, no product, no network client,
no cloud SDK, no pydantic. Composition roots, products and applications may import
it; **no capability package may**. A boundary test asserts the import set over the
AST and the declared dependency list.

## Gaps that survive this package `[G]`

- Nothing here proves organizational truth, deployment, or that a registered system
  is the running one.
- No systems-of-record connector, no discovery, no reconciliation against a CMDB or
  an HR system — all post-v1 under D-5.
- No store, so nothing persists; a composition root holds whatever it registers.
- The risk classification vocabulary is unratified, so the label stays
  uninterpreted (D-2) until an owner fixes a taxonomy.
- The repository still has no test enforcing "no capability package may import it";
  that gap is shared with both wave 2 packages and belongs to a repository-wide
  boundary test.

One prohibition: the package never registers anything *into* a system of record,
never gates, and never attests. A registration is a record, not a permission.

## Next step

Implement `packages/integration/ai-system-registry` 0.1.0 under the decisions above.
