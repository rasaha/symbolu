# Composition Explorer (P3D)

Shows the plan state prominently (COMPLETE / PARTIAL / NO_FEASIBLE_TEAM /
SEARCH_SPACE_EXCEEDED / INVALID_INPUT as a domain state, not an error). For a
feasible plan: role assignments (selected primary, score, top-ranked, non-greedy
flag, fingerprint), team-level facts (unfilled roles, hard constraints with
measured/limit, objectives), and search statistics. Candidate selection states
(INELIGIBLE / ELIGIBLE_NOT_SELECTED / SELECTED_PRIMARY / SELECTED_FALLBACK) come
from `POST /explanations/plan`. The browser never reruns the composition search.
