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
| the start relay | `ShadowRunStarter` over the adapter, `wf-shadow`, `UGENCE_REVIEW_DEFINITION_DIGEST` (front-door seam 6, FD-10) | the above |
| the ledger read | the same `AuditLedger`, handed as `ledger_reader` (front-door seam 7, FD-11): the seventh route reads this deployment's own tenant's rows, raw | the above |
| the service | `ReviewService(..., tenant_mode=SINGLE_TENANT, production=<mode>, starter=<the starter>, ledger_reader=<the audit ledger>)` and `build_app` | the above |

One injected clock (`WorkerClock`: `epoch()` for the engine, `datetime()` for every store
and the service) is shared by everything. `Worker.close()` unwinds it in reverse.

## The authority plane: its contract, the four reads it serves, and the two writes it holds unserved

Steps 1 and 2 of `docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §11, under
rulings AP-1 to AP-5. `src/governed_runtime_worker/authority_plane.py` enumerates the
plane's eight operations, four reads under AP-5 and four writes under AP-3, and
`authority-plane-contract.json` is its committed, drift-tested rendering.
`tests/test_authority_plane_contract.py` holds the AP-4 verb rule in the shape of the
studio's SD-2 test with the sense reversed: grant, revoke, activate and issue may be
named; authorize, clear and execute fail the build.

**Since 0.4.0 the four reads are served** (`authority_reads.py`, mounted by
`composition.py` beside `/healthz`): `GET /authority/grants?principal_id=`,
`GET /authority/holders?role=&scope=`, `GET /authority/committees/{committee_id}?role=&scope=`
and `GET /authority/grants/{grant_id}/events`, each over the `SqliteAuthorityDirectory`
this process opened, for this worker's own tenant, at the injected clock. A read is not
authenticated and says so (`read_authenticated: false`); every answer carries the
decision proof the deployment can give (`IDP_AUTHENTICATED` when an identity port is
composed, `PRESENTED_UNPROVEN` otherwise), the adapter's `issuer_validation` label, and
the directory's own provenance statement. No proof or credential header is read. An
untyped identifier is refused before the directory is asked; a missing committee or
grant is a typed not-found.
`tests/test_end_to_end.py::test_the_authority_reads_are_served_by_the_composed_worker_and_no_write_is`
proves all of that over the composed worker on a real PostgreSQL, in the same CI job as
the decision relay, and that no AP-3 write path answers (ADR §15).

**The two directory writes are implemented and not served** (`authority_writes.py`,
ADR §16 rulings AW-2 to AW-5; §18, AW-1 reversed, AP-3 controlling).
`POST /authority/grants` loads one time-bounded role grant from a typed body (the
worker derives the grant id, so an identical replay answers `ALREADY_LOADED` with the
standing grant), and `POST /authority/grants/{grant_id}/revoke` appends a `REVOKED`
event with a reason. Each reads the operator's proof from `X-Ugence-Approver-Proof`,
the header the decision route reads, and records the issuer-qualified subject as
`loaded_by` or the revocation's actor. The gate is stricter than the decision route's:
no identity port composed, no proof, a proof that authenticates nobody, a non-human
actor, an expired proof, a port that cannot answer, or a missing, ambiguous or foreign
tenant claim is a typed refusal, and nothing is recorded as presented.

Under AP-3 no write is served until the identity adapter has been validated end to end
against at least one real enterprise issuer, covering issuer, audience, JWKS trust, the
tenant claim, the actor-type claim, and the worker's refusal of invalid or mismatched
assertions. Until the owner records that validation, `authority_plane.SERVED_WRITES` is
empty, the writes router registers nothing, and a write path on the composed worker
answers the framework's 405 (on `/authority/grants`, which a read shares) or 404.
`tests/test_authority_writes.py` proves the gate and the intake by building the router
with `serve=IMPLEMENTED_WRITES` explicitly, and `test_end_to_end.py` proves the same
against the real directory and the real JWT adapter over the in-process issuer; both
are implementation and conformance evidence only, never enterprise identity validation.
Re-serving the two writes once validation is recorded is one edit to `SERVED_WRITES`,
the regenerated contract, and the plane app's manifest.

**Activate and issue are never served here.** They act on packages this worker does
not compose (AW-2). The contract test asserts that only `authority_writes.py` names the
directory's write methods and that no write path answers on the composed app.

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
- `tests/test_ap3_designation_conformance.py` — AP-3 (ADR §20.6, §20.7): the committed
  designation record is the owner's (Cloudflare Access team `ugence` backed by Google
  Workspace, `PENDING_VALIDATION`), the five mapping fields carry rulings AP3-D1 to
  AP3-D5 and none is `UNRULED`, the file holds nothing token- or secret-shaped, and its
  `conformance_harness` block says exactly what the adapter under the `cloudflare-access`
  profile, the write gate, the `Cf-Access-Jwt-Assertion` boundary
  (`cloudflare_access_boundary.py`, AP3-D4) and the test-only authorizer
  (`tests/_conformance_authorizer.py`, AP3-D5, not AX-5) do with in-process tokens
  shaped like Cloudflare Access tokens. Rows 1 to 13 are implementation evidence only
  and stay null until live Cloudflare evidence is recorded; rows 14 to 16 take their
  result from this suite under AP3-D5's evidence classification. `ci/ap3_jwks_probe.py`
  prints the designated JWKS's key identifiers and document digest and nothing else,
  for the owner to run from a host with egress; `ci/ap3_token_capture.py` reads one
  token on standard input and prints only the redacted capture the record needs
  (`alg`, `typ`, `kid`, payload key names, `iss`, `aud`, whether `sub` is non-empty,
  `type`, a SHA-256 fingerprint), never the token or any other value; it verifies nothing,
  by design. `ci/ap3_live_verify.py` is the verifier: on the owner's machine it obtains a
  fresh token only through `cloudflared` (output filtered), verifies it with the real
  adapter against the live JWKS, drives the matrix rows a human login can drive, and
  prints only redacted evidence and per-row PASS/FAIL/BLOCKED; it aborts rather than
  print anything token-shaped.
- `tests/test_authority_plane_contract.py`, `tests/test_authority_reads.py`,
  `tests/test_authority_writes.py` — the plane's contract (no write served while AP-3
  is not `MET`), the four reads, and the two implemented writes behind the AW-5 gate.

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
