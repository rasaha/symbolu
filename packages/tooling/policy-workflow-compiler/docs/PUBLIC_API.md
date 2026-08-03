# Public API

The package exposes a single, curated public surface: the module
`ugence_policy_workflow_compiler.api`.

## The `api` module

```python
import ugence_policy_workflow_compiler.api
```

Everything intended for external use is re-exported through this one module. It
is a deliberate, curated surface rather than a dump of every internal symbol:
consumers import from `api` and rely on nothing outside it.

## Frozen surface

The public surface comprises **71 names**, frozen in
`artifacts/public_api.json`. The frozen artifact is the source of truth for what
the package promises to external callers. Because it is checked in, any change to
the public surface is visible as a change to that artifact — an accidental
addition or removal of a public name is caught rather than shipped silently.

## Why a curated surface

Confining the public API to one module and pinning it to a frozen artifact gives
two guarantees:

- **Stability.** Callers depend only on names that are explicitly promised. The
  large internal object model, validation rules, and compiler internals can
  evolve without breaking consumers, as long as the `api` surface is preserved.
- **Reviewability.** Widening the public API is an explicit, reviewable act — it
  changes `artifacts/public_api.json`. This keeps the surface intentional and
  prevents scope creep.

## Typing

The package ships `py.typed`, so type information for the public surface is
available to type checkers in downstream projects. See `INSTALL.md` for
installation and `NEXT_PHASES.md` for how the surface is expected to grow in
future phases without breaking the frozen contract.
