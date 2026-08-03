# TAP live-state audit

Machine-readable: `tap_live_state.json`.

- **Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
- **Starting commit:** `a3dfb69ef952e72c4a9c8e77d92b558b30ffec76`
- **Working branch:** `claude/tap-provider-canonical-migration-42p9ip`
- **Python:** 3.11.15
- **Prerequisite PR #1296** (AI Hiring packaging): **MERGED** 2026-08-03T05:41:35Z into the default branch (verified live via GitHub; `packages/products/ai-hiring` present in the base).
- **No prior TAP packaging PR** exists (searched; earlier TAP PRs were the provider implementation, not this migration).
- **Working tree:** clean at audit start.

## Canonical packages (live versions)

| package | version |
|---|---|
| ugence-governance-contracts | 0.1.0 |
| ugence-governance-provider-framework | 0.1.0 |
| ugence-decision-authority | 1.0.0 |
| ugence-ai-hiring | present (distribution 0.1.0) |

## Baseline (pre-migration)

- **TAP implementation version:** 0.1.0 · **private distribution:** dgm-tap-provider 0.1.0
- **TAP test suite:** `tap_provider/tests` — **38 passed**
- **Private wheel:** `dgm_tap_provider-0.1.0-py3-none-any.whl` sha256 `b47890b0…62cd`
- **Existing runtime dependencies:** `decision-governance==1.0.0`, `dgm-provider-framework==0.1.0`
- **Public API exports (`tap_provider.api`):** 32 · snapshot hash `64d0ddea…4cd44f09`
- **Frozen API snapshot file** `platform/api-snapshots/tap_provider.api.json` sha256 `07d4aaaa…f42e4a`
- **Behavioral-capture hash:** `ed920e85…6fc6e3d0`
- **Platform-freeze substantive digest:** `d4ad77e1…a174a1a6` (PASS)
- **Baseline failures:** none.
