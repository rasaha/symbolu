# Governed Diff-Driven Review (P3A)

The structural diff already knows when a change is approval-sensitive, and the pack
already declares who must approve. P3A connects the two: it derives a **routed
review requirement** from a change, and verifies a **ledger** of reviewer
dispositions against it. It routes and records a human review; it never performs,
grants or waives one.

## Ratified postures

| Ruling | Value | Meaning |
| --- | --- | --- |
| **P3A-1** | `REVIEW_ENFORCEMENT = BLOCKING` | An unsatisfied requirement refuses compilation with a typed refusal. No minor-change exemption, no approval carry-forward. With no covering approval path, the refusal is `NO_APPROVAL_PATH_FOR_CHANGE` — a reviewer is never defaulted. |
| **P3A-2** | `REVIEWER_IDENTITY = OPAQUE_REFERENCE` | `reviewer_authority_reference` is carried verbatim and never resolved. This package neither imports nor consults an authority directory. |

## The non-weakening invariant

The review gate is **additional** to the approval gate, never a substitute. The two
compose as AND in both directions: a satisfied review cannot rescue a failed
approval, and a valid approval cannot excuse an unsatisfied review. P3A makes
re-review legible and routable — not avoidable.

## Artifacts

All four are **standalone**. None is stored in the policy pack, in a
`HumanApprovalRecord`, or in a compiled release's logical payload — a review
artifact stored inside the pack would change the very digest the review binds to.
This is why `policy_pack.v1`, `workflow_ir.v1` and `workflow_ir.v2` bytes are
unchanged by P3A.

- **`ReviewRequirement`** — what a change obliges: the triggering object ids and
  change types, the declared approval path that must be re-satisfied, its ordered
  steps, its segregation pairs, and both pack digests. Derived, never authored; the
  `requirement_id` is content-addressed, so identical inputs yield an identical id.
- **`ReviewStepRequirement`** — one ordered step, carried from the pack's own
  `ApprovalStep`.
- **`ReviewDisposition`** — one reviewer's action on one step, binding the **new**
  pack digest. That binding is what makes a re-review a re-binding.
- **`ReviewLedger`** — the ordered dispositions for one requirement.

## Routing rules

Routing is read from the pack, never invented. A path covers a change when:

1. the changed object *is* an approval path — it is covered by itself; or
2. the path and the object explicitly reference each other through
   `related_object_ids` (references in this object model are always explicit, so
   this is a lookup, not an inference); or
3. the pack declares exactly one approval path — the only declared route.

When several paths are declared and none references the change, there is no
determinate route, and the requirement refuses with `NO_APPROVAL_PATH_FOR_CHANGE`.

The triggering set is exactly `APPROVAL_SENSITIVE_OBJECT_TYPES` — the same table
that already drives `approval_re_review_required`. Two lists would be two answers to
one question.

## Refusal codes

| Code | Raised when |
| --- | --- |
| `NO_APPROVAL_PATH_FOR_CHANGE` | An approval-sensitive change has no declared covering path |
| `REVIEW_REQUIREMENT_UNSATISFIED` | A required step has no approving disposition |
| `REVIEW_STEP_OUT_OF_ORDER` | Dispositions do not follow the declared step order |
| `SEGREGATION_OF_DUTIES_VIOLATED` | A segregation pair was satisfied by one identity |
| `DISPOSITION_DIGEST_MISMATCH` | A disposition binds a digest other than the reviewed pack's |
| `SELF_REVIEW` | A disposition was authored by the compiler process |
| `LEDGER_REQUIREMENT_MISMATCH` | The ledger addresses a different requirement |
| `UNKNOWN_REVIEW_STEP` | A disposition names a step the requirement does not declare |
| `REQUIREMENT_PACK_MISMATCH` | The requirement describes a different pack than the one compiled |

Every one is a refusal. None is ever emitted below `ERROR`.

## Compile-time enforcement, and its honest limit

`compile_policy_pack(pack, approval, review_requirement=..., review_ledger=...)`
refuses when the requirement is unsatisfied, and refuses a requirement whose
`new_pack_digest` does not describe the pack in hand.

A review requirement is inherently a **two-pack** derivation, and compilation sees
one pack. The compiler therefore blocks on every requirement it is given, but it
cannot know about a prior version it was never shown. Deriving the requirement is
the caller's obligation, exactly as supplying the approval already is. The compiler
attests what it was given; it does not reconstruct history.

## CLI

```bash
ugence-policy-workflow-compiler review-requirements OLD_PACK.json NEW_PACK.json
ugence-policy-workflow-compiler check-review REQUIREMENT.json [LEDGER.json]
```

Both are offline and emit canonical JSON. Each exits non-zero on a refusal.
