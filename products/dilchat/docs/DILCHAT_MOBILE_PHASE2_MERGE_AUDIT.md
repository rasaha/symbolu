# DilChat Mobile — Phase 2 Independent Merge-Readiness Audit

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com

This is an **independent** completion and merge-readiness audit of PR #1343, run
from a clean session that did not trust the PR description, prior report, test
counts, or CI summaries. Every material claim was re-verified against live state,
and every gate below was re-executed (or its unavailability recorded exactly).

## 1. Live state verified

| Fact | Value |
|---|---|
| Repository | `rasaha/symbolu` |
| Authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default SHA at audit | `ee36e34a` (advanced from the PR base `c89d699c`) |
| PR #1343 head (audited) | `0ddd2036` → new head after audit corrections |
| PR base | `c89d699c` |
| PR state | open, not draft, not merged; review threads: 0; requested changes: 0 |
| Default advancement | Orthogonal: commits `c89d699c..ee36e34a` are a `bindingslots_value_path_diagnosis` research directory + its own CI file — **no** DilChat mobile / mobile-CI / backend-contract / package overlap |

## 2. Defect found and fixed — red mandatory CI job

At the reported head the mandatory **`Mobile lint / typecheck / test / guards`**
CI job was **failing** (conclusion: failure), contradicting the "all runnable
gates green" claim. Root cause, reproduced locally on a cold Jest cache: the
first transform-heavy suite render (`authContext.isolation` sign-out) took
~8–10 s and crossed Jest's 5 s default per-test timeout; warm runs finished in
<0.5 s. The `signOut` path itself is bounded and cannot hang.

**Fix:** raised the default Jest timeout to 20 s in `jest.setup.ts` (documented
rationale inline). No behavior assertion changed. Result: **127/127 tests / 19
suites, exit 0** across repeated cold-cache runs.

## 3. Additional corrections

- **`src/deeplink/parse.ts`** — stale JSDoc examples showed `dilchat://invite?…`
  / `https://<host>/invite?…`, but the route allowlist requires the `invitation`
  segment (the `invite` segment is a real in-app screen and is deliberately
  **not** reachable from an external link). Corrected the examples; behavior was
  already correct and already covered by `deeplink.parse.test.ts` (which asserts
  the `invite` segment is refused as `not-an-invitation-route`).
- **`__tests__/deeplink.parse.test.ts`** — added 5 focused deep-link
  canonicalization regression tests: mixed-case trusted host, explicit-port
  stripping, duplicate-`token` first-wins, and trailing-segment / backslash
  route-escape resistance.

## 4. Gates re-executed in this environment

| Gate | Command | Result |
|---|---|---|
| Lint (0 warnings) | `npm run lint` | exit 0 |
| Strict TypeScript | `npm run typecheck` | exit 0 |
| Unit/component | `npm test` (cold cache ×3) | **127/127**, 19 suites, exit 0 |
| Endpoint guard | `npm run check:endpoint` | OK |
| Config guard | `npm run check:config` | OK |
| Contract-drift (real OpenAPI) | `check:contract` w/ generated `openapi.json` | OK — 13 routes, **no Guna/compatibility route** |
| Native Android manifest guard | `npm run check:native` | OK (scheme, minimal perms, backup off, no cleartext) |
| Expo config resolves | `expo config --json --full` | exit 0 |
| Metro export | `toolchain:export` | exit 0 — 2.28 MB Hermes bundle |
| Bundle safety scan | grep exported `.hbc` | clean (no leaked path / secret / `localhost:8080` / `dilchat.com`) |
| Live integration | `npm run test:integration` | **9/9** against fresh alembic-migrated **PostgreSQL 16.13** + real FastAPI via the production `HttpClient` |
| Integration fails-loud w/o backend | jest integration w/o `BASE` | exit 1 (fails, never skips) — verified |
| Secret / token-logging scan | CI grep + `console.*` scan | clean |
| AJV hoist | `require('ajv')` / eslint nested | top-level **8.20.0**, eslint nested **6.15.0**, `ajv/dist/compile/codegen` resolvable, `ajv-keywords@5.1.0` |
| Duplicate React / RN | `node_modules` scan | 0 duplicate copies |

CI job execution was additionally confirmed from GitHub Actions logs: the
integration job ran a **real PostgreSQL 16 service container**; the toolchain job
ran `expo prebuild` + Metro export + bundle scan + manifest guard; `expo-doctor`
is `continue-on-error` (informational) and reports 16/17 in CI (the one failure is
a benign SDK-version suggestion). Workflow permissions are least-privilege
(`contents: read`); there is no `pull_request_target`; mandatory shell steps use
`pipefail`.

## 5. Install-safe invitation link (app-not-installed journey) — INFRASTRUCTURE-GATED

- **Installed-app journey:** implemented and unit-tested — `dilchat://invitation`
  is versioned, allowlisted, fragment-safe, token-validated, consent-gated
  (never a direct accept), and single-accept.
- **App-not-installed journey:** **not validated** and cannot be validated in this
  environment. The mobile parser already supports HTTPS Universal/App Links via a
  configurable host allowlist (`extra.invitationLinkHosts`, empty by default,
  tested with `links.dilchat.app`), so the **code is ready**. What is missing is
  pure infrastructure, none of which exists or is verifiable here:
  - a verified, owned HTTPS host serving the invitation landing page;
  - `/.well-known/assetlinks.json` (Android App Links) with the app's **signing
    certificate SHA-256** — no production signing exists yet;
  - `apple-app-site-association` (iOS Universal Links) with the **Apple Team ID**;
  - a privacy-safe landing page (no third-party analytics, `Referrer-Policy:
    no-referrer`, no invitation capability in title/metadata).

  The product specs reference an owned domain (`dilchat.com` / `api.dilchat.com`)
  and a documented web `accept_url` pattern, but domain ownership, DNS, a
  deployment surface, and signing material could **not** be exercised or verified
  from this container. Per the audit's own rules this dependency is **documented,
  not fabricated**; no Universal/App Link success is claimed. This is a genuine
  unmet merge gate and is a primary reason the verdict remains
  validation-pending.

## 6. Scope confirmations (independently checked across all 41 changed files)

- **No** Friends Finder / Relationship Discovery / public discovery / candidate
  ranking.
- **No** secure chat or messaging.
- **No** AI Assist or conversation/preference learning.
- **No** Guna / Moon runtime enabled; the rule pack stays non-executable.
- **No** compatibility score exposed (the compatibility screen still reads "not
  available").
- **No** production deployment, credentials, secrets, hardcoded endpoint, or
  committed generated native (`android/` / `ios/`) directory.
- Synthetic accounts and synthetic birth data only; no private data in tests,
  logs, or artifacts.
- Changes are confined to `products/dilchat/mobile/**`, `products/dilchat/docs/**`,
  and the mobile CI workflow. No backend model / migration / authorization policy
  / API contract was changed.

## 7. Verdict

**`MOBILE_PHASE2_IMPLEMENTED_VALIDATION_PENDING`.**

Implementation is materially complete and every gate this environment can run is
green (after the CI-red fix above). The gates that remain **unexecuted** are
those that require hardware/infrastructure absent here and are merge-relevant:

- Android compiled (gradle) build — no Android SDK;
- Android emulator launch — no emulator;
- iOS simulator build + launch — Linux host, no macOS/Xcode (not claimed);
- physical two-device pilot — no devices;
- app-not-installed invitation-link fallback — no owned/verified host, landing
  page, association files, or signing material.

These are missing **evidence/infrastructure**, not phase-scope reductions, so the
verdict is **not** reinterpreted as a `MERGE_READY` limitation. The PR is **not**
merged.
