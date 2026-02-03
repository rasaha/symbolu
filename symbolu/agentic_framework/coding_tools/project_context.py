"""
Project Context for Codebase Understanding

Provides project analysis for the Sentinel agentic framework:
- Language detection
- Dependency parsing
- Framework detection
- Project structure analysis

Helps the agent understand the codebase context.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


@dataclass
class ProjectContext:
    """
    Context information about a code project.

    Provides structured understanding of the codebase.
    """
    # Basic info
    root_path: str = ""
    name: str = ""

    # Languages
    primary_language: str = ""
    languages: Dict[str, int] = field(default_factory=dict)  # language -> file count

    # Framework/Runtime
    framework: Optional[str] = None
    runtime: Optional[str] = None
    runtime_version: Optional[str] = None

    # Structure
    source_dirs: List[str] = field(default_factory=list)
    test_dirs: List[str] = field(default_factory=list)
    config_files: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)

    # Dependencies
    dependencies: Dict[str, str] = field(default_factory=dict)  # package -> version
    dev_dependencies: Dict[str, str] = field(default_factory=dict)

    # Conventions
    indent_style: str = "spaces"  # "spaces" or "tabs"
    indent_size: int = 4
    naming_convention: str = "snake_case"  # "snake_case", "camelCase", "PascalCase"

    # Metadata
    has_git: bool = False
    has_tests: bool = False
    has_ci: bool = False
    has_docker: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_path": self.root_path,
            "name": self.name,
            "primary_language": self.primary_language,
            "languages": self.languages,
            "framework": self.framework,
            "runtime": self.runtime,
            "runtime_version": self.runtime_version,
            "source_dirs": self.source_dirs,
            "test_dirs": self.test_dirs,
            "config_files": self.config_files,
            "entry_points": self.entry_points,
            "dependencies": self.dependencies,
            "dev_dependencies": self.dev_dependencies,
            "indent_style": self.indent_style,
            "indent_size": self.indent_size,
            "naming_convention": self.naming_convention,
            "has_git": self.has_git,
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            "has_docker": self.has_docker,
        }

    def summary(self) -> str:
        """Generate a text summary of the project."""
        parts = []

        if self.name:
            parts.append(f"Project: {self.name}")

        if self.primary_language:
            lang_info = self.primary_language
            if self.framework:
                lang_info += f" ({self.framework})"
            parts.append(f"Language: {lang_info}")

        if self.runtime and self.runtime_version:
            parts.append(f"Runtime: {self.runtime} {self.runtime_version}")

        if self.dependencies:
            parts.append(f"Dependencies: {len(self.dependencies)} packages")

        features = []
        if self.has_git:
            features.append("git")
        if self.has_tests:
            features.append("tests")
        if self.has_ci:
            features.append("CI")
        if self.has_docker:
            features.append("docker")
        if features:
            parts.append(f"Features: {', '.join(features)}")

        return "\n".join(parts)


# =============================================================================
# Project Analyzer
# =============================================================================


class ProjectAnalyzer:
    """
    Analyzes a project directory to build context.

    Detects:
    - Primary language
    - Frameworks and runtimes
    - Dependencies
    - Project structure
    - Coding conventions
    """

    # Language detection by extension
    LANGUAGE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".kt": "kotlin",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".swift": "swift",
        ".m": "objective-c",
        ".scala": "scala",
        ".r": "r",
        ".R": "r",
        ".jl": "julia",
    }

    # Config file patterns
    CONFIG_PATTERNS = {
        "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
        "javascript": ["package.json", "tsconfig.json", ".babelrc"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "go": ["go.mod", "go.sum"],
        "rust": ["Cargo.toml"],
        "ruby": ["Gemfile", "*.gemspec"],
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "django": ["manage.py", "settings.py", "wsgi.py"],
        "flask": ["app.py", "flask"],
        "fastapi": ["fastapi"],
        "react": ["react", "react-dom"],
        "vue": ["vue"],
        "angular": ["@angular/core"],
        "express": ["express"],
        "nextjs": ["next"],
        "rails": ["rails", "Gemfile"],
        "spring": ["spring-boot"],
    }

    # Directories to skip
    SKIP_DIRS = {
        ".git", ".svn", ".hg", "node_modules", "__pycache__",
        ".mypy_cache", ".pytest_cache", "venv", ".venv", "env",
        "dist", "build", ".eggs", "target", ".idea", ".vscode",
    }

    def __init__(self, root_path: Optional[str] = None):
        """
        Initialize ProjectAnalyzer.

        Args:
            root_path: Root path of the project
        """
        self.root_path = Path(root_path) if root_path else Path.cwd()

    def analyze(self) -> ProjectContext:
        """
        Analyze the project and build context.

        Returns:
            ProjectContext with project information
        """
        context = ProjectContext(
            root_path=str(self.root_path.absolute()),
            name=self.root_path.name,
        )

        # Detect languages
        context.languages = self._detect_languages()
        if context.languages:
            context.primary_language = max(
                context.languages.items(),
                key=lambda x: x[1]
            )[0]

        # Find config files
        context.config_files = self._find_config_files()

        # Parse dependencies
        self._parse_dependencies(context)

        # Detect framework
        context.framework = self._detect_framework(context)

        # Find source and test directories
        context.source_dirs = self._find_source_dirs(context.primary_language)
        context.test_dirs = self._find_test_dirs()

        # Find entry points
        context.entry_points = self._find_entry_points(context.primary_language)

        # Detect conventions
        self._detect_conventions(context)

        # Check for common features
        context.has_git = (self.root_path / ".git").is_dir()
        context.has_tests = bool(context.test_dirs)
        context.has_ci = self._has_ci()
        context.has_docker = (
            (self.root_path / "Dockerfile").exists() or
            (self.root_path / "docker-compose.yml").exists()
        )

        logger.info(f"Analyzed project: {context.name}, {context.primary_language}")

        return context

    def _detect_languages(self) -> Dict[str, int]:
        """Detect languages by counting files."""
        counts: Dict[str, int] = {}

        for root, dirs, files in os.walk(self.root_path):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for filename in files:
                ext = Path(filename).suffix.lower()
                if ext in self.LANGUAGE_EXTENSIONS:
                    lang = self.LANGUAGE_EXTENSIONS[ext]
                    counts[lang] = counts.get(lang, 0) + 1

        return counts

    def _find_config_files(self) -> List[str]:
        """Find configuration files."""
        config_files = []

        # Check known config files
        known_configs = [
            "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
            "package.json", "tsconfig.json",
            "Cargo.toml", "go.mod",
            "Makefile", "Dockerfile", "docker-compose.yml",
            ".env", ".env.example",
            "README.md", "README.rst",
        ]

        for config in known_configs:
            config_path = self.root_path / config
            if config_path.exists():
                config_files.append(config)

        return config_files

    def _parse_dependencies(self, context: ProjectContext) -> None:
        """Parse dependencies from config files."""
        # Python: pyproject.toml
        pyproject = self.root_path / "pyproject.toml"
        if pyproject.exists():
            self._parse_pyproject(pyproject, context)

        # Python: requirements.txt
        requirements = self.root_path / "requirements.txt"
        if requirements.exists():
            self._parse_requirements(requirements, context)

        # JavaScript: package.json
        package_json = self.root_path / "package.json"
        if package_json.exists():
            self._parse_package_json(package_json, context)

    def _parse_pyproject(self, path: Path, context: ProjectContext) -> None:
        """Parse pyproject.toml."""
        try:
            content = path.read_text()

            # Simple TOML parsing for dependencies
            # Full TOML parsing would require tomllib (Python 3.11+)
            in_deps = False
            in_dev_deps = False

            for line in content.splitlines():
                line = line.strip()

                if line.startswith("[project.dependencies]") or line.startswith("dependencies = ["):
                    in_deps = True
                    in_dev_deps = False
                elif line.startswith("[project.optional-dependencies]") or line.startswith("[tool."):
                    in_deps = False
                    in_dev_deps = "dev" in line
                elif line.startswith("["):
                    in_deps = False
                    in_dev_deps = False
                elif in_deps or in_dev_deps:
                    # Parse dependency line
                    match = re.match(r'"?([a-zA-Z0-9_-]+)"?\s*[>=<~^]*\s*"?([0-9.]*)"?', line)
                    if match:
                        pkg, version = match.groups()
                        if in_dev_deps:
                            context.dev_dependencies[pkg] = version or "*"
                        else:
                            context.dependencies[pkg] = version or "*"

            # Extract Python version
            version_match = re.search(r'requires-python\s*=\s*"([^"]+)"', content)
            if version_match:
                context.runtime = "python"
                context.runtime_version = version_match.group(1)

        except Exception as e:
            logger.debug(f"Failed to parse pyproject.toml: {e}")

    def _parse_requirements(self, path: Path, context: ProjectContext) -> None:
        """Parse requirements.txt."""
        try:
            content = path.read_text()

            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue

                # Parse package==version or package>=version
                match = re.match(r'([a-zA-Z0-9_-]+)\s*([>=<~^!]+)?\s*(.+)?', line)
                if match:
                    pkg = match.group(1)
                    version = match.group(3) or "*"
                    context.dependencies[pkg] = version

        except Exception as e:
            logger.debug(f"Failed to parse requirements.txt: {e}")

    def _parse_package_json(self, path: Path, context: ProjectContext) -> None:
        """Parse package.json."""
        try:
            content = json.loads(path.read_text())

            context.dependencies.update(content.get("dependencies", {}))
            context.dev_dependencies.update(content.get("devDependencies", {}))

            # Extract Node version
            engines = content.get("engines", {})
            if "node" in engines:
                context.runtime = "node"
                context.runtime_version = engines["node"]

        except Exception as e:
            logger.debug(f"Failed to parse package.json: {e}")

    def _detect_framework(self, context: ProjectContext) -> Optional[str]:
        """Detect framework from dependencies and files."""
        deps = set(context.dependencies.keys()) | set(context.dev_dependencies.keys())

        # Check dependency-based patterns
        if "django" in deps:
            return "django"
        if "flask" in deps:
            return "flask"
        if "fastapi" in deps:
            return "fastapi"
        if "react" in deps or "react-dom" in deps:
            return "react"
        if "vue" in deps:
            return "vue"
        if "@angular/core" in deps:
            return "angular"
        if "express" in deps:
            return "express"
        if "next" in deps:
            return "nextjs"

        # Check file-based patterns
        if (self.root_path / "manage.py").exists():
            return "django"

        return None

    def _find_source_dirs(self, language: str) -> List[str]:
        """Find source directories."""
        source_dirs = []

        common_src_dirs = ["src", "lib", "app", "source"]
        language_dirs = {
            "python": ["src", self.root_path.name],
            "javascript": ["src", "lib", "app"],
            "java": ["src/main/java"],
            "go": ["cmd", "pkg", "internal"],
        }

        dirs_to_check = language_dirs.get(language, common_src_dirs)

        for dir_name in dirs_to_check:
            dir_path = self.root_path / dir_name
            if dir_path.is_dir():
                source_dirs.append(dir_name)

        return source_dirs

    def _find_test_dirs(self) -> List[str]:
        """Find test directories."""
        test_dirs = []

        common_test_dirs = [
            "tests", "test", "spec", "specs",
            "src/test", "src/tests",
            "__tests__",
        ]

        for dir_name in common_test_dirs:
            dir_path = self.root_path / dir_name
            if dir_path.is_dir():
                test_dirs.append(dir_name)

        return test_dirs

    def _find_entry_points(self, language: str) -> List[str]:
        """Find entry point files."""
        entry_points = []

        patterns = {
            "python": ["main.py", "app.py", "__main__.py", "cli.py", "run.py"],
            "javascript": ["index.js", "main.js", "app.js", "server.js"],
            "typescript": ["index.ts", "main.ts", "app.ts"],
            "go": ["main.go", "cmd/main.go"],
            "java": ["Main.java", "Application.java"],
        }

        for pattern in patterns.get(language, []):
            # Check root
            if (self.root_path / pattern).exists():
                entry_points.append(pattern)

            # Check src
            if (self.root_path / "src" / pattern).exists():
                entry_points.append(f"src/{pattern}")

        return entry_points

    def _detect_conventions(self, context: ProjectContext) -> None:
        """Detect coding conventions from sample files."""
        # Find a sample file
        sample_file = None
        ext_map = {
            "python": "*.py",
            "javascript": "*.js",
            "typescript": "*.ts",
        }

        pattern = ext_map.get(context.primary_language, "*.py")

        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

            for filename in files:
                if Path(filename).suffix == pattern[1:]:
                    sample_file = Path(root) / filename
                    break
            if sample_file:
                break

        if not sample_file:
            return

        try:
            content = sample_file.read_text()
            lines = content.splitlines()

            # Detect indent
            for line in lines:
                if line and line[0] in " \t":
                    if line[0] == "\t":
                        context.indent_style = "tabs"
                        context.indent_size = 1
                    else:
                        context.indent_style = "spaces"
                        # Count leading spaces
                        spaces = len(line) - len(line.lstrip(" "))
                        if spaces in (2, 4, 8):
                            context.indent_size = spaces
                    break

            # Detect naming convention
            if context.primary_language == "python":
                context.naming_convention = "snake_case"
            elif context.primary_language in ("javascript", "typescript"):
                context.naming_convention = "camelCase"
            elif context.primary_language == "java":
                context.naming_convention = "camelCase"

        except Exception:
            pass

    def _has_ci(self) -> bool:
        """Check for CI configuration."""
        ci_paths = [
            ".github/workflows",
            ".gitlab-ci.yml",
            ".circleci/config.yml",
            "Jenkinsfile",
            ".travis.yml",
            "azure-pipelines.yml",
        ]

        for ci_path in ci_paths:
            if (self.root_path / ci_path).exists():
                return True

        return False


# =============================================================================
# MCP Tool Adapter
# =============================================================================


def create_project_context_handler():
    """Create MCP handler for project context."""
    def handler(params: Dict[str, Any]) -> Dict[str, Any]:
        root_path = params.get("path")
        analyzer = ProjectAnalyzer(root_path)
        context = analyzer.analyze()
        return context.to_dict()
    return handler


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ProjectContext",
    "ProjectAnalyzer",
    "create_project_context_handler",
]
