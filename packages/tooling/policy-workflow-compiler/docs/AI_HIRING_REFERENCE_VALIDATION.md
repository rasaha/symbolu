# AI Hiring Reference Validation (decision D3)

The second equivalence domain. Decision D3 requires both Procurement **and** AI
Hiring equivalence before `pilot_validated` can be earned, and chose AI Hiring
because its governance shape *differs*: agreement across two differently shaped
domains is evidence of generality, where agreement within one is repetition.

As with Procurement, this is a validation harness, not an integration — **AI Hiring
is never modified** — and it sits behind the optional `ai-hiring-reference` extra.

## Why these dimensions

Procurement's dimensions are about authorization order over an amount. AI Hiring's
central governance claims are different, so copying them would test the harness
rather than the domain.

| Dimension | What it checks | Checks |
| --- | --- | --- |
| `eligibility_derivation` | Non-compensatory eligibility over mandatory gates alone: any FAIL blocks, then any INDETERMINATE blocks fail-closed, else eligible — including that a FAIL outranks an INDETERMINATE | 6 |
| `advisory_disposition` | The transparent floors: every scored dimension at or above the score floor plus confidence at or above the confidence floor advances; insufficient evidence holds; anything else declines — tested at, above and below each boundary | 7 |
| `advisory_binding_separation` | The product types a recommendation `actor_type="AI"`, `binding=False`; the pack reserves the binding decision for a human authority that no machine actor may satisfy | 2 |
| `compatibility_not_eligibility` | No eligibility-determining object reads a score, fit, confidence or rank fact — the pack-side form of the product's structural rule | 5 |
| `deterministic_threshold_translation` | The product's float floors translate exactly into the pack's integer units | 2 |

**Result: `EQUIVALENT` across all five, 22 checks.**

## The float finding

The live product states its advisory floors as floats — `60.0` and `0.6`. The
compiler refuses a float in policy logic, because a float comparison is not
reproducibly deterministic across platforms and a pack must be.

The reference therefore states the same floors in integer units: the score floor
unchanged on the product's 0–100 scale, and the confidence floor as whole percent.
That is a representation change, so it gets its own dimension rather than a comment:
`deterministic_threshold_translation` fails if the translation ever stops being
exact.

## Availability

Gated behind the optional `ai-hiring-reference` extra (`ugence-ai-hiring>=0.1.1`).
Core compilation does not depend on it, and the test module skips when it is absent
— exactly as the Procurement harness does.

## What this does not claim

Equivalence is measured against a reference product's modelled behaviour. It is not
a certification of either product: AI Hiring reports
`production_certified=False` itself, and so does this compiler. D3 is one item of
the pilot evidence list in `MATURITY.md`; the rest remain outstanding.
