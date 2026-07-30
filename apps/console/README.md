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

## Views

- **Governed Loop** — pick a Kubernetes / infrastructure-agent scenario and run
  it through the shadow governed loop; see each stage's verdict and the final
  (shadow) disposition.
- **Modules** — the nine modules by layer, with maturity, wiring, and live
  availability.
- **Audit** — reconstruct a decision chain by correlation id.
