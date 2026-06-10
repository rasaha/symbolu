"""Phase 6K.16 — CPU tests for the prefix-caching guard.

Pinned acceptance criteria:

  1. Default (caller passes nothing / False): resolver returns False and
     the factory passes an EXPLICIT enable_prefix_caching=False (engine
     logs become self-documenting).

  2. enable_prefix_caching=True RAISES RuntimeError by default — the
     prefix-prefill branch would read the int4-packed cache as bf16.

  3. INT4_PROTECTED_ALLOW_PREFIX_CACHING=1 bypasses (dev escape hatch),
     returning True with a loud warning.

  4. Factory wiring routes through the resolver, gated on the
     int4_protected dtype (stock "auto" runs keep the caller's value).

  5. Backend-side guard exists at the prefix-enabled prefill branch in
     phase5b_backend_install (static check — executing it needs vllm +
     GPU): the RuntimeError + env name are present INSIDE that branch.

All tests are CPU-only.
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


class TestResolvePrefixCaching(unittest.TestCase):

    def setUp(self):
        os.environ.pop(ip._ALLOW_PREFIX_CACHING_ENV, None)

    def tearDown(self):
        os.environ.pop(ip._ALLOW_PREFIX_CACHING_ENV, None)

    def test_default_none_is_false(self):
        self.assertIs(ip._resolve_prefix_caching(None), False)

    def test_explicit_false_is_false(self):
        self.assertIs(ip._resolve_prefix_caching(False), False)

    def test_true_refused_by_default(self):
        with self.assertRaises(RuntimeError) as cm:
            ip._resolve_prefix_caching(True)
        msg = str(cm.exception)
        self.assertIn("prefix", msg.lower())
        self.assertIn("gated", msg)
        self.assertIn("phase6k16_prefix_gates", msg)
        self.assertIn(ip._ALLOW_PREFIX_CACHING_ENV, msg)
        self.assertIn("PHASE6K16_PREFIX_CACHING_PLAN.md", msg)

    def test_env_override_allows_true(self):
        os.environ[ip._ALLOW_PREFIX_CACHING_ENV] = "1"
        self.assertIs(ip._resolve_prefix_caching(True), True)

    def test_env_override_zero_still_refuses(self):
        os.environ[ip._ALLOW_PREFIX_CACHING_ENV] = "0"
        with self.assertRaises(RuntimeError):
            ip._resolve_prefix_caching(True)

    def test_env_override_does_not_change_default(self):
        os.environ[ip._ALLOW_PREFIX_CACHING_ENV] = "1"
        self.assertIs(ip._resolve_prefix_caching(None), False)


class TestWiring(unittest.TestCase):
    """Static checks (the factory + backend branch need vllm/GPU to run)."""

    def test_factory_routes_through_resolver(self):
        import inspect
        src = inspect.getsource(ip.Int4ProtectedLLM)
        self.assertIn("_resolve_prefix_caching", src)
        self.assertIn('kwargs.pop("enable_prefix_caching"', src)
        idx_gate = src.index('if kv_cache_dtype == "int4_protected":\n'
                             '        kwargs["enable_prefix_caching"]')
        self.assertGreater(idx_gate, 0)

    def test_backend_branch_guarded_and_rewired(self):
        # Tier 1: inside the prefix-enabled prefill branch (between the
        # decoder-only assert and the decode section) the guard must come
        # first, the dequant-context path must be called, and the STOCK
        # varlen-over-packed call (its distinctive block_table= line) must
        # be GONE from this branch.
        bi_path = Path(ip.__file__).parent / "phase5b_backend_install.py"
        src = bi_path.read_text()
        self.assertIn("_ALLOW_PREFIX_CACHING_ENV", src)
        anchor = src.index("Only decoder-only models support prefix caching")
        decode_section = src.index("Decode attention", anchor)
        branch = src[anchor:decode_section]
        guard = branch.index("prefix-aware prefill is gated")
        dequant = branch.index("run_prefix_prefill")
        self.assertLess(guard, dequant,
                        "guard must precede the dequant-context call")
        self.assertNotIn("block_table=prefill_meta.block_tables", branch,
                         "stock varlen-over-packed call must be removed "
                         "from the prefix branch")

    def test_shared_env_name(self):
        from kv_policy import phase5b_backend_install as bi
        self.assertEqual(ip._ALLOW_PREFIX_CACHING_ENV,
                         bi._ALLOW_PREFIX_CACHING_ENV)


if __name__ == "__main__":
    unittest.main(verbosity=2)
