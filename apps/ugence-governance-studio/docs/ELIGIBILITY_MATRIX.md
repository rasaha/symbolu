# Eligibility Matrix

Complete API-provided role-agent accounting. Columns are condition categories;
cells are pass / fail / unknown / not-applicable from the API. Row summaries carry
identity, provider, state, condition counts and a result fingerprint. Filters:
state, provider, residency, evidence class, elimination reason, agent status.
Sorts: identity, state, provider, failed-count, unknown-count. No pass/fail is
computed in TypeScript.
