# LLM Steering Controller — Dependency Boundary Report

## 1. Dependency direction (must point outward only)

```
                 ugence_llm_steering_controller  (leaf: python stdlib ONLY)
                          │  (no outbound edges to any of the below)
   ┌──────────────────────┼───────────────────────────────────────────┐
   ▼                      ▼                                             ▼
 provider SDKs      ugence_model_selection                 control_plane / agent_runtime
 (openai/anthropic/  (selection leaf — NOT a dependency)   hybrid_llm / governance_*
  boto3/google/…)                                          model_selection_pilot/experiment
   ✗ forbidden            ✗ not imported                    ✗ forbidden
```

The steering controller imports **only the Python standard library** (`dataclasses`, `enum`,
`hashlib`, `json`, `re`, `ast`, `argparse`, `importlib`, `os.path`/`pathlib`, `textwrap` in tests).
It imports **no** third-party package and **no** other Ugence package.

## 2. Forbidden dependencies (asserted, not just declared)

Provider SDKs and network/execution infrastructure that must never be a dependency or a module import:

```
openai, anthropic, boto3, botocore, google-cloud, google-generativeai, vertexai, cohere,
mistralai, requests, httpx, urllib3, aiohttp,
socket, subprocess, urllib, http, ssl, asyncio, threading, multiprocessing
```

Forbidden sibling Ugence / research packages:

```
governance_studio, decision_governance, actiongate, agent_runtime, hybrid_llm, ai_hiring,
control_plane, model_selection_pilot, model_selection_experiment, model_selection_reconciliation,
execution_gate
```

**Enforcement (three independent layers):**
1. `tests/boundaries/test_advisory_boundary.py` — AST import scan + source text scan over `src/`.
2. CI `forbidden-import scan` job — AST scan over the tracked source.
3. `verify_llm_steering_controller_distribution.py` — AST + text scan over the **packaged wheel
   source**, plus a clean-venv probe asserting none of the forbidden packages is importable.

## 3. Why provider SDKs are not (even optional) dependencies

Provider SDKs are required for **none** of: import, routing recommendation, simulation, CLI fixture
execution, or package verification. The registry holds **metadata only**; scoring uses configured
class priors / caller-supplied numeric estimates; discovery reads the in-memory snapshot. There is no
code path that would benefit from a provider client, so no SDK appears even as an extra. The only
optional extra is `dev` (pytest / build / pip-audit).

## 4. Relationship to the selection leaf

`ugence-model-selection` is **complementary but not a dependency**. Making it a dependency was
considered and rejected: it would couple two independently-installable capabilities and pull the
steering package away from a zero-dependency leaf. The routing contracts are self-contained; a
governed runtime may compose the two, but neither imports the other.

## 5. SBOM / runtime closure

The generated SBOM (`artifacts/llm_steering/…` at build time via `scripts/generate_sbom.py`) records
**zero third-party runtime dependencies**. `pip check` passes and the runtime `pip-audit` closure is
empty (stdlib only), so there is no third-party CVE surface in the distributed package.

## 6. No circular dependencies

Because the package has no outbound edges to any in-repo module, no cycle involving the steering
controller is possible. Any future legacy shim must depend on the package (inward), never the reverse.
