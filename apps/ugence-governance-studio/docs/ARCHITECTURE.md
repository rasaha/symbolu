# Governance Studio — Architecture

## Intended end-state

```
Browser
   │  HTTPS
   ▼
Thin web frontend            (Next.js + React + TypeScript — P3C/P3D)
   │  HTTP, JSON envelopes
   ▼
Deterministic demo API       (Python — P3B)
   │  in-process function calls
   ▼
Installed ugence-agent-workforce-composer package   +   packaged demo_data/
```

Each layer has one job. The boundaries below are contractual and enforced by tests
(in P3A for the data/tooling layer; extended per stage).

## Layer responsibilities

### Frontend (P3C/P3D)
- Renders workflow graphs, role requirements, the agent registry, the eligibility
  matrix, rankings, team composition, permission proposals, fallback plans, the
  AgentTeamPlan, replay, and what-if diffs.
- **Must not** import Python logic. **Must not** compute eligibility, ranking, or
  composition in TypeScript. **Must not** hard-code results that come from the API.
- Consumes types generated from the frozen OpenAPI contract (`contracts/openapi.json`,
  produced in P3B).

### Demo API (P3B)
The API **may**: select demo scenarios; validate request envelopes; call public AWC
functions; serialize canonical results; provide view-oriented projections; export
artifacts; expose health/version metadata.

The API **must not**: duplicate AWC policy logic (eligibility, ranking, composition,
permission bounding, fallback). It maps AWC's typed failures
(`NO_ELIGIBLE_AGENT`, `NO_FEASIBLE_TEAM`, `SEARCH_SPACE_EXCEEDED`, `INVALID_INPUT`)
to explicit envelopes — never generic HTTP 500s.

### AWC package (existing, authoritative)
`ugence-agent-workforce-composer` (`awc.v1` + `awc.composition.v1`). A leaf
capability depending only on the Python stdlib and `pydantic`. It owns **all**
planning logic. The studio treats it as a black box behind
`import ugence_agent_workforce_composer.api`.

## The nine behaviours the studio never re-implements

workflow adaptation · node disposition · agent eligibility · ranking · team
composition · permission bounding · fallback planning · plan fingerprinting · plan
replay · plan comparison.

Every one is a public AWC function call. See
`docs/audits/ugence_governance_studio_p3a/AWC_API_INVENTORY.md`.

## Determinism as a first-class property

- Inputs are frozen synthetic fixtures with a fixed `logical_time`.
- AWC canonicalizes every object; serialization order is irrelevant.
- The demo API must return identical logical results and identical AWC fingerprints
  for identical logical inputs, excluding transport-only fields (request id, server
  timestamp) from logical fingerprints.
- P3A already proves this at the data layer: `demo_data/` → real engine →
  byte-identical `expected_outputs/`, with a hash `MANIFEST.json`.

## Data flow for one scenario (P3A, no server yet)

```
demo_data/<scenario>/compiled_workflow.json      ─┐
demo_data/<scenario>/enterprise_role_overlay.json ─┤ adapt_compiled_workflow
                                                    ▼
                             CompilerAdaptationResult (roles + non-agent dispositions)
demo_data/<scenario>/agent_registry_snapshot.json ─┐
demo_data/<scenario>/*_policy.json                 ─┤ build_agent_team_plan
                                                    ▼
   eligibility → ranking → composition → permission proposals → fallback → AgentTeamPlan
                                                    ▼
                       expected_outputs/<scenario>/*.json  (frozen, hashed)
```

## Deployment shape (P3E, forward reference)

A single deployable container hosting the static frontend, the deterministic API,
and the packaged fixtures; 1 vCPU / 2 GB / no GPU / no external model API;
invite-only, HTTPS-only. The API keeps configurable-CORS and access-control seams so
authentication can be added without touching AWC.

## What P3A commits

The application root, this document, the four demo scenarios in real AWC schemas,
frozen canonical expected outputs with a hash manifest, the presenter narrative
(`DEMO_SCRIPT.md`), and the regression tests. No backend or frontend application
code exists yet.
