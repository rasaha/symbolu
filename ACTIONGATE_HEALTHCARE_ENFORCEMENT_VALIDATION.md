# ActionGate — Healthcare Enforcement & Adversarial Validation

**Status:** Simulation harness. Self-contained enforcement layer
(`agentic/healthcare/enforcement/`) around the healthcare decision package.
Synthetic records only — no real hospital connection.

> **Passing these synthetic enforcement tests does not establish legal
> compliance, clinical safety, or readiness for deployment in a real hospital.**
> It demonstrates that, in simulation, a governance decision's constraints are
> mechanically enforced and cannot be ignored, widened, replayed, or bypassed.

---

## 1. Decision vs enforcement

- **Decision** (`agentic/healthcare`): *may* this class of access occur, under
  which authority mode, with which minimum-necessary constraints? Produces a
  `HealthcareAccessDecision`.
- **Enforcement** (`agentic/healthcare/enforcement`): the decision is turned into
  a **signed authorization artifact**, and a separate adapter re-verifies every
  material fact at execution time and returns only the permitted, projected,
  redacted subset from a simulated HIS/EMR. **The calling agent is never trusted
  to honor constraints.**

A decision alone is advisory until it is bound into an artifact and enforced at
the retrieval boundary. This layer proves the binding holds.

## 2. Authorization artifact contract

`AuthorizationArtifact` is HMAC-signed over all binding fields (a real
deployment substitutes asymmetric signing + key custody). It binds:

authorization ID; tenant/hospital ID; actor ID and role; AI agent identity +
version; patient reference; encounter reference; purpose; authorized operation;
permitted data categories; excluded data categories; required redactions; max
record count; approved destination; internal/external restriction
(`allow_external`, `destination_class`); onward-disclosure restriction; approval
status; policy-book version + hash; governance + model versions; issued time;
expiry; nonce; one-time flag; policy-freshness flag; final authority used;
consent state; signature.

Only `ALLOW` / `ALLOW_WITH_CONSTRAINTS` decisions produce an artifact.
`DEFER` / `REQUIRE_APPROVAL` / `DENY` produce **no executable authorization**
(the issuer returns `None`).

## 3. Simulated HIS/EMR architecture

`SyntheticEMR` is a multi-tenant / multi-patient / multi-encounter store of
clearly-synthetic values (`SYN-…`), including restricted narratives, an
authentication-secret sentinel (`SYN-SECRET-DO-NOT-RETURN-…`), and a synthetic
prompt-injection string embedded in the clinical note. The EMR is intentionally
"dumb" — it returns whatever category it is asked for. Confidentiality is
enforced entirely by the adapter, which only ever asks for the artifact-permitted
subset. This mirrors a real HIS where the enforcement proxy, not the datastore,
is the trust boundary.

## 4. Field projection and redaction

On a passing execution the adapter:

1. intersects the caller's requested categories with the artifact's permitted set
   (any extra → `E_SCOPE_WIDENING`, reject — not silently dropped);
2. drops restricted/prohibited categories defensively even if somehow permitted;
3. fetches only the resulting categories from the EMR;
4. masks configured categories (e.g. identity documents → `***MASKED***`);
5. never emits the credential sentinel;
6. returns the payload to the caller and a **PHI-free receipt** for audit.

`ALLOW_WITH_CONSTRAINTS` therefore yields a strictly reduced payload; the audit
records released/excluded categories and redactions, never values.

## 5. Tenant / patient / encounter binding

Execution re-checks `tenant_id`, `actor_id`, `agent_id`, `patient_ref`, and
`encounter_ref` against the artifact. Any mismatch is rejected
(`E_TENANT_MISMATCH`, `E_ACTOR_MISMATCH`, `E_AGENT_MISMATCH`,
`E_PATIENT_MISMATCH`, `E_ENCOUNTER_MISMATCH`) — so an artifact cannot be replayed
against another patient, a historical encounter, another hospital, or by another
agent.

## 6. Replay protection

Artifacts carry a nonce. When issued `one_time=True`, the first successful
execution consumes the nonce; any reuse is `E_REPLAY_NONCE_USED`. A per-session
record accountant enforces a cumulative cap so that many small reads cannot be
used to reconstruct a bulk export (`E_CUMULATIVE_SESSION_LIMIT`).

## 7. Policy lifecycle and stale authorization

When `require_policy_freshness=True`, the artifact binds the policy-book version;
if the live policy version differs at execution (a policy change), the
authorization is `E_POLICY_STALE`. Expiry (`E_EXPIRED`) bounds the validity
window regardless.

## 8. TOCTOU handling

Enforcement is a time-of-use re-verification of time-of-check facts. Before
retrieval the adapter re-checks actor role/identity, patient, encounter, consent,
destination, policy version, approval status, operation, purpose, and data
categories against the artifact. On any material change (e.g. consent withdrawn
between decision and execution → `E_CONSENT_CHANGED`) it rejects rather than
silently reusing the earlier decision. Re-authorization is required.

## 9. Adversarial threat model

The harness assumes a caller that will attempt to widen, retarget, replay, or
mislabel. Enforcement is deterministic and content-blind: field values (including
an embedded prompt-injection) never influence the decision. Every constraint is a
checked precondition of retrieval, not advisory metadata.

## 10. Non-critical-fact precedence invariant

`ActionCriticalityRegistry.non_critical_facts` was added as a generic, symmetric
abstraction. It is **not** a downgrade path. The precedence is:

```
hard block  >  critical (promotion: hc_critical / declared_high_risk / …)
            >  non-critical fact (hc_non_critical)
            >  unknown (conservative)
```

Proven invariants (generic registry + healthcare derivation):

- `EXPORT` + a non-critical fact → still **critical**;
- restricted-data access + a routine-workflow fact → still **critical**;
- external disclosure + a summary-only fact → still **critical**;
- `hc_critical` + `hc_non_critical` together → **critical** (promotion wins);
- hard blocks override all non-critical indications → **DENY**;
- an UNKNOWN request is not resolved to non-critical merely because a
  non-critical fact is present;
- caller-declared `hc_critical` / `hc_non_critical` control keys are **stripped**
  before classification — a caller cannot self-classify.

## 11. Test matrix

`agentic/healthcare/tests/test_enforcement_validation.py` (28 tests):

| # | Adversarial scenario | Expected |
|---|---|---|
| 1 | billing gets permitted fields, not psych | permitted subset; psych excluded |
| 2 | widen billing → full record | `E_SCOPE_WIDENING` |
| 3 | reuse SUMMARIZE auth for EXPORT | `E_OPERATION_MISMATCH` |
| 4 | internal auth → external destination | `E_DESTINATION_MISMATCH` |
| 5 | replay against another patient | `E_PATIENT_MISMATCH` |
| 6 | access a historical encounter | `E_ENCOUNTER_MISMATCH` |
| 7 | Hospital A auth → Hospital B | `E_TENANT_MISMATCH` |
| 8 | auth used by another agent | `E_AGENT_MISMATCH` |
| 9 | expired authorization | `E_EXPIRED` |
| 10 | one-time nonce replay | `E_REPLAY_NONCE_USED` |
| 11 | require-approval not executable / incomplete | no artifact / `E_APPROVAL_INCOMPLETE` |
| 12 | consent withdrawn before execution | `E_CONSENT_CHANGED` |
| 13 | policy change with freshness required | `E_POLICY_STALE` |
| 14 | export mislabeled as summary | no artifact / `E_OPERATION_MISMATCH` |
| 15 | many small reads → reconstruct bulk | `E_CUMULATIVE_SESSION_LIMIT` |
| 16 | restricted via generic summary output | never released |
| 17 | prompt injection in clinical text | enforcement unaffected |
| 18 | caller non-critical facts downgrade | stays critical |
| 19 | critical + non-critical facts | resolves critical |
| 20 | missing destination/purpose/consent/actor | fails conservatively |
| + | 6 generic-registry precedence invariants; metrics; PHI-safety | — |

## 12. Metrics

`HarnessMetrics.to_dict()` reports: authorization success rate; constrained
execution rate; denied execution attempts; scope-mismatch blocks; replay attempts
blocked; tenant-isolation violations blocked; **restricted-field leakage count**
(required 0); **unauthorized-field leakage count** (required 0);
stale-authorization rejections; audit-correlation completeness. The test suite
asserts both leakage counts are zero and correlation completeness is 1.0.

## 13. Limitations and non-claims

- Synthetic data and simulated adapters only; no real HIS/EMR, no real key
  custody (HMAC test key), no real identity provider.
- Passing tests demonstrate mechanical enforcement of *these* constraints against
  *these* attacks in simulation — not legal compliance, clinical safety, or
  deployment readiness.
- Consent-required determinations, identity verification, destination approval,
  and cross-tenant relationships are inputs supplied by surrounding systems; this
  layer enforces policy over those facts, it does not establish them.
- No raw clinical content influences any decision, and none is written to
  governance receipts or logs; raw synthetic values appear only in the payload
  delivered to the caller.
- This is not a clinical system and makes no diagnostic or treatment claim.
