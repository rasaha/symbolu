# Ugence governed review service composition root — scoping record

**Status: SCOPED, AWAITING RULING — nothing here is implemented.** This record scopes
where `ReviewService` is composed and served, with the identity port (AI-C), the
linkage appender (HE-1) and the durable adapter it needs. It authorizes no code, adds
no dependency, provisions no secret and reopens no ruling of P3E, GAS-7, HE or ID.

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

## 3 — What the root composes `[I]`

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
is never stored (AI-B, AI-C).

## 4 — Constraints the root must satisfy `[I]`

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
  studio image; the worker image would need its own gate set, and until it has one it
  carries none.
- **Label.** `REFERENCE_GRADE_SHADOW_ONLY`: every provider the worker invokes is a
  fixture, every decision is `PRESENTED_UNPROVEN` until AI-C runs against a real
  issuer, and `ENFORCEMENT_ENABLED` stays `False`.

## 5 — Owner decisions `[R]`

| # | Decision | Recommendation |
|---|---|---|
| **CR-1** | Placement: a separate governed runtime worker deployment unit hosting the DBOS engine, the three stores and the review service; or extend the P3E container; or compose inside the studio backend. | **Separate worker unit.** Facts 2, 5, 6 and 7 rule out the other two without reopening P3E or the studio's driver boundary. |
| **CR-2** | The studio side: add `UGENCE_STUDIO_REVIEW_SERVICE_URL` to the P3E configuration allowlist and serve `create_combined_app` under the existing gate, amending `approved-runtime-config`; or keep P3E at v1 and reach the review screens only from a non-P3E profile. | **Amend P3E to serve v2 with the one new variable.** Otherwise the ratified deployment can never show the review screens. |
| **CR-3** | Protection of the service listener: private-network reachability plus TLS with the identity port mandatory in production; or an access gate of its own in front of `build_app`. | **Private network, TLS, identity port mandatory.** A second Basic gate would hold a second credential in the studio, which HR-1 and ID-1 forbid. |
| **CR-4** | Production posture: one `UGENCE_REVIEW_DEPLOYMENT_MODE` that sets the four production switches together and fails closed on any static adapter or in-memory store; or leave them independent. | **One switch.** Four independent flags are four ways to ship a fixture as production. |
| **CR-5** | Egress: allowlist exactly the JWKS host as platform configuration, recorded as external evidence; or require the issuer inside the private network with no egress at all. | **Allowlisted single host.** Enterprise issuers are rarely inside the segment; the rule is recorded, not assumed. |

Prohibitions, stated once: no database driver, DSN or store in the studio; no
credential beyond the database DSNs in the worker; no second identity provider; no
static identity or eligibility adapter in production mode; no container gate described
as passed on account of the worker; no LIVE execution.

## 6 — Sequence and ceiling

1. **Ruling** on CR-1 to CR-5 (documentation only).
2. **Worker composition root**: a `deployment/governed-runtime-worker` profile with its
   configuration, the four-switch production mode, the SQLite volume, the JWKS egress
   record, TLS on the listener, and tests that a fixture adapter or in-memory store is
   refused in production and that the studio's proof header reaches the service.
   Label: **Reference-grade, shadow-only**.
3. **P3E amendment** (CR-2): the variable, the combined app under the gate, the
   runtime-config record and its freeze test.
4. **Worker container gates**: a gate set for the worker image, entered only when the
   mirror blocker is cleared, since no image can be built until then.

**Ceiling.** With steps 2 and 3 the review screens work end to end against fixture
providers and the in-process issuer. Real approver identity waits on an enterprise
issuer (adapter ADR fact 10); enforcement and LIVE wait on AI-E, the external security
review and the mirror.

## 7 — Next step

Rule on CR-1 to CR-5. No implementation prompt is issued while they are open.
