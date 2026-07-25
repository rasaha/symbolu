"""Shared machinery for the provider conformance kits."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from typing import Callable

from ..contracts.base import Provider
from ..errors import ProviderError
from ..metadata import ProviderKind
from ..version import is_contract_compatible
from ..version import TARGET_KERNEL_MAJOR


@dataclass(frozen=True)
class CheckResult:
    dimension: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ProviderConformanceReport:
    kind: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"{self.kind}: {ok}/{len(self.results)} conformance checks passed"


def ok(dim, name, detail=""):
    return CheckResult(dim, name, True, detail)


def fail(dim, name, detail=""):
    return CheckResult(dim, name, False, detail)


def common_checks(provider_factory: Callable[[], Provider], *,
                  expected_kind: ProviderKind, protocol: type) -> list[CheckResult]:
    """Dimensions shared by every provider kind."""
    out: list[CheckResult] = []
    provider = provider_factory()
    d = provider.descriptor()

    out.append(ok("descriptor", "kind") if d.kind is expected_kind
               else fail("descriptor", "kind", f"{d.kind} != {expected_kind}"))
    out.append(ok("descriptor", "identity")
               if d.provider_id and d.implementation_version and d.contract_version
               else fail("descriptor", "identity", "missing id/version"))
    out.append(ok("descriptor", "capabilities_kind")
               if d.capabilities.kind is expected_kind
               else fail("descriptor", "capabilities_kind", "capabilities kind mismatch"))

    out.append(ok("protocol", "conforms") if isinstance(provider, protocol)
               else fail("protocol", "conforms", f"not a {protocol.__name__}"))

    compatible = (is_contract_compatible(d.contract_version)
                  and str(TARGET_KERNEL_MAJOR) in d.compatibility.compatible_kernel_majors)
    out.append(ok("version", "compatible") if compatible
               else fail("version", "compatible", "declared versions incompatible"))

    out.append(ok("capability", "reported") if d.capabilities.features
               else fail("capability", "reported", "no capability features reported"))

    # lifecycle
    provider.initialize()
    healthy = provider.health().healthy
    provider.shutdown()
    stopped = not provider.health().healthy
    out.append(ok("lifecycle", "init_health_shutdown") if healthy and stopped
               else fail("lifecycle", "init_health_shutdown", "lifecycle transitions wrong"))

    out.append(_no_kernel_internal_imports(provider))
    return out


def _no_kernel_internal_imports(provider: Provider) -> CheckResult:
    """The provider's defining module imports the kernel only via its public api."""
    try:
        source = inspect.getsource(inspect.getmodule(type(provider)))
    except (OSError, TypeError):
        return ok("imports", "kernel_api_only", "source unavailable")
    bad = []
    for node in ast.walk(ast.parse(source)):
        mod = None
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
        elif isinstance(node, ast.Import):
            mod = node.names[0].name
        if mod and mod.startswith("decision_governance") and not mod.startswith("decision_governance.api"):
            bad.append(mod)
    return (ok("imports", "kernel_api_only") if not bad
            else fail("imports", "kernel_api_only", f"internal kernel imports: {bad}"))


def deterministic_fingerprint(call: Callable[[Provider], object],
                              provider_factory: Callable[[], Provider]) -> CheckResult:
    """Two fresh providers, same input → identical non-empty fingerprint."""
    r1 = call(provider_factory())
    r2 = call(provider_factory())
    fp1, fp2 = getattr(r1, "fingerprint", ""), getattr(r2, "fingerprint", "")
    good = fp1 and fp1 == fp2
    return (ok("determinism", "fingerprint") if good
            else fail("determinism", "fingerprint", f"{fp1!r} != {fp2!r}"))


def classified_error(fn: Callable[[], object], *, expected: type) -> CheckResult:
    try:
        fn()
        return fail("errors", expected.__name__, "no error raised")
    except ProviderError as exc:
        good = isinstance(exc, expected) and hasattr(exc, "failure_class")
        return (ok("errors", expected.__name__) if good
                else fail("errors", expected.__name__, f"got {type(exc).__name__}"))
