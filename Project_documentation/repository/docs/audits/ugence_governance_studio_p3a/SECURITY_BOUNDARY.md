# Security Boundary — P3A

P3A introduces data and documentation only (no server, no UI, no auth, no
network). This note records the boundary the studio must hold, and how P3A already
enforces the parts that apply to fixtures and tooling.

## Trust and authority boundary

- The studio is a **planning-time** presentation layer. It **never** grants,
  authorizes, provisions, schedules, or executes anything. AWC's own public API
  exposes no execution/grant surface (asserted in tests:
  `test_public_api_exposes_no_execution_or_grant_surface`).
- Permission-bound proposals are proposals. Every proposal carries AWC's notice
  *"…does not grant, authorize, provision or execute any permission."* (asserted:
  `test_permission_proposals_carry_no_grant_notice`).
- Governance-owned and human-authority workflow nodes are preserved as non-agent
  dispositions and are **never** turned into agent assignments (asserted:
  `test_no_business_action_authorization_in_plans`).

## Data boundary (fixtures)

- All fixtures are **unmistakably synthetic** (`provenance.synthetic=True`,
  `release_metadata.synthetic=True`, `scenario_manifest.synthetic=true`); no real
  supplier, customer, incident, agent, benchmark, or evidence data appears
  (asserted: `test_fixtures_are_marked_synthetic`).
- No secrets, tokens, credentials, hostnames, or personal data are present in any
  fixture or expected output.

## Execution boundary (tooling / tests)

- The authoring and generation scripts import AWC's **public** API and its
  canonical/fingerprint helpers only; importing a private AWC engine module or
  re-defining an engine function fails a test
  (`test_scripts_only_orchestrate_awc_never_reimplement_it`).
- Evaluation performs **no network I/O**: the determinism suite monkeypatches
  `socket.socket` / `socket.create_connection` to raise and still completes the full
  pipeline for all scenarios (`test_no_network_access_during_evaluation`).
- No filesystem paths, shell commands, or code are taken from any request — there is
  no request surface in P3A at all.

## Boundary seams reserved for later stages

The demo **API** (P3B) will add strict request schemas, unknown-field rejection,
body-size limits, sanitized errors, secure headers, configurable CORS, and
rate-limit / access-control seams. Private access, HTTPS-only, secure cookies,
CSP, dependency/container/secret scanning, and audit logging are P3E. P3A leaves the
boundary uncrossed and documents where those controls attach.

## Explicit non-goals for P3A

No authentication, hosting, database, runtime execution, live agent registry, Model
Selection, H16, H22, ActionGate, or external LLM calls.
