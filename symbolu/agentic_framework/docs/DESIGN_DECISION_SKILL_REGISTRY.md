# Design Decision: Skill / Plugin Registry

**Status:** Planned (Phase 2 - Minimal)
**Version:** N/A (Not yet implemented)
**Date:** 2026-02-02

## Summary

A minimal skill registry for loading trusted, signed plugins with strict capability controls. This is about **supply chain risk**, not features.

## ChatGPT's Assessment

> This is about supply chain risk, not features.
>
> Do NOT build a marketplace.
> Do NOT allow unsigned skills.
> Do NOT allow dynamic permissions.
>
> What to build instead:
> - Signed manifest loader
> - Capability allowlist
> - Hard block dangerous primitives
>
> This aligns perfectly with your SafetyContract philosophy.
>
> **Verdict: Phase 2 (minimal)**

## What We Will NOT Build

### ❌ Marketplace

```
REJECTED: Public skill marketplace
- Supply chain attacks
- Malicious plugins
- Dependency hell
- Version conflicts
- Trust issues
```

### ❌ Unsigned Skills

```
REJECTED: Loading unsigned/unverified code
- No provenance
- No integrity check
- Easy to tamper
- No accountability
```

### ❌ Dynamic Permissions

```
REJECTED: Skills that request permissions at runtime
- Privilege escalation
- Permission creep
- User fatigue ("just click allow")
- Unpredictable behavior
```

## What We Will Build (Minimal)

### 1. Signed Manifest Loader

Every skill must have a signed manifest:

```yaml
# skill.manifest.yaml
name: "backup-tools"
version: "1.0.0"
author: "internal-team"
signature: "sha256:abc123..."  # Must verify

capabilities:
  - file_read
  - file_write_tmp

tools:
  - name: create_backup
    risk_level: write
    parameters:
      - name: source
        type: string
      - name: destination
        type: string
        pattern: "^/tmp/.*"  # Restricted to /tmp
```

### 2. Capability Allowlist

Skills declare capabilities; Sentinel verifies against allowlist:

```python
ALLOWED_CAPABILITIES = {
    "file_read",
    "file_write_tmp",
    "network_internal",
    "database_read",
}

FORBIDDEN_CAPABILITIES = {
    "file_write_system",
    "network_external",
    "shell_execute",
    "credential_access",
    "privilege_escalation",
}
```

### 3. Hard Block Dangerous Primitives

Regardless of manifest, certain operations are ALWAYS blocked:

```python
HARD_BLOCKED = [
    "eval",
    "exec",
    "subprocess",
    "os.system",
    "__import__",
    "importlib",
    "ctypes",
    "pickle.loads",
]
```

## Integration with Existing Components

### With SafetyContract

Skills must satisfy SafetyContract preconditions:

```python
# Before executing any skill tool
contract = safety_evaluator.evaluate(
    coherence_state=state,
    goal_state=goal,
    proposed_actions=[skill_tool.name],
)

if not contract.eligible:
    raise SkillExecutionBlocked(contract.blocking_reasons)
```

### With MCP Gateway

Skills register their tools through MCP Gateway:

```python
# Skill loader registers tools
for tool in skill.tools:
    mcp_client.register_tool(
        name=f"{skill.name}.{tool.name}",
        handler=tool.handler,
        risk_level=tool.risk_level,
    )
```

### With ConfidenceGate

Skill tool calls go through confidence gating:

```python
# Same as any other tool call
result = await gateway.call_tool(
    MCPToolCall(
        tool_name=f"{skill.name}.{tool.name}",
        parameters=params,
        quality_score=signals.quality_score,
        coherence_score=signals.coherence_score,
    )
)
```

## Proposed API (Phase 2)

```python
from symbolu.agentic_framework import (
    SkillRegistry,
    SkillManifest,
    load_skill,
)

# Create registry with gateway integration
registry = SkillRegistry(
    mcp_gateway=gateway,
    allowed_capabilities=["file_read", "file_write_tmp"],
    signature_verifier=SignatureVerifier(trusted_keys=keys),
)

# Load a signed skill
skill = load_skill("/path/to/skill.manifest.yaml")

# Verify signature and capabilities
registry.register(skill)  # Raises if invalid

# List registered skills
for skill in registry.list_skills():
    print(f"{skill.name}: {skill.capabilities}")

# Unregister skill
registry.unregister("backup-tools")
```

## Why Phase 2?

1. **MCP Gateway must be stable first** - Skills use MCP for tool execution
2. **Proactive Scheduler must be stable first** - Skills may include scheduled tasks
3. **Core safety infrastructure mature** - ConfidenceGate, SafetyContract working
4. **Real use cases needed** - Don't build abstractions without concrete needs

## Implementation Checklist (Future)

- [ ] SkillManifest dataclass with validation
- [ ] SignatureVerifier for manifest signatures
- [ ] CapabilityValidator against allowlist
- [ ] SkillRegistry for loading/unloading
- [ ] Integration tests with MCP Gateway
- [ ] Documentation and examples

## Security Considerations

### Supply Chain

- Only load skills from trusted sources
- Verify signatures before loading
- Pin skill versions in production
- Audit skill changes

### Runtime

- Skills run in same process (no sandbox)
- Capabilities enforced by Sentinel, not isolation
- Monitor skill behavior through audit logs

### Updates

- No automatic updates
- Manual review for skill changes
- Version pinning required

## References

- [SafetyContract Design](./safety_contract.py)
- [MCP Gateway Design Decision](DESIGN_DECISION_MCP_GATEWAY.md)
- [ChatGPT Feature Assessment](./FEATURE_ASSESSMENT_CHATGPT.md)
