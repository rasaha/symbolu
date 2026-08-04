"""Background-job primitives (in-process for this phase; broker-ready interface)."""

from .scope_revalidation import JobScopeRevoked, run_shared_write_job

__all__ = ["JobScopeRevoked", "run_shared_write_job"]
