# Prerequisite A — Trusted-Signal Provenance & Integrity

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Closes design open question **Q3**
(`docs/design/action_clearance/OPEN_QUESTIONS.md`). This document defines *how Action Clearance decides
that a current-state signal is trustworthy enough to evaluate*. It changes no runtime code and adds no
field to the merged `TrustedSignal` neutral core — it **extends** that model with an integrity/provenance
projection consumed by the evaluator's fail-closed rules.

## A.1 The question this answers

The merged `TrustedSignal` model (`docs/design/action_clearance/TRUSTED_SIGNAL_MODEL.md`) is
tenant-bound, subject-bound, time-bound, source-identified, integrity-verifiable, freshness-evaluable,
and immutable. It does **not** yet say *how* `integrity_digest` and `provenance_ref` are produced and
verified per `source_kind`. That is the gap this document closes. The evaluator itself performs **no**
external calls and holds **no** credentials or keys; it evaluates provenance evidence that the ingestion
boundary has already attached.

## A.2 Minimal provenance model (MVP shadow)

The neutral core keeps its ten core-required fields unchanged. Provenance is expressed as a compact
sub-structure carried alongside each signal, `SignalProvenance`, evaluated but never fetched:

| Field | Maps to merged field | Purpose |
|---|---|---|
| `signal_id` | `signal_id` | stable id within the bundle |
| `signal_type` | `signal_type` | which fact is asserted |
| `tenant_id` | `tenant_id` | tenant the signal belongs to; must equal `request.tenant_id` |
| `subject_ref` | `subject_ref` | subject/target described; must bind to the action identity |
| `authorization_ref` | *new projection* | the authorization the signal relates to (may be `null` for global signals such as `ACTIVE_INCIDENT`) |
| `action_fingerprint` | *new projection* | the exact action the signal relates to (`null` for non-action-scoped signals) |
| `source_id` | `source_ref` | emitting source **instance** id |
| `source_kind` | `source_kind` | class of source (identity/incident/change-mgmt/github/execution-ledger/policy/target) |
| `adapter_id` | *adapter ext* | adapter that normalized the fact |
| `adapter_version` | *adapter ext* | adapter build/version that produced this signal |
| `captured_at` | `captured_at` | when the source observed the fact |
| `valid_until` | `valid_until` | freshness bound (conditionally required) |
| `normalized_value` | `value` | deterministic normalized state |
| `content_digest` | `integrity_digest` | digest over the canonicalized signal content |
| `provenance_ref` | `provenance_ref` | audit reference to how the value was obtained |
| `ingestion_boundary` | *adapter ext* | which trust boundary admitted the signal |
| `policy_refs` | `policy_ref` | policy/version(s) that permit this source for this signal type |
| `signature_ref` | *conditional* | reference to a MAC/signature envelope (Level 2/3 only) |

`adapter_id`, `adapter_version`, `ingestion_boundary`, and `signature_ref` live in the **adapter
extension map**, not the neutral core — the core evaluates their presence against policy but does not
mandate their shape. This keeps the merged `trusted_signal.schema.json` unchanged; the provenance schema
(`trusted_signal_provenance.schema.json`) is an additive design artifact.

## A.3 Integrity levels

Three levels, in increasing strength. The required level is a **policy decision per signal type and
operating mode**, not a global constant.

### Level 1 — trusted-ingestion digest
- trusted adapter identity (`adapter_id` on an approved list),
- deterministic normalization (`SIGNAL_NORMALIZATION_AND_DIGESTS.md`),
- `content_digest` over the canonical content,
- controlled `ingestion_boundary` (the signal entered through a known, authenticated ingress).

No producer key is required. The trust root is the **ingestion boundary + adapter registry**, not a
cryptographic producer signature.

### Level 2 — keyed authentication
- all Level-1 fields, plus
- a MAC or service-authenticated envelope over the signal (`signature_ref`),
- verifier identity + key-rotation metadata owned by the platform key service.

### Level 3 — signed signal
- a producer **signature** over the canonical content,
- a verifiable key identity (KID) resolvable to an approved producer,
- durable signature evidence retained for audit.

## A.4 Required level by mode (decision)

| Operating mode | Required integrity level | Rationale |
|---|---|---|
| **MVP shadow** (no dispatch) | **Level 1** for all signals | shadow cannot execute; trusted-ingestion digest + approved adapter is sufficient, and it is the only level the current repository can satisfy without a key service |
| **Recommendation mode** | **Level 1** core signals; **Level 2** for `PRIOR_CONSUMPTION` and `AUTHORIZATION_VALIDITY` | recommendations influence humans; the consumption/authorization signals gate the safety story |
| **Enforced execution** | **Level 2** minimum for every mandatory signal; **Level 3** where a producer key exists | enforcement acts on the signal; a keyed envelope is the floor |
| **High-risk domains** (freeze override, incident suppression, security-status) | **Level 3** | these signals can *unblock*; forging one is the highest-value attack |

**Decision:** MVP shadow adopts **Level 1**; the package core is built to *evaluate* all three levels
from day one (the required level is policy, not code), so raising the bar for enforcement needs **no
contract change** — only a policy/registry change. Public-key signatures are **not required for MVP**
because the repository has no producer-key infrastructure today and shadow mode never executes; Level 3
is an enforcement/high-risk prerequisite, not an MVP one.

## A.5 Condition handling (fail-closed)

Every provenance failure resolves to a fail-closed result — never to `CLEAR`. These rows **extend**, and
never contradict, the merged condition table in `TRUSTED_SIGNAL_MODEL.md`.

| Condition | Detection | Result | Reason code |
|---|---|---|---|
| missing provenance | required provenance evidence absent | **BLOCK** | `SIGNAL_UNTRUSTED` |
| unknown source | `source_id`/`source_kind` not in registry | **BLOCK** | `SIGNAL_UNTRUSTED` |
| unapproved adapter | `adapter_id` not approved for this signal type | **BLOCK** | `SIGNAL_UNTRUSTED` |
| adapter-version mismatch | `adapter_version` not in `approved_versions` | **BLOCK** | `SIGNAL_UNTRUSTED` |
| digest mismatch | recomputed `content_digest` ≠ presented | **BLOCK** | `SIGNAL_UNTRUSTED` |
| tenant mismatch | `signal.tenant_id ≠ request.tenant_id` | **BLOCK** | `TENANT_MISMATCH` |
| subject mismatch | `subject_ref` not bound to action identity | **BLOCK** | `SUBJECT_MISMATCH` |
| authorization mismatch | `authorization_ref` ≠ request authorization (for action-scoped signals) | **BLOCK** | `SUBJECT_MISMATCH` |
| signal replay | duplicate `(signal_id, content_digest)` presented as fresh state | dedup; identical fingerprint (no new trust) | — |
| expired signal | `valid_until < evaluation_time` | **HOLD** | `SIGNAL_STALE` |
| stale signal | `captured_at` older than policy max-age | **HOLD** (BLOCK by policy) | `SIGNAL_STALE` |
| conflicting signals | two signals of one type disagree | **ESCALATE** | `SIGNAL_CONFLICT` |
| source unavailable | required signal `status == UNKNOWN` | **HOLD** (fail closed) | `SIGNAL_MISSING` |

**Missing mandatory trust evidence must fail closed.** A signal that *declares* a trust-required slot but
supplies no valid `content_digest`/`signature_ref` at the required level is `SIGNAL_UNTRUSTED → BLOCK`; a
signal whose slot is not even declared is a `NON_RETRYABLE_ERROR` exception (malformed request), not a
result.

## A.6 What stays out of the core

The evaluator does not verify signatures against a live key service, does not call an adapter, does not
read the registry from a network endpoint, and holds no key material. It receives (a) the signal, (b) its
provenance evidence, and (c) an **immutable source-trust projection** (`SIGNAL_SOURCE_REGISTRY.md`) — and
applies deterministic fail-closed rules. Signature/MAC verification for Level 2/3 is performed at the
**ingestion boundary / workflow layer** before the evaluator runs; the evaluator only checks that the
required evidence is present, well-formed, and matches the registry policy.

## A.7 Closure

Prerequisite A is **CLOSED_BY_NEW_PRODUCT_INTERFACE** (the additive `SignalProvenance` projection + the
source-trust projection contract) with an MVP integrity level of **Level 1**. See
`prerequisite_decisions.json` decision `PA-*` and `trusted_signal_provenance.schema.json`.
