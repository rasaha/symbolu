# Assertion Taxonomy

*Phase 4. Canonical delivery dispositions with precise semantics. These govern **delivering a
statement**, and are deliberately NOT the ActionGate action vocabulary. Source of truth:
`assertion_governance/taxonomy.py` (`age_taxonomy_v1`).*

## Dispositions

| Disposition | Meaning | Delivered text | Evidence relation | Delivers claim? |
|---|---|---|---|---|
| **ALLOW** | evidence supports the claim at its stated strength | verbatim | support ≥ claim strength | yes |
| **QUALIFY** | evidence supports a *weaker* claim than written (overclaim) | scoped/hedged rewrite | 0 < support < claim strength | yes (weaker) |
| **REJECT** | evidence contradicts the claim | withheld + reason | contradiction | no |
| **ESCALATE** | needs a qualified human (high-risk or authoritative conflict) | withheld pending human | high-risk & insufficient basis, or conflict | no |
| **INDETERMINATE** | evidence present but neutral/mixed | withheld or delivered with explicit uncertainty | neutral | no |
| **NOT_SUPPORTED** | no evidence addresses the claim (missing) | withheld or marked unsupported | no relevant evidence | no |
| **UNKNOWN** | governance could not run (missing inputs/error) | fail-closed withhold | n/a | no |

## Why seven, and why these boundaries

- **QUALIFY is the load-bearing novelty.** It is the only disposition that *transforms* rather than
  gates: it delivers the supported remainder as a weaker claim. Binary techniques (accept/reject,
  entail/contradict, answer/abstain) have no QUALIFY. If QUALIFY is not needed, AGE reduces toward a
  binary gate and loses much of its claim to independence.
- **INDETERMINATE vs NOT_SUPPORTED vs UNKNOWN** are three different "we can't say yes":
  - INDETERMINATE — evidence exists but is *neutral/mixed* (NLI-NEUTRAL-like).
  - NOT_SUPPORTED — *no* evidence bears on the claim (missing). The claim might be true; we just
    have no basis here.
  - UNKNOWN — the *governance process itself* failed (missing inputs). A meta-state, always
    fail-closed.
  Collapsing these (as most baselines do) loses the missing-vs-conflicting-vs-broken distinction
  that drives different downstream handling (retrieve more vs contradict vs retry).
- **ESCALATE is risk-gated, not support-gated.** The same weak support yields QUALIFY in a casual
  domain but ESCALATE in a medical/legal one. This risk-interaction is what H0-8 (renamed
  uncertainty) predicts a single scalar cannot reproduce.

## Non-overload with ActionGate (explicit)

| AGE (statement) | ActionGate (action) | Not the same because |
|---|---|---|
| ALLOW = state as written | ALLOW = perform the act | stating ≠ doing |
| QUALIFY = state weaker | CONSTRAIN = act within limits | rewriting a claim ≠ constraining an act |
| REJECT = don't state | DENY = don't act | withholding a claim ≠ blocking an action |
| ESCALATE = human review of a claim | APPROVE = human authorizes an act | both human, different objects |

AGE has **no** APPROVE/CONSTRAIN; ActionGate has **no** QUALIFY/NOT_SUPPORTED. The vocabularies are
kept disjoint on purpose.

## Fail-closed rule

`fail_closed(risk)` returns ESCALATE for high/critical risk and INDETERMINATE otherwise — **never a
silent ALLOW**. UNKNOWN always withholds.

## Scoring note

For the disposition-agreement metric (Phase 7), NOT_SUPPORTED and UNKNOWN collapse into the
INDETERMINATE family (`to_primary`), giving a 5-way comparison: ALLOW / QUALIFY / REJECT / ESCALATE
/ INDETERMINATE. The finer 7-way distinctions are evaluated separately (evidence-handling metrics).
