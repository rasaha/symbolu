# Risk Authority RA-4.5 — Production Authority Adapter Plan

**Status: DESIGN / NOT IMPLEMENTED**

This document records the agreed architecture for a *future* Risk Authority
RA-4.5 work item. It is a design artifact only. Nothing described under
"PLANNED / RA-4.5" headings is shipped, wired, or scheduled by the act of
writing this document.

## Authoring context (point-in-time facts)

At the time this plan was authored:

- The Risk Authority **RA-1 → RA-4** authority spine lives in **PR #1396**
  (branch `claude/risk-authority-audit-3r6ffs`, head
  `16056fb0b0e7794df7291ac852bc171fd1b09c54`).
- **PR #1396 is OPEN, DRAFT, CI-green, and NOT MERGED.** Therefore the
  `packages/risk_authority` code this plan refers to is **not present on the
  default branch yet**. This document may describe capabilities introduced by
  PR #1396, but those capabilities are *proposed-and-in-review*, not merged.
- The following audit findings were already **resolved** inside PR #1396:
  **F-A** (forged `RiskEvaluation` / non-compensatory bypass), **F-B** (expired
  `RiskDecision` minting fresh authority), **F-C** (Decision Authority ownership
  ambiguity), **F-E** (duplicate-control masking).
- The following are **tracked separately** as non-blocking follow-ups:
  **#1397** (F-D scope enforcement), **#1398** (F-G trusted-clock / key-window),
  **#1399** (F-H governance-event-chain integrity).

RA-4.5 does not begin until PR #1396 is reviewed and merged (see §17).

---

## 1. Architectural objective

**RA-4.5 objective:** replace the Risk Authority *conformance / reference*
Decision Authority and ActionGate implementations, **in production
composition**, with **adapters to the canonical shipped Ugence kernels**, while
preserving Risk Authority as an **independently installable, stdlib-only leaf**.

Conceptual target architecture:

```
                    ugence-risk-authority
                    (stdlib-only leaf)
                           │
                 ┌─────────┴─────────┐
                 │                   │
                 ▼                   ▼
      DecisionAuthorityPort      ActionGatePort
                 ▲                   ▲
                 │                   │
                 └─────────┬─────────┘
                           │
                           ▼
             Production integration package
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
KernelDecisionAuthorityAdapter   KernelActionGateAdapter
              │                         │
              ▼                         ▼
ugence-decision-authority      ugence-actiongate-provider
```

The integration-package name is **tentative** and subject to repository naming
conventions. A tentative working name is **`ugence-risk-authority-runtime`**;
this is **not finalized** and must be reconciled with the monorepo's package
layout (`packages/…`) at RA-4.5 kickoff.

---

## 2. Core architectural invariant

**`risk_authority` MUST remain a stdlib-only leaf.**

Therefore `risk_authority` (the package rooted at `packages/risk_authority`)
must **NOT** directly import:

- `ugence_decision_authority`
- `ugence_actiongate_provider`

Production adapters belong **outside** the leaf package, in the separate
integration package.

Why this invariant is load-bearing:

- **Isolated distribution stays independently verifiable** — the single-wheel,
  `--no-index`, zero-dependency install proof continues to hold.
- **Authority contracts stay portable** — the ports (`DecisionAuthorityPort`,
  `ActionGatePort`) can be satisfied by any conforming implementation, not only
  the platform kernels.
- **Risk Authority does not become coupled to platform orchestration** — the
  leaf never transitively pulls in the platform's dependency graph.
- **Reference / conformance behavior stays independently testable** — the
  deterministic reference implementations remain usable for tests and
  standalone demonstrations without the kernels present.
- **Production composition stays explicit** — wiring the production kernels is a
  deliberate, visible act in the integration layer, never an implicit import
  side effect.

---

## 3. Current reference architecture (CURRENT / IMPLEMENTED IN RA-1 → RA-4)

> Implemented in PR #1396 (in review, not merged). Accurate description of the
> arrangement as of head `16056fb0`.

```
RiskAuthorityApplication
        │
        ├── DecisionAuthorityPort
        │        └── ReferenceDecisionAuthority
        │
        └── ActionGatePort
                 └── ReferenceActionGate
```

Explicit statements:

- **`ReferenceDecisionAuthority` is NOT the canonical production Decision
  Authority.** The canonical production binding-decision implementation is
  **`ugence-decision-authority`** (`packages/capabilities/decision-authority`).
- **`ReferenceActionGate` is NOT the canonical production ActionGate.** The
  canonical production exact-action enforcement provider is
  **`ugence-actiongate-provider`**.

The reference implementations exist for:

- conformance;
- isolated testing;
- deterministic protocol verification;
- standalone distribution verification.

They must not be confused with production platform authority. Their presence in
the leaf is exactly what lets RA-1 → RA-4 be proven in isolation; it is not a
claim that the leaf *is* the platform's authority stack.

---

## 4. RA-4.5 production composition (PLANNED / RA-4.5)

Intended production authority path once the adapters exist:

```
WorkflowIR
    ↓
RiskDecisionCase
    ↓
Control evaluation
    ↓
Risk recommendation / evidence
    ↓
DecisionAuthorityPort
    ↓
KernelDecisionAuthorityAdapter
    ↓
ugence-decision-authority
    ↓
binding RiskDecision
    ↓
RiskAuthorizationEnvelope
    ↓
ActionGatePort
    ↓
KernelActionGateAdapter
    ↓
ugence-actiongate-provider
    ↓
ALLOW / DENY
```

Authority ownership must stay precise:

- Risk Authority orchestrates and binds; it **must not silently become the
  canonical Decision Authority**. The binding ruling is owned by
  `ugence-decision-authority`, reached through `DecisionAuthorityPort`.
- **ActionGate remains the exact-action enforcement boundary.** The canonical
  enforcement is `ugence-actiongate-provider`, reached through `ActionGatePort`.

---

## 5. Dependency inversion

Production integration follows dependency inversion:

- **Risk Authority defines the ports.**
- **The integration layer implements the ports.**
- **The canonical kernels remain independently owned** by their own packages.

Not: "Risk Authority imports every platform component."

Intended dependency direction:

```
risk_authority
      ▲
      │
risk_authority_runtime  (integration package; tentative name)
      │
      ├── decision-authority
      └── actiongate-provider
```

There must be **no reverse dependency** from the canonical kernels
(`ugence-decision-authority`, `ugence-actiongate-provider`) *into* Risk
Authority unless separately justified and reviewed. The kernels do not know
about Risk Authority; the integration package knows about all three.

---

## 6. DI seam (PLANNED / RA-4.5 — not implemented here)

The expected future dependency-injection seam in the application facade:

```
RiskAuthorityApplication(
    decision_authority=...,   # DecisionAuthorityPort
    action_gate=...,          # ActionGatePort
)
```

- Reference defaults (`ReferenceDecisionAuthority`, `ReferenceActionGate`) may
  remain the defaults, useful for: tests, conformance, standalone
  demonstrations, and isolated single-wheel verification.
- **Production composition must explicitly inject production adapters** built in
  the integration package.

This DI seam is **not implemented in this documentation task** and is not part
of PR #1396's committed scope. It is the expected first code change of RA-4.5
(a small, leaf-safe parameterization that adds no new dependency). Whether it is
folded into PR #1396 or introduced at RA-4.5 kickoff is a reviewer decision;
the default assumption is RA-4.5.

---

## 7. Phase 1 — semantic parity audit (mandatory first RA-4.5 phase)

Before any adapter is written, RA-4.5 must compare the reference semantics with
the shipped kernels' semantics. This is the highest-risk part of RA-4.5: the
correctness of the whole integration rides on it.

Planned parity matrix — one row per dimension, at minimum:

| Dimension | Reference semantics | Kernel semantics | Equivalent? | Kernel stricter? | Reference stricter? | Mapping required? | Blocking gap? |
|---|---|---|---|---|---|---|---|
| tenant | | | | | | | |
| actor | | | | | | | |
| model | | | | | | | |
| purpose | | | | | | | |
| tool allow-set | | | | | | | |
| tool deny-set | | | | | | | |
| data allow-set | | | | | | | |
| data deny-set | | | | | | | |
| destination | | | | | | | |
| amount / value ceiling | | | | | | | |
| conditions | | | | | | | |
| human approval | | | | | | | |
| delegation monotonicity | | | | | | | |
| authority scope | | | | | | | |
| workflow / policy digest | | | | | | | |
| authority epoch | | | | | | | |
| revocation | | | | | | | |
| issued-at | | | | | | | |
| expiry | | | | | | | |
| payload / action binding | | | | | | | |
| risk class | | | | | | | |
| autonomy | | | | | | | |
| jurisdiction | | | | | | | |
| resource / target | | | | | | | |

Rule: **do not assume semantic equivalence merely because fields have similar
names.** A field named `tenant` in both models is not proof the enforcement
semantics match; each row must be validated by reading the kernels.

---

## 8. Decision Authority adapter (PLANNED / RA-4.5)

`KernelDecisionAuthorityAdapter` maps Risk Authority's port/domain
representation onto the canonical `ugence-decision-authority` kernel and maps the
binding ruling back to Risk Authority's `RiskDecision`.

**Critical invariant — the F-A fix must survive adapter integration.** No
adapter may reintroduce the path:

```
caller-supplied RiskEvaluation → trusted directly → binding ALLOW
```

The binding recommendation must continue to derive from **authoritative
state / control evidence** according to the accepted RA-1 → RA-4 semantics, not
from a caller-provided recommendation.

The adapter must also preserve:

- delegation monotonicity: `Scope_issued ⊆ Scope_delegated`;
- tenant, policy/workflow-digest, and time bindings;
- the fail-closed disposition of DENY / ESCALATE outcomes.

If the kernel's decision contract cannot represent one of these guarantees, that
is a **blocking parity gap** to resolve at the architecture level — not a
license to relax the guarantee.

---

## 9. ActionGate adapter (PLANNED / RA-4.5)

`KernelActionGateAdapter` maps:

```
RiskAuthorizationEnvelope + CanonicalAction
```

onto the canonical `ugence-actiongate-provider` request/artifact model, and maps
the provider's result back to `ActionAuthorization`.

The adapter must **preserve or strengthen** every reference enforcement
dimension:

- tenant binding
- actor binding
- model binding
- purpose binding
- tool restrictions (allow and deny)
- data restrictions (allow and deny)
- destination restrictions
- amount ceiling
- conditions
- payload / action identity
- time validity
- revocation
- authority epoch

**The production adapter must never weaken reference enforcement semantics
merely to make integration convenient.** If the production kernel cannot
represent a required Risk Authority semantic, that is a **blocking parity gap**,
not permission to drop the restriction.

---

## 10. Differential conformance (PLANNED / RA-4.5)

RA-4.5 must run the same authority scenarios through both stacks:

- reference stack: `ReferenceDecisionAuthority` + `ReferenceActionGate`;
- production stack: `KernelDecisionAuthorityAdapter` + `KernelActionGateAdapter`.

Expectation: **identical ALLOW / DENY disposition** for every semantic intended
to be equivalent.

Where the production kernels are **deliberately stricter**, the case:

```
Reference = ALLOW
Production = DENY
```

is acceptable **only when explicitly documented and justified**. Production must
**never** become *less* restrictive than the reference without an approved
architecture change.

---

## 11. Preserve known fixes (PLANNED / RA-4.5)

RA-4.5 must carry forward regression coverage for the resolved findings, and
these regressions must run **against the production-adapter path**, not merely
the reference path:

- **F-A** — a forged / caller-supplied ALLOW cannot bypass a required-control
  failure.
- **F-B** — an expired `RiskDecision` cannot mint fresh authority.
- **F-E** — duplicate control results cannot mask a failure.

---

## 12. Existing follow-ups

Tracked, not solved by RA-4.5's core scope:

- **#1397 — F-D** — `jurisdiction`, `autonomy`, and `resource / target`
  currently participate **incompletely** in runtime ActionGate enforcement (the
  reference `CanonicalAction` has no matching fields; these dimensions bound
  issuance-time monotonicity but are not matched against a presented action).
- **#1398 — F-G** — trusted-clock seam and unenforced signing-key validity
  windows.
- **#1399 — F-H** — governance event chain is tamper-*evident* (unsigned hash
  chain), not tamper-*proof*.

**F-D is not solved in this design-document task.** However, the RA-4.5 Phase 1
parity audit (§7) **must determine whether `ugence-actiongate-provider` already
provides suitable jurisdiction / autonomy / resource semantics** before any new
`CanonicalAction` extension is designed. This ordering prevents duplicating
enforcement that the production provider may already implement.

---

## 13. Signing architecture

The existing pure-Python Ed25519 implementation in `risk_authority` is a
**reference / conformance signing implementation**. It is *not* evidence of
production HSM readiness.

Future production signing may use a KMS, HSM, managed signing service, or other
vetted cryptographic backend, **behind the existing signing abstraction**
(`SigningKey` / `VerifyKey`).

RA-4.5 must **not** require production signing changes unless semantic
integration with the kernels demands them. Signing-backend modernization is kept
**separable** from authority-adapter correctness so the two can be reviewed and
shipped independently.

---

## 14. Verification requirements (PLANNED / RA-4.5)

Minimum bar for a future RA-4.5 implementation.

**Existing Risk Authority package** — the standalone leaf must continue to pass:

- all Risk Authority tests;
- isolated single-wheel installation;
- zero undeclared runtime dependencies;
- RFC 8032 reference verification;
- the deny-heavy conformance suite.

**Production integration package** — adds its own verification covering:

- Decision Authority adapter;
- ActionGate adapter;
- semantic parity;
- differential conformance;
- cross-tenant denial;
- scope-expansion denial;
- expired-authority denial;
- revoked-authority denial;
- payload-substitution denial;
- policy / workflow-substitution denial;
- F-A regression;
- F-B regression;
- F-E regression.

**Packaging** — must prove:

- `risk_authority` remains **independently installable without the production
  kernels**;
- the integration package **may** depend on the canonical kernels.

---

## 15. Explicit RA-4.5 non-goals

RA-4.5 must **not** become a vehicle for any of:

- RA-5+;
- TAP expansion;
- Control Assurance;
- Trajectory Control;
- ACP;
- Reconciliation;
- Cloud Scaling;
- GRC dashboards;
- Agent Runtime redesign;
- Decision Authority redesign;
- ActionGate redesign;
- general policy-engine redesign.

RA-4.5 is narrowly:

```
REFERENCE PORTS  →  PRODUCTION KERNEL ADAPTERS
```

---

## 16. Production maturity gate

RA-1 → RA-4 can be a valid **conformance / reference implementation** *without*
claiming **production authority integration complete**.

Precise maturity language:

- Passing tests and green CI on the reference spine demonstrate **conformance
  correctness of the reference implementation** — nothing more.
- **Production maturity requires successful RA-4.5 integration and verification
  against the canonical kernels** (`ugence-decision-authority`,
  `ugence-actiongate-provider`).

Do not call the reference spine "production-ready" solely because its tests and
CI pass.

---

## 17. Sequence

Intended order of operations:

```
PR #1396 reviewed
        ↓
PR #1396 merged
        ↓
RA-4.5 plan rebased onto merged default
        ↓
semantic parity audit  (§7)
        ↓
architecture gaps resolved
        ↓
production adapters implemented  (§8, §9)
        ↓
differential conformance  (§10)
        ↓
production integration PR
        ↓
only then RA-5+
```

This sequencing is important: adapters are not designed until the parity audit
has classified every dimension, and RA-5+ does not begin until the
reference → production swap is proven against the canonical kernels.
