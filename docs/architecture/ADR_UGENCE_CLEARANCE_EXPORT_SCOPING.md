# Ugence clearance export — scoping audit

**Status:** audit, 2026-09-06. Documentation only: this record amends no package,
port, test, manifest or deployment artifact, activates no seam, and moves no
contract byte. It proposes one ruling ballot, CE-1 to CE-5, for the owner.

Ordered by the owner after ruling CP-1 to CP-5, deliberately **before** console
packaging implementation, so that a service is not packaged and then immediately
reopened to widen its public API. It inherits CP-3's principle in terms: **a
capability does not become public API because the underlying function exists.**

Evidence labels: `[V]` verified against this repository at `64a6082e`, `[I]`
inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question, and the answer

What is the smallest portable, independently verifiable clearance artifact an
external runtime can consume? **Most of it already exists and is not reachable.**
`ClearanceReceiptBody` is a frozen, content-addressed record carrying eleven of the
bindings such an artifact needs. What is missing is three fields, one identity
ceiling that must travel with the artifact, one verification story, and a seam — and
the seam is the part no ruling can supply cheaply, because the studio cannot reach
the package that owns the receipt.

## 2 — The spine that already exists `[V]`

`packages/capabilities/action-clearance/.../models/result.py:73` —
`ClearanceReceiptBody`, a frozen dataclass, content-addressed by
`result_fingerprint` with `receipt_id = "acr_" + result_fingerprint`:

| Binding the owner asked for | Field present today |
|---|---|
| schema / protocol version | `receipt_version` (`action_clearance.receipt.v1`) |
| clearance identity | `receipt_id`, `result_fingerprint`, `request_id` |
| policy identity | `policy_refs` |
| canonical / digest binding | `request_fingerprint`, `result_fingerprint` |
| approval / authority references | `authorization_ref` |
| subject / action / scope binding | `authorized_action_fingerprint`, `tenant_id` |
| validity / expiry | `evaluated_at`, `valid_until` |
| evidence references | `signal_refs`, `signal_bundle_fingerprint` |
| the decision and its reasons | `clearance_status`, `reason_codes` |
| what the runtime must still honour | `effective_constraints`, `obligations` |

Its own docstring records the partition: "the evaluator-partition projection… It
contains no persistence or lifecycle-mutation behavior." A neutral, immutable body
that something else wraps and persists is exactly the shape a portable artifact
wants.

## 3 — What it lacks `[V]`

Four things, of which only the first three are fields.

- **Workflow identity.** `policy_refs` names policy; nothing names the compiled
  workflow. `policy.compile` produces `logical_digest` and `workflow_ir`
  (`studio_v2.py:295-309`) and neither reaches the receipt `[G]`.
- **Constitution / agent identity.** Absent from the body `[G]`.
- **Identity assurance.** Absent — and this is the load-bearing gap, treated in §5.
- **Cryptographic authenticity.** Content-addressing is not authenticity: a
  fingerprint proves the body was not altered *by someone who cannot recompute it*,
  which is everyone and no one. Nothing signs a receipt `[G]`.

## 4 — Why exporting is not clearing `[V]`

A compile result is not a clearance and must never be serialized as one.
`policy.compile` establishes *what was compiled*, under an approval record the
compiler validates. `ClearanceResult` establishes *whether a consequential action may
proceed now*, with a `valid_until`. The studio's `PolicyService` docstring already
holds the line — "`compile` is the only one that produces a compiled…" release, and
the service never passes `require_approval=False`. An export seam that promoted a
`logical_digest` to a clearance would collapse two different questions into one
artifact, and an external runtime consuming it would be acting on the wrong one.

**The repository cannot currently produce a genuine clearance through the studio
anyway** `[V]`: `/v1/actions/clear` is a console route the studio's frozen allowlist
does not reach, and CP-3 has just ruled that the packaged console will not serve it.
So the first honest export is of a clearance the studio *received*, not one it
*minted*.

## 5 — The identity ceiling must travel `[V]`

The owner's instinct — that `PRESENTED_UNPROVEN` must not evaporate at the
serialization boundary — is right, and the repository has already ruled how to
express it.

`SystemBindingAuthenticityStatus`
(`governance-contracts/.../system_identity.py:217`) is an enum with **exactly one
member**, and its docstring says why: "A second member (an authority-verified status)
is deliberately **absent**: admitting one would require a ratified system-binding
verifier, which no [package provides]."

That is the precedent for `identity_assurance`. The proposed shape is correct; the
ruled way to build it is **one member now** — `PRESENTED_UNPROVEN` — with `VERIFIED`
admitted only when a verifier exists. An enum that offers `VERIFIED` before anything
can produce it invites an external runtime to look for a value the platform can never
set, and invites a producer to set it anyway.

Thirty-three sites across registration, data-use and vendor record declarers as
`PRESENTED_UNPROVEN` today `[V]`. Every one of them is upstream of a clearance.

## 6 — Verification: what an external runtime could actually check `[V]`

The owner's requirement is that the runtime "does not need to trust the Studio HTTP
session that produced it". Today it would have to:

| Check | Available? |
|---|---|
| the body is internally consistent and unaltered | **yes** — recompute `result_fingerprint` |
| the referenced policy exists and is in force | only against the same deployment `[G]` |
| the approval is genuine | `authorization_ref` is a reference, not a proof `[G]` |
| the producer is who it claims | **no** — nothing signs `[G]` |
| the declarers were verified | **no**, permanently, until an issuer exists `[G]` |

A `TrustAnchorResolverPort` exists in `trusted-evidence-authority`, with
`TrustAnchorRecord`, and the studio itself already reports that "no signing key or
trust root exists" (`studio_v2.py:19`) `[V]`. So the resolver contract is present and
unfed. **An honest first export is verifiable for integrity and unverifiable for
authenticity, and must say so in the artifact itself** rather than leaving a consumer
to infer it.

## 7 — Proposed ruling CE-1 to CE-5 (five decisions, recommended option first)

| # | Decision | Options |
|---|---|---|
| **CE-1** | What is exported | **`RECEIVED_CLEARANCE_ONLY`**: the artifact carries a `ClearanceReceiptBody` the studio received, never one it minted, and never a compile result. `COMPILE_RESULT_AS_CLEARANCE` (refused by §4). `BOTH_AS_LABELLED_PARTS`. |
| **CE-2** | Where the type lives | **`NEW_CONTRACTS_ONLY_PACKAGE`**: `packages/integration/clearance-export`, a record type plus a pure verifier function and no store, on the shape seams 5, 8 and 9 proved. `EXTEND_ACTION_CLEARANCE` (would give an evaluator package a serialization concern its docstring disclaims). |
| **CE-3** | Identity assurance | **`ONE_MEMBER_NOW`**: `identity_assurance` is an enum with the single member `PRESENTED_UNPROVEN`, on the `SystemBindingAuthenticityStatus` precedent; `VERIFIED` is admitted only by a further ruling once an issuer exists. `TWO_MEMBERS_NOW`. |
| **CE-4** | Authenticity | **`INTEGRITY_ONLY_AND_SAY_SO`**: the artifact is content-addressed and self-describing about what a consumer can check; it carries an explicit `authenticity: UNSIGNED` and names the trust-anchor resolver as the unfed prerequisite. `SIGN_FIRST` (blocked: no signing key or trust root exists). |
| **CE-5** | The seam | **`EXPORT_IS_A_READ`**: one v2 read operation returning the artifact for a clearance the deployment already holds; no new egress destination, no write, no credential. `FILE_DOWNLOAD_FROM_THE_BROWSER`. `NO_SEAM_YET` (record the type, defer the route). |

## 8 — What a ruling would not authorize

- **LIVE execution, credentials, or `ENFORCEMENT_ENABLED`.** All unchanged; `LIVE`
  stays absent from `SIMULATION_MODES` and `ENFORCEMENT_ENABLED` stays `False` in all
  eleven packages that declare it `[V]`.
- **Minting clearances in the studio.** CE-1 forbids it and CP-3 keeps
  `/v1/actions/clear` unserved.
- **A second egress destination.** FD-8.4 governs that and is untouched.
- **Any claim of authenticity.** CE-4 forbids it until a trust root exists.
- The frozen v1 and v2 contracts, every `FROM` line and ratified digest, and
  `REFERENCE_GRADE_SHADOW_ONLY` are preserved.

## 9 — The prerequisite the ballot cannot decide `[G]`

`ugence_action_clearance` is **not** on the studio's SD-1 public-entry-point
allowlist `[V]`. Whatever CE-2 and CE-5 rule, the export seam requires either that
allowlist entry or a relay through a package that already has one. That is an
implementation consequence of the ruling, not a sixth decision — but it is the reason
this seam is not a small change, and it is named here so the estimate is honest.
