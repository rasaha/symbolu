# Reviewer Guide (Phase 4)

*For real reviewers assessing the frozen minimal evidence-obligation policy. Examples here are excluded
from the final review set. This guide never reveals final answers.*

## Four things to keep separate

| Concept | Question |
|---|---|
| **Obligation assigned** | What minimum evidence standard applies to this claim? |
| **Obligation satisfied** | Does the available evidence meet that standard? |
| **Claim true** | Is the claim actually correct? (not your job to assert) |
| **Assertion deliverable / action authorized** | Would the system deliver/qualify/withhold; is an action permitted? |

## The six obligation levels

| Level | Meaning | Assign when… |
|---|---|---|
| **E0** | No factual evidence gate | genuinely non-factual: opinion, preference, hypothetical, rhetorical, formatting, declared intention, local label |
| **E1** | Contextual support | low-impact factual statement supported by local context, correctly attributed, not contradicted |
| **E2** | Authoritative internal / implementation | internal-policy or code/config/test claim an authoritative internal artifact or the implementation can establish |
| **E3** | Independent or measured | needs corroboration, telemetry, measurement, integration evidence, or a primary source |
| **E4** | External authoritative + review | high-authority external evidence required (medical/legal/financial/regulatory or high-impact) **and** human review |
| **ER** | Human review / indeterminate | risk/authority/type unresolved, rules conflict, or a safety trap is present |

## Risk floor (start here; only raise)

low → E1, medium → E2, high → E3, critical → E4, unknown → ER. **E0 only for genuinely non-factual
content, never high-risk.**

## Upward-only modifiers

Regulated (medical/financial/legal/regulatory) → ≥ E4. Performance/reliability/current-state/security →
≥ E3. Internal-policy/implementation → ≥ E2. Time-sensitive → ≥ E3. Action proposals → ≥ E3 (E4 if
irreversible/high-impact) and always need policy + authority + approval evidence. High-impact
recommendations → ≥ E4.

## Source role and authority (type ≠ authority)

Code is authoritative for *current behavior*, not *production performance*. Approved policy is
authoritative; draft/expired is not. A user is authoritative for their own preference. **Generated text
is never evidence for its own factual claim.**

## Evidence types

- **Implementation** (E2): code/config/tests establish a *behavior* claim — never a production
  performance/reliability/availability claim.
- **Telemetry / measurement** (E3): only these establish performance, reliability, current status.
- **Policy authority:** approved current policy establishes internal requirements/prohibitions.
- **External authoritative** (E4): medical/legal/financial/regulatory and high-impact claims.
- **Attribution verification:** confirming a source *said* something is **not** confirming it is **true**.
- **Action authority:** a well-argued action still needs policy + authorization + approval.

## Safety traps

- **Self-verification:** the only "evidence" is the same generated output / model confidence → ≥ E3.
- **Circular corroboration:** the "independent" evidence derives from the claim/same upstream → ≥ E3.
- **Stale authority:** an expired/superseded policy cannot establish a current claim.

## When to choose ER

Unknown risk/authority, ambiguous claim type, conflicting rules, or a triggered trap. ER is the safe
default, not a failure.
