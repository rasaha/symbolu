# Ugence Risk Authority Runtime (RA-4.5)

**Fail-closed governance composition** — composes the machine-authority owner
(`ugence-risk-authority`) with two *additive* governance inputs
(`ugence-decision-authority`, `ugence-actiongate-provider`) into a single,
fail-closed execution-eligibility decision.

> Status: **RA-4.5 governance composition implemented and CI-verified; production
> deployment validation remains pending.**

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
