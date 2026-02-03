"""
Git Tools for Version Control

Provides Git operations for the Sentinel agentic framework:
- Status, diff, log (read operations)
- Add, commit (write operations)
- Push, pull, fetch (network operations)

Integrates with SafeMCPGateway for safety gating.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class GitOperationType(Enum):
    """Types of Git operations by risk level."""
    READ = "read"        # status, diff, log, branch
    WRITE = "write"      # add, commit, checkout
    NETWORK = "network"  # push, pull, fetch
    DESTRUCTIVE = "destructive"  # reset --hard, clean -f


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str = ""
    clean: bool = True
    staged: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    untracked: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "clean": self.clean,
            "staged": self.staged,
            "modified": self.modified,
            "untracked": self.untracked,
            "deleted": self.deleted,
            "ahead": self.ahead,
            "behind": self.behind,
        }


@dataclass
class GitCommit:
    """Git commit information."""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "short_hash": self.short_hash,
            "author": self.author,
            "date": self.date,
            "message": self.message,
        }


@dataclass
class GitResult:
    """Result from a Git operation."""
    success: bool
    operation: str
    output: str = ""
    error: Optional[str] = None
    data: Any = None  # Structured data (status, commits, etc.)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "operation": self.operation,
            "output": self.output,
            "error": self.error,
        }
        if self.data is not None:
            if hasattr(self.data, "to_dict"):
                result["data"] = self.data.to_dict()
            elif isinstance(self.data, list) and self.data and hasattr(self.data[0], "to_dict"):
                result["data"] = [item.to_dict() for item in self.data]
            else:
                result["data"] = self.data
        return result


# =============================================================================
# Git Tools
# =============================================================================


class GitTools:
    """
    Git operations for the Sentinel framework.

    Provides safe wrappers around Git commands with:
    - Operation type classification
    - Output parsing
    - Error handling
    """

    def __init__(self, repo_path: Optional[str] = None):
        """
        Initialize GitTools.

        Args:
            repo_path: Path to Git repository (default: current directory)
        """
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()

    def _run_git(
        self,
        args: List[str],
        operation_type: GitOperationType = GitOperationType.READ,
        capture_output: bool = True,
    ) -> Tuple[bool, str, str]:
        """
        Run a Git command.

        Args:
            args: Git command arguments
            operation_type: Type of operation for logging
            capture_output: Whether to capture output

        Returns:
            Tuple of (success, stdout, stderr)
        """
        command = ["git"] + args

        logger.debug(f"Running git command: {' '.join(command)} ({operation_type.value})")

        try:
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=capture_output,
                text=True,
                timeout=60.0,
            )

            return (
                result.returncode == 0,
                result.stdout.strip() if result.stdout else "",
                result.stderr.strip() if result.stderr else "",
            )

        except subprocess.TimeoutExpired:
            return False, "", "Git command timed out"
        except FileNotFoundError:
            return False, "", "Git is not installed or not in PATH"
        except Exception as e:
            return False, "", str(e)

    # =========================================================================
    # Read Operations
    # =========================================================================

    def status(self) -> GitResult:
        """
        Get repository status.

        Returns:
            GitResult with GitStatus data
        """
        success, output, error = self._run_git(
            ["status", "--porcelain=v2", "--branch"],
            GitOperationType.READ,
        )

        if not success:
            return GitResult(
                success=False,
                operation="status",
                error=error or "Failed to get status",
            )

        status = GitStatus()

        for line in output.splitlines():
            if line.startswith("# branch.head"):
                status.branch = line.split()[-1]
            elif line.startswith("# branch.ab"):
                parts = line.split()
                for part in parts:
                    if part.startswith("+"):
                        status.ahead = int(part[1:])
                    elif part.startswith("-"):
                        status.behind = int(part[1:])
            elif line.startswith("1 "):
                # Modified file
                parts = line.split()
                xy = parts[1]
                path = parts[-1]
                if xy[0] in "MADRC":
                    status.staged.append(path)
                if xy[1] in "MD":
                    status.modified.append(path)
            elif line.startswith("2 "):
                # Renamed file
                parts = line.split()
                path = parts[-1]
                status.staged.append(path)
            elif line.startswith("? "):
                # Untracked
                path = line[2:]
                status.untracked.append(path)

        status.clean = not (
            status.staged or status.modified or status.untracked
        )

        return GitResult(
            success=True,
            operation="status",
            output=output,
            data=status,
        )

    def diff(
        self,
        staged: bool = False,
        file_path: Optional[str] = None,
        base: Optional[str] = None,
    ) -> GitResult:
        """
        Get diff output.

        Args:
            staged: Show staged changes
            file_path: Specific file to diff
            base: Base reference for diff

        Returns:
            GitResult with diff output
        """
        args = ["diff"]

        if staged:
            args.append("--cached")

        if base:
            args.append(base)

        if file_path:
            args.extend(["--", file_path])

        success, output, error = self._run_git(args, GitOperationType.READ)

        return GitResult(
            success=success,
            operation="diff",
            output=output,
            error=error if not success else None,
        )

    def log(
        self,
        n: int = 10,
        oneline: bool = False,
        file_path: Optional[str] = None,
    ) -> GitResult:
        """
        Get commit log.

        Args:
            n: Number of commits to show
            oneline: Use oneline format
            file_path: Show commits for specific file

        Returns:
            GitResult with list of GitCommit
        """
        if oneline:
            args = ["log", f"-{n}", "--oneline"]
        else:
            args = [
                "log", f"-{n}",
                "--format=%H|%h|%an|%ai|%s"
            ]

        if file_path:
            args.extend(["--", file_path])

        success, output, error = self._run_git(args, GitOperationType.READ)

        if not success:
            return GitResult(
                success=False,
                operation="log",
                error=error or "Failed to get log",
            )

        commits = []
        if not oneline:
            for line in output.splitlines():
                if "|" in line:
                    parts = line.split("|", 4)
                    if len(parts) >= 5:
                        commits.append(GitCommit(
                            hash=parts[0],
                            short_hash=parts[1],
                            author=parts[2],
                            date=parts[3],
                            message=parts[4],
                        ))

        return GitResult(
            success=True,
            operation="log",
            output=output,
            data=commits if commits else None,
        )

    def branch_list(self, all_branches: bool = False) -> GitResult:
        """
        List branches.

        Args:
            all_branches: Include remote branches

        Returns:
            GitResult with branch list
        """
        args = ["branch"]
        if all_branches:
            args.append("-a")

        success, output, error = self._run_git(args, GitOperationType.READ)

        if not success:
            return GitResult(
                success=False,
                operation="branch_list",
                error=error,
            )

        branches = []
        current_branch = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("* "):
                current_branch = line[2:]
                branches.append(current_branch)
            elif line:
                branches.append(line)

        return GitResult(
            success=True,
            operation="branch_list",
            output=output,
            data={"branches": branches, "current": current_branch},
        )

    def show(self, ref: str = "HEAD", file_path: Optional[str] = None) -> GitResult:
        """
        Show object (commit, file at commit, etc.).

        Args:
            ref: Git reference (commit hash, branch, tag, HEAD)
            file_path: File to show at that ref

        Returns:
            GitResult with content
        """
        if file_path:
            args = ["show", f"{ref}:{file_path}"]
        else:
            args = ["show", ref]

        success, output, error = self._run_git(args, GitOperationType.READ)

        return GitResult(
            success=success,
            operation="show",
            output=output,
            error=error if not success else None,
        )

    # =========================================================================
    # Write Operations
    # =========================================================================

    def add(self, paths: List[str]) -> GitResult:
        """
        Stage files for commit.

        Args:
            paths: List of file paths to stage

        Returns:
            GitResult
        """
        if not paths:
            return GitResult(
                success=False,
                operation="add",
                error="No paths specified",
            )

        args = ["add", "--"] + paths

        success, output, error = self._run_git(args, GitOperationType.WRITE)

        return GitResult(
            success=success,
            operation="add",
            output=output or f"Staged {len(paths)} file(s)",
            error=error if not success else None,
        )

    def commit(self, message: str, allow_empty: bool = False) -> GitResult:
        """
        Create a commit.

        Args:
            message: Commit message
            allow_empty: Allow empty commits

        Returns:
            GitResult with commit hash
        """
        if not message:
            return GitResult(
                success=False,
                operation="commit",
                error="Commit message is required",
            )

        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")

        success, output, error = self._run_git(args, GitOperationType.WRITE)

        return GitResult(
            success=success,
            operation="commit",
            output=output,
            error=error if not success else None,
        )

    def checkout(self, ref: str, create: bool = False) -> GitResult:
        """
        Checkout a branch or commit.

        Args:
            ref: Branch name or commit to checkout
            create: Create new branch

        Returns:
            GitResult
        """
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(ref)

        success, output, error = self._run_git(args, GitOperationType.WRITE)

        return GitResult(
            success=success,
            operation="checkout",
            output=output or f"Switched to {ref}",
            error=error if not success else None,
        )

    def create_branch(self, name: str, start_point: Optional[str] = None) -> GitResult:
        """
        Create a new branch.

        Args:
            name: Branch name
            start_point: Starting commit/branch

        Returns:
            GitResult
        """
        args = ["branch", name]
        if start_point:
            args.append(start_point)

        success, output, error = self._run_git(args, GitOperationType.WRITE)

        return GitResult(
            success=success,
            operation="create_branch",
            output=output or f"Created branch {name}",
            error=error if not success else None,
        )

    # =========================================================================
    # Network Operations
    # =========================================================================

    def push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
        force: bool = False,
    ) -> GitResult:
        """
        Push to remote.

        Args:
            remote: Remote name
            branch: Branch to push
            set_upstream: Set upstream tracking
            force: Force push (DANGEROUS)

        Returns:
            GitResult
        """
        args = ["push"]

        if set_upstream:
            args.append("-u")

        if force:
            # Warning for force push
            logger.warning("Force push requested - this can destroy remote history!")
            args.append("--force-with-lease")  # Safer than --force

        args.append(remote)

        if branch:
            args.append(branch)

        success, output, error = self._run_git(args, GitOperationType.NETWORK)

        return GitResult(
            success=success,
            operation="push",
            output=output,
            error=error if not success else None,
        )

    def pull(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        rebase: bool = False,
    ) -> GitResult:
        """
        Pull from remote.

        Args:
            remote: Remote name
            branch: Branch to pull
            rebase: Rebase instead of merge

        Returns:
            GitResult
        """
        args = ["pull"]

        if rebase:
            args.append("--rebase")

        args.append(remote)

        if branch:
            args.append(branch)

        success, output, error = self._run_git(args, GitOperationType.NETWORK)

        return GitResult(
            success=success,
            operation="pull",
            output=output,
            error=error if not success else None,
        )

    def fetch(
        self,
        remote: str = "origin",
        prune: bool = False,
    ) -> GitResult:
        """
        Fetch from remote.

        Args:
            remote: Remote name
            prune: Prune deleted remote branches

        Returns:
            GitResult
        """
        args = ["fetch", remote]

        if prune:
            args.append("--prune")

        success, output, error = self._run_git(args, GitOperationType.NETWORK)

        return GitResult(
            success=success,
            operation="fetch",
            output=output or "Fetch complete",
            error=error if not success else None,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def is_git_repo(self) -> bool:
        """Check if current directory is a Git repository."""
        success, _, _ = self._run_git(
            ["rev-parse", "--is-inside-work-tree"],
            GitOperationType.READ,
        )
        return success

    def get_current_branch(self) -> Optional[str]:
        """Get current branch name."""
        success, output, _ = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            GitOperationType.READ,
        )
        return output if success else None

    def get_root_dir(self) -> Optional[str]:
        """Get repository root directory."""
        success, output, _ = self._run_git(
            ["rev-parse", "--show-toplevel"],
            GitOperationType.READ,
        )
        return output if success else None


# =============================================================================
# MCP Tool Adapters
# =============================================================================


def create_git_status_handler(tools: Optional[GitTools] = None):
    """Create MCP handler for git status."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        repo_path = params.get("repo_path")
        _tools = tools or GitTools(repo_path)
        result = _tools.status()
        return result.to_dict()
    return handler


def create_git_diff_handler(tools: Optional[GitTools] = None):
    """Create MCP handler for git diff."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        repo_path = params.get("repo_path")
        _tools = tools or GitTools(repo_path)
        result = _tools.diff(
            staged=params.get("staged", False),
            file_path=params.get("file_path"),
            base=params.get("base"),
        )
        return result.to_dict()
    return handler


def create_git_log_handler(tools: Optional[GitTools] = None):
    """Create MCP handler for git log."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        repo_path = params.get("repo_path")
        _tools = tools or GitTools(repo_path)
        result = _tools.log(
            n=params.get("n", 10),
            file_path=params.get("file_path"),
        )
        return result.to_dict()
    return handler


def create_git_commit_handler(tools: Optional[GitTools] = None):
    """Create MCP handler for git commit."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        repo_path = params.get("repo_path")
        _tools = tools or GitTools(repo_path)

        # Stage files if provided
        files = params.get("files", [])
        if files:
            add_result = _tools.add(files)
            if not add_result.success:
                return add_result.to_dict()

        # Commit
        result = _tools.commit(
            message=params.get("message", ""),
        )
        return result.to_dict()
    return handler


def create_git_push_handler(tools: Optional[GitTools] = None):
    """Create MCP handler for git push."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        repo_path = params.get("repo_path")
        _tools = tools or GitTools(repo_path)
        result = _tools.push(
            remote=params.get("remote", "origin"),
            branch=params.get("branch"),
            set_upstream=params.get("set_upstream", False),
            force=params.get("force", False),
        )
        return result.to_dict()
    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "GitOperationType",
    "GitStatus",
    "GitCommit",
    "GitResult",
    # Tools
    "GitTools",
    # MCP handlers
    "create_git_status_handler",
    "create_git_diff_handler",
    "create_git_log_handler",
    "create_git_commit_handler",
    "create_git_push_handler",
]
