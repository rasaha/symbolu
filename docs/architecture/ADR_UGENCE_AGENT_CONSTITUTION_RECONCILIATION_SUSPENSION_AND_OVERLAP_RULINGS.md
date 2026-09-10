# ADR: Ugence Agent Constitution — documentation reconciliation, suspension implementation authority, governed-role overlap, and the retirement of the pending-work ledger

**Status:** **Accepted (ratified owner declaration).** This ADR records four
rulings made by the repository owner in one sitting on 2026-09-09, over the
capability audit of the five `packages/integration` distributions that opened
that session.

`ACC-DR` is **performed** by the same change set that carries this ADR
(documentation only). `ACC-SUSP-IA` and `ACC-OVL` **authorize** implementation
and perform none: authorization is not implementation. `ACC-PWP` is performed
here as a header on the retired document.

**No constitution is authored, issued, activated, superseded, suspended or
revoked by virtue of this record. No `ACC-FC-5` gate is closed or advanced by
it. No signing key, trust root or approval artifact enters this repository.**

**Date:** 2026-09-09.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-09-09. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Baseline:** default head `dbeae82c246d9e532f0364d03f994238166243cb`, clean
tree, all scoped gates green at ruling time `[V]`.

**Numbering.** `[R]` Four ADR-scoped registers on the standing precedent:
**`ACC-DR`**, **`ACC-SUSP-IA-1`** – **`ACC-SUSP-IA-6`**, **`ACC-OVL-1`** –
**`ACC-OVL-6`**, and **`ACC-PWP-1`**. No `OD`, `ACC-S1`, `ACC-AM`, `ACC-FC`,
`ACC-FC5R`, `ACC-IA`, `ACC-PR`, `ACC-LC`, `ACC-SU`, `ACC-SUSP` or `CV2` number is
assigned, moved or reopened.

---

## 1. `ACC-DR` — documentation reconciliation: **authorized and performed**

**Ruled:** make the documentation-only corrections proposed by the audit;
remove only the **discharged** resolver and `OD-C1=B` blockers; preserve every
genuine disclosure; claim no issuance or activation; change no behaviour,
version, public API or surface ruling.

### What was stale, and why

| Site | The discharged claim | Evidence it is discharged |
|---|---|---|
| `agentic-proposer-strategy-permission-policy` — `README.md`, `src/…/__init__.py`, `src/…/version.py` | "still needs a concrete resolver… cannot execute end to end"; "not yet wired by any composition root" | `[V]` `ugence-agentic-proposer-strategy-permission-runtime` 0.1.0 ships the resolver **and** `build_strategy_policy_resolver`, which registers this family's adapter |
| `agent-constitution-policy` — `README.md`, `src/…/__init__.py` | "still needs the conformance distribution's resolver and verifier"; "first release additionally awaits… `OD-C1=B`" | `[V]` conformance 0.1.0 shipped as the second `ACC-S1-Q2` change set; `OD-C1=B` ratified with `ACC-AM-IMPL=YES` and implemented in Agentic Proposer 0.4.0 (`contracts.py` `constitution_ref`, `constitution_policy_id`) |
| `agent-constitution-conformance` — `README.md`, `src/…/__init__.py`, `src/…/version.py` | "first release awaits the separately balloted `OD-C1=B` contract-amendment round" | as above |

`[V]` **Nothing pinned this drift.** No test asserts any of these status
sentences, which is why they survived the change sets that discharged them —
the same failure mode `S2B_STRATEGY_PERMISSION_POLICY_FAMILY_AND_RESOLVER_DESIGN.md`
§10 step 6 predicted in writing ("no test pins them, so nothing will flag the
drift").

### What was deliberately preserved

`[R]` Every genuine disclosure stands, unedited: `ACC-COUPLING`'s
narrowed-not-eliminated reference-map gap (`build_constitution_resolver` still
accepts any mapping); `ACC-FACTS` (presented facts remain a disclosed caller
assertion, no `verified` boolean); `ACC-ATTESTER` (deferred behind the Trusted
Evidence Authority); the runtime's `[G]` on the weakness of a raw-text scan; and
every open `ACC-FC-5` gate. Each corrected site now **states** that no
constitution has been issued or activated and that no `ACC-FC-5` gate is closed,
so the correction cannot be misread as a readiness claim.

`[R]` **The three CHANGELOG statements were not rewritten.** On the
`ADDITIONAL_STALE_SITES=EXACT_FIVE` precedent, each release paragraph is
retained verbatim as the record of what was true at that release and carries a
dated superseded marker. A CHANGELOG is history; editing it to reflect later
state would be worse practice, not better.

### What `ACC-DR` did not touch

`[V]` No behaviour, no `version.py` version literal, no `public_api.json`, no
package metadata, no CI workflow, no platform-freeze artifact, and no test. The
`__init__.py` and `version.py` edits are **module docstrings only**.

---

## 2. `ACC-SUSP-IA` — suspension implementation authority: **YES, bounded**

This is the implementation-authority ruling that
[`ADR_UGENCE_AGENT_CONSTITUTION_SUSPENSION_ROUND_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_SUSPENSION_ROUND_RATIFICATION.md)
(`ACC-SUSP-BASE`, `ACC-SUSP-1` – `ACC-SUSP-5`, ruled
`SUSP_SURFACE=YES SUSP-1=A SUSP-2=A SUSP-3=A SUSP-4=A SUSP-5=A`) sequenced after
itself, and which that ADR made a precondition of any source change under its
record.

### `ACC-SUSP-IA-1` — the authorization `[R]`

**Ruled: YES**, limited to the round's **already-ratified** contracts,
deterministic validation, lifecycle-state handling and fail-closed resolution
behaviour.

### `ACC-SUSP-IA-2` — what this does **not** authorize `[R]`

Recorded as ruled, in the owner's own enumeration:

* issuing, activating or suspending a **genuine** constitution;
* naming or impersonating an approving authority;
* generating or assuming custody of signing keys;
* closing any `ACC-FC-5` gate;
* adding an operational administration endpoint;
* granting ActionGate or execution authority.

### `ACC-SUSP-IA-3` — the standing invariants, restated as binding `[R]`

Policy Authority remains the owner of authoritative constitution lifecycle
records. Approval must precede signing. Approval must be checked on **every**
use, not once at issuance. Records remain append-only. Suspension or revocation
must **prevent** successful resolution.

### `ACC-SUSP-IA-4` — exercise is test-only until the gates close `[R]`

Until the custody and approving-authority gates (`ACC-FC-5` gates 1 and 2)
close, the implementation is exercised **only** through deterministic tests and
fixtures. `[G]` Suspension will therefore be **unexercisable in production on
the day it lands**, exactly as supersession is, and for the same reason: nothing
has been issued and the gates are shut. That is expected, not a defect.

### `ACC-SUSP-IA-5` — the `ACC-SUSP-4` consumer enumeration, **discharged** `[V]`

`ACC-SUSP-4` obliged this ballot to name the new `PolicyResolutionReason`
member(s) **and** the consumer outcome members required by
`cloud-scaling-policy-authenticity`'s total, injective mapping, **before** the
surface is bounded. Enumerated from the repository at the baseline commit:

**Producer — `ugence_policy_authority.core.statuses.PolicyResolutionReason`**
(`[V]` 22 members at the baseline; the consumer mapping carries the 21
non-`RESOLVED` ones, against 47 `PolicyAuthenticityOutcome` members). Two
members are added, on the exact
revocation/supersession precedent — a member for the applied state, and a member
for a record that exists but does not verify:

| New member | Meaning |
|---|---|
| `SUSPENDED` | A verified suspension record is the latest applicable record at `as_of`. The version is paused, not withdrawn and not replaced; its record stays readable and it may later resolve again |
| `SUSPENSION_INTEGRITY_INVALID` | A suspension-store record targeting this version exists but does not verify — unsigned, wrong key, unauthorized signer, tampered, or ambiguous under `ACC-SUSP-IA-6`. Neither honoured nor ignored: it fails closed |

**Consumer — `ugence_cloud_scaling_policy_authenticity.outcomes`.** The mapping
`RESOLUTION_REASON_OUTCOMES` is asserted **total** over every non-`RESOLVED`
reason and **injective** by
`cloud-scaling-policy-authenticity/tests/test_typed_outcomes.py`
(`test_the_reason_mapping_is_total_over_the_authority_s_refusals`,
`test_the_reason_mapping_is_injective_so_no_refusal_is_collapsed_into_another`).
`[V]` Adding a producer member without the matching consumer member **fails that
suite** — this is the coupling that made `ACC-LC-IA-BASE`'s surface
unsatisfiable and forced the `A1` amendment. Two distinct members are therefore
added to `PolicyAuthenticityOutcome`, with two matching mapping entries:

| Producer reason | Consumer outcome member |
|---|---|
| `SUSPENDED` | `POLICY_SUSPENDED` (named on `POLICY_SUPERSEDED`'s precedent, avoiding a bare-verb collision) |
| `SUSPENSION_INTEGRITY_INVALID` | `SUSPENSION_INTEGRITY_INVALID` |

**The rest of the surface the two members touch**, enumerated at the baseline so
the change set is bounded before it is written:

| Site | What it needs | Why |
|---|---|---|
| `packages/policy-authority/public_api.json` | the two new values appended to the `PolicyResolutionReason` `values` list | `[V]` the snapshot pins enum members literally, so an added member without it is an API-snapshot drift |
| `packages/policy-authority` version | an **additive minor** bump | two members added, none removed or renamed |
| `cloud-scaling-policy-authenticity/tests/test_adversarial.py:311` | nothing | `[V]` parametrizes by **iterating** the enum, so it adapts — but it will newly exercise both members and must pass |
| `agentic-proposer-strategy-permission-runtime/tests/test_no_authority_claimed.py:197` | nothing | `[V]` same: iterates rather than pinning a literal list |

`[V]` **No other consumer is affected.** Every other module that imports
`PolicyResolutionReason` — read individually at the baseline across
`agent-value-readiness` (`deny.py`, `service.py`, `trace.py`), the three
constitution distributions, the strategy-permission pair,
`authoritative-policy-compilation`, `procurement-policy-compilation` and
`cloud-scaling-capacity-bounds-policy` — either branches on one named member
(`NOT_FOUND`), type-checks the enum without enumerating it, or carries the
reason opaquely on an error attribute. `[G]` That is a statement about
**today's** call sites, verified by reading each; it is not a guarantee that no
future consumer will mirror the enum totally, and any that does inherits this
same obligation.

### `ACC-SUSP-IA-6` — the three `ACC-SUSP-2` ordering cases: **NOT SETTLED** `[G]`

> **Settled by amendment (2026-09-09, second sitting).** The heading and the
> section below are retained verbatim as the record of what was open when this
> ADR was first written. `[V]` The three cases are **now ruled** — see §9
> (`ACC-SUSP-IA-7`), which also **corrects** the out-of-order recommendation
> made below. This note reopens nothing.

`ACC-SUSP-2` recorded, as `[G]`, that suspension is *"the first state in this
authority whose current value is not simply 'a record exists'"*, that the
ordering rule must be total and unambiguous, and that **the
implementation-authority ballot must settle three cases explicitly**: equal
timestamps, out-of-order arrival, and a reinstate with no prior suspend.

`[G]` **The 2026-09-09 ruling did not reach these three cases**, and this ADR
does not invent answers for them. They are the one open ownership question
blocking the suspension change set, and they are put to the owner in §5.

`[R]` **Consequence, recorded rather than worked around:** `ACC-SUSP-IA-1`
authorizes the change set, but `ACC-SUSP-2` conditions it on these three
settlements. **No suspension store, record type, resolution reason or act is
implemented under this ADR.** The enumeration in `ACC-SUSP-IA-5` stands ready
and is unaffected by how the three cases are ruled — which is why it was
discharged here rather than deferred with them.

---

## 3. `ACC-OVL` — cross-artifact governed-role overlap: **ratified, close before second issuance**

The gap this closes was recorded as item 5 of the retired pending-work ledger
(§4) and is `[V]` real: `governed_role_refs` is not consulted at issuance, so
two separately issued constitutions may claim the same governed role. The
backstop is downstream — `populate_reference_map` raises
`ReferenceMapConflictError` at activation — which refuses the *map*, not the
*issuance*.

### `ACC-OVL-1` — the invariant `[R]`

**Ratified, fail-closed:** two **simultaneously effective** constitutions may
not govern the same role within the same tenant and scope, unless an
**explicitly ratified** supersession or delegation relationship permits it.

### `ACC-OVL-2` — ownership of the two halves `[R]`

**Conformance owns detection and diagnostic evidence. Policy Authority owns
enforcement**, at issuance and at resolution. `[R]` The split is deliberate:
detection that lives where enforcement lives is a single point of failure, and
conformance must remain unable to authorize anything.

### `ACC-OVL-3` — how an overlap must fail `[R]`

An **unresolved, ambiguous or conflicting** overlap must refuse issuance and
refuse resolution. `[R]` It must **never** be resolved by mapping order or
last-write-wins behaviour. A deployment that would have to guess must instead
be told it cannot proceed.

### `ACC-OVL-4` — the sequencing constraint `[R]`

**Do not issue a second constitution until this invariant is implemented and
verified.** `[R]` This ruling **does not authorize a second constitution**, and
nothing in it advances an `ACC-FC-5` gate.

### `ACC-OVL-5` — the consumer obligation carries `[R]`

`[R]` Enforcement at **resolution** adds at least one `PolicyResolutionReason`
member, so `ACC-SU-4`'s standing obligation — the same one `ACC-SUSP-4` imposed
— applies to this round too: the reason member(s) and their
`cloud-scaling-policy-authenticity` counterparts must be enumerated before the
overlap surface is bounded.

### `ACC-OVL-6` — the enumeration attempted, and the two blockers it found `[G]`

> **Answered by amendment (2026-09-09, second sitting).** Retained verbatim as
> the record of the two blockers as found. `[V]` Both are **now ruled** — see §9
> (`ACC-OVL-7`, `ACC-OVL-8`). The findings themselves stand unchanged; what
> changes is that the owner has said what to do about them.

Discharging `ACC-OVL-5` before writing anything surfaced two obstacles that are
**owner questions, not implementation details**. Recorded here rather than
resolved, and no overlap enforcement is implemented under this ADR.

**Blocker 1 — the authority cannot see a governed role, by design.** `[V]` The
adapter seam exists precisely so that *"the generic core knows nothing about any
policy family: it never imports a family type, never branches on one"*
(`core/adapters.py` module docstring), and the core reads **only**
`PolicyArtifactDescriptor` fields — which carry no governed-role or exclusivity
concept. `governed_role_refs` lives inside the constitution artifact, where the
authority is structurally forbidden to look. So `ACC-OVL-2`'s "Policy Authority
owns enforcement" cannot be implemented by teaching the authority about
constitutions. It requires a **new family-neutral seam**: the adapter declares
opaque exclusivity claims on the descriptor, and the core enforces uniqueness
over `(tenant, scope, claim)` among simultaneously effective versions. `[R]`
That is a **public API change to Policy Authority affecting every family**, plus
its `public_api.json` enum-and-shape snapshot and an additive minor version —
materially larger than the constitution-local change the ruling's wording
implies, and not obviously inside what was authorized.

**Blocker 2 — the delegation carve-out names something that does not exist.**
`[V]` `ACC-OVL-1` permits an overlap where *"an explicitly ratified supersession
or delegation relationship permits it"*. Supersession exists and is implemented.
**Delegation does not exist anywhere**: the substring appears in no source file
of Policy Authority, of the three constitution distributions, or of
`governance-contracts`. There is no delegation contract, no record type, no
ratification. `[R]` Implementing the invariant **without** the carve-out would
enforce something **stricter** than was ruled; implementing the carve-out would
mean inventing a governance relationship, which is a ratification act and not
available to an implementer.

`[R]` **Consequence:** `ACC-OVL-1` – `ACC-OVL-4` stand as ratified, and
`ACC-OVL-4`'s sequencing constraint — no second constitution before the
invariant is implemented and verified — **binds now**, whether or not the
implementation has landed. It is the constraint, not the code, that keeps the
gap harmless in the meantime, exactly as it has been.

---

## 4. `ACC-PWP-1` — `AGENT_CONSTITUTION_PENDING_WORK_PRIORITY.md`: **retired**

**Ruled:** do not refresh another duplicate status ledger. Preserve the document
as historical evidence, mark it retired/superseded and dated 2026-09-09, state
that its versions, baseline and P0 claims are no longer current, point readers
to the canonical ADR decisions by immutable commit SHA, and move any still-valid
open item that exists **only** there into a canonical record before retiring it.

`[V]` **Why it had to be retired rather than refreshed.** Its own baseline
`ab0205df` is **not an object in this repository's history**; its pinned
versions (proposer 0.4.0, activation 0.1.0, authority 0.2.0) trail the tree
(0.6.0, 0.2.0, 0.3.1); and its P0 — the `approval_digest` exclusion — was ruled
`LR-1=A LR-2=A` in
`ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_AMENDMENT.md`. A ledger
that duplicates the ADRs will drift from them again; the ADRs are the record.

**Migration of still-valid open items** `[V]`, so retirement loses nothing:

| Ledger item | Where it now lives |
|---|---|
| 5 — cross-artifact governed-role overlap | **`ACC-OVL`, §3 of this ADR** (ratified, with a sequencing constraint) |
| 1 (P0), 2 (`CV2`), 3 (suspension design) | Already ruled; the ADRs are canonical |
| 4 — proposer README stops at 0.3.0 | `[G]` **Still open and untracked elsewhere.** Carried forward in §5 as a residual item; it is a documentation gap in `packages/capabilities/agentic-proposer/README.md`, not in the five audited distributions, and no ruling in this ADR authorizes editing it |
| 6 — global `policy_family` uniqueness | `[G]` Defence-in-depth gap, unchanged, no live hole; `ACC-S1-Q3`'s registration-time collision guard protects every supported composition path |
| 7 — the two malformed-resolver edge cases | Already disclosed in `agentic-proposer/version.py`; needs an owner decision about the boundary's contract, not a bug fix |
| 8 (P3) — close the four `ACC-FC-5` gates | Unchanged and **operational**: gates 1 and 2 are unadvanceable by any pull request |

---

## 5. What remained open at first writing

> `[V]` **All five questions in this section were ruled on 2026-09-09 in a
> second sitting.** The section is retained as the record of what was put to
> the owner and how it was framed. For the answers, read §9.

`[G]` **The three `ACC-SUSP-2` ordering cases** (`ACC-SUSP-IA-6`) — the one
question blocking the suspension change set. Recommended answers, each derived
from `ACC-SUSP-IA-3`'s fail-closed and deterministic-validation constraints, are
offered as recommendations only and are **not** ruled here:

1. **Equal timestamps** — two records for one coordinate at the same instant are
   **ambiguous**, and ambiguity refuses: reject the second at append time, and
   fail closed at resolution as `SUSPENSION_INTEGRITY_INVALID` if one is ever
   present. Recommended because the alternative is a tie broken by insertion
   order, which is last-write-wins under another name.
2. **Out-of-order arrival** — order by the record's **own signed instant**,
   never by arrival or insertion order, so an append sequence cannot change a
   resolution. Recommended because arrival order is not signed and therefore
   not evidence.
3. **Reinstate with no prior suspend** — refuse at append time; nothing is
   paused, so nothing can be unpaused.

`[G]` **`ACC-OVL` is ratified but unimplemented**, blocked on two owner
questions recorded at `ACC-OVL-6` and put here:

**And the two `ACC-OVL-6` questions:**

4. **The exclusivity seam.** Enforcement in a family-agnostic authority means a
   new generic descriptor/adapter surface affecting every policy family, its
   `public_api.json` snapshot and an additive minor version. Is that in scope,
   or should enforcement instead sit in the constitution family's own adapter
   and in conformance, with the authority enforcing nothing new?
5. **Delegation.** The carve-out names a relationship that does not exist in
   this repository. Should the invariant ship with the supersession carve-out
   only — strictly narrower than ruled, and stated as such — or does delegation
   need its own round first?

`[R]` Until these are answered, `ACC-OVL-4` alone holds the line, and it holds
it adequately: no second constitution may issue, and none can, since no
constitution has been issued at all.

`[G]` **The residual documentation item** carried from the retired ledger:
`packages/capabilities/agentic-proposer/README.md` describes the surface only
through 0.3.0 and does not explain the 0.4.0 constitution binding. Unauthorized
here.

`[G]` **The binding constraint is unmoved.** No constitution has ever been
issued, no `ACC-FC-5` gate is closed, and **no pull request can advance gates 1
or 2** (custody; approving authority).

## 6. Canonical records, by immutable commit SHA

Readers arriving from the retired ledger should use these, not it. Each SHA is
the commit at which the named document currently stands.

| Document | Commit |
|---|---|
| `ADR_UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_SCOPING.md` (`OD-C1`–`OD-C5`) | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_AMENDMENT_ROUND_RATIFICATION.md` (`OD-C1=B`, `ACC-AM-IMPL=YES`) | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_ISSUANCE_ACTIVATION_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_FIRST_CONSTITUTION_RATIFICATION.md` (`ACC-FC-*`) | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_SUSPENSION_ROUND_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_CLAUSES_V2_ROUND_RATIFICATION.md` | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_RATIFICATION.md` (`ACC-FC5R-*`) | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_DEPLOYMENT_GATE_RUNBOOK_AMENDMENT.md` (`LR-1=A LR-2=A`) | `5d602fdbadbdcf8fe4cbe5b7f9d68e7f4e01ed00` |
| `ADR_UGENCE_AGENT_CONSTITUTION_LIVE_ATTESTATION_SCOPING.md` (`ACC-COUPLING`, `ACC-FACTS`, `ACC-ATTESTER`) | `c0e48ca3e89631ca6eab978a3a1037d114cd082a` |

## 7. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record. No
lifecycle authority over agents or roles exists or is implied (`OD-C4=A`).
Constitution binding grants no compute, tools, evidence access or consequential
execution; digest membership proves integrity after construction, never
provenance; no verifier emits a disposition or reserved authority term
(`OD-C3=B`). Conformance replay proves conformance of **presented facts** only,
and that those facts equal a live role's declarations remains the caller's
assertion (`ACC-FACTS`). No constitution is issued, superseded, suspended or
revoked by virtue of this record.

## 8. What this ADR changed

This ADR, the `ACC-DR` documentation-only corrections enumerated in §1, and the
`ACC-PWP-1` retirement header on
`AGENT_CONSTITUTION_PENDING_WORK_PRIORITY.md`. **No production source, test,
`public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** Policy Authority remains at `0.3.1`;
Agentic Proposer at `0.6.0`; `agent-constitution-policy` at `0.2.0`;
`agent-constitution-activation` at `0.2.0`; `agent-constitution-conformance`,
`agentic-proposer-strategy-permission-policy` and
`agentic-proposer-strategy-permission-runtime` at `0.1.0`.

**Next step:** rule the three `ACC-SUSP-IA-6` ordering cases, which unblocks the
suspension change set, and the two `ACC-OVL-6` questions, which unblock the
overlap round. Both are put in §5. Nothing else in either round is waiting on
anything but these.

---

## 9. Amendment — the five rulings of 2026-09-09 (second sitting)

**Status:** **Accepted (ratified owner declaration).** The owner ruled all five
questions §5 put, in a second sitting the same day, and **corrected** one of the
recommendations this ADR had offered. Recorded here rather than by editing §2–§5,
so that what was recommended and what was ruled stay separately legible.

**Numbering.** `[R]` Two further ADR-scoped labels: **`ACC-SUSP-IA-7`** (the
settled ordering rules) and **`ACC-OVL-7`** – **`ACC-OVL-8`** (the seam and the
delegation deferral).

### `ACC-SUSP-IA-7` — the three ordering cases, ruled `[R]`

The single organising rule: **the accepted history is append-only and strictly
time-monotonic.** Arrival order is never authoritative — the signed instants
establish order — but the append-only log may not be **retroactively rewritten**
by inserting an earlier record.

**1. Equal signed timestamps — refuse ambiguity.** For the same policy
coordinate, two **distinct** suspension lifecycle records may not share the same
signed instant. Refuse the second at append time. If a collision is nevertheless
present at resolution, fail closed as `SUSPENSION_INTEGRITY_INVALID`.

`[R]` **An exact replay of the same record identity and signed payload is an
idempotent no-op, not a second append.** A *different* record at the same instant
is an integrity failure. This is the distinction the revocation and supersession
stores already draw between "identical repeat" and "conflicting record", carried
into a sequence store.

**2. Out-of-order arrival — refuse retroactive insertion.** Do **not** sort
arbitrary arrivals into the stored history. A candidate record's signed instant
must be **strictly later** than the latest accepted lifecycle record for that
coordinate; an older candidate is refused at append time. At resolution,
independently verify that the stored sequence is strictly monotonic, and return
`SUSPENSION_INTEGRITY_INVALID` if it is not.

`[R]` **This corrects the recommendation at §5.2**, which proposed ordering
arbitrary arrivals by signed instant. The owner's ground, recorded because it is
the load-bearing one: *accepting reordered records conflicts with rejecting
orphan reinstatements* — under a sort-on-read rule, whether a reinstatement is an
orphan would depend on **delivery order**, which is exactly the property rule 3
exists to deny. Strict monotonicity at append time makes the two rules
consistent; sorting makes them contradict.

**3. Reinstatement without an effective prior suspension — refuse.** A
reinstatement is valid only when the latest valid accepted lifecycle state is
*suspended*. Refuse reinstatement from an active or never-suspended state at
append time. Re-check the transition sequence at **every** resolution and fail
closed as `SUSPENSION_INTEGRITY_INVALID` if an invalid transition is stored.

**Authorized by this ruling:** implementation of the two already-enumerated
`PolicyResolutionReason` members and their downstream mappings
(`ACC-SUSP-IA-5`), under the ratified signature, approval, append-only and
resolution-time re-verification boundaries. `[R]` **Fixtures and deterministic
implementation only.** It does not authorize genuine issuance, activation or
suspension, key custody, or the closure of any `ACC-FC-5` gate —
`ACC-SUSP-IA-2` and `ACC-SUSP-IA-4` are unchanged and still bind.

### `ACC-OVL-7` — a family-neutral exclusivity seam in Policy Authority `[R]`

**Ruled**, answering §5.4. Policy Authority owns **authoritative** overlap
enforcement at issuance and resolution. The Agent Constitution adapter owns the
**projection** of constitution-specific meaning into a normalized, family-neutral
exclusivity claim. Conformance **mirrors** the check and produces diagnostic
evidence, but **cannot be the sole enforcement boundary, because conformance is
not issuance authority**.

Binding constraints on the implementation:

* the Policy Authority core **must not import or branch on constitution types** —
  the seam is generic and optional, and an adapter projects claims through it
  (tenant, scope, governed role);
* **existing families with no exclusivity semantics produce no claims**, so
  nothing changes for them;
* the **constitution family must fail closed** if its required projection is
  missing, malformed or unresolved;
* before a second constitution issues, the authority **compares normalized claims
  against all simultaneously effective constitution claims and refuses
  unresolved overlap**;
* `[R]` **registration, mapping and arrival order may never choose a winner.**

**Sequencing, as ruled:** implement suspension **first**; record the overlap seam
design and enumeration **before** changing Policy Authority's public surface;
and `[R]` **if adding the generic seam changes existing adapter obligations or
serialized descriptors, stop and report the exact compatibility impact before
implementing.**

### `ACC-OVL-8` — delegation deferred to its own round `[R]`

**Ruled:** ship **supersession-only**. The overlap exception narrows to an
**explicitly verified supersession relationship**. `[R]` Delegation is absent
from the current contracts and **must not be invented inside this
implementation**.

`[R]` **`ACC-OVL-1`'s delegation language is deferred, not implemented**, and
this record says so rather than leaving the wording to imply capability that does
not exist. Any future delegation exception requires its own contract and owner
round, covering: delegated authority bounds, identity, scope, duration,
revocation, and the **monotonic rule that delegated authority cannot exceed
issued authority**.

### What §9 does not change

`[R]` No `ACC-FC-5` gate is closed or advanced. No constitution is issued,
activated, superseded, suspended or revoked. No signing key, trust root or
approval artifact enters this repository. `ACC-OVL-4`'s sequencing constraint —
no second constitution before the overlap invariant is implemented and verified —
stands unchanged and still binds.
