"""Distribution version (single source of truth).

Read statically by the build backend (``[tool.setuptools.dynamic]``) so the
version never requires importing the package.
"""

__version__ = "0.3.0"
