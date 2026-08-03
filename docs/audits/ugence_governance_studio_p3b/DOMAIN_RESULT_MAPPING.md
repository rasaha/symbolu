# Domain-Result Mapping (P3B)

Typed AWC outcomes map to HTTP 200 domain results, never 5xx:
`NO_ELIGIBLE_AGENT`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `PARTIAL`,
`INVALID_INPUT`. Request/transport failures map to 400/404/409/413/415/422/429;
not-ready to 503; unexpected internal failures to a sanitized 500.

`cybersecurity_no_feasible_team` returns HTTP 200 with `plan_state =
NO_FEASIBLE_TEAM` — the canonical proof that domain non-success is not an error.
