# Governed runtime worker

**The composition root of the governed review service.** Step 2 of
`docs/architecture/ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md`, under owner
rulings CR-1 (`SEPARATE_WORKER_UNIT`), CR-3 (`PRIVATE_NETWORK_TLS_IDENTITY_MANDATORY`),
CR-4 (`ONE_DEPLOYMENT_MODE_SWITCH`) and CR-5 (`ALLOWLISTED_JWKS_HOST`).

    ONE PROCESS. IT WIRES; IT DECIDES NOTHING.

## Maturity — read this before citing the deployment

`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`. Every provider the worker
invokes is the fixture in `workload.py`. The only identity adapter it can compose has
been validated against an in-process issuer only. `UGENCE_REVIEW_DEPLOYMENT_MODE=production`
is a **fail-closed posture** and nothing more: it refuses fixtures, in-memory stores,
public binds and plain HTTP, and it certifies nothing, validates nothing and enables no
LIVE execution. The container gate set exists and has never executed (the mirror is
unconfigured); no image has been built.

## What it composes

In one process, in this order (`composition.py`):

| Seam | Object | From |
|---|---|---|
| authority directory | `SqliteAuthorityDirectory` | `<data_dir>/authority-directory.sqlite3` |
| approval ledger | `build_review_ledger` over `DirectoryApproverEligibility` | `<data_dir>/approvals.sqlite3` |
| audit ledger and index | `AuditLedger`, `LedgerLinkageIndex` | `<data_dir>/audit-ledger.sqlite3` |
| durable engine | DBOS over two PostgreSQL databases, `PostgresStoreBundle` | the two DSNs |
| governance | `GovernedExecutionHook` over `ApprovalBoundInputSource` over the workload's upstream source | configuration |
| runtime host and adapter | `DbosRuntimeHost`, `DbosExecutionAdapter` | the workload's definitions and providers |
| reads and linkage | `DbosRunReader`, `LinkageAppender` | the above |
| identity | `JwtApproverIdentityAdapter` from issuer, audience, JWKS URL and claim names | configuration (AI-C) |
| the service | `ReviewService(..., tenant_mode=SINGLE_TENANT, production=<mode>)` and `build_app` | the above |

One injected clock (`WorkerClock`: `epoch()` for the engine, `datetime()` for every store
and the service) is shared by everything. `Worker.close()` unwinds it in reverse.

## Configuration

Every value is explicit, `UGENCE_REVIEW_*` or a constructor override; nothing is
discovered. `validate()` returns every reason the configuration must not compose.

| Variable | Meaning | Production rule |
|---|---|---|
| `DEPLOYMENT_MODE` | `production` or `test`; nothing else | |
| `APP_DATABASE_URL`, `SYSTEM_DATABASE_URL` | the two PostgreSQL DSNs; **the only secrets** | required, distinct, never logged |
| `DATA_DIR` | the durable volume holding the three SQLite stores | must exist; in-memory refused |
| `TENANT_ID`, `REQUIRED_ROLE`, `DEFINITION_DIGEST`, `WORKER_ID`, `REQUESTER_REF` | the service's tenant, the role approvals require, the compiled definition this worker runs | required |
| `BIND_HOST`, `PORT` | the listener (default `127.0.0.1:8444`) | loopback or private address only (CR-3) |
| `TLS_CERT_FILE`, `TLS_KEY_FILE` | the listener's certificate | required; plain HTTP refused (CR-3) |
| `IDENTITY_ISSUER`, `IDENTITY_AUDIENCE`, `IDENTITY_JWKS_URL` | the AI-C adapter | required, `https` only (CR-3, CR-5) |
| `IDENTITY_TENANT_CLAIM`, `IDENTITY_ACTOR_TYPE_CLAIM`, `IDENTITY_HUMAN_ACTOR_VALUE` | the IA-4 claim mapping; no defaults | the actor pair together or not at all |

`preflight(config, identity_port=, eligibility=, bundle=)` applies the posture before
any connection: in production an identity port is mandatory, a fixture identity or
eligibility adapter, an in-memory store and a non-authoritative bundle are refused.
`config.redacted()` is the only rendering of the configuration and passes the DSNs
through `redact_dsn`; `Scrubber` masks them, and their passwords, in every line the
server writes.

## Egress and inbound

Outbound: the JWKS host only, as platform configuration recorded in
`EXTERNAL_DEPLOYMENT_EVIDENCE.json` (CR-5). It is external evidence, not application
behaviour. Inbound: one private TLS listener reachable from the studio's segment; the
service has no gate of its own, so in production every decision requires a proof.

## Running

```bash
PYTHONPATH=deployment/governed-runtime-worker/src:<the composed packages' src dirs> \
UGENCE_REVIEW_DEPLOYMENT_MODE=test UGENCE_REVIEW_APP_DATABASE_URL=... \
UGENCE_REVIEW_SYSTEM_DATABASE_URL=... UGENCE_REVIEW_DATA_DIR=/var/lib/ugence-review \
UGENCE_REVIEW_TENANT_ID=tenant-a UGENCE_REVIEW_REQUIRED_ROLE=risk-approver \
UGENCE_REVIEW_DEFINITION_DIGEST=shadow-v1 python -m governed_runtime_worker
```

The server composes the shadow workload. A deployment with a real workload composes
through `compose(config, clock=, workload=)` from its own entrypoint.

## Evidence

- `tests/test_config.py` — ADR §4a rows 2, 7 and 8 at configuration level: exactly two
  modes; a public or unspecified bind and a plain listener are refused in production;
  the redacted view and the scrubber carry no DSN or password.
- `tests/test_preflight.py` — rows 1 and 3: a fixture identity or eligibility adapter, an
  in-memory store and a non-authoritative bundle are refused in production before any
  connection; an identity port is mandatory; test mode accepts them and says so.
- `tests/test_maturity_and_boundaries.py` — row 7: `MATURITY` and `ENFORCEMENT_ENABLED`
  across every composed package; no studio import; DBOS imported only inside `compose`.
- `tests/test_end_to_end.py` — the whole root over a real PostgreSQL 16 and the AI-C
  adapter's in-process issuer: park, list, decide over HTTP with a signed proof
  (`IDP_AUTHENTICATED`, `authentication_reference`), re-arm, consume, run once, link,
  and no DSN or token in any answer or output (row 8).

## Container image and gate set (step 4)

`Dockerfile` builds only from the ratified `python:3.11-slim-bookworm` digest, in the
same `backend` and `runtime` stage roles the studio image uses; `base-images.json`
pins it and `ci/verify_ratified_pins.py` asserts pins == the owner's ratification
record == the FROM lines, offline, first. Non-root `10001:10001`, read-only root with
`/tmp` and the `/var/lib/ugence-review` volume writable, `8444/tcp` only, the two DSNs
as environment at run time and nothing in any layer. `CONTAINER_GATE_SET.json` defines
the worker's own P3E-equivalent gates (GRW-CTR-01 to 10) and
`.github/workflows/governed-runtime-worker-ci.yml` runs them in its `container` job;
`ci/verify_container.sh` is the runtime gate (fail-closed startup negatives on an
internal network, then a hardened positive run with a private TLS listener over a real
PostgreSQL). **Every gate is `NOT_EXECUTED`**: the job halts with
`RESOURCE_BLOCKER_MIRROR_UNCONFIGURED` until the owner-approved mirror is recorded, the
runtime script has been validated by static parsing only, and the evidence manifest is
`INCOMPLETE` on every run. The gate set is defined, not ratified.

## Not claimed

Production certification, pilot validation, enterprise-issuer validation, container
gate execution or evidence, a built image, enforcement, LIVE execution, multi-tenancy. The P3E studio profile is
unchanged by this package (step 3, CR-2).
