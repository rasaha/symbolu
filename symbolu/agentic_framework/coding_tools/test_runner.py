"""
Test Runner for Test Execution

Provides test execution capabilities for the Sentinel agentic framework:
- Test discovery
- Test execution
- Result parsing
- Coverage integration

Supports multiple testing frameworks.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class TestStatus(Enum):
    """Status of a test."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    MOCHA = "mocha"
    GO_TEST = "go_test"
    CARGO_TEST = "cargo_test"


@dataclass
class TestCase:
    """A single test case."""
    name: str
    file_path: str
    status: TestStatus = TestStatus.PASSED
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    stdout: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "file_path": self.file_path,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error_message": self.error_message,
            "stdout": self.stdout,
        }


@dataclass
class TestResult:
    """Result of a test run."""
    success: bool
    framework: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    total: int = 0
    duration_ms: float = 0.0
    tests: List[TestCase] = field(default_factory=list)
    failures: List[TestCase] = field(default_factory=list)
    coverage_percent: Optional[float] = None
    output: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "framework": self.framework,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "total": self.total,
            "duration_ms": self.duration_ms,
            "tests": [t.to_dict() for t in self.tests],
            "failures": [f.to_dict() for f in self.failures],
            "coverage_percent": self.coverage_percent,
            "output": self.output,
            "error": self.error,
        }

    def summary(self) -> str:
        """Generate a summary string."""
        status = "PASSED" if self.success else "FAILED"
        return (
            f"{status}: {self.passed} passed, {self.failed} failed, "
            f"{self.skipped} skipped ({self.duration_ms:.0f}ms)"
        )


# =============================================================================
# Test Runner
# =============================================================================


class TestRunner:
    """
    Test execution and result parsing.

    Supports multiple testing frameworks with automatic detection.
    """

    def __init__(self, root_path: Optional[str] = None):
        """
        Initialize TestRunner.

        Args:
            root_path: Root path of the project
        """
        self.root_path = Path(root_path) if root_path else Path.cwd()

    def detect_framework(self) -> Optional[TestFramework]:
        """Detect the testing framework used in the project."""
        # Python: pytest
        if (
            (self.root_path / "pytest.ini").exists() or
            (self.root_path / "pyproject.toml").exists() or
            (self.root_path / "setup.cfg").exists()
        ):
            # Check if pytest is importable or in dependencies
            return TestFramework.PYTEST

        # Python: unittest (if tests/ or test_*.py exists)
        if list(self.root_path.glob("test*.py")) or (self.root_path / "tests").is_dir():
            return TestFramework.PYTEST  # Default to pytest for Python

        # JavaScript: jest
        package_json = self.root_path / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(package_json.read_text())
                deps = set(pkg.get("dependencies", {}).keys()) | set(pkg.get("devDependencies", {}).keys())
                if "jest" in deps:
                    return TestFramework.JEST
                if "mocha" in deps:
                    return TestFramework.MOCHA
            except Exception:
                pass

        # Go
        if (self.root_path / "go.mod").exists():
            return TestFramework.GO_TEST

        # Rust
        if (self.root_path / "Cargo.toml").exists():
            return TestFramework.CARGO_TEST

        return None

    def run(
        self,
        test_path: Optional[str] = None,
        pattern: Optional[str] = None,
        framework: Optional[TestFramework] = None,
        coverage: bool = False,
        verbose: bool = False,
        timeout: float = 300.0,
    ) -> TestResult:
        """
        Run tests.

        Args:
            test_path: Specific test file or directory
            pattern: Test name pattern to match
            framework: Force specific framework
            coverage: Enable coverage reporting
            verbose: Verbose output
            timeout: Timeout in seconds

        Returns:
            TestResult with execution results
        """
        # Auto-detect framework if not specified
        if framework is None:
            framework = self.detect_framework()

        if framework is None:
            return TestResult(
                success=False,
                framework="unknown",
                error="Could not detect test framework",
            )

        # Run appropriate runner
        if framework == TestFramework.PYTEST:
            return self._run_pytest(test_path, pattern, coverage, verbose, timeout)
        elif framework == TestFramework.JEST:
            return self._run_jest(test_path, pattern, coverage, verbose, timeout)
        elif framework == TestFramework.GO_TEST:
            return self._run_go_test(test_path, pattern, coverage, verbose, timeout)
        elif framework == TestFramework.CARGO_TEST:
            return self._run_cargo_test(test_path, pattern, verbose, timeout)
        else:
            return TestResult(
                success=False,
                framework=framework.value,
                error=f"Unsupported framework: {framework.value}",
            )

    def _run_pytest(
        self,
        test_path: Optional[str],
        pattern: Optional[str],
        coverage: bool,
        verbose: bool,
        timeout: float,
    ) -> TestResult:
        """Run pytest."""
        command = ["python", "-m", "pytest"]

        # JSON output for parsing
        command.extend(["--tb=short", "-q"])

        if verbose:
            command.append("-v")

        if coverage:
            command.extend(["--cov", "--cov-report=term-missing"])

        if pattern:
            command.extend(["-k", pattern])

        if test_path:
            command.append(test_path)

        try:
            result = subprocess.run(
                command,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout + result.stderr

            # Parse pytest output
            return self._parse_pytest_output(output, result.returncode == 0)

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                framework="pytest",
                error=f"Test execution timed out after {timeout}s",
            )
        except FileNotFoundError:
            return TestResult(
                success=False,
                framework="pytest",
                error="pytest not found - install with: pip install pytest",
            )
        except Exception as e:
            return TestResult(
                success=False,
                framework="pytest",
                error=str(e),
            )

    def _parse_pytest_output(self, output: str, success: bool) -> TestResult:
        """Parse pytest output."""
        result = TestResult(
            success=success,
            framework="pytest",
            output=output,
        )

        # Parse summary line: "X passed, Y failed, Z skipped in Xs"
        summary_match = re.search(
            r'(\d+)\s+passed.*?'
            r'(?:(\d+)\s+failed)?.*?'
            r'(?:(\d+)\s+skipped)?.*?'
            r'(?:(\d+)\s+error)?.*?'
            r'in\s+([\d.]+)s?',
            output,
            re.IGNORECASE | re.DOTALL
        )

        if summary_match:
            result.passed = int(summary_match.group(1) or 0)
            result.failed = int(summary_match.group(2) or 0)
            result.skipped = int(summary_match.group(3) or 0)
            result.errors = int(summary_match.group(4) or 0)
            result.duration_ms = float(summary_match.group(5) or 0) * 1000
            result.total = result.passed + result.failed + result.skipped + result.errors

        # Extract failure details
        failure_section = re.search(r'=+ FAILURES =+(.+?)(?:=+ |$)', output, re.DOTALL)
        if failure_section:
            failures_text = failure_section.group(1)
            # Extract individual failures
            failure_matches = re.findall(
                r'_+ ([\w:]+) _+\n(.+?)(?=_+ |$)',
                failures_text,
                re.DOTALL
            )
            for name, error_text in failure_matches:
                result.failures.append(TestCase(
                    name=name,
                    file_path="",
                    status=TestStatus.FAILED,
                    error_message=error_text.strip()[:500],  # Truncate
                ))

        # Parse coverage if present
        coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', output)
        if coverage_match:
            result.coverage_percent = float(coverage_match.group(1))

        return result

    def _run_jest(
        self,
        test_path: Optional[str],
        pattern: Optional[str],
        coverage: bool,
        verbose: bool,
        timeout: float,
    ) -> TestResult:
        """Run Jest."""
        command = ["npx", "jest", "--json"]

        if coverage:
            command.append("--coverage")

        if pattern:
            command.extend(["--testNamePattern", pattern])

        if test_path:
            command.append(test_path)

        try:
            result = subprocess.run(
                command,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Jest outputs JSON
            try:
                data = json.loads(result.stdout)
                return self._parse_jest_json(data)
            except json.JSONDecodeError:
                return TestResult(
                    success=result.returncode == 0,
                    framework="jest",
                    output=result.stdout + result.stderr,
                )

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                framework="jest",
                error=f"Test execution timed out after {timeout}s",
            )
        except Exception as e:
            return TestResult(
                success=False,
                framework="jest",
                error=str(e),
            )

    def _parse_jest_json(self, data: Dict[str, Any]) -> TestResult:
        """Parse Jest JSON output."""
        result = TestResult(
            success=data.get("success", False),
            framework="jest",
        )

        result.passed = data.get("numPassedTests", 0)
        result.failed = data.get("numFailedTests", 0)
        result.skipped = data.get("numPendingTests", 0)
        result.total = data.get("numTotalTests", 0)

        # Duration
        start_time = data.get("startTime", 0)
        end_time = start_time
        for suite in data.get("testResults", []):
            end_time = max(end_time, suite.get("endTime", 0))
        result.duration_ms = end_time - start_time

        # Extract failures
        for suite in data.get("testResults", []):
            for assertion in suite.get("assertionResults", []):
                if assertion.get("status") == "failed":
                    result.failures.append(TestCase(
                        name=assertion.get("fullName", ""),
                        file_path=suite.get("name", ""),
                        status=TestStatus.FAILED,
                        error_message="\n".join(assertion.get("failureMessages", [])),
                    ))

        return result

    def _run_go_test(
        self,
        test_path: Optional[str],
        pattern: Optional[str],
        coverage: bool,
        verbose: bool,
        timeout: float,
    ) -> TestResult:
        """Run Go tests."""
        command = ["go", "test", "-json"]

        if verbose:
            command.append("-v")

        if coverage:
            command.append("-cover")

        if test_path:
            command.append(test_path)
        else:
            command.append("./...")

        if pattern:
            command.extend(["-run", pattern])

        try:
            result = subprocess.run(
                command,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return self._parse_go_test_output(result.stdout, result.returncode == 0)

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                framework="go_test",
                error=f"Test execution timed out after {timeout}s",
            )
        except Exception as e:
            return TestResult(
                success=False,
                framework="go_test",
                error=str(e),
            )

    def _parse_go_test_output(self, output: str, success: bool) -> TestResult:
        """Parse Go test JSON output."""
        result = TestResult(
            success=success,
            framework="go_test",
            output=output,
        )

        # Go test JSON is newline-delimited
        for line in output.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                action = event.get("Action")
                test_name = event.get("Test")

                if action == "pass" and test_name:
                    result.passed += 1
                    result.total += 1
                elif action == "fail" and test_name:
                    result.failed += 1
                    result.total += 1
                    result.failures.append(TestCase(
                        name=test_name,
                        file_path=event.get("Package", ""),
                        status=TestStatus.FAILED,
                        error_message=event.get("Output", ""),
                    ))
                elif action == "skip" and test_name:
                    result.skipped += 1
                    result.total += 1

            except json.JSONDecodeError:
                continue

        return result

    def _run_cargo_test(
        self,
        test_path: Optional[str],
        pattern: Optional[str],
        verbose: bool,
        timeout: float,
    ) -> TestResult:
        """Run Cargo tests."""
        command = ["cargo", "test"]

        if pattern:
            command.append(pattern)

        command.append("--")

        if verbose:
            command.append("--nocapture")

        try:
            result = subprocess.run(
                command,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return self._parse_cargo_output(result.stdout + result.stderr, result.returncode == 0)

        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                framework="cargo_test",
                error=f"Test execution timed out after {timeout}s",
            )
        except Exception as e:
            return TestResult(
                success=False,
                framework="cargo_test",
                error=str(e),
            )

    def _parse_cargo_output(self, output: str, success: bool) -> TestResult:
        """Parse Cargo test output."""
        result = TestResult(
            success=success,
            framework="cargo_test",
            output=output,
        )

        # Parse "test result: ok. X passed; Y failed; Z ignored"
        summary_match = re.search(
            r'test result:.*?(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+ignored',
            output,
            re.IGNORECASE
        )

        if summary_match:
            result.passed = int(summary_match.group(1))
            result.failed = int(summary_match.group(2))
            result.skipped = int(summary_match.group(3))
            result.total = result.passed + result.failed + result.skipped

        return result

    def discover(self, path: Optional[str] = None) -> List[str]:
        """
        Discover test files.

        Args:
            path: Path to search

        Returns:
            List of test file paths
        """
        search_path = Path(path) if path else self.root_path
        test_files = []

        # Python
        test_files.extend(str(p) for p in search_path.rglob("test_*.py"))
        test_files.extend(str(p) for p in search_path.rglob("*_test.py"))

        # JavaScript
        test_files.extend(str(p) for p in search_path.rglob("*.test.js"))
        test_files.extend(str(p) for p in search_path.rglob("*.spec.js"))
        test_files.extend(str(p) for p in search_path.rglob("*.test.ts"))
        test_files.extend(str(p) for p in search_path.rglob("*.spec.ts"))

        # Go
        test_files.extend(str(p) for p in search_path.rglob("*_test.go"))

        # Rust
        test_files.extend(str(p) for p in search_path.rglob("tests/*.rs"))

        return sorted(set(test_files))


# =============================================================================
# MCP Tool Adapter
# =============================================================================


def create_test_runner_handler(runner: Optional[TestRunner] = None):
    """Create MCP handler for test runner."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        root_path = params.get("path")
        _runner = runner or TestRunner(root_path)

        result = _runner.run(
            test_path=params.get("test_path"),
            pattern=params.get("pattern"),
            coverage=params.get("coverage", False),
            verbose=params.get("verbose", False),
            timeout=params.get("timeout", 300.0),
        )

        return result.to_dict()
    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "TestStatus",
    "TestFramework",
    "TestCase",
    "TestResult",
    # Runner
    "TestRunner",
    # MCP handler
    "create_test_runner_handler",
]
