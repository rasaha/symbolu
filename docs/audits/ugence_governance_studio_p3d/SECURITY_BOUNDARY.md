# Security Boundary (P3D)

P3D widens the *read* surface and adds one *controlled write-shaped* operation
(what-if). The security posture is unchanged in spirit from P3C: the browser is a
thin presentation client over a frozen contract, holds no secrets, and performs no
authorization.

## Input surface — fully bounded

- **No arbitrary input.** The app accepts no free-form JSON, policy, URL, code, or
  fixture upload anywhere. Scenario ids come from the API's own `list_scenarios`.
- **What-if is allowlisted.** The only mutating-looking control sends one of nine
  fixed operation tokens (`WHAT_IF_OPERATIONS`) plus typed, validated parameters
  drawn from the scenario's own data. Unknown operations are rejected server-side.
  The operation runs against a server-side **temporary copy**; the real scenario is
  never mutated.
- **No dynamic execution.** No `eval`, no `Function`, no `dangerouslySetInnerHTML`,
  no runtime code loading. Export is a download of the exact bytes the API returns.

## Fail-closed decoding

Every P3D response's untyped envelope `result` is validated by a fail-closed decoder
(`src/api/decoders.ts`): `decodeRanking / decodePlan / decodeExplainPlan /
decodeReplay / decodeCompare / decodeWhatIf`. Missing required public fields, an
unknown plan state, or a non-object payload throw `DecodeError` rather than
rendering a fabricated value. Decoders perform no domain calculation — e.g. a
missing replay `match` throws instead of assuming `false`.

## No authorization / provisioning

The Studio proposes permission scopes; it never grants, provisions, activates or
authorizes anything, and it stores no credentials or tokens. Enforced by
`scripts/verify-terminology.mjs` and `tests/permission-scope.test.tsx`.

## Dependency direction & imports

`scripts/verify-boundary.mjs` bans any import of AWC, the compiler, or backend
source, and any model-provider SDK. `BANNED_API_PATHS` is now empty because P3D
legitimately consumes the ranking/plan/replay/compare/what-if/export endpoints, but
the import bans remain. See `DEPENDENCY_DIRECTION.md`.

## Supply chain

Production dependencies are audited with `npm audit --omit=dev` under a blocking
policy (`production-dependency-audit`); structured, expiring exceptions only.
