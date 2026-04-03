"""
Tests for ProactiveScheduler

Tests the scheduler for autonomous task execution with safety controls.
"""

import pytest
from datetime import datetime, timedelta
import asyncio

from agentic.agentic_framework.proactive_scheduler import (
    ProactiveScheduler,
    ScheduledTask,
    ExecutionRecord,
    CronExpression,
    TaskStatus,
    ScheduleType,
    create_proactive_scheduler,
    create_task,
)
from agentic.agentic_framework.mcp_gateway import (
    create_mock_mcp_gateway,
    ToolRiskLevel,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceGate,
    ConfidenceSignals,
    create_confidence_gate,
)


def run_async(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# CronExpression Tests
# =============================================================================


class TestCronExpression:
    """Tests for CronExpression parsing and matching."""

    def test_parse_valid_expression(self):
        """Test parsing valid cron expression."""
        cron = CronExpression.parse("0 2 * * *")
        assert cron.minute == "0"
        assert cron.hour == "2"
        assert cron.day_of_month == "*"
        assert cron.month == "*"
        assert cron.day_of_week == "*"

    def test_parse_invalid_expression(self):
        """Test parsing invalid cron expression."""
        with pytest.raises(ValueError):
            CronExpression.parse("0 2 *")  # Too few parts

    def test_wildcard_matches_all(self):
        """Test wildcard matches all values."""
        cron = CronExpression.parse("* * * * *")
        now = datetime.now()
        assert cron.matches(now)

    def test_exact_match(self):
        """Test exact value matching."""
        cron = CronExpression.parse("30 14 * * *")
        # 2:30 PM
        dt = datetime(2026, 2, 2, 14, 30, 0)
        assert cron.matches(dt)
        # 2:31 PM should not match
        dt2 = datetime(2026, 2, 2, 14, 31, 0)
        assert not cron.matches(dt2)

    def test_range_match(self):
        """Test range matching."""
        cron = CronExpression.parse("0 9-17 * * *")
        # 9 AM should match
        dt1 = datetime(2026, 2, 2, 9, 0, 0)
        assert cron.matches(dt1)
        # 5 PM should match
        dt2 = datetime(2026, 2, 2, 17, 0, 0)
        assert cron.matches(dt2)
        # 6 PM should not match
        dt3 = datetime(2026, 2, 2, 18, 0, 0)
        assert not cron.matches(dt3)

    def test_step_match(self):
        """Test step value matching."""
        cron = CronExpression.parse("*/15 * * * *")
        # 0, 15, 30, 45 should match
        assert cron.matches(datetime(2026, 2, 2, 10, 0, 0))
        assert cron.matches(datetime(2026, 2, 2, 10, 15, 0))
        assert cron.matches(datetime(2026, 2, 2, 10, 30, 0))
        assert cron.matches(datetime(2026, 2, 2, 10, 45, 0))
        # 10 should not match
        assert not cron.matches(datetime(2026, 2, 2, 10, 10, 0))

    def test_next_run_calculation(self):
        """Test next run time calculation."""
        cron = CronExpression.parse("0 2 * * *")  # 2 AM daily
        after = datetime(2026, 2, 2, 3, 0, 0)  # 3 AM
        next_run = cron.next_run(after)
        # Should be next day at 2 AM
        assert next_run.hour == 2
        assert next_run.minute == 0
        assert next_run.day == 3

    def test_next_run_same_day(self):
        """Test next run on same day."""
        cron = CronExpression.parse("0 14 * * *")  # 2 PM daily
        after = datetime(2026, 2, 2, 10, 0, 0)  # 10 AM
        next_run = cron.next_run(after)
        # Should be same day at 2 PM
        assert next_run.hour == 14
        assert next_run.day == 2


# =============================================================================
# ScheduledTask Tests
# =============================================================================


class TestScheduledTask:
    """Tests for ScheduledTask configuration."""

    def test_create_task(self):
        """Test creating scheduled task."""
        task = ScheduledTask(
            name="test_task",
            schedule="0 2 * * *",
            tool_name="backup",
            parameters={"target": "db"},
        )
        assert task.name == "test_task"
        assert task.min_confidence == 0.7  # Default
        assert task.enabled is True

    def test_min_confidence_validation(self):
        """Test min_confidence must be >= 0.5."""
        with pytest.raises(ValueError):
            ScheduledTask(
                name="test",
                schedule="0 * * * *",
                tool_name="tool",
                parameters={},
                min_confidence=0.3,  # Too low
            )

    def test_custom_min_confidence(self):
        """Test custom min_confidence."""
        task = ScheduledTask(
            name="high_confidence_task",
            schedule="0 * * * *",
            tool_name="critical_tool",
            parameters={},
            min_confidence=0.9,
        )
        assert task.min_confidence == 0.9

    def test_calculate_next_run(self):
        """Test next run calculation."""
        task = ScheduledTask(
            name="test",
            schedule="0 3 * * *",  # 3 AM
            tool_name="tool",
            parameters={},
        )
        after = datetime(2026, 2, 2, 4, 0, 0)
        next_run = task.calculate_next_run(after)
        assert next_run.hour == 3
        assert next_run.day == 3

    def test_to_dict(self):
        """Test serialization."""
        task = ScheduledTask(
            name="test_task",
            schedule="0 2 * * *",
            tool_name="backup",
            parameters={"target": "db"},
            description="Daily backup",
        )
        d = task.to_dict()
        assert d["name"] == "test_task"
        assert d["schedule"] == "0 2 * * *"
        assert d["tool_name"] == "backup"
        assert d["description"] == "Daily backup"


class TestCreateTaskFactory:
    """Tests for create_task factory function."""

    def test_create_task_minimal(self):
        """Test creating task with minimal parameters."""
        task = create_task(
            name="simple_task",
            schedule="0 * * * *",
            tool_name="ping",
        )
        assert task.name == "simple_task"
        assert task.parameters == {}
        assert task.min_confidence == 0.7

    def test_create_task_full(self):
        """Test creating task with all parameters."""
        task = create_task(
            name="full_task",
            schedule="30 8 * * 1-5",
            tool_name="send_report",
            parameters={"to": "team@example.com"},
            min_confidence=0.8,
            description="Weekly report",
        )
        assert task.name == "full_task"
        assert task.parameters["to"] == "team@example.com"
        assert task.min_confidence == 0.8


# =============================================================================
# ProactiveScheduler Tests
# =============================================================================


class TestProactiveSchedulerCreation:
    """Tests for ProactiveScheduler creation."""

    def test_default_disabled(self):
        """Test scheduler is disabled by default."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)
        assert scheduler.enabled is False

    def test_explicitly_enabled(self):
        """Test scheduler can be explicitly enabled."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)
        assert scheduler.enabled is True

    def test_enable_disable(self):
        """Test enable/disable methods."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        assert scheduler.enabled is False
        scheduler.enable()
        assert scheduler.enabled is True
        scheduler.disable()
        assert scheduler.enabled is False


class TestProactiveSchedulerTasks:
    """Tests for task management."""

    def test_add_task(self):
        """Test adding a task."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("test", "0 * * * *", "tool")
        scheduler.add_task(task)

        assert "test" in [t.name for t in scheduler.list_tasks()]

    def test_add_duplicate_task(self):
        """Test adding duplicate task raises error."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task1 = create_task("test", "0 * * * *", "tool")
        scheduler.add_task(task1)

        task2 = create_task("test", "0 * * * *", "tool2")
        with pytest.raises(ValueError):
            scheduler.add_task(task2)

    def test_remove_task(self):
        """Test removing a task."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("test", "0 * * * *", "tool")
        scheduler.add_task(task)
        assert scheduler.remove_task("test") is True
        assert scheduler.remove_task("nonexistent") is False

    def test_get_task(self):
        """Test getting task by name."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("test", "0 * * * *", "tool")
        scheduler.add_task(task)

        retrieved = scheduler.get_task("test")
        assert retrieved is not None
        assert retrieved.name == "test"
        assert scheduler.get_task("nonexistent") is None

    def test_enable_disable_task(self):
        """Test enabling/disabling specific tasks."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("test", "0 * * * *", "tool")
        scheduler.add_task(task)

        scheduler.disable_task("test")
        assert scheduler.get_task("test").enabled is False

        scheduler.enable_task("test")
        assert scheduler.get_task("test").enabled is True


class TestProactiveSchedulerDueTasks:
    """Tests for due task detection."""

    def test_get_due_tasks_empty(self):
        """Test no due tasks when empty."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)
        assert scheduler.get_due_tasks() == []

    def test_get_due_tasks_future(self):
        """Test no due tasks when all in future."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        # Task scheduled for far future
        task = create_task("future", "0 0 1 1 *", "tool")  # Jan 1 midnight
        scheduler.add_task(task)

        due = scheduler.get_due_tasks(now=datetime(2026, 2, 2, 12, 0, 0))
        assert len(due) == 0

    def test_get_due_tasks_past(self):
        """Test due tasks when next_run is in past."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("past", "0 * * * *", "tool")
        scheduler.add_task(task)
        # Force next_run to be in past
        task._next_run = datetime(2026, 2, 1, 12, 0, 0)

        due = scheduler.get_due_tasks(now=datetime(2026, 2, 2, 12, 0, 0))
        assert len(due) == 1
        assert due[0].name == "past"

    def test_disabled_tasks_not_due(self):
        """Test disabled tasks not returned as due."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway)

        task = create_task("disabled", "0 * * * *", "tool")
        scheduler.add_task(task)
        task._next_run = datetime(2026, 2, 1, 12, 0, 0)
        task.enabled = False

        due = scheduler.get_due_tasks(now=datetime(2026, 2, 2, 12, 0, 0))
        assert len(due) == 0


class TestProactiveSchedulerExecution:
    """Tests for task execution."""

    def test_execute_task_success(self):
        """Test successful task execution."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task("search_task", "0 * * * *", "search", {"query": "test"})
        scheduler.add_task(task)

        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.9,
            trajectory_confidence=0.9,
        )

        record = run_async(scheduler.execute_task(task, signals))
        assert record.success is True
        assert record.task_name == "search_task"

    def test_execute_task_low_confidence(self):
        """Test task blocked due to low confidence."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task(
            "high_confidence_task",
            "0 * * * *",
            "search",
            min_confidence=0.9,
        )
        scheduler.add_task(task)

        signals = ConfidenceSignals(
            quality_score=0.5,
            coherence_score=0.5,
            trajectory_confidence=0.5,
        )

        record = run_async(scheduler.execute_task(task, signals))
        assert record.success is False
        assert record.blocked_reason == "low_confidence"

    def test_execute_task_human_review_no_callback(self):
        """Test task requiring human review without callback."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = ScheduledTask(
            name="review_task",
            schedule="0 * * * *",
            tool_name="search",
            parameters={},
            require_human_review=True,
        )
        scheduler.add_task(task)

        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.9,
        )

        record = run_async(scheduler.execute_task(task, signals))
        assert record.success is False
        assert record.blocked_reason == "no_human_callback"

    def test_execute_task_human_review_denied(self):
        """Test task denied by human review."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(
            mcp_gateway=gateway,
            enabled=True,
            human_confirmation_callback=lambda q: False,  # Always deny
        )

        task = ScheduledTask(
            name="denied_task",
            schedule="0 * * * *",
            tool_name="search",
            parameters={},
            require_human_review=True,
        )
        scheduler.add_task(task)

        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.9,
        )

        record = run_async(scheduler.execute_task(task, signals))
        assert record.success is False
        assert record.blocked_reason == "human_denied"

    def test_execute_task_human_review_approved(self):
        """Test task approved by human review."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(
            mcp_gateway=gateway,
            enabled=True,
            human_confirmation_callback=lambda q: True,  # Always approve
        )

        task = ScheduledTask(
            name="approved_task",
            schedule="0 * * * *",
            tool_name="search",
            parameters={"query": "test"},
            require_human_review=True,
        )
        scheduler.add_task(task)

        signals = ConfidenceSignals(
            quality_score=0.9,
            coherence_score=0.9,
        )

        record = run_async(scheduler.execute_task(task, signals))
        assert record.success is True
        assert record.human_confirmed is True


class TestProactiveSchedulerRunOnce:
    """Tests for run_once method."""

    def test_run_once_disabled(self):
        """Test run_once does nothing when disabled."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=False)

        task = create_task("task", "0 * * * *", "search")
        scheduler.add_task(task)
        task._next_run = datetime(2020, 1, 1)  # Past

        records = run_async(scheduler.run_once())
        assert len(records) == 0

    def test_run_once_enabled(self):
        """Test run_once executes due tasks when enabled."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task("task", "0 * * * *", "search", {"query": "test"})
        scheduler.add_task(task)
        task._next_run = datetime(2020, 1, 1)  # Past

        records = run_async(scheduler.run_once())
        assert len(records) == 1
        assert records[0].task_name == "task"


class TestProactiveSchedulerHistory:
    """Tests for execution history."""

    def test_get_execution_history(self):
        """Test getting execution history."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task("task", "0 * * * *", "search", {"query": "test"})
        scheduler.add_task(task)
        task._next_run = datetime(2020, 1, 1)

        run_async(scheduler.run_once())

        history = scheduler.get_execution_history()
        assert len(history) == 1

    def test_filter_by_task_name(self):
        """Test filtering history by task name."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task1 = create_task("task1", "0 * * * *", "search", {"query": "test"})
        task2 = create_task("task2", "0 * * * *", "search", {"query": "test2"})
        scheduler.add_task(task1)
        scheduler.add_task(task2)
        task1._next_run = datetime(2020, 1, 1)
        task2._next_run = datetime(2020, 1, 1)

        run_async(scheduler.run_once())

        history = scheduler.get_execution_history(task_name="task1")
        assert len(history) == 1
        assert history[0].task_name == "task1"

    def test_filter_success_only(self):
        """Test filtering successful executions only."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        # Successful task
        task1 = create_task("success", "0 * * * *", "search", {"query": "test"})
        # Task that will fail (low confidence)
        task2 = create_task("fail", "0 * * * *", "search", min_confidence=0.99)
        scheduler.add_task(task1)
        scheduler.add_task(task2)
        task1._next_run = datetime(2020, 1, 1)
        task2._next_run = datetime(2020, 1, 1)

        run_async(scheduler.run_once())

        success_only = scheduler.get_execution_history(success_only=True)
        failed_only = scheduler.get_execution_history(failed_only=True)

        assert len(success_only) == 1
        assert success_only[0].success is True
        assert len(failed_only) == 1
        assert failed_only[0].success is False


class TestProactiveSchedulerStatistics:
    """Tests for scheduler statistics."""

    def test_get_statistics(self):
        """Test getting statistics."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task("task", "0 * * * *", "search", {"query": "test"})
        scheduler.add_task(task)
        task._next_run = datetime(2020, 1, 1)

        run_async(scheduler.run_once())

        stats = scheduler.get_statistics()
        assert stats["enabled"] is True
        assert stats["total_tasks"] == 1
        assert stats["total_executions"] == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        # Add successful and failing tasks
        task1 = create_task("success", "0 * * * *", "search", {"query": "test"})
        task2 = create_task("fail", "0 * * * *", "search", min_confidence=0.99)
        scheduler.add_task(task1)
        scheduler.add_task(task2)
        task1._next_run = datetime(2020, 1, 1)
        task2._next_run = datetime(2020, 1, 1)

        run_async(scheduler.run_once())

        stats = scheduler.get_statistics()
        assert stats["successful_executions"] == 1
        assert stats["failed_executions"] == 1
        assert stats["success_rate"] == 0.5


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_proactive_scheduler(self):
        """Test create_proactive_scheduler factory."""
        gateway = create_mock_mcp_gateway()
        scheduler = create_proactive_scheduler(
            mcp_gateway=gateway,
            enabled=True,
            default_min_confidence=0.8,
        )

        assert scheduler.enabled is True
        assert scheduler.default_min_confidence == 0.8

    def test_create_proactive_scheduler_default_disabled(self):
        """Test factory creates disabled scheduler by default."""
        gateway = create_mock_mcp_gateway()
        scheduler = create_proactive_scheduler(mcp_gateway=gateway)

        assert scheduler.enabled is False


class TestExecutionRecord:
    """Tests for ExecutionRecord."""

    def test_to_dict(self):
        """Test serialization."""
        record = ExecutionRecord(
            task_name="test",
            timestamp=datetime(2026, 2, 2, 12, 0, 0),
            tool_name="search",
            parameters={"query": "test"},
            success=True,
            result="found",
            confidence_score=0.9,
            risk_level=ToolRiskLevel.READ_ONLY,
        )

        d = record.to_dict()
        assert d["task_name"] == "test"
        assert d["success"] is True
        assert d["risk_level"] == "read_only"


class TestSchedulerSerialization:
    """Tests for scheduler serialization."""

    def test_to_dict(self):
        """Test scheduler to_dict."""
        gateway = create_mock_mcp_gateway()
        scheduler = ProactiveScheduler(mcp_gateway=gateway, enabled=True)

        task = create_task("task", "0 * * * *", "search")
        scheduler.add_task(task)

        d = scheduler.to_dict()
        assert d["enabled"] is True
        assert len(d["tasks"]) == 1
        assert "statistics" in d
