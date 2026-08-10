# P3D Final Hardening — Live-State Audit

| Item | Value |
|------|-------|
| Live default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch tip | `340c29e1ca9b0457b4a79b810ec6f9d204894160` |
| PR #1323 state | open, not merged |
| PR #1323 base | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (`340c29e1`) |
| PR #1323 head branch | `claude/governance-studio-p3d-planning-explorer` |
| PR #1323 head commit (start) | `0beadfeadc348418a5913c7dfb46e86b2e84cf97` |
| PR #1323 checks | none reported (`total_count: 0`, pending) |
| PR #1323 mergeable_state | unstable |
| Later hardening PR exists? | no |
| Changed files vs base | 73 |
| Working tree | clean |

## Branch decision (mechanical)

PR #1323 is **open and unmerged** → check out its head branch
`claude/governance-studio-p3d-planning-explorer`, apply the hardening changes to
that same branch, push to PR #1323, do **not** open a second PR.

## Baseline (before hardening)

| Gate | Result |
|------|--------|
| type-check | clean |
| lint | clean (0 warnings) |
| vitest | 61 passed / 11 files |
| verify:openapi | in sync, sha256 `dc309eab…` |
| verify:boundary | PASS |
| verify:terminology | PASS |
| verify:contrast | PASS, 34 pairs, lowest 4.09:1 |
| audit:dependencies | PASS |
| Playwright E2E | 8 passed (4 P3C + 4 P3D) |
| platform-freeze | PASS, digest `d993093570…` |

## Frozen values (not re-baselined)

- OpenAPI sha256 `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656`
- Platform-freeze digest `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`
