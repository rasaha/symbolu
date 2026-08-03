# Governance Studio API — OpenAPI Freeze (P3B)

The OpenAPI document is generated deterministically (host-free, timestamp-free,
stable operation IDs and model names) and committed at
`apps/ugence-governance-studio/contracts/openapi.json`.

```bash
python backend/scripts/verify_openapi.py          # verify (fails on drift)
python backend/scripts/verify_openapi.py --write    # regenerate
```

The public Python API surface is frozen at
`backend/artifacts/public_api.json` and verified by
`backend/scripts/public_api_snapshot.py`. Both are enforced in CI.
