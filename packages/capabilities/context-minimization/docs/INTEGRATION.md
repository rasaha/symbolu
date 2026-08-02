# Integration

## Implementing an oracle

Provide any object with an `evaluate(context, *, evaluation_time=None) -> OracleEvaluation`
method. The oracle owns all equivalence/authorization semantics and returns a canonical,
versioned, opaque `equivalence_key`.

```python
from ugence_context_minimization.api import OracleEvaluation

class MyOracle:
    def evaluate(self, context, *, evaluation_time=None):
        key = my_canonical_key(context)          # deterministic, versioned, opaque
        return OracleEvaluation(
            equivalence_key=key,
            oracle_id="my-oracle",
            contract_version="1.0",
            correlation_id=context.correlation_id,
            valid_until=evaluation_time + 900 if evaluation_time else None,
        )
```

## ActionGate as a concrete oracle (outside this package)

An ActionGate-derived oracle assembles the surviving units into a request, evaluates
the real gate, and returns a canonical key over the **decision outputs** (envelope +
outcome + dispositive rules + applied constraints). It lives in an integration package
or the existing experimental harness — **never** in the core. The architecture is:

```
assembled context → ugence-context-minimization core → InvarianceOracle protocol
                                                              ↑ implemented by
                                                    ActionGate integration adapter
```

The core minimizes; ActionGate decides authorization and supplies the deterministic
equivalence result; the minimizer creates no authority.

## Implementing protection

Provide a `ProtectionProvider` with `protect(context) -> ProtectionResult`, or pass
`protected_ids` / `protected=True` units directly. Fail closed: mark unsure units
`uncertain` (retained), never guess them removable.

## Token counting

Supply per-unit `token_count`, or inject a `TokenCounter`, or rely on the neutral
default. The core never requires a model tokenizer.
