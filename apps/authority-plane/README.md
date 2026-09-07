# Ugence Authority Plane

**The administrators' surface for authority acts, as its own deployable.** Step 3 of
`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §11, under rulings AP-1 to
AP-5. It is the third front end the platform has, admitted by AP-2 as the one thing
MA-3 refused for module administration: a surface for the acts the Governance Studio
is ruled never to perform.

    AT THIS STEP IT LOOKS AND DOES NOT TOUCH.

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

Load a grant, revoke one, activate a constitution, issue a record. Those are the
plane's four writes (AP-3) and they are not served by the worker and not nameable by
this app's client until the identity adapter is validated against a real enterprise
issuer and every write carries an issuer-authenticated subject. At no step does this
surface authorize, clear or execute anything (AP-4). It sets no module composition
and shows no module registry: those stay with the deployment and the studio.

## Boundary

`security/approved-operations.json` names the four reads this app may consume and the
four writes it may not, and binds itself to the worker's committed contract by hash.
`scripts/verify-boundary.mjs` checks the manifest against that contract and against
the client's real call sites; only `src/api/client.ts` may open an HTTP connection.
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

## Maturity

`REFERENCE_GRADE_SHADOW_ONLY`, like everything it reads from. No identity provider is
provisioned anywhere in this repository, and this app says so in its footer.
