# Local Frontend Development

```bash
cd apps/ugence-governance-studio/frontend
npm install
npm run generate:api
npm run dev            # 127.0.0.1:5173
```

Backend (separate terminal): `python -m ugence_governance_studio_api.cli serve`.
Set `VITE_API_BASE_URL` to point elsewhere (default `http://127.0.0.1:8000`). For
cross-origin dev, start the backend with
`UGS_API_CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173`.
