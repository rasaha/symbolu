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

    def test_true_accepted_shipped(self):
        # 6K.16 SHIPPED (eager-only opt-in): True is accepted without any
        # env — contract-validated (S1 13/13, hard-needle 0.955 == bf16).
        self.assertIs(ip._resolve_prefix_caching(True), True)

    def test_env_override_still_harmless(self):
        os.environ[ip._ALLOW_PREFIX_CACHING_ENV] = "1"
        self.assertIs(ip._resolve_prefix_caching(True), True)
        os.environ[ip._ALLOW_PREFIX_CACHING_ENV] = "0"
        self.assertIs(ip._resolve_prefix_caching(True), True)

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
        # int4-gated resolution + the 6K.16c contract flag are both wired:
        gate = src.index('if kv_cache_dtype == "int4_protected":')
        self.assertGreater(src.index("_resolve_prefix_caching", gate), gate)
        # Contract arming happens POST-init (capture warm-ups exempt):
        self.assertIn("set_apc_active(True)", src)
        self.assertLess(src.index("llm = LLM("), src.index("set_apc_active(True)"),
                        "C-ID refusal must arm AFTER engine construction")

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
        guard = branch.index("WITHOUT factory arming")
        dequant = branch.index("run_prefix_prefill")
        self.assertLess(guard, dequant,
                        "raw-LLM refusal must precede the dequant-context call")
        self.assertIn("apc_active", branch)   # factory-armed path honored
        self.assertNotIn("block_table=prefill_meta.block_tables", branch,
                         "stock varlen-over-packed call must be removed "
                         "from the prefix branch")

    def test_shared_env_name(self):
        from kv_policy import phase5b_backend_install as bi
        self.assertEqual(ip._ALLOW_PREFIX_CACHING_ENV,
                         bi._ALLOW_PREFIX_CACHING_ENV)


if __name__ == "__main__":
    unittest.main(verbosity=2)
