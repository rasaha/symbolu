# Governance Studio API — Domain Results (P3B)

The API surfaces AWC's typed outcomes verbatim. Plan states:
`COMPLETE`, `PARTIAL`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `INVALID_INPUT`.

Candidate selection states (explanations) are kept distinct:
`INELIGIBLE`, `ELIGIBLE_NOT_SELECTED`, `SELECTED_PRIMARY`, `SELECTED_FALLBACK`.

v1/v2 adaptation equivalence states: `BYTE_IDENTICAL`, `SEMANTICALLY_EQUIVALENT`,
`INTENTIONALLY_DIFFERENT`, `INCOMPATIBLE`. The four demo scenarios are
`SEMANTICALLY_EQUIVALENT` (node dispositions byte-identical; v2 carries richer
provenance and a different source contract).

Built-in scenario outcomes: procurement `COMPLETE`, customer_support `COMPLETE`,
cybersecurity_success `COMPLETE`, cybersecurity_no_feasible_team `NO_FEASIBLE_TEAM`.
