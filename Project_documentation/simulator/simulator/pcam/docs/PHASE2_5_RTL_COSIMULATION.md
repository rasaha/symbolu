# PCAM Phase 2.5 — RTL Cosimulation

**Status:** Phase 2.5 complete (harness landed; external simulator required to execute)
**Scope:** bit-parity verification of `simulator/pcam/rtl/core/freq_sketch.sv`
**Contract:** [`docs/design/ADR-0001`](../../../docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Depends on:** Phase 0 (vendored reference), Phase 1 (Python runtime policy)

---

## What Phase 2.5 ships

A cocotb-based parity harness that drives the existing
`freq_sketch.sv` RTL module and `simulator.pcam.kv_policy.FrequencySketch`
from the same deterministic trace and asserts bit-for-bit
observational parity. The harness is ready to run; the actual
execution requires an external SystemVerilog simulator that is not
installed in the default dev environment.

## What a green run proves

The SystemVerilog `freq_sketch` module is observationally equivalent
to the canonical Python reference on every deterministic scenario in
the suite. Because the Python reference is itself a bit-parity port
of the vendored CTM+ reference per ADR-0001, a green cosim run
transitively proves the RTL matches the vendored specification.

## What a green run does NOT prove

- Full `KVCachePolicy` RTL parity. Phase 2.5 is scoped to the sketch
  only — the biggest single translation target, the most error-prone
  halving FSM, and the module the acquisition story leans on hardest.
  The rest of the policy (scoring, classification, victim selection)
  stays on the software side.
- Timing closure or synthesis results. The cosim runs behavioral RTL;
  it says nothing about Fmax, area, or power.
- Multi-sequence or multi-port contention. The sketch is single-port;
  stress testing concurrent increment/estimate paths is a separate
  verification concern.

## Files

| File | Role |
|---|---|
| `simulator/pcam/rtl/tests/test_freq_sketch_cosim.py` | Pytest wrapper. Subprocess-invokes `make cosim`. Skips gracefully when cocotb or a simulator backend is unavailable. |
| `simulator/pcam/rtl/tests/cosim_freq_sketch.py` | Cocotb test module — four `@cocotb.test()` scenarios. Loaded by the Makefile via `MODULE=cosim_freq_sketch`. |
| `simulator/pcam/rtl/tests/Makefile` | Cocotb Makefile. Compiles `pcam_pkg.sv` + `freq_sketch.sv`, elaborates with `CAPACITY=64`, invokes the simulator backend. |
| `simulator/pcam/rtl/tests/conftest.py` | Tells pytest to ignore `cosim_freq_sketch.py` (it's not a pytest module). |
| `simulator/pcam/rtl/tests/__init__.py` | Subpackage marker with a pointer back to this runbook. |

## Scenarios

Four deterministic scenarios, each implemented as a `@cocotb.test()`
function in `cosim_freq_sketch.py`:

1. **`test_single_key_saturation`** — drive 20 increments of key 42,
   assert `inc_min_count` matches the reference every step and
   saturates at 15.
2. **`test_distinct_keys_light_load`** — insert 32 distinct keys,
   probe every one plus an uninserted key 9999, assert estimates
   match the reference exactly.
3. **`test_halving_fires_at_reset_threshold`** — saturate key 0,
   drive 624 filler keys to just under `reset_threshold = 640`, then
   fire one more increment to trigger the halving FSM. Assert the
   DUT's `size_count` drops to exactly 320 and key 0's estimate
   drops from 15 to 7.
4. **`test_randomized_parity_200_steps`** — 200-step pseudo-random
   increment stream with seed `0xC0DECAFE`, spot-check estimates
   every 25 steps against a parallel Python reference.

## Prerequisites

The harness requires **both** of the following:

- **cocotb** ≥ 1.8 (`pip install cocotb`)
- One SystemVerilog simulator backend on `PATH`:
  - **Verilator** ≥ 5.x (`apt install verilator`) — recommended
  - **Icarus Verilog** ≥ 12.x (`apt install iverilog`) — alternative

When either dependency is missing, `test_freq_sketch_cosim.py`
**skips with a clear install hint** rather than failing or faking a
pass. This is intentional: the pytest suite must remain green on
machines without RTL tooling.

## How to run

### With tooling installed (Verilator)

```bash
# From the repo root
pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -v

# Or directly via Make
make -C simulator/pcam/rtl/tests cosim

# Switch backend
make -C simulator/pcam/rtl/tests cosim SIM=icarus
```

### Without tooling

```bash
pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -v
# → SKIPPED: cocotb is not installed / no SystemVerilog simulator on PATH
```

### Clean

```bash
make -C simulator/pcam/rtl/tests clean
```

## Elaboration knobs

The Makefile overrides three parameters at elaboration time so the
halving trigger is reachable in a short test:

```
-GCAPACITY=64
-GWIDTH=64
-GINDEX_WIDTH=6
-GRESET_THRESHOLD=640
```

The Python reference is constructed with `FrequencySketch(capacity=64)`
on the cocotb side, which produces identical width / depth / seeds /
reset_threshold. The full-capacity (production) parameters in
`pcam_pkg.sv` are unchanged — the override is cosim-only.

## What pass means

```
$ make -C simulator/pcam/rtl/tests cosim
...
** TEST                                           STATUS  SIM TIME (ns)  REAL TIME (s)  RATIO (ns/s) **
**************************************************************************************************
** cosim_freq_sketch.test_single_key_saturation    PASS           ...              ...           ... **
** cosim_freq_sketch.test_distinct_keys_light_load PASS           ...              ...           ... **
** cosim_freq_sketch.test_halving_fires_at_reset_threshold PASS  ...              ...           ... **
** cosim_freq_sketch.test_randomized_parity_200_steps PASS       ...              ...           ... **
**************************************************************************************************
** TESTS=4 PASS=4 FAIL=0 SKIP=0
```

A green run means every increment returned the reference's
`inc_min_count`, every estimate matched the reference byte-for-byte,
the halving FSM fired on the threshold-crossing cycle, and the
post-halve state matched the reference's halved table.

## If parity fails

Do **not** weaken the test or the reference. Parity failures on this
harness mean one of three things:

1. **RTL bug.** The SystemVerilog does not implement the algorithm
   the reference describes. Debug the SV against
   `simulator/pcam/kv_policy.py::FrequencySketch` as the oracle. Do
   not modify the reference.
2. **Reference drift.** Someone updated the vendored reference
   without re-running the update ritual. Re-run
   `pytest simulator/pcam/tests/test_sketch_conformance.py` and fix
   the runtime port first; the RTL follows.
3. **Simulator bug.** Rare but possible with certain Verilator
   versions. Try the other backend (`SIM=icarus`) to isolate.

## What remains out of scope

Phase 2.5 deliberately does NOT cover:

- `KVCachePolicy` RTL. Victim selection and scoring stay on the
  software side of the parity contract.
- Full-capacity halving. We use `CAPACITY=64` to keep test runtime
  short. A nightly run at production capacity is a Phase 3+ concern.
- RTL synthesis, place-and-route, or timing closure.
- Multi-port / multi-sequence stress testing.
- Any cocotb coverage collection or reporting infrastructure.

If any of these become business-critical, they belong in a later
phase with their own scope doc.

## Environment note for the current branch

At the time this phase was landed, the dev environment where the
harness was authored had **neither cocotb nor a SystemVerilog backend
installed**. The harness is therefore committed as ready-to-run but
untested end-to-end in that environment. The pytest wrapper skips
cleanly as designed; all other PCAM tests remain green.

The first engineer with a dev box that has
`pip install cocotb && apt install verilator` should run

```bash
pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -v
```

and report the result. If anything diverges, file it against this
runbook and debug against the Python reference per the "If parity
fails" section above.
