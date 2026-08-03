# Implementation Decisions — P3A

Decisions made while building the Governance Studio foundation, with rationale.

## D1 — Consume AWC only through `ugence_agent_workforce_composer.api`
The 93-name curated surface (frozen in `artifacts/public_api.json`) is the contract.
No private module is imported; a test enforces this. This keeps the studio insulated
from AWC internals and honours "never re-implement" for all nine listed behaviours.

## D2 — Author fixtures in code, commit them as JSON
`scenario_authoring.py` constructs each scenario from AWC schema classes;
`generate_fixtures.py` serializes to `demo_data/*.json` and freezes
`expected_outputs/*.json`. The committed **JSON** is the fixture of record; the tests
load the JSON (not the authoring objects), so they verify exactly what ships. The
authoring module remains as human-readable provenance and is regenerable.

## D3 — Do not mutate AWC package fixtures
The studio ships its own `demo_data/` rather than editing
`packages/.../fixtures.py`. The package fixtures are reproduced and reviewed
(`EXISTING_FIXTURE_REVIEW.md`) but left untouched, per the brief.

## D4 — Fixed `logical_time = 1_000_000.0`
Matches the AWC package fixtures' epoch so freshness/expiry semantics line up, and
makes every plan replayable and every fingerprint stable.

## D5 — Auto-attach `evidence_extraction` MEASURED evidence
Every `EVIDENCE_REQUIREMENT` role carries a compiler-derived base
`evidence_extraction` capability. To keep each fixture's explicit evidence focused
on the *specialist* capability, `_snapshot(...)` attaches a MEASURED evidence record
for `evidence_extraction` to any agent that **declares** it and ships none. This
never masks an intended elimination — the demo eliminations are always residency,
clearance, provider, or specialist-capability, verified explicitly in tests.

## D6 — Distribute the mandatory demonstrations across scenarios
- Non-greedy team selection → **procurement** (hard provider-concentration limit).
- `NO_FEASIBLE_TEAM` → **cybersecurity_no_feasible_team** (team-level: single cleared
  provider).
- `NO_FALLBACK_AVAILABLE` → **procurement** and **cybersecurity_success** (single-holder
  roles).
Support and cyber-success are kept as clean, greedy-selected baselines so the
non-greedy lesson is unambiguous and localized to procurement.

## D7 — Force the procurement swap deterministically
The generalist is made eligible for **only** the evidence-collection role. The
greedy per-role choice is all-Anthropic (infeasible under 67% concentration); the
only way to add a second provider is to move the evidence role to the generalist.
This yields a single feasible optimum and a crisp, replayable non-greedy story,
rather than a score-tuning knife-edge.

## D8 — Canonical, byte-stable serialization
`json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` + trailing newline
for both fixtures and outputs, so `MANIFEST.json` hashes are meaningful and
regeneration is a clean no-op diff.

## D9 — Mirror `build_agent_team_plan` internals in the generator/tests
To serialize `composition.json` and `replay_record.json` as standalone artifacts
that are byte-identical to the pipeline's internal computation, the generator
reproduces the plan's exact call order (per-role `evaluate_registry_for_role` →
`rank_eligible_candidates` → `build_role_dependency_graph` → `compose_agent_team`
with the same digest kwargs). Tests and freeze share this one routine.

## D10 — No CI workflow in P3A
The P3A brief lists no CI workflow (CI is P3B's `governance-studio-api-ci.yml`).
P3A adds only fixtures/docs/tests and touches no frozen artifact, so it does not
change platform-freeze. A CI workflow is intentionally deferred to keep stage scope
clean.

## D11 — Branch name
Development is on the environment-assigned `claude/governance-studio-p3a-ficdup`,
which supersedes the brief's suggested `chatgpt/governance-studio-p3a-demo-foundation`.
