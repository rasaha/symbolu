# Governance Studio API — Local Development (P3B)

```bash
pip install "pydantic>=2" fastapi uvicorn httpx pytest
export PYTHONPATH=apps/ugence-governance-studio/backend/src:\
packages/capabilities/agent-workforce-composer/src

python -m pytest apps/ugence-governance-studio/backend/tests
python -m ugence_governance_studio_api.cli serve   # 127.0.0.1:8000, docs at /docs
```

Config via `UGS_API_*` env vars (see `settings.py`): environment, log level,
CORS origins, request-size limit, docs toggle, rate-limit/auth seams, fixture
roots, build metadata. Domain behaviour never depends on env configuration —
policy/workflow behaviour comes only from pinned request/scenario artifacts.

The service defaults to host `127.0.0.1`, port `8000`, authentication disabled,
no external network use. It never binds to all interfaces unless explicitly
configured.
