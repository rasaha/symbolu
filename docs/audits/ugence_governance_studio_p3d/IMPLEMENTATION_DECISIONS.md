# Implementation Decisions (P3D)

1. **Presentation view-models, not `any`.** The backend types the envelope `result`
   as `Any`. Rather than leak `any` into screens, P3D hand-writes view-models in
   `src/api/types-p3d.ts` and validates each response through a fail-closed decoder
   (`src/api/decoders.ts`). This mirrors the P3C exception and keeps the no-`any`
   rule intact for every canonical field.

2. **Decoders validate, never compute.** Decoders check required public fields and
   known enum values and throw `DecodeError` on anything unexpected. They contain no
   domain math — a missing replay `match` throws instead of defaulting to `false`, so
   the UI never fabricates a governance-relevant value.

3. **Reuse contrast-verified state tokens.** `src/lib/domain-p3d.ts` maps plan /
   selection / fallback / permission / diff states onto the existing
   contrast-verified semantic token set instead of introducing new colours, so P3D
   inherits WCAG compliance and only 13 additional pairs needed measuring.

4. **Card primitive forwards `data-testid`.** `Card` in `primitives.tsx` now spreads
   `...rest: HTMLAttributes<HTMLDivElement>` so screens can attach test ids
   (`non-greedy`, `no-feasible-team`, `proposal-notice`, …) that both the component
   suite and Playwright E2E rely on.

5. **What-if is an enum, not a form.** The nine operations are a single source-of-
   truth array offered via `<select>`; the component test asserts option-value
   equality. This makes the "bounded input" guarantee mechanically checkable.

6. **NO_FEASIBLE_TEAM everywhere is a domain state.** Composition, fallback and
   what-if all render it honestly at HTTP 200 with no fabricated assignment; no code
   path treats it as an error.

7. **One POST helper, explicit endpoints.** The client uses a small `postJson` helper
   and names each endpoint literally, keeping the consumed-operation set auditable
   against `P3D_API_INVENTORY.md`.

8. **Version bump 0.1.0 → 0.2.0.** A feature addition on a frozen contract; the
   contract sha256 and platform digest are unchanged.
