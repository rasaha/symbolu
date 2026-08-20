# ADR — Ugence Trusted Evidence Verification and the Shared Benchmark Registry

## 1. Status, date, baseline, scope, decision owners

- **Status:** **Accepted (ratified) — design-only.** This ADR records owner rulings on
  **ownership, role separation, naming, placement, and boundary** for two distinct
  platform responsibilities: **trusted evidence verification** and the **Benchmark
  Registry**. Acceptance is of the *design*. Every runtime capability described here
  remains a separate, future, separately-reviewed milestone.
- **Date:** 2026-08-17.
- **Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
  default head **`d905c5515de5e18008c78298361e69820ab23109`** (merge of PR #1440,
  `fix(governance): harden assessed-system binding canonicalization`). Agent Readiness
  M-3R.1 → M-3R.3, PR #1440 (system-binding hardening) and PR #1432 (Risk Authority
  v2 subject-context contracts, `aa8a526e`) are merged and reachable from this head.
  PR #1441 (Cloud Scaling Phase 4B) is **open, draft, unmerged**, is a **separate
  workstream**, is **not a prerequisite** for this ADR, and is **not modified by it**.
- **Scope:** the **owner, home, naming, and architectural boundary** of (a) trusted
  evidence admission and verification, and (b) admitted benchmark definitions, their
  lifecycle and their trusted resolution — plus the v0.1 rulings on role separation,
  refusal semantics, receipts, canonicalization, supersession, and revocation.
- **Non-scope:** this ADR introduces **no runtime code, no contracts, no packages, no
  authority instance, no public API, and no behavior**. It changes **no** package
  source, test, workflow, `pyproject.toml`, `public_api.json`, package README/CHANGELOG,
  generated artifact, version, or `CONTRACT_VERSION`. It changes **architecture
  documentation only**.
- **Decision owners:** Ugence platform architecture owners for Trust Assurance, Policy
  Authority, Risk Authority, Decision Authority, Value Intelligence, Governance
  Contracts, Agent Runtime, and Runtime Assurance.
- **Related:**
  - [`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`](ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md)
    — D-3 (benchmark registry), D-8/D-9 (evidence axes), D-14 (assessed system),
    D-16 (roles), §19, §20, §21, §26.5; amended additively alongside this ADR.
  - [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — P-4, P-5, P-8,
    §6, §11, §14, §15, §19.9, §20; the approval/issuance/registry pattern this ADR
    mirrors, and whose §6 row 4 is reconciled additively.
  - [`ADR_RISK_AUTHORITY_RA5_EVIDENCE_CONTROL_ASSURANCE.md`](ADR_RISK_AUTHORITY_RA5_EVIDENCE_CONTROL_ASSURANCE.md)
    and [`RISK_AUTHORITY_RA5_SPEC.md`](RISK_AUTHORITY_RA5_SPEC.md) — the **ratified**
    RA-scoped Evidence Admission seam and the ratified "TAP is the conceptual umbrella"
    naming decision (RA-5 SPEC §3.2), which this ADR **preserves and extends, never
    reopens**.
  - [`ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md`](ADR_RISK_AUTHORITY_RA6_AUTHORITY_LIFECYCLE.md)
    — Risk Authority owns runtime authorization envelopes and their revocation; a
    boundary this ADR must not cross.
  - [`ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md)
    — the canonicalize-into-one-owner placement pattern.

> *This ADR changes **no** production code, package, wheel, public API, schema, frozen
> identifier, serialization, digest, or existing authority boundary. It assigns canonical
> ownership and records ratified rulings. Every implied code/package change is explicitly
> deferred to later, compatibility-controlled, separately-reviewed milestones. The
> platform-freeze substantive digest is unchanged before and after this ADR
> (`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).*

---

## 2. Context and problem

Three merged facts create the gap this ADR closes.

**1. Readiness now binds an exact system but still trusts caller-supplied evidence.**
M-3R.1 → M-3R.3 gave Agent Value Readiness a digest-bound `AssessedSystemBinding`, a
non-compensatory gate evaluator, and indicator admission. What no merged contract
provides is a way to answer *"is the evidence behind this indicator authentic, intact,
attributable, in-scope, temporally valid, and bound to this tenant, context, subject and
assessed system?"* The UVI ADR's five evidence axes (D-8) are **classifications carried
on a claim**, not verifications performed on evidence — and D-8 §12 already warns that
"caller-provided labels alone never elevate any axis". Today nothing performs the
elevation, so the axes are asserted rather than earned.

**2. "Evidence admission" currently has two partial owners and one wrong one.**
- RA-5 is **ratified** and owns *RA-scoped control-evidence admission* behind
  `EvidenceAdmissionPort` inside `ugence-risk-authority`, feeding `ControlResult` →
  `RiskAuthorizationEnvelope`. Its SPEC §3.2 deliberately declined to name a productized
  admission owner and retained **"TAP" as the broader conceptual umbrella (Truth/Trust
  Assurance)**.
- The Policy Authority ADR §6 row 4 disclaims evidence admission and names the owner as
  *"evidence producers under UVI ADR D-8/D-9"*. **A producer cannot be the verifier of
  its own evidence.** That row is a role-assignment defect and is reconciled additively
  in §34.
- The result is that a platform-wide trusted-evidence verifier is **unowned**, while two
  ratified documents each point somewhere else.

**3. The Benchmark Registry is staked but homeless.**
UVI ADR D-3 ratifies the *direction* (immutable versions, digest-bound resolution, no
silent substitution) and §21 already draws `benchmark-registry (service)` depending only
on `governance-contracts` — but **§26.5, "Benchmark registry home & attestation cadence",
is an open owner decision**, and D-3 states "Policy Authority governs admission and
permitted uses" while the Policy Authority ADR §6.9/§19.9/§20 explicitly disclaims
benchmark-value governance as "separate and deferred". Two ratified documents disagree
about whether Policy Authority approves benchmarks. Left unresolved, the first
implementation either forks a UVI-owned registry — the exact failure mode P-1 was written
to prevent — or silently makes Policy Authority the benchmark signer.

**Why now, and why design-only.** Deciding ownership costs nothing to defer
implementation, and the naming is load-bearing: a distribution or a receipt type shipped
under the wrong owner is a breaking change to rename after merge and free to rename
before. This ADR merges a decision, not a package.

---

## 3. Central decisions

> **(A) Trusted evidence verification is owned by TAP — the Trust Assurance role —
> as a single platform-wide evidence *admission and verification* authority.** TAP
> decides whether supplied evidence is authentic, intact, attributable, within scope,
> temporally valid, and bound to the asserted tenant, context, subject and assessed
> system. **TAP never manufactures the underlying evidence and never approves its own
> evidence source.**

> **(B) Admitted benchmark definitions, their exact versions, their lifecycle state and
> their trusted resolution are owned by one shared, platform-wide Ugence Benchmark
> Registry** — internal platform infrastructure, not a UVI-owned leaf and not a
> customer-facing module. **It does not manufacture observations, calculate benchmark
> results, compute readiness, calculate ROI, or approve its own benchmark content.**

The two capabilities **may interoperate and must not be conflated.** Verifying the
evidence behind an observation and resolving the benchmark that observation is compared
against are different trust questions with different authorities, different artifacts,
and different failure modes. A trusted benchmark resolution says nothing about the
evidence; a trusted evidence receipt says nothing about the benchmark.

---

## 4. Ratified decisions — trusted evidence (E-1 … E-14)

### E-1 — One platform-wide evidence verification authority
Ugence has exactly **one** trusted evidence admission/verification authority role, shared
platform-wide. **No** per-capability evidence verifier. **No** UVI-specific evidence
authority. Readiness, Governed Value, Policy Authority and Risk Authority are **consumers**
of the boundary, not owners of it.

### E-2 — TAP is the role, not the existing provider package
"TAP" names the **Trust Assurance umbrella role**, exactly as ratified in RA-5 SPEC §3.2.
It is **not** `ugence-tap-provider` (§5.1). Adopting the assertion-support scorer as the
verification owner is prohibited by name.

### E-3 — Producers never verify their own evidence
An evidence **producer/source** cannot verify its own evidence, and cannot verify it
merely by labelling it verified. Verification requires a distinct verifier authority, a
trusted key, and a verification protocol. `verified=True` from a producer is caller input.

### E-4 — Verification is external to, and separate from, collection
The **collector/submitter** role is distinct from both producer and verifier. A collector
transports evidence; transport confers no trust. A component may not occupy the producer
and verifier roles for the same evidence item.

### E-5 — No authority authorizes itself
No component may verify its own authorization, approve its own trust anchor, or admit its
own key. Trust anchors and verifier entitlements are configured at the **composition
root**, never supplied by the caller of verification and never self-declared inside the
artifact.

### E-6 — A verification result binds an exact coordinate set
A trusted evidence-verification result binds the full coordinate set of §9. A result that
cannot name the evidence digest, the producer, the tenant, the context, the subject, the
verifier authority and key, the protocol version, and both the observation and
verification instants is not a verification result.

### E-7 — Enumerated non-proofs
The artifacts listed in §8 — a `verified=True` flag, a lifecycle label, an authority
**name**, a caller-provided confidence score, an unsigned or untrusted verification
object — are **never** proof of verification for any consumer.

### E-8 — Production denies without a trust anchor
When no trusted verifier or trust anchor is configured, the production default is
**deny**. No production allow-all verifier may ship; permissive verifiers exist only under
`tests/`. This mirrors Policy Authority §11.5.

### E-9 — Fail-closed refusal across the whole failure surface
Every condition in §9 fails closed with a **stable typed reason code**. No condition
degrades to a warning, an advisory, a default-allow, or a silently-dropped evidence item.

### E-10 — Six distinct trust stages; no single boolean
The six stages of §10 — structurally constructible, cryptographically authentic,
provenance-verified, context/system-bound, currently valid, and policy-sufficient — are
**distinct**. **No single boolean may collapse them**, and no contract may expose one flag
that purports to mean all six.

### E-11 — TAP issues a signed, immutable verification receipt
TAP's output is a **signed, immutable evidence-verification receipt** (§11) that describes
exactly what TAP verified, remains distinct from the underlying evidence, and supports
later re-verification **without mutating** the earlier receipt.

### E-12 — A receipt is not an authorization
A receipt **never** authorizes deployment, **never** authorizes runtime action, **never**
proves a claim is economically valuable, **never** proves causal attribution, and **never**
silently converts reported evidence into verified truth.

### E-13 — RA-5's seam is preserved as the RA-scoped instance
RA-5's `EvidenceAdmissionPort` and its `ControlAssurancePort` boundary are **unchanged and
not reopened**. RA-5 remains the ratified owner of *RA-scoped control-evidence admission*
for `ControlResult` production. This ADR ratifies the **platform-wide** role that RA-5
deliberately left unnamed; alignment of RA-5's seam to the platform receipt is a separate,
later, separately-reviewed decision (§31, DD-6).

### E-14 — TAP imports no engine and mints no runtime authority
TAP imports no readiness engine, no `governed-value`, no Policy Authority internal, and no
Risk Authority internal. It sits **before** runtime, consulted by verification; it is never
on the hot path as an authorizer. It mints no envelope, no policy, and no deployment
permission.

---

## 5. Ratified decisions — Benchmark Registry (B-1 … B-12)

### B-1 — One shared platform-wide Benchmark Registry
Exactly **one** Benchmark Registry, shared platform-wide, **internal platform
infrastructure**. **No** UVI-specific benchmark registry, **no** per-capability fork. UVI
is its **first consumer**, not its owner. This resolves UVI ADR §26.5 by the same
reasoning P-1 resolved §26.1: the first non-UVI benchmark family would otherwise fork a
second registry or bend a UVI-named one into a de-facto platform authority.

### B-2 — Not a fourth UVI engine
The Benchmark Registry is **not** a customer-facing module, **not** a product, and **not**
a fourth UVI engine. UVI ADR D-18 holds: UVI's engines remain Agent Value Readiness, Value
Forecasting, and Governed Value Verification.

### B-3 — Benchmark authorship, approval and registration are separate roles
A benchmark **author/publisher** cannot approve its own benchmark. An **approver** is
external to the Registry. The **Registry** verifies approval; it never produces it. No
component occupies two adjacent roles for the same benchmark version.

### B-4 — The Registry does not approve its own input
The Benchmark Registry **cannot** act as both approving authority and registering
authority for the same benchmark version. Approver ≠ registrar is checked by the Registry
itself, not merely assumed of the verifier.

### B-5 — Approval evidence is not a label
A caller-provided approval label, a lifecycle enum on the artifact, a reputation score, a
publisher **name**, or a caller-created verification object is **not** approval evidence.
Approval binds an exact **content digest**, not a name and not an intent.

### B-6 — The authorized signer/publisher role is named and is not Policy Authority by default
The benchmark **publisher/signer** is a distinct, explicitly identified role (§16.1).
**Benchmark signing is not silently assigned to the Policy Authority.** Whether the
Policy Authority is *entitled* to act as benchmark approval verifier for a given benchmark
family is a separate owner decision (§31, DD-3) and requires an explicit entitlement in
the relevant authority contract.

### B-7 — Registration ordering is fixed and atomic in outcome
The six-stage ordering of §16.2 is mandatory. Failure at any stage produces **no trusted
registration, no partial state, no silent fallback**, and a stable typed refusal reason.

### B-8 — Benchmark identity is exact and digest-bound
Benchmark identity is the coordinate set of §15. Floating `latest`, implicit version
selection, and string-parsed successor guesses are **prohibited in governed evaluation**.
A floating reference must be *unrepresentable* on the trusted path, not merely discouraged.

### B-9 — Possession is not validity; retrieval is not resolution
A record fetched from storage has proved nothing until digest, approval, publisher
signature, key trust, lifecycle, effective period, revocation and scope checks pass.
**Raw retrieval and trusted resolution are different operations with different return
types.**

### B-10 — Append-only, byte-identical idempotence, typed conflict
Registration is append-only. Re-registering a **byte-identical** record at the same exact
coordinate is idempotent. **Any other reuse of an occupied slot is a typed conflict**, never
an overwrite and never a silent accept.

### B-11 — Signed, authorized, resolution-verified revocation; exact supersession only
Benchmark-version revocation must be signed, authority-controlled, and **verified before
denial is applied**. Supersession is expressed **only** through a structured successor
reference; when supersession cannot be determined, resolution **fails closed**.

### B-12 — The Registry computes nothing
The Benchmark Registry does not manufacture observations, calculate benchmark results,
perform comparisons, compute readiness, or calculate ROI. Its outputs are definitions and
resolutions.

---

## 6. Naming and placement rulings

### 6.1 The "TAP" name — a four-way collision, already documented

RA-5 SPEC §3.1 re-verified the distinct things sharing the name. This ADR **restates and
preserves** that finding and adds the platform ruling:

| Artifact | Path | What it is | Ruling |
|---|---|---|---|
| `ugence-tap-provider` | `packages/providers/tap/` | **Assertion-support scorer** — a peer of ActionGate. `TapOutcome` = {SUPPORTED, UNSUPPORTED, CONSTRAINED, INDETERMINATE, UNKNOWN}; emits an `evidence_coverage` ratio and a SHA-256 **fingerprint (a hash, not a signature)**; `evaluate()` takes no `now` and no first-class tenant/workflow. | **NOT** the evidence verification owner. Remains an RA-5 Control-Assurance evaluator *candidate*. Unchanged by this ADR. |
| `EvidenceAdmissionPort` / `ReferenceEvidenceAdmission` | `packages/risk_authority/.../risk_authority/integrations/tap.py` | The **RA-scoped evidence-admission seam** ratified by RA-5, admitting control evidence backing a `ControlResult` bound to `tenant / risk_case / policy_digest / workflow_ir_digest / control_id`. | **RA-scoped, NOT the platform verification owner.** RA-5 remains its ratified owner and it is **unchanged and not reopened** (E-13); platform-wide extension was considered and **rejected** (§25.3). Alignment with the platform receipt is DD-6. |
| `truth_assurance_pipeline/` | repo root | Synthetic research corpus (TAP-E1…E7), self-described as not production-ready. | Research lineage only. **Not** a platform capability. |
| **TAP — the Trust Assurance role** | *(no package; DEFERRED)* | The umbrella retained by RA-5 SPEC §3.2. | **Ratified here as the owner of trusted evidence admission and verification (E-1, E-2).** |

**Non-collapse rule (restated from RA-5 SPEC §3.2 and extended):** assertion-support
scoring and evidence verification are **different trust questions and are never merged**.
A high `evidence_coverage` is not a verification decision. Nothing in this ADR authorizes
reusing `ugence-tap-provider`'s outcome vocabulary, fingerprint, or coverage ratio as a
verification result.

### 6.2 Ratified canonical names

Proposed canonical names, unless a later merged convention requires a different
equivalent. **Package creation is DEFERRED (§30); no distribution is created here.**

> **Amendment (BR-2 ratification, §35).** The Benchmark Registry is recorded as
> **two layers**, not one:
>
> * the **frozen identity layer** — distribution `ugence-benchmark-registry`,
>   namespace `ugence_benchmark_registry`, version `0.1.0`. BR-1's benchmark
>   identity, canonicalization and refusal vocabulary. Zero runtime
>   dependencies. **Frozen**: BR-2 adds no field, changes no digest, appends no
>   member to its refusal enum, and never mutates a stored canonical artifact or
>   its identity digest.
> * the **authority/registry layer** — distribution
>   `ugence-benchmark-registry-authority`, namespace
>   `ugence_benchmark_registry_authority`, at
>   `packages/benchmark-registry-authority/`. BR-2's registry lifecycle,
>   admission, trust and resolution.
>
> **BR-2 behaviour never enters BR-1.** The split is what keeps a reviewed,
> frozen identity layer genuinely frozen and its isolated-install proof exact.
> The names below are otherwise unchanged.

| Aspect | Trusted evidence verification | Benchmark Registry |
|---|---|---|
| Capability name | **Ugence Trusted Evidence Authority** (the TAP role) | **Ugence Benchmark Registry** |
| Package location | `packages/trusted-evidence-authority/` | `packages/benchmark-registry/` |
| Distribution | `ugence-trusted-evidence-authority` | `ugence-benchmark-registry` |
| Namespace | `ugence_trusted_evidence_authority` | `ugence_benchmark_registry` |

**Explicitly prohibited:**

- reusing `packages/providers/tap/` or the `ugence-tap-provider` distribution as the
  evidence verification owner;
- `ugence-uvi-benchmark-registry` / `packages/uvi-benchmark-registry/` as an independent
  registry owner (B-1);
- a fourth customer-facing UVI engine for either capability (B-2, UVI ADR D-18);
- any name that presents either capability as a customer-facing product.

### 6.3 A second collision: "benchmark" is already an overloaded word

The repository already uses "benchmark" for **evaluation datasets and performance
harnesses**, none of which is the Benchmark Registry. Recorded so a reader does not
conflate them:

| Existing use | Location | Relationship |
|---|---|---|
| `comparative_governance_benchmark` — the **frozen comparative-governance dataset** gating `platform_freeze.verify`'s `benchmark_identity` check (90 scenarios, content hash `4d6de429…`) | `packaging/dgm-comparative-governance-benchmark/`, `docs/COMPARATIVE_GOVERNANCE_BENCHMARK.md` | **Unrelated.** An evaluation dataset, not a governed benchmark definition. **Not touched by this ADR.** |
| ML/performance harnesses (`CTM_plus/Bench/`, `symbolu_extensions/**/benchmarks/`, `symbolu_bcvf_llm/benchmark/`, `ndol/bench.py`) | repo root trees | **Unrelated.** Research performance measurement. |
| `BenchmarkReference` — the neutral **contract shape** | UVI ADR §20 (`governance-contracts`, DEFERRED as M-2E.1) | **Related.** The reference *type*; this ADR owns the **values** it points at, exactly as UVI ADR §20 already assigns ("`BenchmarkReference` **values** → internal benchmark registry"). |

### 6.4 A third collision: "receipt"

`execution_reference` / execution receipts already exist as a reserved seam in Agent
Runtime and `risk-authority-execution-assurance`. The **evidence-verification receipt** of
§11 is a **different artifact**: it attests verification of evidence, not the occurrence of
an execution. The two are never merged, and neither substitutes for the other.

---

## 7. What each capability owns and does not own

### 7.1 Trusted Evidence Authority (TAP)

| # | Owned |
|---|---|
| 1 | **Evidence admission** — may this evidence enter a governed process at all |
| 2 | **Authenticity verification** — signature and key trust over the exact content |
| 3 | **Integrity verification** — content digest agreement |
| 4 | **Attributability** — binding to an authorized producer identity |
| 5 | **Scope verification** — tenant, assessment context, subject, assessed system |
| 6 | **Temporal validity** — observation instant, verification instant, effective period, freshness |
| 7 | **Provenance / chain-of-custody verification** |
| 8 | **Issuance of the signed verification receipt** (§11) |
| 9 | **Verifier key trust and key revocation** |
| 10 | **Evidence revocation checking** before a receipt is honoured |

| # | Explicitly **not** owned | Owner instead |
|---|---|---|
| 1 | **Manufacturing evidence** | evidence producers/sources |
| 2 | **Approving its own evidence source** | structurally prohibited (E-3, E-5) |
| 3 | **Deciding a claim is true in the world** | nothing does; verification ≠ truth |
| 4 | **Assertion-support scoring** | `ugence-tap-provider` (a different question, §6.1) |
| 5 | **Benchmark definitions or resolution** | Benchmark Registry |
| 6 | **Readiness evaluation** | `agent-value-readiness` |
| 7 | **Policy approval / issuance** | Ugence Policy Authority |
| 8 | **Runtime action authorization** | Risk Authority / ActionGate |
| 9 | **Causal attribution** | UVI `AttributionAssessment` producer (DEFERRED) |
| 10 | **Financial valuation** | `governed-value` |
| 11 | **Assessed-system identity ownership** | Governance Contracts (§14) |

### 7.2 Ugence Benchmark Registry

| # | Owned |
|---|---|
| 1 | **Admission** of benchmark definitions (structural + approval + publisher verification) |
| 2 | **Exact version registration** (append-only) |
| 3 | **Exact-coordinate trusted resolution** |
| 4 | **Lifecycle state** and effective-period validation |
| 5 | **Publisher identity and key trust** |
| 6 | **Benchmark-version revocation** |
| 7 | **Structured supersession** (once DD-4 lands) |
| 8 | **Cross-tenant non-disclosure** of benchmark records |

| # | Explicitly **not** owned | Owner instead |
|---|---|---|
| 1 | **Authoring benchmark content** | domain owners / publishers |
| 2 | **Approving its own benchmark** | structurally prohibited (B-3, B-4) |
| 3 | **Deciding a benchmark is methodologically sound** | external governance process |
| 4 | **Manufacturing observations** | measurement systems; evidence verified by TAP |
| 5 | **Calculating benchmark results / comparisons** | consuming evaluation engine (§18) |
| 6 | **Computing readiness** | `agent-value-readiness` |
| 7 | **Calculating ROI or monetary value** | `governed-value` |
| 8 | **Policy requirements referencing benchmarks** | Ugence Policy Authority |
| 9 | **Evidence verification** | TAP |

A successful resolution proves **admission authenticity and current validity of the
definition**. It proves **nothing** about whether the benchmark is appropriate, whether
any observation was measured correctly, or whether a comparison is meaningful.

---

## 8. Role separation matrix

Fourteen roles. **No row may absorb another.**

| # | Role | Owner | Must never also be |
|---|---|---|---|
| 1 | **Evidence producer / source** | external systems, measurement processes, providers | the verifier of its own evidence (E-3) |
| 2 | **Evidence collector / submitter** | integration/ingestion layers | the verifier of what it submits (E-4) |
| 3 | **Evidence verifier / admission authority** | **TAP — Ugence Trusted Evidence Authority** | a producer, a collector, or a runtime authorizer (E-14) |
| 4 | **Evidence-verification receipt issuer** | **TAP**, under a configured authority key | the producer of the evidence it attests |
| 5 | **Benchmark author / publisher** | domain owners; signed by an authorized publisher | the approver of its own benchmark (B-3) |
| 6 | **Benchmark approver** | **external governance process** | the Registry (B-4) |
| 7 | **Benchmark approval verifier** | configured trust boundary at the **composition root** | the approver, or the caller |
| 8 | **Benchmark Registry** | **Ugence Benchmark Registry** | approver, author, or comparison engine (B-4, B-12) |
| 9 | **Benchmark resolver** | **Ugence Benchmark Registry** (trusted resolution) | a raw-retrieval cache presented as resolution (B-9) |
| 10 | **Benchmark-version revoker** | **Ugence Benchmark Registry**, under signed, entitled authorization | a caller; an unentitled foreign signer (B-11) |
| 11 | **Measurement / comparison engine** | consuming evaluation engine | the Registry, TAP, or Policy Authority (§18) |
| 12 | **Readiness consumer** | `agent-value-readiness` | an evidence verifier or benchmark registrar (§19) |
| 13 | **Governed Value consumer** | `governed-value` | a verifier, registrar, attributor, or independent verifier (§20) |
| 14 | **Policy Authority** | **Ugence Policy Authority** | benchmark author, evidence verifier, comparison engine, or ROI calculator (§17) |

### 8.1 Ratified self-authorization prohibitions

Each is a standalone ratified rule:

1. **An evidence producer cannot verify its own evidence merely by labelling it verified.**
2. **A benchmark author cannot approve its own benchmark.**
3. **Registry possession is not proof of validity.**
4. **Retrieval is not trusted resolution.**
5. **No consumer may manufacture verification.**
6. **No authority may authorize itself.**

A lax or compromised verifier must still be unable to get a **mismatched** or
**self-approved** artifact admitted: the authority independently re-checks that the
verification binds the exact identity, version, tenant/scope, content digest, approving or
producing authority, and approval or verification artifact.

---

## 9. Evidence trust model — what a verification result must bind (E-6)

A trusted evidence-verification result binds **all** of the following. Optionality is
justified per row; nothing is optional merely to ease implementation.

| # | Bound coordinate | Optionality |
|---|---|---|
| 1 | **Stable evidence identifier** | required |
| 2 | **Evidence type / schema** (with schema version) | required |
| 3 | **Content digest** of the exact evidence bytes | required |
| 4 | **Producer / source identity** | required |
| 5 | **Collection or observation time** (timezone-aware) | required |
| 6 | **Explicit verification time** (timezone-aware; distinct from #5) | required |
| 7 | **Tenant** | required |
| 8 | **Assessment context** | required |
| 9 | **Subject**, or an opaque **subject-context reference** | required |
| 10 | **`AssessedSystemBinding` reference and digest** | required *where the evidence describes an assessed system*; absent only where the evidence is system-independent, and its absence is explicit, never defaulted |
| 11 | **Claim or metric identity** | required *where the evidence backs a claim or metric*; absent for raw non-metric evidence, explicitly |
| 12 | **Units and measurement semantics** | required whenever #11 is present |
| 13 | **Provenance / chain-of-custody references** | required |
| 14 | **Verifier authority identity and key identifier** | required |
| 15 | **Verification protocol / version** | required |
| 16 | **Verification status and stable reason codes** | required |
| 17 | **Validity / effective period** | required where the evidence carries one; a half-open interval (§17.9) |

**Both instants are mandatory and distinct** (#5, #6). Collapsing observation time into
verification time destroys freshness reasoning; omitting verification time makes staleness
of the *verification* undetectable.

---

## 10. What a downstream consumer must never accept as proof (E-7)

A consumer **must not** treat any of these as proof that evidence was verified:

1. **`verified=True`** — or any caller-settable boolean;
2. **a lifecycle label** — e.g. `VERIFIED`, `ATTESTED`, `APPROVED_ACTIVE` carried on the
   artifact itself;
3. **an authority name** — a string naming a verifier is not that verifier's signature;
4. **a caller-provided confidence score** — including an evidence-coverage ratio;
5. **an unsigned or untrusted verification object** — including a structurally valid
   receipt whose signature, key, or trust anchor did not verify.

Consistency: this is the evidence-side analogue of Policy Authority §11.4 ("Not approval:
a caller Boolean; a lifecycle enum; a bare authority name; a caller-created verification
label; any evidence-status enum") and of UVI ADR §12 ("Caller-provided labels alone never
elevate any axis"). **Production defaults deny when no trusted verifier or trust anchor is
configured** (E-8).

---

## 11. Evidence-verification refusal semantics (E-9)

Every condition below is **fail-closed** with a **stable typed reason code**. None is a
warning; none degrades to allow; none is silently dropped.

| # | Condition | Outcome |
|---|---|---|
| 1 | Missing evidence | refuse — `EVIDENCE_MISSING` |
| 2 | Malformed evidence | refuse — `EVIDENCE_MALFORMED` |
| 3 | Digest mismatch | refuse — `EVIDENCE_DIGEST_MISMATCH` |
| 4 | Unknown or unauthorized producer | refuse — `PRODUCER_UNKNOWN` / `PRODUCER_UNAUTHORIZED` |
| 5 | Unknown, revoked, expired or not-yet-valid key | refuse — `KEY_UNKNOWN` / `KEY_REVOKED` / `KEY_EXPIRED` / `KEY_NOT_YET_VALID` |
| 6 | Signature failure | refuse — `SIGNATURE_INVALID` |
| 7 | Tenant mismatch | refuse — `TENANT_MISMATCH` |
| 8 | Context mismatch | refuse — `CONTEXT_MISMATCH` |
| 9 | Subject / system-binding mismatch | refuse — `SUBJECT_MISMATCH` / `SYSTEM_BINDING_MISMATCH` |
| 10 | Stale or not-yet-valid evidence | refuse — `EVIDENCE_STALE` / `EVIDENCE_NOT_YET_VALID` |
| 11 | Broken provenance | refuse — `PROVENANCE_BROKEN` |
| 12 | Unsupported schema | refuse — `SCHEMA_UNSUPPORTED` |
| 13 | Unit or metric mismatch | refuse — `UNIT_MISMATCH` / `METRIC_MISMATCH` |
| 14 | Verifier timeout or error | refuse — `VERIFIER_UNAVAILABLE` / `VERIFIER_ERROR` |
| 15 | Revoked evidence | refuse — `EVIDENCE_REVOKED` |
| 16 | Indeterminate verification | refuse — `VERIFICATION_INDETERMINATE` |

**Indeterminate is a refusal, not a pass.** A verifier that cannot decide has not verified.
Reason codes above are **illustrative of the required namespace shape**; the exact
vocabulary is an implementation detail (§31, DD-1), but stability, typing and
namespace-scoping are ratified now.

---

## 12. The six trust stages — no single boolean may collapse them (E-10)

| # | Stage | Question answered | What it does **not** establish |
|---|---|---|---|
| 1 | **Structurally constructible** | Does it parse into a well-formed, schema-known shape? | nothing about authenticity |
| 2 | **Cryptographically authentic** | Does a trusted key's signature verify over the exact content digest? | nothing about where the content came from |
| 3 | **Provenance-verified** | Is the chain of custody from an authorized producer intact? | nothing about *which* system/tenant it describes |
| 4 | **Context/system-bound** | Does it bind this tenant, context, subject and `AssessedSystemBinding`? | nothing about whether it is current |
| 5 | **Currently valid** | Is it within its effective period, fresh, and unrevoked at the caller-supplied instant? | nothing about sufficiency for any rule |
| 6 | **Sufficient for a particular policy requirement** | Does it satisfy *this* policy's evidence requirement? | nothing transferable to a different requirement |

**Stage 6 is requirement-relative and is not a property of the evidence.** The same
verified evidence may be sufficient for one policy requirement and insufficient for
another; a receipt therefore records stages 1–5 and never asserts stage 6 globally.
Ownership of stage 6 is the **Policy Authority's requirement** applied by the **consuming
evaluation engine** — not by TAP.

---

## 13. The signed TAP verification receipt (E-11, E-12)

### 13.1 What the receipt must do

1. **Describe exactly what TAP verified** — which stages of §12 were cleared, and which
   were not attempted.
2. **Bind the source evidence digest.**
3. **Bind the relevant tenant / context / subject / system coordinates** (§9).
4. **Identify the verifier authority and key identifier.**
5. **Include an explicit timezone-aware `verified_at`.**
6. **Preserve validity / effectivity semantics** — the receipt's own validity is distinct
   from the evidence's effective period, and both are carried.
7. **Support later re-verification without mutating the earlier receipt** — re-verification
   issues a **new** receipt; receipts are immutable and append-only.
8. **Remain distinct from the underlying evidence** — a receipt is never substituted for,
   merged into, or used as, the evidence it attests.

### 13.2 What the receipt must never do

1. **Authorize deployment.**
2. **Authorize runtime action.**
3. **Prove a claim is economically valuable.**
4. **Prove causal attribution.**
5. **Silently convert reported evidence into verified truth** — a receipt over `REPORTED`
   evidence attests that a *report* was authentic and bound; it does not make the report
   an observation. UVI ADR §12 governs: attestation "never converts `REPORTED` into
   `OBSERVED`, and never implies attribution."

### 13.3 Cryptographic and canonical properties

| Property | Requirement |
|---|---|
| **Domain separation** | Every signed payload and every digest binds a **versioned domain-separation tag**. Receipt, evidence, and benchmark domains are distinct; a signature valid in one domain must not verify in another. |
| **Versioning** | The canonicalization version and the verification protocol version are both bound into the signed payload. |
| **Deterministic canonicalization** | Canonical bytes are a deterministic function of the payload — no wall clock, no locale, no map-iteration-order dependence, no environment input. |
| **Signature verification** | Independent verification must be possible: a third party holding the receipt and the public verification functions can recompute the digest and check the signature without authority internals. |
| **Key revocation** | Key revocation is checked at verification time; a receipt signed by a key that was later revoked is not silently honoured. Key revocation is distinct from evidence revocation and from policy-version revocation. |
| **Signature exclusion** | Signature fields never participate in the content digest, but the digest is bound **through** the signed payload. |
| **No fixed-point digests** | Self-referential/fixed-point digest algorithms and sentinel digests are **prohibited**. If a self-referential declaration field exists, it is **exactly identified and removed — not blanked** — in one pass. |
| **No unsigned "trusted" receipts** | A receipt that is unsigned, or whose signature does not verify against a configured trust anchor, is **not** a receipt. There is no "trusted but unsigned" state. |

**Exact byte constants — domain tags, tag strings, algorithm identifiers, encodings — are
deliberately left to the implementation milestone (TEV-1/TEV-2).** What is ratified now is
that they must be **unambiguous, versioned, and fixed before signing exists**; ambiguity,
fixed-point digests, and unsigned "trusted" receipts are prohibited outright.

---

## 14. Assessed-system and subject-context boundary

Existing ownership is **preserved unchanged**:

1. **Governance Contracts owns `AssessedSystemBinding`.** It is defined exactly once, in
   `packages/governance-contracts/.../contracts/system_identity.py`. This ADR does not
   move it, redefine it, or extend it.
2. **TAP may verify evidence against the binding's exact reference and digest.**
3. **TAP does not become the owner of assessed-system identity.** Verifying against an
   identity does not confer ownership of it.
4. **A receipt may prove evidence was verified against a binding.**
5. **That does not make the binding authority-authentic.** The merged contract already
   states this precisely: `AssessedSystemBinding.authenticity_status` is a permanently
   `STRUCTURAL_UNVERIFIED` **property**, not a field — "raising it requires a ratified
   system-binding verifier, which no merged contract defines." A **distinct trusted
   binding-verification mechanism** would be required, and **none is created here**
   (§31, DD-5).
6. **`canonical_subject_context_ref` remains an opaque, digest-bound bridge** to Risk
   Authority's subject-context contract. It stays an opaque token in Governance Contracts.
7. **Governance Contracts and Readiness must not import Risk Authority.** This one-way
   rule is unchanged and is re-affirmed as an invariant of any TEV/BR milestone. It is
   also why the platform receipt contract cannot live inside `ugence-risk-authority`
   (E-13).

**`SystemManifest` is not invented here.** No `SystemManifest` type is defined, named as
owned, or placed by this ADR. Its home remains the **open owner decision** recorded at
UVI ADR §26.3 / §20, and no ratified repository decision resolves it at `d905c551`.

> *Observation, not a ruling.* UVI ADR §26.2 records the RA-owned `SubjectContext` as
> "draft-only (PR #1425, not merged)". At this baseline, PR #1432 has merged an RA-owned
> v2 subject-context contract (`SUBJECT_CONTEXT_SCHEMA_VERSION = "risk-subject-context-1"`,
> `packages/risk_authority/.../integrations/evaluation_contracts.py`). Updating §26.2 is
> **out of scope for this ADR** and is deliberately not done here; it is already tracked as
> housekeeping on the Risk Authority workstream. This ADR relies only on the opacity of
> `canonical_subject_context_ref`, which is unaffected either way.

---

## 15. Benchmark definition identity (B-8)

The minimum security-relevant identity of a benchmark definition. Optionality is justified
per row.

| # | Field | Optionality |
|---|---|---|
| 1 | **Benchmark id** | required |
| 2 | **Family / type** | required |
| 3 | **Semantic version** | required |
| 4 | **Content digest** | required |
| 5 | **Tenant / scope** | required (may denote a platform-wide scope explicitly, never by omission) |
| 6 | **Geography** | required where applicability depends on it; explicitly `NOT_APPLICABLE` otherwise — never omitted |
| 7 | **Domain** | required where applicability depends on it; explicitly `NOT_APPLICABLE` otherwise |
| 8 | **Intended outcome / metric purpose** | required |
| 9 | **Metric identity** | required |
| 10 | **Unit** | required |
| 11 | **Measurement protocol / reference** | required |
| 12 | **Population / cohort** | required |
| 13 | **Aggregation semantics** | required |
| 14 | **Observation window** | required |
| 15 | **Effective period** | required; half-open (§17.9) |
| 16 | **Source / provenance requirements** | required |
| 17 | **Approval reference** | required |
| 18 | **Publisher identity** | required |
| 19 | **Lifecycle state** | required |
| 20 | **Structured supersession / revocation reference** | required **where supported**; absent until DD-4 lands, and its absence never implies "not superseded" |

**Geography, domain and intended outcome are not cosmetic labels.** Where they affect
applicability they are load-bearing identity, and a mismatch is a resolution refusal
(§17), not an advisory note. An explicit `NOT_APPLICABLE` is a decision on the record; an
omitted field is not.

---

## 16. Benchmark approval and registration ordering (B-7)

### 16.1 The authorized signer/publisher role

The **benchmark publisher/signer** is the authorized party that signs the exact benchmark
content digest under a key trusted by the Registry's configured trust anchors. It is:

- **distinct** from the benchmark **author** (who may write content without signing
  authority);
- **distinct** from the benchmark **approver** (B-3, B-4);
- **distinct** from the **Registry** itself (B-4);
- **not the Policy Authority by default** (B-6). The Policy Authority's ratified scope is
  *policy* issuance and signing (Policy Authority ADR §5); extending it to benchmark
  content would make it the approver of data it also writes policy against. Whether a
  Policy Authority instance is *entitled* to act as benchmark approval verifier for a
  given family requires an explicit entitlement in the relevant authority contract and is
  **DD-3**.

### 16.2 Mandatory ordering

1. **Structural validation** — schema known, shape well-formed, required identity present.
2. **Canonical digest verification** — declared digest equals the computed canonical digest.
3. **External benchmark-approval verification** — approval binds this exact content digest,
   through a configured trusted approval-verification boundary.
4. **Publisher / signature verification** — authorized publisher, trusted key, valid
   signature, key not revoked/expired/not-yet-valid.
5. **Lifecycle / effectivity validation** — state admissible, effective period well-formed.
6. **Exact append-only registration** — at the exact coordinate, append-only.

### 16.3 Failure behavior

Failure at **any** stage produces:

- **no trusted registration**;
- **no partial state** — nothing half-written, no reserved slot, no pending record that a
  later call could complete;
- **no silent fallback** — no downgrade to an untrusted registration, no retry under
  weaker checks, no substitution of a different version;
- **a stable typed refusal reason**.

**The Benchmark Registry must not approve its own input** (B-4), and a caller-provided
approval label, reputation score, or publisher name is **not approval evidence** (B-5).

---

## 17. Registry and resolution semantics

| # | Requirement |
|---|---|
| 1 | **Exact-coordinate lookup only.** |
| 2 | **No `latest()`, `current()`, or newest-version fallback** on the trusted path. A floating reference must be *unrepresentable*, not merely discouraged. |
| 3 | **Append-only registration.** |
| 4 | **Byte-identical idempotence only** — re-registering identical bytes at the same coordinate succeeds idempotently. |
| 5 | **Typed conflict on any other slot reuse** — never an overwrite, never a silent accept. |
| 6 | **Cross-tenant non-disclosure** — a resolution for tenant A must not disclose the existence, identity, or content of tenant B's records; a not-found and a not-permitted must not be distinguishable to an unauthorized caller. |
| 7 | **Immutable records and trust-anchor views** — trust anchors and key rings defensively copy caller mappings and expose immutable views; a caller that mutates what it passed in cannot alter registry trust state after construction. |
| 8 | **Explicit timezone-aware `as_of`** — supplied by the caller; never a wall-clock read inside resolution. |
| 9 | **Half-open effective periods** — `[start, end)`; boundary semantics stated once and applied identically everywhere. |
| 10 | **Signed and authorized revocation** — the revoking authority must be entitled for the exact benchmark scope; the publisher's identity is never silently substituted as the revoker; a missing revoker is an error, not a defaulting opportunity. |
| 11 | **Verified revocation before denial is applied** — an unverified revocation record does not deny and does not allow; it fails closed as an integrity error. |
| 12 | **Exact supersession only through a structured successor reference** — no string matching, no version ordering, no "latest" inference. A guessed supersession is an unsigned authority decision. |
| 13 | **Fail closed when supersession cannot be determined.** |
| 14 | **Retrieval distinct from trusted resolution** (B-9) — different operations, different return types; a retrieved record carries no trust. |

### 17.1 Historical resolution

If historical resolution is enabled at all, its output must:

- **preserve and disclose the requested `as_of`** instant;
- **state explicitly that it does not imply current validity**;
- **never authorize present runtime use**.

A historical answer is **labelled as historical in the result**, mirroring Policy Authority
§14.10.

---

## 18. Definitions versus observations versus results versus policy

Four artifacts. **No renaming promotes one into another.**

| Artifact | Definition | Owner |
|---|---|---|
| **Benchmark definition** | An approved, versioned reference describing **what is measured and how comparison is interpreted**. | **Ugence Benchmark Registry** |
| **Observed measurement** | An **evidence-backed value** produced by an external system or measurement process. | measurement systems; the supporting **evidence is verified by TAP** |
| **Benchmark comparison result** | A **deterministic comparison** of a verified observation against an **exact resolved** benchmark definition. | **consuming evaluation engine** |
| **Policy decision** | A rule determining **whether that comparison matters** for readiness, risk, or value assessment. | **Ugence Policy Authority** (requirement) applied by the consuming engine |

**Ratified ownership:**

- **Benchmark Registry owns definitions and exact resolution** — and nothing downstream.
- **TAP verifies evidence supporting observations** — and does not produce observations.
- **A consuming evaluation engine performs deterministic comparison** — over a verified
  observation and an exactly resolved definition.
- **Policy Authority owns applicable policy requirements** — and **does not own benchmark
  observations or comparison results**.
- **Benchmark Registry does not compute readiness or ROI** (B-12).

This preserves UVI ADR §13: a signed threshold is a `PolicyThreshold` literal or a
`BenchmarkReference`, **never** a `MetricClaim`; policy thresholds are policy artifacts,
not metric evidence claims.

---

## 19. Policy Authority boundary

The shared Policy Authority ADR is **preserved**. Policy Authority **may** issue policies
referencing **exact benchmark coordinates** and **evidence requirements**.

It does **not**:

1. author benchmark definitions;
2. verify evidence;
3. calculate benchmark results;
4. compute readiness;
5. calculate ROI;
6. authorize deployment;
7. revoke evidence or benchmark versions — **unless separately entitled** by the relevant
   authority contract (an explicit entitlement, never an implicit one; see DD-3).

**A policy reference to a benchmark is not proof that the benchmark resolved
successfully.** A policy artifact may name benchmark coordinates that are unregistered,
revoked, superseded, expired, or belong to another tenant. Each artifact must be
**resolved and verified through its proper authority boundary**:

| Artifact in a policy | Resolved and verified through |
|---|---|
| the policy itself | **Ugence Policy Authority** (signature, digest, lifecycle, revocation) |
| a referenced benchmark coordinate | **Ugence Benchmark Registry** (exact resolution, §17) |
| a referenced evidence requirement | **TAP** verification of the actual evidence (§9, §11) |
| the assessed system | **Governance Contracts** `AssessedSystemBinding` digest equality (§14) |

Resolving one proves nothing about the others. A policy that resolves successfully while
its referenced benchmark does not **fails closed** on the benchmark, per the applicable
policy requirement.

---

## 20. Readiness integration boundary (future posture, not implemented)

Agent Value Readiness **may later** consume:

1. exact resolved **readiness policy**;
2. **`AssessedSystemBinding`**;
3. **signed TAP evidence-verification receipts**;
4. **exact resolved benchmark definitions**;
5. **deterministic benchmark comparison results**.

Readiness **must not**:

1. **verify raw evidence itself** — that is TAP's role (E-1);
2. **register or approve benchmarks** — that is the Registry's and the external approver's;
3. **manufacture trusted receipts**;
4. **trust a caller's `verified` flag** (§10);
5. **reintroduce indicator-family counting** — the **RA-01** ruling stands: requirements are
   policy/gate-driven, never indicator-presence-driven, and catalog presence never creates
   a requirement;
6. **convert benchmark performance into financial value** — that is `governed-value`;
7. **authorize deployment** — UVI ADR D-4 and the permanent `authorizes_deployment = False`
   invariant stand.

**Evidence or benchmark gaps fail closed according to the applicable policy requirement**,
while preserving **RA-01 gate-driven semantics**: a gap becomes a gate outcome under a
policy requirement that declares the gate, not a global penalty derived from what happens
to be missing from a catalog. Existing determination ordering, the non-compensatory
mandatory-gate invariant (D-6), and composite-is-advisory (D-5) are **unchanged**.

**Nothing in this section is implemented.** No readiness contract, evaluator, orchestration
stage, indicator, reason code, or version changes in this ADR.

---

## 21. Governed Value boundary (future posture, not implemented)

Governed Value **may later** consume: verified evidence; exact benchmark definitions;
observed measurements; readiness determinations; execution/outcome receipts; attribution
evidence.

The **five-stage model is preserved**:

1. `PRE_ROI_READINESS`
2. `FORECAST_ROI`
3. `OBSERVED_ROI`
4. `ATTRIBUTED_ROI`
5. `VERIFIED_ROI`

**Trusted evidence and benchmark resolution do not establish attribution or verified ROI by
themselves.** The honest chain of UVI ADR D-10/§17 is unchanged and re-affirmed:

| Boundary | Ratified |
|---|---|
| **Benchmark comparison is not monetary valuation.** | A comparison result is a non-financial determination; converting it to money requires `governed-value` under an approved `IntendedOutcomePolicy`/`ValuationPolicy`. |
| **Forecasts are not observations.** | A forecast carries `ForecastHorizon`, not `AssessmentWindow`; `MetricObservation` is reserved for `source_basis = OBSERVED`. |
| **Observations are not attribution.** | Attribution requires a declared counterfactual, causal method, assumptions and evidence (UVI §12). |
| **Attribution is not independent verification.** | Verification must bind a declared `claim_ref` and does not imply attribution (UVI §12). |

The conservative headline rule (D-12) stands: **a verified component never elevates** a
weaker required component. A TAP receipt over one component does not raise the headline of
a valuation whose other required components remain reported, unattributed, or unverified.

**Nothing in this section is implemented.** `governed-value` is unchanged by this ADR.

---

## 22. Canonicalization, time, and determinism

Shared properties for **both** evidence receipts and benchmark artifacts:

| # | Requirement |
|---|---|
| 1 | **Versioned domain separation** — every digest and signed payload binds a canonicalization version and a domain-separation tag; receipt, evidence and benchmark domains are distinct. |
| 2 | **Deterministic canonical bytes** — a pure function of the payload. |
| 3 | **UTC normalization of aware datetimes** — every aware datetime is re-expressed in UTC before serialization, so two instants that are equal produce byte-identical canonical bytes. This is the discipline already merged for `AssessedSystemBinding` (PR #1440) and is adopted verbatim. |
| 4 | **Rejection of naive datetimes** — at the boundary and again at canonicalization. A value with no offset does not name an instant; guessing UTC for it silently invents one. Rejection, never a default. |
| 5 | **Exactly identified exclusion of a self-referential digest field, if one exists** — that field is **removed, not blanked**; one pass, no fixed-point iteration. |
| 6 | **No sentinel or fixed-point digest.** |
| 7 | **Signatures excluded from content digests but bound through signed payloads.** |
| 8 | **Unknown types fail closed** — an unrecognized schema, artifact type, or algorithm identifier is a refusal, never a best-effort serialization. |
| 9 | **No wall clock inside canonicalization or evaluation.** |
| 10 | **Explicit caller-supplied evaluation instant** — `as_of` / evaluation time is a parameter, not an ambient read. |
| 11 | **Stable reason-code namespaces** — scoped per capability, stable across versions, never reused for a different meaning. |
| 12 | **Immutable records.** |
| 13 | **Deterministic reason ordering** — the same inputs produce the same reason sequence, so digests over results are stable. |

**Placement rule.** Genuinely shared contracts belong in **Governance Contracts** — but
**only where doing so creates no dependency cycle**. Concretely: Governance Contracts
depends on nothing and must not import Risk Authority, Policy Authority, TAP, the Benchmark
Registry, or any engine. A contract that cannot satisfy that constraint stays in its owning
capability and is consumed **by value**, digest-bound. Which specific contracts land in
Governance Contracts is **DD-2**.

---

## 23. Consumer and dependency matrix

```
governance-contracts                  (depends on nothing)
     ▲          ▲          ▲          ▲            ▲
     │          │          │          │            │
uvi-policy-  agent-value-  governed-  ugence-      ugence-
contracts    readiness     value      benchmark-   trusted-evidence-
                                      registry     authority
                                      (DEFERRED)   (DEFERRED)

ugence-policy-authority ── governance-contracts + registered family adapters

Consumers receive, BY VALUE and digest-bound:
   exact resolved policy artifacts        ← Ugence Policy Authority
   exact resolved benchmark definitions   ← Ugence Benchmark Registry
   signed evidence-verification receipts  ← TAP
```

| Consumer | May consume | Must never import |
|---|---|---|
| `agent-value-readiness` | resolved readiness policy; `AssessedSystemBinding`; TAP receipts; resolved benchmark definitions; comparison results | Policy Authority internals; TAP internals; Benchmark Registry internals; `governed-value`; **Risk Authority** |
| `governed-value` | verified evidence; benchmark definitions; observations; readiness determinations; execution/outcome receipts; attribution evidence | `agent-value-readiness`; TAP internals; Benchmark Registry internals |
| `governance-contracts` | *nothing* | **everything** — it remains a leaf depending on nothing; **must not import Risk Authority** |
| **Ugence Benchmark Registry** | `governance-contracts` only | TAP; Policy Authority; any engine; Risk Authority |
| **TAP** | `governance-contracts` only | Benchmark Registry; Policy Authority; any engine; Risk Authority |
| Ugence Policy Authority | `governance-contracts`; registered family adapters | TAP; Benchmark Registry; engines; Risk/Decision Authority internals |

**Invariants.** Every arrow points at a neutral-contract package. `agent-value-readiness`
does not import `governed-value` and vice versa. No leaf imports an authority internal.
**Governance Contracts and Readiness must not import Risk Authority.** The Benchmark
Registry and TAP each depend only on `governance-contracts` — consistent with UVI ADR §21,
which already draws the benchmark registry that way.

---

## 24. Alternatives considered

| # | Alternative | Assessment |
|---|---|---|
| A1 | **One combined "Trust & Benchmark" service** | Considered for operational simplicity. **Rejected** — §25.1. |
| A2 | **Extend `ugence-tap-provider` to own verification** | Considered because the name already exists. **Rejected** — §25.2. |
| A3 | **Extend RA-5's `EvidenceAdmissionPort` to the whole platform** | Genuinely attractive: the seam exists and is ratified. **Rejected** — §25.3. |
| A4 | **Policy Authority owns benchmark admission and signing** | Considered; UVI D-3 arguably implies it. **Rejected** — §25.4. |
| A5 | **A UVI-owned benchmark registry** | The literal reading of "internal UVI benchmark registry" in D-3. **Rejected** — §25.5. |
| A6 | **Readiness verifies its own evidence** | Shortest path to a working milestone. **Rejected** — §25.6. |
| A7 | **A single `verified: bool` on evidence contracts** | Simplest possible model. **Rejected** — §25.7. |
| A8 | **Defer the whole decision until TEV-1 implementation** | Considered. **Rejected** — naming and ownership are load-bearing (§2); a distribution or receipt type shipped under the wrong owner is a breaking rename after merge and free before. |
| A9 | **Allow `latest()` resolution outside governed evaluation** | Considered for developer ergonomics. **Not adopted as a trusted path**: §17.2 prohibits it on the trusted path; any untrusted convenience surface must return a type that cannot be mistaken for a trusted resolution (B-9). |

---

## 25. Rejected alternatives, with reasons

### 25.1 One combined Trust & Benchmark service — rejected
Conflates two different trust questions with different failure modes. A benchmark
resolution failure would become indistinguishable from an evidence verification failure in
reason codes and refusal semantics, and a compromise of either trust anchor would
compromise both. The task's central constraint — "may interoperate but must not be
conflated" — is a security property, not a stylistic preference.

### 25.2 Extend `ugence-tap-provider` — rejected
Re-affirms RA-5 SPEC §3.2's rejection on the same live-code evidence: its semantics are
*assertion-support scoring over caller-supplied evidence references*, not *evidence
verification*. It has no provenance gate, no freshness model (`evaluate()` takes no `now`),
no first-class tenant/workflow binding, and produces a **fingerprint (a hash), not a
signature**. Treating its `evidence_coverage` ratio as a verification decision would
**falsely equate assertion-support scoring with evidence verification** — precisely the
trap §10.4 forbids.

### 25.3 Extend RA-5's `EvidenceAdmissionPort` platform-wide — rejected
The port lives **inside `ugence-risk-authority`**, a stdlib-only leaf whose admission
semantics are shaped for *control evidence backing a `ControlResult`* bound to
`tenant / risk_case / policy_digest / workflow_ir_digest / control_id`. Adopting it
platform-wide would either (a) force Governance Contracts and Readiness to import Risk
Authority — **prohibited** (§14.7, §23) — or (b) silently widen a ratified RA-scoped
contract into a platform one without review. RA-5 is preserved as the RA-scoped instance
(E-13); alignment is DD-6.

### 25.4 Policy Authority owns benchmark admission and signing — rejected
Would make one authority both the writer of policy requirements *and* the approver of the
reference data those requirements are evaluated against — a self-authorization loop that
P-5 exists to prevent. The Policy Authority ADR itself disclaims benchmark-value
governance three times (§6.9, §19.9, §20). Policy Authority **may** reference exact
benchmark coordinates; that is a citation, not ownership (§19).

### 25.5 A UVI-owned benchmark registry — rejected
Identical failure mode to the one P-1 was written to prevent. The first non-UVI benchmark
family (risk benchmarks, capacity benchmarks, model-selection benchmarks) would either fork
a second registry or bend a UVI-named registry into a de-facto platform authority. Renaming
a distribution after merge is a breaking change; deciding now is free. UVI ADR §21 already
draws the registry as a peer depending only on `governance-contracts` — consistent with a
shared owner, not a UVI-internal one.

### 25.6 Readiness verifies its own evidence — rejected
Makes the readiness engine both consumer and verifier, violating E-3/E-5 and UVI ADR §23.10
("Reference producers never self-attest/self-verify/self-approve"). It would also duplicate
verification the moment `governed-value` needs the same evidence, producing two verifiers
that can disagree.

### 25.7 A single `verified: bool` — rejected
Collapses the six distinct stages of §12 into one flag, making it impossible to distinguish
"the signature verified" from "the provenance chain is intact" from "this is bound to the
right tenant" from "this is sufficient for *this* policy requirement". Stage 6 is
requirement-relative and cannot be a property of the evidence at all. A single boolean is
also exactly the artifact §10.1 forbids consumers from trusting.

---

## 26. Security considerations

1. **No caller-elevated trust.** No caller-supplied label, boolean, score, name, or
   unsigned object elevates evidence or benchmark trust (§10, B-5).
2. **No self-authorization.** Producer ≠ verifier; author ≠ approver; approver ≠ registrar;
   issuer ≠ approver. Checked by the authority, not assumed of the verifier (§8.1).
3. **Deny by default.** No trust anchor configured ⇒ deny. No production allow-all verifier
   ships (E-8).
4. **Fail closed across the entire failure surface** — including `INDETERMINATE`, verifier
   timeout, and verifier error, which are refusals, not passes (§11).
5. **Replay and swap resistance.** Every artifact binds exact identity + digests; tenant,
   context, subject and `AssessedSystemBinding` mismatches are refusals, so a favourable
   result for one system/tenant is mechanically detectable when replayed under another.
6. **Domain separation prevents cross-artifact signature reuse** — a receipt signature must
   not verify as a benchmark signature or a policy signature (§13.3).
7. **Revocation is verified before it is applied** — an unverified revocation neither denies
   nor allows; it fails closed as an integrity error (§17.11).
8. **Three distinct revocations, never conflated** — key revocation, evidence revocation,
   benchmark-version revocation. Policy-version revocation (Policy Authority §14) and Risk
   Authority envelope revocation (RA-6) remain separate again.
9. **Guessing is prohibited** — no string-matched, version-ordered, or "latest"-inferred
   supersession. A guessed supersession is an unsigned authority decision (§17.12).
10. **Possession is not validity; retrieval is not resolution** (§8.1.3, §8.1.4).
11. **No component on the runtime hot path.** Neither TAP nor the Registry authorizes
    runtime action; Risk Authority and ActionGate retain runtime authorization (E-14).
12. **Structural authenticity is not source authenticity.** A fully self-consistent forged
    artifact that satisfies every internal binding is still not authority-authentic; this is
    named explicitly for `AssessedSystemBinding` (§14.5) rather than glossed over.
13. **No fixed-point digests, no sentinel digests, no unsigned "trusted" artifacts** (§13.3).

---

## 27. Privacy and tenant considerations

1. **Tenant binding is mandatory** on every verification result and every benchmark record
   (§9.7, §15.5). It is never inferred and never defaulted.
2. **Cross-tenant non-disclosure** — a resolution for one tenant must not disclose the
   existence, identity, or content of another tenant's records; **not-found and
   not-permitted must be indistinguishable** to an unauthorized caller, so the registry is
   not an enumeration oracle (§17.6).
3. **Storage partitioning is insufficient** — trust binding must be **intrinsic to the
   artifact**, not a property of where it is stored. This is the same ruling RA-5 §5 made
   for admitted evidence and trusted `ControlResult`s.
4. **Subject data stays opaque at the seam.** `canonical_subject_context_ref` is an opaque,
   digest-bound token; Governance Contracts carries no subject payload and mints no subject
   contract (§14.6).
5. **Receipts should bind digests, not payloads.** A receipt binds the evidence *digest* and
   coordinates; it is not a copy of the evidence and must not become a secondary store of
   sensitive content (§13.1.8).
6. **Reason codes must not leak cross-tenant existence** — a refusal reason must not reveal
   that a coordinate exists in another tenant's scope.
7. **Provenance references may be sensitive** — chain-of-custody references identify
   producers and systems; their disclosure scope is a deployment concern recorded as DD-7.

---

## 28. Evidence lifecycle

```
   produce            collect /           verify                issue signed
   evidence  ───────▶ submit    ───────▶  (stages 1–5, §12) ──▶ receipt
   (producer/         (collector;         (TAP;                 (TAP, authority key,
    source)            confers no          trust anchors at      explicit verified_at)
                       trust)              composition root)
                                                 │
                                                 ▼
   consume by value  ◀────  check receipt  ◀──── register / retain
   (readiness, governed      (signature, key,    (immutable, append-only)
    value — never trust      domain tag, digest,
    a bare flag)             coordinates, validity)
        │
        ├──▶ re-verify later ──▶ NEW receipt (earlier receipt never mutated)
        │
        └──▶ revoke evidence / revoke key ──▶ verified before denial applies
```

**Status legend:** every stage above is **RATIFIED as design**. **None is IMPLEMENTED** —
no trusted evidence verification package, contract, receipt type, or verifier exists at
`d905c551`. Stage 6 of §12 (policy sufficiency) is deliberately **outside** this flow: it
belongs to the consuming engine under a Policy Authority requirement.

---

## 29. Benchmark lifecycle

```
   author             approve             verify approval        verify publisher
   benchmark ───────▶ the EXACT  ───────▶ at configured   ────▶  signature + key
   content            digest              trust boundary         trust
   (domain owner)     (external           (composition root)     (authorized publisher)
                       governance)
                                                                        │
                                                                        ▼
   consume by value ◀──── trusted        ◀──── validate       ◀──── register exact
   (evaluation       resolution           lifecycle /              version
    engine; exact     (exact coordinate,  effectivity             (append-only;
    resolved defn)    as_of, revocation,                           byte-identical
                      scope)                                       idempotence only)
        │
        ├──▶ revoke version (signed, entitled, verified before denial)
        │
        └──▶ supersede (structured successor reference ONLY — DEFERRED, DD-4;
                        fail closed while undeterminable)
```

**Status legend:** every stage above is **RATIFIED as design**. **None is IMPLEMENTED** —
no benchmark registry package, contract, definition type, or resolver exists at
`d905c551`. Structured supersession is **DEFERRED** (DD-4).

---

## 30. Implementation milestones — all DEFERRED

Independently reviewable, dependency-ordered. **Nothing below is implemented, started, or
approved for implementation by this ADR.**

| # | Milestone | Content | Depends on | Status |
|---|---|---|---|---|
| 1 | **TEV-1** | **Trusted Evidence Verification Contracts** — the verification-result coordinate set (§9), the six-stage model (§12), receipt shape (§13), reason-code namespace (§11). Contracts only; no verifier. | — | **DEFERRED** |
| 2 | **TEV-2** | **TAP Verification Service and signed receipts** — the verification authority, trust anchors, key trust/revocation, signing, independent verification. | TEV-1 | **DEFERRED** |
| 3 | **BR-1** | **Benchmark Definition Contracts** — benchmark identity (§15), lifecycle state, structured references. Contracts only; no registry. | — | **DEFERRED** |
| 4 | **BR-2** | **Benchmark Registry and trusted resolver** — admission ordering (§16.2), append-only registration, exact resolution, revocation (§17). **Subdivided by §35 (D-01, amended 2026-08-20) into five independently auditable subphases:** BR-2A contracts, BR-2B non-authoritative lifecycle kernel, BR-2C cryptographic trust authority, BR-2D durable registry authority, BR-2E production composition and operations. | BR-1 | **BR-2A ratified and implemented; BR-2B–BR-2E DEFERRED** |
| 5 | **UVI-EV-1** | **Readiness evidence/benchmark integration** — readiness consumes receipts and resolved definitions per §20. | TEV-2, BR-2 | **DEFERRED** |
| 6 | **GV-F** | **Forecast ROI** | UVI-EV-1 | **DEFERRED** |
| 7 | **GV-O** | **Observed ROI** | GV-F, TEV-2 | **DEFERRED** |
| 8 | **GV-A** | **Attributed ROI** | GV-O | **DEFERRED** |
| 9 | **GV-V** | **Verified ROI** | GV-A | **DEFERRED** |

### 30.1 Label reconciliation with repository convention

The labels above are **retained** as primary identifiers, and mapped to existing repository
conventions rather than silently renamed:

| Label | Repository-convention equivalent | Note |
|---|---|---|
| **TEV-1**, **TEV-2** | *(new namespace)* | TAP is **platform infrastructure**, not a UVI engine, so a `M-*` UVI milestone prefix would be wrong — the same reasoning by which Policy Authority §16.4 ruled its build a "platform dependency milestone, not a UVI engine milestone". No collision with `RA-*`, `P-*`, `M-*`, `D-*`, `GV-2*`. |
| **BR-1**, **BR-2** | subsumes and supersedes UVI ADR §25.3 **M-2C.2** ("internal benchmark registry") | M-2C.2 is retained as a historical UVI-milestone name; BR-1/BR-2 are its platform-owned split (contracts, then registry). The `BenchmarkReference` *contract shape* remains UVI **M-2E.1**. |
| **UVI-EV-1** | **M-3R.4** in the UVI milestone sequence | A genuine UVI engine milestone; the `M-3R.*` sequence is the repository convention and M-3R.1–M-3R.3 are merged. Both names denote the same milestone. |
| **GV-F / GV-O / GV-A / GV-V** | **M-VAL.2 / M-VAL.3 / M-VAL.4 / M-VAL.5** | UVI ADR §25.7 already defines **M-VAL.1**; these continue that sequence. `GV-*` names the ROI stage, `M-VAL.*` names the review milestone. No collision with `GV-2C`/`GV-2E`/`GV-3R` (ADR scopes) or `GV-3R-b` (evaluator formula version). |

**Dependency order and responsibility separation are preserved under either naming.**

---

## 31. Deferred decisions ledger

| # | Deferred decision | Why not decided here |
|---|---|---|
| **DD-1** | Exact typed reason-code vocabulary and namespace strings for evidence verification and benchmark refusal | Implementation detail; §11/§16.3 ratify that codes must be stable, typed and namespace-scoped, which is the boundary-relevant part. |
| **DD-2** | Which specific contracts land in `governance-contracts` versus stay capability-local | Requires the concrete contract shapes from TEV-1/BR-1; the ratified constraint is "shared only where no dependency cycle results" (§22). |
| **DD-3** | Whether any Policy Authority instance is *entitled* to act as benchmark approval verifier, and for which families | Requires an explicit entitlement contract; B-6 ratifies only that it is **not** the default. **Narrowed by §35 (D-04):** with composition-root trust-anchor ownership ratified and Policy Authority *ownership* explicitly excluded, DD-3 is **no longer on BR-2C's critical path**. It remains open only as a deployment-configuration question — whether a particular Policy Authority instance may be *configured as one approval verifier among others by the composition root*. If DD-3 is later found to govern an entitlement not covered by composition-root ownership, that specific entitlement re-enters scope; the general blocker does not. |
| **DD-4** | Structured benchmark successor/predecessor reference — shape, successor authorization, activation instant, predecessor invalidation, historical resolution across the boundary, cross-tenant/cross-family restrictions | Mirrors Policy Authority P-7/§13.4, deliberately kept on the same deferral track so the two do not diverge. |
| **DD-5** | A trusted **binding-verification** mechanism that could raise `AssessedSystemBinding.authenticity_status` above `STRUCTURAL_UNVERIFIED` | No merged contract defines one; inventing one here would mint an authority. |
| **DD-6** | Alignment of RA-5's RA-scoped `EvidenceAdmissionPort` with the platform TAP receipt | RA-5 is ratified and must not be reopened; alignment is a separate, later, separately-reviewed decision (E-13). |
| **DD-7** | Disclosure scope and retention of provenance / chain-of-custody references | A deployment/privacy concern requiring its own review (§27.7). |
| **DD-8** | Attestation cadence for benchmark definitions (the second half of UVI ADR §26.5) | Operational cadence, not a boundary; the *home* half is resolved here (§33). |
| **DD-9** | Exact byte constants — domain-separation tags, algorithm identifiers, encodings | Explicitly left to TEV-1/TEV-2 and BR-1/BR-2; ambiguity, fixed-point digests and unsigned "trusted" receipts are prohibited now (§13.3). |
| **DD-10** | Production persistence, distributed concurrency, and HSM/KMS posture for both capabilities | Mirrors Policy Authority §15.7; reference-grade first. |
| **DD-11** | `SystemManifest` home | **Remains open** at UVI ADR §26.3 / §20. Explicitly **not** resolved here (§14). |

---

## 32. Status ledger — RATIFIED / IMPLEMENTED / DEFERRED

Every claim carries exactly one status. **Nothing below is implemented.**

| Item | RATIFIED | IMPLEMENTED | DEFERRED |
|---|---|---|---|
| TAP owns platform-wide evidence admission and verification (E-1, E-2) | ✅ | ❌ | — |
| TAP never manufactures evidence / approves its own source (E-3, E-5) | ✅ | ❌ | — |
| One shared platform-wide Benchmark Registry (B-1) | ✅ | ❌ | — |
| Registry computes no observations/results/readiness/ROI (B-12) | ✅ | ❌ | — |
| Two capabilities interoperate but are never conflated (§3) | ✅ | ❌ | — |
| Fourteen-role separation matrix (§8) | ✅ | ❌ | — |
| Six self-authorization prohibitions (§8.1) | ✅ | ❌ | — |
| Verification-result coordinate set (§9) | ✅ | ❌ | ✅ contract shape = TEV-1 |
| Enumerated non-proofs (§10) | ✅ | ❌ | — |
| Deny-by-default without a trust anchor (E-8) | ✅ | ❌ | — |
| Fail-closed refusal surface + typed reasons (§11) | ✅ | ❌ | ✅ vocabulary = DD-1 |
| Six distinct trust stages; no collapsing boolean (§12) | ✅ | ❌ | — |
| Signed, immutable TAP verification receipt (§13) | ✅ | ❌ | ✅ shape = TEV-1, service = TEV-2 |
| Receipt authorizes nothing (§13.2) | ✅ | ❌ | — |
| Domain separation, versioning, deterministic canonicalization, key revocation (§13.3) | ✅ | ❌ | ✅ byte constants = DD-9 |
| Governance Contracts keeps `AssessedSystemBinding`; TAP does not own system identity (§14) | ✅ | ❌ | — |
| Binding remains `STRUCTURAL_UNVERIFIED`; no binding verifier minted (§14.5) | ✅ | ❌ | ✅ DD-5 |
| `canonical_subject_context_ref` stays an opaque digest-bound bridge (§14.6) | ✅ | ✅ *(already merged in `governance-contracts`)* | — |
| Governance Contracts / Readiness must not import Risk Authority (§14.7) | ✅ | ✅ *(holds at `d905c551`)* | — |
| `SystemManifest` not invented; home stays open (§14) | ✅ *(as a non-decision)* | ❌ | ✅ DD-11 |
| Benchmark definition identity (§15) | ✅ | ❌ | ✅ contract shape = BR-1 |
| Named publisher/signer role; not Policy Authority by default (B-6, §16.1) | ✅ | ❌ | ✅ entitlement = DD-3 |
| Six-stage registration ordering; no partial state (§16.2, §16.3) | ✅ | ❌ | ✅ BR-2 |
| Exact-only resolution, append-only, byte-identical idempotence, typed conflict (§17) | ✅ | ❌ | ✅ BR-2 |
| Cross-tenant non-disclosure (§17.6, §27.2) | ✅ | ❌ | ✅ BR-2 |
| Signed, entitled, resolution-verified revocation (§17.10, §17.11) | ✅ | ❌ | ✅ BR-2 |
| Exact structured supersession only; fail closed when undeterminable (§17.12, §17.13) | ✅ | ❌ | ✅ DD-4 |
| Historical resolution discloses `as_of`, implies no current validity (§17.1) | ✅ | ❌ | ✅ BR-2 |
| Definition / observation / comparison / policy separation (§18) | ✅ | ❌ | — |
| Policy Authority boundary; benchmark citation ≠ resolution (§19) | ✅ | ❌ | — |
| Readiness integration posture; RA-01 preserved (§20) | ✅ | ❌ | ✅ UVI-EV-1 |
| Governed Value posture; five-stage model preserved (§21) | ✅ | ❌ | ✅ GV-F → GV-V |
| Canonicalization / time / determinism properties (§22) | ✅ | ❌ | ✅ constants = DD-9 |
| Consumer and dependency matrix (§23) | ✅ | ❌ | — |
| Canonical names and placement (§6.2) | ✅ | ❌ | ✅ packages = TEV-2 / BR-2 |
| Three name collisions recorded and separated (§6.1, §6.3, §6.4) | ✅ | n/a | — |
| RA-5 seam preserved as the RA-scoped instance (E-13) | ✅ | ✅ *(RA-5 unchanged)* | ✅ alignment = DD-6 |
| Milestones TEV-1, TEV-2, BR-1, BR-2, UVI-EV-1, GV-F, GV-O, GV-A, GV-V | ✅ *(as sequence)* | ❌ | ✅ all nine |
| Any package, contract, verifier, registry, receipt, or reason code | — | ❌ | ✅ entirely |

**At completion of this ADR: ownership is RATIFIED; every new runtime capability remains
DEFERRED.**

---

## 33. Consistency mapping to existing ADRs

### 33.1 UVI ADR (`ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`)

| UVI item | Relationship |
|---|---|
| **D-3** (benchmark registry) | **Upheld and completed.** Immutable versions, digest-bound resolution, no silent substitution, "registry resolution creates no policy authority" — all restated. The *home* is now decided (B-1), and D-3's "Policy Authority governs admission" is reconciled additively (§34.1). |
| **§26.5** (benchmark registry home & attestation cadence) | **Home RESOLVED** by B-1/§6.2. **Attestation cadence remains open** as DD-8. |
| **D-8 / §12** (five evidence axes; caller labels never elevate) | **Upheld and operationalized.** This ADR supplies the missing *mechanism* by which `VerificationStatus` could ever be earned rather than asserted. Axis semantics unchanged. |
| **D-9** (synthetic evidence) | **Unchanged.** Synthetic evidence may be verified as authentic synthetic evidence; that never makes it `OBSERVED`, `ATTRIBUTED`, or sufficient for realized ROI. |
| **D-10 / §17** (execution → effect → attribution → verification) | **Unchanged and re-affirmed** (§21). |
| **D-11 / D-12** (valuation, conservative headline) | **Unchanged.** A receipt over one component never elevates the headline (§21). |
| **D-13 / §15** (geography/domain/intended outcome) | **Upheld and strengthened** — these are load-bearing benchmark identity, not cosmetic labels (§15). |
| **D-14 / §16** (assessed system, subject context) | **Preserved exactly.** No new owner, no `SystemManifest`, opaque bridge retained (§14). |
| **D-16 / §19** (policy roles: author → approver → compiler → issuer → registry → revoker) | **Mirrored** for evidence and benchmarks (§8). The "Registry / resolver" row's "UVI benchmark registry to be built" now names a platform owner. |
| **D-18** (one customer-facing capability) | **Upheld** — neither capability is a product or a fourth UVI engine (B-2). |
| **§20** (`BenchmarkReference` **values** → internal benchmark registry) | **Upheld.** This ADR owns the values; the `BenchmarkReference` *shape* stays a `governance-contracts` M-2E.1 item. |
| **§21** (dependency rules; benchmark registry depends only on governance-contracts) | **Upheld verbatim** (§23). |
| **§23.5** (determinations bind exact identity + digests) | **Extended** to evidence receipts and benchmark records. |
| **§23.10** (producers never self-attest/self-verify/self-approve) | **Ratified as structural rules** (§8.1). |
| **§25.3 (M-2C.2)** | **Superseded in ownership**, retained in name; split into BR-1/BR-2 (§30.1). |
| **§26.2** (RA `SubjectContext` dependency) | **Not resolved here** — out of scope; observation recorded at §14. |
| **§26.3** (`SystemManifest` home) | **Left open** deliberately (DD-11). |

### 33.2 Policy Authority ADR (`ADR_UGENCE_POLICY_AUTHORITY.md`)

| PA item | Relationship |
|---|---|
| **P-1 / §7.2** (one shared platform authority; second-system prevention) | **Pattern reused** for both capabilities (E-1, B-1). |
| **P-4 / §9** (roles remain separate) | **Extended** to fourteen roles (§8). |
| **P-5 / §11** (approval remains external; no self-approval; deny-by-default verifier; composition-root trust) | **Mirrored** for evidence verification (E-5, E-8) and benchmark approval (B-3, B-4, B-5, §16.1). |
| **P-8 / §14** (signed, authorized, resolution-verified revocation; historical resolution disclosure) | **Mirrored** for benchmark-version revocation (B-11, §17.10–§17.11, §17.1). |
| **§12** (versioned domain-separated canonicalization; remove-not-blank; no fixed-point digest; independent verification) | **Adopted verbatim** (§13.3, §22). |
| **§13 / P-6, P-7** (reject unstructured supersession; structured references deferred) | **Same posture** for benchmarks (B-11, DD-4), kept on the same deferral track. |
| **§15** (exact-only resolution; no `latest()`; append-only; immutable anchors; retrieval ≠ trusted resolution) | **Adopted verbatim** (§17). |
| **§6 row 4** (evidence admission → "evidence producers") | **Reconciled additively** — see §34.2. This is the one place an existing ADR assigns a role differently. |
| **§6.9 / §19.9 / §20** (benchmark-value governance separate and deferred) | **Upheld** — still not Policy Authority's; now has a named owner and remains DEFERRED (§34.2). |
| **§19.8** (authority must not become a runtime decision maker) | **Mirrored** (E-14). |

### 33.3 Risk Authority RA-5 (`ADR_RISK_AUTHORITY_RA5_EVIDENCE_CONTROL_ASSURANCE.md`, `RISK_AUTHORITY_RA5_SPEC.md`)

| RA-5 item | Relationship |
|---|---|
| **SPEC §3.2** ("TAP" = conceptual umbrella; Evidence Admission is a neutral seam; `ugence-tap-provider` is not the admission owner) | **Preserved and built upon.** This ADR names the platform-wide role RA-5 deliberately left unnamed, under the umbrella RA-5 retained (E-2, §6.1). |
| **SPEC §3.2 non-collapse rule** (assertion-support scoring ≠ evidence admission) | **Restated and extended** (§6.1). |
| **ADR decision 2** (two trust questions, two ports: admission vs control assurance) | **Unchanged.** |
| **ADR decision 3** (RA keeps the non-compensatory aggregation rule; no new authorization artifact) | **Unchanged** — a TAP receipt is not an authorization artifact (E-12). |
| **ADR decision 5** (trust binding intrinsic, not storage-partitioned) | **Adopted** (§27.3). |
| **`EvidenceAdmissionPort` scope** | **Remains RA-scoped** (E-13). Platform-wide extension was considered and **rejected** (§25.3). Alignment is DD-6. |

### 33.4 Risk Authority RA-6

Envelope/authority revocation remains Risk Authority's (RA-6). Evidence revocation, key
revocation, benchmark-version revocation and policy-version revocation are four **separate**
acts with separate owners; none is conflated (§26.8).

---

## 34. Additive amendments made to existing ADRs

Two ratified ADRs are amended **additively**. No earlier normative decision is rewritten,
weakened, or silently altered; each amendment is marked in place and explained here.

### 34.1 UVI ADR — D-3 and §26.5

**What was there.** D-3: "an internal **UVI benchmark registry**: domain owners curate
candidates; **Policy Authority governs admission and permitted uses** …". §26.5: "Benchmark
registry home & attestation cadence" listed as unresolved.

**Reconciliation.** D-3's *substance* — immutability, digest-bound resolution, no silent
substitution, resolution mints no authority — is **entirely upheld**. Two clarifications are
added:

1. **Home.** "Internal UVI benchmark registry" is read as *internal platform
   infrastructure*, not *UVI-owned*, consistent with UVI ADR §21 already drawing the
   registry as a peer of the UVI engines depending only on `governance-contracts`, and with
   the precedent by which §26.1 was resolved (a shared platform authority with UVI as first
   consumer). §26.5's **home** half is marked RESOLVED; its **attestation cadence** half
   stays open as DD-8.
2. **"Policy Authority governs admission."** Read as governing **permitted uses** — policy
   may require, reference, and constrain the use of exact benchmark coordinates — **not** as
   making the Policy Authority the benchmark **approver or signer**. That reading is forced
   by the Policy Authority ADR itself, which disclaims benchmark-value governance in §6.9,
   §19.9 and §20; the opposite reading would put two ratified ADRs in direct conflict and
   create the self-authorization loop P-5 exists to prevent.

### 34.2 Policy Authority ADR — §6 rows 4 and 9

**What was there.** §6 row 4: "**Evidence admission** | *owner instead:* evidence producers
under UVI ADR D-8/D-9." §6 row 9: "**Benchmark-value governance** | benchmark registry (UVI
ADR D-3) — separate and deferred."

**Reconciliation — row 4.** The *disclaimer* is upheld: the Policy Authority does not own
evidence admission. The *redirect* is corrected additively: **evidence producers produce
evidence; they do not admit or verify it** (E-3). Naming producers as the owner of admission
would ratify exactly the self-verification the same ADR forbids at §11.4 and that UVI ADR
§23.10 prohibits. Ownership is TAP (E-1). UVI D-8/D-9 remain the correct reference for the
*classification axes* the evidence carries — which is what that row was pointing at — and
they are unchanged.

**Reconciliation — row 9.** Upheld unchanged in substance: still not Policy Authority's,
still deferred. The redirect now names the **Ugence Benchmark Registry** as the owner rather
than an unbuilt UVI-internal one.

**Not amended.** No other row, ruling, ledger entry, or milestone of the Policy Authority
ADR is touched. P-1 … P-11 stand as written.

### 34.3 RA-5 ADR — cross-reference only

A short amendment note records that the platform-wide TAP verification role is now ratified
here, that RA-5's `EvidenceAdmissionPort` remains the **RA-scoped** instance, and that
alignment between them is DD-6. **No RA-5 decision, precondition resolution, port, contract,
or verdict is changed.**

---

## 35. BR-2 ratification ledger

The repository's permanent record of the BR-2 admission-boundary ratification.
Nineteen owner decisions, **D-01 through D-19**, all ratified. This section is
governance; the supporting architecture brief that produced it is evidence, not
a repository artifact, and is not authority here.

> **Amendment, 2026-08-20 — four subphases become five.** This supersedes
> D-01's original four-subphase ruling. Cryptographic trust, durable state and
> production composition carry **different threat models** and warrant separate
> delivery and closure audits, so they no longer share one closure. The
> consequential half of the change is BR-2B: it becomes **non-authoritative by
> construction** rather than by an injected default, which removes the need for
> a deny-all default to be load-bearing at a phase that ships no verifier at
> all. Two new decisions, **D-18** and **D-19**, record the surface and naming
> rulings that follow from it. §35.8 records which decisions are deliberately
> unchanged, so they are not re-opened.

### 35.1 Subphase allocation

| Subphase | Version | Ships | Must not ship |
|---|---|---|---|
| **BR-2A** | `0.1.0` | Registry and exact-resolution **contracts**: record, event, envelope and request shapes; the registry lifecycle vocabulary and its closed relation; one structural representation bound to each transition; typed outcomes; ports as Protocols; new digest domains; pure validation | Any engine, any store, any verifier, any clock read, any convenience resolver |
| BR-2B | `0.2.0` | **Non-authoritative lifecycle kernel**: deterministic transition validation, predecessor-digest checks, terminality, conflict and idempotency calculation; produces transition **plans** and typed refusals | Any store, any verifier, any clock — and any authoritative act: it **cannot admit, register, revoke or resolve** |
| BR-2C | `0.3.0` | **Cryptographic trust authority**: audited verifier, signing-frame verification, publisher/approver/revoker anchor resolution, key rotation and revocation. A verified result **binds exact artifact digest, role, key, profile and anchor revision** | Any storage, and any registry state whatsoever |
| BR-2D | `0.4.0` | **Durable registry authority**: transactional persistence, the trusted clock, compare-and-set transitions, concurrency protection, immutable event history, the process-local in-memory adapter, registry-event signing, and the **first authoritative** admission, registration, revocation and exact resolution. Closes with the **identity-locked composition root** | A backend chosen before DD-10 is ratified; any authoritative operation exposed before the composition root locks |
| BR-2E | `0.5.0` | **Production composition and operations**: tenant authorization, service APIs, deployment controls, migrations, backup/recovery, observability, operational audit export | Any new authority — BR-2E composes and operates what BR-2D made authoritative, and mints nothing of its own |

**Gating.** BR-2A is ratified and implemented. BR-2B may follow with **no
verifier, no store and no clock**: it is non-authoritative *by construction*, not
by an injected default, so nothing at that phase depends on a deny-all default
holding. BR-2C is blocked on **audited cryptographic engineering** — a secure
verifier and a composition-root trust-resolver design, specified and
independently audited, reusing neither the Policy Authority nor the Risk
Authority Ed25519 implementation. That blocker is engineering, not governance:
**no owner decision is outstanding for it.** BR-2D awaits DD-10 and BR-2C.
BR-2E awaits BR-2D.

### 35.2 Decision register — final dispositions

| ID | Question | Ruling as ratified |
|---|---|---|
| **D-01** | Is BR-2 subdivided, and along which boundaries? | **RATIFIED WITH PRECISION; AMENDED 2026-08-20 TO FIVE SUBPHASES.** Five separately auditable subphases (§35.1). The governing rule: **BR-2B may determine what transition *would be* valid; BR-2D is the first phase permitted to assert that a transition *occurred*.** BR-2B ships no verifier, so the injected deny-all default is a **BR-2C/BR-2D constraint**, not a BR-2B one: from BR-2C the injected verifier carries an exact deny-all default, and any reference or test verifier is **structurally refused in production** by the identity-locked composition root that closes BR-2D — not warned about. |
| **D-02** | Who is the admission authority? | **RATIFIED.** Four-party separation: publisher submits and signs; an independent approver supplies an authenticated approval; the registry validates prerequisites and appends records; the composition root supplies trust anchors, clock and production adapters. The registry never manufactures publisher authenticity or approval, and publisher approval of its own artifact is insufficient. |
| **D-03** | Must an admitted artifact carry a verified publisher signature? | **RATIFIED.** Mandatory before admission. An unsigned, malformed, unknown-key, revoked-key or invalidly signed artifact cannot become `ADMITTED` or `REGISTERED`. BR-2A may define the signed-submission contract and **must not implement or simulate signature verification**. |
| **D-04** | Who owns the benchmark trust anchors? | **RATIFIED WITH MODIFICATION.** The **composition root** owns and configures them, under seven binding constraints: exact deny-all default; no registry-minted anchors; no Policy Authority ownership; no import of the trusted-evidence trust-anchor directory; no exception to §23; **no second hidden trust store inside the registry**; production startup fails closed when a production trust resolver is absent. DD-3 is narrowed accordingly (§31). |
| **D-05** | What is the canonical registry key? | **RATIFIED WITH PRECISION.** Dual immutable indexing: the exact BR-1 locator → one immutable admission digest; admission/content digest → immutable canonical bytes and record identity. The resolver never accepts `BenchmarkReference` directly, and never `latest`, `active`, `current`, `stable`, `default`, wildcards, ranges, partial versions or build metadata. Admission requires the embedded lifecycle state to be exactly `APPROVED`. **Idempotency compares canonical bytes, not only digests.** |
| **D-06** | What happens on a duplicate or conflicting submission? | **RATIFIED WITH MODIFICATION.** Byte-identical resubmission is idempotent; every non-identical submission for an occupied exact locator is a typed conflict; last-writer-wins and publisher-partitioned coordinate squatting are prohibited. Unicode confusable handling is **rejection-only**: never casefold, NFKC-normalize or otherwise rewrite the canonical locator or the stored bytes. BR-2A defines the typed `CONFUSABLE_COORDINATE` refusal and the comparison contract, and **must not claim a complete implementation** until the deterministic algorithm and its version are specified and tested. |
| **D-07** | Is any convenience resolution permitted? | **RATIFIED.** None. The trusted resolution API accepts only the exact BR-1 locator and exact version. No `latest`, `active`, version selection, implicit default, fallback or compatibility coercion exists. Any future selection feature uses a separately named API, returns a distinct non-authoritative type, and receives its own ratification. |
| **D-08** | Which registration lifecycle states exist, and is any reversible? | **RATIFIED WITH PRECISION.** Five states: `SUBMITTED`, `ADMITTED`, `REGISTERED`, `REVOKED`, `REJECTED`, distinct from the artifact's embedded lifecycle state. Permitted forward transitions only; **no reverse transition and no self-transition**. `ADMITTED → REJECTED` only while no registration record has been appended. **No state named `ACTIVE`, `PUBLISHED`, `CURRENT`, `DEFAULT`, `SUSPENDED` or `DEPRECATED` may be introduced.** |
| **D-09** | Is revocation retroactive? | **RATIFIED WITH MODIFICATION.** `DENY_ALWAYS` for trusted resolution: a revoked version never resolves as admissible, regardless of any caller-supplied `as_of`. Historical inspection remains possible through a **separately named read-only API returning a distinct record type** that cannot be passed where a resolved registered artifact is required. `ALLOW_BEFORE_REVOCATION` may exist only as an explicit future composition-root policy, must never make a revoked artifact *currently* admissible, and is not part of BR-2A. |
| **D-10** | What are BR-2's supersession rules? | **RATIFIED.** Out of scope. Every supersession request, inference or version-order guess **fails closed** with a typed unsupported-operation result. **BR-2 must not infer authority from SemVer ordering** — a guessed supersession is an unsigned authority decision (§17.12). Blocks UVI-EV-1's supersession-aware paths; blocks nothing in BR-2. |
| **D-11** | Who owns the authoritative clock? | **RATIFIED WITH MODIFICATION.** One injected authoritative clock owns `recorded_at`. Publisher-supplied time is evidence, never registry time. Caller-supplied `as_of` is permitted **only** on explicitly historical inspection APIs and never bypasses `DENY_ALWAYS` or influences trusted exact resolution. **Zero clock skew** — no non-zero tolerance precedent exists in this repository and none is invented. No future-dated registration. A revocation's `effective_at` is validated against registry-observed time and its own signed record and can never reopen or reverse a revocation. **BR-2A and BR-2B read no clock; the authoritative clock arrives at BR-2D.** |
| **D-12** | Are registry records signed? | **RATIFIED; AMENDED 2026-08-20.** Through BR-2C, registry registration records and events are **unsigned** — no registry event exists at all before BR-2D. Publisher submissions require publisher signatures; approval assertions require their independent authority; revocation assertions require revoker signatures. Registry-generated artifacts are called **records or events, never verification receipts** — "receipt" is the trusted-evidence layer's word under §6.4, and no component issues the independent verification receipt validating its own action. Registry-event signing lands with BR-2D's event history, which is the first place an event exists to sign. |
| **D-13** | What is the tenant and visibility model? | **RATIFIED.** BR-1's model preserved exactly: tenant-scoped or explicitly platform-wide, declared and digest-bound, never inferred. Reads make not-found and not-permitted **externally indistinguishable**. No publisher-private or shared-by-policy visibility is added. Cross-tenant and platform-wide access is enforced by exact types and tested through constructor bypass, forged records and resolution attacks. |
| **D-14** | Who owns the durable store, and when? | **RATIFIED; AMENDED 2026-08-20.** BR-2A defines the durable-store port. **BR-2D** ships the clearly named **process-local** in-memory adapter, alongside durable persistence; **BR-2B ships no store of any kind**. Production composition raises a **typed startup error** when given the non-production adapter — a warning or docstring is insufficient. No Postgres, no reuse of Risk Authority persistence, no durable backend chosen before DD-10. Enforced by an allow-list of adapter classes checked by **interpreter identity**, not by a settable flag, in the identity-locked composition root that **closes BR-2D**. |
| **D-15** | What consistency model does BR-2 claim? | **RATIFIED.** Process-local atomicity and read-after-write behaviour, and nothing more. The port contract **explicitly disclaims** durability, multi-process coordination, distributed strong consistency, eventual-consistency safety, and cross-process atomic revocation. An unavailable guarantee **must not be represented as a Boolean capability that can be flipped**: a frozen typed descriptor plus an identity-checked adapter allow-list replaces any such flag. |
| **D-16** | Where does BR-2 live, and what does §6.2 become? | **RATIFIED.** New distribution `ugence-benchmark-registry-authority` at `packages/benchmark-registry-authority/`, namespace `ugence_benchmark_registry_authority`, initial version `0.1.0`. `ugence-benchmark-registry` stays at `0.1.0` with its zero-dependency proof intact. §6.2 amended to record the two layers. **BR-2 behaviour never goes inside BR-1.** |
| **D-17** | What exactly is guaranteed unchanged in BR-1? | **RATIFIED.** BR-2 CI preserves and independently reverifies: the pinned identity digests; the canonicalization version; the single BR-1 domain string; the curated public API; `BR1_BENCHMARK_REFUSAL_REASONS` including declaration order; the package suite and probe counts; package version `0.1.0`; the empty dependency list; and the platform-freeze substantive digest. BR-1's suite, probes and verifier run **unmodified**, and the pinned digests are recomputed independently from raw canonical bytes and again from the installed wheel. **Note:** the curated `api.__all__` and the `public_api.json` symbol map differ by exactly one, because `__version__` is carried separately as `package_version`. **Both counts are asserted and the manifest is not "corrected" to match.** Gates every subphase. |
| **D-18** | Does BR-2 curate one public surface or more than one? | **RATIFIED 2026-08-20.** **One** curated surface, `api.__all__`, at every subphase; no second curated surface and no second symbol manifest is introduced. The pinned surface counts are **milestone-scoped snapshots, not invariants**: they move deliberately at each version bump, and every assertion site moves with them — `packages/benchmark-registry-authority/public_api.json`, `tests/packaging/test_public_api.py:40-41`, and `verify_benchmark_registry_authority_distribution.py:337,361`. Two mechanisms make this the only coherent choice. `tests/packaging/test_public_api.py:118-125` derives from the **sealed contract-type registry** and requires every root-canonicalizable class to appear in `api.__all__`, so BR-2B's transition-plan and refusal types enter that surface by force. And `MANIFEST.in` enumerates its JSON manifests **by name** while `pyproject.toml`'s `packages.find` glob ships every module **automatically**, so a second manifest would ship in neither artifact while the code it describes shipped in both. |
| **D-19** | May a later subphase extend the exported-function naming allow-list? | **RATIFIED 2026-08-20.** The exported-function prefix allow-list at `tests/packaging/test_milestone_boundary.py:252-257` — `require_`, `is_`, `canonical_`, `bound_`, `fault_` — is **milestone-scoped, not permanent**. BR-2B extends it with the verbs its kernel needs, each chosen so that **no verb implies an authoritative act**. The registry-operation ban at `:225-249` — `register`, `admit`, `resolve`, `lookup`, `revoke`, `append`, `claim_slot`, `verify`, `sign`, `now`, `read`, `write`, `persist` — **stands unchanged at BR-2B**, and is what keeps the kernel non-authoritative in name as well as in fact. The two capability-token lists at `tests/contract/test_confusable_and_ports.py:158-176` and `tests/packaging/test_milestone_boundary.py:18-45` likewise become **milestone-conditional**: each token carries its unlock phase and the exact classes permitted to carry it then. **BR-2B requires none of them to unlock** — a non-authoritative kernel needs no engine, verifier, adapter, store, resolver or composition root. |

### 35.3 BR-1 freeze guarantees

BR-1 is a **frozen identity layer**. BR-2 adds no BR-1 field, changes no BR-1
digest, appends no member to BR-1's frozen refusal enum, defines no competing
coordinate type, and never mutates a stored BR-1 canonical artifact or its
identity digest. A silently shifted BR-1 digest would invalidate every reference
already issued against it, which is what makes BR-1 usable as a stable canonical
identity layer at all.

### 35.4 Two lifecycles, never merged

`lifecycle_state` is **inside** BR-1's identity digest, so the same content
yields a different digest as the label moves. Pinning admission at `APPROVED`
(D-05) fixes the artifact's digest for all time.

|  | BR-1 embedded lifecycle | BR-2 registry lifecycle |
|---|---|---|
| Owner | the artifact's author — a self-declaration | the registry — an observed, appended fact |
| Members | `AUTHORED · APPROVED · REGISTERED · REVOKED` | `SUBMITTED · ADMITTED · REGISTERED · REVOKED · REJECTED` |
| Evidential weight | **none** — B-5: a lifecycle enum on the artifact is not approval evidence | authoritative for resolvability, within the trust the composition root configured |
| Mutability | frozen and digest-bound, immutable forever | append-only events; no record is ever edited |

**BR-2 lifecycle events are a separate vocabulary and must never mutate the
stored BR-1 canonical artifact or its identity digest.** No field-name equality,
enum-value equality or conversion helper bridges the two automatically, in
either direction.

### 35.5 Exact resolution versus historical inspection

|  | Trusted resolution | Historical inspection |
|---|---|---|
| Question | "May I rely on this benchmark right now?" | "What did the registry hold, and when?" |
| Accepts | exact BR-1 locator and exact version, and nothing else | exact locator, plus an explicit timezone-aware `as_of` |
| `as_of` | **not accepted** — a present-tense question | mandatory, caller-supplied, disclosed on the result |
| Revoked artifact | **never resolves**, at any instant, under `DENY_ALWAYS` | visible as history, labelled, never admissible |
| Authorization | tenant check first, before any temporal or lifecycle check | identical; `as_of` never relaxes it |
| Selection | none | none |

The two return **different exact types**, and the second is structurally
unusable wherever the first is required. Type separation, not documentation, is
what stops a historical answer from being consumed as a current one.

### 35.6 Typed outcomes

| Case | Behaviour | Typed outcome |
|---|---|---|
| Byte-identical resubmission at an occupied locator | idempotent no-op returning the existing record and its original recorded time | `IDEMPOTENT_DUPLICATE` |
| Any non-identical submission at an occupied locator | typed conflict; last-writer-wins prohibited | `COORDINATE_SLOT_CONFLICT` |
| Same locator claimed by a second publisher | typed conflict; publisher-partitioned squatting prohibited | `COORDINATE_SLOT_CONFLICT` |
| Known digest arriving under a different locator | refused — an aliasing attack | `DIGEST_ALREADY_BOUND` |
| Locator visually confusable with an occupied one | rejection only; never rewrite the locator or the stored bytes | `CONFUSABLE_COORDINATE` |
| Equal digest, unequal bytes | integrity error; neither admits nor overwrites | `STORE_INTEGRITY_INVALID` |
| Stale `prev_event_digest` | refused — replay or rollback | `STALE_REGISTRY_SNAPSHOT` |
| Any supersession request or inference | fails closed | `UNSUPPORTED_SUPERSESSION` |
| Re-registration after revocation at the same locator | refused — `REVOKED` is terminal | `LIFECYCLE_CONFLICT` |
| Read for the wrong tenant, or for a nonexistent locator | externally indistinguishable — same code, same shape | `NOT_FOUND` |

BR-1's seventeen refusal reasons are frozen and §22.13 sorts refusals by
declaration index, so **BR-2 appends and never inserts, renames, re-values,
re-orders or removes**. The two vocabularies are disjoint with no alias in
either direction.

### 35.7 BR-2A closure

BR-2A is implemented at `packages/benchmark-registry-authority/` version
`0.1.0`, with a new additive path-scoped CI workflow. `benchmark-registry-ci.yml`
is **not modified**, and no other package or workflow is touched.

The delivering session implemented, tested, built and verified distributions,
ran author-owned adversarial probes and a measured gate-deletion mutation
analysis, and opened a draft pull request. **It did not conduct an independent
closure audit, and an author-owned test, probe or mutation run is not one.** A
separate session, on its own branch or clean worktree, must independently
reproduce the decisive claims — the BR-1 freeze matrix, the offline install with
its negative controls, the mutation ledger, both inventories, the state-machine,
chain-integrity and chain-substitution results, and the
no-caller-constructible-authority properties — and only that session may
recommend merge.

### 35.8 Five-phase amendment — what is deliberately unchanged

Recorded so that a later reader does not re-open a decision this amendment
already considered and left alone.

| Decision | Disposition under five phases |
|---|---|
| **D-03** (§35.2) | **Unchanged, and strictly stronger.** It rules that an unsigned, malformed, unknown-key, revoked-key or invalidly signed artifact cannot become `ADMITTED` or `REGISTERED`. Under five phases BR-2B cannot reach those states *at all*, by construction rather than by refusal. |
| **D-05** (§35.2) | **Unchanged text; closure splits.** Its ruling now spans two phases — idempotency-by-canonical-bytes is BR-2B *calculation*, admission-requires-`APPROVED` is BR-2D *assertion*. D-05 cannot be closed in a single audit; record which half closes where. |
| **D-06** (§35.2) | **Unchanged text; owner assigned.** It forbids claiming a complete Unicode confusable implementation until the deterministic algorithm and its version are specified and tested, but named no owner for completing it. That work is **BR-2B** conflict calculation. |
| **D-15** (§35.2) | **Unchanged, and needs no amendment.** D-15 carries no subphase letter: it rules on what *BR-2* claims, not on which subphase ships the store. Only its arrival point moves, and D-14 carries that sentence. |
| **D-09** (§35.2) | **Unchanged.** `ALLOW_BEFORE_REVOCATION` remains a possible future composition-root policy, which now lands at **BR-2E**. |

**Reserved authority-issued type names.** The three names reserved at
`packages/benchmark-registry-authority/src/ugence_benchmark_registry_authority/contracts/_authority.py:74-82`
— `BenchmarkAdmissionDecision`, `BenchmarkRegistrationEvent`,
`BenchmarkResolution` — have **BR-2D as their named unlock point**. All three
assert that something *occurred*, which is precisely what BR-2D is the first
phase permitted to say. Until then the gates at
`tests/packaging/test_milestone_boundary.py:103` and `:109` continue to enforce
their absence.

**Consequence, not a ruling.** BR-2B's new canonicalizable types must be
registered in `contracts/_seal.py`'s `REGISTERING_MODULES` **before the seal
closes**, or `canonical_bytes` refuses them as unregistered. This follows
mechanically from the sealed registry and requires no owner decision; it is
recorded here so it is not discovered late.

**Distribution text not corrected here.** Seventy-seven statements in
`packages/benchmark-registry-authority` assert the four-phase subdivision, 30 of
them inside `src/` and therefore shipped in both the wheel and the sdist. They
are corrected **with BR-2B**, so the text is corrected once rather than twice.

---

*Design-only ADR for every milestone except BR-1 and BR-2A. No authority is
minted here. Trusted evidence verification and benchmark **resolution** remain
**NOT implemented**; BR-2B, BR-2C, BR-2D and BR-2E in §30 remain DEFERRED and each
requires a separate reviewed phase.*
