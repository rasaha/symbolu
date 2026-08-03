# Quickstart

```python
from ugence_governance_provider_framework.api import AssertionGovernanceRequest
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import TapEngine

provider = build_tap_provider(TapEngine())
provider.initialize()

result = provider.evaluate(
    AssertionGovernanceRequest("Revenue increased", evidence_refs=("e1", "e2")))
print(result.coverage.value)        # SUPPORTED / UNSUPPORTED / CONSTRAINED / INDETERMINATE
print(result.evidence_coverage)     # bounded 0.0..1.0
print(result.unsupported_elements, result.constraints, result.obligations)
```

Missing evidence, engine failures, and unknown outcomes all yield `INDETERMINATE`
— never `SUPPORTED`. See `FAIL_SAFE_BEHAVIOR.md`.

CLI: `python -m ugence_tap_provider version|verify|demo`.
