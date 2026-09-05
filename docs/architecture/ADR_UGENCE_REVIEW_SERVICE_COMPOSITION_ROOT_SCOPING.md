# Ugence governed review service composition root — scoping record

**Status: SCOPED AND RULED — nothing here is implemented.** This record scopes where
`ReviewService` is composed and served, with the identity port (AI-C), the linkage
appender (HE-1) and the durable adapter it needs. The five decisions in §5 were ruled
by the owner on 2026-09-05. Implementation is entered only by its own prompt. This
record adds no dependency, provisions no secret and reopens no ruling of P3E, GAS-7,
HE or ID. `REFERENCE_GRADE_SHADOW_ONLY` is preserved throughout: a `production=True`
switch anywhere in this topology selects fail-closed posture and never implies
production certification, pilot validation or LIVE execution.

Evidence labels: `[V]` verified against this repository at the merge of PR #1635,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

**Where can `ReviewService(identity_port=..., tenant_mode=..., production=...,
linkage_appender=...)` run so that a human decision proven by AI-C reaches a real
parked instance, without breaking the ratified P3E boundary?** Not inside the P3E
studio container, and not inside the studio backend process. The review service's
`resume` runs the durable engine's `continue_workflow` in its own process, so the
composition root is the durable-execution worker: a second deployment unit, private to
the studio, holding the Postgres-backed engine, the three SQLite stores and the
identity adapter. The studio reaches it over one configured URL that the P3E profile
does not yet carry.

## 2 — What exists

| # | Fact | Label |
|---|---|---|
| 1 | The service is composed from four seams plus three optional ones: `ledger` (`ApprovalWorkflowPort`), `adapter` (`signal`, `resume`, `status`), `reader` (`RunReader`), `clock`, and `eligibility`, `linkage_appender`, `identity_port` with an explicit `tenant_mode` and a `production` flag (`governed-review-service/.../service.py`). `build_app(service)` is the only HTTP entry and carries no access gate of its own (`http.py`). | `[V]` |
| 2 | The adapter's `resume` calls `engine.continue_workflow(instance_id)` inside a DBOS durable step, through a `DbosRuntimeHost` that must supply `build_engine`, `definition_for` and a durable clock; `signal` and `status` need only the datasource (`durable-execution/.../engine/dbos_engine.py`, `resume`, `DbosExecutionAdapter.__init__`). The process composing the review service therefore hosts the runtime engine, the governed hook and the provider registry. | `[V]` |
| 3 | DBOS needs an application database and a system database, both Postgres, launched in-process (`_dbos_harness.py`, `launch_dbos`); the review-service matrix rows run exactly that way on a runner-hosted PostgreSQL 16. | `[V]` |
| 4 | The approval ledger, the authority directory and the control-plane audit ledger are SQLite files opened by path; production mode refuses `:memory:` (`governed-review/composition.py`, `approval-workflow/sqlite.py`, `LedgerLinkageIndex`). | `[V]` |
| 5 | The P3E studio container serves the frozen v1 API only: the deployment builds the backend with `create_app`, and `create_combined_app` (v1 with v2 mounted) is served nowhere (`deployment/governance-studio/src/.../app.py`, `_build_backend`). The SPA's review screens call `/api/v2/review/*`, which the v1 backend answers with 404. | `[V]` |
| 6 | The studio learns the review service only through `build_studio_context(review_service_base_url=...)`; no `UGENCE_STUDIO_*` variable carries it (`app_v2.py`, `docs/p3e/CONFIGURATION_REFERENCE.md`). The studio must never import a database driver (`reader.py` docstring; `test_architecture.py`). | `[V]` |
| 7 | The P3E profile is ratified as `single_process: true`, `external_network_egress: none`, read-only root with `/tmp` and `/var/run/ugence-studio` writable, `persistent_database` prohibited, one exposed port, secrets only as env and a read-only TLS mount (`approved-runtime-config.json`, `compose.private.yml`). | `[V]` |
| 8 | The AI-C adapter fetches a JWKS over HTTPS from a configured URL, needs no credential, and refuses plain HTTP outside loopback in production (`approver-identity-jwt/config.py`). The studio forwards the proof header on one route and holds no identity (AI-B). | `[V]` |
| 9 | Four production switches exist and are independent: `ReviewService(production=True)` refuses the static identity adapter; `AdapterConfig(production=True)` refuses the loopback JWKS exception; `SqliteApprovalWorkflowStore(production_mode=True)` refuses in-memory; `DbosExecutionAdapter(production_mode=True)` refuses a non-authoritative bundle. | `[V]` |
| 10 | No composition root for the review service exists anywhere; no deployment profile hosts a durable-execution worker; no enterprise issuer is provisioned (adapter ADR facts 9 and 10). | `[G]` |

**Net finding.** The review service is a facet of the runtime worker, not a thin
service beside the studio. Every one of its stores and its one egress conflicts with
the P3E container's ratified profile, so composing it there would reopen P3E; composing
it in the studio backend would breach the studio's driver boundary. The root is a new
deployment unit, and the studio needs one new configuration value and the v2 app served
to reach it.

## 3 — Topology and configuration (ruled)

Two deployment units on one private network segment:

| Unit | Process | Serves | Holds |
|---|---|---|---|
| **Governance Studio** (P3E, amended under CR-2) | the existing single ASGI process behind its TLS listener and Basic gate | the SPA and, after CR-2, the combined v1 and v2 API under the same gate | no database, no driver, no identity, one new value `UGENCE_STUDIO_REVIEW_SERVICE_URL` |
| **Governed runtime worker** (new under CR-1) | one process: DBOS engine, runtime host, providers, governed hook, review service HTTP | `build_app(service)` on a private TLS listener | the two Postgres DSNs, three SQLite stores on a durable volume, the JWKS adapter configuration |

The studio relays the five review routes and the one proof header to the worker over
HTTPS; the worker never calls the studio. The worker's only outbound connection is the
JWKS URL (CR-5). Configuration of the worker, all explicit:

| Concern | Source | Production posture |
|---|---|---|
| Postgres application and system URLs | configuration, credentials in the DSN | the only secrets; env or mounted file, never logged |
| approval ledger, directory, audit ledger | three SQLite paths on a durable, writable volume | `production_mode=True`; `:memory:` refused |
| durable adapter | `DbosExecutionAdapter` over the worker's host, bundle and datasource | `production_mode=True`; `definition_digest` stated |
| run reader | `DbosRunReader(datasource, bundle)` | read-only transactions |
| identity port | `JwtApproverIdentityAdapter(AdapterConfig(...))` with issuer, audience, JWKS URL, tenant and actor claim names | `production=True`; static adapter refused |
| tenant mode | `SINGLE_TENANT`, explicit | the durable engine is tenant-unaware (identity ADR §2, row 7) |
| linkage appender | `LinkageAppender(AuditLedger(path), LedgerLinkageIndex(path))` | HE-1 as ruled |
| clock | one injected tz-aware clock shared with the host's durable clock | never process-local |
| HTTP | `build_app(service)` behind TLS on a private listener | no gate of its own (fact 1) |

Everything the root reads is configuration; nothing it holds is a credential except
the database DSNs. The proof arrives in `X-Ugence-Approver-Proof` from the studio and
is never stored (AI-B, AI-C). Under CR-4 one `UGENCE_REVIEW_DEPLOYMENT_MODE=production`
sets every production switch in the table together and refuses, at composition, any
static identity or eligibility adapter, any in-memory store and any non-authoritative
bundle. The same switch never enables LIVE execution: `ENFORCEMENT_ENABLED` stays
`False` in every package the worker composes, and the label stays
`REFERENCE_GRADE_SHADOW_ONLY`.

## 4 — P3E and secret boundary (ruled)

- **P3E stays as ratified.** The studio container keeps `single_process`, no egress,
  no database. What changes on the studio side is one configuration value and the v2
  app being served under the same access gate, which amends `approved-runtime-config`
  (`api_contract` is frozen at v1 there) and is itself a P3E amendment to record.
- **The service's own listener is unprotected by the studio's Basic gate.** Anyone who
  can reach it can list the queue and, without an identity port, record a decision by
  a presented approver. In production the identity port is mandatory and the listener
  is reachable only from the studio's network segment over TLS.
- **Egress is one host.** The worker's only outbound connection is the JWKS URL.
  Under P3E's precedent for platform controls (the Vercel record), an allowlisted
  egress rule is `EXTERNAL_DEPLOYMENT_EVIDENCE`, never application behaviour.
- **No container gate evidence transfers.** The thirteen P3E-CTR gates verify the
  studio image. Ruled: the worker image needs its own P3E-equivalent gate set and
  evidence manifest, separate from the studio's, and until it has one it carries no
  gate evidence and none may be described as passed or waived on its account.
- **Secrets.** The worker holds exactly two: the application and system Postgres DSNs,
  supplied as environment or a read-only mounted file, never logged, never in an
  image layer. The JWKS adapter holds public keys only. The studio gains no secret:
  the review-service URL is configuration, and the approver proof passes through
  unread (ID-1). No secret is ever committed.
- **Label and ceiling.** `REFERENCE_GRADE_SHADOW_ONLY`: every provider the worker
  invokes is a fixture, every decision is `PRESENTED_UNPROVEN` until AI-C runs against
  a real issuer, `ENFORCEMENT_ENABLED` stays `False`, and `production=True` on any
  component is a posture (fail closed, no fixtures) and never a certification.

## 4a — Failure matrix

| # | Failure | Required property | Holds today `[V]` | Gap `[G]` | Proving test |
|---|---|---|---|---|---|
| 1 | The worker is composed with the static identity adapter or an in-memory store in production mode | Refused at composition, before any listener opens | Each package refuses its own fixture in its own production mode | One switch sets all (CR-4) | Mode production, fixture supplied: composition raises; no port bound |
| 2 | The worker listener is reached from outside the studio's segment | Unreachable: the listener binds the private interface only and TLS is mandatory | Nothing: `build_app` has no gate and no bind rule | CR-3 | Bind configuration refuses a public interface in production; plain HTTP refused |
| 3 | A decision reaches the worker without a proof | `REFUSED_UNAUTHENTICATED`, ledger unchanged | Holds when an identity port is configured (AI-A row 1) | Port mandatory in production (CR-3) | Production mode with no identity port: composition refused |
| 4 | The studio is deployed without the review-service URL | The review screens report a typed gap, never an empty queue | `ReviewRelayService` reports `LEDGER`-style gaps today | The variable itself (CR-2) | Unset variable: `/api/v2/review/queue` answers `available: false` |
| 5 | The worker attempts any egress other than the JWKS host | Refused by platform allowlist; recorded as external evidence | Nothing | CR-5 | Egress test: only the configured JWKS host is reachable; docker.io and the issuer's discovery document are not |
| 6 | The worker image is described as gate-evidenced because the studio image is | Never; separate gate set | Nothing | Evidence ruling, §6 step 4 | The worker's evidence manifest is absent until its own gates run; the studio manifest names only the studio image |
| 7 | `production=True` is read as production certification or as LIVE | Never: labels stay `REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED` `False` | Every package declares both constants | None; a test must pin it in the worker | Worker maturity test asserts both constants across every composed package |
| 8 | A database DSN appears in a log, an answer or an image layer | Never | Studio logging discipline exists; the worker has none yet | Worker logging and image-layer secret scan | Redaction test over startup and every route; layer scan in the worker gate set |

## 5 — Owner decisions (ruled 2026-09-05)

| # | Ruling |
|---|---|
| **CR-1** | **`SEPARATE_WORKER_UNIT`.** A companion deployment unit, the governed runtime worker, hosts the DBOS engine, the runtime host, the three SQLite stores and the review service. The P3E container is not extended and the studio backend composes nothing. |
| **CR-2** | **`AMEND_P3E_SERVE_V2`.** The P3E profile gains one configuration value, `UGENCE_STUDIO_REVIEW_SERVICE_URL`, and serves the combined v1 and v2 application under its existing gate; `approved-runtime-config` and its freeze test are amended to say so. |
| **CR-3** | **`PRIVATE_NETWORK_TLS_IDENTITY_MANDATORY`.** The worker's listener binds the private segment only, over TLS, and in production mode an identity port is mandatory. No second access gate and no second credential. |
| **CR-4** | **`ONE_DEPLOYMENT_MODE_SWITCH`.** `UGENCE_REVIEW_DEPLOYMENT_MODE=production` sets every production switch together and refuses any fixture adapter, in-memory store or non-authoritative bundle at composition. It certifies nothing and enables no LIVE execution. |
| **CR-5** | **`ALLOWLISTED_JWKS_HOST`.** The worker's only egress is the configured JWKS host over HTTPS, as platform configuration recorded as `EXTERNAL_DEPLOYMENT_EVIDENCE`; no discovery document, no docker.io, nothing else. |

Ruled alongside, on evidence: **`SEPARATE_P3E_EQUIVALENT_EVIDENCE`**. The worker image
gets its own P3E-equivalent gate set and evidence manifest; the studio profile is not
extended to cover it (§4, §6 step 4).

Prohibitions, stated once: no database driver, DSN or store in the studio; no
credential beyond the database DSNs in the worker; no second identity provider; no
static identity or eligibility adapter in production mode; no container gate described
as passed on account of the worker; no LIVE execution.

## 6 — Sequence and ceiling

1. **Ruling** on CR-1 to CR-5 (documentation only). Done, above.
2. **Worker composition root**: a `deployment/governed-runtime-worker` profile with its
   configuration, the four-switch production mode, the SQLite volume, the JWKS egress
   record, TLS on the listener, and tests that a fixture adapter or in-memory store is
   refused in production and that the studio's proof header reaches the service.
   Label: **Reference-grade, shadow-only**. Shipped as `deployment/governed-runtime-worker`
   0.1.0 (`REFERENCE_GRADE_SHADOW_ONLY`, `ENFORCEMENT_ENABLED = False`): `compose` wires
   every seam of §3 in one process; `UGENCE_REVIEW_DEPLOYMENT_MODE` has exactly two
   values; `preflight` refuses a fixture identity or eligibility adapter, an in-memory
   store, a non-authoritative bundle, a public bind and a plain listener before any
   connection; `EXTERNAL_DEPLOYMENT_EVIDENCE.json` records the JWKS host as the only
   egress; §4a rows 1, 2, 3, 7 and 8 and an end-to-end run over a real PostgreSQL with
   the in-process issuer are tests. Composing surfaced two defects in the composed
   packages, fixed alongside: the review service's HTTP queue view assumed an
   `ApproverRef` method the directory's eligibility projection lacks
   (`governed-review-service`), and the control-plane audit ledger's SQLite
   connection was bound to its opening thread and refused every linkage append from
   an HTTP handler (`control-plane-root` 0.1.1). No image, no container gate (step 4).
3. **P3E amendment** (CR-2): the variable, the combined app under the gate, the
   runtime-config record and its freeze test. Shipped as `governance-studio-deployment`
   0.2.0: `UGENCE_STUDIO_REVIEW_SERVICE_URL` (optional; https only outside loopback test
   mode; no credential, query or fragment) is read by `DeploymentConfig` and handed to
   `build_studio_context(review_service_base_url=...)` only; `_build_backend` serves
   `create_combined_app` under the unchanged gate; `approved-runtime-config.json`
   records the one permitted egress, the served v2 contract and its hash, and the
   freeze test pins all of it; the deployment suite proves §4a row 4 (unset URL, typed
   gap on every review route) and ID-1 pass-through against a loopback stand-in. The
   image gains one dependency-free package (`ugence-agent-runtime`, imported by the v2
   services) and no other change; FROM digests and the digest gate are untouched.
   Composing surfaced one defect in the studio backend, fixed alongside:
   `create_combined_app` mounted v2 under `/v2`, so the contract's and the frontend's
   `/api/v2/...` paths were served nowhere; it now mounts at the root behind v1.
4. **Worker container gates**: a gate set for the worker image, entered only when the
   mirror blocker is cleared, since no image can be built until then. Defined
   statically (owner choice of 2026-09-05, mirror values not yet at hand):
   `deployment/governed-runtime-worker/Dockerfile` from the ratified python digest
   only, `base-images.json`, `ci/verify_ratified_pins.py` (offline, first),
   `ci/verify_container.sh`, `CONTAINER_GATE_SET.json` (GRW-CTR-01 to 10,
   `DEFINED_NOT_RATIFIED`) and the `container` job of the worker workflow with its own
   evidence artifact. Every gate is `NOT_EXECUTED` and every manifest `INCOMPLETE`
   until the mirror record carries owner-supplied coordinates; the runtime script is
   validated by static parsing only. No ratified digest, FROM line or studio gate
   record was changed.

**Ceiling.** With steps 2 and 3 the review screens work end to end against fixture
providers and the in-process issuer. Real approver identity waits on an enterprise
issuer (adapter ADR fact 10); enforcement and LIVE wait on AI-E, the external security
review and the mirror.

## 7 — Next step

Steps 2 and 3 are shipped and step 4 is defined; the ceiling above is reached. The
worker gate set executes, and the mirror configuration may be recorded, only when the
owner supplies the mirror host, repository prefix and secret name. Real approver
identity waits on an enterprise issuer (AI-E).
