# Governance Studio on Vercel (frontend + backend)

Public-Internet hosting, which **departs from the ratified P3E boundary**
("not a public-Internet SaaS deployment", `docs/p3e/LIMITATIONS.md`). The
departure and what it costs are recorded in
`docs/audits/ugence_governance_studio_p3e/VERCEL_PUBLIC_HOSTING_RATIFICATION.json`.
Read that first.

Synthetic demonstration data only · deterministic planning only · no permission
granting, runtime provisioning, agent execution or business-action authorization ·
not production certified.

## Shape

One ASGI application serves everything, and `vercel.json` rewrites **every** path
to it, so the SPA, its assets and the API all sit behind the same access gate. No
asset is served by the CDN ahead of authentication.

```
Browser ──HTTPS(Vercel edge)──▶ api/index.py ──▶ security headers
                                              ──▶ forwarded-proto guard  (HTTPS or 400)
                                              ──▶ trusted host
                                              ──▶ access gate            (Basic or 401)
                                              ──▶ origin guard, body cap
                                              ──▶ SPA · assets · /api/v1/*
```

## Vercel project settings

| Setting | Value |
|---|---|
| Root Directory | repository root (the function reads sources across the monorepo) |
| Build Command | from `vercel.json` — builds the frontend into `dist/` |
| Install Command | must resolve `api/requirements.txt`, **not** the repository-root `requirements.txt` |

### Environment variables

Set in the Vercel project, never committed:

| Variable | Value |
|---|---|
| `UGENCE_STUDIO_USERNAME` | operator username |
| `UGENCE_STUDIO_PASSWORD_HASH` | Argon2id hash (below) |
| `UGENCE_STUDIO_ALLOWED_HOSTS` | your deployment hostname(s), comma-separated |

Generate the hash offline — it never prints the password:

```bash
PYTHONPATH=deployment/governance-studio/src \
  python -m governance_studio_deployment.generate_password_hash
```

`UGENCE_STUDIO_TLS_TERMINATION=platform` and `UGENCE_STUDIO_TRUSTED_PROXY=1` are
set by the entrypoint; do not override them. Wildcards in `ALLOWED_HOSTS` are
rejected in production.

## Two things to know before you ship

**The brute-force cooldown does not hold here.** `FailureTracker` is in-memory and
serverless instances do not share it, so an attacker landing on a fresh instance
meets a zeroed counter. Use a high-entropy password: it is the effective defence.

**This deployment carries no container gate evidence.** All thirteen P3E-CTR gates
verify a built OCI image that Vercel does not run. They remain `NOT_EXECUTED`, and
none may be described as passed or waived because this is deployed.

## Verified, and not

Verified locally: the entrypoint builds; unauthenticated SPA and API requests get
401 and authenticated ones 200 with all four scenarios; a request without a
forwarded-protocol header gets 400; HSTS, CSP and nosniff are present; the full
deployment suite passes with the platform-TLS change.

**Not verified**: nothing here was deployed to or observed on Vercel. The project
configuration — build, function packaging, routing, dependency installation — is
untested against the platform, and the root-`requirements.txt` collision noted
above is the most likely first failure.
