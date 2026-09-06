# PWC-P3A — Governed Diff-Driven Review and Approval Binding: Design

**Status:** design. No source change is authorized by this document.
**Scope:** `packages/tooling/policy-workflow-compiler`. First phase in the amended
ratified order (`../policy_workflow_compiler_ratification/RATIFICATION.md`), chosen
to lead because it expands no source contract and so never approaches a frozen
digest.

Findings carry `[V]` verified against the repository, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

## The delta is smaller than it looks

The signals P3A needs already exist. What is missing is routing, and a record.

### What exists today `[V]`

| Capability | Where |
| --- | --- |
| Ten classified change types per object | `diff/structural_diff.py` (`ChangeType`) |
| `approval_re_review_required`, set from a seven-member approval-sensitive object set (decision rule, authority requirement, prohibited condition, action constraint, override rule, exception rule, approval path) | `diff/change_impact.py` (`_APPROVAL_SENSITIVE`) |
| Affected workflow nodes, assurance tests, connector mappings, authority scopes | `diff/change_impact.py::compute_impact` |
| Fail-closed approval gate — no record, pack not `APPROVED`, decision not `APPROVED`, pack-id mismatch, **digest mismatch**, missing reviewer identity or role, self-approval by `COMPILER_PRINCIPAL` | `approval/service.py::ApprovalService.check` |
| Status-independent pack structural digest that approval binds to | `approval/records.py::compute_pack_digest` |
| Declared routing in the pack itself: `ApprovalPath` (`step_ids`, `segregation_pairs`, `owning_capability=DECISION_AUTHORITY`) and `ApprovalStep` (`order`, `authority_requirement_id`, `role_label`, `optional`) | `models/authority.py` |
| Approval-path integrity and segregation-of-duties contradiction checks | `validation/references.py` |

### The four gaps P3A closes `[G]`

1. `approval_re_review_required` is a single boolean. It never says **which**
   declared approval path must be re-satisfied, nor which changes forced it.
2. Nothing derives a routed review requirement from the pack's own `ApprovalPath`
   declarations — the routing is declared in the model and unused by the gate.
3. Nothing records that a re-review **happened**. The only re-binding today is
   implicit: a later approval whose digest happens to match.
4. Between "the pack changed" and "compilation refused" there is no reviewable
   artifact a human can act on.

P3A supplies the routing and the record. It invents neither the signal nor the
authority.

## The hard constraint, measured

`[V]` `PolicyPack.approval_records` sits **inside** the pack, therefore inside both
`compute_pack_digest` and `_pack_logical`. Three measurements on the procurement
reference:

- The pack carries **zero** approval records. Its approval binds to
  `sha256:28eedf60…`, the digest of the pack without it.
- Embedding that approval into `pack.approval_records` **changes** the pack digest.
  An approval therefore can never be stored in the pack it approves — the reference
  would be self-defeating.
- Adding a single field to `HumanApprovalRecord` moves the digest of any pack that
  carries approval records.

**Consequence, and the guarantee it buys:** P3A adds no field to `PolicyPack`, to
`HumanApprovalRecord`, or to anything reachable from `_pack_logical`. Review
artifacts are standalone computed objects — exactly what `PolicyPackDiff` already is.
Digest invariance is therefore structural, not a matter of careful editing:

| Output | Effect |
| --- | --- |
| `policy_pack.v1` pack digest | unchanged — no pack field added |
| `workflow_ir.v1` release digest | unchanged — `sha256:fb9fd4b9…` |
| `workflow_ir.v1` IR digest | unchanged — `sha256:169ad24c…` |
| `workflow_ir.v2` fingerprint | unchanged — `sha256:2e031c78…` |
| Existing approvals | still valid — `HumanApprovalRecord` gains no field |

## The model — a new `review/` subpackage

**`ReviewRequirement`** — derived, never authored. Carries `requirement_id`,
`old_pack_digest`, `new_pack_digest`, the triggering object ids and change types
taken from the diff, the `required_approval_path_id`, the ordered required steps
carried from the pack's own `ApprovalStep` declarations (`order`,
`authority_requirement_id`, `role_label`, `optional`), and the path's
`segregation_pairs`.

Where the pack declares no approval path covering a changed object, that is a
diagnostic — never a defaulted reviewer. This mirrors the P2 rule that a value the
source policy does not declare is unresolved, never fabricated.

**`ReviewDisposition`** — one reviewer's action on one step, each binding
`new_pack_digest` explicitly.

**`ReviewLedger`** — the ordered dispositions for one requirement. This is the
re-binding evidence: it demonstrates the review was performed **against the changed
pack**, rather than carried over from an earlier one.

**`ReviewRouter`** — `derive_review_requirement(old_pack, new_pack)`, deterministic
and provenance-backed, computed from the existing diff.

**`ReviewGate`** — verifies a ledger satisfies a requirement: every non-optional step
satisfied in declared order, segregation pairs held by distinct identities, no
disposition authored by `COMPILER_PRINCIPAL`, and every disposition bound to
`new_pack_digest`.

## The non-weakening invariant `[R]`

**P3A must never make an approval valid that today's gate would reject.**

The composition is AND: `ApprovalService.check()` runs unchanged, and `ReviewGate`
adds a second condition when a requirement exists. There is no "minor change"
exemption, no carry-forward of a prior approval past a digest change, and no path by
which routing information relaxes the digest binding.

This needs explicit ratification because the natural reading of "governed review
workflow" — *let small changes reuse the existing approval* — is precisely the
weakening the current gate exists to prevent. P3A makes re-review **legible and
routable**; it does not make it **avoidable**.

## Fail-closed codes

All structural, all refusals:

```text
NO_APPROVAL_PATH_FOR_CHANGE      an approval-sensitive change with no declared covering path
REVIEW_REQUIREMENT_UNSATISFIED   a required step has no disposition
REVIEW_STEP_OUT_OF_ORDER         dispositions do not follow declared step order
SEGREGATION_OF_DUTIES_VIOLATED   a segregation pair satisfied by one identity
DISPOSITION_DIGEST_MISMATCH      a disposition bound to a digest other than new_pack_digest
SELF_REVIEW                      a disposition authored by COMPILER_PRINCIPAL
```

## Surface

Public API additions: `ReviewRequirement`, `ReviewDisposition`, `ReviewLedger`,
`ReviewRouter`, `ReviewGate`, `derive_review_requirement`, `check_review`, and the
code enum — roughly **105 → 113** names. `artifacts/public_api.json` is regenerated
and the existing freeze check gates the change, as it does for every surface
widening.

CLI additions, both offline and JSON-emitting like `diff`:

```text
review-requirements OLD_PACK NEW_PACK
check-review REQUIREMENT LEDGER
```

Maturity: a new `diff_driven_review_implemented` gate reports the phase honestly.
No existing boolean changes; `runtime_deployment_implemented`,
`runtime_execution_implemented`, `pilot_validated` and `production_certified` stay
`false`.

## Boundary

P3A adds no provider import, no runtime call, no credential, no network access and
no side effect. It routes a human review and records its disposition; it never
performs, grants, or waives an approval. The compiler still does not approve its own
output.

## Open items

`[R]` **Blocking or advisory.** Whether an unsatisfied `ReviewRequirement` refuses
compilation or merely reports. Recommendation: refuse whenever the pack declares a
covering path. Fail-closed is the house rule, and an advisory review gate is one a
pipeline learns to ignore.

`[R]` **Reviewer identity resolution.** Dispositions carry reference strings today,
consistent with the existing `reviewer_authority_reference`. Whether P3A should
instead resolve identities against `packages/integration/authority-directory` is a
boundary question: resolving would add a first-party dependency that the D1 ruling
would have to permit, and would move this package off its current
zero-Ugence-dependency posture.
