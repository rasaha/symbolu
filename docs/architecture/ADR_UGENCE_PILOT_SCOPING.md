# Ugence pilot scoping — audit

**Status:** audit, 2026-09-06. Documentation only: this record amends no package,
port, test, manifest or deployment artifact, activates no seam, and moves no
contract byte. It proposes one ruling ballot, PI-1 to PI-4, for the owner.

Ordered after clearance export shipped (CE-1 to CE-7, `ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md`
§14). Evidence labels: `[V]` verified against this repository at `cd759a6b9`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question, and the answer

Which one real cross-platform workflow should prove that an independent clearance
and evidence layer is valuable?

**The workflow already exists, it already produces real clearances, and it is not
the studio's.** `products/code-governance` 0.5.0 (MVP 1F) governs source-control
changes, calls the canonical `evaluate_clearance` in shipped source, and carries
its own stage-gate standard naming exactly what a pilot needs `[V]`. The pilot is
**not blocked on code**. It is blocked on three owner inputs that document names
and nobody has supplied.

The gap this audit adds is different from the one it went looking for: the real
clearance producer and the export seam **cannot see each other**, and the export
package would refuse a real clearance if they could.

## 2 — What the studio can already define, review and explain `[V]`

Twenty-six approved v2 operations across nine screens. End to end, unaided, the
studio covers:

| Stage | Operations |
|---|---|
| define | `v2_constitution_validate`, `v2_constitution_preflight`, `v2_policy_validate`, `v2_policy_synthesize`, `v2_policy_compile` |
| register the subject | `v2_registry_register`/`_list`, `v2_data_use_declare`/`_list`, `v2_vendor_declare`/`_list` |
| review | `v2_review_list_queue`, `v2_review_read_run`, `v2_review_read_run_events`, `v2_review_read_approval`, `v2_review_submit_decision`, `v2_review_start_shadow_run` |
| explain | `v2_authority_list_policies`, `v2_authority_read_policy`, `v2_authority_read_decision`, `v2_observe_audit_ids`, `v2_observe_audit_chain`, `v2_observe_ledger_chain`, `v2_simulate_run`, `v2_publish_shadow` |
| export | `v2_export_read` |

`policy.compile` produces `logical_digest` and `workflow_ir` (`studio_v2.py:319,321`).
So the studio can define a governed workflow, review a shadow run of it, explain
the decision chain, and export a clearance — **provided a clearance exists**.

## 3 — What an external runtime receives today, and what it can do `[V]`

One `ClearanceExportArtifact`: a received `ClearanceReceiptBody` carried
unaltered (sixteen fields), content-addressed as `cxp_` + fingerprint, plus
`identity_assurance: PRESENTED_UNPROVEN`, `authenticity: UNSIGNED` with the unfed
trust-anchor prerequisite named, and `data_classification:
SYNTHETIC_DEMONSTRATION_ONLY`.

What it can do with it: **recompute the fingerprint and detect any alteration,
including a stripped label.** That is the whole of it, and `verify_export` says so
— it returns a report, not a boolean, and `confers` answers `NOTHING`.

What it cannot do: treat it as a grant. The classification is not decoration; the
package **refuses to build an artifact carrying any other value** (`ClassificationClaimRefused`).
Today every export the platform can produce is, correctly, demonstration data.

## 4 — Which of the four unestablished things block a pilot `[I]`

`verify_export` names four. Whether each blocks depends entirely on whether the
pilot confers anything, and a shadow pilot confers nothing.

| Unestablished | Blocks a bounded shadow pilot? | Why |
|---|---|---|
| `AUTHENTICITY_NOT_ESTABLISHED` | **No** | In a bounded pilot the parties are known and the transport is authenticated. The channel authenticates; the artifact need not. It blocks *unbounded distribution*, where a recipient has no other basis for trusting the producer. |
| `POLICY_IN_FORCE_NOT_CHECKABLE` | **No** | A single-deployment pilot resolves `policy_refs` against the deployment that produced them. It blocks a *multi-deployment* or cross-tenant pilot. |
| `DECLARER_IDENTITY_NOT_VERIFIED` | **No, but it caps the claim** | Every upstream declarer is `PRESENTED_UNPROVEN`. A pilot may still measure whether the *chain* is reconstructable and useful; it may not conclude anything about who asserted what. |
| `APPROVAL_NOT_PROVEN` | **No for shadow, yes for enforcement** | `authorization_ref` is a reference. Acting on it is exactly what enforcement means, and Code Governance's own standard blocks enforcement behind three further gates. |

**None of the four blocks a bounded shadow pilot.** All four block enforcement, and
the two that block distribution beyond one deployment (authenticity, policy-in-force)
are the ones a *second* pilot would have to close.

## 5 — The shortest path to a clearance an authority granted `[V]`

Code Governance already produces one. `api.py:556` calls `evaluate_clearance` on a
request built from real evidence, and `ClearanceReceiptBody.from_result` (`result.py:105`)
projects any such result into exactly the body the export artifact carries. **The
code distance is one function call.**

The governance distance is not:

| Step | State |
|---|---|
| a real `ClearanceResult` exists | **yes** `[V]` — Code Governance, execution disabled |
| it is projected to a `ClearanceReceiptBody` | **no** `[G]` — zero references in `products/code-governance/src` |
| the deployment holds it | **no** `[G]` — the seeded source reads pinned fixtures only |
| the studio may reach the producer | **no** `[G]` — `ugence_code_governance` is on no SD-1 allowlist and in no image |
| the artifact may say it is real | **no** `[G]` — `ExportDataClassification` has one member, and the package refuses any other |

So the path is four ruled steps, not four coding tasks. Each is an owner act:
admitting a producer to the studio's boundary (SD-1, as CE-6 did for the export
package), admitting a second classification member (as CE-3 anticipated for
`VERIFIED`), composing the producer into a deployment, and deciding whether a
Code Governance clearance is the studio's to export at all.

**And none of it is the next step**, because Code Governance's own standard says
the next authorized activity is a bounded internal live GitHub shadow pilot, and
that pilot needs no export at all.

## 6 — The three owner inputs, quoted `[V]`

`CODE_GOVERNANCE_PHASE_READINESS_REQUIREMENTS.md` names them:

> It requires a dedicated read-only GitHub credential, explicit bounded pilot
> authorization, and at least one real human reviewer — none of which has been
> supplied.

The standing verdict is `INSUFFICIENT_LIVE_EVIDENCE`, and the document is explicit
that offline tests, supplied snapshots and mock reviewer feedback are *deliberately
excluded* from the live-evidence classes. **The pilot is blocked on owner inputs,
not on code**, and this audit does not propose implementation that would obscure
that.

Together with the standing mirror blocker, the owner inputs outstanding across the
programme are now five: mirror `registry_host`, `repository_prefix`, `secret_name`;
a read-only GitHub credential; bounded pilot authorization; and one real reviewer.

## 7 — One finding this audit did not go looking for `[G]`

`products/code-governance` has 33 test modules and **is named by no workflow**. The
CI coverage ratchet does not catch it: `check_package_ci_coverage.py:31` scans
`REPO / "packages"` only, so everything under `products/` is invisible to the gate
that exists to stop exactly this. The one component that already produces real
clearances is the one component whose tests nothing runs.

This is not a pilot blocker. It is a reason to distrust "offline-verified" as a
current claim rather than a historical one, and it should be closed before any
pilot leans on that suite.

## 8 — Recommended next step

**Close the CI blind spot, then supply the three inputs.** The ruling below is
small because the pilot decision itself is not an architecture decision — it is a
resourcing one the readiness standard already framed.

## 9 — Proposed ballot PI-1 to PI-4 (four decisions, recommended option first)

| # | Decision | Options |
|---|---|---|
| **PI-1** | The pilot workflow | **`CODE_GOVERNANCE_GITHUB`**: the bounded internal live GitHub shadow pilot Gate 1 already specifies. `NEW_WORKFLOW`: scope a different one (rejects work already at MVP 1F). `DEFER`. |
| **PI-2** | The CI blind spot | **`EXTEND_THE_RATCHET`**: `check_package_ci_coverage.py` scans `products/` as well as `packages/`, and Code Governance gains a workflow. `WORKFLOW_ONLY`: add the workflow, leave the ratchet blind. `EXEMPT`. |
| **PI-3** | Whether export is in pilot scope | **`OUT_OF_SCOPE`**: Gate 1 needs no export; the seam waits. `IN_SCOPE`: admit a producer and a second classification member now (four owner acts, per §5). |
| **PI-4** | What the pilot may claim | **`RECONSTRUCTABILITY_ONLY`**: the pilot measures whether the chain reconstructs and whether reviewers find it useful, and claims nothing about identity or authenticity. `VALUE_CLAIM`: also claim incremental value over existing GitHub and CI controls (which Gate 1 explicitly requires evidence for, not assertion). |

**What ratifying these would not authorize.** No enforcement, no execution
(`EXECUTION_ENABLED` stays `False`), no merge path, no credential in any durable or
reported surface, no second SD-1 entry, no change to CE-1 to CE-7, and no
relaxation of any one-member enum. `LIVE` stays absent from `SIMULATION_MODES` and
`ENFORCEMENT_ENABLED` stays `False` in every package that declares it.
