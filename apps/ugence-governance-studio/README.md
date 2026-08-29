# Ugence Governance Studio — Agent Workforce Composer Explorer

A web application that lets people **see** how the Ugence Agent Workforce Composer
(AWC) turns a governed workflow into an eligibility-checked, ranked, team-composed,
permission-bounded, fallback-planned **AgentTeamPlan** — using the real AWC P1/P2
engine, on synthetic data, with deterministic results.

The studio is a **presentation and orchestration layer only**. It never
re-implements workflow adaptation, node disposition, agent eligibility, ranking,
team composition, permission bounding, fallback planning, plan fingerprinting, plan
replay, or plan comparison. All of that comes from the installed
`ugence-agent-workforce-composer` package.

> Synthetic demonstration data · Deterministic planning only · No live agent
> execution · No permission granting · No business-action authorization · No
> production certification.

## Staged build

| Stage | Deliverable | Status |
|---|---|---|
| P3A | Architecture, contract freeze, credible demo fixtures, frozen expected outputs, narratives, regression tests | delivered |
| P3B | Deterministic demo API (thin orchestration over AWC) | delivered |
| P3C | Eligibility Explorer frontend | delivered |
| P3D | Composition, replay and what-if explorer | delivered |
| P3E | Private hosted deployment (single container, HTTPS, deployment-local access control) | delivered |
| P3F | Controlled private pilot operations | next |

The studio is therefore runnable end to end: `backend/` serves the frozen
`governance_studio.api.v1` contract over HTTP and `frontend/` is the twelve-screen
planning explorer that consumes it. See `docs/ARCHITECTURE.md` for the layering,
`docs/DEMO_SCRIPT.md` for the per-scenario narratives, `frontend/README.md` and
`backend/README.md` to run each half, and `docs/p3e/` for the deployment runbooks.

Delivered means built, tested and merged — not pilot validated and not production
certified. The OCI image build, run and vulnerability scan are CI-gated and are
reported `NOT_EXECUTED` wherever no container runtime and registry access are
available; see `docs/p3e/LIMITATIONS.md`. P3F is described in
`docs/p3e/NEXT_PHASES.md`.

## Layout

```
apps/ugence-governance-studio/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md      # Browser → frontend → demo API → AWC package
│   ├── DEMO_SCRIPT.md       # per-scenario presenter narrative
│   └── p3e/                 # private-hosted deployment + operator runbooks
├── contracts/               # frozen OpenAPI contract (governance_studio.api.v1)
├── backend/                 # deterministic demo API over the AWC package (P3B)
├── frontend/                # planning explorer SPA (P3C/P3D)
├── demo_data/               # 4 scenarios × 10 input fixtures (real AWC schemas)
│   ├── procurement/
│   ├── customer_support/
│   ├── cybersecurity_success/
│   └── cybersecurity_no_feasible_team/
├── expected_outputs/        # frozen canonical P1/P2 outputs + MANIFEST.json
├── scripts/
│   ├── scenario_authoring.py   # builds scenarios from AWC public schema classes
│   └── generate_fixtures.py    # serializes fixtures + freezes expected outputs
└── tests/                   # P3A: schema, determinism, demonstration, boundary, manifest
```

## Regenerate the fixtures

```bash
pip install -e packages/capabilities/agent-workforce-composer   # AWC engine
python apps/ugence-governance-studio/scripts/generate_fixtures.py
```

Regeneration is idempotent — identical inputs produce byte-identical fixtures and
expected outputs.

## Run the tests

```bash
pip install pytest pydantic
pip install -e packages/capabilities/agent-workforce-composer
python -m pytest apps/ugence-governance-studio/tests -q
```

The suite verifies: every fixture parses under the real AWC schemas and all
references resolve; the engine reproduces the frozen outputs and fingerprints
byte-for-byte; input ordering does not change results; the four scenarios actually
demonstrate non-greedy selection, `NO_FEASIBLE_TEAM`, `NO_FALLBACK_AVAILABLE`, and
domain-credible assignments; non-agent dispositions are preserved; no AWC logic is
duplicated; and no network access occurs during evaluation.
