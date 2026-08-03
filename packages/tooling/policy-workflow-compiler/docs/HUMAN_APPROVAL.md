# Human Approval

Human approval (`approval/`) is how a reviewed policy pack becomes eligible for a
compiled release. The compiler records approval as a structured `HumanApprovalRecord`;
it does not itself grant approval.

## The approval record

`HumanApprovalRecord` fields:

| Field | Meaning |
| --- | --- |
| `approval_id` | Unique identifier for the approval. |
| `policy_pack_id` | The pack being approved. |
| `policy_pack_digest` | The pack's structural digest at approval time. |
| `reviewer_id` | The human reviewer. |
| `reviewer_role` | The reviewer's role. |
| `reviewer_authority_reference` | The reviewer's authority basis. |
| `decision` | `APPROVED`, `REJECTED`, or `CHANGES_REQUIRED`. |
| `approved_at` | When the decision was made. |
| `reviewed_gap_ids` | Provenance gaps the reviewer accepted. |
| `accepted_warning_ids` | Warnings the reviewer accepted. |
| `justification` | The reviewer's rationale. |
| `signature_reference` | Reference to the reviewer's signature. |
| `is_fixture` | Whether the record is an offline example fixture. |

## Digest binding

An approval binds to the pack's **structural digest**, which is
**status-independent**. The approval therefore attaches to the substance of the
pack, not to its lifecycle status: moving the pack through lifecycle states does
not change what was approved, and an approval cannot be silently transferred to a
structurally different pack. If the structure changes, the digest changes and the
prior approval no longer matches.

## No self-approval

A compiler process must not approve its own output. An approval whose principal
is the compiler (`COMPILER_PRINCIPAL`) is **rejected**. Approval authority is
reserved for a human reviewer with a recorded role and authority reference. This
preserves the product boundary: the tooling compiles; a human approves.

## Offline example fixtures

Every approval shipped as an example is an **offline fixture** with
`is_fixture=True`. Fixtures illustrate the record shape and the compile flow
without standing in for a real reviewer's sign-off. They require no credentials
and no network, consistent with the package's offline determinism guarantees.

The reviewed-gap and accepted-warning fields are the governed channel through
which a pack carrying `REVIEW_REQUIRED` provenance gaps or warnings can still
proceed — see `VALIDATION_MODEL.md` for how those findings are raised, and
`DETERMINISM.md` for the structural digest the approval binds to.
