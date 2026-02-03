# Sentinel Framework - Coding Capability Gap Analysis

**Date:** 2026-02-03
**Purpose:** Identify what's needed to enable Sentinel to handle coding tasks like Claude Code
**Status:** Gap Analysis & Implementation Roadmap

---

## Executive Summary

Sentinel is a **general-purpose agentic framework** optimized for reliability, safety, and auditability. While it has strong foundational components (safety contracts, confidence gating, memory, MCP tool integration), it lacks **coding-specific capabilities** that would allow it to perform development tasks at the level of purpose-built coding assistants like Claude Code.

This document identifies the gaps and provides an implementation roadmap to bridge them.

---

## Current Sentinel Capabilities

### Strengths (Already Present)

| Component | File | Capability |
|-----------|------|------------|
| **Safety Contract** | `safety_contract.py` | Fail-closed gating with 6 preconditions |
| **Confidence Gate** | `confidence_gate.py` | Behavioral control based on confidence signals |
| **MCP Gateway** | `mcp_gateway.py` | Safe tool execution with risk classification |
| **Memory Store** | `memory_store.py` | Append-only session memory with semantic retrieval |
| **Quality Critics** | `local_critic.py` | Multi-dimensional quality evaluation |
| **Goal Decomposition** | `goal_decomposition.py` | Intent extraction to ActionItems |
| **Reflective Loop** | `reflective_loop.py` | Self-revising generation |
| **Adaptive Policy** | `adaptive_policy.py` | Per-session behavior tuning |

### Current Action Types (goal_decomposition.py)

```python
ActionItem.action_type: str  # "search", "compute", "generate", "validate", "execute"
```

These are **generic** action types - none are code-specific.

---

## Gap Analysis: What's Missing for Coding

### Gap 1: Code-Specific Action Types

**Current State:** Generic action types only
**Required:** Code-aware action taxonomy

| Missing Action Type | Description | Example |
|---------------------|-------------|---------|
| `code_read` | Read and parse source file | Read `main.py` lines 50-100 |
| `code_edit` | Modify existing code | Replace function body |
| `code_write` | Create new file | Create `utils.py` |
| `code_execute` | Run code/tests | `pytest tests/` |
| `code_lint` | Static analysis | Run flake8, mypy |
| `code_search` | Semantic code search | Find all usages of `UserService` |
| `code_refactor` | Structural changes | Rename variable across files |
| `git_operation` | Version control | Commit, push, branch |

**Implementation Location:** `goal_decomposition.py`

---

### Gap 2: Code Execution Sandbox

**Current State:** MCP Gateway executes tools but no code sandbox
**Required:** Isolated execution environment for code

```
┌─────────────────────────────────────────────────────────┐
│                    Sentinel Agent                        │
│                                                          │
│  ┌──────────────┐     ┌──────────────────────────────┐  │
│  │ Goal         │────▶│ Code Execution Sandbox       │  │
│  │ Decomposer   │     │ ┌──────────────────────────┐ │  │
│  └──────────────┘     │ │ - Process isolation      │ │  │
│                       │ │ - Filesystem sandboxing  │ │  │
│  ┌──────────────┐     │ │ - Network restrictions   │ │  │
│  │ MCP Gateway  │────▶│ │ - Resource limits        │ │  │
│  │              │     │ │ - Timeout enforcement    │ │  │
│  └──────────────┘     │ └──────────────────────────┘ │  │
│                       └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Missing Components:**
1. **Process Isolation:** Run code in subprocess with restricted permissions
2. **Filesystem Sandboxing:** Limit file access to project directory
3. **Network Control:** Block external network by default
4. **Resource Limits:** CPU, memory, execution time limits
5. **Cleanup:** Automatic cleanup of temp files

**Implementation Approach:**
- Use Python `subprocess` with `preexec_fn` for Unix
- Docker container execution (optional, more secure)
- Windows: Job Objects for resource limits

---

### Gap 3: Code-Specific Quality Critics

**Current State:** Generic quality dimensions (coherence, correctness, completeness, relevance)
**Required:** Code-aware evaluation

| Current Critic | Missing Code Dimension |
|----------------|------------------------|
| Coherence | **Syntax Validity** - Does the code parse? |
| Correctness | **Semantic Correctness** - Does it do what's intended? |
| Completeness | **Implementation Completeness** - All edge cases handled? |
| Relevance | **Style Conformance** - Follows project conventions? |

**Additional Code-Specific Metrics:**

```python
@dataclass
class CodeQualityCritique:
    # Syntax
    syntax_valid: bool
    parse_errors: List[str]

    # Static Analysis
    lint_warnings: List[str]
    type_errors: List[str]

    # Semantic
    logic_correct: float  # 0.0-1.0
    edge_cases_handled: float

    # Style
    style_conformance: float
    naming_consistency: float

    # Security
    security_issues: List[str]
    injection_risks: List[str]

    # Performance
    complexity_score: float  # Cyclomatic complexity
    obvious_inefficiencies: List[str]
```

**Implementation Location:** New file `code_critic.py`

---

### Gap 4: File Editing Tools

**Current State:** No direct file manipulation tools
**Required:** Precise file editing capabilities

| Tool | Capability | Claude Code Equivalent |
|------|------------|------------------------|
| `FileRead` | Read file with line numbers | `Read` tool |
| `FileWrite` | Create/overwrite file | `Write` tool |
| `FileEdit` | Surgical string replacement | `Edit` tool |
| `FileSearch` | Glob pattern matching | `Glob` tool |
| `ContentSearch` | Regex search in files | `Grep` tool |

**Critical Requirement:** The `FileEdit` tool must support:
- Exact string matching (not regex by default)
- Line number context
- Indentation preservation
- Atomic operations (no partial edits)

**Implementation:**
```python
@dataclass
class FileEditRequest:
    file_path: str
    old_string: str  # Must be unique in file
    new_string: str
    replace_all: bool = False

class FileEditTool:
    def execute(self, request: FileEditRequest) -> FileEditResult:
        # 1. Read file
        # 2. Verify old_string uniqueness
        # 3. Replace
        # 4. Write atomically (temp file + rename)
        # 5. Return result with diff
```

---

### Gap 5: Language Server Integration

**Current State:** No IDE-like intelligence
**Required:** Language-aware code understanding

**Missing Capabilities:**

| Capability | Purpose | Implementation |
|------------|---------|----------------|
| **Go to Definition** | Navigate to symbol definition | LSP `textDocument/definition` |
| **Find References** | Find all usages | LSP `textDocument/references` |
| **Hover Info** | Type/docstring at position | LSP `textDocument/hover` |
| **Completions** | Code completion suggestions | LSP `textDocument/completion` |
| **Diagnostics** | Real-time errors/warnings | LSP `textDocument/publishDiagnostics` |

**Implementation Options:**

1. **Direct LSP Integration**
   - Start language server subprocess
   - Communicate via JSON-RPC
   - Pro: Full IDE intelligence
   - Con: Complex, per-language setup

2. **Tree-sitter Parsing**
   - Language-agnostic AST parsing
   - Pro: Fast, many languages
   - Con: Less semantic info

3. **Regex-Based (Fallback)**
   - Pattern matching for symbols
   - Pro: Simple, no dependencies
   - Con: Limited accuracy

**Recommended:** Tree-sitter for parsing + optional LSP for detailed analysis

---

### Gap 6: Version Control Integration

**Current State:** No git awareness
**Required:** Full git workflow support

```python
class GitTools:
    """Git operations through SafeMCPGateway."""

    # Read Operations (LOW risk)
    async def status(self) -> GitStatus: ...
    async def diff(self, staged: bool = False) -> str: ...
    async def log(self, n: int = 10) -> List[GitCommit]: ...
    async def branch_list(self) -> List[str]: ...

    # Write Operations (MEDIUM risk)
    async def add(self, paths: List[str]) -> bool: ...
    async def commit(self, message: str) -> str: ...
    async def checkout(self, branch: str) -> bool: ...
    async def create_branch(self, name: str) -> bool: ...

    # Network Operations (HIGH risk, requires confirmation)
    async def push(self, branch: str, force: bool = False) -> bool: ...
    async def pull(self, branch: str) -> bool: ...
    async def fetch(self) -> bool: ...

    # Destructive Operations (PRIVILEGED, requires confirmation)
    async def reset_hard(self, ref: str) -> bool: ...
    async def force_push(self) -> bool: ...  # Should warn on main/master
```

---

### Gap 7: Project Context Understanding

**Current State:** Memory store has generic context
**Required:** Code-aware project context

```python
@dataclass
class ProjectContext:
    """Understanding of the codebase structure."""

    # Structure
    root_path: Path
    language: str  # Primary language
    languages: Dict[str, int]  # Language -> file count
    framework: Optional[str]  # Django, React, etc.

    # Files
    file_tree: Dict[str, List[str]]  # Directory -> files
    entry_points: List[str]  # main.py, index.ts, etc.
    config_files: List[str]  # package.json, pyproject.toml

    # Dependencies
    dependencies: Dict[str, str]  # Package -> version
    dev_dependencies: Dict[str, str]

    # Patterns
    import_graph: Dict[str, List[str]]  # File -> imports
    export_map: Dict[str, List[str]]  # File -> exported symbols

    # Conventions
    naming_convention: str  # snake_case, camelCase
    indent_style: str  # spaces, tabs
    indent_size: int
```

**Implementation:** Parse common config files + AST analysis

---

### Gap 8: Test Execution & Validation

**Current State:** No test awareness
**Required:** Test discovery, execution, and result analysis

```python
class TestRunner:
    """Discovers and runs tests."""

    async def discover(self, path: str) -> List[TestCase]:
        """Find all tests in path."""
        ...

    async def run(
        self,
        tests: List[str],
        coverage: bool = False,
    ) -> TestResult:
        """Run tests and return results."""
        ...

    async def run_affected(
        self,
        changed_files: List[str],
    ) -> TestResult:
        """Run only tests affected by changes."""
        ...

@dataclass
class TestResult:
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    failures: List[TestFailure]
    coverage: Optional[CoverageReport]
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

| Task | Files to Create/Modify | Priority |
|------|------------------------|----------|
| Add code action types | `goal_decomposition.py` | P0 |
| Implement FileEdit tool | `tools/file_edit.py` (new) | P0 |
| Implement FileRead tool | `tools/file_read.py` (new) | P0 |
| Implement FileWrite tool | `tools/file_write.py` (new) | P0 |
| Register tools in MCP Gateway | `mcp_gateway.py` | P0 |

### Phase 2: Code Intelligence (Week 3-4)

| Task | Files to Create/Modify | Priority |
|------|------------------------|----------|
| Implement CodeCritic | `code_critic.py` (new) | P1 |
| Add syntax validation | `code_critic.py` | P1 |
| Implement code search (Glob, Grep) | `tools/code_search.py` (new) | P1 |
| Basic project context | `project_context.py` (new) | P1 |

### Phase 3: Execution (Week 5-6)

| Task | Files to Create/Modify | Priority |
|------|------------------------|----------|
| Code execution sandbox | `sandbox/executor.py` (new) | P1 |
| Git tools integration | `tools/git_tools.py` (new) | P1 |
| Test runner integration | `tools/test_runner.py` (new) | P2 |
| Update risk classifier for code tools | `mcp_gateway.py` | P1 |

### Phase 4: Advanced Features (Week 7-8)

| Task | Files to Create/Modify | Priority |
|------|------------------------|----------|
| LSP integration (optional) | `lsp/client.py` (new) | P2 |
| Tree-sitter parsing | `parsing/tree_sitter.py` (new) | P2 |
| Import graph analysis | `project_context.py` | P2 |
| Affected test detection | `tools/test_runner.py` | P3 |

---

## Detailed Component Specifications

### 1. Code Action Types Extension

```python
# goal_decomposition.py - Extended ActionItem types

CODE_ACTION_TYPES = {
    # File Operations
    "code_read": {
        "risk_level": ToolRiskLevel.READ_ONLY,
        "description": "Read source file contents",
    },
    "code_write": {
        "risk_level": ToolRiskLevel.WRITE,
        "description": "Create or overwrite source file",
    },
    "code_edit": {
        "risk_level": ToolRiskLevel.WRITE,
        "description": "Modify existing source file",
    },

    # Analysis
    "code_search": {
        "risk_level": ToolRiskLevel.READ_ONLY,
        "description": "Search for code patterns",
    },
    "code_lint": {
        "risk_level": ToolRiskLevel.READ_ONLY,
        "description": "Run static analysis",
    },

    # Execution
    "code_execute": {
        "risk_level": ToolRiskLevel.EXECUTE,
        "description": "Run code in sandbox",
    },
    "test_run": {
        "risk_level": ToolRiskLevel.EXECUTE,
        "description": "Run test suite",
    },

    # Version Control
    "git_read": {
        "risk_level": ToolRiskLevel.READ_ONLY,
        "description": "Git status, diff, log",
    },
    "git_write": {
        "risk_level": ToolRiskLevel.WRITE,
        "description": "Git add, commit",
    },
    "git_network": {
        "risk_level": ToolRiskLevel.PRIVILEGED,
        "description": "Git push, pull, fetch",
    },
}
```

### 2. Code Critic Implementation

```python
# code_critic.py

from dataclasses import dataclass
from typing import List, Optional
import ast
import subprocess

@dataclass
class CodeCritique:
    """Code-specific quality evaluation."""

    # Syntax
    syntax_valid: bool
    parse_errors: List[str]

    # Lint
    lint_score: float  # 0.0-1.0
    lint_issues: List[LintIssue]

    # Type checking (if available)
    type_errors: List[TypeIssue]

    # Security
    security_issues: List[SecurityIssue]

    # Overall
    overall_score: float
    revision_guidance: str

class CodeCritic:
    """Evaluates code quality."""

    def __init__(self, language: str = "python"):
        self.language = language

    def evaluate(self, code: str, context: Optional[str] = None) -> CodeCritique:
        """Evaluate code quality."""
        critique = CodeCritique(
            syntax_valid=True,
            parse_errors=[],
            lint_score=1.0,
            lint_issues=[],
            type_errors=[],
            security_issues=[],
            overall_score=1.0,
            revision_guidance="",
        )

        # 1. Syntax check
        critique.syntax_valid, critique.parse_errors = self._check_syntax(code)

        # 2. Lint check
        if critique.syntax_valid:
            critique.lint_issues = self._run_linter(code)
            critique.lint_score = max(0, 1.0 - len(critique.lint_issues) * 0.1)

        # 3. Security check
        critique.security_issues = self._check_security(code)

        # 4. Overall score
        critique.overall_score = self._compute_overall(critique)

        # 5. Guidance
        critique.revision_guidance = self._generate_guidance(critique)

        return critique

    def _check_syntax(self, code: str) -> tuple[bool, List[str]]:
        """Check if code parses."""
        if self.language == "python":
            try:
                ast.parse(code)
                return True, []
            except SyntaxError as e:
                return False, [f"Line {e.lineno}: {e.msg}"]
        # Add other languages...
        return True, []

    def _run_linter(self, code: str) -> List[LintIssue]:
        """Run language-specific linter."""
        # Implementation depends on language
        # For Python: run flake8, pylint
        # For JS/TS: run eslint
        return []

    def _check_security(self, code: str) -> List[SecurityIssue]:
        """Check for common security issues."""
        issues = []

        # Python-specific checks
        dangerous_patterns = [
            (r"eval\s*\(", "Use of eval() is dangerous"),
            (r"exec\s*\(", "Use of exec() is dangerous"),
            (r"__import__\s*\(", "Dynamic import can be dangerous"),
            (r"subprocess\.call.*shell\s*=\s*True", "shell=True is dangerous"),
            (r"os\.system\s*\(", "os.system is dangerous, use subprocess"),
        ]

        for pattern, message in dangerous_patterns:
            if re.search(pattern, code):
                issues.append(SecurityIssue(severity="HIGH", message=message))

        return issues
```

### 3. File Edit Tool

```python
# tools/file_edit.py

from dataclasses import dataclass
from pathlib import Path
import tempfile
import shutil

@dataclass
class FileEditResult:
    success: bool
    message: str
    diff: Optional[str] = None
    error: Optional[str] = None

class FileEditTool:
    """Precise file editing with exact string matching."""

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> FileEditResult:
        """
        Edit file by replacing exact string.

        Args:
            file_path: Path to file
            old_string: Exact string to replace (must be unique unless replace_all)
            new_string: Replacement string
            replace_all: If True, replace all occurrences
        """
        path = Path(file_path)

        # Validate
        if not path.exists():
            return FileEditResult(
                success=False,
                message=f"File not found: {file_path}",
                error="FILE_NOT_FOUND",
            )

        # Read current content
        content = path.read_text()

        # Check uniqueness
        count = content.count(old_string)
        if count == 0:
            return FileEditResult(
                success=False,
                message=f"String not found in file",
                error="STRING_NOT_FOUND",
            )

        if count > 1 and not replace_all:
            return FileEditResult(
                success=False,
                message=f"String appears {count} times. Use replace_all=True or provide more context.",
                error="NOT_UNIQUE",
            )

        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        # Atomic write (temp file + rename)
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=path.parent,
            delete=False,
            suffix='.tmp',
        ) as f:
            f.write(new_content)
            temp_path = f.name

        shutil.move(temp_path, path)

        # Generate diff
        diff = self._generate_diff(content, new_content, file_path)

        return FileEditResult(
            success=True,
            message=f"Replaced {count} occurrence(s)",
            diff=diff,
        )
```

### 4. Risk Classification Update

```python
# mcp_gateway.py - Updated patterns

CODE_TOOL_PATTERNS = {
    ToolRiskLevel.READ_ONLY: [
        "file_read", "code_read", "glob", "grep", "search",
        "git_status", "git_diff", "git_log",
    ],
    ToolRiskLevel.WRITE: [
        "file_write", "file_edit", "code_write", "code_edit",
        "git_add", "git_commit",
    ],
    ToolRiskLevel.EXECUTE: [
        "code_execute", "test_run", "build", "lint",
        "bash",  # General shell execution
    ],
    ToolRiskLevel.PRIVILEGED: [
        "git_push", "git_pull", "git_force_push",
        "deploy", "publish",
    ],
    ToolRiskLevel.DESTRUCTIVE: [
        "git_reset_hard", "file_delete", "rm",
        "drop_database", "truncate",
    ],
}
```

---

## Comparison: Sentinel + Extensions vs Claude Code

| Capability | Claude Code | Sentinel (Current) | Sentinel (Extended) |
|------------|-------------|-------------------|---------------------|
| File Read | Native | No | Yes (P0) |
| File Edit | Native | No | Yes (P0) |
| File Write | Native | No | Yes (P0) |
| Code Search | Native (Glob, Grep) | No | Yes (P1) |
| Code Execution | Native (Bash) | Via MCP | Yes + Sandbox (P1) |
| Git Operations | Native | No | Yes (P1) |
| Syntax Validation | Implicit | No | Yes (P1) |
| LSP Integration | No | No | Optional (P2) |
| Safety Gating | Basic | **Advanced** | Advanced |
| Memory/Context | Conversation | **Structured** | Structured |
| Quality Critics | No | **Yes** | Yes + Code |
| Audit Trail | Limited | **Full** | Full |
| Confidence Control | No | **Yes** | Yes |

**Key Insight:** Sentinel has stronger safety/audit infrastructure than Claude Code. The gap is purely in **coding-specific tools and intelligence**.

---

## Estimated Effort

| Phase | Duration | FTE | Components |
|-------|----------|-----|------------|
| Phase 1: Foundation | 2 weeks | 1 | File tools, action types |
| Phase 2: Intelligence | 2 weeks | 1 | CodeCritic, search |
| Phase 3: Execution | 2 weeks | 1.5 | Sandbox, Git, tests |
| Phase 4: Advanced | 2 weeks | 1 | LSP, AST analysis |
| **Total** | **8 weeks** | **~5 FTE-weeks** | |

---

## Recommendation

**Should Sentinel be extended for coding tasks?**

**If the goal is:**
- **General coding assistant** → Use Claude Code (purpose-built, maintained)
- **Coding in specific enterprise context** → Extend Sentinel (audit trails, safety)
- **AI agents that sometimes write code** → Extend Sentinel (unified framework)
- **Maximum coding capability** → Use Claude Code

**Hybrid Approach:**
Sentinel could delegate coding tasks to Claude Code via tool integration, gaining coding capabilities while maintaining Sentinel's safety/audit infrastructure.

```python
# Hypothetical integration
class ClaudeCodeTool:
    """Delegate coding tasks to Claude Code."""

    async def execute(self, task: str) -> str:
        # Call Claude Code CLI
        result = await subprocess.run(
            ["claude", "--print", task],
            capture_output=True,
        )
        return result.stdout
```

---

## Conclusion

Bridging the gap requires:

1. **8 new components** (file tools, code critic, sandbox, git, test runner, project context, search tools, action types)
2. **~8 weeks development** for full parity
3. **Leverage existing infrastructure** (SafetyContract, ConfidenceGate, MCP Gateway)

The investment is justified if:
- Coding is a core use case
- Enterprise audit/safety requirements exist
- Unified agentic framework is preferred over tool-specific solutions

Otherwise, using Claude Code directly (or as a Sentinel tool) is more practical.
