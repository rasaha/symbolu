# P3D Security

Retains all P3C controls. What-if input is allowlisted to the nine bounded
operations with validated parameters (provider/residency/agent from pinned data,
numeric bounds) — no arbitrary JSON/policy/URL/code, no fixture mutation, no plan
or replay-record upload from local files. Strict boundary decoders validate public
API fields and fail closed rather than defaulting. Export is client-side download
of the API bundle only (no source/secrets/paths). No credentials, token storage,
unsafe HTML, eval, dynamic execution or model-provider SDK. The backend remains
authoritative.
