# Specification — the Model Egress Unit

**Opened by** D-1 `INFERENCE_IS_AN_ACTION` and D-2 `SEPARATE_EGRESS_UNIT`, ratified
2026-09-10 (`OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md`).

**Scope of this revision.** Architecture and boundary only. D-3 (credential custody), D-4
(what is recorded) and D-5 (concentration limits at execution) are open, and every section
that depends on one says so rather than assuming an answer. Nothing here is implemented,
and no gate identifier of P3E-CTR or GRW-CTR is marked satisfied.

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

## 3 — The direction of the call is not yet decided `[R]`

**This is the first thing the next revision must settle, and the rulings do not settle
it.** CR-5 says the worker's only egress is the configured JWKS host. The MEU is not that
host. So if the worker initiates the call to the MEU, the worker has a second outbound
destination and CR-5 needs a narrow amendment after all — for a private in-perimeter host
rather than a vendor, but an amendment nonetheless.

| Option | Consequence |
|---|---|
| `WORKER_CALLS_THE_UNIT` | The natural request/response shape, and the smaller change to the runtime. CR-5 gains a second permitted destination; the claim becomes "the JWKS host and one private unit" rather than "one host". |
| `UNIT_CALLS_THE_WORKER` | The worker stays inbound-only and CR-5 is preserved **literally**, with no amendment at all. The MEU claims authorized requests and returns results through the worker's existing inbound surface. Costs an asynchronous shape: a request queue, claim semantics, and a result that arrives later than the proposal. |

**Recommendation: `UNIT_CALLS_THE_WORKER`.** D-2's stated purpose is to preserve CR-5, and
only this option preserves it without an amendment. It also puts the boundary the safer way
round: the worker never initiates a connection toward the component that talks to vendors,
so a compromised MEU cannot reach inward except through the surface the worker already
exposes and already authenticates.

The cost is real and should be accepted knowingly: inference becomes asynchronous, which
the durable-execution engine already accommodates but the current synchronous
`Provider.execute(ToolInvocation) -> ToolResult` shape does not `[V]`.

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
| **§3 direction** `[R]` | The request/result transport, the runtime's inference shape, and whether CR-5 is amended at all |
| **D-3** credential custody `[R]` | Where the MEU's vendor credential lives, how it rotates, and whether the unit is deployable in *this* deployment or only a customer-operated one |
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
