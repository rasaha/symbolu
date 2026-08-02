# Decision Authority — import graph (after)

## Canonical kernel outbound (after)

`ugence_decision_authority` imports only: Python standard library + **pydantic**. No other
Ugence capability, provider, product, platform service, domain, application, console, or
research package is imported. Enforced by the automated prohibited-import test
`tests/test_platform_boundaries.py`:

- `test_kernel_never_imports_a_consuming_layer` — full forbidden-root list (§17).
- `test_kernel_external_imports_are_only_pydantic_and_stdlib` — leafward dependency direction.
- `test_kernel_imports_standalone_as_a_third_party_package` — imports with only `src` on path.

The package does **not** depend on `ugence_governance_contracts` (the kernel does not import
the neutral contracts).

## Legacy namespace (after)

`decision_governance` is a single logic-free shim. On import it bootstraps the canonical
`src` onto `sys.path` (only when not installed) and aliases every canonical submodule into
`sys.modules` under the legacy dotted name → identical module objects.

`decision_governance` → (re-exports) → `ugence_decision_authority` → pydantic + stdlib

## Inbound consumers (after)

Unchanged. Consumers still `import decision_governance...`; every such import resolves to the
identical object in `ugence_decision_authority`. No consumer business logic was moved; only
three consumer *tests* that hard-coded the old `__module__` string were updated to accept the
canonical prefix (legacy prefix retained).

## Dependency direction (machine-checked)

```
applications → domains → decision_governance (shim) → ugence_decision_authority → pydantic + stdlib
providers / pilots → decision_governance.api (shim) → ugence_decision_authority.api
```

No cycle; the canonical capability remains a leaf among Ugence packages.
