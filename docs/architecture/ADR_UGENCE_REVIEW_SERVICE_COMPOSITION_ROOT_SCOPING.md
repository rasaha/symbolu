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
HTTPS and, since front-door seam 6 (FD-10.4, 2026-09-06), a sixth route, the start of
the worker's own shadow run; the worker never calls the studio. The worker's only outbound connection is the
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
| **CR-2** | **`AMEND_P3E_SERVE_V2`.** The P3E profile gains one configuration value, `UGENCE_STUDIO_REVIEW_SERVICE_URL`, and serves the combined v1 and v2 application under its existing gate; `approved-runtime-config` and its freeze test are amended to say so. **Amended 2026-09-06 under `ADR_UGENCE_STUDIO_FRONT_DOOR_SCOPING.md` FD-10.4 (`ONE_STEP_AMENDMENT`):** the permitted route set over that one destination is six, the five review routes plus `POST /review/runs`, the relayed start of the worker's own shadow run (FD-10.1 to FD-10.3); the egress record, its freeze test, the studio's review client and the frontend manifest name all six; no second configuration value, credential or destination. **Amended again 2026-09-06 under FD-11.5 (`READ_ONLY_ONE_STEP_AMENDMENT`):** seven routes, the seventh `GET /review/audit/{correlation_id}`, a raw read of the worker's own tenant's audit-ledger rows by correlation id with the worker's chain verification (FD-11.3); read-only, no write route; still one destination, no configuration value, credential or package. |
| **CR-3** | **`PRIVATE_NETWORK_TLS_IDENTITY_MANDATORY`.** The worker's listener binds the private segment only, over TLS, and in production mode an identity port is mandatory. No second access gate and no second credential. |
| **CR-4** | **`ONE_DEPLOYMENT_MODE_SWITCH`.** `UGENCE_REVIEW_DEPLOYMENT_MODE=production` sets every production switch together and refuses any fixture adapter, in-memory store or non-authoritative bundle at composition. It certifies nothing and enables no LIVE execution. |
| **CR-5** | **`ALLOWLISTED_JWKS_HOST`.** The worker's only egress is the configured JWKS host over HTTPS, as platform configuration recorded as `EXTERNAL_DEPLOYMENT_EVIDENCE`; no discovery document, no docker.io, nothing else. |

#### CR-5 clarification, 2026-09-10 — internal connectivity is not vendor egress, but it must still be declared

> Supersede the statement that the worker has only one outbound connection. The worker
> currently initiates:
>
> - JWKS retrieval to its ratified identity endpoint;
> - PostgreSQL connections for application and DBOS durable state.
>
> PostgreSQL is outbound network connectivity even when addressed through
> `postgres.railway.internal`. It must appear explicitly in the deployment evidence and
> network allowlist; do not hide it by redefining it as "not egress."
>
> CR-5's security boundary is clarified as:
>
> - the worker may connect only to its approved JWKS endpoint and explicitly configured
>   private PostgreSQL persistence endpoints;
> - it may not connect to the MEU, model providers, arbitrary private services or the
>   public internet;
> - adding any new destination requires a separate CR-family amendment.
>
> The asynchronous MEU design may use the existing PostgreSQL/DBOS connection for an
> authorized-request outbox only if this introduces no additional network destination.
> Schema, authorization and tenancy changes to that outbox remain separately reviewable.
> — owner, 2026-09-10

This clarification was prompted by a finding recorded in `SPEC_MODEL_EGRESS_UNIT.md` §3.1:
`EXTERNAL_DEPLOYMENT_EVIDENCE.json` claimed the JWKS fetch was the worker's only outbound
connection while the worker had been dialling PostgreSQL since it first composed
(`composition.py:223-260`) `[V]`. The record now declares three destinations rather than
one, and the ruling's refusal to solve the problem by redefining the word is the substance
of it: the boundary is narrowed by naming what crosses, never by renaming it.


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

Steps 2 and 3 are shipped and step 4 is defined; the ceiling above is reached. Front-door
seam 6 (2026-09-06) amended CR-2 to six routes: `governed-review-service` 0.5.0 exposes
`POST /review/runs`, `governed-runtime-worker` 0.2.0 composes the `ShadowRunStarter`
behind it, and the P3E record names the sixth route over the same destination. Seam 7
(2026-09-06) amended it to seven: `control-plane-root` 0.2.0 adds the raw read,
`governed-review-service` 0.6.0 exposes `GET /review/audit/{correlation_id}` over it,
`governed-runtime-worker` 0.3.0 hands its ledger as the reader, and the P3E record
names the seventh route over the same destination. The
worker gate set executes, and the mirror configuration may be recorded, only when the
owner supplies the mirror host, repository prefix and secret name. Real approver
identity waits on an enterprise issuer (AI-E).

## 8 — Owner ruling RW-1 to RW-6: hosting the worker on Railway (owner, 2026-09-08)

Asked what deploying `deployment/governed-runtime-worker` on a managed cloud host
(Railway) would require given CR-3, the owner ruled on six questions. Nothing here is
implemented: this section records the answers and where each stands against what the
repository enforces today. `RAILWAY_HOSTING_DECISION.json` beside the deployment is the
machine-read rendering. No ruling of CR-1 to CR-5 is reopened and no code changed.

Evidence labels as §1: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

The ruling, in the owner's terms:

> **1. BINDING = `DEFER_PENDING_NETWORK_PROOF`.** Do not ratify bind-by-discovery yet
> and do not permit `"::"` merely because the deployment is on Railway. Preserve the
> current `is_private_bind` enforcement. Require a Railway deployment proof establishing
> the locally bindable address, routing behaviour, redeployment behaviour and absence of
> public ingress. This answer authorizes investigation only, not implementation.
>
> **2. CONTAINER_SUPPLY_CHAIN = `EXTERNALLY_GATED_DIGEST_PINNED_IMAGE_ONLY`.** Railway is
> admissible as a runtime host, but Railway native source or Dockerfile builds are not
> admissible for production. The image must be built, inspected, SBOM-produced,
> vulnerability-scanned, secret-scanned and verified by the ratified external gate
> pipeline, pushed to the approved private registry and deployed by immutable digest. No
> production deployment is authorized until the base-image mirror coordinates and all
> required gates are satisfied.
>
> **3. PRIVATE_LISTENER_TLS = `OWNER_CA_ISSUED_AND_CLIENT_VERIFIED`.** CR-3 requires
> authenticated TLS identity on the private listener. Refuse unverified self-signed TLS,
> generated keys persisted on the application volume, `ssl.CERT_NONE` and
> `rejectUnauthorized:false`. Use an owner-controlled CA, externally provisioned key
> custody and certificate verification by every client. This answer does not require
> mutual TLS unless separately ratified.
>
> **4. IDENTITY = `REAL_AP3_HTTPS_JWKS_ISSUER_REQUIRED_FOR_PRODUCTION`.** Production
> requires validation against a genuine HTTPS JWKS issuer, including issuer, audience,
> signature/key rotation, tenant and actor-type claims, with fail-closed behaviour. No
> Railway-specific identity exception is authorized. Test mode is permitted only for
> controlled demonstrations using synthetic data and must remain labelled
> `PRESENTED_UNPROVEN`.
>
> **5. DATABASE = `ONE_POSTGRES_SERVICE_TWO_LOGICAL_DATABASES`.** For the reference
> pilot, use one PostgreSQL 16 service containing separate DBOS system and application
> databases, with distinct DSNs, database names, roles and credentials. Disable public
> database exposure. Require encrypted, certificate-verified connections; record that
> repository DSN enforcement does not yet implement this requirement. Separate PostgreSQL
> services remain an optional future isolation or resilience enhancement.
>
> **6. SQLITE_STATE = `SINGLE_INSTANCE_REFERENCE_DEPLOYMENT_ONLY`.** The three SQLite
> stores and attached volume are accepted only for a single-instance reference-grade
> pilot. This does not authorize a highly available or enterprise-production claim.
> Production authorization requires PostgreSQL-backed or otherwise durable shared
> implementations, or a separate explicit acceptance of single-writer availability,
> backup, recovery and deployment-downtime limitations.

### 8.1 — What each ruling stands on

| Ruling | What the repository enforces today | Label |
|---|---|---|
| RW-1 | `config.py:36-55` tests `is_unspecified` before `is_private`, so `::` is refused and a unique-local address passes; a hostname is refused outright, so no `*.internal` name is a bind value. `config.py:158-162` raises the CR-3 refusal in production. `config.py:1-6` states that nothing is discovered, which is why bind-by-discovery would be a change and not a configuration. | `[V]` |
| RW-2 | `CONTAINER_GATE_SET.json` is `DEFINED_NOT_RATIFIED` and `NOT_EXECUTED`; eight of ten gates halt at `RESOURCE_BLOCKER_MIRROR_UNCONFIGURED`. `BASE_IMAGE_MIRROR_DECISION.json` carries `registry_host`, `repository_prefix` and `secret_name` as `null`. A host that builds from the `Dockerfile` pulls the base from docker.io, the first entry of this gate set's `never` list. | `[V]` |
| RW-3 | `config.py:163-170` requires a readable certificate and key in production and refuses a plain listener. Nothing verifies that certificate. | `[V]` |
| RW-4 | `config.py:172-181` requires issuer, audience and an `https` JWKS URL in production; `composition.py:149-150` refuses composition without an identity port; every authority read carries `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY` until AP-3's validation is recorded. | `[V]` |
| RW-5 | `config.py:139-147` requires both DSNs, requires the `postgresql` prefix and requires them to differ; `composition.py:221-229` hands them to DBOS as the system and application databases. | `[V]` |
| RW-6 | `composition.py:205-217` opens the authority directory, the approval ledger and the audit ledger as three SQLite files under `data_dir`. The image declared that path a volume until 2026-09-09; the `VOLUME` instruction was removed because Railway rejects it, so the single-instance property now rests on the platform-managed volume an operator attaches, which the image does not require and no test pins. | `[V]` for the three stores; `[G]` for the constraint |

### 8.2 — Where a ruling asks for behaviour the repository does not implement

Recorded rather than implemented; no code, validation rule or client was changed to
match, and no gate or check is marked satisfied on account of a ruling.

| Ruling | The gap | Label |
|---|---|---|
| RW-3 | Two committed clients disable certificate verification, which the ruling refuses: `container-healthcheck.py:27` sets `ssl.CERT_NONE`, and `apps/authority-plane/server.mjs:139` sets `rejectUnauthorized: false`. Until both verify an owner-controlled CA, a deployment does not satisfy RW-3 and must not be described as satisfying CR-3's TLS identity requirement. | `[G]` |
| RW-3 | No certificate authority and no key custody mechanism exists in this repository. | `[G]` |
| RW-5 | The DSN check is a prefix test; a plaintext DSN passes `validate()`. The ruling's "encrypted, certificate-verified connections" is therefore a policy ahead of the code, as the owner's own wording records. | `[G]` |
| RW-2 | No workflow implements a registry credential mechanism, and the container job has no publish step; both are prerequisites of the gated-image path the ruling requires. | `[G]` |
| RW-6 | No test pins the single-instance constraint, and no record states the backup, recovery and downtime expectations the alternative acceptance would need. | `[G]` |

### 8.3 — What this ruling authorizes

Investigation of RW-1 on a throwaway deployment, and a single-instance test-mode
deployment over synthetic data as demonstration evidence, labelled `PRESENTED_UNPROVEN`.

It authorizes no production-mode deployment, no host-built production image, no
enterprise-production or high-availability claim, and no code change: implementation is
entered only by its own prompt. RW-1, RW-2, RW-3, RW-4 and RW-6 each independently block
production authorization `[R]`.

The host's own private network is not ruled to be CR-3's private segment; RW-1's proof
is what would put that question on the record `[R]`. Nothing in this deployment or in
this record requires on-premises or customer-managed hosting `[V]`.
