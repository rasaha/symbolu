# Ugence Console

Separate web app for the Ugence AI Control Plane — a unified governance console
over the nine consolidated modules. Talks to the `ugence_console_api` service.

Stack: Vite + React 18 + TypeScript + Tailwind + Zustand + lucide-react (mirrors
`frontend/`).

## Run

```bash
# 1. start the backend (from repo root)
python -m ugence_console_api           # :8090

# 2. start the console
cd apps/console
npm install
npm run dev                            # :3100, proxies /api -> :8090
```

Set `CONSOLE_API_URL` to point the dev proxy at a non-default backend.

## Served surface

The packaged `ugence-console-api` serves five routes and no more (ruling CP-3,
`docs/architecture/ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md`). This app calls
exactly those five (ruling MA-4,
`docs/architecture/ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md`): `/health`, the
scenario run, and the two audit reads. `/v1/modules` and `/v1/scenarios` are
withheld and are not called; the views that read them show a typed gap
(`CONSOLE_ROUTE_WITHHELD`) instead of an empty result.

## Views

- **Governed Loop** — enter a Kubernetes / infrastructure-agent scenario id and
  run it through the shadow governed loop; see each stage's verdict and the
  final (shadow) disposition. The scenario catalogue is a typed gap; an unknown
  id is the service's own 404.
- **Modules** — the service's per-engine availability probes from `/health`,
  under the keys it returns, plus its declared audit ceiling. The nine-module
  registry (name, layer, maturity, wiring) is a typed gap.
- **Audit** — reconstruct a decision chain by correlation id.
