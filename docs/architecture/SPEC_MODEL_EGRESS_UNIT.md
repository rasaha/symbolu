# Specification — the Model Egress Unit

**Opened by** D-1 `INFERENCE_IS_AN_ACTION` and D-2 `SEPARATE_EGRESS_UNIT`, ratified
2026-09-10 (`OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md`).

**Scope of this revision.** Architecture and boundary only, plus §3's ratified direction.
The interface and deployment sections are **deliberately not written**: they depend on D-3,
and writing them first would describe a partially decided architecture. D-4 and D-5 remain
explicitly open. Nothing here is implemented, and no gate identifier of P3E-CTR or GRW-CTR
is marked satisfied.

**One finding requires an owner answer before the next revision** — §3.1. It is not about
the Model Egress Unit.

## 1 — What the two rulings fix

| | |
|---|---|
| The **request** is a governed action | It transmits data outward, incurs cost, invokes a vendor and creates compliance exposure. It is proposed, authorized, cleared and recorded like any other action. |
| The **response** is granted nothing | It returns as an untrusted proposal or as evidence. It carries no decision or execution authority and stays untrusted until independently verified and separately authorized for any consequential use. |
| CR-5 is **not amended** | The worker's egress claim stands as written. The vendor call moves outside it. |
| Credentials and SDKs live **outside** the worker | No vendor SDK enters the worker's image; no vendor credential enters its environment. |

The Model Egress Unit (MEU) **may** perform an approved inference call. It **may not**
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

### 3.1 — The contradiction this ruling asked to be reported `[R]`

**Stopping here as instructed rather than proceeding.** The ruling's condition is met, but
not in the way it anticipated: the obstacle is not the durable mechanism's capability. It
is that **the worker already makes an outbound connection the egress record does not
account for**, and the outbox would use that same connection.

`EXTERNAL_DEPLOYMENT_EVIDENCE.json` states: *"the worker's only outbound connection is the
JWKS fetch its identity adapter makes to `UGENCE_REVIEW_IDENTITY_JWKS_URL` over HTTPS"*,
and lists exactly one entry under `permitted_egress` `[V]`.

The worker also dials PostgreSQL at boot, three times: `SQLAlchemyDatasource.create`,
`DBOS(system_database_url=…, application_database_url=…)`, and one direct
`sa.create_engine` for the schema step (`composition.py:223-260`) `[V]`. The 2026-09-09
deployment's own startup line records both DSNs pointing at
`postgres.railway.internal:5432` `[V]`. PostgreSQL appears in neither `permitted_egress`
nor `forbidden_egress`.

So one of two things is true, and only the owner can say which:

| Reading | Consequence for this specification |
|---|---|
| **`EGRESS_MEANS_LEAVING_THE_PERIMETER`** — an in-perimeter datastore connection is not egress | The design is admissible as ratified. The outbox lives in the database the worker already uses; the MEU reaches the same database from its own side; the worker opens nothing new. CR-5 is untouched, and the egress record needs one clarifying sentence rather than an amendment. |
| **`EGRESS_MEANS_ANY_OUTBOUND_CONNECTION`** — the record means what it literally says | The record is already inaccurate today, before any MEU exists, and the contradiction is pre-existing rather than introduced here. A Postgres-backed outbox would then be a second instance of the same problem, and the ruling's "stop and report" applies to the current deployment as much as to this design. |

**This is not a question about the Model Egress Unit.** It is a question about what CR-5
has meant since the worker first connected to a database. The specification cannot choose
between the readings without deciding a ratified ruling's scope, so it stops here.

**No amendment to CR-5 is proposed, and none is implied.** Under the first reading none is
needed. Under the second, what needs correcting is a record about the deployment that
already exists.

### 3.2 — What the durable mechanism can carry, separately from the above

Assessed on the assumption that 3.1 resolves to the first reading. DBOS is composed into
the worker over PostgreSQL system and application databases `[V]`, which is the class of
mechanism the ruling names. Whether it supports an externally-leased outbox with the
claim, correlation and resume semantics §4 and §5 require — without the worker initiating
anything — is **not yet verified here** `[G]`. It is the next revision's first engineering
question, and it is answerable offline against the composed engine rather than by
deploying anything.

## 4 — What crosses, in each direction

**Inward to the MEU** — a claimed inference request carrying:

- the correlation id and the clearance receipt (`cer-…`) that authorized *this request*;
- the minimized context admitted by Context Minimization, and nothing else;
- the model identity and call parameters the authorization named;
- an idempotency key, so a re-claim cannot produce a second billed call.

**Outward from the MEU** — a result carrying:

- the same correlation id, and a provenance record: which vendor, which model, when;
- the response payload, typed as **untrusted**;
- the call's own metering — token counts, latency, cost — for the governance the request
  was authorized against;
- or a typed failure, which is a first-class outcome rather than an exception.

**Never crossing, in either direction:** a credential, a raw un-minimized context, an
authorization decision, or an instruction the worker will act on without re-authorizing.

## 5 — Refusals the unit owes

The MEU refuses rather than proceeds when:

- the clearance receipt is absent, expired, unbound to this request, or fails integrity;
- the requested model or parameters differ from what the authorization named;
- the context carries anything Context Minimization did not admit;
- the idempotency key has already been served.

Each is a typed refusal naming the reason. **A refusal must not be recoverable by retrying
with the same inputs** — that is the difference between a control and a speed bump.

## 6 — What the ruling does not authorize

- **No provider in the worker's registry calls a vendor.** Whatever represents inference
  inside the runtime speaks to the MEU, never to `api.openai.com` or any peer.
- **The MEU has no authority surface.** It cannot grant, clear, approve or execute. AP-4's
  read-only posture on the authority plane is untouched and stays untouched `[V]`.
- **The MEU is not a second governance layer.** It performs one call and returns one
  result, exactly as RA-7 observes without owning authority consequences `[V]`.

## 7 — Open decisions, and what each one blocks

| Decision | Blocks |
|---|---|
| **§3.1 what CR-5 counts as egress** `[R]` | Whether the ratified §3 design is admissible at all, and whether the current deployment's egress record is accurate |
| **D-3** credential custody `[R]` | The interface and deployment sections in full — where the MEU's vendor credential lives, how it rotates, and whether the unit is deployable in *this* deployment or only a customer-operated one |
| **D-4** what is recorded `[R]` | The provenance record's content in §4, and whether the response payload reaches the ledger at all |
| **D-5** concentration limits `[R]` | Whether the MEU refuses a call that would breach the vendor mix a plan promised — a §5 refusal that cannot be written until this is answered |
| **New CR-family ruling** `[R]` | What may cross the boundary in §2, as an owner act rather than a consequence of this document |

## 8 — What exists to build on

| | |
|---|---|
| Neutral `Provider` protocol and registry | Built `[V]` |
| The only concrete provider | `ShadowProvider`, `FIXTURE_ONLY`, records in memory `[V]` |
| Context Minimization, TAP, ActionGate, Autonomous Control Plane | Composed into the loop and demonstrated `[V]` |
| Clearance receipts (`cer-…`) | Ride every disposition `[V]` |
| Receipt verification by a consumer | Does not exist `[G]` |
| Durable execution able to carry an asynchronous result | DBOS engine composed `[V]`; used for this, unproven `[G]` |
| The MEU | Does not exist. No package, no image, no deployment unit `[G]` |
