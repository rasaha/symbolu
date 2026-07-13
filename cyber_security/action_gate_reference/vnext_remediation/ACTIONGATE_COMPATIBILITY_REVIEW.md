# ACTIONGATE_COMPATIBILITY_REVIEW — adding remediation without breaking anything (vNext)

Status: **DESIGN ONLY.** Question 8: can `required_changes[]` (and `all_unmet_conditions[]`)
be added without breaking SDK, CLI, MCP, JSON schema, conformance vectors, the reference
implementation, and versioning? **Yes — as a purely additive extension (SemVer MINOR).**

## 1. What is added, precisely

- Two **new, optional** keys inside a **new, optional** `remediation` object on the decision
  response. Existing decision keys (`outcome`, `dispositive_rules`, `applied_constraints`,
  `action_hash`, `policy_hash`, `state_trace`, `terminal`, `reason`, `hash_algorithm_id`) are
  **unchanged in name, type, and meaning**.
- New `R_*` `reason_code` values, namespaced apart from existing `E_*` error codes.
- **No** new outcome value (Recommendation A). **No** change to operators, precedence,
  thresholds, projection, binding, or the audit payload.

## 2. Surface-by-surface impact

| surface | today | after | breaking? |
|---|---|---|---|
| **Reference gate `gate.evaluate`** | returns decision dict | same dict + optional `remediation` computed post-decision from the same inputs | **No** — additive key; existing keys byte-stable |
| **JSON schema** (`fixtures/envelope.schema.json` for input; response shape) | envelope schema governs *input* and is untouched; response is a superset | response gains an optional `remediation` object (added to the response schema, `additionalProperties`-tolerant) | **No** — optional field; old consumers ignore it |
| **Conformance vectors** (`conformance.py VECTORS`, `fixtures/conformance_vectors.json`) | assert canonicalization/hashing/binding invariants (`same`/`different`/`reject:E_*`) and **pinned digests** (`action_hash`, canonical bytes) | all 24 vectors and every pinned digest are unaffected — remediation touches no canonical byte, no digest, no binding | **No** — add *new* vectors for remediation separately |
| **Audit** (`audit.build_audit_record`) | hashes a fixed payload (no full decision dict, no `remediation`) | payload schema unchanged; `remediation` deliberately excluded | **No** — every existing `audit_record_hash` and chain head is identical |
| **`action_hash`** (`projection.PROJECTION_MANIFEST`) | fixed field set | unchanged; `remediation` is not projected | **No** — hashes identical |
| **SDK** (typed clients) | decision model | add optional `remediation?` field | **No** — additive; older SDKs ignore unknown field if tolerant, so ship as MINOR and document |
| **CLI** (`action_gateway*/cli.py`) | prints outcome/rules | optionally prints remediation when present/disclosed | **No** — additive flag (e.g. `--explain`) |
| **MCP** (`action_gateway_mcp` protocol/server) | returns decision | returns decision + optional `remediation` per disclosure | **No** — MCP result objects are open maps; add a field |
| **Reference implementation** | pure `D` | pure `D` + a separate read-only `derive_remediation(decision, envelope, policy, evidence, approvals)` helper | **No** — new function; `D` untouched |
| **Versioning constants** (`CANONICALIZATION_VERSION`, `ENVELOPE_SCHEMA_VERSION`, `POLICY_SCHEMA_VERSION`) | fixed | **unchanged** — no canonicalization, envelope, or policy schema change | **No** |

## 3. The two compatibility-critical invariants (must be conformance-tested)

1. **Hash invariance.** For every existing conformance vector, `action_hash`,
   `policy_hash`, `approval_hash`, `evidence_hash`, and `audit_record_hash` are **bit-identical**
   before and after the change. This is guaranteed structurally because `remediation` is
   excluded from all four projections/payloads — but it must be asserted, not assumed.
2. **Decision invariance.** For every existing vector, `(outcome, dispositive_rules,
   applied_constraints, terminal, state_trace)` are unchanged. Guaranteed because
   `derive_remediation` runs *after* `D` and feeds nothing back.

If either invariant ever fails, the change is no longer additive and must be halted.

## 4. Consumer-tolerance considerations

- **Unknown-field tolerance.** The envelope validator fails closed on unknown *required*
  fields (`schema.validate_envelope`), but that governs **input** envelopes, not **response**
  objects. Response consumers must tolerate unknown keys. Well-behaved SDK/MCP clients already
  treat result maps as open; a conformance note should require additive tolerance. For any
  strict client, MINOR versioning plus a capability flag (below) is the safety valve.
- **Capability negotiation.** Add an optional request capability
  (`supports_remediation: true` / MCP capability / CLI `--explain`) so the gate omits
  `remediation` for callers that did not opt in. This makes the change invisible to
  non-upgraded consumers and lets disclosure default to NONE when unrequested.

## 5. Versioning recommendation

**Additive extension → SemVer MINOR (e.g. gateway/SDK 1.x → 1.(x+1)).**

Rationale:
- No existing field changes type or meaning; no outcome added; no hash changes.
- Behavior for callers that do not request remediation is byte-identical.
- The canonicalization/envelope/policy schema versions do **not** change (nothing in the
  signed, hashed surface changed), so **no policy re-signing and no re-issuance of conformance
  golden hashes** is required.

A **major** bump would only be warranted if a seventh outcome were added (it is not —
Recommendation A) or if `remediation` were folded into the hashed audit payload (it is not).
A bare "patch" is too low because a new optional field in the public response is a feature.

## 6. Rollout gating

Ship the MINOR only when a CI job proves, over the full existing conformance-vector set:
`hash_invariance == True` **and** `decision_invariance == True`, and that at disclosure NONE
the `remediation` key is absent. New remediation behavior gets its **own** new vectors
(reason codes, classes, disclosure redaction, the DENY-never-retryable assertion) so the old
golden set is never edited.
