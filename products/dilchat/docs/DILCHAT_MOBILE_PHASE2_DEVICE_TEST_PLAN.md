# DilChat Mobile — Phase 2 Closed-Pilot Device Test Plan

A **bounded, closed** pilot using **synthetic accounts and synthetic birth data
only**. This is **not** a public pilot, production deployment, or app-store release.
Execution status in the current environment: **PENDING** — no physical devices,
Android emulator, or iOS simulator are available (Linux CI). The harness below is
ready to run on capable hardware.

## 1. Synthetic test identities (create fresh; never real people)

| Alias | Email | Password | Birth data (synthetic) |
|-------|-------|----------|------------------------|
| Partner A | `pilot-a+<runid>@dilchat.test` | random ≥12 chars | 1990-03-14, 08:30, EXACT, "Test City A", Asia/Kolkata, 12.9716, 77.5946 |
| Partner B | `pilot-b+<runid>@dilchat.test` | random ≥12 chars | 1992-07-02, 14:05, APPROXIMATE ±30m, "Test City B", America/New_York, 40.7128, -74.0060 |
| Switch acct C | `pilot-c+<runid>@dilchat.test` | random ≥12 chars | 1988-11-20, UNKNOWN time, "Test City C", Europe/London, 51.5074, -0.1278 |

`<runid>` = a per-pilot tag so runs don't collide. Use only `@dilchat.test`
addresses. **Never** enter a real person's birth details.

## 2. Test-data reset

- Point the app at a **disposable** backend DB (`DILCHAT_DATABASE_URL` → a scratch
  Postgres). Reset between runs: `DROP DATABASE … ; CREATE DATABASE …; alembic
  upgrade head` (see `scripts/run-integration.sh`). Never a production DB.
- On device: sign out (clears Keychain/Keystore + cache), or reinstall to clear all
  local state.
- Rotate synthetic accounts per run; do not reuse tokens across runs.

## 3. Two-device pilot journey (record pass/fail per step)

1. Install the app on **two separate devices** (A, B).
2. Register separate accounts (A, B).
3. Create separate **private** birth profiles.
4. On A: create an invitation; **share the deep link** (share sheet).
5. On B: **open the deep link**.
6. Authenticate on B if signed out; confirm the invitation **resumes** after auth.
7. On B: **explicitly consent** (toggle unchecked by default).
8. Pair.
9. Verify **both** devices show the paired state (status + scope slots only; no
   partner private fields).
10. **Expire an access token** (wait past access TTL / background the app) and
    resume — confirm silent refresh, no spurious sign-out, no refresh storm.
11. **Lose and restore network** mid-use — confirm neutral recovery, no crash, no
    false success.
12. **Terminate and relaunch** — confirm session restores (or clean sign-in), no
    infinite loading.
13. **Switch account** on one device (sign out A, sign in C) — confirm **no** A data
    (profile, couple, invitation, errors) is visible to C.
14. **Unpair** from either device.
15. Verify **immediate revocation on both** devices (couple gone for both).
16. **Reopen the old invitation link** — confirm it **cannot** restore the
    relationship (invalidated / consumed; token cleared).
17. Confirm no stale couple state reappears after the stale link.
18. **Reinstall** and validate expected session behavior (no improper session
    restore; clean state).

## 4. Checklists

### Android
- [ ] Installs; launches; portrait; app name "DilChat".
- [ ] `dilchat://invitation?v=1&token=…` opens the app (cold/foreground/background).
- [ ] Only `INTERNET` permission requested (Settings → App → Permissions).
- [ ] App-switcher (Recents) snapshot shows the **cover**, not birth/token/email.
- [ ] No cleartext to a production host (release build).
- [ ] Backup disabled (`adb shell bmgr` shows no app data / `allowBackup=false`).

### iOS
- [ ] Installs (simulator/TestFlight-style internal); launches; portrait.
- [ ] `dilchat://` URL scheme opens the app.
- [ ] App-switcher snapshot shows the cover.
- [ ] Keychain items not synced to iCloud (device-only).
- [ ] Permission usage strings present for anything prompted (none expected).

### Deep-link
- [ ] Valid link → consent (signed-in) / sign-in→resume (signed-out).
- [ ] Invalid / expired / consumed / self / malformed / unsupported-version link →
      neutral error, no crash, no route jump.
- [ ] Link to a non-invitation path (e.g. `dilchat://settings`) does nothing.
- [ ] Repeated taps / concurrent opens → one acceptance.

### Privacy
- [ ] No token/birth data in logs, share previews, or notification previews.
- [ ] Cross-account: B never sees A's data after switch.
- [ ] Stale link cannot restore an unpaired relationship.

### Lifecycle
- [ ] Background→foreground with expired token → silent refresh.
- [ ] Terminate→relaunch → correct session state.
- [ ] Network loss/restore → recovery, no false success.
- [ ] Clock/timezone change → no auth breakage.

### Accessibility
- [ ] VoiceOver/TalkBack reads labels, roles, and error/loading announcements.
- [ ] Focus order logical; focus moves to errors on validation failure.
- [ ] Largest dynamic-type setting → no clipping/overlap; landscape usable.
- [ ] Touch targets ≥ 44 px; one-handed reachable.
- [ ] Errors distinguishable without color.

## 5. Defect severity rubric

| Severity | Definition | Examples |
|---|---|---|
| **S1 Critical** | Data leak, auth bypass, cross-account leak, consent bypass, token exposure, corruption | B sees A's profile; deep link accepts without consent; token in a log |
| **S2 High** | Core journey broken; wrong pairing/unpair; refresh storm; stale authenticated screen | Unpair doesn't revoke on both; infinite loading; spurious sign-out |
| **S3 Medium** | Recoverable UX defect; poor a11y; missing announcement | No error announcement; small touch target |
| **S4 Low** | Cosmetic | Copy/layout nits |

S1/S2 block the pilot exit; S3/S4 are logged and triaged.

## 6. Pilot result template

```
Pilot run: <runid>            Date: <utc>            Tester: <name>
Devices: Android <model/OS>, iOS <model/OS>
Backend: <scratch db + api base>          Build: <commit sha>
Journey steps 1–18: [ pass/fail each, with notes ]
Checklists: Android [ ] iOS [ ] Deep-link [ ] Privacy [ ] Lifecycle [ ] A11y [ ]
Defects: [ id · severity · step · summary · evidence ref ]
Verdict: <MOBILE_PHASE2_* per exit rubric>
```

## 7. Evidence-capture guidance (privacy-preserving)

- Capture screenshots/screen-recordings **only** of non-sensitive screens, or
  **redact** birth values, invitation tokens/links, and email before sharing.
- **Never** paste a real invitation token or an access/refresh token into a bug
  report, log, or ticket. Reference by step number, not by value.
- Use synthetic identities only; do not capture any real person's data.
- Store evidence in the pilot's private folder; do not attach tokens to CI
  artifacts.
