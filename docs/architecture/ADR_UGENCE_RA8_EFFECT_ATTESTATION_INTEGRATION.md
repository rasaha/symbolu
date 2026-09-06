# ADR — RA-8 effect-attestation integration (RI-1 to RI-5)

**Status:** ratified by the owner, 2026-09-06; implemented at reference grade in
`ugence-risk-authority-execution-assurance` 0.2.0.
**Maturity:** REFERENCE-GRADE / NOT PRODUCTION-READY. Production wiring is
blocked by RI-4.
**Predecessor:** `ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md` (SE-1 to SE-5).

## 1 — The question

Where does RA-8 accept a verified `EffectAttestation`, and what may it conclude
from one? Answer: at a new pre-normalization entry point on
`TrustedEffectIngress`, and only provenance and integrity. Provider-signed
evidence can raise a mismatch; only observer-signed evidence can support a
production `MATCHED`.

## 2 — Audit findings the rulings answer

| Finding | Evidence |
| --- | --- |
| RA-8's seam authenticates the normalized `EffectObservation`, never the `ExecutionObservation` an attestation binds; `normalize_execution_observation` sits outside the gate and `assess` takes normalized observations `[V]` | `ingress.py:75-87`, `ingress.py:118-163`, `assurance.py:132-144` |
| The rules that hold: binding errors, domain mismatches, exact-`True` admission, authenticator fault fails closed, reference authenticator refused in production, service requires a production ingress `[V]` | `ingress.py:207-260`, `ingress.py:185-192`, `assurance.py:88-110` |
| `EffectObservation.effect_digest` is a content digest, not an attestation `[V]` | `contracts.py:246-256` |
| Spec D-A ratifies authenticated ingress; per-receipt signing is FUTURE; provider self-report is the residual `[V]` | `RISK_AUTHORITY_RA8_SPEC.md:139-171,648` |
| No production `TrustAnchorResolverPort` exists; TEA ships `StaticTrustAnchorDirectory` (reference) and `DenyAllTrustAnchorDirectory` `[G]` | `packages/trusted-evidence-authority/src/.../authority/trust.py` |
| The attestation package ships no signer, key custody or clock, by ruling `[V]` | `ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md` §4 |
| `assess` still falls back to `datetime.now` for `produced_at`; that clock is the assessment timestamp, not the attestation instant, and is unchanged here `[V]` | `assurance.py:155` |
| The normalized type carries no attester role, so RI-3 needs a typed amendment `[V]` | `contracts.py:246-275` |

## 3 — Rulings

| Ruling | Consequence in code |
| --- | --- |
| **RI-1 SEAM = ADMIT_ATTESTED_ENTRY_POINT** | `TrustedEffectIngress.admit_attested(attestation, correlation=, as_of=, observation_id=, ...)` verifies the exact wrapped observation under the attester's declared role and anchor, binds tenant and correlation, normalizes only after `VERIFIED`, then runs the unchanged binding, domain and authentication checks. `EffectSourceAuthenticator.authenticate` is untouched. Every non-`VERIFIED` disposition rejects with the verifier's typed reason. |
| **RI-2 PRODUCTION_UNATTESTED = REJECT** | `admit` (the unsigned path) rejects every observation when the ingress was built with `production_mode=True`. No flag, default or fallback admits unsigned evidence in production. At reference grade `admit` is unchanged and its reference authenticator is still refused in production. |
| **RI-3 PRODUCTION_ROLE_SUFFICIENCY = OBSERVER_REQUIRED_FOR_MATCHED** | The attester role travels in a typed `EffectAttestationProvenance` on the normalized observation (never in `source`, `source_version` or reason text). In production, an aggregate `MATCHED` is withheld unless an admitted observation carries verified `INDEPENDENT_OBSERVER` provenance with a favorable final outcome; the result is `UNVERIFIABLE` with reason `INDEPENDENT_OBSERVER_REQUIRED`. `MISMATCH`, `CONFLICTED`, `PARTIAL`, `UNKNOWN` and `MANUAL_REVIEW` pass through, so adverse provider evidence is never suppressed. |
| **RI-4 PRODUCTION_RESOLVER = SEPARATE_TEA_MILESTONE_BLOCKS_PRODUCTION** | A production ingress that carries a verifier requires the verifier's own `production_mode is True`, which refuses `StaticTrustAnchorDirectory`. The only admissible resolver in the repository is `DenyAllTrustAnchorDirectory`, which refuses every anchor; production `MATCHED` is therefore unreachable and the suite pins that. The production resolver and its anchor-publication process are a separate TEA milestone, not implemented here. |
| **RI-5 INSTANT = INJECTED_ON_INGRESS** | `admit_attested` takes an explicit `as_of`. An absent, naive, non-`datetime` or subclassed instant rejects before the verifier or resolver is touched; the suite proves zero resolver consultation. `attested_at` in the attestation stays signed evidence about the attester's claim. No clock is read for verification. |

## 4 — The typed provenance amendment `[R]`

RI-3 says to stop if the normalized types cannot preserve the role without
ambiguity. They could not: `EffectObservation` had no role field, and Decision
Authority's `ExecutionRecord` has none either. The amendment made here is
additive and confined to RA-8's own contract: an optional
`EffectObservation.provenance: EffectAttestationProvenance` (role, identity,
key id, observation digest, signing-payload digest, anchor revision, verified
instant), excluded from `effect_digest`. The role is consulted on the admitted
observations at RA-8's aggregation stage, which RA-8 owns; it is not threaded
through DA records. Decision Authority is unchanged. This confinement is recorded
for ratification; it is not a claim that DA-level provenance exists.

## 5 — Stated explicitly

- A verified attestation proves who signed and that the bytes are intact. It
  never proves the effect occurred.
- Provider self-attestation is provenance only and cannot make production
  `MATCHED` reachable.
- Unsigned observations are admissible only under the labelled reference-grade,
  non-production posture.
- No production resolver, signer, key custody, anchor publication, KMS/HSM,
  provider onboarding, connector, gateway, LIVE execution or credential is
  added. The Third-Party Gateway remains FUTURE.
- `ExecutionObservation` is unchanged. `effect_digest` stays content-only.
- No genuine production `MATCHED` flow exists in this repository; the suite pins
  the blocker rather than substituting the reference resolver.

## 6 — Next step

Scope the TEA production `TrustAnchorResolverPort` milestone (RI-4): resolver
contract, anchor-publication process, custody boundary and its own verification
evidence. Until it lands, this integration stays reference-grade.
