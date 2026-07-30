# Ugence Console API

Dedicated backend service for the unified AI Control Plane console. Consolidates
the governance functionality of the platform's Specialized-AI-Systems and
AI-Control-Plane layers behind one stable HTTP surface (excludes KVPro and the
Cloud Scaling Controller — the AI-Infrastructure modules that never govern).

It is intentionally separate from `symbolu.service.api_server` (the Symbol-U
research pipeline) and imports each platform module only through its **frozen
public API surface**.

## Run

```bash
pip install -e . 'fastapi[standard]' uvicorn pydantic
python -m ugence_console_api          # serves on :8090 (CONSOLE_API_PORT to override)
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Service + per-module availability |
| GET  | `/v1/modules` | The nine consolidated modules + maturity |
| GET  | `/v1/scenarios` | Sample K8s shadow workflows |
| POST | `/v1/gateway/minimize` | Context Minimization |
| POST | `/v1/assertions/evaluate` | Truth Assurance Platform |
| POST | `/v1/actions/authorize` | ActionGate (CER-bound) |
| POST | `/v1/actions/clear` | Autonomous Control Plane (operational safety) |
| POST | `/v1/governed-loop/shadow` | Full governed loop over a supplied request |
| POST | `/v1/governed-loop/scenario/{id}` | Full governed loop over a sample scenario |
| GET  | `/v1/audit/{correlation_id}` | Reconstruct the decision chain |

## The governed loop

```
Gateway   -> Context Minimization      what may enter
Verify    -> Truth Assurance Platform  is the assertion supported
Authorize -> ActionGate                may THIS exact action execute (CER-bound)
Clear     -> Autonomous Control Plane  is it operationally safe right now
Record    -> Audit                     reconstructable decision chain
```

Deployment mode governs consequence, not evaluation. In **shadow** the loop
evaluates and records but changes nothing; `would_execute` still reports what
enforcement would have done. Gates are non-compensatory.

## Tests

```bash
python -m pytest ugence_console_api/tests/ -q
```
