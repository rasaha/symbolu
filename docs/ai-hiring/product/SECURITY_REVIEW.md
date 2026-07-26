# Security Review

Scope: the AI Hiring product `0.6.0` as packaged (`ai_hiring.product`) on the frozen
Decision Governance Platform v1.0. This review covers the packaging layer's posture;
the platform's own governance guarantees are inherited, not re-litigated here.

## Threat model (for this package)

Because the product runs **in-memory, offline, deterministic, with no production
effect**, the classic external threat surface is minimal. The relevant concerns are
about **not overstepping** that boundary and **not leaking data** in artifacts a user
might share.

| Concern | Posture |
|---|---|
| Accidental production effect | Fail-closed config: only `DETERMINISTIC_SIMULATION`; production modes raise `UnsupportedExecutionModeError` before any wiring |
| Network egress / exfiltration | None — no HTTP clients, no sockets, no vendor SDKs (enforced by boundary tests) |
| Secret handling | No secrets read, embedded, or required |
| PII in shared artifacts | Accountability reports redact subject/actor identifiers by default (`redact_pii=True`) |
| Cross-tenant data access | Enforced by the platform; reconstruction raises `CrossTenantHiringAccessError` across tenants |
| Audit tampering | Detected: hash-chain validation + link/scope checks reported by reconstruction |
| Untrusted config input | `load_config` fail-closes on unknown keys and invalid values |

## Authorization & decision integrity (inherited, enforced)

- **Human-only binding decisions.** Only an authenticated `HUMAN_APPROVER` may record
  a binding decision; the AI actor is grant-denied `MAKE_DECISION` /
  `OVERRIDE_RECOMMENDATION`. The AI attempting a decision raises `ReviewerAuthorityError`.
- **No unauthorized execution.** Execution requires a valid ActionGate authorization
  bound to the human decision; denial blocks execution.
- **Recommendation ≠ action.** An action cannot originate from a recommendation
  without an eligible, review-ready recommendation and an authorized decision.

These are properties of the frozen platform; the packaging layer adds nothing that
can weaken them and is tested to add no new authority or lifecycle state.

## PII / data protection

- Redaction is **on by default** and deterministic (salted SHA-256 pseudonyms), so
  reports are shareable for audit without exposing personal or identity data while
  remaining internally correlatable.
- Analysis-only attributes (group labels / protected attributes) **never** enter the
  operational pipeline — a validated leakage guarantee (H5 counterfactual invariance).
- Un-redacted output requires an explicit opt-in (`redact=False` / `report --no-redact`).

## What this review does NOT assert

- No penetration test, no formal threat-model sign-off for a *production* deployment
  (there is none to deploy).
- No compliance certification (GDPR/CCPA/EEOC or equivalent). Fairness analysis is
  read-only and descriptive; it makes no compliance claim.
- Production adapters, when/if built, would introduce credentials, network egress, and
  a real threat surface that this review explicitly does **not** cover.

## Recommendations for an embedding application

1. Pin runtime dependencies in your own lockfile.
2. Keep `redact_pii=True` for any shared report; treat `--no-redact` output as
   sensitive.
3. Do not implement a production execution adapter without a separate security review
   of that adapter's credentials, egress, and idempotency.
