# ADR — Ugence Policy Authority: One Shared Platform-Wide Policy Authority with Policy-Family Adapters

## 1. Status, date, baseline, scope, decision owners

- **Status:** **Accepted (ratified) — design-only.** This ADR records owner rulings on
  **ownership, naming, placement, and boundary**. Acceptance is of the *design*; the
  Policy Authority *implementation* remains a separate, future, reviewed milestone.
- **Date:** 2026-08-16.
- **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
  default head `df799c28` (merge of PR #1433, `feat(uvi): add deterministic readiness
  evaluator (GV-3R-b)`). PR #1435 (`claude/uvi-gv2c-policy-authority-3kpupf`, head
  `e53fcaf9`) is **open, draft, and unmerged**; it is **not modified by this ADR**.
- **Scope:** the **home, ownership, naming, and architectural boundary** of the Ugence
  Policy Authority, and the v0.1 rulings on approval separation, canonicalization,
  supersession, revocation, and registry/trust-anchor semantics.
- **Non-scope:** this ADR introduces **no runtime code, no contracts, no packages, no
  authority instance, and no behavior**, and changes **no** existing package, test,
  version, or `CONTRACT_VERSION`. It changes **architecture documentation only**.
- **Decision owners:** Ugence platform architecture owners for Policy Authority, Risk
  Authority, Decision Authority, Value Intelligence, Agent Runtime, and Runtime Assurance.
- **Related:**
  - [`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`](ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md)
    — D-1 (Policy Authority), D-16 (policy roles), §19, §20, §21, §26.1; amended for
    consistency alongside this ADR.
  - [`ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md`](ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md)
    — Risk Authority owns runtime authorization envelopes and their revocation; the
    boundary this ADR must not cross.
  - [`ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md)
    — the canonicalize-into-one-owner placement pattern this ADR mirrors.

> *This ADR changes **no** production code, package, wheel, public API, schema, frozen
> identifier, serialization, digest, or existing authority boundary. It assigns canonical
> ownership and records ratified rulings. Every implied code/package change is explicitly
> deferred to later, compatibility-controlled, separately-reviewed milestones. The
> platform-freeze substantive digest is unchanged before and after this ADR
> (`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).*

---

## 2. Context

The ratified UVI ADR records the **Ugence Policy Authority** as an *existing/planned*
capability and an **explicit required dependency** (D-1, D-16, §19), while §26.1 leaves
open the question the owner must answer: **who actually builds and owns it.** In the
interim, PR #1435 proposed `ugence-uvi-policy-authority` under
`packages/uvi-policy-authority/` — a **UVI-specific** authority — and its PR body asserts
that "ADR D-1's 'no UVI-specific Policy Authority' is superseded by the owner ruling for
this milestone."

An audit of PR #1435 exposed two classes of question that documentation, not code, must
answer first:

1. **Ownership / home.** Is the Policy Authority a UVI-owned leaf, or shared platform
   infrastructure? A UVI-specific authority contradicts D-1 as written, and — more
   importantly — guarantees a second authority is built the first time any non-UVI policy
   family needs issuance. This is the identical failure mode the Agent Workforce Composer
   ADR was written to prevent: *building a second selection system while one already
   exists*.
2. **Supersession.** The merged `supersedes_ref: str` is an **unstructured string** that
   cannot bind a complete exact `PolicyReference`. PR #1435 handles it with a configurable
   posture (`SELF_DECLARED_ONLY` ignores it; a strict mode fails closed with
   `SUPERSESSION_UNDETERMINED`). Both postures are defensible in isolation and both are
   wrong as a default: ignoring it leaves a superseded predecessor **trusted**, and strict
   uncertainty can render **every** version of an identity unusable.

This ADR resolves both, plus the approval, canonicalization, revocation, and registry
rulings the audit surfaced. It is deliberately **design-only** so the ownership question
is settled *before* an implementation is merged under a name that would be wrong.

---

## 3. Central decision

> **One shared, platform-wide Ugence Policy Authority — not a UVI-specific authority.**
> It is **internal platform infrastructure**, not a customer-facing module. UVI policy
> schemas are its **first supported policy family**, delivered through a **policy-family
> adapter**, not through UVI-specific semantics baked into the authority core.

The authority is the **technical** governance of approved policy artifacts: it proves
*who issued this exact artifact, under whose key, against which approval, and whether it
is currently valid*. It never decides whether a policy is **wise**, and it never
**approves its own** policy.

---

## 4. Ratified decisions P-1 … P-11

### P-1 — One shared platform authority
Ugence has exactly **one** Policy Authority, shared platform-wide across Ugence policy
domains. **No** UVI-specific Policy Authority. **No** per-capability authority fork.

### P-2 — UVI is the first policy family
UVI policy schemas (`GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`,
`ValuationPolicy`, `ReadinessPolicy`) are the **first supported policy family/adapter** of
the shared authority — a consumer of the boundary, not the owner of it.

### P-3 — Internal platform infrastructure
The Policy Authority is **internal platform infrastructure**. It is **not** a
customer-facing module, **not** a product, and **not** a fourth UVI engine. UVI remains
exactly one customer-facing capability (UVI ADR D-18).

### P-4 — Roles remain separate
Policy **authorship**, policy **approval**, **issuance/signing**, **resolution**, and
**runtime authorization** remain five distinct roles with distinct owners (§9). They are
never conflated, and no single component performs two adjacent roles for the same policy.

### P-5 — Approval remains external
Approval is produced **outside** the Policy Authority by a governance process. The Policy
Authority **cannot approve its own policy** and cannot act as both approving authority and
issuing authority for the same policy (§11).

### P-6 — v0.1 rejects unstructured supersession
Version 0.1 **must reject issuance** of any policy artifact carrying a **non-empty,
unstructured** `supersedes_ref`. Failure is a stable typed reason; nothing is signed or
registered (§13).

### P-7 — Structured successor references are deferred
Exact **structured** successor/predecessor references are **deferred to a separate
contract milestone** with its own review and its own owner ruling (§13.3).

### P-8 — Revocation is signed and verified
Policy-**version** revocation must be **signed**, **authority-controlled**, and
**verified during resolution** before it is applied (§14).

### P-9 — Shared core plus policy-family adapters
The authority is a **generic core** plus **policy-family adapters**. The core must not
hard-code any UVI policy semantics (§10).

### P-10 — Canonical naming and placement
`packages/policy-authority/` · distribution `ugence-policy-authority` · namespace
`ugence_policy_authority` · capability name **Ugence Policy Authority** (§8).

### P-11 — PR #1435 is salvage-only, and only after this ADR merges
PR #1435 may be salvaged **only** by renaming/repositioning it as the shared authority and
correcting its audited findings, and **only after this design decision merges** (§16).
This ADR does **not** approve PR #1435 and does **not** declare it merge-ready.

---

## 5. What the Ugence Policy Authority owns

The shared authority is responsible for the **technical governance of approved policy
artifacts** across Ugence policy domains. It owns:

| # | Owned responsibility |
|---|---|
| 1 | **Issuance** of policy artifacts into a governed, trusted form |
| 2 | **Cryptographic signing** of issued records under a configured authority key |
| 3 | **Exact version registration** (append-only) |
| 4 | **Exact reference resolution** |
| 5 | **Signature verification** |
| 6 | **Lifecycle / effective-period validation** |
| 7 | **Authorized-publisher and key-trust** management |
| 8 | **Policy-version revocation** |
| 9 | **Future structured supersession** (deferred — P-7) |

## 6. What the Ugence Policy Authority does **not** own

| # | Explicitly **not** owned | Owner instead |
|---|---|---|
| 1 | Authoring policy **content** | humans / authoring process |
| 2 | Deciding whether policy content is **beneficial or wise** | external governance process |
| 3 | **Self-approving** policy | structurally prohibited (P-5) |
| 4 | **Evidence admission** | evidence producers under UVI ADR D-8/D-9 |
| 5 | **Readiness evaluation** | `agent-value-readiness` (UVI ADR D-4) |
| 6 | **Deployment authorization** | human/deployment governance |
| 7 | **Runtime action authorization** | Risk Authority / ActionGate |
| 8 | **Condition enforcement** | readiness engine `ConditionSet` handling (UVI ADR D-7) |
| 9 | **Benchmark-value governance** | benchmark registry (UVI ADR D-3) — separate and deferred |
| 10 | **Forecasting** | deferred Value Forecasting engine (UVI ADR §24) |
| 11 | **Financial valuation** | `governed-value` |

A successful resolution proves **issuance authenticity and current validity**. It proves
**nothing** about whether the policy is wise, correct, lawful, or commercially sound.

> *Amendment (2026-08-17) — rows 4 and 9 redirect to named owners; both disclaimers stand.*
> Ratified by
> [`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md).
>
> **Row 4 — evidence admission.** The *disclaimer* is **upheld**: the Policy Authority does
> not own evidence admission. The *redirect* is **corrected**: **evidence producers produce
> evidence; they do not admit or verify it.** Naming producers as the owner of admission
> would ratify exactly the self-verification §11.4 forbids for approval and that UVI ADR
> §23.10 prohibits ("reference producers never self-attest/self-verify/self-approve").
> Evidence admission and verification are owned by **TAP — the Ugence Trusted Evidence
> Authority**, a platform-wide role distinct from `ugence-tap-provider`. UVI ADR D-8/D-9
> remain the correct reference for the evidence **classification axes** — which is what
> this row pointed at — and are unchanged.
>
> **Row 9 — benchmark-value governance.** **Upheld unchanged in substance**: still not the
> Policy Authority's, still deferred. The owner is now named — the **shared, platform-wide
> Ugence Benchmark Registry**. The Policy Authority **may** issue policies referencing
> **exact benchmark coordinates**; that is a citation, not ownership, and a policy
> reference to a benchmark is **not** proof that the benchmark resolved successfully.
> Benchmark **signing is not assigned to the Policy Authority**; any entitlement to act as
> a benchmark approval **verifier** must be explicit in the relevant authority contract.
>
> **P-1 … P-11, §11, §13, §14, §15 and the §20 ledger are unchanged.** Both capabilities
> remain **DEFERRED as implementation** — neither package exists.

---

## 7. Why shared, and why now

1. **D-1 is upheld rather than overridden.** D-1's prohibition on a UVI-specific Policy
   Authority was correct on its own terms; the shared authority satisfies it directly
   instead of requiring an exception (§15).
2. **Second-system prevention.** The first non-UVI policy family (Risk Authority policy,
   Decision Authority policy, model-selection policy, workflow policy) would otherwise
   either fork a second authority or bend UVI's authority into a de-facto platform one
   under a UVI name. Both outcomes are worse than deciding now.
3. **Naming is load-bearing.** A distribution named `ugence-uvi-policy-authority` publicly
   asserts UVI ownership of a platform boundary. Renaming after merge is a breaking
   distribution change; renaming before merge is free.
4. **The boundary is already platform-shaped.** Issuance, signing, key trust, exact
   registry semantics, and revocation contain **zero** UVI-specific content. Only artifact
   identity extraction, body projection, and structural validation are family-specific —
   exactly the adapter seam (§10).
5. **Deciding ownership costs nothing to defer implementation.** This ADR merges a
   decision, not a package.

---

## 8. Naming and placement ruling (P-10)

**Ratified canonical names**, unless a later merged convention requires a different
equivalent:

| Aspect | Canonical value |
|---|---|
| Package location | `packages/policy-authority/` |
| Distribution | `ugence-policy-authority` |
| Namespace | `ugence_policy_authority` |
| Capability name | **Ugence Policy Authority** |

**Explicitly prohibited:**

- `packages/uvi-policy-authority/` **as an independent authority owner**;
- `ugence-uvi-policy-authority` **as a separate platform authority**;
- a **fourth customer-facing UVI engine/module** for policy authority (UVI ADR D-18 holds:
  UVI's engines are Agent Value Readiness, Value Forecasting, and Governed Value
  Verification — the Policy Authority is **not** a fourth).

**Consequence for PR #1435:** if its implementation is retained, it **must be renamed and
repositioned** to the shared authority names above **before merge** (§16).

The placement mirrors the pattern ratified in the Agent Workforce Composer ADR:
canonicalize a shared concept into **one** owner, and let consumers depend on it through a
narrow, neutral seam rather than duplicating it.

---

## 9. Role separation matrix (P-4)

| Role | Owner |
|---|---|
| **Author** | Human / authoring process |
| **Approver** | External governance process |
| **Approval verifier** | Configured trust boundary (composition root) |
| **Issuer / signer** | Shared **Ugence Policy Authority** |
| **Registry / resolver** | Shared **Ugence Policy Authority** |
| **Policy-version revoker** | Shared **Ugence Policy Authority** |
| **Runtime authorizer** | **Risk Authority** / **ActionGate** |
| **Readiness evaluator** | **Agent Value Readiness** |
| **Financial calculator** | **Governed Value** |

No row may absorb another. In particular, *Approver* and *Issuer/signer* are **never** the
same component for the same policy (P-5), and *Issuer/signer* is **never** a runtime
authorizer (P-3, §17).

---

## 10. Shared core plus policy-family adapter architecture (P-9)

### 10.1 Split of responsibility

| Generic authority **core** provides | Policy-**family adapter** provides |
|---|---|
| approval-verification protocols | supported artifact types |
| signing / verifying protocols | identity & reference extraction |
| issued-policy envelopes | canonical body projection |
| exact registry semantics | body-digest calculation |
| trusted resolution | family-specific structural validation |
| key trust and key revocation | lifecycle / effective-period access |
| policy-version revocation | supersession-field interpretation |
| stable typed outcomes | — |

### 10.2 The hard boundary

The generic core **must not hard-code** readiness, `Geography`, `Domain`,
`IntendedOutcome`, `Valuation`, or any other UVI policy semantics **outside the UVI
adapter**. A second policy family must be addable by registering a second adapter — with
**no** change to core issuance, signing, registry, resolution, or revocation logic.

**UVI policy contracts are the first adapter.** They are registered with the core; they do
not extend it.

### 10.3 Packaging of the first distribution

**Ratified:** the first distribution **may contain the UVI adapter internally** for v0.1,
provided the **core/adapter boundary is preserved in code** — the adapter sits behind the
registered-adapter protocol, and the core contains no import of, or branch on, a UVI type.

The objective is **one authority capability, not module proliferation**. A second
distribution (e.g. splitting the UVI adapter out) is **not** introduced unless technically
necessary, and is a separately-reviewed compatibility decision — **not** a precondition of
the first implementation.

### 10.4 Dependency direction

```
governance-contracts            (depends on nothing)
        ▲                    ▲
        │                    │
uvi-policy-contracts    ugence-policy-authority  (core + registered family adapters)
        ▲                    │
        │                    └── uvi-policy-contracts   (first family adapter, by value)
        │
   UVI engines (agent-value-readiness, governed-value, …)
        │
        └── consume EXACT RESOLVED policy artifacts (by value, digest-bound)
            ✗ never import ugence_policy_authority internals
```

**Invariants.** UVI engines consume **exact resolved policy artifacts**; they do **not**
import authority internals. This preserves UVI ADR §21 ("No leaf imports a Policy
Authority internal — policies arrive as signed, digest-bound artifacts"). The authority
imports **no** engine: not `agent-value-readiness`, not `governed-value`, not Risk /
Decision Authority internals, not Agent Runtime, Runtime Assurance, forecasting, or the
benchmark-value service.

---

## 11. Approval and issuance separation (P-5)

**Ratified:**

1. **Humans or an external governance process author policy.**
2. A **separate approving authority/process approves the exact content digest** — approval
   binds a digest, not a name, not an intent.
3. The Policy Authority accepts approval **only** through a **configured trusted
   approval-verification boundary**.
4. **Not approval:** a caller Boolean; a lifecycle enum on the artifact (e.g.
   `APPROVED_ACTIVE`); a bare authority **name**; a caller-created verification label; any
   evidence-status enum.
5. **No production allow-all verifier may ship.** The only verifier permitted in production
   code is one that **denies by default**; permissive verifiers exist only under `tests/`.
6. The **composition root owns approval-verifier trust** — the trust decision is made where
   the application is wired, not inside the authority and not by the caller of issuance.
7. The Policy Authority **cannot act as both approving authority and issuing authority for
   the same policy**. Approver ≠ issuer is checked by the authority itself, not merely
   assumed of the verifier.
8. **Signing proves issuance** under a configured authority key. It does **not** prove
   policy wisdom or business correctness.

A lax or compromised verifier must still be unable to get a **mismatched** or
**self-approved** policy issued: the authority independently re-checks that the
verification binds the exact policy identity, version, family, tenant/scope, body digest,
approving authority, and approval artifact.

---

## 12. Canonicalization ownership (P-9)

**Ratified:**

1. **Canonicalization is versioned and domain-separated.** Every digest and every signed
   payload binds a canonicalization version and a domain-separation tag.
2. The **generic core delegates canonical policy-body construction to the registered
   policy-family adapter**. The core never canonicalizes a family artifact itself.
3. The **UVI adapter's v1 projection may exclude only the self-referential declaration
   field** `metadata.content_digest`. That field is **removed, not blanked** — one pass, no
   fixed-point iteration.
4. **All other governed policy content remains bound**, including every metadata identity
   field.
5. The **declared digest must equal the computed adapter digest before issuance**. A
   mismatch fails closed; nothing is signed or registered.
6. **Signature fields never participate in the policy-body digest.**
7. **No fixed-point or sentinel digest algorithm is allowed.**
8. **Independent verification must be possible** through public adapter/authority
   verification functions — a third party holding the artifact and the public functions can
   recompute and check the digest without authority internals.

### 12.1 Unicode normalization and naive datetimes

Recorded explicitly, because leaving it implicit is how digest equivalence silently breaks:

- **Unicode normalization.** The implementation must choose **one** of:
  **(a)** require canonical **normalized** strings and **reject non-canonical input** at the
  authority boundary; or **(b)** define canonical normalization as **part of the digest
  equivalence relation**, applied identically by issuance and by independent verification.
  The choice is versioned with the canonicalization version. Mixing the two, or leaving it
  unspecified, is prohibited.
- **Naive datetimes.** **Preference: reject naive datetimes at the authority boundary.** A
  datetime without an explicit offset is not a well-defined instant and must not enter a
  signed payload, an effective period, or a digest.

### 12.2 Future movement of the canonicalization helper

Moving the UVI canonicalization helper into `uvi-policy-contracts` is a **separately
reviewed compatibility decision**. It is **not required** for the first authority
implementation, and this ADR neither mandates nor forbids it.

---

## 13. Supersession ruling (P-6, P-7)

### 13.1 The v0.1 rule

> **The shared Policy Authority must reject issuance of a policy artifact containing a
> non-empty unstructured `supersedes_ref`.**

### 13.2 Rationale

- `supersedes_ref: str` **cannot bind a complete exact `PolicyReference`** — it carries no
  family, tenant, identity, version, and digest tuple.
- Accepting it under a **self-declared/default** posture allows the **predecessor to remain
  trusted** — the string is recorded but nothing invalidates the prior version, so a
  resolver still returns the superseded policy as valid.
- Treating it as **strict uncertainty** can make **every version of the identity
  unusable** — an unresolvable claim poisons the identity rather than the one artifact.
- **Guessing is prohibited**: by string match, by ID, by version ordering, or by any
  "latest" lookup. A guessed supersession is an unsigned authority decision.

Rejecting at **issuance** is the only posture that neither leaves a stale policy trusted
nor poisons an identity: the ambiguous artifact never enters the system at all.

### 13.3 Required behavior

| Aspect | Required |
|---|---|
| Outcome | issuance **fails** with a **stable typed** reason — `SUPERSESSION_REFERENCE_UNSUPPORTED` or equivalent |
| Signing | **no record is signed** |
| Registration | **no record is registered** |
| Blast radius | **existing unrelated policy versions remain unaffected** |
| Resolution | **no resolution-time guessing occurs** — ever |

An **empty/absent** `supersedes_ref` is unaffected and issues normally. No existing merged
contract shape changes: the field remains as merged; the authority simply refuses to issue
artifacts that populate it until §13.4 lands.

### 13.4 Deferred to a separate contract milestone (P-7)

The following are **DEFERRED** and require their own contract review and owner ruling:

1. an **exact structured** successor/predecessor reference;
2. **successor authorization** — who may supersede what;
3. the **activation instant** of a supersession;
4. **predecessor invalidation** semantics;
5. **historical resolution** across a supersession boundary;
6. **cross-tenant / cross-family** supersession restrictions.

---

## 14. Revocation ruling (P-8)

**Ratified:**

1. **Policy-version revocation is distinct** from **key revocation** and from **Risk
   Authority envelope revocation**. Three different things; three different owners of the
   act; never conflated.
2. **Every revocation record must be signed.**
3. The **revoking authority must be authorized for the exact policy scope**.
4. **Unsigned revocation is invalid** — it is not "revocation pending", it is not applied.
5. The **issuer's identity must never be silently substituted as the revoker.** A missing
   revoker is an error, not a defaulting opportunity.
6. **A foreign signer cannot revoke without explicit authorization**, even with a
   structurally valid signature.
7. **Resolution must verify the revocation signature and authority entitlement *before*
   applying it.** An unverified revocation record does not deny, and does not allow — it
   fails closed as an integrity error.
8. **Revocation records are append-only and immutable.**
9. **Default operational resolution denies revoked policy.**
10. **Historical resolution**, if explicitly enabled, must **preserve and disclose the
    historical `as_of` instant** and must **not imply current validity**. A historical
    answer is labelled as historical in the result.

---

## 15. Registry and trust-anchor ruling

**Ratified:**

1. **Exact reference resolution only.**
2. **No trusted floating/latest lookup.** A floating reference must be *unrepresentable*,
   not merely discouraged — no `latest()`, `current()`, or `find_by_id()` on the trusted
   path.
3. **Append-only issuance.**
4. **Immutable trust anchors.**
5. **Key rings defensively copy caller mappings and expose immutable views** — a caller
   that mutates the mapping it passed in must not be able to alter the authority's trust
   state after construction.
6. Reference **in-memory registry operations must either enforce synchronization or must
   not claim atomic/thread-safe behavior.** Documenting an unsynchronized structure as
   atomic is prohibited.
7. **Production persistence and distributed concurrency remain DEFERRED** — the reference
   registry is reference-grade, with no durability, replication, or operational story.
8. **Raw registry retrieval never equals trusted resolution.** A record fetched from
   storage has proved nothing until digest, key, signature, lifecycle, effective period,
   revocation, and scope checks pass.

---

## 16. Relationship to the ratified UVI ADR — D-1 consistency

### 16.1 D-1 is upheld, not weakened

D-1 states that "the existing/planned **Ugence Policy Authority** owns policy approval,
signing/issuance, authorized publishers, effective periods, supersession, and revocation …
**No** UVI-specific Policy Authority and **no** new customer-facing module."

This ADR **satisfies D-1 exactly as written**:

| D-1 clause | This ADR |
|---|---|
| "the existing/planned **Ugence Policy Authority** owns …" | **P-1** — that authority is now concretely defined, shared, and platform-wide (§5) |
| "**No** UVI-specific Policy Authority" | **P-1, P-10** — upheld and strengthened; a UVI-specific authority is explicitly prohibited by name (§8) |
| "**no** new customer-facing module" | **P-3** — internal platform infrastructure; UVI keeps three engines, not four |
| "recorded as an **explicit required dependency**" | **§16.3** — remains an external platform dependency of UVI engines |
| "must never self-approve or self-sign" | **P-5, §11** |
| "**fail closed** on unsigned/unapproved/expired/revoked/superseded/digest-mismatched artifacts" | **§11, §13, §14, §15** |

**D-1 is not weakened to permit a separate UVI authority.** No exception, override, or
supersession of D-1 is granted or implied by this ADR. Any assertion elsewhere that D-1 is
"superseded by the owner ruling for this milestone" is **not** ratified.

### 16.2 §26.1 is resolved

UVI ADR §26.1 ("Policy Authority for UVI value-policies — owner to confirm the
existing/planned Policy Authority assumes these") is **RESOLVED** by this ADR: the
**platform-wide Ugence Policy Authority owns it**, and **UVI is the first policy-family
adapter**.

### 16.3 The dependency direction is unchanged

The Policy Authority remains an **external platform dependency** of UVI engines. UVI
engines consume exact resolved policy artifacts by value; they do not import authority
internals (§10.4). UVI ADR D-2…D-18 and all readiness/evidence/valuation semantics are
**unchanged**.

### 16.4 Milestone naming

Any milestone reference for building the shared authority is a **platform dependency
milestone**, **not** a UVI engine milestone. It is **not** "GV-2C-b as a UVI-owned
authority milestone" — UVI's milestones (UVI ADR §25) are unchanged.

---

## 17. Lifecycle flow

```
   author            approve              verify              issue /
   policy   ─────▶   the EXACT   ─────▶   approval   ─────▶   sign
   content           digest               at trust            (authority key)
                                          boundary
  (human /         (external            (configured        (Ugence Policy
   authoring        governance           composition-        Authority)
   process)         process)             root verifier)
                                                                  │
                                                                  ▼
   consume          resolve /            register exact
   by value  ◀────  verify       ◀────   version
   (UVI engines,    (exact ref only;     (append-only)
    digest-bound)    sig + digest +      (Ugence Policy Authority)
                     lifecycle +
                     revocation)
        │
        └───────▶  revoke (signed, authorized, verified at resolution)
                   supersede (DEFERRED — structured reference, §13.4)
```

**Status legend for this flow:** every stage above is **RATIFIED as design**. **None** is
**IMPLEMENTED** in the shared authority — no `ugence-policy-authority` package exists at
`df799c28`. **Supersession is DEFERRED** (P-7). Planned integration must not be presented
as already implemented.

---

## 18. Required disposition of PR #1435

PR #1435 is **open, draft, and unmerged**, and is **not modified by this ADR**. This ADR
does **not** approve it and does **not** declare it merge-ready.

**PR #1435 may proceed only after this design PR merges, and only after it:**

1. **renames** the package / distribution / namespace to the shared authority
   (`packages/policy-authority/`, `ugence-policy-authority`, `ugence_policy_authority`);
2. **describes UVI as its first adapter**, behind the registered-adapter seam (§10);
3. **removes UVI-specific authority ownership claims**, including the assertion that D-1's
   "no UVI-specific Policy Authority" is superseded (§16.1);
4. **rejects unstructured supersession at issuance** with a stable typed reason, replacing
   the configurable `SELF_DECLARED_ONLY` / `SUPERSESSION_UNDETERMINED` posture (§13);
5. **requires signed, authorized revocation and verifies it during resolution** (§14);
6. **makes key-ring storage immutable** — defensive copy plus immutable view (§15.5);
7. **resolves the remaining audited findings**;
8. **preserves the technically sound approval, digest, signature, issuance, registry, and
   resolver work where compatible** — the audit's objection is to *ownership, naming, and
   the supersession/revocation/key-ring defaults*, not to that machinery.

---

## 19. Compatibility and dependency rules

Recorded, and unchanged by this ADR:

1. **Existing UVI policy contract shapes remain unchanged** in this design PR — including
   `supersedes_ref` as merged.
2. **Existing readiness behavior remains unchanged.**
3. **`governed-value` remains unchanged.**
4. **No existing authority imports the new authority implementation.** There is nothing to
   import; and when there is, the direction stays one-way.
5. **Risk Authority continues to own runtime authorization envelopes** — and their
   revocation, per the RA-6 ADR.
6. **Decision Authority continues to own decision cases** — it approves decision cases, not
   policy artifacts.
7. **ActionGate continues to enforce action authorization.**
8. **The shared Policy Authority must not become a runtime decision maker.** It is consulted
   before runtime, by resolution; it never sits on the hot path as an authorizer.
9. **Benchmark-value authority remains separate and DEFERRED** (UVI ADR D-3, M-2C.2).

---

## 20. Status ledger — RATIFIED / IMPLEMENTED / DEFERRED

Every claim in this ADR carries exactly one status. Nothing below is implemented.

| Item | RATIFIED | IMPLEMENTED | DEFERRED |
|---|---|---|---|
| One shared platform-wide Policy Authority (P-1) | ✅ | ❌ | — |
| UVI as first policy family / adapter (P-2) | ✅ | ❌ | — |
| Internal platform infrastructure, not customer-facing (P-3) | ✅ | n/a | — |
| Five separate roles (P-4, §9) | ✅ | ❌ | — |
| External approval; no self-approval (P-5, §11) | ✅ | ❌ | — |
| Canonical names and placement (P-10, §8) | ✅ | ❌ | — |
| Core + family-adapter architecture (P-9, §10) | ✅ | ❌ | — |
| UVI adapter may ship inside the first distribution (§10.3) | ✅ | ❌ | — |
| Versioned, domain-separated canonicalization (§12) | ✅ | ❌ | — |
| Unicode-normalization posture choice (§12.1) | ✅ (as a required choice) | ❌ | implementation selects and versions it |
| Reject naive datetimes at the boundary (§12.1) | ✅ (preference) | ❌ | — |
| Reject non-empty unstructured `supersedes_ref` at issuance (P-6, §13) | ✅ | ❌ | — |
| Structured successor reference + activation + invalidation (P-7, §13.4) | — | ❌ | ✅ separate contract milestone |
| Signed, authorized, resolution-verified revocation (P-8, §14) | ✅ | ❌ | — |
| Historical resolution disclosure (§14.10) | ✅ | ❌ | — |
| Exact-only resolution, append-only, immutable anchors (§15) | ✅ | ❌ | — |
| Immutable key-ring views (§15.5) | ✅ | ❌ | — |
| Production persistence, distributed concurrency, HSM/KMS (§15.7) | — | ❌ | ✅ deployment milestone |
| Benchmark-value governance (§19.9) | — | ❌ | ✅ UVI ADR D-3 / M-2C.2 |
| Moving the UVI canonicalization helper into `uvi-policy-contracts` (§12.2) | — | ❌ | ✅ separately reviewed |
| Forecasting, attribution, verification, readiness integration, financial valuation | — | ❌ | ✅ out of scope entirely |

---

## 21. Open items for the implementation milestone

These are **implementation details only** — none alters the ownership or boundary
ratified above:

1. Which Unicode-normalization posture (§12.1 (a) or (b)) the implementation selects.
2. The exact typed-reason vocabulary, beyond the requirement that
   `SUPERSESSION_REFERENCE_UNSUPPORTED` (or an equivalent stable identifier) exists.
3. Whether the UVI adapter is registered statically or via an explicit registration API.
4. The signing algorithm and key-management shape for production (the reference signer is
   not a production posture).
5. The persistence and concurrency design for a non-reference registry (§15.7).

---

*Design-only ADR. No runtime behavior, no authority minted, no contracts or packages
created, no test or version changed, and no modification to PR #1435. Implementation
requires separate reviewed phases.*
