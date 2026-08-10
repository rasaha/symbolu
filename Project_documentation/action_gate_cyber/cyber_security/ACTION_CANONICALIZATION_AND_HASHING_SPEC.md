# Action Canonicalization & Hashing Specification

**Status:** the frozen, byte-level contract underpinning every hash, signature, approval binding,
and audit chain in the admissibility gate. It is **implementation-independent** and MUST produce
**identical canonical bytes and digests across programming languages**. It is the substrate for
`ACTION_GATE_SPECIFICATION.md` (§8 approval binding, §9 audit record) and
`AGENT_ACTION_ADMISSIBILITY_MVP.md`. Documentation only — no production code; it does not modify
the action-gate architecture.

Conformance keywords **MUST / MUST NOT / SHOULD / MAY** are RFC-2119.

> **Hashing establishes byte-level identity, not truth.** A digest proves *what bytes were
> submitted/approved/logged*, never that the enclosed state is real, the delegator legitimate,
> the simulator accurate, or the external system safe. See §21.

---

## 1. Purpose and security properties

This document defines the exact canonical representation used for: action hashes, approval
binding, policy hashes, evidence hashes, audit-record hashes, replay prevention, and
modification detection. Required properties:

| Property | Requirement |
|---|---|
| Deterministic serialization | identical logical value → identical bytes, always |
| Language independence | Python/Go/Rust/JS/Java produce identical bytes |
| Field-order independence at input | input key order irrelevant; canonical order fixed (§2) |
| Type preservation | string ≠ number ≠ bool ≠ null; no cross-type coercion |
| Collision resistance | via a cryptographic hash + domain separation (§9, §17) |
| Unambiguous null/missing handling | absent key ≠ explicit `null`; both explicit (§3) |
| Stable approval binding | approval binds the exact action + policy digest (§10, §11) |
| Replay resistance | nonces + state-hash + sequence enforcement (§15, §16) |
| Domain separation | distinct hash domains per object class (§9) |
| Algorithm agility | algorithm id in every signed object; migration path (§17) |

Explicit non-property: **hashing does not establish the truthfulness of the enclosed data** (§21).

---

## 2. Canonical serialization standard

**Selected standard: RFC 8785 JSON Canonicalization Scheme (JCS)**, restricted by the narrow
**Action Profile** below. JCS is chosen because it is an established IETF standard, is
language-independent, and already fixes the hard parts deterministically:

| Concern | JCS rule (adopted) |
|---|---|
| Encoding | **UTF-8**, no BOM |
| Object-key ordering | lexicographic by **UTF-16 code unit** of the key |
| Array ordering | **preserved as given** (arrays are ordered; see §7 for set-like) |
| Whitespace | **none** between tokens |
| String escaping | JCS minimal escaping (control chars + `"` + `\`; no gratuitous `\uXXXX`) |
| Boolean | `true` / `false` |
| Null | `null` |
| Duplicate keys | **rejected** (I-JSON) |

**Action Profile extensions (narrow, mandatory):**

1. **No bare JSON numbers in any canonicalized authorization payload.** JCS serializes numbers
   via ECMAScript `Number` (IEEE-754 double), which is ambiguous/lossy for money, quotas,
   limits, thresholds, and integers beyond 2⁵³. Therefore **every numeric value is encoded as a
   typed string** (§4): decimal string (`"1234.56"`), minor-unit integer string (`"123456"`),
   or scaled integer string. A bare JSON number in a canonicalized payload is a **hard error**
   (`E_BARE_NUMBER`). This eliminates floating-point ambiguity by construction.
2. **No Unicode normalization at hashing time.** The canonicalizer preserves string content
   byte-for-byte (valid UTF-8 required); it MUST NOT silently apply NFC/NFKC. Per-field
   normalization requirements are declared by the signed schema and enforced at **validation**
   (reject non-conforming), never by rewriting during hashing (§6). This prevents the
   canonicalizer from silently changing identifier meaning.
3. **Unsupported values rejected:** JSON numbers `NaN`/`Infinity` (impossible in JSON, rejected
   if injected via extension), non-finite, and any value not expressible under this profile →
   hard error (§18).

No bespoke serializer is invented; JCS + this profile is the whole standard.

---

## 3. Required-versus-optional field handling

**Global rule.** An **absent key** and an **explicit `null`** are **different canonical inputs
and produce different digests** (JCS serializes `{}` vs `{"k":null}` differently). No implicit
defaults are inserted during hashing; defaults may exist only if the **signed schema version**
defines them, and such defaults are materialized *before* canonicalization by a schema-versioned
normalizer, never invented by the hasher.

Per-field treatment for the 24 canonical envelope fields (from `ACTION_GATE_SPECIFICATION.md` §2):

| Field | Omit? | Null? | Empty string? | Empty array/obj? | In ACTION hash? |
|---|---|---|---|---|---|
| `action_id` | no (R) | no | no | — | **excluded** (attempt id, §10) |
| `timestamp` | no (R) | no | no | — | **excluded** (submission time, §10) |
| `agent_identity` | no (R) | no | — | no | **id+key_id included; sig excluded** |
| `runtime` | no (R) | no | no | — | included |
| `model_provider` | no (R) | no | no | no | included |
| `delegator` | no (R) | no | — | no | included |
| `delegation_chain` | no (R) | no | — | **no** (≥1 link) | included |
| `objective` | no (R) | no | no | — | included |
| `tool` | no (R) | no | — | no | included |
| `operation` | no (R) | no | no | — | included |
| `target_resource` | no (R) | no | — | **no** (≥1) | included |
| `arguments` | no (R) | no | — | yes (`{}` allowed) | included (redacted, §8) |
| `credential_scope` | no (R) | no | — | no | included |
| `current_state_hash` | no (R) | no | no | — | included |
| `state_freshness` | no (R) | no | — | no | included |
| `linked_ticket` | **yes (O)** | yes* | no | — | included if present |
| `approvals` | **yes (O)** | no | — | yes (`[]`) | **excluded** (binds *to* action, §11) |
| `attestation` | **yes (O)** | yes* | — | no | **excluded** (evidence, §13) |
| `policy_version` | no (R) | no | no | — | included |
| `rollback_plan` | **yes (O)** | yes* | — | no | included if present |
| `reversibility` | no (R) | no | no | — | included |
| `expected_effects` | **yes (O)** | no | — | yes (`[]`) | **digest-referenced** (§10, §13) |
| `correlation_id` | no (R) | no | no | — | included |
| `sequence_id` | no (R) | no | no | — | included |

`*` For an optional field, the schema version MUST declare whether **absent** and **explicit
null** are semantically distinct. Where they are not distinct, the schema-versioned normalizer
MUST canonicalize to the **absent** form before hashing (so producers cannot create two digests
for one meaning). Required fields reject both omission and null at validation (fail-closed, §18).

---

## 4. Type normalization

All values are strings under the Action Profile (§2.1). Canonical string forms:

| Logical type | Canonical form | Notes |
|---|---|---|
| Timestamp | RFC-3339 UTC, `Z`, fixed fractional precision (§5) | e.g. `"2026-07-12T14:03:11.000Z"` |
| Duration | ISO-8601 duration string | e.g. `"PT10M"` |
| Integer (exact) | decimal string, no leading zeros, no `+` | `"0"`, `"-7"`, `"123456"` |
| Decimal (exact) | fixed-scale decimal string; scale declared by schema | `"1234.56"` (never a float) |
| **Money / limit / quota / threshold** | **minor-unit integer string** *or* exact decimal string + explicit `currency`/`unit` sibling | never IEEE-754; `E_BARE_NUMBER` otherwise |
| Floating-point (non-authorization only, e.g. confidence) | decimal string with declared precision | authorization-relevant values MUST be exact, never float |
| Resource identifier / ARN / cloud path | namespace-qualified string, verbatim (§6) | no silent case change |
| URL | RFC-3986 normalized by producer; verbatim at hashing | scheme/host lowercasing is producer's job, declared by schema |
| IP / CIDR | canonical text form (compressed IPv6, explicit prefix length) | `"2001:db8::/32"`, `"10.0.0.0/8"` |
| UUID | lowercase 8-4-4-4-12 | `E_AMBIGUOUS_ID` if malformed |
| Crypto key id | namespace-qualified string, verbatim | e.g. `"kms://acct/keys/k7"` |
| Binary data | base64url **without padding**, or a content digest reference | one form per schema field |
| Enum | exact declared symbol, case-sensitive | `E_INVALID_ENUM` otherwise |

**Money/limits/quotas/thresholds MUST NOT use binary floating-point.** They use fixed-unit
integer minor-units or exact decimal strings with a declared scale. This is a hard requirement,
enforced by `E_BARE_NUMBER` and schema type-checking.

---

## 5. Timestamp and freshness normalization

- **Format:** RFC-3339, always **UTC**, always suffix `Z` (no numeric offset; `+00:00` and other
  offsets are rejected → `E_BAD_TIMESTAMP`, normalized upstream by the producer).
- **Fractional seconds:** fixed precision of **exactly 3 digits (milliseconds)**; producers pad
  or (round-half-even) reduce to millisecond precision before canonicalization. `…T14:03:11Z`
  (no fraction) is rejected in canonical form; it MUST be `…T14:03:11.000Z`.
- **Leap seconds:** `60` in the seconds field is **rejected** (`E_BAD_TIMESTAMP`); producers map
  leap instants to `…:59.999Z` upstream.
- **Timezone:** non-UTC offsets rejected in canonical form (must be pre-normalized to `Z`).
- **Clock-skew metadata:** carried in `state_freshness{as_of, source}` and evaluated by the gate
  against per-class bounds; it is data, not a canonicalization rule.
- **Freshness reference time:** the gate's authoritative decision clock; `state_freshness.as_of`
  is compared to it. Canonicalization does not consult wall-clock.

**Semantic equivalence:** two timestamp strings canonicalize identically **iff** they denote the
same instant at millisecond precision after UTC/`Z`/3-digit normalization. `2026-07-12T14:03:11Z`
and `2026-07-12T15:03:11+01:00` MUST both be pre-normalized to `2026-07-12T14:03:11.000Z` and
then hash identically; the raw offset forms are not accepted in canonical bytes.

---

## 6. Resource and operation normalization

Canonical identity is **namespace-qualified and verbatim** (no silent lowercasing/rewriting):

| Field | Canonical identity |
|---|---|
| `tool` | `{server_id, tool_name}`, each a namespace-qualified string |
| `operation` | exact enum symbol from the registered operation taxonomy |
| `target_resource` | array of namespace-qualified resource URNs (e.g. `aws:arn:…`, `gcp:…`, `k8s:…`) |
| `credential_scope` | `{principal, permissions[sorted], ttl}` — permissions is a **set** (§7) |
| `agent_identity` | `{id (namespace-qualified), key_id}` (sig excluded, §10) |
| `delegator` | `{id (namespace-qualified), type}` |
| `policy_version` | `semver "+" policy_hash` (§12) |

**Case sensitivity:** identifiers are case-**sensitive** by default. Case-insensitivity applies
**only** where the identifier namespace explicitly defines it (e.g. a DNS label); such folding is
performed **by the producer per the signed schema**, and the canonicalizer then treats the result
verbatim. Ambiguous or unqualified identifiers → `E_AMBIGUOUS_ID`. Namespace qualification is
**mandatory** to prevent cross-cloud/cross-runtime collisions (an `arn:…` and a `gcp:…` naming
the "same" logical thing are distinct canonical identities).

---

## 7. Argument normalization

`arguments` is authorization-critical and included in the action hash (redacted, §8). Rules:

- **Nested objects:** JCS recursion; keys ordered per §2.
- **Ordered arrays (lists):** order preserved; reordering changes the hash.
- **Set-like collections:** a collection is treated as an unordered **set** (sorted by canonical
  element bytes, duplicates rejected) **only where the signed schema declares that field a set**
  (e.g. `credential_scope.permissions`). Absent a schema set-declaration, arrays are ordered.
- **Command-line arguments, environment variables:** ordered arrays of strings; verbatim.
- **SQL statements, shell commands, Terraform/Kubernetes objects:** treated as **opaque
  strings/structures, verbatim**. They are hashed exactly as submitted.

**No semantic equivalence is inferred.** Two syntactically different commands (`rm -rf /x` vs
`rm -fr /x`; two logically-equivalent SQL statements; two equivalent Terraform HCL orderings)
**hash differently** unless a **domain adapter** first produces an explicitly normalized action
representation (e.g. a parsed, canonicalized SQL AST or a planned Terraform resource-diff), which
is then the value that is hashed. Semantic normalization is an explicit, versioned adapter step —
never an implicit canonicalizer behavior.

---

## 8. Redaction and secret handling

Raw secrets/sensitive values MUST NOT be stored in audit records or hashed payloads merely to
stabilize a hash. Scheme:

- **Secret references:** a secret argument is represented by a **reference identifier** (e.g.
  `secretref://vault/path#version`), never the plaintext. The reference is what is hashed.
- **Keyed commitments (HMAC) where value-equality must be provable without exposure:** to prove
  "the same value was the one approved" without revealing it, use
  `commitment = HMAC(commit_key, canonical_value)` with a service-held `commit_key`. The
  commitment (not the value) enters the payload. HMAC (keyed) is distinct from a bare hash (§17).
- **Redaction markers:** redacted positions carry an explicit typed marker
  `{"__redacted__": "<ref-or-commitment>"}` so the structure (and thus the action identity) is
  stable while the value is hidden.
- **Low-entropy values:** a **bare hash of a low-entropy secret is PROHIBITED** (offline
  guessing / dictionary attack). Low-entropy sensitive values MUST use an **HMAC keyed
  commitment** (or not be committed at all), never `H(value)`.
- **Access-controlled audit payloads:** the full (redacted) envelope in the audit record is
  access-controlled; redaction ensures even audit readers do not see plaintext secrets.
- **Rotation implications:** references bind to a specific secret **version**; rotation yields a
  new reference (and thus a new action identity), which is correct — an approval for one secret
  version does not silently authorize a rotated value.

---

## 9. Domain-separated hashes

Every digest is domain-separated. Distinct domains:

`ACTION`, `APPROVAL`, `POLICY`, `EVIDENCE`, `SIMULATION`, `AUDIT_RECORD`, `AUDIT_CHAIN`,
`DELEGATION`, `EXECUTION_RESULT`, `EXECUTION_TOKEN`.

**Exact construction (length-prefixed framing to prevent concatenation ambiguity):**
```
digest = H(  LP(domain_tag)
          || LP(canonicalization_version)
          || LP(schema_version)
          || LP(canonical_bytes) )

LP(x)      = uint64_be(byte_length(x)) || x        # 8-byte big-endian length prefix
domain_tag = ASCII, e.g. "SYMBOLU/ACTIONGATE/ACTION/v1"
H          = the active hash (SHA-256 default, §17)
```
Length-prefixing each component makes the concatenation **unambiguous** (no field can smear into
the next). Domain tags are unique ASCII constants; the versioned suffix (`/v1`) allows domain
evolution. **A raw digest's meaning is never reused across object classes** — the same
`canonical_bytes` hashed under two domains yields two unrelated digests, by construction.

Example domain tags:
`SYMBOLU/ACTIONGATE/{ACTION,APPROVAL,POLICY,EVIDENCE,SIMULATION,AUDIT_RECORD,AUDIT_CHAIN,DELEGATION,EXECUTION_RESULT,EXECUTION_TOKEN}/v1`.

---

## 10. Action hash

`action_hash = digest(ACTION, canonical(action_payload))`, where `action_payload` is a JSON
object built **only** from the following fields (schema-versioned, §20):

**Included (authorization-relevant):** `agent_identity.{id,key_id}`, `runtime`, `model_provider`,
`delegator`, `delegation_chain`, `objective`, `tool`, `operation`, `target_resource`,
`arguments` (redacted, §8), `credential_scope`, `current_state_hash`, `state_freshness`,
`reversibility`, `rollback_plan` (if present), `linked_ticket` (if present), `policy_version`,
`correlation_id`, `sequence_id`, and `expected_effects_digest`.

`expected_effects_digest = digest(SIMULATION, canonical(expected_effects))` — the predicted
consequence is bound **by digest** (approval is for "this action *with this reviewed predicted
effect set*"; a different prediction is a materially different action requiring re-review), while
keeping the action payload bounded in size.

**Excluded (justified):**

| Excluded field | Justification |
|---|---|
| `action_id` | per-attempt id, not action **identity**; identical action content must yield an identical `action_hash` across resubmissions (approval stability). Attempt identity lives in the token/audit (§15). |
| `timestamp` | submission time is transport/temporal metadata; it cannot change authorization semantics. Replay is prevented by nonces + state-hash + sequence (§16), **not** by embedding submit time in the action identity. |
| `agent_identity.sig` | the signature is computed *over* the action payload; including it would be circular. `id`+`key_id` bind the acting key. |
| `approvals` | approvals bind **to** `action_hash` (§11); including them would be circular. |
| `attestation` | attestation is **evidence** bound separately to `action_hash` (§13); it rotates independently of action identity. |

Every excluded field is either self-referential (`sig`, `approvals`), pure attempt/transport
metadata (`action_id`, `timestamp`), or independently-bound evidence (`attestation`). No field
that can change the authorization decision is excluded.

---

## 11. Approval binding

An approval is a **signed object** in the `APPROVAL` domain over:
```
approval_payload = {
  action_hash, policy_hash, approver, approval_scope, decision, constraints,
  issued_at, expiration, nonce, approval_version
}
approval_hash = digest(APPROVAL, canonical(approval_payload))
signature     = SIGN(approver_key, approval_hash)          # §17: sign over the digest
```
- **Invalidation on modification:** any change to any field in §10's `action_payload` changes
  `action_hash`; the approval's bound `action_hash` no longer matches → **invalid**. Likewise a
  `policy_hash` change invalidates (policy re-evaluation required).
- **Constrained approvals authorize subsets:** an incoming action is authorized by an approval
  iff its normalized `(operation, target_resource, argument-bounds)` is **subsumed** by
  `approval_scope` under a declared, deterministic subsumption relation (subset of targets,
  argument values within approved bounds). A **broader** action is **not** authorized.
- **Multi-approver handshakes:** represented as **N independent signatures**, each over the same
  `{action_hash, policy_hash}` by an independent `approver` (preferred — each identity is
  separately auditable and SoD-checkable). **Threshold signatures** MAY be used where compactness
  outweighs per-approver auditability; the audit record MUST still record the constituent approver
  set. Dual-control = N≥2 independent, SoD-satisfying signatures.
- **Revocation:** approvals are revocable by `nonce`/`approval_id` on a signed revocation list
  checked at decision time.
- **Replay prevention:** `nonce` is single-use and bound to `action_hash`; reuse → reject.
- **Emergency (break-glass) approvals:** a distinct approval class with tighter `expiration`,
  mandatory post-hoc review, and stronger audit annotation — never a silent bypass.

**Approval MUST NOT bind only to `action_id` or a ticket title** — it binds the `action_hash` and
`policy_hash` (the content), per this section.

---

## 12. Policy hashing and root of trust

```
policy_bundle  = { rules[], metadata, parent_ref, root_ref, effective_time,
                   canonicalization_version, policy_schema_version }
policy_hash    = digest(POLICY, canonical(policy_bundle))
policy_version = semver "+" policy_hash
policy_sig     = SIGN(root_of_trust_key, policy_hash)
```
- **Root of trust:** the policy signing key is held **out-of-band** from the governed
  agents/runtime (MVP §4). A policy change is itself a governed action, but its authority roots
  outside the governed plane to avoid bootstrap circularity.
- **Parent/root policy:** `parent_ref`/`root_ref` express delegated/hierarchical policy; the
  chain is verifiable to a pinned root.
- **Effective time / rollback:** `effective_time` gates activation; rollback = activating a prior
  signed `policy_version`. In-flight approvals bound to a superseded `policy_hash` are invalidated
  (§11) — no silent drift.
- **Key rotation / revocation:** root keys rotate with overlap; revoked policy versions are on a
  signed revocation list.
- **Emergency policy changes:** still signed by the root of trust; faster review path with
  stronger audit — never unsigned.

**The decision record MUST record the exact `policy_hash` evaluated** (§14).

---

## 13. Evidence and simulation hashing

Each evidence item is an envelope in the `EVIDENCE` domain (simulation uses `SIMULATION`):
```
evidence_payload = {
  bound_to,                 # action_hash (post-action) OR {pre_action_correlation_id, current_state_hash}
  producer, generated_at, valid_until, evidence_version,
  fidelity_or_confidence,   # HIGH/MEDIUM/LOW or float, per §7 gate spec
  content_digest            # digest of the raw evidence content, same hash family
}
evidence_hash = digest(EVIDENCE | SIMULATION, canonical(evidence_payload))
```
Covered evidence: attestation, current-state snapshot, simulator output, blast-radius result,
human justification, AI advisory, and optional BCVF/USE/SCC signals.

- **Non-replay across actions:** `bound_to` binds evidence to a specific `action_hash` (or, for
  pre-action evidence, to a `{correlation_id, current_state_hash}` pair). Evidence generated for
  action X (one `action_hash`) is **not valid** for a materially different action Y (different
  `action_hash`), because the gate checks `evidence.bound_to == action_hash` at decision time.
- **Validity interval:** `generated_at`/`valid_until` bound freshness; expired evidence is
  rejected/escalated (gate spec §3).
- **AI advisory & optional BCVF/USE/SCC** are evidence items like any other — recorded, bound,
  and **advisory-only**; they never alter canonicalization rules or admit an action.

---

## 14. Audit-record canonicalization

```
audit_payload = {
  action_hash, decision, dispositive_rules[], policy_hash,
  evidence_hashes[], approval_hashes[], timestamps{received,decided,committed?},
  applied_constraints, execution_authorization_token_hash?, execution_result_hash?,
  canonicalization_version, envelope_schema_version, hash_algorithm_id
}
audit_record_hash = digest(AUDIT_RECORD, canonical(audit_payload))
signature         = SIGN(gate_audit_key, audit_record_hash)
```
**Append-only chaining** (`AUDIT_CHAIN` domain):
```
chain_hash_0 = digest(AUDIT_CHAIN, canonical({genesis: true, chain_id, canonicalization_version}))
chain_hash_n = H( LP("SYMBOLU/ACTIONGATE/AUDIT_CHAIN/v1")
               || LP(chain_hash_{n-1})
               || LP(audit_record_hash_n) )
```
- **Genesis:** an explicit signed genesis record fixes `chain_id`.
- **Checkpointing:** periodic **signed checkpoints** publish `(index N, chain_hash_N)`; a
  checkpoint MAY be externally anchored (e.g. timestamping authority) — *if and only if* that is
  actually implemented (see below).
- **Verification:** recompute the chain from a trusted checkpoint forward; any mismatch localizes
  tampering to a record.
- **Partial export:** export a contiguous record range plus its two boundary `chain_hash` values
  and a signed checkpoint covering the range; the importer verifies the sub-chain.
- **No overclaiming:** this is **tamper-evident given the audit signing key is protected**. It is
  **not** "blockchain" or "tamper-proof storage" unless external anchoring/immutable storage is
  actually deployed. Do not claim otherwise.

---

## 15. Execution authorization token

A short-lived, gate-signed token in the `EXECUTION_TOKEN` domain:
```
token_payload = {
  action_hash, permitted_operation, permitted_target, credential_scope,
  constraints, expiration, nonce, policy_hash, decision_record_hash
}
token_hash = digest(EXECUTION_TOKEN, canonical(token_payload))
token_sig  = SIGN(gate_key, token_hash)
```
The tool / credential broker **MUST reject** a call when any of:
- token **expired**;
- **nonce reused** (single-use, replay);
- **action modified** — recomputing `action_hash` from the actual call ≠ `token.action_hash`;
- **arguments expanded** — call arguments not subsumed by `constraints`/approved bounds;
- **different target** — call target ≠ `permitted_target`;
- **policy-version mismatch** where policy marks the class as requiring re-evaluation
  (`token.policy_hash` ≠ current active `policy_hash`).

The token is the credential-broker's enforcement handle: no valid token ⇒ no usable credential
⇒ no effect (MVP §9 bypass-resistance).

---

## 16. Replay and race-condition handling

| Vector | Handling |
|---|---|
| Duplicate action submission | idempotency on `action_id` + single-use `nonce`; duplicate committed decision returns the recorded outcome, not a re-execution |
| Approval replay | `nonce` single-use, bound to `action_hash` (§11) |
| Evidence replay | `bound_to == action_hash` check (§13) |
| Token replay | single-use `nonce`, short TTL (§15) |
| TOCTOU state change | **commit-time re-validation**: the gate recomputes/re-fetches `current_state_hash` at commit; if it ≠ the approved-against state hash and the delta exceeds the class-declared accepted bound → **re-evaluate or deny** |
| Concurrent conflicting actions | `sequence_id` monotonicity within `correlation_id` + optimistic concurrency on `current_state_hash` (first commit wins; the loser re-evaluates) |
| Sequence enforcement | monotonic `sequence_id`; out-of-order or gap where the class forbids it → escalate/deny |
| State-hash mismatch at commit | mandatory; mismatch beyond bound → re-evaluate or deny (never commit on stale approval) |

**Commit-time validation is REQUIRED**: an approval/decision authorizes a transition *from a
specific state*; the gate MUST confirm at commit that the current state still matches the approved
assumptions (exact `current_state_hash`, or a bounded, class-declared accepted delta) before
allowing the effect.

---

## 17. Hash algorithm and agility

- **Initial hash: SHA-256** — ubiquitous, FIPS-180-4, widely hardware-accelerated, broad
  multi-language library support. **SHA-512/256** is an approved alternative (length-extension
  resistant, faster on 64-bit) and SHOULD be preferred where those properties matter; the
  length-prefixed framing (§9) already neutralizes length-extension for SHA-256 use.
- **Algorithm identifier** (`hash_algorithm_id`, e.g. `"sha-256"`) appears in **every signed
  object** (approval, policy, audit, token). Verifiers select the algorithm from the id; they
  never assume.
- **Migration / dual-hash period:** during a transition, producers emit **both** digests and
  verifiers accept **either**; after cutover, the deprecated algorithm is rejected. Migration is
  a `canonicalization_version`/`hash_algorithm_id` bump (§20).
- **Prohibited:** MD5, SHA-1, and any non-cryptographic hash (CRC, xxHash, FNV, SipHash) for any
  security-relevant digest.
- **Hashing vs signing vs HMAC (distinct):** **HASH** = unkeyed integrity/identity (`action_hash`,
  digests). **SIGN** = asymmetric authenticity + non-repudiation over a digest (approvals,
  policy, audit, token). **HMAC** = keyed integrity/commitment (secret commitments, §8). They are
  not interchangeable.

---

## 18. Error handling — fail closed

Canonicalization MUST **fail closed** (no digest produced, action denied/escalated) on:

| Code | Condition |
|---|---|
| `E_DUP_KEY` | duplicate object key |
| `E_INVALID_UTF8` | invalid UTF-8 in any string |
| `E_BARE_NUMBER` | JSON number where a typed string is required (§2.1, §4) |
| `E_NAN_INF` | NaN / Infinity / non-finite value |
| `E_BAD_TIMESTAMP` | malformed / non-UTC / leap-second / wrong precision timestamp (§5) |
| `E_AMBIGUOUS_ID` | unqualified or malformed identifier (§6) |
| `E_UNKNOWN_SCHEMA` | unknown/unsupported `envelope_schema_version` or `canonicalization_version` |
| `E_INVALID_ENUM` | value not in the declared enum |
| `E_INVALID_SIGNATURE` | signature verification failure |
| `E_MISSING_CANON_RULE` | a mandatory canonicalization rule (e.g. set-declaration) is unavailable |
| `E_NON_NFC` | string not in required normalization where the schema mandates it (§2.2) |
| `E_REQUIRED_MISSING` | required field omitted or explicit null (§3) |

Errors are machine-readable (stable string codes above); a canonicalization error is a **hard
deny/escalate**, never a "best-effort" hash.

---

## 19. Conformance vectors

The **canonical byte form** is the frozen deterministic contract; the **digest** is a mechanical
function of `H(LP(domain)||LP(canon_version)||LP(schema_version)||LP(bytes))` (§9) and is produced
by the frozen reference harness (digests are not hand-authored here to avoid fabricating hash
values; canonical bytes are given where practical). ≥20 vectors:

| # | Description | Expected |
|---|---|---|
| V1 | `{"b":"1","a":"2"}` vs `{"a":"2","b":"1"}` (different input key order) | **same** canonical bytes → same hash |
| V2 | whitespace/indentation differences in input | **same** |
| V3 | optional field omitted vs `"linked_ticket":null` | **different** (§3) |
| V4 | `"count":"5"` (string) vs `"count":5` (number) | V-string valid; number → **reject** `E_BARE_NUMBER` |
| V5 | `2026-07-12T14:03:11Z` vs `…15:03:11+01:00` (both pre-normalized to `…14:03:11.000Z`) | **same**; raw offset form → `E_BAD_TIMESTAMP` |
| V6 | change one `arguments` byte | **different** `action_hash` |
| V7 | change `target_resource` | **different** |
| V8 | `credential_scope.permissions` expanded | **different** |
| V9 | `policy_version` change | **different** `action_hash`; approval invalidated |
| V10 | approval `expiration` changed | **different** `approval_hash` |
| V11 | altered `rollback_plan` | **different** `action_hash` |
| V12 | reorder a schema-declared **set** (`permissions`) | **same** (sorted) |
| V13 | reorder an **ordered** list (e.g. CLI args) | **different** |
| V14 | duplicate key in input | **reject** `E_DUP_KEY` |
| V15 | NaN / Infinity injected | **reject** `E_NAN_INF` |
| V16 | Unicode: `"é"` NFC vs `"e"+U+0301` NFD in a NFC-required field | **reject** `E_NON_NFC` (producer must normalize); as raw distinct strings elsewhere → **different** |
| V17 | secret as `secretref://…#v1` vs raw plaintext | plaintext in a secret field → **reject**; two different versions → **different** |
| V18 | audit-chain: recompute `chain_hash_n` from checkpoint | **verifies**; single altered record → mismatch localizes it |
| V19 | replayed execution token (reused nonce) | **reject** at broker (§15) |
| V20 | TOCTOU: `current_state_hash` at commit ≠ approved, delta > bound | **re-evaluate or deny** (§16) |
| V21 | `action_id`/`timestamp` differ, all else identical | **same** `action_hash` (both excluded, §10) |
| V22 | same bytes hashed under `ACTION` vs `EVIDENCE` domain | **different** digests (domain separation, §9) |
| V23 | `model_provider`/`runtime` changed | **different** `action_hash` (included, §10) |
| V24 | low-entropy secret committed via bare `H(value)` | **reject**; require HMAC commitment (§8) |

The reference harness (frozen with this spec) MUST include these as executable fixtures with
concrete canonical bytes and computed digests before any service is built (§22).

---

## 20. Compatibility and versioning

Five independently-versioned identifiers, all present in signed objects:

| Id | Governs |
|---|---|
| `canonicalization_version` | the rules in *this* document |
| `envelope_schema_version` | the action-envelope field set/types |
| `policy_schema_version` | the policy language/bundle |
| `signature_format_version` | signature container format |
| `hash_algorithm_id` | the active hash (§17) |

**Rules:** MINOR/PATCH changes MUST be additive and MUST NOT change the canonical bytes or digest
of any previously-valid object. A MAJOR change (which could alter existing digests) requires a new
`canonicalization_version` and a dual-verify migration window. **No version may silently
reinterpret existing signed content** — a verifier selects rules strictly by the object's declared
versions.

---

## 21. Can and cannot prove

**Can establish:**
- byte-level deterministic identity across languages;
- modification detection (any authorization-relevant change ⇒ different `action_hash`);
- approval binding to the exact action + policy digest;
- replay resistance **when** nonce/state/sequence mechanisms are enforced (§15, §16);
- audit-chain integrity verification (tamper-evident given a protected audit key).

**Cannot establish:**
- correctness of the action;
- truth of the submitted state (`current_state_hash` proves *what was claimed*, not that it is
  real);
- simulator accuracy;
- legitimacy of the delegator;
- safety of the external system;
- absence of endpoint/tool compromise below the enforcement layer.

---

## 22. Relationship to implementation

This document MUST be **frozen** (as `canonicalization_version` v1) **before** any of: executable
conformance fixtures, the approval service, the audit logger, the credential broker, the MCP
adapter, or the conformance suite are built — all of them depend on identical canonical bytes.

Implementations MUST use **official, audited cryptographic libraries** for SHA-256/SHA-512-256,
signatures, and HMAC. Implementations **MUST NOT** hand-roll hash primitives, serializers that
deviate from RFC 8785 + the Action Profile, or bespoke cryptography. The canonicalizer SHOULD be a
single shared, versioned library reused by every component to guarantee byte-identical output.

---

## Validation (performed on this document)

- ✓ **Every canonical action-envelope field has a defined hashing treatment** — §3 table covers
  all 24 fields (omit/null/empty/in-action-hash); §10 fixes inclusion/exclusion.
- ✓ **No field is ambiguously omitted** — every field is listed once with explicit rules.
- ✓ **Omitted vs null behavior explicit** — §3 global rule + per-field `*` schema declaration.
- ✓ **Money/limits avoid binary floating-point** — §2.1 + §4 (typed strings / minor-unit
  integers; `E_BARE_NUMBER`).
- ✓ **Domain separators unique** — §9 ten distinct tags, length-prefixed framing.
- ✓ **Action hash binds every authorization-relevant field** — §10 inclusion list; exclusions all
  justified (attempt/transport/self-referential/evidence).
- ✓ **Approval binds the exact action and policy** — §11 (`action_hash` + `policy_hash`, not
  `action_id`/ticket).
- ✓ **Evidence cannot be silently reused across actions** — §13 `bound_to == action_hash`.
- ✓ **Commit-time state validation defined** — §16 (TOCTOU re-check, required).
- ✓ **No AI/optional extension affects canonicalization rules** — §8/§13 (advisory evidence only);
  no rule depends on AI/BCVF/USE/SCC.
- ✓ **No bespoke cryptography** — §2 (RFC 8785), §17 (SHA-256/512-256), §22 (official libs only).
- ✓ **Consistent with `ACTION_GATE_SPECIFICATION.md` and `AGENT_ACTION_ADMISSIBILITY_MVP.md`** —
  same 24 fields, same six domains + EXECUTION_TOKEN, approval/audit/token hashes match the gate
  spec's §8/§9 and MVP §8/§9; no architecture changed.
