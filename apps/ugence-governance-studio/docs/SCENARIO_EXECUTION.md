# Governance Studio API — Scenario Execution (P3B)

Built-in scenario endpoints EXECUTE the real AWC pipeline; they never return
committed expected JSON directly. Frozen expected outputs are verification
oracles only.

```
load frozen inputs → validate manifest → adapt (AWC) → eligibility → ranking
    → compose → permission proposals → fallbacks → AgentTeamPlan
    → compare observed vs frozen expected fingerprints
```

Verification metadata is exposed on execution endpoints (`verify_expected=true`
by default): `expected_fingerprint`, `observed_fingerprint`, `match`, and a
per-artifact breakdown (adaptation, eligibility, composition, plan, replay).
