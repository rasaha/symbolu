# Deployment

## Current deployment posture

This package deploys as a **library + CLI**, not a service. It has no server, no
listening ports, no database, no message queue, and no outbound network calls. It
runs in a single process, entirely in memory, in deterministic simulation.

Supported "deployments" today:

- **Library** — `import ai_hiring.product` inside a Python ≥ 3.10 process.
- **CLI** — `python -m ai_hiring.product {version|demo|report|verify}`.

Both are appropriate for evaluation, demonstration, and a **controlled pilot** where
no real hiring action is taken and no personal data leaves the process.

## What a real production deployment would require (NOT in this package)

This package intentionally stops at the port boundary. Moving from controlled pilot
to production would require work explicitly **out of scope** for H0–H6:

| Concern | Status here | Needed for production |
|---|---|---|
| External execution (ATS/HRIS writes) | deterministic in-memory adapter | real, idempotent adapters implementing `ExternalExecutionProvider`, with credentials, retries, and outage handling |
| Consequential steps (`ISSUE_OFFER`, `SEND_REJECTION`) | **not implemented** | contractual/communication integration + legal review |
| Identity / access grants | static in-memory provider | enterprise IdP integration, real RBAC, session management |
| Persistence | in-memory repositories | durable, backed-up stores preserving the hash-chained audit |
| Assertion/action governance providers | deterministic validation implementations | production TAP / ActionGate configuration and tuning |
| Fairness / compliance | read-only analysis, **no** certification | independent audit, legal/regulatory sign-off |
| Scale / performance | descriptive local timing only | load testing, capacity planning, SLOs |
| Secrets / config management | typed config, no secrets | secret store, environment separation |

None of the above is provided or implied. The platform's port design means these are
**replaceable adapters**, but the adapters themselves are not shipped and are not
part of any H0–H6 claim.

## Configuration at deploy time

The only supported execution mode is `DETERMINISTIC_SIMULATION`. Any attempt to
configure a production mode fails closed at construction
(`UnsupportedExecutionModeError`). This is deliberate: it makes it impossible to
accidentally "deploy to production" with this package.

## Rollback

There is no persistent state; a deployment is the installed package version. Roll
back by pinning/reinstalling the prior version (see [`VERSIONING.md`](VERSIONING.md)
and [`PACKAGING.md`](PACKAGING.md)).
