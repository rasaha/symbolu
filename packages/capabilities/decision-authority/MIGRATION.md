# Migration — `decision_governance` → `ugence_decision_authority`

The bounded Decision Authority kernel moved to the canonical package
`ugence_decision_authority` (distribution `ugence-decision-authority`). The legacy
`decision_governance` namespace remains available and behaves identically.

## What changed

- Canonical source: `packages/capabilities/decision-authority/src/ugence_decision_authority/`
  (one physical implementation).
- Legacy `decision_governance` at the repository root is now a **logic-free compatibility
  shim** (a single `__init__.py`) that re-exports the canonical package.
- The legacy `decision-governance` distribution is a **compatibility shell** depending on
  `ugence-decision-authority` (no duplicated source).

## For consumers — nothing is required

Existing imports keep working unchanged and resolve to the **same objects**:

```python
from decision_governance.api.services import DecisionCaseService   # still works
from ugence_decision_authority.api.services import DecisionCaseService  # canonical
# these are the identical class object
```

When convenient, migrate imports to the canonical `ugence_decision_authority` namespace.
The only observable difference is `type(x).__module__`, which now reports the canonical
name; checks that hard-code the string `"decision_governance."` should accept
`"ugence_decision_authority."` too.

## Compatibility mechanism

`decision_governance/__init__.py` performs a source-checkout bootstrap (adds the canonical
`src` to `sys.path` only when the package is not already installed) and then aliases every
canonical submodule into `sys.modules` under the legacy dotted name — so
`import decision_governance.<path>` returns the identical module object as
`import ugence_decision_authority.<path>`. This is an explicit, eager alias, **not** a
meta-path import hook, and contains no business logic.

## Removal / review

The `decision_governance` shim and the `decision-governance` compatibility distribution are
transitional. Review/removal target: `decision_governance` 2.0.0.
