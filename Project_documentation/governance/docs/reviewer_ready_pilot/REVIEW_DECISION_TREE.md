# Review Decision Tree (Phase 5)

*A step-by-step path from an artifact to an obligation and disposition. Follow it top to bottom; the risk
floor and traps can only **raise** the result.*

```
1. Is the text CLAIM-BEARING?
   └─ no  → not assertive (formatting / label / pure narration) → E0 candidate → step 10
   └─ yes → step 2

2. Is the claim FACTUAL or NON-FACTUAL?
   └─ non-factual (opinion / preference / hypothetical / rhetorical), and LOW risk, no factual leak → E0
   └─ factual → step 3

3. What is the RISK LEVEL?
   └─ set the risk floor: low→E1, medium→E2, high→E3, critical→E4, unknown→ER
      (this is the MINIMUM; only raise from here)

4. Is an ACTION proposed?
   └─ yes → at least E3; needs policy + authority + approval; irreversible/high-impact → E4
   └─ no  → step 5

5. What SOURCE ROLE applies?
   └─ primary implementation / test → can support behavior claims (E2)
   └─ generated doc / model text → cannot self-verify factual claims (≥ E3)
   └─ approved policy → authoritative internal (E2); draft/expired → not
   └─ telemetry → measurement/status (E3); external authority → regulated/high-impact (E4)
   └─ unknown → ER

6. Is the SOURCE AUTHORITATIVE for THIS claim?
   └─ no / self-referential → raise (≥ E3); do not accept self-support
   └─ historical only → current claims need fresh evidence (≥ E3)

7. Is the claim CURRENT or TIME-SENSITIVE?
   └─ yes → at least E3 (freshness required)

8. What MINIMUM OBLIGATION applies?
   └─ take the HIGHEST of: risk floor, claim-type modifier, action/temporal escalation, trap raises
      (regulated → E4; performance/security/current → E3; internal/impl → E2; context → E1)

9. Does the AVAILABLE EVIDENCE satisfy the obligation?
   └─ this is EvidenceAssurance's job to judge; you record whether you think it does
   └─ high-external-burden (E3/E4) with no external/telemetry evidence → not satisfied → withhold/escalate

10. DISPOSITION
    └─ obligation met by context/implementation (E0/E1/E2 satisfied) → ALLOW (with caveats)
    └─ E3/E4 not satisfied → WITHHOLD (indeterminate) or ESCALATE
    └─ E4 → mandatory human review; ER → human review
```

## Trap overrides (apply at any step; they only raise)

self-verification / circular evidence → ≥ E3 · fixture-as-telemetry / impl-as-operational → ≥ E3 · stale
authority → ≥ E3 · attribution-as-truth → verify attribution only · high-risk opinion → never E0.

## Remember

The tree computes a **minimum obligation**, not a truth verdict. "Allow" means the applicable evidence
standard is met — not that the claim is universally true.
