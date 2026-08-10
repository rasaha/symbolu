# Existing AWC Fixture Review

Before authoring demo-specific fixtures, the AWC package's own synthetic fixtures
were inspected and reproduced. This documents what exists, what was reused, and
the commercially unintuitive assignments the studio should surface.

## Where the package fixtures live

There are **no `.json` fixture files** in the AWC package. All P1/P2 scenario
fixtures are Python factories in
`packages/capabilities/agent-workforce-composer/src/ugence_agent_workforce_composer/fixtures.py`:

- Workflows: `procurement_workflow()`, `support_workflow()`, `security_workflow()`
  (serialized `workflow_ir.v1` documents, `release_metadata.synthetic=True`).
- `role_overlay()` — enterprise overlay mapping.
- `registry_snapshot()` — 17 synthetic agents, each crafted to trip a specific
  elimination reason.
- Policies: `enterprise_policy()`, `eligibility_policy()`, `ranking_policy()`,
  `team_composition_policy()`, `permission_policy()`, `fallback_policy()`.
- Demo runners: `run_demo(name)` (P1), `run_compose_demo(name)` (P1→P2).

Reproduced locally: `run_compose_demo("procurement")` → `COMPLETE`,
`run_compose_demo("security")` → typed `NO_FEASIBLE_TEAM`, consistent with the
package's own P2 CI assertions.

## Decision: author demo-specific fixtures, do not mutate package fixtures

Per the P3A brief ("Do not alter P1/P2 canonical package fixtures merely to make
the demo attractive"), the studio ships its **own** fixtures under
`apps/ugence-governance-studio/demo_data/`, built from the **same public schema
classes** and the same construction helpers, but tuned for four teachable
scenarios. The package fixtures are left untouched. The studio fixtures reuse the
`fixtures.py` node/agent/evidence/policy construction *patterns* (documented in
`scenario_authoring.py`) so they are schema-faithful, not a parallel object model.

Key schema facts confirmed by reproduction (and encoded in the demo authoring):

- An `EVIDENCE_REQUIREMENT` node owned by `COMPILER` with `ADVISORY` disposition is
  the only node kind that becomes an **AI-agent role**; the adapter unions a base
  `evidence_extraction` capability onto every such role, so eligible agents need
  MEASURED/OBSERVED evidence for it plus the overlay's specialist capability.
- `APPROVAL_GATE` / `OVERRIDE_GATE` / `AUTHORITY_CHECK` → human authority;
  `ACTION_CONSTRAINT` / `ACTION_CLEARANCE_REQUIREMENT` with authoritative governance
  owners → governance-owned; `DECISION_RULE` / `AUDIT_EMISSION` → deterministic
  service; `TERMINAL_OUTCOME` → no agent. These are preserved verbatim into the plan.

## Commercially unintuitive assignments to surface

The studio's value is showing where **individually best ≠ team-best** and where the
honest answer is "no". The demo scenarios were authored so the real engine produces:

1. **Non-greedy selection (procurement).** For supplier-evidence collection the
   top-ranked candidate is the Anthropic specialist `agent_supplier_evidence`
   (7819 bp), yet the composer selects the lower-ranked OpenAI
   `agent_general_analyst` (7604 bp). Reason: the 67% provider-concentration limit
   forbids an all-Anthropic three-role team, and the generalist is the only
   non-Anthropic procurement agent — so the *cheapest* way to diversify is to move
   the evidence role off its top agent. The two harder specialist roles keep their
   top agents. This is the canonical "top individuals are not the selected team"
   demonstration.

2. **Honest `NO_FEASIBLE_TEAM` (cybersecurity_no_feasible_team).** Both incident
   roles are individually eligible, but only one approved provider (Anthropic)
   fields level-4-cleared agents; a two-role team on one provider is 100%
   concentration, which the policy forbids — so there is **no feasible team**, not a
   silently truncated one.

3. **Honest `NO_FALLBACK_AVAILABLE`.** In procurement (risk, recommendation) and in
   cybersecurity_success (threat, correlation, recommendation), the specialist
   capability is held by a single cleared agent, so those roles have a primary but
   **no fallback** — presented as such, not hidden.

4. **Specialist NOT mis-assigned (customer_support).** A cybersecurity specialist
   (`agent_threat_analysis`) sits in the support registry but holds no support
   capability, so it is **eliminated** (`MISSING_REQUIRED_CAPABILITY`) on the
   drafting role rather than mis-assigned there on generic contract compatibility.
