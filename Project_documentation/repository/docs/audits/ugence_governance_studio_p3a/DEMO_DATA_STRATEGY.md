# Demo Data Strategy

How the Governance Studio's four demo scenarios are authored, serialized, frozen,
and regression-protected — all on the real AWC schemas and engine.

## Source of truth

`apps/ugence-governance-studio/scripts/scenario_authoring.py` builds each scenario
out of AWC public schema classes only (workflow `workflow_ir.v1` dict, overlay
mapping, `AgentRegistrySnapshot`, and the six policies). It is the human-readable
record of *why* each fixture looks the way it does. It calls **no** AWC policy
engine — it only constructs inputs.

`apps/ugence-governance-studio/scripts/generate_fixtures.py` then:

1. serializes every input to `demo_data/<scenario>/*.json` (canonical JSON:
   `sort_keys=True`, 2-space indent, trailing newline);
2. runs the **real** P1→P2 pipeline (mirroring `build_agent_team_plan`'s internal
   call order so separately serialized composition/replay artifacts are byte-exact);
3. serializes the frozen outputs to `expected_outputs/<scenario>/*.json`;
4. writes `expected_outputs/MANIFEST.json` with sha256 of every input and output.

Regenerating is idempotent: same inputs → byte-identical files.

## The four scenarios and what each proves

| Scenario | Plan state | Demonstrates |
|---|---|---|
| `procurement` | `COMPLETE` | **Non-greedy** team selection: the top-ranked evidence specialist is dropped for a lower-ranked generalist because the 67% provider-concentration limit forbids the greedy all-Anthropic team. Also two `NO_FALLBACK_AVAILABLE` roles and a `RESIDENCY_MISMATCH` elimination. |
| `customer_support` | `COMPLETE` | Clean feasible team; a cybersecurity specialist is **eliminated** (`MISSING_REQUIRED_CAPABILITY`), never mis-assigned to drafting; one role has full (`COMPLETE`) fallback coverage. |
| `cybersecurity_success` | `COMPLETE` | Feasible level-4 incident-response team spanning two providers; three single-holder specialist roles yield honest `NO_FALLBACK_AVAILABLE`; low-clearance agent eliminated on `SECURITY_CLASSIFICATION_INSUFFICIENT`. |
| `cybersecurity_no_feasible_team` | `NO_FEASIBLE_TEAM` | Both roles individually eligible, but only one approved provider is cleared to level 4, so provider-concentration policy forbids any feasible two-role team. |

## Credible, domain-appropriate agents

Each scenario ships domain-named agents (e.g. Supplier Evidence Collection Agent,
Procurement Risk Analysis Agent, Support Triage Agent, Threat Analysis Agent,
Incident Correlation Agent, plus a General Enterprise Analyst). Cross-domain
mis-assignment is prevented by capability requirements, not by hand-waving: a cyber
specialist without support capabilities is simply ineligible for support roles.

## Determinism guarantees (encoded as tests)

- Fixed `logical_time = 1_000_000.0`.
- JSON round-trip reproduces identical AWC fingerprints.
- Input ordering (registry profile/evidence order, overlay key order) does not
  change any fingerprint.
- Every frozen output is byte-stable against a fresh engine run.
- `MANIFEST.json` hashes match the committed bytes; the manifest records the AWC
  version and contract versions.

## What is deliberately NOT done here

No backend server, no UI, no auth, no hosting, no database, no runtime execution,
no live registry, no Model Selection / H16 / H22 / ActionGate integration, no
external LLM calls. Those are later stages (P3B–P3E) or explicitly out of scope.
