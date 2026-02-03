"""
Code Execution Sandbox

Provides isolated code execution for the Sentinel agentic framework:
- Process isolation with resource limits
- Timeout enforcement
- Output capture
- Cleanup handling

This sandbox is NOT a security boundary - it's a convenience wrapper.
For true isolation, use Docker or VMs.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import shutil

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class ExecutionStatus(Enum):
    """Status of code execution."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    KILLED = "killed"
    SETUP_FAILED = "setup_failed"


@dataclass
class ExecutionResult:
    """Result from code execution."""
    status: ExecutionStatus
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS and self.exit_code == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    # Timeouts
    timeout_seconds: float = 30.0

    # Output limits
    max_stdout_bytes: int = 100_000  # 100KB
    max_stderr_bytes: int = 50_000   # 50KB

    # Working directory
    working_dir: Optional[str] = None
    use_temp_dir: bool = False

    # Environment
    inherit_env: bool = True
    extra_env: Dict[str, str] = field(default_factory=dict)

    # Cleanup
    cleanup_temp: bool = True


# =============================================================================
# Sandbox Executor
# =============================================================================


class SandboxExecutor:
    """
    Execute code in a sandboxed subprocess.

    Features:
    - Timeout enforcement
    - Output capture with limits
    - Working directory isolation
    - Environment control
    - Cleanup handling

    NOTE: This is not a security sandbox. For security-critical
    applications, use Docker containers or VMs.
    """

    def __init__(self, config: Optional[SandboxConfig] = None):
        """
        Initialize SandboxExecutor.

        Args:
            config: Sandbox configuration
        """
        self.config = config or SandboxConfig()
        self._temp_dirs: List[Path] = []

    def execute_command(
        self,
        command: List[str],
        stdin: Optional[str] = None,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionResult:
        """
        Execute a shell command.

        Args:
            command: Command as list of arguments
            stdin: Optional stdin input
            working_dir: Working directory (overrides config)
            env: Environment variables (merged with config)
            timeout: Timeout in seconds (overrides config)

        Returns:
            ExecutionResult with output and status
        """
        start_time = time.time()
        actual_timeout = timeout or self.config.timeout_seconds

        # Determine working directory
        cwd = self._get_working_dir(working_dir)

        # Build environment
        exec_env = self._build_env(env)

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=exec_env,
                # Don't use shell=True for security
                shell=False,
                # Start new process group for clean termination
                start_new_session=True,
            )

            try:
                stdout_bytes, stderr_bytes = process.communicate(
                    input=stdin.encode() if stdin else None,
                    timeout=actual_timeout,
                )

                execution_time = (time.time() - start_time) * 1000

                # Decode and truncate output
                stdout = self._decode_output(stdout_bytes, self.config.max_stdout_bytes)
                stderr = self._decode_output(stderr_bytes, self.config.max_stderr_bytes)

                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    exit_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    execution_time_ms=execution_time,
                )

            except subprocess.TimeoutExpired:
                # Kill the process group
                self._kill_process_tree(process)
                execution_time = (time.time() - start_time) * 1000

                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    exit_code=-1,
                    error=f"Execution timed out after {actual_timeout}s",
                    execution_time_ms=execution_time,
                )

        except FileNotFoundError:
            return ExecutionResult(
                status=ExecutionStatus.SETUP_FAILED,
                exit_code=-1,
                error=f"Command not found: {command[0]}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except PermissionError:
            return ExecutionResult(
                status=ExecutionStatus.SETUP_FAILED,
                exit_code=-1,
                error=f"Permission denied: {command[0]}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                exit_code=-1,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def execute_python(
        self,
        code: str,
        python_path: Optional[str] = None,
        args: Optional[List[str]] = None,
        **kwargs,
    ) -> ExecutionResult:
        """
        Execute Python code.

        Args:
            code: Python code to execute
            python_path: Path to Python interpreter (default: sys.executable)
            args: Additional arguments to pass to the script
            **kwargs: Passed to execute_command

        Returns:
            ExecutionResult with output
        """
        interpreter = python_path or sys.executable
        args = args or []

        # Create temp file for code
        temp_dir = self._create_temp_dir()
        script_path = temp_dir / "script.py"
        script_path.write_text(code)

        command = [interpreter, str(script_path)] + args

        try:
            return self.execute_command(command, **kwargs)
        finally:
            if self.config.cleanup_temp:
                self._cleanup_temp_dir(temp_dir)

    def execute_node(
        self,
        code: str,
        node_path: Optional[str] = None,
        args: Optional[List[str]] = None,
        **kwargs,
    ) -> ExecutionResult:
        """
        Execute JavaScript/Node.js code.

        Args:
            code: JavaScript code to execute
            node_path: Path to node interpreter
            args: Additional arguments
            **kwargs: Passed to execute_command

        Returns:
            ExecutionResult with output
        """
        interpreter = node_path or "node"
        args = args or []

        # Create temp file for code
        temp_dir = self._create_temp_dir()
        script_path = temp_dir / "script.js"
        script_path.write_text(code)

        command = [interpreter, str(script_path)] + args

        try:
            return self.execute_command(command, **kwargs)
        finally:
            if self.config.cleanup_temp:
                self._cleanup_temp_dir(temp_dir)

    def execute_bash(
        self,
        script: str,
        shell: str = "/bin/bash",
        **kwargs,
    ) -> ExecutionResult:
        """
        Execute a bash script.

        Args:
            script: Bash script to execute
            shell: Shell to use
            **kwargs: Passed to execute_command

        Returns:
            ExecutionResult with output
        """
        # Create temp file for script
        temp_dir = self._create_temp_dir()
        script_path = temp_dir / "script.sh"
        script_path.write_text(script)
        script_path.chmod(0o755)

        command = [shell, str(script_path)]

        try:
            return self.execute_command(command, **kwargs)
        finally:
            if self.config.cleanup_temp:
                self._cleanup_temp_dir(temp_dir)

    def _get_working_dir(self, override: Optional[str] = None) -> str:
        """Get working directory for execution."""
        if override:
            return override

        if self.config.working_dir:
            return self.config.working_dir

        if self.config.use_temp_dir:
            temp_dir = self._create_temp_dir()
            return str(temp_dir)

        return os.getcwd()

    def _build_env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build environment for execution."""
        if self.config.inherit_env:
            env = os.environ.copy()
        else:
            # Minimal environment
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
                "LANG": "en_US.UTF-8",
            }

        # Add config extras
        env.update(self.config.extra_env)

        # Add call-specific extras
        if extra:
            env.update(extra)

        return env

    def _create_temp_dir(self) -> Path:
        """Create a temporary directory."""
        temp_dir = Path(tempfile.mkdtemp(prefix="sandbox_"))
        self._temp_dirs.append(temp_dir)
        return temp_dir

    def _cleanup_temp_dir(self, path: Path) -> None:
        """Cleanup a temporary directory."""
        try:
            if path.exists():
                shutil.rmtree(path)
            if path in self._temp_dirs:
                self._temp_dirs.remove(path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {path}: {e}")

    def _kill_process_tree(self, process: subprocess.Popen) -> None:
        """Kill a process and all its children."""
        try:
            # Kill the process group
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            # Fallback to just killing the process
            try:
                process.kill()
            except Exception:
                pass

        # Wait for process to terminate
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            pass

    def _decode_output(self, data: bytes, max_bytes: int) -> str:
        """Decode and truncate output."""
        if len(data) > max_bytes:
            data = data[:max_bytes]
            truncated = True
        else:
            truncated = False

        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")

        if truncated:
            text += "\n... [output truncated]"

        return text

    def cleanup(self) -> None:
        """Cleanup all temporary directories."""
        for temp_dir in list(self._temp_dirs):
            self._cleanup_temp_dir(temp_dir)

    def __del__(self):
        """Cleanup on destruction."""
        self.cleanup()


# =============================================================================
# High-Level Code Runner
# =============================================================================


class CodeRunner:
    """
    High-level code execution interface.

    Automatically detects language and uses appropriate executor.
    """

    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".sh": "bash",
        ".bash": "bash",
    }

    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize CodeRunner."""
        self.sandbox = SandboxExecutor(config)

    def run(
        self,
        code: str,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs,
    ) -> ExecutionResult:
        """
        Run code in the appropriate runtime.

        Args:
            code: Code to execute
            language: Programming language (auto-detected if not provided)
            file_path: Optional file path for language detection
            **kwargs: Passed to sandbox executor

        Returns:
            ExecutionResult with output
        """
        # Detect language
        if not language and file_path:
            ext = Path(file_path).suffix.lower()
            language = self.LANGUAGE_EXTENSIONS.get(ext)

        if not language:
            # Try to auto-detect from code
            language = self._detect_language(code)

        # Execute based on language
        if language in ("python", "py"):
            return self.sandbox.execute_python(code, **kwargs)
        elif language in ("javascript", "js", "node"):
            return self.sandbox.execute_node(code, **kwargs)
        elif language in ("bash", "sh", "shell"):
            return self.sandbox.execute_bash(code, **kwargs)
        else:
            return ExecutionResult(
                status=ExecutionStatus.SETUP_FAILED,
                exit_code=-1,
                error=f"Unsupported language: {language}",
            )

    def run_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        **kwargs,
    ) -> ExecutionResult:
        """
        Run a file.

        Args:
            file_path: Path to file to execute
            args: Arguments to pass to the script
            **kwargs: Passed to sandbox executor

        Returns:
            ExecutionResult with output
        """
        path = Path(file_path)

        if not path.exists():
            return ExecutionResult(
                status=ExecutionStatus.SETUP_FAILED,
                exit_code=-1,
                error=f"File not found: {file_path}",
            )

        ext = path.suffix.lower()
        language = self.LANGUAGE_EXTENSIONS.get(ext)
        args = args or []

        if language == "python":
            command = [sys.executable, str(path)] + args
        elif language in ("javascript", "node"):
            command = ["node", str(path)] + args
        elif language == "bash":
            command = ["/bin/bash", str(path)] + args
        else:
            return ExecutionResult(
                status=ExecutionStatus.SETUP_FAILED,
                exit_code=-1,
                error=f"Unknown file type: {ext}",
            )

        return self.sandbox.execute_command(command, **kwargs)

    def _detect_language(self, code: str) -> str:
        """Try to detect language from code content."""
        # Simple heuristics
        if code.startswith("#!"):
            shebang = code.split("\n")[0].lower()
            if "python" in shebang:
                return "python"
            if "node" in shebang:
                return "javascript"
            if "bash" in shebang or "sh" in shebang:
                return "bash"

        if "def " in code or "import " in code or "class " in code:
            return "python"

        if "function " in code or "const " in code or "let " in code:
            return "javascript"

        # Default to python
        return "python"

    def cleanup(self) -> None:
        """Cleanup resources."""
        self.sandbox.cleanup()


# =============================================================================
# MCP Tool Adapter
# =============================================================================


def create_code_execute_handler(runner: Optional[CodeRunner] = None):
    """Create MCP handler for code execution."""
    _runner = runner or CodeRunner()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        code = params.get("code", "")
        language = params.get("language")
        timeout = params.get("timeout", 30.0)
        working_dir = params.get("working_dir")

        result = _runner.run(
            code=code,
            language=language,
            timeout=timeout,
            working_dir=working_dir,
        )

        return result.to_dict()

    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "ExecutionStatus",
    "ExecutionResult",
    "SandboxConfig",
    # Executors
    "SandboxExecutor",
    "CodeRunner",
    # MCP handler
    "create_code_execute_handler",
]
