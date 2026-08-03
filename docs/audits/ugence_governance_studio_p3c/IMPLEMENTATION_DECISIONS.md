# Implementation Decisions (P3C)

1. **Mirror repo stack** (Vite/React/TS/Tailwind/zustand) instead of Next.js —
   established convention, lighter static build, easier isolated verification.
2. **Generated client, view-model result types** — envelope typed from OpenAPI;
   the `Any` `result` field projected via documented view-models (the sole `any`
   exception), with a hash-pinned drift verifier.
3. **Custom deterministic SVG graph + accessible list** — determinism and full
   a11y control without a heavy graph library.
4. **Startup compatibility gate** — blocks the whole app on unsupported/unavailable
   backend; no partial rendering, no version guessing.
5. **Thin presentation only** — filtering/sorting never change domain results;
   the matrix reads API condition outcomes; no P3D operation is reachable.
6. **Honest maturity everywhere** — persistent banner distinguishing eligibility
   from selection/assignment/authorization/execution; synthetic-data labels on
   scenarios and evidence.
