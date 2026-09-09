# Governance Studio, Console and Authority Plane — Railway reference deployment

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

## Two repositories, one deployment

The three front ends no longer deploy from this repository. `tools/export_demo.py` and the
`demo-export-publish` workflow generate them into `rasaha/demo`, which now holds that
content — first successful run 2026-09-09, source commit `40ff3818`, 141 files, five
verifiers passed `[V]`.

| Service | Deploys from | Root directory |
|---|---|---|
| `studio-api` | `rasaha/symbolu` | `/` |
| `console-api` | `rasaha/symbolu` | `/` |
| `worker` | `rasaha/symbolu` | `/` (Dockerfile) |
| `studio-web` | `rasaha/demo` | `apps/ugence-governance-studio/frontend` |
| `console-web` | `rasaha/demo` | `apps/console` |
| `authority-plane` | `rasaha/demo` | `apps/authority-plane` |

The root directories under `rasaha/demo` are identical to the paths those applications
occupy here: the export preserves the tree layout, so only the repository field changes
`[V]`.

> **`rasaha/demo` is generated. A deployment is never fixed by editing it.**
> `replace-destination-content` removes every tracked file before copying the export in,
> and `commit-and-push` force-pushes, so anything committed there by hand is discarded
> without warning on the next export. This is observed, not theoretical: the destination's
> first commit added `.github/workflows/blank.yml`, and the first export deleted it `[V]`.
>
> The practical consequence for this walkthrough is that **no Railway configuration file
> can live in `rasaha/demo`** — a `railway.json`, `nixpacks.toml` or `Procfile` committed
> there does not survive. Configure the three demo services entirely through the Railway
> dashboard, or add the file to `tools/export_demo.py` here so the export generates it.
> A fix to a front end belongs in this repository and reaches the demo by being exported.

## What the rulings allow here

`ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md` §8 (RW-1 to RW-6, owner,
2026-09-08) and `deployment/governed-runtime-worker/RAILWAY_HOSTING_DECISION.json` govern
what may be deployed on a managed cloud host and what may be claimed of it.

| Ruling | Effect on this walkthrough |
|---|---|
| RW-1 `DEFER_PENDING_NETWORK_PROOF` | The worker's `is_private_bind` check is unchanged. It is not applied in `test` mode, which is the only reason `BIND_HOST=::` appears in part 7. |
| RW-2 `EXTERNALLY_GATED_DIGEST_PINNED_IMAGE_ONLY` | A Railway-built image is ungated. Admissible here because this is demonstration evidence; never for production. |
| RW-3 `OWNER_CA_ISSUED_AND_CLIENT_VERIFIED` | No certificate authority exists yet, so the worker runs `test` mode over plain HTTP inside the private network rather than unverified TLS. |
| RW-4 `REAL_AP3_HTTPS_JWKS_ISSUER_REQUIRED_FOR_PRODUCTION` | No identity port is composed. Every authority read stays `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY`. |
| RW-5 `ONE_POSTGRES_SERVICE_TWO_LOGICAL_DATABASES` | One PostgreSQL service, two databases, no public database endpoint. |
| RW-6 `SINGLE_INSTANCE_REFERENCE_DEPLOYMENT_ONLY` | One replica. The volume is not shared and no availability claim follows. |
| CR-3 (`ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`) | The plane's proxy reaches the worker over a private segment and does not verify its certificate. This is what forbids a public worker origin, and it is what makes part 0.4 a constraint rather than a preference. |

---

## Part 0 — Before you create anything

**0.1 Sign in and check the plan.** Hobby is enough. Pro is needed only to deploy a
pre-built image from a private registry, which this walkthrough does not do `[I]`.

**0.2 Connect GitHub and grant access to both repositories.** Account Settings → Connected
Accounts, then grant `rasaha/symbolu` **and** `rasaha/demo`. Three services come from each.
If a repository does not appear in the service picker, this is why `[I]`.

**0.3 Use each repository's default branch.**

> An earlier revision of this document pinned every service to
> `claude/railway-hosting-setup-r5qk1s`, because the authority plane's `server.mjs` and its
> `start` script existed only there. That is no longer true — both are on this repository's
> default branch, as are all seventeen packages in the 1.3 install list `[V]`. The pin is
> withdrawn, and it must not be reinstated for the demo services: that branch does not
> exist in `rasaha/demo` at all. The export publishes one commit to the default branch, so
> a demo service pointed at that name fails to resolve.

**0.4 Create one project, and put every service in it.** This is the constraint the whole
arrangement turns on. Railway's private network is scoped to a single project *and* a
single environment: `worker.railway.internal` resolves only for services inside that same
project and environment, and from another project the name does not resolve at all `[I]`.

A Railway project draws each of its services from whichever repository you point it at, so
the repository split does not force a project split. Keep them together.

> **Can the authority plane reach the worker if they are in different projects? No.**
> There is no cross-project private networking to configure, and `WORKER_URL` has no valid
> value in that arrangement. If you must use two projects — separate billing, separate
> collaborator access — then `studio-web` and `console-web` may sit alone in one, because
> both reach their APIs over public HTTPS and are genuinely project-agnostic. The
> `authority-plane` goes in the *worker's* project despite deploying from `rasaha/demo`.
>
> Do not bridge the gap by giving the worker a public domain. `server.mjs` sets
> `rejectUnauthorized: false` unconditionally and says why in its own header: *"this
> process must not be given a public worker origin"* `[V]`. Over the private segment the
> unverified hop is the documented trade, because the segment is the protection (CR-3).
> Pointed at a public origin the same line becomes an unverified hop across the internet to
> a publicly reachable worker. It would work, and it would invalidate CR-3. Part 7.5 is
> explicit: never generate a domain for the worker.
>
> The third option is legitimate: **do not deploy the worker at all.** The plane's four
> screens then render under *"The authority plane's worker is not reachable"*, which is
> part 6.4's own pass condition. Decide this deliberately — under a split it is the
> permanent state, not a step you pass through.

---

## Part 1 — `studio-api`

The v1 + v2 planning API. Everything else waits on its URL.

**1.1** Add a service from `rasaha/symbolu`; rename it `studio-api`. The first build will
fail; you are about to replace what it does.

**1.2** Settings → Source:

```
Branch:         <the repository default branch>
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
runtime at module load `[V]`. All seventeen paths are present on the default branch `[V]`.

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

**1.5** Variables: `UGS_API_ENABLE_DOCS=false`. Leave CORS for part 4. Deploy.

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

## Part 2 — `console-api`

The control-plane console's backing service. It has no dependants but the console, so it
can be built any time before part 5.

**2.1** Add a service from `rasaha/symbolu`; rename it `console-api`.

**2.2** Settings:

```
Branch:          <the repository default branch>
Root Directory:  /
Watch Paths:     packages/integration/console-api/**
Build Command:   pip install ./packages/integration/console-api
Start Command:   uvicorn ugence_console_api.app:create_app --factory \
                   --host 0.0.0.0 --port $PORT
```

Use uvicorn directly rather than `python -m ugence_console_api`: the module entry point
reads `CONSOLE_API_PORT` and defaults to 8090, ignoring Railway's `$PORT` `[V]`.

**2.3** No CORS variable pairs with this service. `create_app()` installs `CORSMiddleware`
with `allow_origins=["*"]`, because the console is served from a separate static host `[V]`.

**2.4** Generate a domain.

**2.5 Check.** `/health` answers 200 carrying the audit-ceiling header.

> The service serves five routes and no more (CP-3), and its audit store is in-memory and
> lost on restart (CP-4). Both are declared, not incidental; the console shows a typed
> `CONSOLE_ROUTE_WITHHELD` gap for the two withheld routes rather than an empty result.

---

## Part 3 — `studio-web`

The studio's browser app, now built from `rasaha/demo`. It needs `studio-api`'s URL
*before* it builds.

**3.1** Add a service from **`rasaha/demo`**; rename it `studio-web`.

**3.2** Settings:

```
Repository:     rasaha/demo
Branch:         <the repository default branch>
Root Directory: apps/ugence-governance-studio/frontend
Build Command:  npm ci && npm run build
Start Command:  npx -y serve@14 -s dist -l $PORT
```

`-s` serves `index.html` for unknown paths, so the router survives a refresh.

Verified against the published export tree: `package-lock.json` travels, `tsc --noEmit`
exits 0 even though `tests/` and `vitest.config.ts` are withheld, and `vite build` produces
a bundle `[V]`.

**3.3** Variables:

```
NODE_VERSION=22
VITE_API_BASE_URL=https://<studio-api>.up.railway.app     # no trailing slash
```

`config.ts:10-25` sanitizes this value and falls back to `http://127.0.0.1:8000` if it
does not parse `[V]`, so a typo presents as the contract screen below rather than as an
error. It must be the **public** domain: the value is compiled into the browser bundle
`[V]`, so a `*.railway.internal` address is wrong here even when both services share a
project. Changing it later requires a **redeploy**, not a restart.

**3.4** Generate a domain and open it. Expect a full-page *"Governance Studio API is not
compatible"* with *Detected contract: unknown*. That is correct until part 4.

---

## Part 4 — Let the API accept the browser

**4.1** On `studio-api`, Variables:

```
UGS_API_CORS_ALLOWED_ORIGINS=https://<studio-web>.up.railway.app
```

Exactly the origin the browser sends: scheme included, no trailing slash, no path.
`cors_allowed_origins` defaults to an empty list (`settings.py:74`) `[V]`, so unset means
allow nothing.

Nothing about CORS itself changes under the split — it is origin-based and indifferent to
repositories and projects. What changes is the ordering: the origin now belongs to a
service built from the other repository, so part 3 must complete before this value exists.
Do not add the console's origin here; the console does not call this API.

**4.2** Redeploy `studio-api`, then reload the studio.

Pass condition: the scenario catalog renders and the browser console is clean `[V]`.
Screens whose seams are unconfigured report typed gaps — `available: false` with a reason
— which is this deployment's correct state, not a fault `[V]`.

> At boot the app calls `/health`, `/ready` and `/version` and refuses to render until it
> recognises the frozen `governance_studio.api.v1` contract `[V]`. When those calls are
> blocked the failure presents as the contract screen above, which reads as a version
> mismatch and is almost always the origin string.

---

## Part 5 — `console-web`

The control-plane console. Note the build command: it is **not** the one parts 3 and 6 use.

**5.1** Add a service from **`rasaha/demo`**; rename it `console-web`.

**5.2** Settings:

```
Repository:     rasaha/demo
Branch:         <the repository default branch>
Root Directory: apps/console
Build Command:  npm install && npm run build      # NOT npm ci
Start Command:  npx -y serve@14 -s dist -l $PORT
```

`apps/console` ships **no `package-lock.json`**, in either repository. `npm ci` exits
non-zero with *"can only install with an existing package-lock.json"*; `npm install`
succeeds and the build completes `[V]`. Copying part 3's build command verbatim to this
service is the first failure you will hit.

**5.3** Variables:

```
NODE_VERSION=22
VITE_CONSOLE_API_URL=https://<console-api>.up.railway.app
```

Build-time, same redeploy rule as `VITE_API_BASE_URL`. Unlike the studio's, this value has
no sanitizer: `api.ts:11` falls back to the relative `/api`, which the static host cannot
serve, so an unset value yields failed fetches rather than a typed gap `[V]`.

**5.4** Generate a domain.

Pass condition: the Modules view renders the service's per-engine probes from `/health`
under the keys it returns, and the two withheld routes show as
`CONSOLE_ROUTE_WITHHELD` gaps `[V]`.

---

## Part 6 — `authority-plane`

Deploy before the worker; it runs on its own and says so. Built from `rasaha/demo`, but it
belongs in the **worker's** Railway project — see 0.4.

**6.1** Add a service from **`rasaha/demo`**; rename it `authority-plane`.

**6.2** Settings:

```
Repository:     rasaha/demo
Branch:         <the repository default branch>
Root Directory: apps/authority-plane
Build Command:  npm ci && npm run build
Start Command:  npm start
```

`npm start` runs the plane's own `server.mjs`: it serves the built app and proxies `/api`
to the worker server-side, so the worker's address never reaches a browser (CR-3).
`server.mjs`, the `start` script and `security/approved-operations.json` are all in the
export, and the exported app builds cleanly `[V]`.

> **Do not wire the export's other scripts into a build.** `package.json` is copied
> unchanged, so `verify:boundary` and `test` are still listed — but
> `scripts/verify-boundary.mjs`, `vitest.config.ts` and `tests/` are withheld from the
> export. Those scripts fail in `rasaha/demo` by construction, because the worker's
> contract they bind to by hash stays here. That is the design, recorded in
> `EXPORT_PROVENANCE.json` under `proofs_that_do_not_travel`; the verifier ran *here*
> before the export was written.

**6.3** Variables:

```
NODE_VERSION=22
WORKER_URL=http://worker.railway.internal:8444
```

Valid only if this service and `worker` are in the same Railway project and environment,
and only if the worker service is named exactly `worker`. `http:`, not `https:` — under
RW-3 the worker runs `test` mode over plain HTTP inside the private segment, which differs
from `server.mjs`'s own `https://127.0.0.1:8444` default, the local development shape.

Do **not** set `VITE_WORKER_BASE_URL`. Unset, the client calls `/api` on its own origin
(`client.ts:13`) `[V]`; set, it would compile a private address into the browser bundle,
where it cannot resolve. Set `WORKER_URL` now even though no worker exists yet.

**6.4** Generate a domain and check:

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

## Part 7 — `worker` (optional, `test` mode only)

Deploy only to give the plane data. Unchanged by the split: it stays in `rasaha/symbolu`.

**7.1** Project → New → Database → Add PostgreSQL. One service suffices; the worker needs
two databases that differ, so connect once and `CREATE DATABASE sysdb;`. No public domain.

**7.2** Add a service from `rasaha/symbolu`, then Settings:

```
Branch:           <the repository default branch>
Root Directory:   /
Dockerfile Path:  deployment/governed-runtime-worker/Dockerfile
```

Rename it `worker` — the name must match `WORKER_URL` from 6.3, and that matching only
means anything within one project and environment.

**7.3** Settings → Volumes → Add Volume, mount path `/var/lib/ugence-review`. The three
SQLite stores live there (`composition.py:205-217`; `Dockerfile:68` declares the volume)
`[V]`. A volume attaches to one instance, which is what makes this deployment
single-replica by construction `[I]`.

**7.4** Variables:

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
UGENCE_REVIEW_DEFINITION_DIGEST=shadow-v1
```

`WorkerConfig.validate()` returns empty for exactly these values in `test` mode `[V]`: the
bind check, the TLS requirement and the identity requirement apply in production mode only
(`config.py:158-179`).

`DEFINITION_DIGEST` is a free-form required label naming the compiled definition this
worker runs, not a value you compute: `validate()` asks only that it be non-empty
(`config.py:152`), and the worker README's own run line uses `shadow-v1`
(`deployment/governed-runtime-worker/README.md:132`) `[V]`.

**7.5** Deploy, and never generate a domain for it.

Pass condition: the log shows `WARNING: UGENCE_REVIEW_DEPLOYMENT_MODE=test` — leave that
line visible, it is the label this deployment runs under — and the plane's four screens
answer under a banner reading `PRESENTED_UNPROVEN` and `IN_PROCESS_ISSUER_ONLY` `[V]`.

Railway's private DNS name is `<service>.railway.internal`, resolves only inside the
environment, and requires the listener to accept connections on the container's IPv6
interface `[I]`. That behaviour is vendor-documented and not measured here; RW-1's proof is
what would put it on the record `[G]`.

> **The worker image has never been built anywhere** `[V]`
> (`CONTAINER_GATE_SET.json`: `execution_state: NOT_EXECUTED`). Until 2026-09-08 it could
> not have been: this Dockerfile is built with the repository root as its context — by the
> container job (`-f deployment/governed-runtime-worker/Dockerfile .`) and by any managed
> host — where the root `.dockerignore` (`*`, re-including `symbolu/` only, written for the
> GKE controller image) excluded **all 19** of its `COPY` sources `[V]`. The container gate
> set has never executed, so nothing caught it. `Dockerfile.dockerignore` beside the
> Dockerfile now carries that deployment's own exclusion set, which BuildKit reads in
> preference to the context root's; the same defect and the same fix apply to
> `deployment/governance-studio/Dockerfile` (29 of 29 sources) `[V]`. The build itself
> remains unproven: no image has been produced from either Dockerfile `[G]`.

> **Do not switch to production mode.** The composition refuses it in three independent
> places: an unspecified bind (RW-1 preserves that check), missing TLS certificate and key
> files with no CA to issue them (RW-3), and a missing `https` JWKS issuer (RW-4) `[V]`.
> RW-2 separately rules that a production image comes from the external gate pipeline by
> digest, which a Railway build is not.

---

## The four variables, in one place

| Variable | Set on | Value | When it takes effect |
|---|---|---|---|
| `VITE_API_BASE_URL` | `studio-web` | `https://<studio-api>.up.railway.app` | build time — redeploy |
| `VITE_CONSOLE_API_URL` | `console-web` | `https://<console-api>.up.railway.app` | build time — redeploy |
| `UGS_API_CORS_ALLOWED_ORIGINS` | `studio-api` | `https://<studio-web>.up.railway.app` | restart |
| `WORKER_URL` | `authority-plane` | `http://worker.railway.internal:8444` | restart |

The first two are public HTTPS domains compiled into a browser bundle. The last is a
private address that must never be public, and resolves only within one project and
environment.

## If something fails

| What you see | What it is | Fix |
|---|---|---|
| A demo service's branch will not resolve | `claude/railway-hosting-setup-r5qk1s` does not exist in `rasaha/demo` | 0.3 |
| `ModuleNotFoundError: ugence_agent_runtime` | Incomplete install list; the v2 surface imports it at module load | 1.3 |
| `studio-api` serves an unrelated API | Start command blank, so the root `Procfile` won | 1.4 |
| `console-api` answers on 8090, not `$PORT` | `python -m ugence_console_api` used instead of the uvicorn line | 2.2 |
| "API is not compatible / Detected contract: unknown" | CORS origin mismatch, not a version mismatch | 4.1 |
| Studio or console still calls the old API after a variable change | `VITE_*` is compiled into the bundle | redeploy that service |
| `npm ci` fails: *can only install with an existing package-lock.json* | `console-web`; that app ships no lockfile | 5.2 |
| Console fetches fail against the deployed origin | `VITE_CONSOLE_API_URL` unset, so the client fell back to a relative `/api` | 5.3 |
| Plane reports the worker unreachable | Correct until part 7; after it, check the service is named `worker` — **or** the plane and worker are in different Railway projects, in which case no configuration fixes it | 0.4, 6.3, 7.2 |
| Worker exits at boot printing a list | It reports every reason at once; usually the two DSNs are identical | 7.4 |
| A hand edit to `rasaha/demo` vanished | The next export discarded it; that is the design | the note at the top |

## Verification of this document

The parts that stayed in this repository were run against it on 2026-09-08, outside
Railway: the 1.3 install list installs cleanly into a clean virtual environment and the 1.4
start command serves v1 and v2 with `/health`, `/ready` and `/version` answering 200; the
3.4 failure was reproduced with a mismatched CORS origin and cleared by 4.1, after which
the scenario catalog loaded with no console errors; the plane's four reads answered through
`server.mjs` over a self-signed TLS listener carrying the worker's real
`build_authority_reads` router, with `POST` refused 405; and `WorkerConfig.validate()`
returned empty for the 7.4 variables.

The split was verified on 2026-09-09 against the **published export tree**, which is not
this tree — `tests/`, `vitest.config.ts`, `playwright.config.ts` and the plane's boundary
verifier are all withheld from it, so the earlier front-end verification did not carry
over `[V]`:

- `rasaha/demo` holds the export at `df3716fc`; `EXPORT_PROVENANCE.json` names source
  commit `40ff3818`, five verifiers passed, `verifiers_skipped: false`, 141 files.
- All three front ends build from that tree: `studio-web` (`tsc --noEmit` exit 0, 1859
  modules), `authority-plane` (38 modules), `console-web` (1365 modules, after
  `npm install`; `npm ci` fails as part 5.2 describes).
- `VITE_API_BASE_URL` appears verbatim in the studio bundle after a build with it set.
- `server.mjs`, the `start` script and `security/approved-operations.json` are present in
  the export; `scripts/verify-boundary.mjs`, `vitest.config.ts` and `tests/` are not.
- `server.mjs` forwards `GET` only, to the four approved paths, forwards no request header,
  and sets `rejectUnauthorized: false`.
- `ugence_console_api.__main__` reads `CONSOLE_API_PORT` and ignores `$PORT`;
  `create_app()` sets `allow_origins=["*"]`.
- The export deleted the destination's pre-existing `.github/workflows/blank.yml`,
  demonstrating the one-way property directly.

**Not verified `[G]`.** No Railway deployment has been performed, before or after the
split. Every build above ran locally; none ran on Railway's builders. Railway's UI wording,
its per-service repository selection, and its private-network scoping are vendor
documentation `[I]` and may drift — in particular, the claim in 0.4 that no cross-project
private networking exists is inferred, not measured. No service in this walkthrough has
been observed running on Railway, so not one of the pass conditions above has been
confirmed against a live deployment.
