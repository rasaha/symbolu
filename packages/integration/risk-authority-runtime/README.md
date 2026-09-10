# Ugence Risk Authority Runtime (RA-4.5)

**Fail-closed governance composition** — composes the machine-authority owner
(`ugence-risk-authority`) with two *additive* governance inputs
(`ugence-decision-authority`, `ugence-actiongate-provider`) into a single,
fail-closed execution-eligibility decision.

> Status: **RA-4.5 ratified as the production composition layer above the RA-1→RA-4
> spine** (`ADR_RISK_AUTHORITY_RA45_PRODUCTION_POSTURE_RATIFICATION.md`). It predates and
> does not adopt RA 0.8's `ActionAdmissionSeam`. Production eligibility depends on
> authenticated inputs — see *Verified composition* below. Deployment validation against
> real ActionGate deployments, live revocation stores and HSM/KMS custody remains pending.

## Verified composition — breaking changes at 0.2.0

A deployment-supplied `RiskAuthorityMachineResult` is **not** machine authority, whatever
its Python type and whatever posture field it carries (ADR §2). Only a verified, signed
`RiskAuthorizationEnvelope` is. The production path therefore derives its own result:

```
verified envelope → ActionAuthorization binding → VerifiedRiskAuthorityResult → composition
```

```python
enforcer = RiskAuthorityEnforcer.production(gate=my_production_gate, clock=trusted_clock)
verified = enforcer.derive(authorization_id=..., envelope=..., action=..., identity=...,
                           key_ring=..., revocation_state=...)
decision = RiskAuthorityCompositionEngine().compose_verified(
    risk_authority=verified, decision_authority=da_veto, actiongate=ag_veto)
```

Nothing new is signed or attested. `ActionAuthorization` — which Risk Authority's own
`ActionGatePort.authorize` already returns — is the envelope's action-specific binding, and
this package simply stops discarding it. `VerifiedRiskAuthorityResult` is an internal
verified-flow marker, **not** proof: it prevents reference and production flows from being
mixed by accident; the envelope and the binding checks are what establish trust.

Three changes break callers at 0.2.0:

| Was | Now | Why |
|---|---|---|
| `RiskAuthorityEnforcer()` built a `ReferenceActionGate` implicitly | typed `EnforcerConfigurationError`; use `.production(gate=...)` or `.reference()` | a reference enforcer was reachable without anyone saying so (ADR §8/D-E) |
| `StatusAwareActionGate(reader, policy=...)` likewise | same, via `.production(...)` / `.reference(...)` | the same default at the commit point |
| `compose(risk_authority=<caller-built result>)` was the only entry point | `compose` remains for reference/non-authoritative use; production must call `compose_verified` | ADR §2 |

A warning-only transition was rejected: it would have preserved the ambiguity it warns
about. `compose` itself is unchanged, so reference and test callers keep working.

## Clock authority — breaking change at 0.3.0

Issue #1398 item 1, ruling D-A. **`derive` no longer accepts `now`.** A production enforcer
requires an injected callable clock and refuses construction without one; `derive` reads it
**once** per call.

| Was (0.2.0) | Now (0.3.0) |
|---|---|
| `RiskAuthorityEnforcer.production(gate=…)` | `…production(gate=…, clock=trusted_clock)` — a missing clock is a typed refusal |
| `derive(…, now=caller_supplied)` | `derive(…)` — the instant comes from the injected clock, never the caller |
| `reference()` | `reference(clock=lambda: FIXED_NOW)` for deterministic replay; still never production posture |

The reason this mattered here and not in the RA leaf: the leaf's services are pure functions
of an instant, which is what makes them offline-testable and replayable, and no facade or
network path can supply a clock to them. `derive`, by contrast, is the production entry point
that mints a `VerifiedRiskAuthorityResult` — and its caller-supplied instant governed the
envelope window, the revocation epoch, and (since kernel 0.9.0) the signing key's own validity
window. Everything else on that path is fail-closed and envelope-bound; the clock was the one
input still taken on trust. Reading it once also means those three questions are judged at a
single instant, so a slow derive cannot straddle an expiry boundary.

Every RA leaf signature and the `ActionGatePort` protocol are unchanged — `enforce`, which
returns the non-authoritative `RiskAuthorityMachineResult`, still takes `now`.

`resolve(...) → None` in the RA-6 pre-effect recheck no longer passes through on caller
omission. Only an authenticated Policy Authority rule, supplied through the new
`applicability` port, can place an action outside Risk Authority scope; absence, lookup
failure, ambiguity and malformed answers all mean authority required (ADR §8/D-D).

## The corrected authority model

```
Decision Authority   = human / organizational governance veto
Risk Authority       = machine-capability authority  (the owner)
ActionGate provider  = supplementary action-policy veto / restriction
RA envelope verify   = execution-eligibility enforcement (RA-owned)
```

Risk Authority is the **sole issuer of machine execution authority**. Decision
Authority and ActionGate are additive governance inputs that may only
**subtract** authority (veto / hold / restrict) — never add it. The
non-negotiable invariants hold *by construction*:

```
FinalAuthority ≤ RiskAuthority
FinalScope    ⊆ RiskAuthorityScope
```

No permissive governance result — upstream or downstream — can upgrade a Risk
Authority `DENY`, widen scope, or manufacture authority RA did not issue.

- **`production kernel ALLOW ≠ machine execution authority`.** An organizational
  `ADVANCE` means only "governance does not veto." The machine capability is
  bounded entirely by Risk Authority's signed, scoped, time-bound envelope.

## Composition rule (GRANT iff all hold — plan §2)

```
1. RA envelope verifies (Ed25519 signature, key_id, canonical bytes)   [RA]
2. RA authority == ALLOW (control-derived)                             [RA]
3. RA not_before ≤ now < expires_at                                    [RA]
4. RA decision not expired at issuance (F-B)                           [RA]
5. RA envelope not revoked                                             [RA]
6. RA authority epoch current                                         [RA]
7. exact action matches signed envelope scope                         [RA]
8. Decision Authority does not veto  (ADVANCE; not HOLD/DEFER/REJECT)  [DA]
9. ActionGate does not veto          (ALLOW/…; not DENY/UNKNOWN)       [AG]
10. effective restrictions leave a non-empty scope                     [∩]

else → DENY / HOLD_NON_EXECUTABLE / ERROR_NON_EXECUTABLE  (never ALLOW)
```

Precedence (highest wins, all fail-closed): `RA ERROR` > `RA DENY/invalid/expired
/revoked` > `DA REJECT` > `AG DENY/UNKNOWN` > `DA HOLD/DEFER` >
`ERROR/UNAVAILABLE` > empty effective scope > `GRANT`.

## Decision Authority mapping (§4)

| Production `DecisionOutcome` | Composition veto | Final effect |
|---|---|---|
| `ADVANCE` | `NO_VETO` | governance does not object |
| `HOLD` | `HOLD` | `HOLD_NON_EXECUTABLE` |
| `DEFER` | `HOLD` | `HOLD_NON_EXECUTABLE` |
| `REJECT` | `DENY` | `DENY` (organizational veto) |
| unknown outcome | `DENY` | fail closed |
| unavailable / malformed | `ERROR` | `ERROR_NON_EXECUTABLE` |

The adapter never issues an RA scope, mints an envelope, derives a machine
`ALLOW`, or weakens an RA `DENY`.

## ActionGate mapping (§6, §11)

| Native `ActionGateOutcome` | Composition veto | Restrictions folded in (tightening only) |
|---|---|---|
| `ALLOW` | `NO_VETO` | default obligations recorded |
| `ALLOW_WITH_CONSTRAINTS` | `NO_VETO` | `maximum_amount`→min, expiry→earliest, `required_approval`→union |
| `DENY` | `DENY` | — |
| `UNKNOWN` | `DENY` (fail closed) | — |
| unavailable / malformed | `ERROR` | — |

ActionGate verifies **none** of signature / tenant / actor / model / scope /
expiry / revocation / epoch / exact payload — those remain RA-owned. An
`allowed_region` constraint is recorded as an obligation only; it is **not**
mapped onto RA jurisdiction enforcement (see F-D below — no silent mapping).

## Restriction algebra (§12)

`EffectiveAuthority = RiskAuthority ∩ GovernanceRestrictions`, always
`⊆ RiskAuthority`. Only tightening operators, only on dimensions RA represents:

```
amount ceiling    → min()           expiry → earliest()
allow sets        → intersection    deny sets → union
required approvals→ union
```

There is no operator, on any dimension, that enlarges authority.

## Signed-artifact ownership (§13)

The signed `RiskAuthorizationEnvelope` remains the **sole** machine-execution
authority artifact. `GovernedExecutionDecision` *wraps* it with governance
evidence and effective constraints — it carries no signature and is **not** a
second authorization envelope.

## F-D remains a separate issue (#1397)

RA-4.5 composition **preserves current enforcement coverage and does not close
F-D** (jurisdiction / autonomy / resource-target enforcement). `CanonicalAction`
has no `jurisdiction`/`autonomy` field and the ActionGate provider does not match
them; those require extending Risk Authority under separate review. No F-D
dimension is silently claimed as enforced here.

## Layout

```
src/ugence_risk_authority_runtime/
  contracts.py                  # value objects (fail-closed by construction)
  risk_authority_enforcer.py    # reuse of the canonical RA enforcement path
  decision_authority_adapter.py # DA outcome → governance veto
  actiongate_adapter.py         # AG outcome → policy veto / tightening restriction
  restrictions.py               # monotone restriction algebra
  composition.py                # the fail-closed composition engine
tests/                          # matrix, adversarial, restrictions, failure, invariants, packaging
scripts/verify_isolated_install.py
```

## Verify

```
python -m pytest packages/integration/risk-authority-runtime/tests -q
python packages/integration/risk-authority-runtime/scripts/verify_isolated_install.py
```
