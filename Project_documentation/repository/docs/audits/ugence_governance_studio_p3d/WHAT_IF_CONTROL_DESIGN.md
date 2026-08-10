# Controlled What-If Design

**Screen:** `src/features/whatif/WhatIfScreen.tsx` ·
**Route:** `/scenarios/:id/what-if` · **Operation:** `scenario_what_if`.

## Intent

Let a reviewer apply a single **bounded, allowlisted** perturbation to a temporary
copy of a scenario and see the backend recompute the plan — baseline vs modified —
without ever mutating the real scenario or introducing free-form input.

## The nine allowlisted operations

Exactly these, offered in a `<select>` (no free-form entry):

`FORBID_PROVIDER`, `REQUIRE_RESIDENCY`, `TIGHTEN_COST_CEILING`,
`TIGHTEN_LATENCY_CEILING`, `REVOKE_AGENT_VERSION`, `EXPIRE_EVIDENCE`,
`TIGHTEN_PERMISSION_POLICY`, `TIGHTEN_PROVIDER_CONCENTRATION`, `REMOVE_CANDIDATE`.

The list is defined once (`WHAT_IF_OPERATIONS` in `src/api/types-p3d.ts`) and the
component test asserts the option values equal this array exactly. Any operation the
backend does not recognise is rejected server-side; the client sends only these
tokens plus validated parameters.

## Control rules

- **Copy semantics.** A notice (`data-testid="whatif-notice"`) states the
  perturbation runs against a *temporary copied scenario*; the original is never
  changed. Server-side the operation is applied to a copy.
- **Apply / Reset.** `whatif-apply` runs the operation and renders
  `whatif-result` (baseline state vs "Modified (temporary copy)"); `whatif-reset`
  discards the result and returns to baseline.
- **Bounded parameters only.** Parameters are typed and validated (e.g. a provider
  id chosen from the scenario's own registry, a numeric ceiling within range). No
  arbitrary JSON, policy, URL, code or fixture upload is accepted — the entire input
  surface is the operation enum plus its validated parameters.
- **NO_FEASIBLE_TEAM** is a legitimate modified outcome and is rendered honestly.

## Security note

This is the only mutating-looking control in the app, and it is deliberately
narrow: allowlisted verbs, validated params, server-side copy, decoder fail-closed
on the response. See `SECURITY_BOUNDARY.md`.
