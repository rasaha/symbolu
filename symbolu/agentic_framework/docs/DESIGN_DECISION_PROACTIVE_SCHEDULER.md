# Design Decision: Proactive Scheduler

**Status:** Implemented
**Version:** 1.5.0
**Date:** 2026-02-02

## Summary

The Proactive Scheduler enables autonomous task execution on explicit schedules with full safety controls. It integrates with MCP Gateway and ConfidenceGate to ensure proactive actions maintain Sentinel's safety guarantees.

## Problem Statement

Agents that only respond to user input are limited. Real automation requires:

1. **Scheduled tasks** - Daily backups, periodic reports, maintenance
2. **Proactive monitoring** - Alert on conditions without user prompting
3. **Background processing** - Long-running tasks that complete asynchronously

However, autonomous execution creates significant risks:

```
❌ Without controls:
   Agent: "I'll help by cleaning up old files every hour"
   Result: Agent deletes production data at 3 AM, no one notices until Monday

✅ With controls:
   Agent: "I'll clean up old files every hour"
   Scheduler: Confidence 0.65 < threshold 0.7 → BLOCKED
   Result: Task requires explicit configuration and approval
```

## Decision

Implement a ProactiveScheduler with these KEY CONSTRAINTS (per ChatGPT's recommendation):

1. **Default = OFF** - Must explicitly enable
2. **min_confidence: 0.7** - Single constraint that turns liability into feature
3. **Cron-style only** - No reactive loops
4. **Explicit schedules** - User defines exactly when tasks run
5. **Full audit trail** - Every execution logged
6. **MCP Gateway integration** - Reuse existing safety infrastructure

## Why Wait for MCP?

ChatGPT correctly identified:

```
Proactivity + no ecosystem = demo toy
Proactivity + MCP = real automation
```

With MCP Gateway now implemented, the scheduler can:
- Execute real tools safely
- Reuse risk classification
- Leverage existing confidence gating
- Maintain audit trails across both systems

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  ProactiveScheduler                          │
├─────────────────────────────────────────────────────────────┤
│  Task Registry                                               │
│  ├── ScheduledTask definitions                              │
│  ├── Cron expression parsing                                │
│  └── Next run calculation                                   │
├─────────────────────────────────────────────────────────────┤
│  Execution Engine                                            │
│  ├── Due task detection                                     │
│  ├── Confidence check (min 0.7)                            │
│  ├── Human review (for high-risk)                          │
│  └── MCP Gateway execution                                  │
├─────────────────────────────────────────────────────────────┤
│  Audit System                                                │
│  ├── ExecutionRecord logging                                │
│  ├── Success/failure tracking                               │
│  └── History with filters                                   │
└─────────────────────────────────────────────────────────────┘
```

## Safety Constraints

### 1. Default OFF

```python
scheduler = ProactiveScheduler(mcp_gateway=gateway)
assert scheduler.enabled is False  # Must explicitly enable

scheduler.enable()  # Explicit action required
```

### 2. Minimum Confidence (0.7)

Every scheduled task must meet a minimum confidence threshold:

```python
task = ScheduledTask(
    name="backup",
    schedule="0 2 * * *",
    tool_name="backup_database",
    parameters={"target": "prod"},
    min_confidence=0.8,  # Can be higher, never lower than 0.5
)
```

The scheduler enforces `min_confidence >= 0.5` for all tasks.

### 3. Cron-Style Only (No Reactive Loops)

```
✅ Supported:
   "0 2 * * *"     # 2 AM daily
   "*/15 * * * *"  # Every 15 minutes
   "0 9-17 * * 1-5" # Hourly during business hours

❌ NOT Supported:
   on_event("file_created")  # Reactive triggers
   while(true) { check() }   # Polling loops
   subscribe(events)         # Event subscriptions
```

### 4. Human Review Option

High-risk tasks can require human confirmation:

```python
task = ScheduledTask(
    name="delete_old_logs",
    schedule="0 3 * * 0",  # Sunday 3 AM
    tool_name="delete_files",
    parameters={"pattern": "*.log", "older_than_days": 30},
    min_confidence=0.85,
    require_human_review=True,  # Human must approve
)
```

### 5. Full Audit Trail

Every execution creates an `ExecutionRecord`:

```python
record = ExecutionRecord(
    task_name="backup",
    timestamp=datetime.now(),
    tool_name="backup_database",
    parameters={"target": "prod"},
    success=True,
    result="Backup completed: 1.2GB",
    confidence_score=0.85,
    risk_level=ToolRiskLevel.WRITE,
    human_confirmed=False,
    duration_seconds=45.2,
)
```

## Integration Points

### With MCP Gateway

```python
# Scheduler uses MCP Gateway for all tool execution
tool_call = MCPToolCall(
    tool_name=task.tool_name,
    parameters=task.parameters,
    quality_score=confidence_signals.quality_score,
    coherence_score=confidence_signals.coherence_score,
)

# MCP Gateway applies its own safety checks
result = await self.mcp_gateway.call_tool(tool_call)
```

### With ConfidenceGate (Optional)

```python
# Can optionally integrate with ConfidenceGate for richer signals
scheduler = create_proactive_scheduler(
    mcp_gateway=gateway,
    confidence_gate=gate,  # Optional
)
```

## Usage Examples

### Basic Usage

```python
from symbolu.agentic_framework import (
    create_proactive_scheduler,
    create_mock_mcp_gateway,
    create_task,
)

# Create gateway and scheduler
gateway = create_mock_mcp_gateway()
scheduler = create_proactive_scheduler(
    mcp_gateway=gateway,
    enabled=True,  # Must explicitly enable
)

# Add a scheduled task
task = create_task(
    name="hourly_health_check",
    schedule="0 * * * *",  # Every hour
    tool_name="health_check",
    parameters={"endpoint": "https://api.example.com/health"},
    min_confidence=0.7,
)
scheduler.add_task(task)

# Run scheduler
await scheduler.run()  # Runs continuously
```

### With Human Review

```python
def ask_user(question: str) -> bool:
    return input(f"{question} [y/n]: ").lower() == 'y'

scheduler = create_proactive_scheduler(
    mcp_gateway=gateway,
    enabled=True,
    human_confirmation_callback=ask_user,
)

# This task will prompt for approval
task = ScheduledTask(
    name="weekly_cleanup",
    schedule="0 2 * * 0",
    tool_name="cleanup_temp_files",
    parameters={"older_than_days": 7},
    require_human_review=True,
)
scheduler.add_task(task)
```

### Monitoring and Debugging

```python
# Get execution history
history = scheduler.get_execution_history(
    task_name="backup",
    success_only=True,
    limit=10,
)

# Get statistics
stats = scheduler.get_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Total executions: {stats['total_executions']}")
```

## Test Coverage

| Category | Tests | Description |
|----------|-------|-------------|
| CronExpression | 8 | Parsing, matching, next run calculation |
| ScheduledTask | 5 | Creation, validation, serialization |
| Scheduler Creation | 3 | Default disabled, enable/disable |
| Task Management | 5 | Add, remove, get, enable/disable tasks |
| Due Tasks | 4 | Detection, filtering disabled/running |
| Execution | 5 | Success, low confidence, human review |
| Run Once | 2 | Disabled vs enabled execution |
| History | 3 | Filtering by task, success/failure |
| Statistics | 2 | Counts, success rate |
| Factory | 2 | Scheduler and task creation |
| Serialization | 2 | Record and scheduler to_dict |
| **Total** | **43** | **All passing** |

## Alternatives Considered

### 1. Reactive Event System

**Rejected:** Too dangerous. Events can cascade unpredictably.

### 2. Natural Language Scheduling

**Rejected:** Ambiguous. "Every morning" is unclear.

### 3. No Minimum Confidence

**Rejected:** ChatGPT correctly identified `min_confidence: 0.7` as the key constraint that makes proactivity safe.

### 4. Build Before MCP

**Rejected:** Per ChatGPT: "Proactivity + no ecosystem = demo toy"

## Future Considerations

1. **Task Dependencies** - Run task B after task A completes
2. **Conditional Execution** - Skip if condition not met
3. **Distributed Scheduling** - Multiple scheduler instances
4. **Backfill** - Run missed executions after downtime

## References

- [MCP Gateway Design Decision](DESIGN_DECISION_MCP_GATEWAY.md)
- [Sentinel Guide - Proactive Scheduler Section](../AGENTIC_FRAMEWORK_GUIDE.md)
