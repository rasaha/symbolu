# Reasoning Method Advisor demo (research-only, Phase 3 intake)

An `experiments/` demonstration, not a production API. It calls the merged
`ugence-reasoning-method-advisor` (Slice 2) over a developer-authored typed task
profile, an optional governed task-class fixture, the seven-method research
catalog and the versioned `rules.research.v0` rule set, and prints the advisory
as machine-readable JSON plus a concise explanation. Every advisory is
`RESEARCH_ONLY` with `evidence_status = COMPARISON_EVIDENCE_ABSENT`.

## Phase 3 intake ruling (owner, 2026-09-02) — RATIFIED

*Owner ruling, verbatim:* "developers directly author the typed task profile
through canonical JSON or a guided form with a one-to-one mapping to the
ratified profile fields and structural-signal tokens. The resulting profile is
DEVELOPER_REPORTED.

Phase 3 introduces no free-text classifier, LLM profiling, inferred signal,
runtime ComplexityDetector, new capability or method-selection logic. Friendly
form labels may explain canonical fields, but they must not alter, combine or
infer values. Before submission, the developer must see and explicitly confirm
the canonical profile.

A future profiling helper may propose a draft profile from natural-language
input, but it must remain outside ugence-reasoning-method-advisor, identify
every inferred field, require developer confirmation, and acquire no authority
from that confirmation beyond DEVELOPER_REPORTED. That helper is not
commissioned now."

**Authority.** Owner ratification by Rakesh Mohan, 2026-09-02, issued as an
explicit owner instruction in Claude Code session
`session_01VXERHvJzbb9cjZ1GyFFQLn`; the model analysis was advisory only and
the owner instruction was the ratifying act.

**Applied here.** `load_profile` requires exactly the nine developer-authored
profile fields with their exact JSON types and refuses unknown keys; nothing
is defaulted, coerced, combined or inferred, and unknown signal tokens are
refused by the contract itself (`SIGNAL_TOKEN_UNKNOWN`). With `--profile` the
CLI prints the canonical profile and exits without advising unless
`--confirm-profile` is given; every run echoes the canonical profile before
the advisory. The bundled examples are pre-confirmed fixtures.

## Usage

```
python -m experiments.reasoning_method_advisor_demo.demo --example 1..4 [--json|--text]
python -m experiments.reasoning_method_advisor_demo.demo --profile p.json [--task-class tc.json] \
    --advised-at 2026-09-02T12:00:00Z              # prints the canonical profile, exit 3
python -m experiments.reasoning_method_advisor_demo.demo --profile p.json [--task-class tc.json] \
    --advised-at 2026-09-02T12:00:00Z --confirm-profile
```

`--advised-at` is required: the demo reads no clock. The demo makes no quality
prediction, benchmark claim, cost or latency label, ranking or production
recommendation, and reproduces none of the advisor's rules.
