# First Live Run — Phase 2.5 RTL Cosimulation Closure

**Status of Phase 2.5 as of the branch tip:** harness complete, execution verification pending.

This document is the operational runbook for the first engineer with
RTL tooling access to close that gap. Follow the steps in order; if
anything diverges, record the finding at the bottom of this file and
debug against the Python reference (never against the test).

## Why this doc exists

Phase 2.5 landed the cocotb harness, the Makefile, the pytest wrapper,
and the runbook. What is missing is **one real simulator-backed green
execution** of

```bash
pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -q
```

The pytest wrapper skips cleanly in environments without cocotb and a
SystemVerilog backend, so the skip is not a failure — but the parity
claim is not *closed* until a live run has produced four green cocotb
test results. This document walks that single closure step.

## What you need

- A Linux (or macOS) dev box
- Python 3.9+
- **cocotb** (any 1.8+ release; 1.9.2 confirmed compatible)
- **Verilator** 5.x (recommended) **or** Icarus Verilog 12.x+

Expected install time: under 10 minutes on a fresh machine.

## Install — Ubuntu / Debian

```bash
# System dependencies
sudo apt update
sudo apt install -y verilator make python3-pip

# cocotb (pip, user-local or venv)
python3 -m pip install --user cocotb

# Sanity check
verilator --version          # expect: Verilator 5.x
cocotb-config --version      # expect: 1.8+ or 1.9+
```

If `verilator` on your distro is older than 5.x, build from source:
<https://verilator.org/guide/latest/install.html> (about 15 minutes).
Verilator 4.x has partial SV support and will likely fail on
`freq_sketch.sv`; do not waste time trying to make it work.

## Install — macOS

```bash
brew install verilator
python3 -m pip install cocotb
```

## Install — Icarus Verilog fallback

If Verilator is not available, Icarus Verilog 12.x+ works as a
fallback. It is slower and has quirkier SV support:

```bash
sudo apt install iverilog    # must be 12.0 or newer
iverilog -V                  # confirm 12.0+
```

Then run the harness with `SIM=icarus` (see below).

## Run

```bash
# From the repo root
cd /path/to/symbolu

# Verify cocotb + a backend are detected
pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -v

# Or invoke the Makefile directly for more verbose output
make -C simulator/pcam/rtl/tests cosim

# Switch backend explicitly
make -C simulator/pcam/rtl/tests cosim SIM=icarus
```

## What a green run looks like

Direct Make invocation:

```
** TEST                                                           STATUS **
***************************************************************************
** cosim_freq_sketch.test_single_key_saturation                    PASS  **
** cosim_freq_sketch.test_distinct_keys_light_load                 PASS  **
** cosim_freq_sketch.test_halving_fires_at_reset_threshold         PASS  **
** cosim_freq_sketch.test_randomized_parity_200_steps              PASS  **
***************************************************************************
** TESTS=4 PASS=4 FAIL=0 SKIP=0
```

Pytest wrapper invocation:

```
simulator/pcam/rtl/tests/test_freq_sketch_cosim.py::test_freq_sketch_rtl_parity PASSED
======================== 1 passed in Xs ========================
```

If you see this, **Phase 2.5 is closed.** Commit a one-line entry in
the "Run log" section below and push.

## Common failure modes and fixes

Every item below is a bug in the harness, not the reference. The
fix lives in `rtl/tests/` or `rtl/core/freq_sketch.sv`; never modify
`simulator/pcam/kv_policy.py` or the vendored reference.

### 1. `cocotb-config: command not found` when running Make

**Cause:** cocotb installed in a different Python environment than
the shell is using.

**Fix:** activate the venv or confirm `which python3` and
`python3 -m pip show cocotb` agree. You can force the Makefile to
use a specific cocotb by prepending its path:

```bash
PATH=$(python3 -m site --user-base)/bin:$PATH make -C simulator/pcam/rtl/tests cosim
```

### 2. `%Error: ... cannot find pcam_pkg::...`

**Cause:** file compile order. `pcam_pkg.sv` must be elaborated
before `freq_sketch.sv`.

**Fix:** the Makefile already lists them in the right order in
`VERILOG_SOURCES`. If you see this error, check that no extra
`.sv` files got pulled in via a shell glob or editor autosave.

### 3. `%Error-UNSUPPORTED: ... unique case`

**Cause:** Verilator 4.x or Icarus before 12.0 does not support
SystemVerilog `unique case`.

**Fix:** upgrade the simulator to a supported version. Do NOT
rewrite the RTL to work around this — it's a tooling issue, and the
`unique case` is load-bearing for the state machine semantics.

### 4. `ImportError: No module named 'simulator.pcam.kv_policy'` inside cocotb

**Cause:** `PYTHONPATH` not propagating from Make to the cocotb test
process.

**Fix:** the Makefile exports `PYTHONPATH := $(REPO_ROOT):$(PYTHONPATH)`.
If you moved the tests directory or ran Make from outside the repo
root, `$(REPO_ROOT)` may be wrong. Confirm:

```bash
make -C simulator/pcam/rtl/tests cosim 2>&1 | grep PYTHONPATH
```

You should see the absolute repo-root path. If not, run from the
repo root or set `PYTHONPATH` explicitly:

```bash
PYTHONPATH=$(pwd) make -C simulator/pcam/rtl/tests cosim
```

### 5. `AssertionError: inc_done never asserted for key=42` (timeout)

**Cause:** the `_wait_not_busy` or inc_done timeout (2048 cycles) is
too small for the parameter override you're using. The halving FSM
walks `WIDTH` indices, so at `WIDTH=64` the busy window is ~64–66
cycles; 2048 is comfortable. At larger widths it may not be.

**Fix:** do NOT increase the CAPACITY override in the Makefile past
the current `CAPACITY=64 WIDTH=64`. Those values were chosen
specifically to keep the halving test fast. If you want a
stress-test at production capacity, add a *new* test scenario in
`cosim_freq_sketch.py` with an explicit larger timeout; do not
change the Makefile defaults.

### 6. iverilog-specific parameter override syntax

**Cause:** the Makefile uses Verilator-style `-GCAPACITY=64` in
`COMPILE_ARGS`. Icarus Verilog uses `-PCAPACITY=64` instead.

**Fix:** if `make cosim SIM=icarus` errors on the `-G` flags, patch
the Makefile to switch syntax based on `$(SIM)`:

```make
ifeq ($(SIM),icarus)
    COMPILE_ARGS += -Pfreq_sketch.CAPACITY=64 -Pfreq_sketch.WIDTH=64
else
    COMPILE_ARGS += -GCAPACITY=64 -GWIDTH=64 -GINDEX_WIDTH=6 -GRESET_THRESHOLD=640
endif
```

Record this change in the Run log below if you make it.

### 7. `inc_min_count diverged on key=N: rtl=X, ref=Y`

**Cause:** real RTL bug. One of the SV datapath operations does not
match the Python reference.

**Fix:** do NOT adjust the test or the reference. Debug against the
Python reference as the oracle:

1. Print the DUT's internal table state at the failing step (add a
   `$display` in `freq_sketch.sv` under `ifdef SIMULATION`).
2. Compare against the reference's table at the same step (add a
   `print(ref.table)` in the cocotb helper temporarily).
3. The first row where they diverge is the bug. Common causes:
   - Hash function off by one bit (check `_hash` in the reference
     vs `sketch_hash` in `pcam_pkg.sv`).
   - Saturation comparison off by one (`==` vs `>=` vs `>`).
   - Halve fires at the wrong edge (`size >= reset_threshold` vs `>`).
   - Deferred-increment state machine skips a row.
4. Fix `freq_sketch.sv`. Rerun. Iterate until green.

Per the `PHASE2_5_RTL_COSIMULATION.md` runbook: *"If parity fails,
debug the SV against the reference. Do not modify the reference."*

### 8. `%Warning-WIDTH: Operator ...`

**Cause:** Verilator is strict about implicit width mismatches.

**Fix:** fix the SV expression to use an explicit width cast. These
are almost always harmless at the behavioral level but must be
cleaned for lint-clean synthesis. If the warning escalates to an
error because of `-Wno-fatal` tuning, add the specific warning to
`EXTRA_ARGS` in the Makefile with a `-Wno-XXXX` override and note it
in the Run log so a follow-up can fix the root cause.

### 9. The pytest wrapper still skips after installing cocotb + verilator

**Cause:** `_check_tooling` in `test_freq_sketch_cosim.py` uses
`shutil.which("verilator")`. If your shell has `verilator` but pytest
runs in a different environment (e.g. a subprocess spawned by an IDE
without the shell PATH), the check fails.

**Fix:** invoke pytest from a shell where `which verilator` succeeds:

```bash
which verilator && pytest simulator/pcam/rtl/tests/test_freq_sketch_cosim.py -v
```

## After a green run — what to do

1. **Update the roadmap status** in `PHASE2_5_RTL_COSIMULATION.md`
   to replace "execution verification pending" with "closed;
   first green run on `<YYYY-MM-DD>`."
2. **Add a Run-log entry** at the bottom of THIS file with:
   - Date
   - Simulator and version (`verilator --version`)
   - cocotb version (`python3 -m pip show cocotb`)
   - OS / distro
   - Any Makefile tweaks you made (especially Icarus parameter syntax)
   - Total runtime
3. **Commit and push** on the current branch. One commit, simple
   message:
   ```
   Phase 2.5: first live cocotb cosimulation run — 4/4 PASS
   ```
4. **Do NOT** commit any simulator build artifacts. `make clean`
   before committing, or add the build dirs to a local `.gitignore`
   if needed (do not touch the repo-root `.gitignore` without
   discussion).

## After a failing run — what to do

1. **Do not commit anything yet.**
2. Capture the full output of `make -C simulator/pcam/rtl/tests cosim`
   to a file.
3. Re-read the "Common failure modes" section above; most failures
   map to one of those items.
4. If the failure is a real RTL bug (section 7), debug against the
   reference per the instructions there. Fix `freq_sketch.sv`, not
   the tests or the reference.
5. If the failure is tooling-related (sections 1–4, 6, 8, 9), fix
   the Makefile or the wrapper and record the fix in the Run log.
6. Re-run until green, then follow the "After a green run" steps.

## What is explicitly NOT in scope for this closure

Do not, during the first live run, also try to:

- Add new cocotb scenarios
- Increase `CAPACITY` past 64
- Add coverage collection
- Add waveform dumping beyond the Makefile's existing `--trace`
- Port `KVCachePolicy` to RTL
- Add more runtime adapters
- Touch Phase 1 / Phase 2 API surfaces
- Modify the vendored reference or the parity harness

Any of those are legitimate follow-up work but do **not** belong in
the commit that closes Phase 2.5. Keep the closure commit as small
and focused as possible: ideally just the roadmap status update and
the Run-log entry.

## Run log

Append to this section after each live execution attempt.

```
# Template (delete this block and replace with real entries)
# - date:        YYYY-MM-DD
# - engineer:    <name / handle>
# - sim:         verilator 5.X.Y  (or iverilog 12.X)
# - cocotb:      1.9.Z
# - os:          Ubuntu 22.04 / macOS 14 / ...
# - result:      4/4 PASS  (or: 3/4 PASS, test_halving_fires_at_reset_threshold FAIL)
# - runtime:     ~Xs
# - notes:       any Makefile tweaks, tooling quirks, or follow-up items
```

*(No live runs yet. Phase 2.5 closure pending.)*
