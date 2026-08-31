# Reviewer Guide (Phase 3)

*For real reviewers calibrating the frozen minimal evidence-obligation policy. This guide explains the
framework and uses examples **outside** the final review set. It never reveals the final answers for any
final-set artifact — you form your own judgment first.*

## What you are judging

For each artifact you assign the **minimum evidence obligation** a claim must meet — not whether the claim
is true. Keep four things separate:

| Concept | Question |
|---|---|
| **Obligation satisfied** | Does available evidence meet the required standard? |
| **Claim true** | Is the claim actually correct? (not your job to assert) |
| **Assertion deliverable** | Would the system deliver / qualify / withhold? |
| **Action authorized** | Is a proposed action permitted by policy/approval? |

## The six obligation levels

| Level | Meaning | Assign when… |
|---|---|---|
| **E0** | No factual evidence gate | genuinely non-factual: opinion, preference, hypothetical, rhetorical, formatting, declared intention, local label |
| **E1** | Contextual support | low-impact factual statement supported by local context, correctly attributed, not contradicted |
| **E2** | Authoritative internal / implementation | internal-policy or code/config/test claim an authoritative internal artifact or the implementation can establish |
| **E3** | Independent or measured | needs corroboration, telemetry, measurement, integration evidence, or a primary source — the artifact cannot self-establish it |
| **E4** | External authoritative + review | high-authority external evidence required (medical/legal/financial/regulatory or high-impact) **and** human review |
| **ER** | Human review / indeterminate | risk/authority/type unresolved, rules conflict, or a safety trap is present |

## Risk floor (start here, then only raise)

low → E1, medium → E2, high → E3, critical → E4, unknown → ER. You may **only raise** from the floor.
**E0 is only for genuinely non-factual content, never for a high-risk claim.**

## Upward-only modifiers

Regulated (medical/financial/legal/regulatory) → ≥ E4. Performance/reliability/current-state/security →
≥ E3. Internal-policy/implementation → ≥ E2. Time-sensitive → ≥ E3. Action proposals → ≥ E3 (E4 if
irreversible/high-impact) and always need policy + authority + approval evidence. High-impact
recommendations → ≥ E4.

## Source authority (type ≠ authority)

Code is authoritative for *current behavior*, not for *production performance*. Approved policy is
authoritative; a draft/expired policy is not. A user is authoritative for their own preference.
**Generated text is never evidence for its own factual claim.**

## Evidence types

- **Implementation** (E2): code/config/tests establish a *behavior* claim — never a production
  performance/reliability/availability claim.
- **Telemetry / measurement** (E3): only these establish performance, reliability, current operational
  status.
- **External authoritative** (E4): medical/legal/financial/regulatory and high-impact claims.
- **Attribution verification:** confirming a source *said* something is **not** confirming it is **true**.

## Safety traps

- **Self-verification:** the only "evidence" is the same generated output / the model's own confidence.
  Raise to ≥ E3; never accept at E1/E2.
- **Circular corroboration:** the "independent" evidence derives from the claim or the same upstream.
  Raise to ≥ E3.
- **Stale authority:** an expired/superseded policy cannot establish a current claim.
- **Fixture ≠ telemetry:** a mock/synthetic fixture cannot satisfy a production claim.

## Action authority

A well-argued action recommendation still needs policy, authorization, and approval evidence — factual
support and action authority are separate. Absent approval, an action claim is at least E3.

## Native ActionGate outcomes

For action-bearing claims, the system reports one of six native outcomes — ALLOW, ALLOW_WITH_CONSTRAINTS,
DENY, ESCALATE_TO_HUMAN, REQUEST_MORE_EVIDENCE, SIMULATE_AND_RETRY. Judge whether that outcome is
appropriate; do not collapse them into a binary.

## When to choose ER

When you cannot safely assign an obligation: unknown risk/authority, ambiguous claim type, conflicting
rules, or a triggered trap. ER means "a human must decide" — the safe default, not a failure.
