# Governance Studio and Authority Plane — Railway reference deployment

Four services in one Railway project: the studio's API and its frontend, the authority
plane behind its own proxying front, and — optionally — the governed runtime worker in
`test` mode on the private network.

    THIS PRODUCES A SINGLE-INSTANCE REFERENCE DEPLOYMENT OVER SYNTHETIC DATA.
    IT IS NEVER PRODUCTION, PILOT OR ENTERPRISE EVIDENCE.

**Does not**: run the worker in production mode · produce a gate-evidenced image ·
authenticate a read · grant permissions · provision credentials · execute agents · use
production data.

## What the rulings allow here

`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md` §8 (RW-1 to RW-6, owner,
2026-09-08) and `deployment/governed-runtime-worker/RAILWAY_HOSTING_DECISION.json` govern
what may be deployed on a managed cloud host and what may be claimed of it.

| Ruling | Effect on this runbook |
|---|---|
| RW-1 `DEFER_PENDING_NETWORK_PROOF` | The worker's `is_private_bind` check is unchanged. In `test` mode it is not applied, which is the only reason `BIND_HOST=::` appears below. |
| RW-2 `EXTERNALLY_GATED_DIGEST_PINNED_IMAGE_ONLY` | A Railway-built image is ungated. Admissible for this deployment because it is demonstration evidence; never for production. |
| RW-3 `OWNER_CA_ISSUED_AND_CLIENT_VERIFIED` | No certificate authority exists yet, so the worker here runs `test` mode over plain HTTP inside the private network rather than unverified TLS. |
| RW-4 `REAL_AP3_HTTPS_JWKS_ISSUER_REQUIRED_FOR_PRODUCTION` | No identity port is composed. Every authority read stays `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY`. |
| RW-5 `ONE_POSTGRES_SERVICE_TWO_LOGICAL_DATABASES` | Two databases, distinct DSNs, no public database endpoint. |
| RW-6 `SINGLE_INSTANCE_REFERENCE_DEPLOYMENT_ONLY` | One replica. The volume is not shared, and no availability claim follows from this deployment. |

Evidence labels as the ADRs use them: `[V]` verified against this repository, `[I]`
inferred or from vendor documentation, `[G]` gap.

## The four services

| Service | Root directory | Public domain | Reaches |
|---|---|---|---|
| `studio-api` | `/` (repository root) | yes | its own scenario fixtures |
| `studio-web` | `apps/ugence-governance-studio/frontend` | yes | `studio-api`, from the browser |
| `authority-plane` | `apps/authority-plane` | yes | `worker`, server-side only |
| `worker` | `/` with the worker Dockerfile | **never** | two PostgreSQL databases, one volume |

Deploy in that order. `VITE_*` values are compiled into the JavaScript bundle at build
time `[V]`, so `studio-web` and `authority-plane` each need their upstream's address
before they build; changing one afterwards requires a redeploy, not a restart.

## 1 — `studio-api`

The v1 + v2 planning API (`apps/ugence-governance-studio/backend`). Its distribution
depends on first-party packages held elsewhere in the repository, so this service's root
directory is the repository root and the build command installs them explicitly.

Installing the backend distribution alone starts and then fails on
`ModuleNotFoundError: ugence_agent_runtime`: the v2 surface imports the agent runtime at
module load `[V]`. The list below is the studio Dockerfile's install list
(`deployment/governance-studio/Dockerfile:60-68`) minus `/build/deployment`, the gated
deployment package this service does not use.

**Build command**

```bash
pip install "pydantic>=2" "fastapi>=0.110" "uvicorn>=0.27" "starlette>=0.36" \
  ./packages/tooling/policy-workflow-compiler \
  ./packages/capabilities/agent-workforce-composer \
  ./packages/runtime/agent-runtime \
  ./packages/governance-contracts ./packages/jcs \
  ./packages/uvi-policy-contracts ./packages/policy-authority \
  ./packages/capabilities/agentic-proposer \
  ./packages/integration/agent-constitution-policy \
  ./packages/integration/agent-constitution-conformance \
  ./packages/integration/agent-constitution-activation \
  ./packages/integration/ai-system-registry \
  ./packages/integration/data-use-admission \
  ./packages/integration/vendor-dependency \
  ./packages/capabilities/action-clearance \
  ./packages/integration/clearance-export \
  ./apps/ugence-governance-studio/backend
```

**Start command.** `create_combined_app` serves v1 and v2 together, takes no required
argument and reads `UGS_API_*` from the environment
(`app_v2.py:166-184`, `settings.py:72-84`) `[V]`.

```bash
uvicorn ugence_governance_studio_api.app_v2:create_combined_app \
  --factory --host 0.0.0.0 --port $PORT
```

| Setting | Value |
|---|---|
| Root directory | `/` |
| Watch paths | `apps/ugence-governance-studio/backend/**`, `packages/**` |
| Health check path | `/health` |
| Variables | `UGS_API_CORS_ALLOWED_ORIGINS` (set in step 2), `UGS_API_ENABLE_DOCS=false` |

The repository root carries another service's build configuration: `nixpacks.toml` and
`Procfile` start the Symbol-U research API `[V]`. Setting the build and start commands
above overrides both; neither file may be deleted, because that service uses them.

Generate a domain. `/health`, `/ready` and `/version` answer 200; `/ready` reports
`scenario_manifests_load`, `fixture_hashes_match` and `awc_import_ok`, which is the
fastest read on a broken install `[V]`.

## 2 — `studio-web`

A static SPA (`apps/ugence-governance-studio/frontend`). It reaches `studio-api` from the
browser, so that service must be public and must allow this one's origin.

| Setting | Value |
|---|---|
| Root directory | `apps/ugence-governance-studio/frontend` |
| Watch paths | `apps/ugence-governance-studio/frontend/**` |
| Build | `npm ci && npm run build` |
| Start | `npx -y serve@14 -s dist -l $PORT` |
| Variables | `NODE_VERSION=22`, `VITE_API_BASE_URL` |

Set `VITE_API_BASE_URL` to `studio-api`'s public origin with scheme and no trailing slash;
`config.ts:10-25` sanitizes it and falls back to `http://127.0.0.1:8000` if it does not parse
`[V]`. Generate a domain for this service, then set on `studio-api` and redeploy it:

```bash
UGS_API_CORS_ALLOWED_ORIGINS=https://<studio-web>.up.railway.app
```

**The failure worth recognising.** At boot the SPA calls `/health`, `/ready` and
`/version` and refuses to render until it recognises the frozen
`governance_studio.api.v1` contract. When the CORS origin does not match character for
character, those three calls fail and the app shows a full-page *"Governance Studio API is
not compatible"* with *Detected contract: unknown* — which reads as a version mismatch and
is almost always the origin `[V]`. `cors_allowed_origins` defaults to an empty list
(`settings.py:74`), so an unset variable produces the same screen `[V]`.

Once it renders, the scenario catalog loads, and the v2 screens whose seams are
unconfigured report typed gaps — `available: false` with a reason — rather than errors
`[V]`. That is this deployment's correct state, not a fault.

## 3 — `authority-plane`

Four read-only screens over the worker (`apps/authority-plane`). The browser never reaches
the worker: CR-3 keeps it on the private segment, and the plane's own Node process
(`server.mjs`) serves the built SPA and proxies to it.

| Setting | Value |
|---|---|
| Root directory | `apps/authority-plane` |
| Watch paths | `apps/authority-plane/**` |
| Build | `npm ci && npm run build` |
| Start | `npm start` |
| Variables | `NODE_VERSION=22`, `WORKER_URL` |

```bash
WORKER_URL=http://worker.railway.internal:8444
# VITE_WORKER_BASE_URL: leave UNSET. The client then defaults to /api (client.ts:13),
# which is same-origin, and the worker's address never reaches a browser.
```

Generate a domain for the plane only. Its proxy forwards `GET` and nothing else, and only
to the four paths `security/approved-operations.json` approves, read from that manifest at
startup: a `POST` to `/api/authority/grants` answers 405 and an unapproved path answers
404 `[V]`. It forwards no request header, so it carries neither a credential nor the write
proof header `[V]`. Until the worker exists the screens show *"The authority plane's worker
is not reachable"*, which is the correct empty state.

## 4 — `worker` (optional, `test` mode only)

Deploy only to give the plane data. Add the PostgreSQL service and the volume first.

| Setting | Value |
|---|---|
| Source | Dockerfile `deployment/governed-runtime-worker/Dockerfile`, build context `/` |
| Public domain | none — never generate one |
| Volume | mounted at `/var/lib/ugence-review` |
| Port | 8444, private network only |

```bash
UGENCE_REVIEW_DEPLOYMENT_MODE=test
UGENCE_REVIEW_BIND_HOST=::
UGENCE_REVIEW_PORT=8444
UGENCE_REVIEW_DATA_DIR=/var/lib/ugence-review
UGENCE_REVIEW_APP_DATABASE_URL=postgresql://…/appdb
UGENCE_REVIEW_SYSTEM_DATABASE_URL=postgresql://…/sysdb   # must differ (config.py:146)
UGENCE_REVIEW_TENANT_ID=tenant-demo
UGENCE_REVIEW_REQUIRED_ROLE=approver
UGENCE_REVIEW_DEFINITION_DIGEST=<the workload digest>
```

`WorkerConfig.validate()` returns empty for exactly these values in `test` mode `[V]`: the
bind check, the TLS requirement and the identity requirement apply in production mode only
(`config.py:158-179`). The listener is plain HTTP, which is why the plane's `WORKER_URL`
above is `http://`. Startup prints `WARNING: UGENCE_REVIEW_DEPLOYMENT_MODE=test` — leave it
in the logs; it is the label this deployment runs under.

Railway's private DNS name is `<service>.railway.internal`, resolves only inside the
environment, and requires the listener to accept connections on the container's IPv6
interface `[I]`. That behaviour is vendor-documented and not measured here; RW-1's proof is
what would put it on the record `[G]`.

**Production mode is not in this runbook** because the composition refuses it in three
independent places: an unspecified bind (RW-1 preserves that check), missing TLS
certificate and key files with no CA to issue them (RW-3), and a missing `https` JWKS
issuer (RW-4) `[V]`. RW-2 separately rules that a production image comes from the external
gate pipeline by digest, which a Railway build is not.

## After it is up

- Changing an upstream URL is a **rebuild**, not a restart: the old value is in the bundle.
- Set watch paths on every service, or a commit anywhere rebuilds all four.
- Never generate a domain for the worker or the databases.
- `<service>.railway.internal` is not a value any `VITE_*` variable may hold — it does not
  resolve in a browser.

## Verification of this document

Run against this repository on 2026-09-08, outside Railway: the `studio-api` install list
installs cleanly into a clean virtual environment and the factory serves v1 and v2 with
`/health`, `/ready` and `/version` answering 200; the frontend built with
`VITE_API_BASE_URL` set showed the *"not compatible"* screen against a mismatched CORS
origin and the scenario catalog with no console errors against the correct one; the
authority plane's four reads answered through `server.mjs` over a self-signed TLS listener
carrying the worker's real `build_authority_reads` router, with `POST` refused 405; and
`WorkerConfig.validate()` returned empty for the `test`-mode variables above. No Railway
deployment was performed `[G]`.
