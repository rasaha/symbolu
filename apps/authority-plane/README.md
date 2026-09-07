# Ugence Authority Plane

**The administrators' surface for authority acts, as its own deployable.** Steps 2 and 3
of `docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §11 under rulings AP-1 to
AP-5, and §16 under AW-1 to AW-5. It is the third front end the platform has, admitted
by AP-2 as the one thing MA-3 refused for module administration: a surface for the acts
the Governance Studio is ruled never to perform.

    IT READS, AND IT LOADS AND REVOKES ROLE GRANTS BEHIND THE IDENTITY GATE. NOTHING ELSE.

## What it does

Four read screens over the four AP-5 reads the governed runtime worker serves, and one
load screen plus a revoke action over the two writes it serves since 0.5.0
(`deployment/governed-runtime-worker/authority-plane-contract.json`):

| Screen | Operation | What it does |
|---|---|---|
| Grants | `GET /authority/grants?principal_id=` | the role grants one principal holds in the worker's tenant, active at the worker's clock; each row offers revoke |
| Holders | `GET /authority/holders?role=&scope=` | every principal holding one role in one scope, committees included; each row offers revoke |
| Committee | `GET /authority/committees/{committee_id}?role=&scope=` | one committee's counted members against its quorum |
| Grant events | `GET /authority/grants/{grant_id}/events` | a grant's append-only history, each event under the subject that did it; offers revoke |
| Load grant | `POST /authority/grants` | one time-bounded role grant from typed fields; the worker derives the id, so an identical replay is `ALREADY_LOADED` |
| revoke (on the three above) | `POST /authority/grants/{grant_id}/revoke` | appends a `REVOKED` event with a reason |

Every read answer is shown under an identity banner that repeats what the worker said:
the read was not authenticated; the decision proof the deployment can give; the
adapter's issuer validation, which stays `IN_PROCESS_ISSUER_ONLY` until the owner
validates it against a real issuer; and the directory's own provenance sentence, that a
grant is what an administrator loaded. An empty list, a typed refusal and an unreachable
worker are shown differently, on purpose.

## The token (AW-3)

The plane has no login of its own: the enterprise identity provider is the login. The
administrator presents the token it issued in the session panel at the top. It is held
in memory only, sent on writes only on the worker's proof header
(`X-Ugence-Approver-Proof`, the decision route's own), never on a read, and never
stored; clearing it or closing the tab is the end of it. Without a presented token every
write control is disabled and nothing is sent. With one, the worker records a write only
for a human subject of its tenant its adapter proved, and refuses everything else with a
typed reason (AW-5): no identity port, no proof, a proof that authenticates nobody, a
non-human actor, an expired proof, or a missing, ambiguous or foreign tenant claim.
Every recorded write shows the proven subject, its authentication reference and the
issuer-validation label, and says on its face that an in-process issuer proved it.

## What it does not do

Activate a constitution or issue a record: the plane's other two writes act on stores
the worker does not compose and are not served (AW-2); this app's client cannot name
them. At no step does this surface authorize, clear or execute anything (AP-4). It sets
no module composition and shows no module registry: those stay with the deployment and
the studio. It performs no login flow and refreshes no token.

## Boundary

`security/approved-operations.json` names the six operations this app may consume, the
four reads and the two served writes, and the two unserved writes it may not, and binds
itself to the worker's committed contract by hash. `scripts/verify-boundary.mjs` checks
the manifest against that contract (an approved id must be served; the forbidden set
must equal the contract's unserved writes; the proof header must be the contract's),
against the client's real call sites by method, and that only `src/api/client.ts` opens
an HTTP connection or names a write method. `npm run verify:boundary` runs it;
`tests/boundary.test.ts` proves it can fail.

## Run

```bash
# the worker, on its private TLS listener (see deployment/governed-runtime-worker)
cd apps/authority-plane
npm ci
npm run dev            # :3200, proxies /api -> https://127.0.0.1:8444 (WORKER_URL to override)
```

The plane must sit inside the worker's private segment (CR-3). It holds no credential
of its own; the token it forwards is the administrator's, for the session, on writes.

## Maturity

`REFERENCE_GRADE_SHADOW_ONLY`, like everything it reads from and writes to. No identity
provider is provisioned anywhere in this repository; the adapter is validated against an
in-process issuer only, and this app says so in its footer and on every recorded write.
