# Internal Pilot Plan (Phase 24)

*Eligible per the architectural decision (Pilot Option B). A bounded, non-enforcing, single internal
tenant pilot whose primary purpose is to close the outstanding gate — **real human validation** — before
any external step. No external customer onboarding.*

## Shape

| Parameter | Value |
|---|---|
| Tenant | one synthetic internal tenant (`internal-pilot-tenant`) |
| Mode | shadow-only, non-enforcing, no external actions, no live provider calls |
| Data | new, de-identified natural repository artifacts only |
| Volume | bounded — the frozen `HELD_OUT_NATURAL` set (250) + up to 250 additional new de-identified internal artifacts |
| Duration | a single bounded execution window; no open-ended running |
| Operating policy | the minimal evidence policy (risk floor + claim-type/temporal/actionability modifiers + invariants) |

## Eligible use cases

Advisory/review over internal natural text: implementation-documentation review, internal-policy
interpretation, design-rationale review, operational-guidance review, and support-content review — all
non-enforcing.

## Excluded use cases

Anything enforcing or world-affecting: external actions, account/permission changes, deployments,
irreversible deletion, medical/legal/financial determinations, regulated automation, and any external
customer data. High-risk claims are withheld/escalated, never auto-delivered.

## Mandatory review rules

- Every **E4** obligation and every **ER** decision routes to a human reviewer (the E4 mandatory-review
  and unresolved paths) — measured review rate ~9.6%.
- **Real reviewers** (≥2, preferably 3) run the Phase-12 `HUMAN_REVIEW_PROTOCOL.md` on the 50-item
  `HUMAN_REVIEW_SET` (blinded), so the pilot produces the human-validation evidence that is currently
  NOT EVALUATED. No silent overrides.

## Allowed / prohibited data

- **Allowed:** de-identified internal natural artifacts (docs/docstrings/comments).
- **Prohibited:** external customer data, PII/sensitive data, secrets, anything an intake classifier
  cannot clear. Prohibited/unclassifiable input fails closed.

## Stop conditions (any one halts the pilot)

1. Any unsafe high-risk or action allow.
2. Any self-verification escape.
3. Any monotonicity violation observed in operation.
4. Any privacy/isolation/audit/control failure.
5. Any decision that cannot be reproduced from its trace (replay failure).

## Audit & deletion

- Full audit: every decision carries a one-trace explanation + replay signature; audit completeness 1.0,
  replay deterministic (verified).
- Native ActionGate vocabulary preserved (0% loss) for any action-bearing claim.
- Deletion: tenant-scoped; on pilot completion or any privacy stop condition, tenant data is deletable in
  one tenant-scoped operation.

## Success criteria

- Real-reviewer study completed with acceptable agreement (≥ 0.70 exact or acceptable-obligation
  agreement) and no unsafe-allow disagreement.
- 0 unsafe high-risk/action allows and 0 self-verification escapes sustained on live internal traffic.
- Clean-allow materially above the prior 0% (target ≥ 0.30) with bounded review burden (< 25%).
- Deterministic replay and full audit maintained.

## Failure criteria

Any stop condition fires; reviewer agreement remains too low; the policy produces an unsafe allow on real
internal traffic; or the review burden proves operationally excessive.

## After the pilot

If success criteria are met — including **real human validation** — the external single-customer shadow
pilot can be **re-gated** (it is currently blocked). If not, the outcome (fix reviewer agreement / utility
/ safety) feeds the next iteration. **No external customer is onboarded at any point in this pilot.**
