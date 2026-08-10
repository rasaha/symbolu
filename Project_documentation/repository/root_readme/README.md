# Symbolu

Symbolu is a research platform for deterministic AGI architectures.

## Agentic Framework

The **Agentic Framework** is a code-first Python library for building
governed agentic applications on top of any LLM. Every action an agent
takes is observable, auditable, and controllable.

See [Project_documentation/agentic_framework/agentic/agentic_framework/README.md](../../agentic_framework/agentic/agentic_framework/README.md)
for full documentation, quickstart, and examples.

### Quick install

```bash
pip install -e .
```

### Minimal example

```python
from agentic.agentic_framework import (
    build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel, format_trace,
)

agent = build_agent(
    adapter=MockLLMAdapter(default_response="Python is versatile."),
    tools={
        "search": ToolSpec(
            handler=lambda p: [f"Result for: {p.get('query', '')}"],
            description="Search for information",
            risk_level=ToolRiskLevel.READ_ONLY,
        ),
    },
)
agent.new_session()

trace = agent.run_with_trace("Tell me about Python")
print(format_trace(trace))
```

No API keys or GPU required. Replace `MockLLMAdapter` with
`OpenAIAdapter` or `AnthropicAdapter` to use a real LLM — no other
wiring changes needed.

### Documentation

| Doc | Path |
|-----|------|
| Framework README | [Project_documentation/agentic_framework/agentic/agentic_framework/README.md](../../agentic_framework/agentic/agentic_framework/README.md) |
| Quickstart | [Project_documentation/agentic_framework/agentic/docs/QUICKSTART.md](../../agentic_framework/agentic/docs/QUICKSTART.md) |
| First Governed Agent | [Project_documentation/agentic_framework/agentic/docs/FIRST_GOVERNED_AGENT.md](../../agentic_framework/agentic/docs/FIRST_GOVERNED_AGENT.md) |
| Mock → Real LLM | [Project_documentation/agentic_framework/agentic/docs/MOCK_TO_REAL_LLM.md](../../agentic_framework/agentic/docs/MOCK_TO_REAL_LLM.md) |
| Goal Decomposition & Action Mapping | [Project_documentation/agentic_framework/agentic/docs/GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md](../../agentic_framework/agentic/docs/GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) |
| Examples Overview | [Project_documentation/agentic_framework/agentic/docs/EXAMPLES_OVERVIEW.md](../../agentic_framework/agentic/docs/EXAMPLES_OVERVIEW.md) |
| Framework Status | [Project_documentation/agentic_framework/agentic/docs/FRAMEWORK_STATUS.md](../../agentic_framework/agentic/docs/FRAMEWORK_STATUS.md) |
| External Validation Guide | [Project_documentation/agentic_framework/agentic/docs/EXTERNAL_DEVELOPER_VALIDATION.md](../../agentic_framework/agentic/docs/EXTERNAL_DEVELOPER_VALIDATION.md) |
