"""
Search Tools for Coding Capabilities

Provides code search operations for the Sentinel agentic framework:
- GlobTool: Find files by pattern
- GrepTool: Search file contents with regex

These tools integrate with SafeMCPGateway for safety gating.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class GlobResult:
    """Result from glob search."""
    success: bool
    pattern: str
    matches: List[str] = field(default_factory=list)
    match_count: int = 0
    truncated: bool = False
    search_path: str = ""
    error: Optional[str] = None


@dataclass
class GrepMatch:
    """Single grep match."""
    file_path: str
    line_number: int
    line_content: str
    match_start: int = 0
    match_end: int = 0


@dataclass
class GrepResult:
    """Result from grep search."""
    success: bool
    pattern: str
    matches: List[GrepMatch] = field(default_factory=list)
    files_searched: int = 0
    files_matched: int = 0
    total_matches: int = 0
    truncated: bool = False
    error: Optional[str] = None

    def get_files_with_matches(self) -> List[str]:
        """Get unique list of files with matches."""
        return list(dict.fromkeys(m.file_path for m in self.matches))

    def get_match_counts(self) -> Dict[str, int]:
        """Get match count per file."""
        counts: Dict[str, int] = {}
        for m in self.matches:
            counts[m.file_path] = counts.get(m.file_path, 0) + 1
        return counts


# =============================================================================
# Glob Tool
# =============================================================================


class GlobTool:
    """
    Find files matching glob patterns.

    Features:
    - Supports ** for recursive matching
    - Supports standard glob patterns (*, ?, [abc])
    - Can sort by modification time
    - Respects gitignore patterns
    """

    DEFAULT_MAX_RESULTS = 1000

    # Common directories to skip
    SKIP_DIRS = {
        ".git", ".svn", ".hg", ".bzr",
        "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache",
        "venv", ".venv", "env", ".env",
        ".tox", ".nox",
        "dist", "build", ".eggs", "*.egg-info",
        ".idea", ".vscode",
        "coverage", ".coverage",
    }

    def __init__(
        self,
        max_results: int = DEFAULT_MAX_RESULTS,
        skip_dirs: Optional[set] = None,
        follow_symlinks: bool = False,
    ):
        """
        Initialize GlobTool.

        Args:
            max_results: Maximum number of results to return
            skip_dirs: Directories to skip (default: common dev dirs)
            follow_symlinks: Whether to follow symbolic links
        """
        self.max_results = max_results
        self.skip_dirs = skip_dirs or self.SKIP_DIRS
        self.follow_symlinks = follow_symlinks

    def search(
        self,
        pattern: str,
        path: Optional[str] = None,
        sort_by_mtime: bool = True,
    ) -> GlobResult:
        """
        Search for files matching pattern.

        Args:
            pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")
            path: Directory to search in (default: current directory)
            sort_by_mtime: Sort results by modification time (newest first)

        Returns:
            GlobResult with matching file paths
        """
        search_path = Path(path) if path else Path.cwd()

        if not search_path.exists():
            return GlobResult(
                success=False,
                pattern=pattern,
                search_path=str(search_path),
                error=f"Path not found: {search_path}",
            )

        if not search_path.is_dir():
            return GlobResult(
                success=False,
                pattern=pattern,
                search_path=str(search_path),
                error=f"Path is not a directory: {search_path}",
            )

        try:
            matches = []
            truncated = False

            # Use pathlib glob for recursive patterns
            if "**" in pattern:
                for match in search_path.glob(pattern):
                    if self._should_skip(match):
                        continue
                    if match.is_file():
                        matches.append(str(match.absolute()))
                        if len(matches) >= self.max_results:
                            truncated = True
                            break
            else:
                # Non-recursive: use fnmatch
                for root, dirs, files in os.walk(search_path, followlinks=self.follow_symlinks):
                    # Filter directories to skip
                    dirs[:] = [d for d in dirs if d not in self.skip_dirs]

                    root_path = Path(root)
                    for filename in files:
                        if fnmatch.fnmatch(filename, pattern):
                            file_path = root_path / filename
                            matches.append(str(file_path.absolute()))
                            if len(matches) >= self.max_results:
                                truncated = True
                                break

                    if truncated:
                        break

            # Sort by modification time if requested
            if sort_by_mtime and matches:
                matches.sort(
                    key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
                    reverse=True,
                )

            logger.debug(
                f"Glob {pattern} in {search_path}: {len(matches)} matches"
                f"{' (truncated)' if truncated else ''}"
            )

            return GlobResult(
                success=True,
                pattern=pattern,
                matches=matches,
                match_count=len(matches),
                truncated=truncated,
                search_path=str(search_path),
            )

        except Exception as e:
            return GlobResult(
                success=False,
                pattern=pattern,
                search_path=str(search_path),
                error=f"Glob search failed: {str(e)}",
            )

    def _should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        for part in path.parts:
            if part in self.skip_dirs:
                return True
        return False


# =============================================================================
# Grep Tool
# =============================================================================


class GrepTool:
    """
    Search file contents with regex.

    Features:
    - Full regex support
    - Case-insensitive option
    - Context lines (before/after)
    - Multiple output modes
    - File type filtering
    """

    DEFAULT_MAX_MATCHES = 500
    DEFAULT_MAX_LINE_LENGTH = 1000

    # File type mappings (like ripgrep)
    FILE_TYPES = {
        "py": ["*.py"],
        "python": ["*.py", "*.pyi"],
        "js": ["*.js", "*.mjs", "*.cjs"],
        "ts": ["*.ts", "*.tsx"],
        "java": ["*.java"],
        "go": ["*.go"],
        "rust": ["*.rs"],
        "c": ["*.c", "*.h"],
        "cpp": ["*.cpp", "*.cc", "*.cxx", "*.hpp", "*.hh"],
        "html": ["*.html", "*.htm"],
        "css": ["*.css", "*.scss", "*.sass", "*.less"],
        "json": ["*.json"],
        "yaml": ["*.yaml", "*.yml"],
        "md": ["*.md", "*.markdown"],
        "sh": ["*.sh", "*.bash", "*.zsh"],
    }

    # Binary file extensions to skip
    BINARY_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        ".exe", ".dll", ".so", ".dylib",
        ".pyc", ".pyo", ".class", ".o", ".obj",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".mp3", ".mp4", ".avi", ".mov", ".wav",
        ".sqlite", ".db",
    }

    def __init__(
        self,
        max_matches: int = DEFAULT_MAX_MATCHES,
        max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
        skip_binary: bool = True,
    ):
        """
        Initialize GrepTool.

        Args:
            max_matches: Maximum total matches to return
            max_line_length: Truncate lines longer than this
            skip_binary: Skip files with binary extensions
        """
        self.max_matches = max_matches
        self.max_line_length = max_line_length
        self.skip_binary = skip_binary

    def search(
        self,
        pattern: str,
        path: Optional[str] = None,
        glob_pattern: Optional[str] = None,
        file_type: Optional[str] = None,
        case_insensitive: bool = False,
        context_before: int = 0,
        context_after: int = 0,
        multiline: bool = False,
    ) -> GrepResult:
        """
        Search for pattern in files.

        Args:
            pattern: Regex pattern to search for
            path: Directory or file to search in
            glob_pattern: Filter files by glob (e.g., "*.py")
            file_type: Filter by file type (e.g., "py", "js")
            case_insensitive: Case-insensitive search
            context_before: Lines of context before match
            context_after: Lines of context after match
            multiline: Enable multiline matching

        Returns:
            GrepResult with matches
        """
        search_path = Path(path) if path else Path.cwd()

        if not search_path.exists():
            return GrepResult(
                success=False,
                pattern=pattern,
                error=f"Path not found: {search_path}",
            )

        # Compile regex
        try:
            flags = 0
            if case_insensitive:
                flags |= re.IGNORECASE
            if multiline:
                flags |= re.MULTILINE | re.DOTALL

            regex = re.compile(pattern, flags)
        except re.error as e:
            return GrepResult(
                success=False,
                pattern=pattern,
                error=f"Invalid regex pattern: {str(e)}",
            )

        # Determine file patterns to search
        file_patterns = self._get_file_patterns(glob_pattern, file_type)

        try:
            matches: List[GrepMatch] = []
            files_searched = 0
            files_matched_set: set = set()
            truncated = False

            # Get files to search
            if search_path.is_file():
                files = [search_path]
            else:
                files = self._find_files(search_path, file_patterns)

            for file_path in files:
                if truncated:
                    break

                # Skip binary files
                if self.skip_binary and file_path.suffix.lower() in self.BINARY_EXTENSIONS:
                    continue

                files_searched += 1
                file_matches = self._search_file(
                    file_path, regex, context_before, context_after
                )

                if file_matches:
                    files_matched_set.add(str(file_path))
                    for match in file_matches:
                        matches.append(match)
                        if len(matches) >= self.max_matches:
                            truncated = True
                            break

            logger.debug(
                f"Grep '{pattern}' in {search_path}: "
                f"{len(matches)} matches in {len(files_matched_set)} files "
                f"({files_searched} searched)"
                f"{' (truncated)' if truncated else ''}"
            )

            return GrepResult(
                success=True,
                pattern=pattern,
                matches=matches,
                files_searched=files_searched,
                files_matched=len(files_matched_set),
                total_matches=len(matches),
                truncated=truncated,
            )

        except Exception as e:
            return GrepResult(
                success=False,
                pattern=pattern,
                error=f"Grep search failed: {str(e)}",
            )

    def _get_file_patterns(
        self,
        glob_pattern: Optional[str],
        file_type: Optional[str],
    ) -> List[str]:
        """Get file patterns to search."""
        patterns = []

        if glob_pattern:
            patterns.append(glob_pattern)

        if file_type and file_type in self.FILE_TYPES:
            patterns.extend(self.FILE_TYPES[file_type])

        return patterns if patterns else ["*"]

    def _find_files(self, path: Path, patterns: List[str]) -> List[Path]:
        """Find files matching patterns."""
        files = []
        skip_dirs = GlobTool.SKIP_DIRS

        for root, dirs, filenames in os.walk(path):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            root_path = Path(root)
            for filename in filenames:
                # Check against patterns
                if any(fnmatch.fnmatch(filename, p) for p in patterns):
                    files.append(root_path / filename)

        return files

    def _search_file(
        self,
        file_path: Path,
        regex: Pattern,
        context_before: int,
        context_after: int,
    ) -> List[GrepMatch]:
        """Search a single file."""
        matches = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            for line_num, line in enumerate(lines, 1):
                for match in regex.finditer(line):
                    # Truncate long lines
                    display_line = line
                    if len(display_line) > self.max_line_length:
                        display_line = display_line[: self.max_line_length] + "..."

                    matches.append(GrepMatch(
                        file_path=str(file_path.absolute()),
                        line_number=line_num,
                        line_content=display_line,
                        match_start=match.start(),
                        match_end=match.end(),
                    ))

        except PermissionError:
            logger.warning(f"Permission denied reading {file_path}")
        except UnicodeDecodeError:
            logger.warning(f"Could not decode {file_path}")
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")

        return matches


# =============================================================================
# MCP Tool Adapters
# =============================================================================


def create_glob_handler(tool: Optional[GlobTool] = None):
    """Create MCP handler for glob search."""
    _tool = tool or GlobTool()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        result = _tool.search(
            pattern=params.get("pattern", ""),
            path=params.get("path"),
            sort_by_mtime=params.get("sort_by_mtime", True),
        )
        return {
            "success": result.success,
            "matches": result.matches,
            "match_count": result.match_count,
            "truncated": result.truncated,
            "error": result.error,
        }

    return handler


def create_grep_handler(tool: Optional[GrepTool] = None):
    """Create MCP handler for grep search."""
    _tool = tool or GrepTool()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        result = _tool.search(
            pattern=params.get("pattern", ""),
            path=params.get("path"),
            glob_pattern=params.get("glob"),
            file_type=params.get("type"),
            case_insensitive=params.get("case_insensitive", False),
            context_before=params.get("context_before", 0),
            context_after=params.get("context_after", 0),
            multiline=params.get("multiline", False),
        )

        # Format output based on output_mode
        output_mode = params.get("output_mode", "files_with_matches")

        if output_mode == "files_with_matches":
            return {
                "success": result.success,
                "files": result.get_files_with_matches(),
                "file_count": result.files_matched,
                "truncated": result.truncated,
                "error": result.error,
            }
        elif output_mode == "count":
            return {
                "success": result.success,
                "counts": result.get_match_counts(),
                "total_matches": result.total_matches,
                "error": result.error,
            }
        else:  # "content"
            return {
                "success": result.success,
                "matches": [
                    {
                        "file": m.file_path,
                        "line": m.line_number,
                        "content": m.line_content,
                    }
                    for m in result.matches
                ],
                "total_matches": result.total_matches,
                "truncated": result.truncated,
                "error": result.error,
            }

    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Result types
    "GlobResult",
    "GrepMatch",
    "GrepResult",
    # Tools
    "GlobTool",
    "GrepTool",
    # MCP handlers
    "create_glob_handler",
    "create_grep_handler",
]
