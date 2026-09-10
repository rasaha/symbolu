# Specification — the Model Egress Unit

**Opened by** D-1 `INFERENCE_IS_AN_ACTION` and D-2 `SEPARATE_EGRESS_UNIT`, ratified
2026-09-10 (`OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md`).

**Also opened by** §3 `MEU_PULLS_AUTHORIZED_WORK_ASYNCHRONOUSLY`, D-3
`NO_CREDENTIAL_IN_THIS_DEPLOYMENT`, and the CR-5 clarification of 2026-09-10 recorded in
`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`.

**Scope of this revision.** Architecture, boundary, interface and deployment. **D-4** (what
is recorded) and **D-5** (concentration limits at execution) remain open, and the sections
that depend on them say so rather than assuming an answer. Nothing here is implemented, no
provider SDK is introduced, no real network call is specified, and no gate identifier of
P3E-CTR or GRW-CTR is marked satisfied.

## 1 — What the rulings fix

| | |
|---|---|
| The **request** is a governed action | It transmits data outward, incurs cost, invokes a vendor and creates compliance exposure. It is proposed, authorized, cleared and recorded like any other action. |
| The **response** is granted nothing | It returns as an untrusted proposal or as evidence. It carries no decision or execution authority and stays untrusted until independently verified and separately authorized for any consequential use. |
| CR-5 is **not amended**, and is now accurate | The vendor call moves outside the worker. The clarification of 2026-09-10 supersedes the claim that the worker had one outbound connection: it declares three destinations — the JWKS endpoint and the two private persistence endpoints — rather than excusing PostgreSQL by renaming it. A fourth needs a CR-family amendment. |
| Credentials and SDKs live **outside** the worker | No vendor SDK enters the worker's image; no vendor credential enters its environment. |

In this deployment the unit performs no genuine call at all (D-3, §5.2). Where one is
commissioned, the Model Egress Unit (MEU) **may** perform an approved inference call. It **may not**
approve a request, interpret provider output as trusted evidence, or execute a resulting
action. Those three prohibitions are the unit's definition, not its configuration.

## 2 — The boundary

```
Agent Runtime (in the worker)          proposes an inference request
        ↓
Control Plane                          authorizes the request
        ↓
Context Minimization                   controls what may be disclosed
        ↓
─────────── trust boundary ───────────  only minimized, authorized context crosses
        ↓
Model Egress Unit                      performs the approved call, and only that
        ↓
─────────── trust boundary ───────────  the response crosses as untrusted evidence
        ↓
TAP / governance verification          the response is verified, not believed
        ↓
Any consequential action               requires its own authorization and clearance
```

Two properties of that diagram are load-bearing and easy to lose:

- **Context Minimization sits before the boundary, not after.** The minimization gate is
  what decides disclosure; placing it after egress would minimize a copy of something
  already sent.
- **The verification stage is not a formality.** Under D-1 the response arrives with no
  authority. TAP's `INDETERMINATE` on a response is a normal outcome, and a response that
  fails verification produces a typed refusal rather than a degraded result — the same
  refusal shape the shipped console scenarios already demonstrate `[V]`.

## 3 — Direction — **RATIFIED: `MEU_PULLS_AUTHORIZED_WORK_ASYNCHRONOUSLY`**

> **§3 — MEU_PULLS_AUTHORIZED_WORK_ASYNCHRONOUSLY.** The Agent Runtime worker must not open
> a network connection to the Model Egress Unit. It records an inference proposal through
> the existing durable-execution mechanism and yields.
>
> After governance authorization and context minimization, the MEU initiates retrieval or
> leasing of the authorized request from the durable control-plane/outbox boundary. It then
> calls the approved provider and writes a correlated result back through that boundary.
> The durable engine resumes the waiting workflow.
>
> The MEU must not call directly into a specific worker process. Requests and responses are
> correlated through immutable request identity and digest, so worker restarts, retries and
> scaling do not change the result's identity.
>
> The MEU may consume only an already-authorized inference request. Retrieving work does not
> give it authority to approve, modify or broaden the request. The returned provider output
> remains untrusted evidence/proposal data.
>
> CR-5 remains unchanged: the worker's only outbound destination remains its ratified JWKS
> host. If the existing durable-execution mechanism cannot support the request/outbox and
> result/resume sequence without adding worker egress, stop and report that contradiction
> rather than silently amending CR-5.
> — owner, 2026-09-10

The flow:

```
Worker records inference proposal and yields
        ↓
Control Plane authorizes + minimizes context
        ↓
Durable authorized-request outbox
        ↓
MEU retrieves request and calls model provider
        ↓
MEU records correlated untrusted response
        ↓
Durable engine resumes worker
```

### 3.1 — The reported contradiction, and how it was resolved

The stop-and-report condition triggered, though not where the ruling expected: the obstacle
was never the durable mechanism's capability. `EXTERNAL_DEPLOYMENT_EVIDENCE.json` claimed
the JWKS fetch was the worker's only outbound connection while the worker had been dialling
PostgreSQL since it first composed (`composition.py:223-260`, and the 2026-09-09
deployment's own startup line) `[V]`.

**Resolved by the CR-5 clarification of 2026-09-10** `[V]`. The resolution refuses the easy
route: PostgreSQL is outbound network connectivity even through
`postgres.railway.internal`, and it is **declared** rather than reclassified. The worker's
permitted destinations are now three and named; the MEU, model providers, arbitrary private
services and the public internet are named as forbidden; a fourth destination requires a
CR-family amendment.

**Consequence for this design, which is the reason it matters.** The outbox may use the
existing PostgreSQL/DBOS connection **only if that introduces no additional network
destination** `[R]`. It introduces none: the worker already connects to those two
endpoints, and the MEU reaches the same database from its own side. The worker opens
nothing new and, in particular, never opens a connection toward the MEU.

Schema, authorization and tenancy changes to that outbox remain **separately reviewable**
and are not authorized by this document.

### 3.2 — What the durable mechanism must be shown to carry `[G]`

DBOS is composed into the worker over PostgreSQL system and application databases `[V]`,
which is the class of mechanism the ruling names. Whether it supports an externally-leased
outbox with the claim, correlation and resume semantics §5 and §6 require — without the
worker initiating anything — is **not verified here**. It is the first engineering question
of implementation, answerable offline against the composed engine, and it is a
precondition rather than a detail: if DBOS cannot resume a workflow on a row written by a
process it does not host, the transport needs rethinking before any code is written.

## 4 — The interface

Two records on the durable boundary, and no endpoint on either side. Neither party calls the
other: the worker writes and later resumes; the MEU claims and writes back.

### 4.1 — The authorized inference request

Written by the worker **after** the request has been authorized and cleared and the context
minimized — never before. Its identity is immutable:

| Field | Purpose |
|---|---|
| `request_id` | Immutable identity. Not a process, host or attempt — restarts, retries and scaling do not change it. |
| `request_digest` | Canonical digest over the authorized fields. The MEU verifies it before calling; a mismatch is a refusal. |
| `correlation_id` | Ties the request, its result and the audit trail together. |
| `clearance_ref` | The `cer-…` receipt that authorized **this request**, with its action binding, scope and expiry. |
| `tenant_id` | The tenant the request belongs to. Never inferred from the claim. |
| `model_ref` | The model the authorization named, not a family or an alias resolved later. |
| `parameters` | The call parameters the authorization named. |
| `minimized_context` | What Context Minimization admitted, and only that. |
| `not_valid_after` | The request's own expiry, independent of the lease. |

The MEU **may not** modify, broaden or reinterpret any of these. Claiming work confers no
authority over what was claimed.

### 4.2 — The correlated result

Written by the MEU. Carries the same `request_id`, `request_digest` and `correlation_id`,
so the result's identity derives from the request rather than from whoever produced it:

| Field | Purpose |
|---|---|
| `trust` | Always `UNTRUSTED_EVIDENCE`. There is no other value. |
| `outcome` | `ANSWERED`, `REFUSED` or `FAILED` — each a first-class outcome, none an exception. |
| `provenance` | Which adapter, which model, when, and **whether the call was genuine or a deterministic fake** (§5.2). |
| `metering` | Token counts, latency, and cost where the adapter reports it — the governance the request was authorized against. |
| `payload` | The provider output, or absent on refusal. Its content is D-4's subject `[R]`. |

`trust` is not a field the MEU computes. It is a constant, because D-1 grants the response
nothing: the output arrives as evidence and is verified downstream, never believed because
it arrived.

### 4.3 — Leasing

A claim is a lease with an expiry, not a removal. An expired lease returns the request to
the unclaimed set; it does not delete it, and it does not entitle a second call. The
`request_id` plus `request_digest` pair is the idempotency key: **a request already served
is never served twice**, whatever the lease state, because the cost of a duplicate is a
second billed vendor call the governance authorized once.

## 5 — Deployment

### 5.1 — The unit

A separate deployment unit, built and released independently of the worker. It holds the
provider adapters. It does not hold, import or link anything from the worker's authority,
approval or audit surfaces — the boundary is one-way by construction, and a shared library
would erode it quietly.

Its network posture, stated as the worker's now is:

| Destination | |
|---|---|
| The shared PostgreSQL persistence endpoints | permitted — how it claims work and writes results |
| Approved model provider endpoints | permitted **only where a credential exists** (§5.2) |
| The worker's listener | **forbidden.** The MEU never calls a worker process, by §3 |
| The authority plane, the studio, the console | **forbidden** |
| Anything else | **forbidden.** A new destination is a CR-family amendment, as for the worker |

### 5.2 — In this deployment there is no credential, and that is a posture

Under D-3, the reference deployment **contains no model-provider credential and makes no
genuine provider call** `[V]`. What that requires of the implementation, stated as
behaviour rather than as absence:

- **The unit starts and runs without a credential.** It does not treat one as required
  configuration and fail; it composes, claims work, validates it, and refuses the call.
- **The refusal is explicit and typed.** `outcome: REFUSED` with a reason naming the missing
  custody — never a generic error, never a silent skip, never a fabricated answer.
- **Provenance never claims what did not happen.** A deterministic fake adapter records
  itself as a fake. A provenance record that could be mistaken for genuine provider evidence
  is the failure this clause exists to prevent.
- **A credential cannot be smuggled in.** Not through an environment variable, not through a
  fixture, not through an undocumented operator step `[V]`. If a credential is present in a
  deployment that has not been commissioned for one, the correct behaviour is to refuse
  rather than to use it.

What may therefore be built and tested now, in full: the deployment boundary,
authorized-request leasing, minimized-context validation, provider-adapter **interfaces**
against deterministic fakes, response correlation, refusal and retry behaviour, and
provenance placeholders that make no genuine-evidence claim.

**Production invocation stays blocked** until an external secret-manager integration, a
rotation policy, an audit trail and a named custody owner are separately commissioned.
`PLATFORM_ENVIRONMENT_VARIABLE` is rejected as a production custody mechanism `[V]`, and
this specification does not reopen it.

### 5.3 — What the deterministic fake must not become

A fake adapter that returns plausible model output is a demo; one that returns *labelled*
output is a test fixture. The difference is the provenance record, and it is the only thing
standing between a governed loop and a governed-looking loop. Every path that produces a
result from a fake carries that label to the ledger, and no consumer may treat a labelled
result as evidence of a provider having answered.

## 6 — Refusals the unit owes

The MEU refuses rather than proceeds when:

- the clearance receipt is absent, expired, unbound to this request, or fails integrity;
- the `request_digest` does not verify against the authorized fields;
- the requested model or parameters differ from what the authorization named;
- the context carries anything Context Minimization did not admit;
- this `request_id` and digest have already been served;
- **no credential is commissioned for the provider the request names** (§5.2);
- the request has passed `not_valid_after`.

Each is a typed refusal naming the reason and correlated to the request. **A refusal must
not be recoverable by retrying with the same inputs** — that is the difference between a
control and a speed bump. A refusal is a result, written back through the boundary like any
other, so the waiting workflow resumes on a refusal rather than hanging.

D-5 would add one more refusal — a call that would breach the vendor mix a plan promised —
and it cannot be written until D-5 is ruled `[R]`.

## 7 — What the rulings do not authorize

- **No provider in the worker's registry calls a vendor**, and the worker opens no
  connection to the MEU. Both are now forbidden destinations in the worker's own egress
  record `[V]`.
- **The MEU has no authority surface.** It cannot grant, clear, approve or execute. AP-4's
  read-only posture on the authority plane is untouched and stays untouched `[V]`.
- **The MEU is not a second governance layer.** It performs one call and returns one
  result, as RA-7 observes without owning authority consequences `[V]`.
- **No schema, authorization or tenancy change to the outbox is authorized here.** Those
  remain separately reviewable `[V]`.

## 8 — Open decisions, and what each one blocks

| Decision | Blocks |
|---|---|
| **D-4** what is recorded `[R]` | The `payload` field of §4.2 — whether the provider output reaches the ledger, as content, as a digest, or through Context Minimization |
| **D-5** concentration limits `[R]` | One refusal in §6 — whether the MEU refuses a call that would breach the vendor mix a plan promised |
| **DBOS external leasing** `[G]` | §3.2 — the first engineering question, and a precondition rather than a detail |
| **Outbox schema, authorization, tenancy** `[R]` | Separately reviewable by the CR-5 clarification; not authorized by this document |

## 9 — What exists to build on

| | |
|---|---|
| Neutral `Provider` protocol and registry | Built `[V]` |
| The only concrete provider | `ShadowProvider`, `FIXTURE_ONLY`, records in memory `[V]` |
| Context Minimization, TAP, ActionGate, Autonomous Control Plane | Composed into the loop and demonstrated `[V]` |
| Clearance receipts (`cer-…`) | Ride every disposition `[V]` |
| Receipt verification by a consumer | Does not exist `[G]` |
| Durable execution able to carry an asynchronous result | DBOS engine composed `[V]`; used for this, unproven `[G]` |
| The MEU | Does not exist. No package, no image, no deployment unit `[G]` |
