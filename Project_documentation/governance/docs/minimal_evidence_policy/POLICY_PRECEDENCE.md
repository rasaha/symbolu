# Policy Precedence (Phase 3)

*Deterministic precedence for the minimal policy. No later rule may weaken an earlier obligation — the
whole policy is upward-only (monotonic).*

## Precedence order

1. **Prohibited / structurally unsafe self-verification** — `INV-1` (model self-verification), `INV-2`
   (circular corroboration) force ≥ E3.
2. **Unknown / unresolved high-impact metadata** — `INV-10` → ER; unknown risk → ER floor.
3. **Critical risk floor** — critical → E4.
4. **Actionability escalation** — `INV-11` + action modifier → ≥ E3; irreversible → E4.
5. **Regulated-domain escalation** — medical/financial/legal/regulation → E4.
6. **Temporal & measurement escalation** — temporal/performance/current → E3; `INV-5`/`INV-6`/`INV-7`.
7. **Implementation / policy evidence handling** — code/policy → E2; `INV-3`/`INV-4`.
8. **Attribution handling** — attribution → E2; `INV-8` (attribution ≠ truth).
9. **Contextual support** — E1.
10. **E0 eligibility** — only independently non-factual content at low risk (and `INV-12`).

## How the implementation realizes this

The policy computes the **risk floor**, applies **upward-only modifiers** (each via `higher(...)`, so
they can only raise), then applies **all invariants** (which also only raise), then **re-asserts the risk
floor** (`INV-9`). Because every step is a monotone `max` over the obligation rank, the *order* of the
raising steps does not matter for safety — the result is the maximum obligation any rule demands. The
precedence list above is the human-facing explanation; the code guarantees it structurally.

## Monotonicity guarantee (tested exhaustively in Phase 15)

Increasing any of {risk, actionability, temporal sensitivity, uncertainty→unknown, contradiction,
regulated-domain status, self-verification, ambiguity} or removing approval **never lowers** the
obligation. `schema.higher` and the final floor re-assertion make this hold by construction; the
monotonicity test verifies it across the input space. **Any monotonicity violation is a pilot blocker.**

## Fail-closed

A structural validation failure (`validate` returns any code — e.g. final below floor) forces the final
obligation to **ER** with `MP.STRUCTURAL_VIOLATION_TO_ER`. Unknown critical metadata → ER, never a
permissive default (`INV-10`).
