# Version Consistency & Clean-Checkout Integrity (C5)

## Version consistency (`npm run verify:version`)

The frontend product version is **0.2.0**, kept distinct from the other component
versions. A latent inconsistency was found and fixed: `package-lock.json` was still
`0.1.0` while `package.json` was `0.2.0`.

| Artifact | Version | Result |
|----------|---------|--------|
| `package.json` version | 0.2.0 | ✅ |
| `package.json` name / private | `@ugence/governance-studio-frontend` / true | ✅ |
| `package-lock.json` root version | 0.1.0 → **0.2.0** (synced) | ✅ |
| `package-lock.json` packages[""] version | 0.1.0 → **0.2.0** (synced) | ✅ |
| README badge | `0.2.0` | ✅ |
| P3D audit `LIVE_STATE.json` `frontend.version_after` | 0.2.0 | ✅ |
| Stale 0.1.0 frontend references | 0 | ✅ |

Distinct versions kept unchanged: backend API distribution **0.1.0**, API contract
`governance_studio.api.v1`, AWC **0.2.1**, compiler **0.2.0**. The frontend version
is not surfaced in the running UI, so there is no in-app version string to reconcile.

## Tracked-source integrity (`npm run verify:tracked-sources`)

Walks every import in `src/` (resolving the `@/*` alias and relative specifiers) and
fails if any resolved application source file is not tracked by Git — the exact
failure mode P3D uncovered (`src/lib/` excluded by the root `lib/` ignore rule).

- src files scanned: 39 · resolved intra-repo imports: 38
- `src/lib` files tracked: **yes** (`config.ts`, `domain.ts`, `domain-p3d.ts`)
- Untracked imported sources: **0** → PASS

## Clean-checkout reproducibility (CI `clean-checkout-build`)

`git archive HEAD` of the committed frontend (+ the frozen contract) is expanded into
a fresh directory, then: assert `src/lib/{config,domain,domain-p3d}.ts` exist →
`npm ci` from the lockfile → `verify:tracked-sources` → `verify:version` →
`verify:api-boundary` → `type-check` → `build`. This proves no ignored or untracked
source file is required to build from a clean clone. Verified locally and wired as a
blocking CI job.

## Tests

`tests/version-and-tracked.test.ts` (11) covers `checkVersions` (stale package/lock,
private flag, README badge, audit disagreement) and the tracked-source resolver
(`@/` alias, relative, bare-package, untracked detection).
