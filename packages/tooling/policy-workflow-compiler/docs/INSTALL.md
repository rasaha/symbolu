# Install

`ugence-policy-workflow-compiler` (namespace `ugence_policy_workflow_compiler`,
version 0.2.0) is a pure-Python tooling package.

## Requirements

- **Python `>= 3.10`.**
- Core runtime dependency: **`pydantic>=2`** only.

## Install the core package

```bash
pip install ugence-policy-workflow-compiler
```

This pulls in `pydantic>=2` and nothing else. The package ships `py.typed`, so
type information is available to downstream type checkers. It installs cleanly
outside the source repository (verified); tests, docs, examples, and scripts are
not included in the wheel.

## Optional extras

| Extra | Installs | Purpose |
| --- | --- | --- |
| `procurement-reference` | `ugence-procurement>=0.1.0` | The Procurement equivalence harness. |
| `dev` | `pytest`, `build` | Testing and building. |

```bash
pip install "ugence-policy-workflow-compiler[procurement-reference]"
pip install "ugence-policy-workflow-compiler[dev]"
```

## Quick start (Python)

```python
import ugence_policy_workflow_compiler.api as api
# The public surface (71 names) is exposed through this one module.
```

See `PUBLIC_API.md` for the curated public surface.

## Command-line interface

The package installs the `ugence-policy-workflow-compiler` console command; it is
also runnable as a module (`python -m ugence_policy_workflow_compiler`).

| Command | Purpose |
| --- | --- |
| `version` | Print version and maturity info. |
| `validate <pack>` | Validate a policy pack. |
| `compile <pack> --approval <approval> [--out DIR]` | Compile an approved pack. |
| `verify <dir>` | Verify a compiled package directory. |
| `diff <old> <new>` | Structural diff of two packs. |
| `inspect <dir>` | Inspect a compiled package. |
| `demo procurement [--out DIR]` | Run the deterministic Procurement demo. |

```bash
ugence-policy-workflow-compiler version
ugence-policy-workflow-compiler demo procurement --out ./out
```

The `demo procurement` command is deterministic, offline, and credential-free —
a good first run to confirm the install. See `DETERMINISM.md` and
`SECURITY_AND_FAILURE_MODEL.md` for the guarantees behind it.
