# Ugence Authority Plane

**The administrators' surface for authority acts, as its own deployable.** Step 3 of
`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §11, under rulings AP-1 to
AP-5; §18 confirms AP-3 as controlling. It is the third front end the platform has,
admitted by AP-2 as the one thing MA-3 refused for module administration: a surface for
the acts the Governance Studio is ruled never to perform.

    AT THIS STEP IT LOOKS AND DOES NOT TOUCH. NO WRITE IS SERVED BEFORE ENTERPRISE
    ISSUER VALIDATION.

## What it does

Four read-only screens over the four AP-5 reads the governed runtime worker serves
(`deployment/governed-runtime-worker/authority-plane-contract.json`):

| Screen | Read | What it shows |
|---|---|---|
| Grants | `GET /authority/grants?principal_id=` | the role grants one principal holds in the worker's tenant, active at the worker's clock |
| Holders | `GET /authority/holders?role=&scope=` | every principal holding one role in one scope, committees included |
| Committee | `GET /authority/committees/{committee_id}?role=&scope=` | one committee's counted members against its quorum |
| Grant events | `GET /authority/grants/{grant_id}/events` | a grant's append-only history: loaded, and possibly revoked |

Every answer is shown under an identity banner that repeats what the worker said:
the read was not authenticated; the decision proof the deployment can give
(`PRESENTED_UNPROVEN` until an identity port is composed, `IDP_AUTHENTICATED` then);
the adapter's issuer validation, which stays `IN_PROCESS_ISSUER_ONLY` until AI-C is
validated against a real issuer; and the directory's own provenance sentence, that a
grant is what an administrator loaded. An empty list, a typed refusal and an
unreachable worker are shown differently, on purpose.

## What it does not do, yet

Load a grant, revoke one, activate a constitution, issue a record. The worker
implements load and revoke behind its identity gate (§16, AW-2 to AW-5) but serves
neither: under AP-3, which the owner confirmed as controlling on 2026-09-07 (§18), no
write is served until the identity adapter has been validated end to end against at
least one real enterprise issuer, and the worker's in-process issuer evidence is
implementation and conformance evidence only. Until that validation is recorded this
app has no write control, and its client cannot name a write. Activate and issue act on
stores the worker does not compose (AW-2). At no step does this surface authorize,
clear or execute anything (AP-4). It sets no module composition and shows no module
registry: those stay with the deployment and the studio.

The app-side write screens that shipped briefly under AW-1 (a session token panel, a
Load grant screen, a revoke action) were removed from the built app when AW-1 was
reversed, so that the boundary verifier can prove the client names no write. They
remain in the repository's history at commit `c3b1ad8c` and can be restored, with the
manifest, once the worker's contract names the two writes served.

## Boundary

`security/approved-operations.json` names the four reads this app may consume and the
four writes it may not, and binds itself to the worker's committed contract by hash.
`scripts/verify-boundary.mjs` checks the manifest against that contract (an approved id
must be served; the forbidden set must equal the contract's unserved writes; the proof
header must be the contract's) and against the client's real call sites by method; only
`src/api/client.ts` may open an HTTP connection or name a write method.
`npm run verify:boundary` runs it; `tests/boundary.test.ts` proves it can fail.

## Run

```bash
# the worker, on its private TLS listener (see deployment/governed-runtime-worker)
cd apps/authority-plane
npm ci
npm run dev            # :3200, proxies /api -> https://127.0.0.1:8444 (WORKER_URL to override)
```

The plane must sit inside the worker's private segment (CR-3). It holds no credential
and forwards none; a read carries no header the worker reads.

In a built deployment nothing plays the dev proxy's part, so `server.mjs` does:

```bash
npm run build
PORT=8080 WORKER_URL=https://worker.internal:8444 npm start
```

It serves `dist` with the router's fallback and forwards `/api/*` to the worker, so
`VITE_WORKER_BASE_URL` stays unset and the client's `/api` default is same-origin — the
worker's origin never reaches a browser. It forwards GET only, only to a path
`security/approved-operations.json` approves, and forwards no request header, so it can
carry no credential and no write. It does not verify the worker's private certificate,
as the dev proxy does not; the private segment is what protects that hop (CR-3), so it
must not be given a public worker origin.

## Maturity

`REFERENCE_GRADE_SHADOW_ONLY`, like everything it reads from. No identity provider is
provisioned anywhere in this repository, and this app says so in its footer.
