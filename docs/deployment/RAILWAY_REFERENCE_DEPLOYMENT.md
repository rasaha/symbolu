# Governance Studio and Authority Plane — Railway reference deployment

A step-by-step walkthrough: one service at a time, in order, with a check after each.
Do not start a part until the previous one passes its check — every later service needs
an address the earlier one hands you.

    THIS PRODUCES A SINGLE-INSTANCE REFERENCE DEPLOYMENT OVER SYNTHETIC DATA.
    IT IS NEVER PRODUCTION, PILOT OR ENTERPRISE EVIDENCE.

**Does not**: run the worker in production mode · produce a gate-evidenced image ·
authenticate a read · grant permissions · provision credentials · execute agents · use
production data.

Evidence labels as the ADRs use them: `[V]` verified against this repository, `[I]`
inferred or from vendor documentation, `[G]` gap.

## What the rulings allow here

`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md` §8 (RW-1 to RW-6, owner,
2026-09-08) and `deployment/governed-runtime-worker/RAILWAY_HOSTING_DECISION.json` govern
what may be deployed on a managed cloud host and what may be claimed of it.

| Ruling | Effect on this walkthrough |
|---|---|
| RW-1 `DEFER_PENDING_NETWORK_PROOF` | The worker's `is_private_bind` check is unchanged. It is not applied in `test` mode, which is the only reason `BIND_HOST=::` appears in part 5. |
| RW-2 `EXTERNALLY_GATED_DIGEST_PINNED_IMAGE_ONLY` | A Railway-built image is ungated. Admissible here because this is demonstration evidence; never for production. |
| RW-3 `OWNER_CA_ISSUED_AND_CLIENT_VERIFIED` | No certificate authority exists yet, so the worker runs `test` mode over plain HTTP inside the private network rather than unverified TLS. |
| RW-4 `REAL_AP3_HTTPS_JWKS_ISSUER_REQUIRED_FOR_PRODUCTION` | No identity port is composed. Every authority read stays `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY`. |
| RW-5 `ONE_POSTGRES_SERVICE_TWO_LOGICAL_DATABASES` | One PostgreSQL service, two databases, no public database endpoint. |
| RW-6 `SINGLE_INSTANCE_REFERENCE_DEPLOYMENT_ONLY` | One replica. The volume is not shared and no availability claim follows. |

---

## Part 0 — Before you create anything

**0.1 Sign in and check the plan.** Hobby is enough. Pro is needed only to deploy a
pre-built image from a private registry, which this walkthrough does not do `[I]`.

**0.2 Connect GitHub and grant access to `rasaha/symbolu`.** Account Settings → Connected
Accounts. The repository is private; if it does not appear in the service picker, this is
why `[I]`.

**0.3 Note the branch.** Every service below is pointed at
`claude/railway-hosting-setup-r5qk1s`, **not** the repository's default branch.

> The authority plane's `server.mjs` and its `start` script exist only on that branch
> `[V]`. Deploying the default branch fails at boot with `npm error Missing script:
> "start"` — after a successful build, so it reads as a platform fault rather than a
> branch selection.

**0.4 Create an empty project.** All four services must share one project and one
environment, or no private network exists between the plane and the worker `[I]`.

---

## Part 1 — `studio-api`

The v1 + v2 planning API. Everything else waits on its URL.

**1.1** Add a service from `rasaha/symbolu`; rename it `studio-api`. The first build will
fail; you are about to replace what it does.

**1.2** Settings → Source:

```
Branch:         claude/railway-hosting-setup-r5qk1s
Root Directory: /                 # the repository root, not the backend folder
Watch Paths:    apps/ugence-governance-studio/backend/**
                packages/**
```

The root directory is the whole repository because this distribution depends on
first-party packages held elsewhere in the tree; a narrower root puts them outside the
build context `[V]`.

**1.3** Settings → Build → Build Command. This is the studio Dockerfile's install list
(`deployment/governance-studio/Dockerfile:60-68`) minus `/build/deployment`, the gated
deployment package this service does not use:

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

Every entry is load-bearing. Installing only the last one builds and then dies at boot on
`ModuleNotFoundError: ugence_agent_runtime`, because the v2 surface imports the agent
runtime at module load `[V]`.

**1.4** Settings → Deploy:

```
Start Command:     uvicorn ugence_governance_studio_api.app_v2:create_combined_app \
                     --factory --host 0.0.0.0 --port $PORT
Healthcheck Path:  /health
```

`create_combined_app` serves v1 and v2 together, takes no required argument and reads
`UGS_API_*` from the environment (`app_v2.py:166-184`, `settings.py:72-84`) `[V]`.

> Do not leave the start command blank. The repository root carries `nixpacks.toml` and
> `Procfile` belonging to the Symbol-U research API `[V]`; without an override Railway
> starts that instead — it boots, looks healthy, and serves the wrong application. Neither
> file may be deleted; the other service uses them.

**1.5** Variables: `UGS_API_ENABLE_DOCS=false`. Leave CORS for part 3. Deploy.

**1.6** Settings → Networking → Generate Domain. Copy the URL.

**1.7 Check.**

```bash
curl -s https://<studio-api>.up.railway.app/health   # {"status":"healthy"}
curl -s https://<studio-api>.up.railway.app/ready    # "ready":true
```

Pass condition: `/ready` reports `scenario_manifests_load`, `fixture_hashes_match` and
`awc_import_ok` all true `[V]`. A false `awc_import_ok`, or a `ModuleNotFoundError` in the
deploy log, means a package is missing from 1.3 — the error names it.

---

## Part 2 — `studio-web`

The studio's browser app. It needs `studio-api`'s URL *before* it builds.

**2.1** Add a second service from the same repository; rename it `studio-web`.

**2.2** Settings:

```
Branch:         claude/railway-hosting-setup-r5qk1s
Root Directory: apps/ugence-governance-studio/frontend
Watch Paths:    apps/ugence-governance-studio/frontend/**
Build Command:  npm ci && npm run build
Start Command:  npx -y serve@14 -s dist -l $PORT
```

`-s` serves `index.html` for unknown paths, so the router survives a refresh.

**2.3** Variables:

```
NODE_VERSION=22
VITE_API_BASE_URL=https://<studio-api>.up.railway.app     # no trailing slash
```

`config.ts:10-25` sanitizes this value and falls back to `http://127.0.0.1:8000` if it
does not parse `[V]`. It is compiled into the bundle at build time `[V]`: changing it
later requires a **redeploy**, not a restart.

**2.4** Generate a domain and open it. Expect a full-page *"Governance Studio API is not
compatible"* with *Detected contract: unknown*. That is correct until part 3.

---

## Part 3 — Let the API accept the browser

**3.1** On `studio-api`, Variables:

```
UGS_API_CORS_ALLOWED_ORIGINS=https://<studio-web>.up.railway.app
```

Exactly the origin the browser sends: scheme included, no trailing slash, no path.
`cors_allowed_origins` defaults to an empty list (`settings.py:74`) `[V]`, so unset means
allow nothing.

**3.2** Redeploy `studio-api`, then reload the studio.

Pass condition: the scenario catalog renders and the browser console is clean `[V]`.
Screens whose seams are unconfigured report typed gaps — `available: false` with a reason
— which is this deployment's correct state, not a fault `[V]`.

> At boot the app calls `/health`, `/ready` and `/version` and refuses to render until it
> recognises the frozen `governance_studio.api.v1` contract `[V]`. When those calls are
> blocked the failure presents as the contract screen above, which reads as a version
> mismatch and is almost always the origin string.

---

## Part 4 — `authority-plane`

Deploy before the worker; it runs on its own and says so.

**4.1** Add a third service from the same repository; rename it `authority-plane`.

**4.2** Settings:

```
Branch:         claude/railway-hosting-setup-r5qk1s
Root Directory: apps/authority-plane
Watch Paths:    apps/authority-plane/**
Build Command:  npm ci && npm run build
Start Command:  npm start
```

`npm start` runs the plane's own `server.mjs`: it serves the built app and proxies `/api`
to the worker server-side, so the worker's address never reaches a browser (CR-3). This is
the file that exists only on the branch from 0.3 `[V]`.

**4.3** Variables:

```
NODE_VERSION=22
WORKER_URL=http://worker.railway.internal:8444
```

Do **not** set `VITE_WORKER_BASE_URL`. Unset, the client calls `/api` on its own origin
(`client.ts:13`) `[V]`; set, it would compile a private address into the browser bundle,
where it cannot resolve. Set `WORKER_URL` now even though no worker exists yet.

**4.4** Generate a domain and check:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://<authority-plane>.up.railway.app/api/authority/grants     # 405
```

Pass condition: the four screens load reporting *"The authority plane's worker is not
reachable"*, and that `POST` answers 405 `[V]`. The proxy forwards `GET` only, and only to
the four paths `security/approved-operations.json` approves, read from that manifest at
startup; it forwards no request header, so it carries neither a credential nor the write
proof header `[V]`.

---

## Part 5 — `worker` (optional, `test` mode only)

Deploy only to give the plane data.

**5.1** Project → New → Database → Add PostgreSQL. One service suffices; the worker needs
two databases that differ, so connect once and `CREATE DATABASE sysdb;`. No public domain.

**5.2** Add a service from the same repository, then Settings:

```
Branch:           claude/railway-hosting-setup-r5qk1s
Root Directory:   /
Dockerfile Path:  deployment/governed-runtime-worker/Dockerfile
```

Rename it `worker` — the name must match `WORKER_URL` from 4.3.

**5.3** Settings → Volumes → Add Volume, mount path `/var/lib/ugence-review`. The three
SQLite stores live there (`composition.py:205-217`; `Dockerfile:68` declares the volume)
`[V]`. A volume attaches to one instance, which is what makes this deployment
single-replica by construction `[I]`.

**5.4** Variables:

```
UGENCE_REVIEW_DEPLOYMENT_MODE=test
UGENCE_REVIEW_BIND_HOST=::
UGENCE_REVIEW_PORT=8444
UGENCE_REVIEW_DATA_DIR=/var/lib/ugence-review
UGENCE_REVIEW_APP_DATABASE_URL=${{Postgres.DATABASE_URL}}
UGENCE_REVIEW_SYSTEM_DATABASE_URL=${{Postgres.DATABASE_URL}}   # edit the database name
                                    # at the end to sysdb — the two must differ (config.py:146)
UGENCE_REVIEW_TENANT_ID=tenant-demo
UGENCE_REVIEW_REQUIRED_ROLE=approver
UGENCE_REVIEW_DEFINITION_DIGEST=<the workload digest>
```

`WorkerConfig.validate()` returns empty for exactly these values in `test` mode `[V]`: the
bind check, the TLS requirement and the identity requirement apply in production mode only
(`config.py:158-179`).

**5.5** Deploy, and never generate a domain for it.

Pass condition: the log shows `WARNING: UGENCE_REVIEW_DEPLOYMENT_MODE=test` — leave that
line visible, it is the label this deployment runs under — and the plane's four screens
answer under a banner reading `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY` `[V]`.

Railway's private DNS name is `<service>.railway.internal`, resolves only inside the
environment, and requires the listener to accept connections on the container's IPv6
interface `[I]`. That behaviour is vendor-documented and not measured here; RW-1's proof is
what would put it on the record `[G]`.

> **Do not switch to production mode.** The composition refuses it in three independent
> places: an unspecified bind (RW-1 preserves that check), missing TLS certificate and key
> files with no CA to issue them (RW-3), and a missing `https` JWKS issuer (RW-4) `[V]`.
> RW-2 separately rules that a production image comes from the external gate pipeline by
> digest, which a Railway build is not.

---

## If something fails

| What you see | What it is | Fix |
|---|---|---|
| `Missing script: "start"` | Wrong branch; the plane's server is not on the default branch | 0.3 |
| `ModuleNotFoundError: ugence_agent_runtime` | Incomplete install list; the v2 surface imports it at module load | 1.3 |
| `studio-api` serves an unrelated API | Start command blank, so the root `Procfile` won | 1.4 |
| "API is not compatible / Detected contract: unknown" | CORS origin mismatch, not a version mismatch | 3.1 |
| Studio still calls the old API after a variable change | `VITE_*` is compiled into the bundle | redeploy `studio-web` |
| Plane reports the worker unreachable | Correct until part 5; after it, check the service is named `worker` | 4.3, 5.2 |
| Worker exits at boot printing a list | It reports every reason at once; usually the two DSNs are identical | 5.4 |

## Verification of this document

Run against this repository on 2026-09-08, outside Railway: the 1.3 install list installs
cleanly into a clean virtual environment and the 1.4 start command serves v1 and v2 with
`/health`, `/ready` and `/version` answering 200; the 2.4 failure was reproduced with a
mismatched CORS origin and cleared by 3.1, after which the scenario catalog loaded with no
console errors; the plane's four reads answered through `server.mjs` over a self-signed TLS
listener carrying the worker's real `build_authority_reads` router, with `POST` refused
405; and `WorkerConfig.validate()` returned empty for the 5.4 variables. Railway's UI
wording and private-network behaviour are vendor documentation and may drift. No Railway
deployment was performed `[G]`.
