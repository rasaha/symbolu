#-----------------------------------------------------------------------------
# PCAM Phase 2.5 — cocotb cosimulation harness for freq_sketch.sv
#-----------------------------------------------------------------------------
# Entry points:
#   make cosim          Run the full freq_sketch parity suite
#   make cosim SIM=icarus
#                       Use Icarus Verilog instead of Verilator
#   make clean          Remove build artifacts
#
# External dependencies:
#   - cocotb         (pip install cocotb)
#   - verilator      (>=5.x recommended; apt install verilator)
#     OR
#   - iverilog       (>=12.x; apt install iverilog)
#
# If neither cocotb nor a simulator backend is available, the pytest
# wrapper at test_freq_sketch_cosim.py will skip with a clear message.
#-----------------------------------------------------------------------------

# ---- Simulator selection ----------------------------------------------------
SIM ?= verilator
TOPLEVEL_LANG ?= verilog

# ---- Paths ------------------------------------------------------------------
THIS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RTL_DIR  := $(abspath $(THIS_DIR)/..)
REPO_ROOT := $(abspath $(THIS_DIR)/../../../..)

# ---- RTL sources ------------------------------------------------------------
# Order matters: pcam_pkg first so its typedefs are visible to freq_sketch.
VERILOG_SOURCES := \
    $(RTL_DIR)/pcam_pkg.sv \
    $(RTL_DIR)/core/freq_sketch.sv

# ---- DUT configuration ------------------------------------------------------
TOPLEVEL   := freq_sketch
MODULE     := cosim_freq_sketch

# Override CAPACITY to 64 so the halving trigger (reset_threshold = 640)
# is reachable in a short test. The Python reference uses the same value.
COMPILE_ARGS += -GCAPACITY=64 -GWIDTH=64 -GINDEX_WIDTH=6 -GRESET_THRESHOLD=640

# ---- Verilator-specific flags -----------------------------------------------
ifeq ($(SIM),verilator)
    EXTRA_ARGS += --trace --trace-structs
    EXTRA_ARGS += -Wno-fatal
    EXTRA_ARGS += -Wno-UNUSED
    EXTRA_ARGS += -Wno-UNOPTFLAT
endif

# ---- PYTHONPATH so cosim_freq_sketch.py can import simulator.pcam ----------
export PYTHONPATH := $(REPO_ROOT):$(PYTHONPATH)

# ---- Entry points -----------------------------------------------------------
.PHONY: cosim clean help

cosim: sim

help:
	@echo "PCAM Phase 2.5 cocotb cosimulation harness"
	@echo ""
	@echo "Targets:"
	@echo "  make cosim            Run the freq_sketch parity suite"
	@echo "  make cosim SIM=icarus Use Icarus Verilog"
	@echo "  make clean            Remove build artifacts"
	@echo ""
	@echo "Requires: cocotb + verilator (or iverilog) on PATH."

# ---- cocotb's boilerplate Makefile ------------------------------------------
# This include brings in the standard cocotb compile/run targets. It
# must come AFTER all VERILOG_SOURCES / MODULE / TOPLEVEL definitions.
include $(shell cocotb-config --makefiles)/Makefile.sim 2>/dev/null || \
    (echo "ERROR: cocotb is not installed. pip install cocotb." >&2; exit 1)
