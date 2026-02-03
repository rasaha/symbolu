"""
Coding Tools for Sentinel Agentic Framework

This module provides coding capabilities for the Sentinel framework:

File Operations:
- FileReadTool: Read files with line numbers
- FileWriteTool: Create/overwrite files
- FileEditTool: Precise string replacement

Code Search:
- GlobTool: Find files by pattern
- GrepTool: Search file contents with regex

Code Quality:
- CodeCritic: Code quality evaluation (syntax, lint, security)

Code Execution:
- SandboxExecutor: Execute code in isolated subprocess
- CodeRunner: High-level code execution interface

Version Control:
- GitTools: Git operations (status, diff, log, commit, push)

Project Understanding:
- ProjectAnalyzer: Detect project structure, dependencies, framework

Test Execution:
- TestRunner: Discover and run tests

Usage:
    from symbolu.agentic_framework.coding_tools import (
        FileReadTool, FileEditTool, GlobTool, GrepTool,
        CodeCritic, CodeRunner, GitTools, ProjectAnalyzer, TestRunner,
    )

    # File operations
    reader = FileReadTool()
    result = reader.read("/path/to/file.py")

    editor = FileEditTool()
    result = editor.edit("/path/to/file.py", "old_code", "new_code")

    # Code search
    glob = GlobTool()
    result = glob.search("**/*.py")

    grep = GrepTool()
    result = grep.search(r"def\\s+\\w+", file_type="py")

    # Code quality
    critic = CodeCritic(language="python")
    critique = critic.evaluate(code)

    # Code execution
    runner = CodeRunner()
    result = runner.run(code, language="python")

    # Git
    git = GitTools()
    status = git.status()
    git.add(["file.py"])
    git.commit("Fix bug")

    # Project understanding
    analyzer = ProjectAnalyzer()
    context = analyzer.analyze()

    # Testing
    test_runner = TestRunner()
    result = test_runner.run()
"""

from symbolu.agentic_framework.coding_tools.file_tools import (
    # Result types
    FileReadResult,
    FileWriteResult,
    FileEditResult,
    # Tools
    FileReadTool,
    FileWriteTool,
    FileEditTool,
    # MCP handlers
    create_file_read_handler,
    create_file_write_handler,
    create_file_edit_handler,
)

from symbolu.agentic_framework.coding_tools.search_tools import (
    # Result types
    GlobResult,
    GrepMatch,
    GrepResult,
    # Tools
    GlobTool,
    GrepTool,
    # MCP handlers
    create_glob_handler,
    create_grep_handler,
)

from symbolu.agentic_framework.coding_tools.code_critic import (
    # Types
    IssueSeverity,
    IssueCategory,
    CodeIssue,
    CodeCritique,
    # Analyzers
    PythonAnalyzer,
    JavaScriptAnalyzer,
    # Main critic
    CodeCritic,
    # MCP handler
    create_code_critic_handler,
)

from symbolu.agentic_framework.coding_tools.sandbox import (
    # Types
    ExecutionStatus,
    ExecutionResult,
    SandboxConfig,
    # Executors
    SandboxExecutor,
    CodeRunner,
    # MCP handler
    create_code_execute_handler,
)

from symbolu.agentic_framework.coding_tools.git_tools import (
    # Types
    GitOperationType,
    GitStatus,
    GitCommit,
    GitResult,
    # Tools
    GitTools,
    # MCP handlers
    create_git_status_handler,
    create_git_diff_handler,
    create_git_log_handler,
    create_git_commit_handler,
    create_git_push_handler,
)

from symbolu.agentic_framework.coding_tools.project_context import (
    ProjectContext,
    ProjectAnalyzer,
    create_project_context_handler,
)

from symbolu.agentic_framework.coding_tools.test_runner import (
    # Types
    TestStatus,
    TestFramework,
    TestCase,
    TestResult,
    # Runner
    TestRunner,
    # MCP handler
    create_test_runner_handler,
)


# =============================================================================
# Factory Function for All Coding Tools
# =============================================================================


def create_coding_tools_gateway():
    """
    Create a SafeMCPGateway pre-configured with all coding tools.

    Returns:
        SafeMCPGateway with coding tools registered
    """
    from symbolu.agentic_framework.mcp_gateway import (
        MockMCPClient,
        SafeMCPGateway,
        MCPToolDefinition,
        ToolRiskLevel,
        create_safe_mcp_gateway,
    )

    # Create mock client with coding tools
    client = MockMCPClient()

    # File tools
    client.register_tool("file_read", create_file_read_handler(), ToolRiskLevel.READ_ONLY)
    client.register_tool("file_write", create_file_write_handler(), ToolRiskLevel.WRITE)
    client.register_tool("file_edit", create_file_edit_handler(), ToolRiskLevel.WRITE)

    # Search tools
    client.register_tool("glob", create_glob_handler(), ToolRiskLevel.READ_ONLY)
    client.register_tool("grep", create_grep_handler(), ToolRiskLevel.READ_ONLY)

    # Code quality
    client.register_tool("code_critic", create_code_critic_handler(), ToolRiskLevel.READ_ONLY)

    # Code execution
    client.register_tool("code_execute", create_code_execute_handler(), ToolRiskLevel.EXECUTE)

    # Git tools
    client.register_tool("git_status", create_git_status_handler(), ToolRiskLevel.READ_ONLY)
    client.register_tool("git_diff", create_git_diff_handler(), ToolRiskLevel.READ_ONLY)
    client.register_tool("git_log", create_git_log_handler(), ToolRiskLevel.READ_ONLY)
    client.register_tool("git_commit", create_git_commit_handler(), ToolRiskLevel.WRITE)
    client.register_tool("git_push", create_git_push_handler(), ToolRiskLevel.PRIVILEGED)

    # Project context
    client.register_tool("project_context", create_project_context_handler(), ToolRiskLevel.READ_ONLY)

    # Test runner
    client.register_tool("test_run", create_test_runner_handler(), ToolRiskLevel.EXECUTE)

    return create_safe_mcp_gateway(mcp_client=client)


# =============================================================================
# Version
# =============================================================================

__version__ = "1.0.0"


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Version
    "__version__",

    # File tools
    "FileReadResult",
    "FileWriteResult",
    "FileEditResult",
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "create_file_read_handler",
    "create_file_write_handler",
    "create_file_edit_handler",

    # Search tools
    "GlobResult",
    "GrepMatch",
    "GrepResult",
    "GlobTool",
    "GrepTool",
    "create_glob_handler",
    "create_grep_handler",

    # Code critic
    "IssueSeverity",
    "IssueCategory",
    "CodeIssue",
    "CodeCritique",
    "PythonAnalyzer",
    "JavaScriptAnalyzer",
    "CodeCritic",
    "create_code_critic_handler",

    # Sandbox
    "ExecutionStatus",
    "ExecutionResult",
    "SandboxConfig",
    "SandboxExecutor",
    "CodeRunner",
    "create_code_execute_handler",

    # Git tools
    "GitOperationType",
    "GitStatus",
    "GitCommit",
    "GitResult",
    "GitTools",
    "create_git_status_handler",
    "create_git_diff_handler",
    "create_git_log_handler",
    "create_git_commit_handler",
    "create_git_push_handler",

    # Project context
    "ProjectContext",
    "ProjectAnalyzer",
    "create_project_context_handler",

    # Test runner
    "TestStatus",
    "TestFramework",
    "TestCase",
    "TestResult",
    "TestRunner",
    "create_test_runner_handler",

    # Factory
    "create_coding_tools_gateway",
]
