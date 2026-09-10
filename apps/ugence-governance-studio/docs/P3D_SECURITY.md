# P3D Security

Retains all P3C controls. What-if input is allowlisted to the nine bounded
operations with validated parameters (provider/residency/agent from pinned data,
numeric bounds) — no policy/URL/code input, no fixture mutation, no plan or
replay-record upload from local files. Amended by owner ruling BW-1 to BW-5
(`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md` §22, 2026-09-07), which
superseded the earlier "no arbitrary JSON" and "no fixture-upload input" sentences
for exactly one surface: the Bring Your Workflow screen accepts an operator-supplied
Ugence Workflow IR JSON document (`workflow_ir.v1` / `workflow_ir.v2`, pasted or read
from a local file in the browser), gated client-side and server-side to 1 MiB, depth
32, 200 nodes and 400 edges, refusing credential-shaped values and remote references,
sent only to the validate, adapt and compare-adaptations operations, never executed,
and never written to the scenario catalog. Since owner ruling BW-3A (§24 of the same
ADR, Bring Your Workflow phase 3A) the screen may also keep a document the server
validated as an unapproved `DRAFT`, through one v2 write: the server keeps its canonical
encoding and digest under the deployment's configured tenant (never the pasted text,
never a tenant the browser names), a claimed owner is recorded as `PRESENTED_UNPROVEN`,
and no route approves, compiles, publishes, exports or executes a draft; the store is
the same append-only, tenant-bound sqlite file posture as the seam-5, 8 and 9 records.
Everything else in this document stands. Strict boundary decoders validate public
API fields and fail closed rather than defaulting. Export is client-side download
of the API bundle only (no source/secrets/paths). No credentials, token storage,
unsafe HTML, eval, dynamic execution or model-provider SDK. The backend remains
authoritative.
