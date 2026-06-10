"""Phase 6K.15 — CPU tests for the swap-preemption guard.

Pinned acceptance criteria:

  1. Default (caller passes nothing): the resolver returns "recompute" —
     vLLM V0's dynamic policy may pick SWAP for multi-seq groups, and the
     paged writer's sidecars are not migrated on swap, so "leave unset"
     must NOT be the outcome.

  2. Explicit "recompute" (any case/whitespace) is honored.

  3. Explicit "swap" RAISES RuntimeError by default — the loud refusal
     is the whole point (silent KV corruption otherwise).

  4. INT4_PROTECTED_ALLOW_SWAP=1 bypasses the refusal and returns
     "swap" (breakage-repro / migration-dev escape hatch only).

  5. Unknown modes raise ValueError naming the valid options.

  6. Factory wiring: the int4_protected branch routes through the
     resolver; the stock branch (kv_cache_dtype="auto") must NOT inject
     a preemption_mode the caller didn't ask for (verified statically —
     the factory requires vllm at call time, unavailable in CPU CI).

All tests are CPU-only; kv_policy.int4_protected guards its vllm/torch
imports so the module imports cleanly without either.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

from kv_policy import int4_protected as ip


class TestResolvePreemptionMode(unittest.TestCase):
    """The resolver is the load-bearing surface — the factory calls
    ip._resolve_preemption_mode(...) for every int4_protected LLM."""

    def setUp(self):
        os.environ.pop(ip._ALLOW_SWAP_ENV, None)

    def tearDown(self):
        os.environ.pop(ip._ALLOW_SWAP_ENV, None)

    def test_default_is_recompute(self):
        self.assertEqual(ip._resolve_preemption_mode(None), "recompute")

    def test_explicit_recompute_honored(self):
        self.assertEqual(ip._resolve_preemption_mode("recompute"), "recompute")
        self.assertEqual(ip._resolve_preemption_mode("RECOMPUTE"), "recompute")
        self.assertEqual(ip._resolve_preemption_mode("  recompute "), "recompute")

    def test_swap_refused_by_default(self):
        with self.assertRaises(RuntimeError) as cm:
            ip._resolve_preemption_mode("swap")
        msg = str(cm.exception)
        self.assertIn("swap", msg)
        self.assertIn("sidecars", msg)
        self.assertIn(ip._ALLOW_SWAP_ENV, msg)

    def test_swap_case_insensitive_refusal(self):
        with self.assertRaises(RuntimeError):
            ip._resolve_preemption_mode("SWAP")

    def test_env_override_allows_swap(self):
        os.environ[ip._ALLOW_SWAP_ENV] = "1"
        self.assertEqual(ip._resolve_preemption_mode("swap"), "swap")

    def test_env_override_zero_still_refuses(self):
        os.environ[ip._ALLOW_SWAP_ENV] = "0"
        with self.assertRaises(RuntimeError):
            ip._resolve_preemption_mode("swap")

    def test_env_override_does_not_change_default(self):
        os.environ[ip._ALLOW_SWAP_ENV] = "1"
        self.assertEqual(ip._resolve_preemption_mode(None), "recompute")

    def test_unknown_mode_value_error(self):
        with self.assertRaises(ValueError) as cm:
            ip._resolve_preemption_mode("hibernate")
        self.assertIn("recompute", str(cm.exception))


class TestFactoryWiring(unittest.TestCase):
    """Static checks of the factory body (the factory itself needs a GPU
    + vllm to execute; CPU CI verifies the wiring is present and gated)."""

    def _factory_source(self):
        import inspect
        return inspect.getsource(ip.Int4ProtectedLLM)

    def test_factory_routes_through_resolver(self):
        src = self._factory_source()
        self.assertIn("_resolve_preemption_mode", src)
        self.assertIn('kwargs.pop("preemption_mode"', src)

    def test_factory_gates_on_int4_dtype(self):
        # The forced mode must apply ONLY to the int4_protected branch;
        # a stock ("auto") run keeps vLLM's own policy.
        src = self._factory_source()
        idx_gate = src.index('if kv_cache_dtype == "int4_protected":\n'
                             '        kwargs["preemption_mode"]')
        self.assertGreater(idx_gate, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
