# Common Review Errors (Phase 5)

*Mistakes reviewers commonly make, and the correction. Study these before qualifying.*

| # | Error | Why it's wrong | Correction |
|---|---|---|---|
| 1 | Accepting a model's own statement that its output is verified | generated text cannot verify itself | force ≥ E3 (INV-1) |
| 2 | Treating a code comment / README as proof of runtime behavior | documentation ≠ implementation | require the implementation (E2), not the comment |
| 3 | Treating source code as proof of production performance | code establishes behavior, not reliability/latency | performance needs telemetry (E3) |
| 4 | Treating a test fixture / mock as production telemetry | fixtures are synthetic | require real measurement (E3) |
| 5 | Treating a draft or expired policy as current authority | draft ≠ approved; expired ≠ current | require approved current policy (E2) or escalate |
| 6 | Treating "According to X, it is compliant" as proof of compliance | attribution ≠ truth | verify attribution only; the fact needs its own evidence |
| 7 | Assigning E0 to a consequential claim framed as opinion | opinion framing does not remove factual risk | never E0 at high risk; check for factual leak |
| 8 | Lowering the obligation because the surface risk looks low | a low-surface claim can still need independent evidence | never go below the risk floor; apply claim-type modifiers |
| 9 | Allowing an action because the reasoning is good | action authority ≠ factual support | require policy + authorization + approval (≥ E3) |
| 10 | Assuming an internal artifact is authoritative | internal ≠ authoritative without an explicit basis | require an explicit authority basis |
| 11 | Collapsing native ActionGate outcomes into allow/deny | the six outcomes carry distinct meaning | read the actual native outcome |
| 12 | Forcing consensus on a genuine domain judgment call | irreducible ambiguity is not a defect | record UNRESOLVED, do not force |
| 13 | Skipping ER when metadata is unknown | unknown must fail to review | choose ER on unknown risk/authority/type |

## The single most important habit

When in doubt about **whether the evidence is independent**, ask: *could this "evidence" have come from
the same source as the claim?* If yes, it is not independent — raise the obligation.
