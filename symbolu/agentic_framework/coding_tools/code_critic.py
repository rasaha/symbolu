"""
Code Critic for Quality Evaluation

Provides code-specific quality evaluation for the Sentinel agentic framework:
- Syntax validation
- Static analysis (lint-like checks)
- Security issue detection
- Style conformance checking

Integrates with the existing LocalCritic infrastructure.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Types
# =============================================================================


class IssueSeverity(Enum):
    """Severity levels for code issues."""
    ERROR = "error"      # Must fix (syntax errors, security issues)
    WARNING = "warning"  # Should fix (potential bugs, bad practices)
    INFO = "info"        # Suggestions (style, optimizations)


class IssueCategory(Enum):
    """Categories of code issues."""
    SYNTAX = "syntax"
    SECURITY = "security"
    LINT = "lint"
    TYPE = "type"
    STYLE = "style"
    PERFORMANCE = "performance"
    COMPLEXITY = "complexity"


@dataclass
class CodeIssue:
    """A single code quality issue."""
    category: IssueCategory
    severity: IssueSeverity
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    rule: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "rule": self.rule,
            "suggestion": self.suggestion,
        }


@dataclass
class CodeCritique:
    """
    Complete code quality evaluation.

    Provides multi-dimensional quality assessment for code.
    """
    # Syntax
    syntax_valid: bool = True
    syntax_errors: List[CodeIssue] = field(default_factory=list)

    # Lint/Style
    lint_issues: List[CodeIssue] = field(default_factory=list)

    # Security
    security_issues: List[CodeIssue] = field(default_factory=list)

    # Type issues (if type checking is available)
    type_issues: List[CodeIssue] = field(default_factory=list)

    # Scores (0.0 - 1.0)
    syntax_score: float = 1.0
    lint_score: float = 1.0
    security_score: float = 1.0
    style_score: float = 1.0
    overall_score: float = 1.0

    # Guidance
    revision_guidance: str = ""

    def all_issues(self) -> List[CodeIssue]:
        """Get all issues combined."""
        return (
            self.syntax_errors +
            self.lint_issues +
            self.security_issues +
            self.type_issues
        )

    def error_count(self) -> int:
        """Count error-severity issues."""
        return sum(
            1 for issue in self.all_issues()
            if issue.severity == IssueSeverity.ERROR
        )

    def warning_count(self) -> int:
        """Count warning-severity issues."""
        return sum(
            1 for issue in self.all_issues()
            if issue.severity == IssueSeverity.WARNING
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "syntax_valid": self.syntax_valid,
            "syntax_errors": [i.to_dict() for i in self.syntax_errors],
            "lint_issues": [i.to_dict() for i in self.lint_issues],
            "security_issues": [i.to_dict() for i in self.security_issues],
            "type_issues": [i.to_dict() for i in self.type_issues],
            "syntax_score": self.syntax_score,
            "lint_score": self.lint_score,
            "security_score": self.security_score,
            "style_score": self.style_score,
            "overall_score": self.overall_score,
            "revision_guidance": self.revision_guidance,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
        }


# =============================================================================
# Language-Specific Analyzers
# =============================================================================


class PythonAnalyzer:
    """Python-specific code analysis."""

    # Dangerous patterns
    SECURITY_PATTERNS = [
        (r"\beval\s*\(", "Use of eval() is dangerous - allows arbitrary code execution", "S001"),
        (r"\bexec\s*\(", "Use of exec() is dangerous - allows arbitrary code execution", "S002"),
        (r"__import__\s*\(", "Dynamic import can be dangerous", "S003"),
        (r"subprocess\.call.*shell\s*=\s*True", "shell=True is dangerous - use list of arguments", "S004"),
        (r"os\.system\s*\(", "os.system is dangerous - use subprocess with list arguments", "S005"),
        (r"pickle\.load", "pickle can execute arbitrary code on untrusted data", "S006"),
        (r"yaml\.load\s*\([^,]+\)", "yaml.load without Loader is dangerous - use yaml.safe_load", "S007"),
        (r"input\s*\(.*\)\s*$", "input() in Python 2 evaluates - ensure Python 3", "S008"),
        (r"random\.", "random module is not cryptographically secure - use secrets for security", "S009"),
        (r"md5\(|sha1\(", "MD5/SHA1 are weak for security purposes - use SHA256+", "S010"),
        (r"password\s*=\s*['\"]", "Hardcoded password detected", "S011"),
        (r"api_key\s*=\s*['\"]", "Hardcoded API key detected", "S012"),
        (r"secret\s*=\s*['\"]", "Hardcoded secret detected", "S013"),
    ]

    # Lint patterns (bad practices)
    LINT_PATTERNS = [
        (r"except\s*:", "Bare except clause - catches all exceptions including KeyboardInterrupt", "L001"),
        (r"except Exception:", "Catching generic Exception - be more specific", "L002"),
        (r"print\s*\(", "print() statement - consider using logging", "L003"),
        (r"# TODO|# FIXME|# XXX|# HACK", "TODO/FIXME comment found", "L004"),
        (r"^\s*pass\s*$", "Empty pass statement", "L005"),
        (r"import \*", "Wildcard import - use explicit imports", "L006"),
        (r"== None|!= None", "Use 'is None' or 'is not None' for None comparison", "L007"),
        (r"== True|== False", "Don't compare to True/False explicitly", "L008"),
        (r"\.keys\(\)\s*\)", "dict.keys() is often unnecessary", "L009"),
        (r"len\([^)]+\)\s*[><=]=?\s*0", "Use truthiness instead of len() comparison", "L010"),
        (r"type\([^)]+\)\s*==", "Use isinstance() instead of type() comparison", "L011"),
    ]

    # Style patterns
    STYLE_PATTERNS = [
        (r"[a-z][A-Z]", "camelCase detected - Python uses snake_case", "ST001"),
        (r"^\s{1,3}[^\s]", "Inconsistent indentation (not 4 spaces)", "ST002"),
        (r".{120,}", "Line exceeds 120 characters", "ST003"),
        (r"\t", "Tab character - use spaces", "ST004"),
        (r"\s+$", "Trailing whitespace", "ST005"),
    ]

    def check_syntax(self, code: str) -> Tuple[bool, List[CodeIssue]]:
        """Check Python syntax."""
        try:
            ast.parse(code)
            return True, []
        except SyntaxError as e:
            return False, [CodeIssue(
                category=IssueCategory.SYNTAX,
                severity=IssueSeverity.ERROR,
                message=e.msg or "Syntax error",
                line=e.lineno,
                column=e.offset,
            )]

    def check_security(self, code: str) -> List[CodeIssue]:
        """Check for security issues."""
        issues = []
        lines = code.splitlines()

        for pattern, message, rule in self.SECURITY_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(CodeIssue(
                        category=IssueCategory.SECURITY,
                        severity=IssueSeverity.WARNING,
                        message=message,
                        line=line_num,
                        rule=rule,
                    ))

        return issues

    def check_lint(self, code: str) -> List[CodeIssue]:
        """Check for lint issues."""
        issues = []
        lines = code.splitlines()

        for pattern, message, rule in self.LINT_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        category=IssueCategory.LINT,
                        severity=IssueSeverity.WARNING if rule != "L003" else IssueSeverity.INFO,
                        message=message,
                        line=line_num,
                        rule=rule,
                    ))

        return issues

    def check_style(self, code: str) -> List[CodeIssue]:
        """Check for style issues."""
        issues = []
        lines = code.splitlines()

        for pattern, message, rule in self.STYLE_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        category=IssueCategory.STYLE,
                        severity=IssueSeverity.INFO,
                        message=message,
                        line=line_num,
                        rule=rule,
                    ))

        return issues

    def analyze(self, code: str) -> CodeCritique:
        """Full analysis of Python code."""
        critique = CodeCritique()

        # Syntax check
        critique.syntax_valid, critique.syntax_errors = self.check_syntax(code)
        critique.syntax_score = 1.0 if critique.syntax_valid else 0.0

        if critique.syntax_valid:
            # Only run other checks if syntax is valid
            critique.security_issues = self.check_security(code)
            critique.lint_issues = self.check_lint(code)
            style_issues = self.check_style(code)
            critique.lint_issues.extend(style_issues)

            # Calculate scores
            critique.security_score = max(0.0, 1.0 - len(critique.security_issues) * 0.15)
            critique.lint_score = max(0.0, 1.0 - len(critique.lint_issues) * 0.05)
            critique.style_score = max(0.0, 1.0 - len(style_issues) * 0.02)

        # Overall score
        critique.overall_score = (
            critique.syntax_score * 0.4 +
            critique.security_score * 0.3 +
            critique.lint_score * 0.2 +
            critique.style_score * 0.1
        )

        # Generate guidance
        critique.revision_guidance = self._generate_guidance(critique)

        return critique

    def _generate_guidance(self, critique: CodeCritique) -> str:
        """Generate revision guidance based on critique."""
        if not critique.syntax_valid:
            return f"Fix syntax error: {critique.syntax_errors[0].message}"

        guidance_parts = []

        if critique.security_issues:
            guidance_parts.append(
                f"Address {len(critique.security_issues)} security issue(s)"
            )

        if critique.lint_issues:
            errors = [i for i in critique.lint_issues if i.severity == IssueSeverity.WARNING]
            if errors:
                guidance_parts.append(f"Fix {len(errors)} lint warning(s)")

        if not guidance_parts:
            return "Code looks good - no critical issues found"

        return "; ".join(guidance_parts)


class JavaScriptAnalyzer:
    """JavaScript/TypeScript-specific code analysis."""

    SECURITY_PATTERNS = [
        (r"\beval\s*\(", "Use of eval() is dangerous", "S001"),
        (r"innerHTML\s*=", "innerHTML can lead to XSS - use textContent", "S002"),
        (r"document\.write", "document.write can lead to XSS", "S003"),
        (r"new Function\s*\(", "new Function() is like eval()", "S004"),
        (r"setTimeout\s*\(['\"]", "setTimeout with string is like eval()", "S005"),
        (r"setInterval\s*\(['\"]", "setInterval with string is like eval()", "S006"),
        (r"password\s*[:=]\s*['\"]", "Hardcoded password detected", "S007"),
        (r"api[_-]?key\s*[:=]\s*['\"]", "Hardcoded API key detected", "S008"),
    ]

    LINT_PATTERNS = [
        (r"var\s+", "Use let or const instead of var", "L001"),
        (r"==(?!=)", "Use === instead of ==", "L002"),
        (r"!=(?!=)", "Use !== instead of !=", "L003"),
        (r"console\.log", "console.log statement - remove for production", "L004"),
        (r"debugger", "debugger statement found", "L005"),
        (r"// TODO|// FIXME", "TODO/FIXME comment found", "L006"),
    ]

    def check_syntax(self, code: str) -> Tuple[bool, List[CodeIssue]]:
        """Basic JS syntax check (very limited without a parser)."""
        # Count braces/brackets for basic balance
        issues = []

        brace_count = code.count("{") - code.count("}")
        bracket_count = code.count("[") - code.count("]")
        paren_count = code.count("(") - code.count(")")

        if brace_count != 0:
            issues.append(CodeIssue(
                category=IssueCategory.SYNTAX,
                severity=IssueSeverity.ERROR,
                message=f"Unbalanced braces: {'+' if brace_count > 0 else ''}{brace_count}",
            ))

        if bracket_count != 0:
            issues.append(CodeIssue(
                category=IssueCategory.SYNTAX,
                severity=IssueSeverity.ERROR,
                message=f"Unbalanced brackets: {'+' if bracket_count > 0 else ''}{bracket_count}",
            ))

        if paren_count != 0:
            issues.append(CodeIssue(
                category=IssueCategory.SYNTAX,
                severity=IssueSeverity.ERROR,
                message=f"Unbalanced parentheses: {'+' if paren_count > 0 else ''}{paren_count}",
            ))

        return len(issues) == 0, issues

    def check_security(self, code: str) -> List[CodeIssue]:
        """Check for security issues."""
        issues = []
        lines = code.splitlines()

        for pattern, message, rule in self.SECURITY_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(CodeIssue(
                        category=IssueCategory.SECURITY,
                        severity=IssueSeverity.WARNING,
                        message=message,
                        line=line_num,
                        rule=rule,
                    ))

        return issues

    def check_lint(self, code: str) -> List[CodeIssue]:
        """Check for lint issues."""
        issues = []
        lines = code.splitlines()

        for pattern, message, rule in self.LINT_PATTERNS:
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        category=IssueCategory.LINT,
                        severity=IssueSeverity.WARNING if rule not in ["L004", "L006"] else IssueSeverity.INFO,
                        message=message,
                        line=line_num,
                        rule=rule,
                    ))

        return issues

    def analyze(self, code: str) -> CodeCritique:
        """Full analysis of JavaScript code."""
        critique = CodeCritique()

        critique.syntax_valid, critique.syntax_errors = self.check_syntax(code)
        critique.syntax_score = 1.0 if critique.syntax_valid else 0.0

        critique.security_issues = self.check_security(code)
        critique.lint_issues = self.check_lint(code)

        critique.security_score = max(0.0, 1.0 - len(critique.security_issues) * 0.15)
        critique.lint_score = max(0.0, 1.0 - len(critique.lint_issues) * 0.05)

        critique.overall_score = (
            critique.syntax_score * 0.4 +
            critique.security_score * 0.3 +
            critique.lint_score * 0.3
        )

        return critique


# =============================================================================
# Main Code Critic
# =============================================================================


class CodeCritic:
    """
    Main code quality critic.

    Evaluates code quality across multiple dimensions:
    - Syntax validity
    - Security issues
    - Lint/style issues
    - Type safety (when available)

    Supports multiple languages through pluggable analyzers.
    """

    ANALYZERS = {
        "python": PythonAnalyzer,
        "py": PythonAnalyzer,
        "javascript": JavaScriptAnalyzer,
        "js": JavaScriptAnalyzer,
        "typescript": JavaScriptAnalyzer,
        "ts": JavaScriptAnalyzer,
    }

    def __init__(self, language: str = "python"):
        """
        Initialize CodeCritic.

        Args:
            language: Programming language to analyze
        """
        self.language = language.lower()
        analyzer_class = self.ANALYZERS.get(self.language)
        self.analyzer = analyzer_class() if analyzer_class else None

    def evaluate(
        self,
        code: str,
        file_path: Optional[str] = None,
        context: Optional[str] = None,
    ) -> CodeCritique:
        """
        Evaluate code quality.

        Args:
            code: Source code to evaluate
            file_path: Optional file path for context
            context: Optional additional context

        Returns:
            CodeCritique with quality assessment
        """
        # Detect language from file extension if not set
        if file_path and not self.analyzer:
            ext = Path(file_path).suffix.lower().lstrip(".")
            analyzer_class = self.ANALYZERS.get(ext)
            if analyzer_class:
                self.analyzer = analyzer_class()

        if not self.analyzer:
            logger.warning(f"No analyzer for language: {self.language}")
            return CodeCritique(
                revision_guidance=f"No analyzer available for {self.language}"
            )

        return self.analyzer.analyze(code)

    def evaluate_file(self, file_path: str) -> CodeCritique:
        """
        Evaluate a file.

        Args:
            file_path: Path to file

        Returns:
            CodeCritique with quality assessment
        """
        path = Path(file_path)

        if not path.exists():
            return CodeCritique(
                syntax_valid=False,
                syntax_score=0.0,
                overall_score=0.0,
                revision_guidance=f"File not found: {file_path}",
            )

        try:
            code = path.read_text()
            return self.evaluate(code, file_path=file_path)
        except Exception as e:
            return CodeCritique(
                syntax_valid=False,
                syntax_score=0.0,
                overall_score=0.0,
                revision_guidance=f"Error reading file: {str(e)}",
            )

    @classmethod
    def supported_languages(cls) -> List[str]:
        """Get list of supported languages."""
        return list(set(cls.ANALYZERS.keys()))


# =============================================================================
# MCP Tool Adapter
# =============================================================================


def create_code_critic_handler(critic: Optional[CodeCritic] = None):
    """Create MCP handler for code critic."""

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        code = params.get("code", "")
        language = params.get("language", "python")
        file_path = params.get("file_path")

        _critic = critic or CodeCritic(language=language)

        if file_path and not code:
            critique = _critic.evaluate_file(file_path)
        else:
            critique = _critic.evaluate(code, file_path=file_path)

        return critique.to_dict()

    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "IssueSeverity",
    "IssueCategory",
    "CodeIssue",
    "CodeCritique",
    # Analyzers
    "PythonAnalyzer",
    "JavaScriptAnalyzer",
    # Main critic
    "CodeCritic",
    # MCP handler
    "create_code_critic_handler",
]
