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

## One repository

Every service deploys from `rasaha/symbolu`. An earlier revision of this document split the
three front ends into `rasaha/demo`; that split is withdrawn.

| Service | Deploys from | Root directory |
|---|---|---|
| `studio-api` | `rasaha/symbolu` | `/` |
| `console-api` | `rasaha/symbolu` | `/` |
| `studio-web` | `rasaha/symbolu` | `apps/ugence-governance-studio/frontend` |
| `console-web` | `rasaha/symbolu` | `apps/console` |
| `authority-plane` | `rasaha/symbolu` | `apps/authority-plane` |
| `worker` | `rasaha/symbolu` | `/` (Dockerfile) |

Nothing about the repository's size argues for a split: Railway clones **14 MB** of tracked
files, and per-service root directories keep each build to its own subtree `[V]`. What did
break root-context builds was the repository root `.dockerignore`, and that is fixed —
`deploy/gke/Dockerfile.dockerignore` now carries the rules that belonged to one image, and
`verify_build_context.py --root-build` asserts on every push that the root build's declared
inputs stay in the context `[V]`.

Keeping one repository also keeps two proofs where the deployment is. The authority plane's
`verify:boundary` binds its manifest to the worker's committed contract by hash, and its
suite runs against that contract: both pass here `[V: boundary OK against contract sha256
a0227d16…; 11 tests passed]`. In a copy that omitted `deployment/` they could not run at all.

> **`tools/export_demo.py` and `demo-export-publish` are not part of deploying.**
> They generate a read-only snapshot of the three front ends into `rasaha/demo` — one
> successful run, 2026-09-09, source commit `40ff3818`, 141 files `[V]`. That repository is
> a generated artefact, not a deployment source: `commit-and-push` force-pushes over it, so
> anything committed there by hand is discarded on the next export, observed directly when
> the first export deleted the destination's `.github/workflows/blank.yml` `[V]`. Do not
> point a Railway service at it. Archiving it is the surest way to keep a service from
> being wired to a snapshot that will silently go stale.

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

**0.2 Connect GitHub and grant access to `rasaha/symbolu`.** Account Settings → Connected
Accounts. Every service comes from it. If the repository does not appear in the service
picker, this is why `[I]`.

**0.3 Use the repository's default branch.**

> An earlier revision of this document pinned every service to
> `claude/railway-hosting-setup-r5qk1s`, because the authority plane's `server.mjs` and its
> `start` script existed only there. That is no longer true — both are on the default
> branch, as are all seventeen packages in the 1.3 install list `[V]`. The pin is
> withdrawn: leave every service on the default branch, so a deploy follows what has been
> merged rather than a feature branch that may be deleted.

**0.4 Create one project, and put every service in it.** This is the constraint the whole
arrangement turns on. Railway's private network is scoped to a single project *and* a
single environment: a service's `*.railway.internal` name resolves only for services inside
that same project and environment, and from another project it does not resolve at all
`[I]`.


> **Can the authority plane reach the worker if they are in different projects? No.**
> There is no cross-project private networking to configure, and `WORKER_URL` has no valid
> value in that arrangement. If you must use two projects — separate billing, separate
> collaborator access — then `studio-web` and `console-web` may sit alone in one, because
> both reach their APIs over public HTTPS and are genuinely project-agnostic. The
> `authority-plane` must go in the *worker's* project.
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
> part 6.4's own pass condition. Decide that deliberately: it is then the permanent state,
> not a step you pass through.

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
  ./packages/integration/workflow-drafts \
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
Root Directory:  /                 # the repository root, as in 1.2 and for the same reason
Watch Paths:     packages/integration/console-api/**
                 packages/**
```

**2.3** Settings → Build → Build Command. Installing the distribution alone does **not**
work. `packages/integration/console-api/pyproject.toml:53-61` requires four first-party
packages — `ugence-context-minimization`, `ugence-governance-provider-framework`,
`ugence-actiongate-provider`, `ugence-tap-provider` — and none of them is published to
PyPI, so pip has no index to resolve them from. Supply their paths, and the path of the
one package they in turn need, exactly as 1.3 does for the studio:

```bash
pip install "fastapi>=0.100" "pydantic>=2" "uvicorn>=0.20" \
  ./packages/capabilities/context-minimization \
  ./packages/governance-contracts \
  ./packages/governance-provider-framework \
  ./packages/providers/actiongate \
  ./packages/providers/tap \
  ./packages/integration/console-api
```

Six local paths, dependency-first. `ugence-governance-contracts` is not a direct
dependency of this service; `ugence-context-minimization` needs it, and pip would look for
it on PyPI too `[V]`.

**2.4** Settings → Deploy → Start Command:

```bash
uvicorn ugence_console_api.app:create_app --factory --host 0.0.0.0 --port $PORT
```

Use uvicorn directly rather than `python -m ugence_console_api`: the module entry point
reads `CONSOLE_API_PORT` and defaults to 8090, ignoring Railway's `$PORT` `[V]`.

**2.5** No CORS variable pairs with this service. `create_app()` installs `CORSMiddleware`
with `allow_origins=["*"]`, because the console is served from a separate static host `[V]`.

**2.6** Generate a domain. Healthcheck path `/health`.

**2.7 Check.** `/health` answers 200 with `"status":"ok"` and a `modules` block reporting
`context_minimization`, `tap`, `actiongate` and `autonomous_control_plane` all
`"available": true`. A module reporting `false` there means its package did not install —
go back to 2.3.

> The service serves five routes and no more (CP-3), and its audit store is in-memory and
> lost on restart (CP-4). Both are declared, not incidental; the console shows a typed
> `CONSOLE_ROUTE_WITHHELD` gap for the two withheld routes rather than an empty result.

---

## Part 3 — `studio-web`

The studio's browser app. It needs `studio-api`'s URL *before* it builds.

**3.1** Add a service from `rasaha/symbolu`; rename it `studio-web`.

**3.2** Settings:

```
Repository:     rasaha/symbolu
Branch:         <the default branch>
Root Directory: apps/ugence-governance-studio/frontend
Build Command:  npm install --include=dev && npm run build
Start Command:  npx -y serve@14 -s dist -l $PORT
```

`-s` serves `index.html` for unknown paths, so the router survives a refresh.

**Not `npm ci`, on any Node service here.** Railway's builder runs its own `npm install`
before your build command, and mounts a build cache *inside* `node_modules`. `npm ci`
begins by deleting that directory and cannot remove a mount point, so it exits 240 on the
cache it did not create:

```
npm error code EBUSY
npm error syscall rmdir
npm error path /app/node_modules/.vite
```

`npm install` reconciles in place and leaves the mount alone. `--include=dev` is the other
half: the builder runs npm with `--omit=dev` set, and `vite` and `typescript` are
devDependencies of all three front ends, so without it the build fails with
`vite: not found`. Verified: this command installs and `npm run build` —
`tsc --noEmit && vite build` — produces a bundle under `NODE_ENV=production` `[V]`.

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

CORS is origin-based and indifferent to projects, but it is order-dependent: the value is
`studio-web`'s public domain, so part 3 must complete before this value exists. Do not add
the console's origin here; the console does not call this API.

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

**5.1** Add a service from `rasaha/symbolu`; rename it `console-web`.

**5.2** Settings:

```
Repository:     rasaha/symbolu
Branch:         <the default branch>
Root Directory: apps/console
Build Command:  npm install --include=dev && npm run build
Start Command:  npx -y serve@14 -s dist -l $PORT
```

Same command as parts 3 and 6 — and this service has a second, independent reason for it.
`apps/console` ships **no `package-lock.json`**; it is not a tracked file `[V]`, so `npm ci`
here would also fail with *"can only install with an existing package-lock.json"* before it
ever reached the cache-mount problem. `npm install --include=dev && npm run build`
completes, 1365 modules `[V]`.

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

Deploy before the worker; it runs on its own and says so. It belongs in the **worker's**
Railway project — see 0.4.

**6.1** Add a service from `rasaha/symbolu`; rename it `authority-plane`.

**6.2** Settings:

```
Repository:     rasaha/symbolu
Branch:         <the default branch>
Root Directory: apps/authority-plane
Build Command:  npm install --include=dev && npm run build
Start Command:  npm start
```

`npm start` runs the plane's own `server.mjs`: it serves the built app and proxies `/api`
to the worker server-side, so the worker's address never reaches a browser (CR-3).
`server.mjs`, the `start` script and `security/approved-operations.json` are all committed
here, and the app builds cleanly with the part 3 command `[V]`. `npm ci` fails here for the
same cache-mount reason; `server.mjs` itself needs no dependency at all, being Node
builtins only.

> **The plane's own checks run in this repository, and they belong in review rather than in
> a Railway build.** `npm run verify:boundary` passes here against the worker's committed
> contract (`sha256 a0227d16…`, four operations consumed) and `npm test` is 11 passed `[V]`
> — both work precisely because `deployment/governed-runtime-worker` is in the same tree.
> There is no reason to add them to the Railway build command: CI already runs them, and a
> deploy that fails on a governance check is a worse signal than a pull request that does.

**6.3** Variables:

```
NODE_VERSION=22
WORKER_URL=http://<the worker's RAILWAY_PRIVATE_DOMAIN>:8444
```

**Read that name; do not derive it from the service name.** Railway assigns the private
domain from the name the service had when it was created, and renaming the service
afterwards does not change it — a service renamed `studio-api` in this deployment kept
`ravishing-insight.railway.internal` `[V]`. Open the **worker's** Variables tab and copy
its `RAILWAY_PRIVATE_DOMAIN` verbatim. `worker.railway.internal` is correct only when the
worker was created under that name and never renamed.

Valid only if this service and the worker are in the same Railway project and environment.
`http:`, not `https:` — under
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

Deploy only to give the plane data.

**7.1** Project → New → Database → Add PostgreSQL. One service suffices: the worker needs
two DSNs that differ, not two servers. No public domain.

Railway's **Data** tab browses tables; it does not execute SQL, so `sysdb` cannot be
created there. It is created through the CLI, which tunnels to the private instance and
never exposes Postgres publicly:

```powershell
npm install -g @railway/cli        # add --allow-scripts=@railway/cli if npm blocks the install script
railway login
railway link                       # workspace → project → production → the Postgres service
railway connect Postgres           # opens psql over an SSH tunnel
```

At the `railway=#` prompt:

```sql
CREATE DATABASE sysdb;
SELECT datname FROM pg_database WHERE datname = 'sysdb';
```

`railway connect` shells out to `psql`, which must be installed locally — Node and npm do
not provide it (`winget install --id PostgreSQL.PostgreSQL.18 --exact`, then put its `bin`
on PATH). It also needs an SSH key registered with Railway; `ssh-keygen -t ed25519` and
answering **Yes** at the registration prompt is enough. A console code-page warning from
`psql` on Windows is informational.

Create `sysdb` **before** the worker's first deploy. A DSN naming a database that does not
exist passes `validate()` — which checks the prefix, not existence (`config.py:139-146`)
`[V]` — and fails later at connect, where the error looks nothing like a configuration
mistake.

**7.2** Add a service from `rasaha/symbolu`, then Settings:

```
Branch:           <the repository default branch>
Root Directory:   /
Dockerfile Path:  deployment/governed-runtime-worker/Dockerfile
```

Rename it `worker` — the name must match `WORKER_URL` from 6.3, and that matching only
means anything within one project and environment.

**7.3** Attach the volume from the **project canvas**, not the service Settings page:
right-click the `worker` tile → **Attach Volume** (or `Ctrl+K` → *Attach Volume*), mount
path `/var/lib/ugence-review`. The dialog closes without reopening; confirm a
`worker-volume` appears under the worker tile rather than attaching a second one. The three
SQLite stores live there (`composition.py:205-217`) `[V]`. A volume attaches to one
instance, which is what makes this deployment single-replica by construction `[I]`.

**This step is load-bearing and nothing enforces it `[G]`.** The Dockerfile declared that
path a volume until 2026-09-09; the declaration was removed because Railway rejects a
`VOLUME` instruction and the image could not be built with it. The image therefore no
longer states the requirement anywhere. A service deployed without this volume starts
cleanly, writes the authority directory and the two ledgers to the container filesystem,
and loses them on the next restart — with no error at any point. Attach the volume before
the first deploy, not after.

**7.4** Variables:

```
UGENCE_REVIEW_DEPLOYMENT_MODE=test
UGENCE_REVIEW_BIND_HOST=::
UGENCE_REVIEW_PORT=8444
UGENCE_REVIEW_DATA_DIR=/var/lib/ugence-review
UGENCE_REVIEW_TENANT_ID=tenant-demo
UGENCE_REVIEW_REQUIRED_ROLE=approver
UGENCE_REVIEW_DEFINITION_DIGEST=shadow-v1
```

Then the two DSNs, from **Postgres → Variables → `DATABASE_PRIVATE_URL`** (the private
address, not `DATABASE_URL`, which routes over the public proxy). Reveal it, and enter both
as literals — same credentials, same host, differing only in the database name:

```
UGENCE_REVIEW_APP_DATABASE_URL     …@<private-host>:5432/railway
UGENCE_REVIEW_SYSTEM_DATABASE_URL  …@<private-host>:5432/sysdb
```

**Literals, not `${{Postgres.DATABASE_PRIVATE_URL}}` `[V]`.** A Railway reference resolves
as one whole value, so it cannot be extended to swap `/railway` for `/sysdb`; the system
DSN has to be literal regardless. In the 2026-09-09 deployment the *application* reference
also resolved empty at runtime while appearing correct in the UI, and the worker reported
`UGENCE_REVIEW_APP_DATABASE_URL is required`. Literals fixed it. The cost is that a
credential rotation no longer propagates — update both DSNs by hand when Postgres rotates.

Never paste a resolved DSN into a screenshot, ticket or chat: it carries the password.
The worker's own startup line prints it as `postgresql://<redacted>@…` `[V]`.

**Do not set `RAILWAY_RUN_UID=0`, and remove it if an earlier deployment set it.** Railway mounts the volume owned by root, and the
image's build-time `chown` is discarded by the mount, so a container that has already
dropped to uid 10001 dies on `sqlite3.OperationalError: unable to open database file`
`[V]`. The platform's escape hatch is to run the whole worker as root, which fixes the
write and discards the non-root posture with it.

The image handles it instead: it carries no `USER` instruction, starts as root, and
`entrypoint.py` chowns the data directory, drops groups, gid and uid to `10001:10001`,
verifies that root is unreachable, and only then exec's the worker. A drop that does not
verify, or a directory root cannot prepare, exits non-zero rather than running the worker
as root `[V]`. Started unprivileged, it changes nothing and exec's directly.

Removing it is also the only way the drop gets tested: with the variable set the container
runs as root anyway, so the entrypoint's work is invisible. Confirm it in the deploy log,
immediately before the startup line:

```
entrypoint: prepared /var/lib/ugence-review and dropped to uid 10001
```

Check the spelling of `UGENCE_REVIEW_DEFINITION_DIGEST` before deploying; a typo surfaces
only as `WORKER_CONFIG_INVALID` on the next boot.

`WorkerConfig.validate()` returns empty for exactly these values in `test` mode `[V]`: the
bind check, the TLS requirement and the identity requirement apply in production mode only
(`config.py:158-179`).

`DEFINITION_DIGEST` is a free-form required label naming the compiled definition this
worker runs, not a value you compute: `validate()` asks only that it be non-empty
(`config.py:152`), and the worker README's own run line uses `shadow-v1`
(`deployment/governed-runtime-worker/README.md:132`) `[V]`.

**7.5** Deploy, and never generate a domain for it.

Worker pass condition, on stderr — which Railway paints red; that colour is not an error
`[V]` (`server.py:31-36` writes both lines with `sys.stderr.write`):

```
governed-runtime-worker 0.5.1 REFERENCE_GRADE_SHADOW_ONLY enforcement_enabled=False
mode=test listener=http://:::8444 config={…}
WARNING: UGENCE_REVIEW_DEPLOYMENT_MODE=test (loopback development mode)
```

Leave that warning visible: it is the label this deployment runs under. In the redacted
config that follows, check `app_database_url` ends `/railway`, `system_database_url` ends
`/sysdb`, `data_dir` is `/var/lib/ugence-review`, and `port` is `8444`.

**7.6** Set `WORKER_URL` on the plane per 6.3, then **apply the staged change**. A
GitHub-triggered plane deploy can succeed while an edited variable is still staged; if the
canvas shows *Apply 1 change*, the plane is running without it.

**7.7 Plane pass condition — and it needs no data.** `decision_identity_proof` and
`issuer_validation` are envelope fields computed once at router construction from
`identity_port_configured`, not stored records (`authority_reads.py:117-131`) `[V]`, and
the plane renders `IdentityBanner` on any 200 (`GrantsView.tsx:45-47`) `[V]`. On **Grants**,
enter any typed token — non-empty, ≤256 characters, NFC, no whitespace (`_is_typed`,
`authority_reads.py:56-62`) — and read:

```
read_authenticated: false
decision proof: PRESENTED_UNPROVEN
issuer validation: IN_PROCESS_ISSUER_ONLY
REFERENCE_GRADE_SHADOW_ONLY          … holds 0 active grants
```

Zero grants is a successful read, not a refusal.

**Two of the four screens, not four.** On an empty directory:

| Screen | Empty-store result | Banner |
|---|---|---|
| Grants (`principal_id`) | 200, `grant_count: 0` | shown |
| Holders (`role`, `scope`) | 200, `holder_count: 0` | shown |
| Committee | 404 `NOT_FOUND` (`authority_reads.py:176-179`) | refusal notice instead |
| Grant events | 404 `NOT_FOUND` (`authority_reads.py:190-192`) | refusal notice instead |

Committee and Grant events returning 404 for a token nothing holds is correct behaviour,
not broken connectivity. On Holders, `role` is `approver` — your own
`UGENCE_REVIEW_REQUIRED_ROLE`; `scope` and `principal_id` have no repository-backed value,
and on an empty directory any typed token returns the same count of zero.

> **No seed path exists, and none is needed `[V]`.** The four write operations are in the
> plane's `forbidden_operation_ids`; `authority_writes.py` is implemented on the worker but
> not served until the identity adapter is validated against a real enterprise issuer
> (AP-3); and outside the worker the only callers of `SqliteAuthorityDirectory` are the
> library and its tests — no CLI, no console script, no fixture loader. A deployed worker's
> directory cannot be populated by any commissioned means. Writing to the SQLite file
> directly would bypass the governance path this deployment exists to demonstrate.

Railway's private DNS name resolves only inside the environment and requires the listener
to accept connections on the container's IPv6 interface. Measured on 2026-09-09: the plane
reached the worker at `worker.railway.internal:8444` over plain HTTP and all four reads
answered, with the worker bound to `:::8444` `[V]`. The name is **not** derived from the
service's current name — it is assigned at creation and survives a rename `[V]` — so read
each service's `RAILWAY_PRIVATE_DOMAIN` from its Variables tab. RW-1's own probe remains
unrun and its record still carries the `[G]`; this walkthrough is not that record `[I]`.

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

## Part 8 — Once it is running

Four properties of the running deployment that no step above establishes, and that are
easier to learn here than from an outage.

**8.1 Every service redeploys when the default branch moves.** Each service tracks a
branch, so merging *anything* — a documentation-only pull request included — triggers a
rebuild of every service whose Watch Paths match, and of every service with none set. The
parts above set Watch Paths for exactly this reason; a service without them rebuilds on
every merge `[V]`, observed repeatedly on 2026-09-09. The consequences are worth stating:
a merge is a deploy, a red build on an unrelated service will follow a docs merge, and two
merges in quick succession can leave a service building the older commit. Check the
Deployments tab after merging, not only the pull request.

**8.2 Prove the volume actually persists, once.** The worker's three SQLite stores are the
only state the platform does not manage for you, and nothing above has restarted the
service. Do it deliberately while nothing depends on it: note what a read returns, use
**Redeploy** on the worker, and read again. If the answer changed, the volume is not
mounted where `UGENCE_REVIEW_DATA_DIR` points and the stores are being written to the
container filesystem — the failure 7.3 warns about, which is silent until exactly this
moment `[G]`. This has not been exercised on any deployment.

The check, precisely, because a vague version of it proves nothing:

1. On the plane's **Grants** tab, read a typed token and note the `as_of` timestamp and the
   grant count.
2. Worker → **Deployments** → **Redeploy**. Wait for Online and for the startup banner.
3. Read the **same** token again.

**Pass:** the read answers, and the identity envelope and count are unchanged. That is the
worker reopening the same three SQLite files on the same volume.

**Fail:** the reads stop answering, or the worker restarts with a fresh directory. On an
empty directory both outcomes look identical to a passing read — every typed token returns
zero either way — so this check is only conclusive once something has been written. Until
authority records can be loaded (no commissioned seed path exists, see 7.7), it
distinguishes *the stores reopen* from *the worker cannot start*, and no more. Say that
rather than claiming durability from a zero that would have been zero regardless `[G]`.

**8.3 Back up the two stores that matter, and know they differ.** Postgres has a
**Backups** tab; the volume is snapshotted separately, if at all. The audit ledger and the
authority directory live on the volume, not in Postgres, so a Postgres backup does not
capture them. Under RW-6 this deployment is single-instance and reference-grade: it has no
replication, and a lost volume is a lost decision record. Do not present it as durable
governance evidence.

**8.4 Literal DSNs do not follow a credential rotation.** 7.4 enters both database URLs as
literals because references resolve as one whole value. If Railway rotates the Postgres
credentials, the worker keeps the old ones and fails at connect — with a message that
looks nothing like a rotation. Update both variables by hand, keeping `/railway` and
`/sysdb` distinct.

> **Turning it off.** Deleting a service does not delete its volume, and deleting a
> Postgres service does not delete its backups; both continue to be billed. Remove the
> volume from the canvas explicitly. Removing only the public domain of `studio-web`,
> `console-web` or `authority-plane` stops the demo being reachable while leaving the
> services and their state intact — the cheaper reversible step when a demo is over.

---

## The four variables, in one place

| Variable | Set on | Value | When it takes effect |
|---|---|---|---|
| `VITE_API_BASE_URL` | `studio-web` | `https://<studio-api>.up.railway.app` | build time — redeploy |
| `VITE_CONSOLE_API_URL` | `console-web` | `https://<console-api>.up.railway.app` | build time — redeploy |
| `UGS_API_CORS_ALLOWED_ORIGINS` | `studio-api` | `https://<studio-web>.up.railway.app` | restart |
| `WORKER_URL` | `authority-plane` | `http://<worker's RAILWAY_PRIVATE_DOMAIN>:8444` | restart |

The first two are public HTTPS domains compiled into a browser bundle. The last is a
private address that must never be public, and resolves only within one project and
environment.

## If something fails

| What you see | What it is | Fix |
|---|---|---|
| `ModuleNotFoundError: ugence_agent_runtime` | Incomplete install list; the v2 surface imports it at module load | 1.3 |
| `studio-api` serves an unrelated API | Start command blank, so the root `Procfile` won | 1.4 |
| `console-api` answers on 8090, not `$PORT` | `python -m ugence_console_api` used instead of the uvicorn line | 2.4 |
| `No matching distribution found for ugence-context-minimization` | `console-api` built with the distribution path alone; its first-party dependencies are not on PyPI | 2.3 |
| "API is not compatible / Detected contract: unknown" | CORS origin mismatch, not a version mismatch | 4.1 |
| Studio or console still calls the old API after a variable change | `VITE_*` is compiled into the bundle | redeploy that service |
| `npm ci` fails: `EBUSY … rmdir '/app/node_modules/.vite'`, exit 240 | `npm ci` deletes `node_modules`, which holds Railway's build cache mount | 3.2 |
| `vite: not found` during the build | `--include=dev` omitted; the builder runs npm with `--omit=dev` | 3.2 |
| `npm ci` fails: *can only install with an existing package-lock.json* | `console-web`; that app ships no lockfile | 5.2 |
| Plane cannot resolve the worker's host name | The worker's private domain was assumed from its service name instead of read from `RAILWAY_PRIVATE_DOMAIN` | 6.3 |
| Console fetches fail against the deployed origin | `VITE_CONSOLE_API_URL` unset, so the client fell back to a relative `/api` | 5.3 |
| Plane reports the worker unreachable | Correct until part 7; after it, check the service is named `worker` — **or** the plane and worker are in different Railway projects, in which case no configuration fixes it | 0.4, 6.3, 7.2 |
| Worker exits at boot printing a list | It reports every reason at once; usually the two DSNs are identical | 7.4 |
| `WORKER_CONFIG_INVALID: … APP_DATABASE_URL is required` with the variable visibly set | A `${{Postgres.…}}` reference resolved empty at runtime | 7.4 — use literals |
| `WORKER_CONFIG_INVALID: … DEFINITION_DIGEST is required` | The variable name is misspelled | 7.4 |
| `sqlite3.OperationalError: unable to open database file` | The entrypoint did not run, or `UGENCE_REVIEW_DATA_DIR` is not the mounted path | 7.4 — expect the `dropped to uid 10001` line |
| `ENTRYPOINT_REFUSED: …` and the container exits 1 | Root could not prepare the data directory, or the privilege drop did not verify | 7.4 — the worker is never run as root |
| Build fails: `docker VOLUME … is not supported, use Railway Volumes` | A `VOLUME` instruction reached the Dockerfile again | it was removed in `bba9d118`; do not restore it |
| No Volumes control in the worker's Settings | Volumes are attached from the project canvas | 7.3 |
| `CREATE DATABASE sysdb;` only filters a table list | The Data tab browses tables and runs no SQL | 7.1 — `railway connect Postgres` |
| `psql must be installed to continue` | `railway connect` shells out to psql; npm does not supply it | 7.1 |
| Plane still reports the worker unreachable after setting `WORKER_URL` | The variable edit is staged, not applied | 7.6 |
| Committee or Grant events answers 404 on the smoke test | Nothing holds that token; a typed refusal carries no banner | 7.7 |
| Worker logs appear red | Both startup lines go to stderr by design | 7.5 |
| A service builds from `rasaha/demo` | That repository is a generated snapshot, not a deployment source | the note in *One repository* |

## Verification of this document

Every part of this walkthrough was run against **this** repository, outside Railway.

On 2026-09-08: the 1.3 install list installs cleanly into a clean virtual environment and
the 1.4 start command serves v1 and v2 with `/health`, `/ready` and `/version` answering
200; the 3.4 failure was reproduced with a mismatched CORS origin and cleared by 4.1, after
which the scenario catalog loaded with no console errors; the plane's four reads answered
through `server.mjs` over a self-signed TLS listener carrying the worker's real
`build_authority_reads` router, with `POST` refused 405; and `WorkerConfig.validate()`
returned empty for the 7.4 variables.

Re-run on 2026-09-09 against the default branch, after the split was withdrawn `[V]`:

- `authority-plane`'s own checks pass in this tree — `npm run verify:boundary` reports 4
  operations consumed against contract `sha256 a0227d16…`, and `npm test` is 11 passed.
  Neither could run in a copy that omitted `deployment/governed-runtime-worker`.
- All three front ends build with `npm install --include=dev && npm run build` under
  `NODE_ENV=production`: `studio-web` 1859 modules with
  `studio-api-production-851c.up.railway.app` compiled into the bundle, `authority-plane`
  and `console-web` likewise. `apps/console` ships no tracked `package-lock.json`.
- `ugence_console_api.__main__` reads `CONSOLE_API_PORT` and ignores `$PORT`;
  `create_app()` sets `allow_origins=["*"]`.
- `server.mjs` forwards `GET` only, to the four approved paths, forwards no request header,
  and sets `rejectUnauthorized: false`.
- `verify_build_context.py --root-build` passes: all three Dockerfiles resolve every COPY
  source, and the root build's five declared inputs are in the context.

**Corrected twice on 2026-09-09 by Railway builds `[V]`.** Two steps carried `[V]` on
local evidence that no builder had ever tested. Railway rejected both.

*Part 3, and by inheritance part 6.* The build command was `npm ci && npm run build`.
Railway's builder runs its own `npm install` first and mounts a build cache inside
`node_modules`; `npm ci` deletes that directory and cannot remove a mount point, so the
deploy died on `EBUSY … rmdir '/app/node_modules/.vite'`, exit 240. The document's own
evidence line said `npm ci` "resolves against the committed `package-lock.json`", which was
true and beside the point: the lockfile was never what failed. All three front ends now use
`npm install --include=dev && npm run build`, which additionally survives the builder's
`--omit=dev`, and which builds all three here under `NODE_ENV=production` `[V]`.

*Part 6.3 and the private-networking notes.* `WORKER_URL` was written as
`http://worker.railway.internal:8444` on the assumption that a service's private domain
follows its name. It does not: this deployment's `studio-api` carries
`ravishing-insight.railway.internal`, the name it was created under, and the rename did not
propagate `[V]`. Every private address must now be read from the target service's
`RAILWAY_PRIVATE_DOMAIN`.

**Corrected on 2026-09-09 by a Railway build `[V]`.** Part 2 previously gave
`pip install ./packages/integration/console-api` as the whole build command and labelled it
`[V]`. That label was wrong: it rested on the distribution's own metadata, never on an
install. Railway's builder rejected it —
`ERROR: No matching distribution found for ugence-context-minimization>=0.1.0` — because
the four first-party dependencies at
`packages/integration/console-api/pyproject.toml:53-61` are not on PyPI. The six-path
command now in 2.3 installs into a clean virtual environment outside this repository, and
`uvicorn ugence_console_api.app:create_app --factory` then answers `/health` 200 with all
four modules `"available": true` `[V]`. A build succeeding locally is what the old step
lacked, and what the studio's own step in 1.3 always had.

**Part 7 completed on Railway, 2026-09-09 `[V]`, reported by the owner.** The worker image
was built for the first time anywhere (`sha256:06afb2f5…`, 80.3 MB) and reached Online after
three defects this walkthrough had never been able to surface: the root `.dockerignore`
exclusion, Railway's rejection of the `VOLUME` instruction, and a bare `postgresql://` DSN
resolving to a psycopg2 dialect the image does not ship (fixed in `bba9d118` and `6c3f36e5`).
The plane then read all four operations across Railway's private network. Every claim in 7.5
and 7.7 above is transcribed from that deployment rather than inferred.

**Observed on Railway `[I]`, reported by the owner.** `studio-api`, `console-api` and the
root `web` service are Online; `console-api` came up on the corrected part 2 command.
`studio-api` serves `studio-api-production-851c.up.railway.app` on port 8080. `studio-web`
has a domain but has not yet completed a build. Parts 4 through 7 have not been reached.

**A pattern worth stating.** Both corrections above were local-evidence failures of the
same kind: a command that builds in this repository does not thereby build on Railway's
builder, whose install phase, cache mounts and `--omit=dev` default are part of the
environment the command runs in. A step describing a build deserves `[V]` only once a
builder has accepted it; until then it is `[I]`.

**Still not verified `[G]`.** Every part of this walkthrough has now been run on Railway,
so what remains unproven is narrower and worth naming precisely:

- **0.4's cross-project claim.** Every service here sits in one project, so the assertion
  that private networking does not cross projects was never exercised — it stays `[I]`.
- **RW-1's own probe.** The plane reaching the worker is evidence about this deployment,
  not the ratified network proof RW-1 asks for; that record keeps its `[G]`.
- **The container gate set.** An image now exists, but `CONTAINER_GATE_SET.json` still
  reads `execution_state: NOT_EXECUTED`: the gates run against a mirrored base image whose
  coordinates are null. A Railway build is not that pipeline (RW-2).
- **The entrypoint on Railway.** The privilege drop is verified in this repository — a
  root-owned directory is chowned, the process reaches uid 10001, and a SQLite store opens
  there `[V]`. On 2026-09-10 the owner removed `RAILWAY_RUN_UID=0` from the worker and
  redeployed `[I]`, which is the deploy that actually exercises the drop: with the variable
  set the container was root regardless and the entrypoint's work went untested. What
  raises this to `[V]` is one line from that deployment's log, immediately above the
  startup banner:

  ```
  entrypoint: prepared /var/lib/ugence-review and dropped to uid 10001
  ```

  Until that line is on the record, the deployment is reported and not observed. A failure
  here is loud rather than silent: the entrypoint exits non-zero with
  `ENTRYPOINT_REFUSED: …` rather than running the worker as root `[V]`.
- **Durability.** No restart, redeploy or volume-detach has been exercised against the
  three SQLite stores; that they survive is designed, not observed.

Railway's UI wording and per-service repository selection remain vendor documentation `[I]`
and may drift.
