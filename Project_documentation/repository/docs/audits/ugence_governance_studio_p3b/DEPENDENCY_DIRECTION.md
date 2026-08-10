# Dependency Direction (P3B)

```
ugence-governance-studio-api  ──depends on──▶  ugence-agent-workforce-composer 0.2.1
```

The API depends ONLY on the AWC public package (+ presentation libs FastAPI/
Starlette/Uvicorn/pydantic). It does NOT import: AWC/compiler private modules,
AWC test helpers, P3A generation scripts as runtime logic, the compiler package,
H16 / agentic framework, Agent Runtime, H22, Model Selection, ActionGate /
Action Clearance execution, or any product runtime package. The compiler is
consumed indirectly through the AWC public v1/v2 adapter (serialized artifacts).
AWC and compiler source are never bundled into the API wheel (audited by the
distribution verifier). Enforced by `tests/test_architecture.py`.
