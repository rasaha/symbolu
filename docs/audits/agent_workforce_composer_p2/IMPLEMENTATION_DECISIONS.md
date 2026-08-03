# Implementation Decisions — Agent Workforce Composer P2

1. **Build strictly on merged P1.** P2 consumes P1 public APIs (adapter,
   eligibility, profiles, snapshot, policies) and never reimplements eligibility or
   reinterprets elimination reasons. P1 object *data* fingerprints are unchanged
   (regression-pinned: P1 snapshot digest `sha256:2cc59b17…`, enterprise policy
   digest `sha256:0526a8c1…`).
2. **Additive contract.** P1 `awc.v1` preserved; P2 objects carry
   `awc.composition.v1`. Public API is append-only (48 → 93 names); the frozen
   artifact was regenerated.
3. **Integer basis-point scoring** with Decimal ROUND_FLOOR normalization — exact,
   cross-platform, monotonic, and reconstructable. Chosen over binary floats to
   guarantee determinism and score transparency.
4. **Bounded exact branch-and-bound** with an admissible bound, proven against a
   brute-force oracle. Typed `SEARCH_SPACE_EXCEEDED` / `NO_FEASIBLE_TEAM`; no silent
   truncation, no heuristic-as-optimal.
5. **Hard/soft separation** everywhere: eligibility (P1) → ranking → team hard
   constraints → team objectives. No score offsets a hard constraint.
6. **Permission bounds are proposals** (least-privilege intersection); nothing is
   granted. Authority ceilings enforced and never broadened.
7. **Fallbacks are offline**, drawn from the pinned eligible set, honest about gaps.
8. **No H16/runtime/Model Selection/H22 change.** Runtime narrowing is documentation
   + plan invariants only. Model references preserved, never resolved.
9. **Documented P1-test migrations** (compatibility, not silent): version 0.1.0→0.2.0
   and maturity flags (`agent_ranking_implemented`/`team_composition_implemented`
   now true) required updating three P1 assertions in `test_public_api.py`
   (`test_version_and_contract`, `test_maturity_is_honest`, and the former
   `test_no_ranking_or_team_surface_leaked` → `test_no_execution_or_grant_surface_leaked`).
   These asserted the ABSENCE of P2 and are legitimately superseded; all other P1
   tests and their intended assertions remain unchanged and green.
10. **Branch**: env-mandated `claude/` prefix → `claude/agent-workforce-composer-p2-54g1d0`
    (supersedes suggested `chatgpt/awc-p2-composition`). One PR, left unmerged.
