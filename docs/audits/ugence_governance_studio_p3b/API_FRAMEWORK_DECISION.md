# API Framework Decision (P3B)

The repository has an existing FastAPI-style service (`ugence_console_api`,
`apps/console`). Consistent with that convention, P3B uses **FastAPI + Starlette
+ Uvicorn + pydantic v2**, pinned per repository practice
(`fastapi>=0.110`, `starlette>=0.36`, `uvicorn>=0.27`, `pydantic>=2`).

The application factory is explicit: `create_app(settings: ApiSettings | None) ->
FastAPI`. No large fixture is loaded at import time and there is no mutable global
state — the read-only catalog and stateless orchestration service are built once
and attached to `app.state`.
