"""vLLM version compatibility checker for Mode B (#2 path).

The CTM+ vLLM evictor patch targets the ``BlockSpaceManagerV1`` +
public ``Evictor`` ABC interface that existed in vLLM ≤ 0.4.x. The
patch raises ``NotImplementedError`` on vLLM ≥ 0.5.x because the
new ``CpuGpuBlockAllocator`` does not expose a public eviction-
policy hook (see ``vllm_evictor.py:patch_vllm_engine`` and
``MODE_B_RUNBOOK.md`` §8).

This module provides a small pure-Python helper that the
``run_mode_b_vllm04.sh`` runbook calls during pre-flight to give
a clear error if vLLM is not at a compatible version. The logic
is broken out of the shell script so it can be unit-tested
without requiring vLLM to be installed.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Optional, Tuple


# Compatibility bands the CTM+ patch knows about.
# Paths in the validation roadmap:
#   * #2: pin to vLLM 0.4.x — uses the existing patch as-is.
#   * #3: vLLM 0.5+ rewrite — required for vLLM 0.5+ and 0.7+.
SUPPORTED_BAND_VLLM_04: Tuple[Tuple[int, int, int], Tuple[int, int, int]] = (
    (0, 4, 0),
    (0, 4, 99),
)


@dataclass(frozen=True)
class VersionCheckResult:
    """Outcome of a vLLM compatibility check."""

    version_str: Optional[str]
    parsed: Optional[Tuple[int, int, int]]
    supported_for_path_2: bool
    message: str


def parse_vllm_version(s: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Parse a vLLM version string like ``0.4.3`` or ``0.4.3.post1``
    into a ``(major, minor, patch)`` tuple. Returns ``None`` if the
    string can't be parsed.

    Tolerates trailing ``.postN``, ``.devN``, ``+local`` suffixes
    that PEP-440-style versions may include.
    """
    if not s:
        return None
    m = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)", s)
    if m is None:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def check_vllm_for_path_2(version_str: Optional[str]) -> VersionCheckResult:
    """Decide whether a given vLLM version string is compatible
    with the validation roadmap's #2 path (pin to vLLM 0.4.x +
    use the existing CTM+ evictor patch).

    Returns a :class:`VersionCheckResult` whose ``message`` field
    is a human-readable explanation suitable for the shell script
    to print verbatim.
    """
    if version_str is None:
        return VersionCheckResult(
            version_str=None,
            parsed=None,
            supported_for_path_2=False,
            message=(
                "ERROR: vLLM is not installed. Install a 0.4.x release "
                "(e.g. `pip install 'vllm==0.4.3'`) and re-run."
            ),
        )

    parsed = parse_vllm_version(version_str)
    if parsed is None:
        return VersionCheckResult(
            version_str=version_str,
            parsed=None,
            supported_for_path_2=False,
            message=(
                f"ERROR: cannot parse vLLM version string {version_str!r}. "
                "Expected something like '0.4.3' or '0.4.3.post1'."
            ),
        )

    lo, hi = SUPPORTED_BAND_VLLM_04
    if lo <= parsed <= hi:
        return VersionCheckResult(
            version_str=version_str,
            parsed=parsed,
            supported_for_path_2=True,
            message=(
                f"OK: vLLM {version_str} is in the supported 0.4.x band "
                "for the CTM+ evictor patch (validation roadmap #2)."
            ),
        )

    if parsed >= (0, 5, 0):
        return VersionCheckResult(
            version_str=version_str,
            parsed=parsed,
            supported_for_path_2=False,
            message=(
                f"ERROR: vLLM {version_str} is too new for the existing "
                "CTM+ evictor patch. vLLM 0.5+ replaced "
                "BlockSpaceManagerV1's public Evictor hook with a private "
                "CpuGpuBlockAllocator allocator dict; the patch raises "
                "NotImplementedError on this version. Two paths:\n"
                "  - Validation roadmap #2: pin to vLLM 0.4.x "
                "(`pip install 'vllm==0.4.3'`) and re-run.\n"
                "  - Validation roadmap #3: rewrite the integration "
                "against the post-0.5 allocator architecture (2-3 days; "
                "see MODE_B_RUNBOOK.md §8)."
            ),
        )

    # parsed < (0, 4, 0)
    return VersionCheckResult(
        version_str=version_str,
        parsed=parsed,
        supported_for_path_2=False,
        message=(
            f"ERROR: vLLM {version_str} predates 0.4.0 and lacks the "
            "BlockSpaceManagerV1 + Evictor ABC the patch targets. "
            "Upgrade to vLLM 0.4.x (`pip install 'vllm==0.4.3'`)."
        ),
    )


def _read_installed_vllm_version() -> Optional[str]:
    """Return the installed vLLM's ``__version__`` if vLLM is on
    the import path, else ``None``. Wrapped in a function so the
    CLI can mock it in tests."""
    try:
        import vllm  # type: ignore

        return getattr(vllm, "__version__", None)
    except ImportError:
        return None


def main(argv) -> int:
    parser = argparse.ArgumentParser(
        prog="vllm_version_check",
        description=(
            "Check the installed vLLM version against the "
            "compatibility band the CTM+ evictor patch targets "
            "(0.4.x). Emits a clear pass/fail message + exit code "
            "for the run_mode_b_vllm04.sh pre-flight."
        ),
    )
    parser.add_argument(
        "--version",
        default=None,
        help=(
            "Optional version string to check instead of importing "
            "vllm. Useful for testing and for documenting the "
            "expected version in CI."
        ),
    )
    args = parser.parse_args(argv)

    version_str = args.version
    if version_str is None:
        version_str = _read_installed_vllm_version()

    result = check_vllm_for_path_2(version_str)
    print(result.message)
    return 0 if result.supported_for_path_2 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
