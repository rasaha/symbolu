# P1 Contract Inventory (baseline preserved by P2)

The exact P1 surfaces P2 must preserve. Machine-readable form in
`P1_CONTRACT_INVENTORY.json`.

## Public API
- Single supported surface: `import ugence_policy_workflow_compiler.api as api`.
- **71 frozen names** before P2 (`artifacts/public_api.json` `count: 71`); **101**
  after (30 additive P2 names). Every P1 name is preserved (asserted by
  `test_all_p1_public_names_preserved` and the packaging public-API test).
- Entry point: `compile_policy_pack(pack, approval=None, *, registry=None, require_approval=True) -> CompilationResult`.

## Version strings (unchanged)
`policy_pack.v1` (schema), `workflow_ir.v1` (IR), `capability_registry.v1`
(registry). `DISTRIBUTION_VERSION` held at `0.1.0`; `PRODUCT_VERSION` → `0.2.0`.

## WorkflowIR (frozen)
- `WorkflowIR`: `policy_pack_id`, `policy_pack_version`, `ir_version="workflow_ir.v1"`,
  `nodes`, `edges`, `referenced_capabilities`; `logical_digest()` over ordered
  nodes+edges.
- `WorkflowNode` (11 fields), `WorkflowEdge` (5 fields), `NodeKind` (14 members),
  `EdgeKind` (9 members) — see JSON. Node ids are content-addressed.

## Release + digests (frozen)
- `CompiledReleasePackage` / `ReleaseManifest` / `CapabilityManifest`.
- One digest concept: the release logical digest = `compute_logical_digest(pack, ir,
  capability_manifest, assurance, coverage, audit_schema)`, which commits to
  `compiler_distribution_version`. `release_metadata` is excluded from the digest.
- No injected clock; wall-clock never enters any digest.

## Validation / verification (frozen)
- `PolicyPackValidator` / `ValidationReport` / `ValidationDiagnostic` / `Severity`
  (INFO/WARNING/REVIEW_REQUIRED/ERROR/FATAL). Existing diagnostic codes: see JSON.
- `CompiledPackageVerifier` recomputes digests and re-checks authority boundaries,
  coverage, capability manifest, and audit baseline.

## CLI (frozen, extended)
Before: `version validate compile verify diff inspect demo`. P2 **adds**
`validate-release inspect-semantics inspect-dependencies inspect-provenance
compare-contracts upgrade-v1` and a `--contract` flag on `compile`. No existing
subcommand's behavior changes.

## Dependency direction (frozen)
Leaf package: core imports `pydantic` only. No import of AWC, agentic, agent
runtime, H22, Model Selection, ActionGate execution, or any provider. Providers are
referenced by metadata string and probed with `importlib.util.find_spec` only.
