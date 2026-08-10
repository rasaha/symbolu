# Governance Studio P3C — Live-State Audit

| Item | Value |
|------|-------|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `01fdf712cc7353155361dce5e0da16783c1d2017` |
| PR #1318 (P3B API) | merged (`f9bbda0d`) |
| PR #1320 (P3B packaging protections) | merged (`01fdf712`) |
| API distribution version | 0.1.0 |
| API contract | `governance_studio.api.v1` |
| OpenAPI sha256 | `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656` |
| AWC version | 0.2.1 |
| Compiler version | 0.2.0 |
| Platform-freeze digest | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |

The frontend mirrors the established `apps/console` stack (Vite + React + TypeScript +
Tailwind + zustand) rather than introducing Next.js, per the "inspect conventions first"
directive. It consumes the frozen `governance_studio.api.v1` contract over HTTP only.
