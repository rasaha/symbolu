# Reviewer Guide (Phase 13)

*For reviewers assessing the minimal evidence-obligation policy. This guide explains the framework; it
does **not** reveal the final labels for any review-set artifact — form your own judgment first.*

## The six obligation levels

| Level | Meaning | You'd assign it when… |
|---|---|---|
| **E0** | No factual evidence gate | the content is genuinely non-factual: opinion, preference, hypothetical, rhetorical, formatting, a declared intention, or a local label |
| **E1** | Contextual support | a low-impact factual statement supported by its local context, correctly attributed, not contradicted |
| **E2** | Authoritative internal / implementation | the claim is about internal policy or code/config/tests and an authoritative internal artifact or the implementation itself can establish it |
| **E3** | Independent or measured | the claim needs corroboration, telemetry, measurement, integration evidence, or a primary source — the artifact cannot self-establish it |
| **E4** | External authoritative + review | high-authority external evidence is required (medical/legal/financial/regulatory or high-impact) **and** a human must review |
| **ER** | Human review / indeterminate | risk, authority, or claim type is unresolved, rules conflict, or a safety invariant is triggered |

## Risk floor (start here)

Every factual claim starts at a floor from its risk: low → E1, medium → E2, high → E3, critical → E4,
unknown → ER. **You may only raise from the floor, never lower it.** E0 is only for genuinely non-factual
content and never for a high-risk claim.

## Upward-only modifiers (raise, never lower)

Regulated (medical/financial/legal/regulatory) → at least E4. Performance/reliability/current-state/
security → at least E3. Internal-policy/implementation claims → at least E2. Time-sensitive claims → at
least E3. Action proposals → at least E3 (E4 if irreversible/high-impact), and they always need policy +
authority + approval evidence. High-impact recommendations → at least E4.

## Source authority

Authority is not the same as source type. Code is authoritative for *current behavior* but not for
*production performance*. Approved policy is authoritative; a draft or expired policy is not. A user is
authoritative for their own preference. **Generated text is never evidence for its own factual claim.**

## Self-verification (the key trap)

If the only "evidence" is the same generated output, a circular citation, the model's own confidence, or
a fixture/mock standing in for production telemetry — the claim is **not** independently supported. Raise
to at least E3; never accept self-support at E1/E2.

## Contextual vs implementation vs measurement evidence

- **Contextual** (E1): the surrounding text supports a low-impact statement.
- **Implementation** (E2): code/config/tests establish a *behavior* claim — but never a *production
  performance/reliability/availability* claim.
- **Measurement** (E3): only telemetry/measurement establishes performance, reliability, or current
  operational status.

## Action authority

A well-argued action recommendation still needs policy, authorization, and approval evidence — factual
support and action authority are separate. Absent approval, an action claim is at least E3.

## When to choose ER

Choose ER when you cannot safely assign an obligation: unknown risk or source authority, ambiguous claim
type, conflicting rules, or a triggered safety invariant. ER means "a human must decide" — it is the safe
default, not a failure.
