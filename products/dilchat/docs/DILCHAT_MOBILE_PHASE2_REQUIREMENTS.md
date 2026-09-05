# DilChat Mobile — Phase 2 Requirements

**Workstream:** DilChat Mobile Phase 2 — device, native-build, lifecycle, privacy,
deep-link, accessibility, and closed-pilot hardening.
**Logical branch:** `dilchat-mobile-device-pilot` · **Working branch:**
`claude/dilchat-mobile-phase-2-qllgp7` (session-mandated `claude/…` name; same
workstream).
**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
at `c89d699c0b7b2a135b0aed14509a3bb373798413` (PR #1341 Mobile Phase 1 + PR #1342
AI Assist requirements docs, both merged).

## 1. Scope

Phase 2 **hardens the already-merged Phase 1 slice** (onboarding, authentication,
birth profile, invitation, consent, pairing, paired-state, unpairing). It adds:

1. **Toolchain reproducibility** — repair the Expo SDK 51 `ajv-keywords`/`ajv`
   resolution failure so `expo config`, `expo-doctor`, and Metro export run.
2. **Native project & build validation** — confirm managed-workflow (CNG) native
   generation, Android manifest, permissions, deep-link intent filters,
   secure-storage, and network-security posture.
3. **Deep-link invitation flow** — a versioned, allowlisted invitation link that
   preserves context through authentication and routes through the consent gate.
4. **App lifecycle & session resilience** — background/foreground, resume,
   token-expiry refresh (single-flight), account switch, secure-storage failure.
5. **Offline & interruption behavior** — bounded offline states; no blind retry of
   ambiguous accept/unpair; neutral recovery.
6. **Privacy hardening** — app-switcher shield, screen-capture policy, notification
   safety, device-only storage/backup exclusion, cross-account isolation.
7. **Accessibility & responsive UX** — labels, roles, announcements, focus,
   dynamic type, touch targets, color-independent errors.
8. **Closed-pilot harness** — device test plan, synthetic identities, checklists,
   defect rubric, result template (execution pending real devices).
9. **CI hardening** — add toolchain/export/deep-link/lifecycle gates.

## 2. Explicit exclusions (NOT in Phase 2)

No secure partner chat; no messaging; no Guna execution, Koota, Dosha, Parihara,
Moon-climate, compatibility scoring, or AI Assist route/value; no conversation
preference learning; no Moon receptivity; no notifications containing message
content; no payments; no production credentials, app-store release, or public
deployment. The Guna rule pack stays **non-executable / `RULE_PACK_BLOCKED`**.

## 3. Sequencing (binding)

**Mobile Phase 2 (this) → Phase 3 secure shared chat → Phase 4A–4D AI Assist.**
AI Assist must not be built before secure shared chat and its privacy boundaries
exist (`DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md`, DEC-048). Phase 2 implements
**none** of Phase 3/4 behavior.

## 4. Inherited contract (unchanged by Phase 2)

- **Mobile routes / backend contract:** 13 operations under `/v1/*`
  (auth register/login/refresh/logout/logout-all, users/me, birth-profiles,
  couples current/invitations/accept/unpair). No Guna/compatibility route exists
  or is added. Source of truth: `DILCHAT_MOBILE_API_CONTRACT_MAP.md`.
- **Token storage & refresh:** access + refresh tokens in `expo-secure-store`
  (Keychain/Keystore) pinned `WHEN_UNLOCKED_THIS_DEVICE_ONLY`; the backend rotates
  refresh tokens and revokes the whole session chain on reuse, so the client
  **single-flights** refresh (one shared refresh for concurrent 401s).
- **Invitation semantics:** `secrets.token_urlsafe(48)` opaque token (64 URL-safe
  chars); self-accept → 422; consumed → 409; invalid/expired → 404; already-paired
  → 409; accept is consent-gated and happens exactly once.
- **Unpair revocation:** unpair immediately revokes shared access for both
  partners (both observe 404 on the couple afterward).
- **Privacy boundary:** RLS-backed per-user isolation; the couple payload carries
  no partner private profile fields.

## 5. Acceptance criteria

Phase 2 is satisfied when, in the available environment:
`npm ci` deterministic · lint 0 · strict `tsc` 0 · unit/component tests green ·
contract/config/endpoint guards green · live FastAPI+PostgreSQL integration green ·
`expo config`/Metro export green · deep-link parser/route-allowlist/consent-gating/
token-cleanup tests green · lifecycle/offline/cross-account tests green · Android
manifest validated (minimal permissions, deep-link filter, no cleartext, backup
off) · privacy (app-switcher/storage/isolation) verified · accessibility labels/
roles/announcements verified · security/dependency review documented with per-
advisory disposition. Native **compiled builds** (Android gradle / iOS Xcode),
emulator/simulator runs, and **physical-device** execution are **deferred** where
the environment cannot run them, and reported as such — never fabricated.

See `DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md` for results and the exact
verdict, and `DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md` for deferrals.
