# Frontend Stack Decision

The repository already establishes a frontend convention in `apps/console`:
**Vite + React 18 + TypeScript + Tailwind + zustand**. Per §7 ("inspect existing
repository frontend conventions first"), P3C mirrors that stack rather than
introducing Next.js.

| Library | Version | License | Purpose | Bundle | A11y | Reason |
|---|---|---|---|---|---|---|
| react / react-dom | ^18.3 | MIT | UI runtime | core | — | repo convention |
| vite | ^5.4 | MIT | build/dev/preview | dev-only | — | repo convention (console) |
| typescript | ^5.6 | Apache-2.0 | strict typing | dev-only | — | strict TS required |
| tailwindcss | ^3.4 | MIT | styling | ~4 kB gz css | — | repo convention |
| zustand | ^4.5 | MIT | selection/filter state | tiny | — | repo convention; minimal store |
| react-router-dom | ^6.28 | MIT | SPA routing + deep links | small | — | routes/deep links (§10) |
| @tanstack/react-query | ^5.62 | MIT | immutable response cache | moderate | — | per-scenario caching (§26) |
| lucide-react | ^0.462 | ISC | icons (paired with text) | tree-shaken | icons decorative + labels | repo convention (console) |
| clsx | ^2.1 | MIT | class composition | tiny | — | repo convention |

**Graph**: a custom deterministic layered-DAG SVG renderer (no heavy graph
library) plus a synchronized accessible node list — chosen for deterministic
layout, full accessibility control and minimal bundle, over React Flow.

**Testing**: Vitest + Testing Library + jsdom (component/unit), axe-core /
vitest-axe (a11y), Playwright (browser E2E against the real backend).

No LLM, chatbot framework or model-provider SDK is included.
