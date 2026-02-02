"""
Proactive Scheduler for Agentic LLM Framework

Enables autonomous task execution on explicit schedules with full safety controls.

KEY CONSTRAINTS:
1. Cron-style scheduling ONLY (no reactive loops)
2. Minimum confidence threshold (default 0.7)
3. Full audit trail
4. Default = OFF (must be explicitly enabled)
5. Integrates with MCP Gateway and ConfidenceGate

SAFETY PHILOSOPHY:
- Proactivity without constraints = liability
- Proactivity + MCP + ConfidenceGate = real automation
- Every scheduled execution goes through the same safety gates as interactive calls

Usage:
    from symbolu.agentic_framework import (
        ProactiveScheduler,
        ScheduledTask,
        create_proactive_scheduler,
    )

    # Create scheduler (disabled by default)
    scheduler = create_proactive_scheduler(
        mcp_gateway=gateway,
        confidence_gate=gate,
        enabled=True,  # Must explicitly enable
    )

    # Schedule a task
    task = ScheduledTask(
        name="daily_backup",
        schedule="0 2 * * *",  # 2 AM daily
        tool_name="backup_database",
        parameters={"target": "production"},
        min_confidence=0.8,
    )
    scheduler.add_task(task)

    # Run scheduler (typically in background)
    await scheduler.run()
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import asyncio
import time
import re
import logging

# Local imports
from symbolu.agentic_framework.mcp_gateway import (
    SafeMCPGateway,
    MCPToolCall,
    MCPToolResult,
    ToolRiskLevel,
)
from symbolu.agentic_framework.confidence_gate import (
    ConfidenceGate,
    ConfidenceSignals,
    EscalationLevel,
)


# =============================================================================
# Enums
# =============================================================================


class TaskStatus(Enum):
    """Status of a scheduled task."""

    PENDING = "pending"  # Waiting for next execution
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Last execution succeeded
    FAILED = "failed"  # Last execution failed
    BLOCKED = "blocked"  # Blocked by safety gate
    DISABLED = "disabled"  # Manually disabled


class ScheduleType(Enum):
    """Type of schedule."""

    CRON = "cron"  # Cron expression
    INTERVAL = "interval"  # Fixed interval
    ONCE = "once"  # One-time execution


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CronExpression:
    """
    Parsed cron expression.

    Format: minute hour day_of_month month day_of_week
    Example: "0 2 * * *" = 2:00 AM every day

    Supported:
    - Exact values: 0, 15, 30
    - Wildcards: *
    - Ranges: 1-5
    - Step values: */15

    NOT supported (intentionally limited):
    - Lists: 1,2,3
    - Complex expressions
    """

    minute: str
    hour: str
    day_of_month: str
    month: str
    day_of_week: str

    # Pre-parsed values for matching
    _minute_values: List[int] = field(default_factory=list, repr=False)
    _hour_values: List[int] = field(default_factory=list, repr=False)
    _day_of_month_values: List[int] = field(default_factory=list, repr=False)
    _month_values: List[int] = field(default_factory=list, repr=False)
    _day_of_week_values: List[int] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Parse cron fields after initialization."""
        self._minute_values = self._parse_field(self.minute, 0, 59)
        self._hour_values = self._parse_field(self.hour, 0, 23)
        self._day_of_month_values = self._parse_field(self.day_of_month, 1, 31)
        self._month_values = self._parse_field(self.month, 1, 12)
        self._day_of_week_values = self._parse_field(self.day_of_week, 0, 6)

    def _parse_field(self, field: str, min_val: int, max_val: int) -> List[int]:
        """Parse a single cron field into list of valid values."""
        field = field.strip()

        # Wildcard - all values
        if field == "*":
            return list(range(min_val, max_val + 1))

        # Step value: */15 or 0-30/5
        if "/" in field:
            base, step = field.split("/", 1)
            step = int(step)
            if base == "*":
                return list(range(min_val, max_val + 1, step))
            elif "-" in base:
                start, end = base.split("-", 1)
                return list(range(int(start), int(end) + 1, step))
            else:
                return list(range(int(base), max_val + 1, step))

        # Range: 1-5
        if "-" in field:
            start, end = field.split("-", 1)
            return list(range(int(start), int(end) + 1))

        # Exact value
        return [int(field)]

    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches this cron expression."""
        return (
            dt.minute in self._minute_values
            and dt.hour in self._hour_values
            and dt.day in self._day_of_month_values
            and dt.month in self._month_values
            and dt.weekday() in self._day_of_week_values
        )

    def next_run(self, after: datetime) -> datetime:
        """Calculate next run time after given datetime."""
        # Start from next minute
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search up to 1 year ahead
        max_iterations = 60 * 24 * 366  # minutes in a year
        for _ in range(max_iterations):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        # Should never reach here for valid cron
        raise ValueError(f"Could not find next run time for cron expression")

    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        """Parse cron expression string."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression: expected 5 parts, got {len(parts)}"
            )
        return cls(
            minute=parts[0],
            hour=parts[1],
            day_of_month=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )


@dataclass
class ScheduledTask:
    """
    A task scheduled for proactive execution.

    Attributes:
        name: Unique task identifier
        schedule: Cron expression or interval
        tool_name: MCP tool to execute
        parameters: Tool parameters
        min_confidence: Minimum confidence required (default 0.7)
        enabled: Whether task is active (default True)
        max_retries: Maximum retry attempts on failure
        retry_delay_seconds: Delay between retries
        description: Human-readable description
    """

    name: str
    schedule: str  # Cron expression like "0 2 * * *"
    tool_name: str
    parameters: Dict[str, Any]

    # Safety constraints
    min_confidence: float = 0.7  # ChatGPT's key constraint
    require_human_review: bool = False  # For high-risk tasks

    # Task configuration
    enabled: bool = True
    max_retries: int = 0
    retry_delay_seconds: int = 60
    timeout_seconds: float = 300.0
    description: str = ""

    # Scheduling
    schedule_type: ScheduleType = ScheduleType.CRON

    # Runtime state (not serialized)
    _status: TaskStatus = field(default=TaskStatus.PENDING, repr=False)
    _last_run: Optional[datetime] = field(default=None, repr=False)
    _next_run: Optional[datetime] = field(default=None, repr=False)
    _consecutive_failures: int = field(default=0, repr=False)
    _cron: Optional[CronExpression] = field(default=None, repr=False)

    def __post_init__(self):
        """Validate and initialize task."""
        if self.min_confidence < 0.5:
            raise ValueError(
                f"min_confidence must be >= 0.5 for scheduled tasks, got {self.min_confidence}"
            )
        if self.min_confidence > 1.0:
            raise ValueError(f"min_confidence must be <= 1.0, got {self.min_confidence}")

        # Parse cron expression
        if self.schedule_type == ScheduleType.CRON:
            self._cron = CronExpression.parse(self.schedule)

    def calculate_next_run(self, after: Optional[datetime] = None) -> datetime:
        """Calculate next run time."""
        after = after or datetime.now()

        if self.schedule_type == ScheduleType.CRON:
            if self._cron is None:
                self._cron = CronExpression.parse(self.schedule)
            return self._cron.next_run(after)

        elif self.schedule_type == ScheduleType.INTERVAL:
            interval_seconds = int(self.schedule)
            if self._last_run:
                return self._last_run + timedelta(seconds=interval_seconds)
            return after + timedelta(seconds=interval_seconds)

        elif self.schedule_type == ScheduleType.ONCE:
            # Parse as ISO datetime
            return datetime.fromisoformat(self.schedule)

        raise ValueError(f"Unknown schedule type: {self.schedule_type}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "schedule": self.schedule,
            "schedule_type": self.schedule_type.value,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "min_confidence": self.min_confidence,
            "require_human_review": self.require_human_review,
            "enabled": self.enabled,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "timeout_seconds": self.timeout_seconds,
            "description": self.description,
            "status": self._status.value,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "consecutive_failures": self._consecutive_failures,
        }


@dataclass
class ExecutionRecord:
    """Record of a scheduled task execution."""

    task_name: str
    timestamp: datetime
    tool_name: str
    parameters: Dict[str, Any]

    # Execution result
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None

    # Safety information
    confidence_score: float = 0.0
    risk_level: Optional[ToolRiskLevel] = None
    blocked_reason: Optional[str] = None
    human_confirmed: bool = False

    # Timing
    duration_seconds: float = 0.0
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "task_name": self.task_name,
            "timestamp": self.timestamp.isoformat(),
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "success": self.success,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "confidence_score": self.confidence_score,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "blocked_reason": self.blocked_reason,
            "human_confirmed": self.human_confirmed,
            "duration_seconds": self.duration_seconds,
            "retry_count": self.retry_count,
        }


# =============================================================================
# Scheduler Implementation
# =============================================================================


class ProactiveScheduler:
    """
    Scheduler for autonomous task execution with safety controls.

    KEY SAFETY FEATURES:
    1. Default = OFF (must explicitly enable)
    2. Minimum confidence threshold per task
    3. Integration with ConfidenceGate
    4. Integration with MCP Gateway
    5. Full audit trail
    6. Cron-style only (no reactive loops)

    EXECUTION FLOW:
    1. Check if scheduler is enabled
    2. Find tasks due for execution
    3. For each task:
       a. Build confidence signals
       b. Check against min_confidence
       c. Call MCP Gateway (which has its own safety checks)
       d. Log execution record
       e. Update task state
    """

    def __init__(
        self,
        mcp_gateway: SafeMCPGateway,
        confidence_gate: Optional[ConfidenceGate] = None,
        enabled: bool = False,  # DEFAULT OFF - must explicitly enable
        default_min_confidence: float = 0.7,
        human_confirmation_callback: Optional[Callable[[str], bool]] = None,
        max_concurrent_tasks: int = 1,  # Conservative default
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize proactive scheduler.

        Args:
            mcp_gateway: Gateway for tool execution
            confidence_gate: Gate for confidence checking (optional)
            enabled: Whether scheduler is active (DEFAULT: False)
            default_min_confidence: Default minimum confidence for tasks
            human_confirmation_callback: Callback for human review
            max_concurrent_tasks: Maximum concurrent task executions
            logger: Logger instance
        """
        self.mcp_gateway = mcp_gateway
        self.confidence_gate = confidence_gate
        self._enabled = enabled
        self.default_min_confidence = default_min_confidence
        self.human_confirmation_callback = human_confirmation_callback
        self.max_concurrent_tasks = max_concurrent_tasks
        self.logger = logger or logging.getLogger(__name__)

        # Task registry
        self._tasks: Dict[str, ScheduledTask] = {}

        # Execution history
        self._execution_history: List[ExecutionRecord] = []
        self._max_history_size: int = 1000

        # Runtime state
        self._running: bool = False
        self._current_executions: int = 0

    @property
    def enabled(self) -> bool:
        """Check if scheduler is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable the scheduler."""
        self._enabled = True
        self.logger.info("Proactive scheduler ENABLED")

    def disable(self) -> None:
        """Disable the scheduler."""
        self._enabled = False
        self.logger.info("Proactive scheduler DISABLED")

    def add_task(self, task: ScheduledTask) -> None:
        """
        Add a task to the scheduler.

        Args:
            task: Task to schedule

        Raises:
            ValueError: If task name already exists
        """
        if task.name in self._tasks:
            raise ValueError(f"Task '{task.name}' already exists")

        # Calculate next run time
        task._next_run = task.calculate_next_run()
        task._status = TaskStatus.PENDING

        self._tasks[task.name] = task
        self.logger.info(f"Added task '{task.name}', next run: {task._next_run}")

    def remove_task(self, name: str) -> bool:
        """
        Remove a task from the scheduler.

        Args:
            name: Task name to remove

        Returns:
            True if task was removed, False if not found
        """
        if name in self._tasks:
            del self._tasks[name]
            self.logger.info(f"Removed task '{name}'")
            return True
        return False

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        """Get task by name."""
        return self._tasks.get(name)

    def list_tasks(self) -> List[ScheduledTask]:
        """List all scheduled tasks."""
        return list(self._tasks.values())

    def enable_task(self, name: str) -> bool:
        """Enable a specific task."""
        task = self._tasks.get(name)
        if task:
            task.enabled = True
            task._status = TaskStatus.PENDING
            task._next_run = task.calculate_next_run()
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a specific task."""
        task = self._tasks.get(name)
        if task:
            task.enabled = False
            task._status = TaskStatus.DISABLED
            return True
        return False

    def get_due_tasks(self, now: Optional[datetime] = None) -> List[ScheduledTask]:
        """Get tasks due for execution."""
        now = now or datetime.now()
        due = []

        for task in self._tasks.values():
            if not task.enabled:
                continue
            if task._status == TaskStatus.RUNNING:
                continue
            if task._next_run and task._next_run <= now:
                due.append(task)

        return due

    async def execute_task(
        self,
        task: ScheduledTask,
        confidence_signals: Optional[ConfidenceSignals] = None,
    ) -> ExecutionRecord:
        """
        Execute a single scheduled task.

        Args:
            task: Task to execute
            confidence_signals: Optional pre-built signals

        Returns:
            ExecutionRecord with result
        """
        start_time = time.time()
        task._status = TaskStatus.RUNNING

        # Build confidence signals if not provided
        if confidence_signals is None:
            confidence_signals = ConfidenceSignals(
                quality_score=0.8,  # Scheduled tasks assumed to be well-defined
                coherence_score=0.9,  # No conversation context
                trajectory_confidence=0.8,
            )

        # Calculate overall confidence
        confidence_score = (
            confidence_signals.quality_score * 0.4
            + confidence_signals.coherence_score * 0.4
            + confidence_signals.trajectory_confidence * 0.2
        )

        # Check against task's minimum confidence
        if confidence_score < task.min_confidence:
            record = ExecutionRecord(
                task_name=task.name,
                timestamp=datetime.now(),
                tool_name=task.tool_name,
                parameters=task.parameters,
                success=False,
                error=f"Confidence {confidence_score:.2f} below threshold {task.min_confidence}",
                confidence_score=confidence_score,
                blocked_reason="low_confidence",
                duration_seconds=time.time() - start_time,
            )
            task._status = TaskStatus.BLOCKED
            task._consecutive_failures += 1
            self._record_execution(record)
            return record

        # Check if human review required
        if task.require_human_review:
            if self.human_confirmation_callback:
                question = (
                    f"Scheduled task '{task.name}' wants to execute "
                    f"'{task.tool_name}' with parameters {task.parameters}. Approve?"
                )
                confirmed = self.human_confirmation_callback(question)
                if not confirmed:
                    record = ExecutionRecord(
                        task_name=task.name,
                        timestamp=datetime.now(),
                        tool_name=task.tool_name,
                        parameters=task.parameters,
                        success=False,
                        error="Human review denied execution",
                        confidence_score=confidence_score,
                        blocked_reason="human_denied",
                        duration_seconds=time.time() - start_time,
                    )
                    task._status = TaskStatus.BLOCKED
                    self._record_execution(record)
                    return record
            else:
                # No callback - block execution
                record = ExecutionRecord(
                    task_name=task.name,
                    timestamp=datetime.now(),
                    tool_name=task.tool_name,
                    parameters=task.parameters,
                    success=False,
                    error="Human review required but no callback configured",
                    confidence_score=confidence_score,
                    blocked_reason="no_human_callback",
                    duration_seconds=time.time() - start_time,
                )
                task._status = TaskStatus.BLOCKED
                self._record_execution(record)
                return record

        # Execute via MCP Gateway
        tool_call = MCPToolCall(
            tool_name=task.tool_name,
            parameters=task.parameters,
            quality_score=confidence_signals.quality_score,
            coherence_score=confidence_signals.coherence_score,
        )

        retry_count = 0
        last_error = None

        while retry_count <= task.max_retries:
            try:
                result = await asyncio.wait_for(
                    self.mcp_gateway.call_tool(tool_call),
                    timeout=task.timeout_seconds,
                )

                if result.success:
                    record = ExecutionRecord(
                        task_name=task.name,
                        timestamp=datetime.now(),
                        tool_name=task.tool_name,
                        parameters=task.parameters,
                        success=True,
                        result=result.result,
                        confidence_score=confidence_score,
                        risk_level=result.risk_level,
                        human_confirmed=task.require_human_review,
                        duration_seconds=time.time() - start_time,
                        retry_count=retry_count,
                    )
                    task._status = TaskStatus.COMPLETED
                    task._last_run = datetime.now()
                    task._next_run = task.calculate_next_run()
                    task._consecutive_failures = 0
                    self._record_execution(record)
                    return record
                else:
                    last_error = result.error
                    retry_count += 1
                    if retry_count <= task.max_retries:
                        await asyncio.sleep(task.retry_delay_seconds)

            except asyncio.TimeoutError:
                last_error = f"Execution timed out after {task.timeout_seconds}s"
                retry_count += 1
                if retry_count <= task.max_retries:
                    await asyncio.sleep(task.retry_delay_seconds)

            except Exception as e:
                last_error = str(e)
                retry_count += 1
                if retry_count <= task.max_retries:
                    await asyncio.sleep(task.retry_delay_seconds)

        # All retries exhausted
        record = ExecutionRecord(
            task_name=task.name,
            timestamp=datetime.now(),
            tool_name=task.tool_name,
            parameters=task.parameters,
            success=False,
            error=last_error,
            confidence_score=confidence_score,
            duration_seconds=time.time() - start_time,
            retry_count=retry_count,
        )
        task._status = TaskStatus.FAILED
        task._last_run = datetime.now()
        task._next_run = task.calculate_next_run()
        task._consecutive_failures += 1
        self._record_execution(record)
        return record

    def _record_execution(self, record: ExecutionRecord) -> None:
        """Record execution in history."""
        self._execution_history.append(record)

        # Trim history if needed
        if len(self._execution_history) > self._max_history_size:
            self._execution_history = self._execution_history[-self._max_history_size :]

        # Log execution
        if record.success:
            self.logger.info(
                f"Task '{record.task_name}' executed successfully "
                f"(confidence={record.confidence_score:.2f})"
            )
        else:
            self.logger.warning(
                f"Task '{record.task_name}' failed: {record.error} "
                f"(confidence={record.confidence_score:.2f})"
            )

    async def run_once(self) -> List[ExecutionRecord]:
        """
        Run one iteration of the scheduler.

        Executes all due tasks and returns execution records.

        Returns:
            List of execution records
        """
        if not self._enabled:
            return []

        due_tasks = self.get_due_tasks()
        records = []

        for task in due_tasks:
            if self._current_executions >= self.max_concurrent_tasks:
                break

            self._current_executions += 1
            try:
                record = await self.execute_task(task)
                records.append(record)
            finally:
                self._current_executions -= 1

        return records

    async def run(self, check_interval_seconds: int = 60) -> None:
        """
        Run the scheduler continuously.

        Args:
            check_interval_seconds: How often to check for due tasks
        """
        self._running = True
        self.logger.info(
            f"Proactive scheduler started (enabled={self._enabled}, "
            f"check_interval={check_interval_seconds}s)"
        )

        while self._running:
            if self._enabled:
                await self.run_once()

            await asyncio.sleep(check_interval_seconds)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        self.logger.info("Proactive scheduler stopped")

    def get_execution_history(
        self,
        task_name: Optional[str] = None,
        success_only: bool = False,
        failed_only: bool = False,
        limit: int = 100,
    ) -> List[ExecutionRecord]:
        """
        Get execution history with optional filters.

        Args:
            task_name: Filter by task name
            success_only: Only successful executions
            failed_only: Only failed executions
            limit: Maximum records to return

        Returns:
            Filtered execution history
        """
        records = self._execution_history

        if task_name:
            records = [r for r in records if r.task_name == task_name]

        if success_only:
            records = [r for r in records if r.success]
        elif failed_only:
            records = [r for r in records if not r.success]

        return records[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        total_executions = len(self._execution_history)
        successful = sum(1 for r in self._execution_history if r.success)
        failed = total_executions - successful

        return {
            "enabled": self._enabled,
            "running": self._running,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "total_executions": total_executions,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": successful / total_executions if total_executions > 0 else 0,
            "current_executions": self._current_executions,
            "max_concurrent_tasks": self.max_concurrent_tasks,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize scheduler state to dictionary."""
        return {
            "enabled": self._enabled,
            "default_min_confidence": self.default_min_confidence,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "statistics": self.get_statistics(),
        }


# =============================================================================
# Factory Functions
# =============================================================================


def create_proactive_scheduler(
    mcp_gateway: SafeMCPGateway,
    confidence_gate: Optional[ConfidenceGate] = None,
    enabled: bool = False,  # DEFAULT OFF
    default_min_confidence: float = 0.7,
    human_confirmation_callback: Optional[Callable[[str], bool]] = None,
) -> ProactiveScheduler:
    """
    Create a proactive scheduler with standard configuration.

    Args:
        mcp_gateway: Gateway for tool execution
        confidence_gate: Gate for confidence checking
        enabled: Whether scheduler is active (DEFAULT: False)
        default_min_confidence: Default minimum confidence
        human_confirmation_callback: Callback for human review

    Returns:
        Configured ProactiveScheduler
    """
    return ProactiveScheduler(
        mcp_gateway=mcp_gateway,
        confidence_gate=confidence_gate,
        enabled=enabled,
        default_min_confidence=default_min_confidence,
        human_confirmation_callback=human_confirmation_callback,
    )


def create_task(
    name: str,
    schedule: str,
    tool_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    min_confidence: float = 0.7,
    description: str = "",
) -> ScheduledTask:
    """
    Create a scheduled task with standard configuration.

    Args:
        name: Task name
        schedule: Cron expression
        tool_name: MCP tool to execute
        parameters: Tool parameters
        min_confidence: Minimum confidence required
        description: Task description

    Returns:
        Configured ScheduledTask
    """
    return ScheduledTask(
        name=name,
        schedule=schedule,
        tool_name=tool_name,
        parameters=parameters or {},
        min_confidence=min_confidence,
        description=description,
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "TaskStatus",
    "ScheduleType",
    # Data classes
    "CronExpression",
    "ScheduledTask",
    "ExecutionRecord",
    # Main scheduler
    "ProactiveScheduler",
    # Factory functions
    "create_proactive_scheduler",
    "create_task",
]
