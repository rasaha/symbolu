"""
File Tools for Coding Capabilities

Provides file operations for the Sentinel agentic framework:
- FileReadTool: Read files with line numbers
- FileWriteTool: Create/overwrite files
- FileEditTool: Precise string replacement in files

These tools integrate with SafeMCPGateway for safety gating.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class FileReadResult:
    """Result from reading a file."""
    success: bool
    file_path: str
    content: Optional[str] = None
    lines: Optional[List[str]] = None
    line_count: int = 0
    file_size: int = 0
    encoding: str = "utf-8"
    error: Optional[str] = None

    def get_lines_with_numbers(self) -> str:
        """Get content with line numbers (cat -n format)."""
        if not self.lines:
            return ""
        max_width = len(str(len(self.lines)))
        numbered = []
        for i, line in enumerate(self.lines, 1):
            numbered.append(f"{i:>{max_width + 2}}\t{line}")
        return "\n".join(numbered)


@dataclass
class FileWriteResult:
    """Result from writing a file."""
    success: bool
    file_path: str
    bytes_written: int = 0
    created: bool = False  # True if file was created, False if overwritten
    error: Optional[str] = None


@dataclass
class FileEditResult:
    """Result from editing a file."""
    success: bool
    file_path: str
    replacements_made: int = 0
    diff: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# File Read Tool
# =============================================================================


class FileReadTool:
    """
    Read files with line numbers.

    Features:
    - Returns content with line numbers (like cat -n)
    - Supports reading specific line ranges
    - Truncates long lines
    - Handles binary file detection
    """

    DEFAULT_MAX_LINES = 2000
    DEFAULT_MAX_LINE_LENGTH = 2000

    def __init__(
        self,
        max_lines: int = DEFAULT_MAX_LINES,
        max_line_length: int = DEFAULT_MAX_LINE_LENGTH,
        allowed_extensions: Optional[List[str]] = None,
    ):
        """
        Initialize FileReadTool.

        Args:
            max_lines: Maximum lines to read (default 2000)
            max_line_length: Truncate lines longer than this
            allowed_extensions: If set, only allow these extensions
        """
        self.max_lines = max_lines
        self.max_line_length = max_line_length
        self.allowed_extensions = allowed_extensions

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> FileReadResult:
        """
        Read a file.

        Args:
            file_path: Absolute path to the file
            offset: Line number to start from (0-indexed)
            limit: Maximum number of lines to read

        Returns:
            FileReadResult with content and metadata
        """
        path = Path(file_path)

        # Validate path
        if not path.is_absolute():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error="Path must be absolute",
            )

        if not path.exists():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"File not found: {file_path}",
            )

        if not path.is_file():
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"Path is not a file: {file_path}",
            )

        # Check extension if restricted
        if self.allowed_extensions:
            ext = path.suffix.lower()
            if ext not in self.allowed_extensions:
                return FileReadResult(
                    success=False,
                    file_path=file_path,
                    error=f"Extension {ext} not allowed",
                )

        # Check for binary file
        if self._is_binary(path):
            return FileReadResult(
                success=False,
                file_path=file_path,
                error="Binary file detected, cannot read as text",
            )

        # Read file
        try:
            encoding = self._detect_encoding(path)
            with open(path, "r", encoding=encoding, errors="replace") as f:
                all_lines = f.readlines()

            file_size = path.stat().st_size
            total_lines = len(all_lines)

            # Apply offset and limit
            actual_limit = limit or self.max_lines
            end_line = min(offset + actual_limit, total_lines)
            selected_lines = all_lines[offset:end_line]

            # Truncate long lines
            truncated_lines = []
            for line in selected_lines:
                line = line.rstrip("\n\r")
                if len(line) > self.max_line_length:
                    line = line[: self.max_line_length] + "..."
                truncated_lines.append(line)

            content = "\n".join(truncated_lines)

            logger.debug(
                f"Read {len(truncated_lines)} lines from {file_path} "
                f"(offset={offset}, total={total_lines})"
            )

            return FileReadResult(
                success=True,
                file_path=file_path,
                content=content,
                lines=truncated_lines,
                line_count=total_lines,
                file_size=file_size,
                encoding=encoding,
            )

        except PermissionError:
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return FileReadResult(
                success=False,
                file_path=file_path,
                error=f"Failed to read file: {str(e)}",
            )

    def _is_binary(self, path: Path) -> bool:
        """Check if file appears to be binary."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                # Check for null bytes (common in binary files)
                if b"\x00" in chunk:
                    return True
                # Check ratio of non-text bytes
                text_chars = set(bytes(range(32, 127)) + b"\n\r\t\f\b")
                non_text = sum(1 for b in chunk if b not in text_chars)
                return non_text / len(chunk) > 0.3 if chunk else False
        except Exception:
            return True

    def _detect_encoding(self, path: Path) -> str:
        """Detect file encoding (simplified)."""
        # Try to detect BOM
        try:
            with open(path, "rb") as f:
                bom = f.read(4)
                if bom.startswith(b"\xef\xbb\xbf"):
                    return "utf-8-sig"
                if bom.startswith(b"\xff\xfe\x00\x00"):
                    return "utf-32-le"
                if bom.startswith(b"\x00\x00\xfe\xff"):
                    return "utf-32-be"
                if bom.startswith(b"\xff\xfe"):
                    return "utf-16-le"
                if bom.startswith(b"\xfe\xff"):
                    return "utf-16-be"
        except Exception:
            pass
        return "utf-8"


# =============================================================================
# File Write Tool
# =============================================================================


class FileWriteTool:
    """
    Write/create files.

    Features:
    - Creates parent directories if needed
    - Atomic writes (temp file + rename)
    - Backup option for existing files
    """

    def __init__(
        self,
        create_parents: bool = True,
        atomic: bool = True,
        backup: bool = False,
        allowed_extensions: Optional[List[str]] = None,
    ):
        """
        Initialize FileWriteTool.

        Args:
            create_parents: Create parent directories if missing
            atomic: Use atomic write (temp file + rename)
            backup: Create .bak backup of existing files
            allowed_extensions: If set, only allow these extensions
        """
        self.create_parents = create_parents
        self.atomic = atomic
        self.backup = backup
        self.allowed_extensions = allowed_extensions

    def write(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> FileWriteResult:
        """
        Write content to a file.

        Args:
            file_path: Absolute path to the file
            content: Content to write
            encoding: File encoding

        Returns:
            FileWriteResult with status
        """
        path = Path(file_path)

        # Validate path
        if not path.is_absolute():
            return FileWriteResult(
                success=False,
                file_path=file_path,
                error="Path must be absolute",
            )

        # Check extension if restricted
        if self.allowed_extensions:
            ext = path.suffix.lower()
            if ext not in self.allowed_extensions:
                return FileWriteResult(
                    success=False,
                    file_path=file_path,
                    error=f"Extension {ext} not allowed",
                )

        # Check if file exists (for created flag)
        existed = path.exists()

        try:
            # Create parent directories
            if self.create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Backup existing file
            if existed and self.backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)

            # Write content
            content_bytes = content.encode(encoding)

            if self.atomic:
                # Atomic write: temp file + rename
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=path.parent,
                    delete=False,
                    suffix=".tmp",
                ) as f:
                    f.write(content_bytes)
                    temp_path = f.name

                shutil.move(temp_path, path)
            else:
                # Direct write
                with open(path, "wb") as f:
                    f.write(content_bytes)

            logger.info(
                f"{'Created' if not existed else 'Overwrote'} {file_path} "
                f"({len(content_bytes)} bytes)"
            )

            return FileWriteResult(
                success=True,
                file_path=file_path,
                bytes_written=len(content_bytes),
                created=not existed,
            )

        except PermissionError:
            return FileWriteResult(
                success=False,
                file_path=file_path,
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return FileWriteResult(
                success=False,
                file_path=file_path,
                error=f"Failed to write file: {str(e)}",
            )


# =============================================================================
# File Edit Tool
# =============================================================================


class FileEditTool:
    """
    Precise file editing with exact string replacement.

    Features:
    - Exact string matching (not regex by default)
    - Uniqueness check to prevent ambiguous edits
    - Generates unified diff for review
    - Atomic writes for safety
    """

    def __init__(
        self,
        require_unique: bool = True,
        atomic: bool = True,
        backup: bool = False,
    ):
        """
        Initialize FileEditTool.

        Args:
            require_unique: Require old_string to be unique (unless replace_all)
            atomic: Use atomic write
            backup: Create backup before editing
        """
        self.require_unique = require_unique
        self.atomic = atomic
        self.backup = backup

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> FileEditResult:
        """
        Edit a file by replacing exact string.

        Args:
            file_path: Absolute path to the file
            old_string: Exact string to replace (must be unique unless replace_all)
            new_string: Replacement string
            replace_all: If True, replace all occurrences

        Returns:
            FileEditResult with diff and status
        """
        path = Path(file_path)

        # Validate path
        if not path.is_absolute():
            return FileEditResult(
                success=False,
                file_path=file_path,
                error="Path must be absolute",
            )

        if not path.exists():
            return FileEditResult(
                success=False,
                file_path=file_path,
                error=f"File not found: {file_path}",
            )

        if not path.is_file():
            return FileEditResult(
                success=False,
                file_path=file_path,
                error=f"Path is not a file: {file_path}",
            )

        # Validate strings
        if not old_string:
            return FileEditResult(
                success=False,
                file_path=file_path,
                error="old_string cannot be empty",
            )

        if old_string == new_string:
            return FileEditResult(
                success=False,
                file_path=file_path,
                error="old_string and new_string are identical",
            )

        try:
            # Read current content
            content = path.read_text()

            # Check occurrences
            count = content.count(old_string)

            if count == 0:
                return FileEditResult(
                    success=False,
                    file_path=file_path,
                    error="old_string not found in file",
                )

            if count > 1 and not replace_all and self.require_unique:
                return FileEditResult(
                    success=False,
                    file_path=file_path,
                    error=(
                        f"old_string appears {count} times. "
                        "Use replace_all=True or provide more context to make it unique."
                    ),
                )

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replacements = 1

            # Generate diff
            diff = self._generate_diff(content, new_content, file_path)

            # Backup existing file
            if self.backup:
                backup_path = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup_path)

            # Write new content
            if self.atomic:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=path.parent,
                    delete=False,
                    suffix=".tmp",
                    encoding="utf-8",
                ) as f:
                    f.write(new_content)
                    temp_path = f.name
                shutil.move(temp_path, path)
            else:
                path.write_text(new_content)

            logger.info(
                f"Edited {file_path}: {replacements} replacement(s)"
            )

            return FileEditResult(
                success=True,
                file_path=file_path,
                replacements_made=replacements,
                diff=diff,
            )

        except PermissionError:
            return FileEditResult(
                success=False,
                file_path=file_path,
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return FileEditResult(
                success=False,
                file_path=file_path,
                error=f"Failed to edit file: {str(e)}",
            )

    def _generate_diff(
        self,
        old_content: str,
        new_content: str,
        file_path: str,
    ) -> str:
        """Generate unified diff."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = list(unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{Path(file_path).name}",
            tofile=f"b/{Path(file_path).name}",
            lineterm="",
        ))

        return "".join(diff_lines)


# =============================================================================
# MCP Tool Adapters
# =============================================================================


def create_file_read_handler(tool: Optional[FileReadTool] = None):
    """Create MCP handler for file read."""
    _tool = tool or FileReadTool()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        result = _tool.read(
            file_path=params.get("file_path", ""),
            offset=params.get("offset", 0),
            limit=params.get("limit"),
        )
        return {
            "success": result.success,
            "content": result.get_lines_with_numbers() if result.success else None,
            "line_count": result.line_count,
            "error": result.error,
        }

    return handler


def create_file_write_handler(tool: Optional[FileWriteTool] = None):
    """Create MCP handler for file write."""
    _tool = tool or FileWriteTool()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        result = _tool.write(
            file_path=params.get("file_path", ""),
            content=params.get("content", ""),
        )
        return {
            "success": result.success,
            "bytes_written": result.bytes_written,
            "created": result.created,
            "error": result.error,
        }

    return handler


def create_file_edit_handler(tool: Optional[FileEditTool] = None):
    """Create MCP handler for file edit."""
    _tool = tool or FileEditTool()

    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        result = _tool.edit(
            file_path=params.get("file_path", ""),
            old_string=params.get("old_string", ""),
            new_string=params.get("new_string", ""),
            replace_all=params.get("replace_all", False),
        )
        return {
            "success": result.success,
            "replacements_made": result.replacements_made,
            "diff": result.diff,
            "error": result.error,
        }

    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Result types
    "FileReadResult",
    "FileWriteResult",
    "FileEditResult",
    # Tools
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    # MCP handlers
    "create_file_read_handler",
    "create_file_write_handler",
    "create_file_edit_handler",
]
