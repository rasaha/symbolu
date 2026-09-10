# Specification — the Model Egress Unit

**Opened by** D-1 `INFERENCE_IS_AN_ACTION` and D-2 `SEPARATE_EGRESS_UNIT`, ratified
2026-09-10 (`OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md`).

**Also opened by** §3 `MEU_PULLS_AUTHORIZED_WORK_ASYNCHRONOUSLY`, D-3
`NO_CREDENTIAL_IN_THIS_DEPLOYMENT`, the CR-5 clarification of 2026-09-10 recorded in
`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`, and the three transport rulings of
2026-09-10 recorded in §3.3, §3.4 and §3.5 below.

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
Worker's reconciliation driver observes it and advances the instance
```

**Amended 2026-09-10 (§3.3).** The ruling above says *"the durable engine resumes the
waiting workflow."* It does not. The engine holds no waiting workflow and observes no row;
the worker's own reconciliation driver observes a durable result and explicitly advances
the parked instance. §3.2 records the audit that established this.

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

### 3.2 — What the audit established `[V]`

A read-only investigation of the repository's durable-execution package, 2026-09-10:

| Question | Finding |
|---|---|
| Does the engine hold a waiting workflow? | **No.** *"Each `advance` runs as a fresh DBOS workflow, so DBOS never replays a previously recorded advance result"* (`dbos_engine.py:29-33`) `[V]` |
| Does writing a row wake anything? | **No.** Nothing observes rows `[V]` |
| Does `resume()` run the workflow? | **No.** *"Re-arm a parked instance. The NEXT `advance` re-evaluates; this call runs nothing"* `[V]` |
| What advances an instance? | A caller of `advance()`. The only one in the product is the start relay (`starter.py:83`), driven by an inbound HTTP request `[V]` |
| Is there a scheduler, poller or background loop? | **None anywhere** in the durable-execution or worker packages `[V]` |
| Is DBOS messaging used? | **No.** No `send`, `recv`, `set_event` or `get_event` in the product tree `[V]` |
| Is there a precedent for an outside result reaching a parked instance? | **Yes, shipped.** The human-review path does `signal()` then `resume()` (`service.py:763-787`) `[V]` — but from inside the worker, with something inbound driving the next quantum |
| Does the model survive a different replica? | Yes by construction: `worker_claims`, `state.claim(...)`, `recover(worker_id)`, and `advance` returning `CLAIM_HELD_BY_ANOTHER_WORKER` **parked rather than executing** `[V]` |

**Not determinable here `[G]`.** What DBOS 2.x offers as a public messaging API could not be
established: the package is not installed in the audit environment, and `dbos>=2.0` is a
floor rather than a pin. §3.6 makes that a prerequisite rather than a footnote.

### 3.3 — Reconciliation — **RATIFIED: worker-owned driver**

> **1. Worker-owned reconciliation driver.** Commission an in-worker background
> reconciliation loop that periodically finds committed MEU results awaiting delivery and
> invokes the existing worker-owned sequence:
>
> ```
> observe committed result
> → validate request/result identity and digest
> → signal()
> → resume()
> → advance()
> ```
>
> The scheduler provides liveness only. It does not authorize inference, create a
> successful result, bypass a refusal or reuse prior clearance. `advance()` must
> re-evaluate from durable state under current governance.
>
> The loop must be restart-safe and idempotent. It must query durable pending work rather
> than depend on an in-memory timer or PostgreSQL notification. Existing claims, advisory
> locks and instance integrity checks remain authoritative when multiple replicas contend.
>
> Amend §3: the durable engine does not independently resume a waiting workflow. The
> worker's reconciliation driver observes a durable result and explicitly advances the
> parked instance.
> — owner, 2026-09-10

**Liveness only** is the whole of the scheduler's remit, and the sentence to hold it to.
It decides nothing. Every governance question is re-asked by `advance()`, which re-enters
the boundary from the beginning against current durable state — the property
`dbos_engine.py` already relies on and the reason a clearance obtained before parking is
never reused `[V]`.

It queries durable pending work. An in-memory timer would lose its schedule on restart and
a notification would lose the wake it missed; neither is a mechanism a governed loop may
depend on for delivery.

### 3.4 — The exchange boundary — **RATIFIED: dedicated schema, least privilege**

> **2. Dedicated exchange schema with least privilege.** Do not give the MEU access to the
> worker's application schema, `runtime_events`, or DBOS-owned tables.
>
> Create a logically separate model-egress exchange schema with distinct database roles:
>
> - The worker may create authorized requests and read committed results.
> - The MEU may lease authorized requests and write correlated results or refusals.
> - The MEU may not call `signal()`, `resume()` or `advance()`.
> - The MEU may not write worker lifecycle state or DBOS system state.
> - The worker alone translates a verified exchange result into its internal
>   `signal()`/`resume()` sequence.
>
> The exchange may use the same Railway PostgreSQL server, but schema ownership, table
> grants and credentials must remain separate. **Sharing one database server does not mean
> sharing authority.**
> — owner, 2026-09-10

This closes the boundary question the audit raised. The pull design's real cost was never
the network shape; it was that the obvious implementation hands the MEU write access to the
worker's own state. It does not. The MEU reaches an exchange schema and nothing else, and
the translation from *a row in the exchange* to *a governed state transition* is the
worker's alone.

The resulting shape:

```
MEU → dedicated exchange tables
Worker scheduler → reads result
Worker only → signal + resume + advance
```

**The MEU transports inference. It never gains control over workflow execution.**

### 3.5 — The ambiguous interval — **RATIFIED: `OUTCOME_UNKNOWN` is terminal**

> **3. Ambiguous provider outcome.** Ratify `OUTCOME_UNKNOWN` as a durable terminal outcome
> for the original request whenever provider dispatch may have occurred but no provider
> result was durably committed.
>
> Lease expiry alone must never authorize another provider call after possible dispatch.
> The original request may not return to `PENDING`, and its previous authorization or
> clearance may not be reused.
>
> Recovery rules:
>
> - Before dispatch: an expired lease may make the request claimable again.
> - After possible dispatch: persist or reconstruct `OUTCOME_UNKNOWN`; do not retry
>   automatically.
> - With a verified provider idempotency guarantee bound to the same `request_id` and
>   identical `request_digest`: recovery may be considered only after fresh governance
>   authorization.
> - Without verified provider idempotency: any new call is a potentially duplicate billed
>   inference and requires an explicitly authorized new request linked to the uncertain
>   original. **It must not be described as a retry of the old request.**
>
> A refusal or `OUTCOME_UNKNOWN` must resume the workflow so it does not remain parked
> indefinitely.
> — owner, 2026-09-10

The last line is the one an implementation is most likely to drop. An unknown outcome is
still an outcome: it is written back through the exchange, the reconciliation driver
observes it like any other, and the workflow advances on it. A request whose provider
outcome is unknown must not become a workflow parked forever.

The naming rule is not cosmetic either. Calling a fresh authorized call a *retry* would
imply the first one did not happen — which is precisely what nobody knows.

### 3.6 — Prerequisite: pin DBOS before writing the scheduler `[R]`

`dbos>=2.0` is a floor, not a pin `[V]`, and the audit could not establish the installed
contract because the package is absent from the audit environment. **Before the scheduler
is coded, identify the exact DBOS version CI exercises and adopt a tested pin or a bounded
compatibility range.** No part of this design may depend on unspecified future DBOS 2.x
behaviour; the mechanisms it does depend on — `@DBOS.workflow`, `@ds.transaction`,
`launch`, `destroy`, `SQLAlchemyDatasource`, `run_tx_step` — are the ones the repository
already exercises `[V]`.

## 4 — The interface

Two records in the **dedicated exchange schema** (§3.4), and no endpoint on either side.
Neither party calls the other. The exchange is the entire vocabulary between them: the
worker creates requests and reads committed results; the MEU leases requests and writes
results or refusals. Nothing else crosses, in either direction, at any privilege.

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
| `outcome` | `ANSWERED`, `REFUSED`, `FAILED` or `OUTCOME_UNKNOWN` — each a first-class outcome, none an exception. `OUTCOME_UNKNOWN` is **terminal** for this request (§3.5). |
| `provenance` | Which adapter, which model, when, and **whether the call was genuine or a deterministic fake** (§5.2). |
| `metering` | Token counts, latency, and cost where the adapter reports it — the governance the request was authorized against. |
| `payload` | The provider output, or absent on refusal. Its content is D-4's subject `[R]`. |

`trust` is not a field the MEU computes. It is a constant, because D-1 grants the response
nothing: the output arrives as evidence and is verified downstream, never believed because
it arrived.

### 4.3 — Leasing, and what an expiry may and may not do

A claim is a lease with an expiry, not a removal. What the expiry permits depends entirely
on whether dispatch may have occurred (§3.5):

| State when the lease expires | What the expiry permits |
|---|---|
| Before dispatch | The request becomes claimable again. No call was made. |
| After possible dispatch | **Nothing.** The request becomes `OUTCOME_UNKNOWN`, terminal. It does not return to `PENDING`, and its authorization and clearance are spent. |

The `request_id` plus `request_digest` pair is the durable dedup key: **a request already
served is never served twice**. But dedup and lease expiry between them cannot make the
ambiguous interval safe, because the provider call happens outside any transaction — which
is why §3.5 exists rather than a cleverer lease.

A fresh authorized call after an `OUTCOME_UNKNOWN` is a **new request linked to the
uncertain original**, never a retry of it.

## 5 — Deployment

### 5.1 — The unit

A separate deployment unit, built and released independently of the worker. It holds the
provider adapters. It does not hold, import or link anything from the worker's authority,
approval or audit surfaces — the boundary is one-way by construction, and a shared library
would erode it quietly.

Its network posture, stated as the worker's now is:

| Destination | |
|---|---|
| The exchange schema, under its own role and credential | permitted — how it leases work and writes results. Not the worker's application schema, not `runtime_events`, not DBOS-owned tables (§3.4) |
| Approved model provider endpoints | permitted **only where a credential exists** (§5.2) |
| The worker's listener | **forbidden.** The MEU never calls a worker process, by §3 |
| The authority plane, the studio, the console | **forbidden** |
| Anything else | **forbidden.** A new destination is a CR-family amendment, as for the worker |

### 5.2 — Privilege, stated as grants rather than as intent

The same PostgreSQL server may host both, and that is not a shared authority. Schema
ownership, table grants and credentials are separate, and the separation is enforced by the
database rather than by the code's good behaviour:

| Role | May |
|---|---|
| worker | create authorized requests; read committed results |
| MEU | lease authorized requests; write correlated results, refusals and `OUTCOME_UNKNOWN` |

And the MEU may **not**, at any privilege: call `signal()`, `resume()` or `advance()`;
write worker lifecycle state; touch DBOS system state; or read or write the worker's
application schema. The translation from an exchange row to a governed state transition is
the worker's alone, and it is the reconciliation driver of §3.3 that performs it.

### 5.3 — In this deployment there is no credential, and that is a posture

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

### 5.4 — What the deterministic fake must not become

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
control and a speed bump.

**A refusal and an `OUTCOME_UNKNOWN` are both written back through the exchange**, so the
reconciliation driver observes them like any answered result and the instance advances on
them (§3.3, §3.5). An instance parked forever because nothing came back is a failure of
this design, not an acceptable degradation.

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
| **DBOS pin** `[R]` | §3.6 — a prerequisite to coding the scheduler, not a cleanup afterwards |
| **Exchange schema, grants, tenancy** `[R]` | Separately reviewable under the CR-5 clarification and §3.4; not authorized by this document |
| **D-5** concentration limits `[R]` | One refusal in §6 — whether the MEU refuses a call that would breach the vendor mix a plan promised |


## 9 — What exists to build on

| | |
|---|---|
| Neutral `Provider` protocol and registry | Built `[V]` |
| The only concrete provider | `ShadowProvider`, `FIXTURE_ONLY`, records in memory `[V]` |
| Context Minimization, TAP, ActionGate, Autonomous Control Plane | Composed into the loop and demonstrated `[V]` |
| Clearance receipts (`cer-…`) | Ride every disposition `[V]` |
| Receipt verification by a consumer | Does not exist `[G]` |
| `signal()` / `resume()` / `advance()` on application-owned tables | Built, and exercised by the human-review path `[V]` |
| An outside party delivering a result to a parked instance | Shipped precedent, from inside the worker `[V]` |
| A reconciliation driver | Does not exist. No scheduler, poller or background loop anywhere `[V]` |
| The exchange schema and its roles | Do not exist `[G]` |
| A pinned DBOS version | Does not exist; `dbos>=2.0` is a floor `[V]` |
| The MEU | Does not exist. No package, no image, no deployment unit `[G]` |
