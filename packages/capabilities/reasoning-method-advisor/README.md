# ugence-reasoning-method-advisor

Slice 2 of the reasoning-method governance thread
(`docs/architecture/REASONING_METHOD_ADVISOR_SLICE2_COMMISSIONING_SPEC.md`,
owner-ratified as amended 2026-09-02): a **research-only, deterministic,
rule-derived** design-time Reasoning Method Advisor.

`advise(request) -> advisory` is a pure function of the developer's
`TaskProfile`, an optional governed `TaskClassIdentity`, the
`ReasoningMethodCatalog` and a versioned, canonically ordered `RuleSet`, all
from `ugence-reasoning-method-governance`. It returns the qualifying set (zero,
one or many methods), every inclusion and exclusion reason, trade-offs between
multiple qualifiers, and a primary **only when exactly one method qualifies**.
Rule count, rule priority and traversal order never manufacture a winner.

Every label is `RULE_DERIVED`, every advisory's evidence status is the explicit
`COMPARISON_EVIDENCE_ABSENT`, and every advisory is `RESEARCH_ONLY`. A request
without a governed task class is marked `UNCLASSIFIED_EXPLORATORY` and
`INELIGIBLE_UNCLASSIFIED`: no benchmark comparison, no configuration binding, no
production authority.

Excluded by ruling: LLM-based selection, `BENCHMARK_DERIVED` claims,
comparison-result ingestion, numeric predictions, scalar cost labels, approval,
configuration mutation, Constitution binding, envelope issuance, and any change
to Agentic Proposer, Agent Workforce Composer, Agent Runtime, readiness
classification, ROI or the advisory composite. The rule set `rules.research.v0`
ships as a **test fixture only**; it is a transcription of the experimental
selector's mapping and is provenance, not evidence of correctness.
