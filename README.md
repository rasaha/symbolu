# Symbolu

Symbolu is a research platform for deterministic AGI architectures.

## Agentic Framework

The **Agentic Framework** is a code-first Python library for building
governed agentic applications on top of any LLM. Every action an agent
takes is observable, auditable, and controllable.

See [agentic/agentic_framework/README.md](agentic/agentic_framework/README.md)
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
| Framework README | [agentic/agentic_framework/README.md](agentic/agentic_framework/README.md) |
| Quickstart | [agentic/docs/QUICKSTART.md](agentic/docs/QUICKSTART.md) |
| First Governed Agent | [agentic/docs/FIRST_GOVERNED_AGENT.md](agentic/docs/FIRST_GOVERNED_AGENT.md) |
| Mock → Real LLM | [agentic/docs/MOCK_TO_REAL_LLM.md](agentic/docs/MOCK_TO_REAL_LLM.md) |
| Goal Decomposition & Action Mapping | [agentic/docs/GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md](agentic/docs/GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) |
| Examples Overview | [agentic/docs/EXAMPLES_OVERVIEW.md](agentic/docs/EXAMPLES_OVERVIEW.md) |
| Framework Status | [agentic/docs/FRAMEWORK_STATUS.md](agentic/docs/FRAMEWORK_STATUS.md) |
