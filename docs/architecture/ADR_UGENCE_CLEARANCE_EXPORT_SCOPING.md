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

## 7 — Proposed ruling CE-1 to CE-5 (five decisions, recommended option first; ruled in §10)

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

> **Corrected 2026-09-06 by §11.** The paragraph below offered implementation two
> paths and called the choice between them an implementation consequence. One of the
> two paths does not exist: no allowlisted package can relay a clearance receipt. The
> claim is left in place because it is what the ballot was ruled against; §11 records
> what implementation actually found, and §12 puts the resulting decisions.

`ugence_action_clearance` is **not** on the studio's SD-1 public-entry-point
allowlist `[V]`. Whatever CE-2 and CE-5 rule, the export seam requires either that
allowlist entry or a relay through a package that already has one. That is an
implementation consequence of the ruling, not a sixth decision — but it is the reason
this seam is not a small change, and it is named here so the estimate is honest.

## 10 — Ruling CE-1 to CE-5 (owner, 2026-09-06)

The recommended option is ratified in every case.

| # | Ruling |
|---|---|
| **CE-1** | **`RECEIVED_CLEARANCE_ONLY`.** The exported artifact carries a `ClearanceReceiptBody` the deployment **received**, never one the studio minted and never a compile result. Exporting is not clearing: compilation establishes what was compiled, a clearance establishes whether a consequential action may proceed now and until when. The two semantics stay separate in the artifact and in the routes that produce them. |
| **CE-2** | **`NEW_CONTRACTS_ONLY_PACKAGE`.** `packages/integration/clearance-export`, a record type plus a pure verifier function, on the shape seams 5, 8 and 9 proved: no store, no adapter, no connector, no clock, no network. `action-clearance` is not extended — its receipt body is the evaluator partition's projection and gains no serialization or transport concern. |
| **CE-3** | **`ONE_MEMBER_NOW`.** `identity_assurance` is an enum with the single member `PRESENTED_UNPROVEN`, on the `SystemBindingAuthenticityStatus` precedent (`system_identity.py:217`, whose docstring records that an authority-verified member is deliberately absent until a ratified verifier exists). `VERIFIED` is admitted only by a further ruling, once an enterprise issuer exists (AI-E). No consumer is offered a value nothing in this repository can set, and no producer is tempted to set one. |
| **CE-4** | **`INTEGRITY_ONLY_AND_SAY_SO`.** The artifact is content-addressed and self-describing about what a consumer can and cannot check. It carries an explicit `authenticity: UNSIGNED` and names the unfed prerequisite: a `TrustAnchorResolverPort` exists in `trusted-evidence-authority` and no signing key or trust root is configured. Content-addressing establishes integrity, never authenticity, and the artifact must not imply otherwise. |
| **CE-5** | **`EXPORT_IS_A_READ`.** One v2 read operation returns the artifact for a clearance the deployment already holds. No write, no new egress destination, no credential, and no route that mints, signs, approves or clears. |

**What the ruling authorizes.** Documentation only. No package is created, no route
exists, no contract byte moves and no code changes. The export seam activates by its
own implementation prompt, after the console packaging implementation CP-1 to CP-5
authorized. `LIVE` stays absent from `SIMULATION_MODES`, `ENFORCEMENT_ENABLED` stays
`False` in all eleven packages that declare it, no credential is introduced, and the
frozen v1 and v2 contracts, every `FROM` line and ratified digest, SD-2, FD-8.1,
FD-8.4 and `REFERENCE_GRADE_SHADOW_ONLY` are preserved.

**The prerequisite this ruling does not remove.** §9 stands: `ugence_action_clearance`
is not on the studio's SD-1 allowlist, so the implementation step must add that entry
or relay through a package that has one. That is the reason this seam is larger than
seams 8 and 9, and the ruling does not make it smaller.

## 11 — What implementation found, and why it stopped (2026-09-06)

Implementation of CE-1 to CE-5 began from `9724fc97` and stopped before writing a
file. CE-1 to CE-4 are implementable as ruled: the record type, the one-member
`identity_assurance`, the explicit `authenticity: UNSIGNED` and the pure verifier are
all determined, and `ClearanceReceiptBody` (`action-clearance/.../models/result.py:73`,
sixteen fields, content-addressed) is the spine §2 describes. Both blockers are in
CE-5's seam, and each falsifies a premise the ballot was ruled on.

### 11.1 — The relay §9 assumed does not exist `[V]`

§9's either/or holds only if some allowlisted package can relay a receipt. None can.
The SD-1 allowlist is `apps/ugence-governance-studio/backend/tests/test_architecture.py:69-113`
and contains exactly ten packages: `ugence_agent_workforce_composer`,
`ugence_policy_workflow_compiler`, `ugence_agent_constitution_activation`,
`ugence_agent_constitution_policy`, `ugence_policy_authority`,
`ugence_decision_authority`, `ugence_agent_runtime`, `ugence_ai_system_registry`,
`ugence_data_use_admission`, `ugence_vendor_dependency`.

Not one re-exports `ClearanceReceiptBody`, a receipt read, or anything from
`ugence_action_clearance`. The single occurrence of the namespace across all ten is
`policy-workflow-compiler/.../compiler/capability_registry.py:87`, where
`public_contract="ugence_action_clearance.api"` is a **registry string** naming a
canonical surface — a catalogue entry, not an import and not a relay.

So the second path is empty, and CE-5's seam requires a **new SD-1 entry**. SD-1 is
itself an owner ruling — "the studio backend boundary widens ONLY through an explicit
per-package allowlist" — enforced by
`test_every_governance_import_is_an_allowlisted_public_entry_point` and
`test_no_package_outside_the_allowlist_is_imported`. Widening it is an owner act, and
which package receives the entry decides what the studio can reach for good.

### 11.2 — The deployment holds no clearance, and has no way to hold one `[V]`

CE-5 returns "the artifact for a clearance the deployment already holds". It holds
none, and no path in the repository leads to it holding one:

| Route to a held clearance | State |
|---|---|
| the studio mints one | closed — `/v1/actions/clear` is unserved under CP-3, and CE-1 forbids minting anyway |
| a receipt store is wired in | absent — `ugence_execution_reservation`, the only package that persists a received body (`receipts.py:160` `ClearanceReceipt`, `:300` `ClearanceReceiptRepository`, `sqlite.py:219`), has **zero** references in the studio backend or the P3E deployment |
| a v2 operation receives one | absent — none of the 25 approved v2 operations is clearance-shaped |
| the deployment receives one | absent — none of the 18 deployment modules names a clearance or a receipt |
| synthetic fixtures supply one | absent — `synthetic.py:135` `enforce` **verifies** a pinned hashed manifest; it seeds no store |

Implemented exactly as ruled, CE-5's read can only ever answer "not found". Making it
answer anything requires a receipt to enter the deployment first — and every way of
doing that is a write, which CE-5 forbids in terms.

## 12 — Proposed ballot CE-6 and CE-7 (two decisions, recommended option first)

Not ruled. These are the two decisions §11 forces; no third is proposed, and neither
reopens CE-1 to CE-4.

| # | Decision | Options |
|---|---|---|
| **CE-6** | Which package gets the new SD-1 entry | **`ONE_ENTRY_EXPORT_PACKAGE`**: add only `ugence_clearance_export`, the contracts-only package CE-2 creates. `TWO_ENTRIES`: also admit `ugence_execution_reservation` so the studio reads the receipt store directly. `ENTRY_FOR_ACTION_CLEARANCE`: admit the evaluator package itself. |
| **CE-7** | Where a held clearance comes from | **`SYNTHETIC_SEEDED_RECEIPTS`**: the deployment seeds a receipt store from pinned fixtures under the existing `SYNTHETIC_DEMONSTRATION_ONLY` manifest discipline; no route writes and CE-5's read stays a read. `RULED_INTAKE`: a separate ruling admits one receipt-intake write. `NO_SEAM_YET`: ship the CE-2 package now and defer the route. |

**CE-6 — why `ONE_ENTRY_EXPORT_PACKAGE`.** It is the smallest widening that can work,
and it is the shape the front door already ratified twice: FD-12 and FD-13 admitted
`ugence_data_use_admission` and `ugence_vendor_dependency` on exactly these terms — one
contracts-only package, one curated public surface, nothing reached behind it. Under
it the studio never imports `ugence_action_clearance` or `ugence_execution_reservation`,
so neither a clearance evaluator nor a receipt store becomes reachable from the studio
process, by design or by accident. `TWO_ENTRIES` puts a persistence surface inside the
studio's boundary to save one indirection, which is the trade SD-1 exists to refuse.
`ENTRY_FOR_ACTION_CLEARANCE` is the option CE-2 already declined at the package level,
and admitting the evaluator to the studio would make it harder, not easier, to keep
CE-1's "received, never minted" true.

**CE-7 — why `SYNTHETIC_SEEDED_RECEIPTS`, and what it does not prove.** It is the only
option that leaves CE-5 intact: no write, no intake route, no new egress destination,
no credential. It also stays inside a boundary the deployment already ratified rather
than opening a new one — `synthetic.py` already fails closed unless fixtures match a
pinned hash and carry `SYNTHETIC_DEMONSTRATION_ONLY`, so a seeded receipt inherits that
discipline instead of needing its own. `RULED_INTAKE` contradicts CE-5 as ruled and
would require reopening it. `NO_SEAM_YET` is the option CE-5 refused, and shipping a
record type with nothing that returns it leaves the export path unexercised — the
failure mode this programme has repeatedly paid for.

The honest limit, which the artifact must carry rather than the reader infer: **a
seeded receipt exercises the export path and the verifier; it is evidence about
serialization and integrity, and evidence about nothing else.** It is not a clearance
any authority granted, it confers no approval, and it says nothing about whether the
platform can produce a real one — which it currently cannot, per §11.2. An export of a
synthetic receipt must be labelled `SYNTHETIC_DEMONSTRATION_ONLY` in the artifact
itself, alongside the `authenticity: UNSIGNED` CE-4 already requires and the
`PRESENTED_UNPROVEN` ceiling CE-3 makes travel.

**What ratifying CE-6 and CE-7 would not authorize.** Everything §8 excludes stays
excluded. `LIVE` stays absent from `SIMULATION_MODES`, `ENFORCEMENT_ENABLED` stays
`False`, no credential is introduced, no clearance is minted in the studio, no second
egress destination appears, no authenticity is claimed, and the frozen v1 and v2
contracts, every `FROM` line and ratified digest, SD-2, FD-8.1, FD-8.4 and
`REFERENCE_GRADE_SHADOW_ONLY` are preserved.

## 13 — Ruling CE-6 and CE-7 (owner, 2026-09-06)

The recommended option is ratified in both cases.

| # | Ruling |
|---|---|
| **CE-6** | **`ONE_ENTRY_EXPORT_PACKAGE`.** The SD-1 public-entry-point allowlist gains exactly one entry: `ugence_clearance_export`, the contracts-only package CE-2 creates, reached through its curated public surface and nothing behind it — the shape FD-12 and FD-13 already ratified for `ugence_data_use_admission` and `ugence_vendor_dependency`. The studio imports neither `ugence_action_clearance` nor `ugence_execution_reservation`, so neither a clearance evaluator nor a receipt store becomes reachable from the studio process. `TWO_ENTRIES` and `ENTRY_FOR_ACTION_CLEARANCE` are refused. |
| **CE-7** | **`SYNTHETIC_SEEDED_RECEIPTS`.** The deployment seeds a receipt store from pinned fixtures under the existing `SYNTHETIC_DEMONSTRATION_ONLY` manifest discipline, which fails closed unless fixtures match a pinned hash (`synthetic.py:135`). No route writes; CE-5's read stays a read. `RULED_INTAKE` is refused because it contradicts CE-5 as ruled; `NO_SEAM_YET` is refused because it leaves the export path unexercised, which is the failure this programme has repeatedly paid for. |

### 13.1 — What a seeded receipt is evidence of, and what it is not

A seeded receipt exercises the **export path and the verifier**. It is evidence about
serialization and integrity, and about nothing else. No authority granted it, it
confers no approval, it satisfies no obligation, and it says nothing about whether the
platform can produce a real clearance — which, per §11.2, it currently cannot.

The artifact must therefore carry **`SYNTHETIC_DEMONSTRATION_ONLY`** as a field of the
exported record, alongside the `authenticity: UNSIGNED` CE-4 requires and the
`PRESENTED_UNPROVEN` identity assurance CE-3 makes travel. Three separate honesty
claims, none of which may be inferred from the absence of another, and none of which
an implementation may omit because a consumer "would know". A synthetic export that
reached an external runtime unlabelled would be the precise failure CE-4 exists to
prevent, in a different coat.

### 13.2 — What this ruling authorizes

The implementation prompt for CE-1 to CE-7 may now proceed. Specifically:

- `packages/integration/clearance-export`, contracts-only: the artifact record type,
  the `identity_assurance` enum with its single member, the `authenticity` and
  synthetic-classification fields, one read-only Protocol, refusal reasons, and a pure
  verifier function. No store, no adapter, no connector, no clock, no network.
- **One** new line in the SD-1 allowlist
  (`apps/ugence-governance-studio/backend/tests/test_architecture.py`), for
  `ugence_clearance_export` and no other package.
- One v2 read operation, as CE-5 ruled, and the contract amendment that admits it.
- Deployment seeding of a receipt store from pinned synthetic fixtures, inside the
  existing manifest discipline rather than beside it.

### 13.3 — What this ruling does not authorize

Everything §8 excludes stays excluded, and nothing here reopens CE-1 to CE-5. `LIVE`
stays absent from `SIMULATION_MODES`; `ENFORCEMENT_ENABLED` stays `False` in all eleven
packages that declare it; no credential is introduced; no clearance is minted in the
studio; no second egress destination appears; no authenticity is claimed; and the
frozen v1 and v2 contracts, every `FROM` line and ratified digest, SD-2, FD-8.1, FD-8.4
and `REFERENCE_GRADE_SHADOW_ONLY` are all preserved.

Three further exclusions follow from CE-6 and CE-7 specifically:

- **No second SD-1 entry.** Admitting `ugence_execution_reservation` or
  `ugence_action_clearance` later is a new owner decision, not a follow-on from this
  one. An implementation that finds it needs one stops and reports.
- **No write on the export path.** CE-5's read stays a read; seeding is deployment
  composition, not a route, and no operation may accept a receipt.
- **No promotion of a synthetic receipt.** Nothing may strip, default, or condition
  away the `SYNTHETIC_DEMONSTRATION_ONLY` label, and no later ruling is implied by its
  presence.

## 14 — Implementation record (2026-09-06)

Shipped as `ugence-clearance-export` 0.1.0, studio contract amendment v2-A6, and
`governance-studio-deployment` 0.11.0. What each ruling became:

| # | Implementation | Checked by |
|---|---|---|
| CE-1 | `build_export` accepts only a `ClearanceReceiptBody`; the reconstruction path refuses the four compile-shaped keys outright. | `test_boundaries.py` (CE-1 group) |
| CE-2 | `packages/integration/clearance-export`: a record type, three enums, refusal reasons, pure selectors, one read-only Protocol, one pure verifier. One declared dependency, `ugence-action-clearance`. No store, adapter, connector, clock or network — enforced by an import ban, not by prose. | `test_boundaries.py`; distribution proofs 1–2 |
| CE-3 | `IdentityAssurance.PRESENTED_UNPROVEN`, single member. | `test_honesty_labels.py`; distribution proof 3 |
| CE-4 | `ExportAuthenticity.UNSIGNED`, single member, with `AUTHENTICITY_PREREQUISITE` fixed text in the artifact. `verify_export` returns a report naming four unestablished things and `confers = NOTHING`. | `test_verifier.py`; distribution proof 3 |
| CE-5 | One v2 read, `GET /api/v2/exports/{receipt_id}` (`v2_export_read`), amendment v2-A6. The port has two reads and no write; the service surface is `{CAPABILITY, read}`; every other method on the prefix answers 405. | `test_clearance_export_seam.py` (both suites); distribution proof 4 |
| CE-6 | Exactly one SD-1 line, for `ugence_clearance_export`. Neither `ugence_action_clearance` nor `ugence_execution_reservation` is allowlisted, and the studio's own source imports neither. | `test_clearance_export_seam.py` asserts the allowlist **count**, not just the entry |
| CE-7 | `clearance_receipts.json` inside the scenario directories the pinned synthetic manifest already hashes; read once at composition time by `SeededClearanceSource`. | P3E `test_clearance_export_seam.py`, including a test that an edited receipt fails `verify_bundle` |

### 14.1 — Three decisions the rulings forced, recorded rather than made quietly

**The route is named `exports`, not `clearances`.** SD-2 is enforced by a test that
scans every v2 operation id *and path* for seven prohibited verbs, one of which is
`clear`. That ratchet was not loosened to make room for a name: the operation exports,
it does not clear, so `exports` is both the accurate word and the one that leaves the
guard exactly as it was.

**A foreign tenant's seeded receipt is skipped, never rebound.** The tenant is part of
what a receipt says and part of its fingerprint, so rewriting it at load time would
forge a clearance for a tenant nobody evaluated one for. A deployment whose tenant
matches no shipped receipt holds none, and the studio says exactly that.

**The frontend allowlist stays at twenty-five operations.** CE-5 ruled one server-side
read and no screen. The generated client carries the twenty-sixth operation because it
is generated from the contract, but the frontend consumes nothing new, so the
browser-reachable surface is unchanged. Approving it in
`security/approved-v2-api-operations.json` would widen the frontend boundary without a
ruling that asked for it; the manifest records why it is absent.

### 14.2 — Verified against the built artifact

`scripts/verify_clearance_export_distribution.py` builds the wheel, installs it into a
clean `--no-index` virtual environment with only its one declared dependency, and
interrogates the installed package — including the proof no source test can make: that
withholding `ugence-action-clearance` makes the install **fail**. Twenty-two checks,
all passing, run in CI by the `clearance-export-distribution` job.

### 14.3 — What is still absent

The deployment still holds no clearance any authority granted, and this seam does not
change that: §11.2 stands. What ships is the export path, its verifier, and honest
labelling of what a seeded receipt is worth. A real clearance needs a producer, and a
producer needs the rulings §11.2 named — none of which this implementation anticipates.
