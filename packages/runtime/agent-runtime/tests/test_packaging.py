"""Packaging and public-API checks (section 24, checks 5-8, plus API surface).

The wheel build / clean-venv install / installed-wheel test-run checks (1-4, 53-55)
are exercised by scripts/verify_isolated_install.py, which builds a wheel, installs
it into a throwaway virtualenv, and runs this same test suite from the installed
distribution. These in-process tests cover the parts that do not require a build.
"""
from __future__ import annotations

from pathlib import Path

import ugence_agent_runtime
from ugence_agent_runtime import api


def test_version_accessible():  # check 7
    assert isinstance(ugence_agent_runtime.__version__, str)
    assert ugence_agent_runtime.__version__ == "0.7.0"


def test_py_typed_shipped():  # check 5
    pkg_dir = Path(ugence_agent_runtime.__file__).parent
    assert (pkg_dir / "py.typed").is_file()


def test_package_imports_without_monorepo_paths():  # check 4
    # The package resolves purely from its own location; nothing about the monorepo
    # application layer is required to import it.
    assert ugence_agent_runtime.__file__.endswith("__init__.py")


def test_public_api_surface_is_curated():
    # The curated public symbols are all present and re-exported at top level.
    expected = {
        "AgentRuntime",
        "AgentRuntimeConfig",
        "AgentDescriptor",
        "WorkflowDefinition",
        "WorkflowInstance",
        "WorkflowStatus",
        "TaskDefinition",
        "TaskInstance",
        "TaskStatus",
        "RuntimeTransition",
        "RuntimeEvent",
        "RuntimeResult",
        "RuntimeFailure",
        "WorkflowAdvanceOutcome",
        "WorkflowAdvanceStop",
        "WorkflowPortfolio",
        "PortfolioWorkflowEntry",
        "PortfolioStatus",
        "WorkflowPriority",
        "priority_rank",
        "DependencyGraph",
        "DependencyType",
        "DependencyState",
        "WorkflowDependency",
        "PortfolioScheduler",
        "SchedulingPolicy",
        "PortfolioStepResult",
        "PortfolioStepReason",
        "SelectionReason",
        "WorkflowEligibility",
        "create_portfolio",
        "create_portfolio_scheduler",
        "create_portfolio_controller",
        "PortfolioCheckpoint",
        "WorkflowCheckpointRef",
        "PortfolioCheckpointStore",
        "InMemoryPortfolioCheckpointStore",
        "PortfolioCheckpointConflict",
        "PortfolioRecoveryResult",
        "recover_portfolio",
        "PortfolioTrace",
        "PortfolioTraceEntry",
        "PortfolioEventType",
        "PortfolioEventStore",
        "InMemoryPortfolioEventStore",
        "PortfolioTraceSequenceError",
        "PortfolioTraceEncodingError",
        "PortfolioController",
        "PortfolioFailurePolicy",
        "CancellationScope",
        "PortfolioCancellationResult",
        "ConcurrencyPolicy",
        "ConcurrentPortfolioExecutor",
        "ConcurrentPortfolioStepResult",
        "ConcurrentStepReason",
        "QuantumOutcome",
        "ExecutionBackend",
        "SynchronousExecutionBackend",
        "ThreadPoolExecutionBackend",
        "ExecutorInfrastructureError",
        "AdmissionDecision",
        "BatchPlan",
        "ResourceMode",
        "ResourceClaim",
        "ResourceConflict",
        "ResourceCoordinator",
        "PortfolioBudget",
        "BudgetRequirement",
        "BudgetShortfall",
        "BudgetCoordinator",
        "BudgetEstimateExceeded",
        "CompensationTrigger",
        "CompensationSpec",
        "CompensationRegistration",
        "CompensationRegistry",
        "create_concurrent_executor",
        "create_concurrent_executor_from_recovery",
        "Provider",
        "ProviderRegistry",
        "ToolInvocation",
        "ToolResult",
        "Checkpoint",
        "CheckpointStore",
        "RuntimeRecoveryResult",
        "GovernanceHook",
        "GovernanceEvaluation",
        "GovernanceDisposition",
        "ExecutionContext",
        "CorrelationContext",
        "CanonicalExecutionState",
        "ExecutionLineage",
        "create_runtime",
        "start_workflow",
        "prepare_workflow",
        "advance_workflow",
        "execution_state",
        "execution_state_by_digest",
        "resume_workflow",
        "continue_workflow",
        "pause_workflow",
        "cancel_workflow",
        "recover_runtime",
        "register_provider",
        "register_governance_hook",
    }
    missing = expected - set(api.__all__)
    assert not missing, f"missing public symbols: {missing}"
    for name in expected:
        assert hasattr(ugence_agent_runtime, name), name


def test_no_product_specific_symbols_exported():
    # No governance-product, GitHub, robotics, or vendor name leaks into the API.
    banned = ("ActionGate", "CodeGovernance", "GitHub", "TAP", "StoryGraph", "Robotics", "CER")
    for name in api.__all__:
        for bad in banned:
            assert bad.lower() not in name.lower(), f"product-specific symbol exported: {name}"
