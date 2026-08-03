# Frontend Security

Env/build-configured API base URL (http(s) only, sanitized); no arbitrary URL
input; no credentials/tokens/secrets in the bundle; no token storage; no
`dangerouslySetInnerHTML`, `eval` or dynamic code execution; no model-provider
SDK; no external fetch beyond the configured API. Production source maps are OFF.
CSP for P3E: the app is self-contained (compiled Tailwind stylesheet, no inline
scripts); a strict `default-src 'self'` policy with `style-src 'self'` is the
intended P3E baseline. Authentication is not implemented in P3C.

## Blocking dependency-audit policy

The production dependency audit (`npm run audit:dependencies`,
`npm audit --omit=dev`) is a **blocking** CI gate: an unexcepted HIGH or CRITICAL
vulnerability in a production/runtime dependency fails the build. Moderate/low
findings are reported, not blocking. Dev-only findings are audited separately and
blocked only when they present a credible build/test/supply-chain/browser risk.

Exceptions live in `security/dependency-audit-exceptions.json` and are bounded:
every entry carries package, installed version, advisory id, severity, affected
range, dependency class, production-reachability, exploitability, compensating
control, reason, owner, expiry date and remediation target. Wildcard suppression,
undocumented fields, expired entries and critical-severity exceptions all fail CI.
The verifier is pure and unit-tested with captured audit JSON.
