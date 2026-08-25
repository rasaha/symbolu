# Ugence internal pilot — what is actually being built

**Status: scoping record, not a commitment.** Written 2026-08-25. No external client
exists; Ugence is its own first user. This document says what is decided, what already
ships, and what is still open. It ratifies nothing and binds no package's governance.

Evidence labels: `[V]` verified against the repository, `[I]` inferred, `[R]` requires
ratification, `[G]` gap — unanswered.

---

## 1. What is decided

Three things, settled by the owner on 2026-08-25:

- **Engagement:** internal pilot. There is no external client, no signed scope and no
  delivery date. Ugence is the client.
- **Deliverable:** a standalone application plus a service API — a Ugence-hosted product
  used directly, not an SDK others embed and not an integration inside someone else's
  platform.
- **Centre of gravity:** agent runtime and execution governance — deciding and acting
  under policy, and being able to show afterwards what was decided and why.

## 2. What already exists to build on

The execution-governance line is the mature part of this repository `[V]`:

| Component | Version | Size | What it does |
|---|---|---|---|
| `ugence-agent-runtime` | `0.7.0` | ~9,900 LOC | Domain-neutral execution-coordination kernel. Canonical execution state, bounded workflow advancement, deterministic multi-workflow coordination, durable checkpoint/recovery, append-only audit event store, bounded concurrent execution |
| `ugence-risk-authority` | — | ~7,550 LOC | Risk evaluation |
| `ugence-policy-authority` | — | ~3,510 LOC | Policy decisions, Ed25519 signing |
| `ugence-governance-contracts` | — | ~1,770 LOC | Shared contract layer |
| `ugence-action-clearance` | `0.1.0` | ~1,610 LOC | Pre-execution clearance: `CLEAR · HOLD · BLOCK · ESCALATE`. Stateless, creates no authority |
| `ugence-governance-provider-framework` | — | ~1,560 LOC | Provider abstraction |
| `ugence-uvi-policy-contracts` | — | ~1,440 LOC | Policy contract vocabulary |
| `ugence-governed-value` | — | ~1,270 LOC | Value governance |
| `actiongate` provider | `0.1.0` | — | Authorization gate |

Agent Runtime's README records `0.2.0` through `0.6.0`/`0.7.0` as
`IMPLEMENTED_AND_CI_VERIFIED` against scoped CI — package suite, isolated wheel-install,
platform-freeze, terminology, API-stability registry, safety-case and SBOM `[V]`.

**Existing app and API surfaces** `[V]`: `ugence_console_api/` (~1,120 LOC — `app.py`,
`orchestrator.py`, `scenarios.py`, `audit.py`, `models.py`), `apps/console`,
`apps/ugence-governance-studio`, and `frontend/`. Whether any of these is the pilot's
starting point or is superseded is undecided — see §5.

## 3. What the pilot is not

Stating this because each has consumed effort and none is on the path:

- **Not BR-2 / the benchmark registry authority.** The BR-2 line ships contracts only at
  `0.2.3` and no cryptographic capability. It was ruled off the critical path on
  2026-08-25 and deliberately deferred. BR-2C, BR-2D and BR-2E are not required for
  anything described here `[V]`.
- **Not the ServiceNow integration.** `UGENCE_SERVICENOW_PRODUCT_ANCHORED_USE_CASES.md`
  and its companion describe a **proposed** integration and say so: *"no ServiceNow
  connector ships today,"* and every scenario is *"fictional but credible… none is an
  actual Ugence customer deployment"* `[V]`. They are positioning material, not a build
  target.
- **Not an external delivery.** No client-facing commitments, deadlines or claims arise
  from this pilot.

## 4. The one binding constraint carried over

No artifact, document or description may state that benchmark evidence is
cryptographically verified, trusted by BR-2C, production-authorized or independently
audited. Nothing in the repository provides that today, and the pilot does not change it
`[V]`.

This constrains claims, not work. Everything in §2 is unaffected.

## 5. What is undecided `[G]`

These are the real open questions. None is answered anywhere in the repository, and the
pilot cannot be planned without them:

1. **What does the pilot demonstrate?** "Execution governance" names a capability, not a
   scenario. Which decision, taken by which agent, over what subject matter, with what
   consequence if wrong?
2. **What is the app?** A console for watching governed execution, an operator tool for
   intervening in it, or a workbench for authoring policy? `apps/console` and
   `apps/ugence-governance-studio` both exist; neither is identified as the target.
3. **Who uses it?** An operator supervising agents, a governance owner reviewing after the
   fact, or a developer building governed workflows. This decides the app before anything
   else does.
4. **Does the API face outward?** A service API implies tenancy, authentication and
   stability commitments. An internal pilot may need none of them yet.
5. **What is "done"?** Without an external client there is no acceptance criterion. One
   has to be chosen deliberately or the pilot has no end.
6. **Which of the nine packages does it actually compose?** Agent Runtime is the kernel,
   but whether Risk Authority, Policy Authority, Action Clearance and ActionGate are all
   in the first cut is unstated.

## 6. Next decision

Question 1 gates the rest. A concrete scenario — one agent, one decision, one consequence
— makes questions 2 through 6 answerable in an afternoon. Without it, they cannot be
answered at all, and the pilot stays a capability list rather than a thing being built.

---

*Written from the repository state at default-branch head `0e31e295` and from owner
answers recorded 2026-08-25. Nothing here is ratified; the governance ledgers of the
individual packages remain the authority on their own contents.*
