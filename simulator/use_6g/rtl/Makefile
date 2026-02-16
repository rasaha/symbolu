# =============================================================================
# USE-6G Massive MIMO Synchronization Chip - RTL Build System
# =============================================================================
# Targets:
#   lint    - Run Verilator lint checks
#   sim     - Run behavioral simulation (Verilator or iverilog)
#   synth   - Run Vivado synthesis
#   wave    - Open waveform viewer
#   clean   - Remove build artifacts
# =============================================================================

# --- Configuration ---
TOP_MODULE   := use_6g_top
TB_MODULE    := tb_use_6g_top
PKG_FILE     := use_6g_pkg.sv
BUILD_DIR    := build
WAVE_FILE    := $(BUILD_DIR)/use_6g_top.vcd

# --- Simulator selection ---
SIM          ?= verilator
# SIM        ?= iverilog

# --- Source files (order matters for packages) ---
PKG_SRC := \
	use_6g_pkg.sv

COMMON_SRC := \
	common/sin_cos_lut.sv \
	common/cordic_atan2.sv \
	common/adder_tree.sv \
	common/fixed_point_mult.sv \
	common/phase_wrap.sv

CORE_SRC := \
	core/eprf.sv \
	core/mfu.sv \
	core/pue.sv \
	core/ce.sv \
	core/ca.sv \
	core/tc.sv \
	core/svg.sv \
	core/mbc.sv \
	core/phc.sv \
	core/bqm.sv

CTRL_SRC := \
	ctrl/sync_ctrl.sv \
	ctrl/reg_if.sv

TOP_SRC := \
	use_6g_top.sv

TB_SRC := \
	tb/tb_use_6g_top.sv

ALL_RTL_SRC := $(PKG_SRC) $(COMMON_SRC) $(CORE_SRC) $(CTRL_SRC) $(TOP_SRC)
ALL_SRC     := $(ALL_RTL_SRC) $(TB_SRC)

# --- Verilator flags ---
VERILATOR_FLAGS := \
	--sv \
	--timing \
	--binary \
	--trace \
	-Wall \
	-Wno-DECLFILENAME \
	-Wno-UNUSED \
	-Wno-UNDRIVEN \
	-Wno-WIDTH \
	--top-module $(TB_MODULE) \
	-o $(TB_MODULE) \
	--Mdir $(BUILD_DIR)/verilator

VERILATOR_LINT_FLAGS := \
	--sv \
	--lint-only \
	-Wall \
	-Wno-DECLFILENAME \
	-Wno-UNUSED \
	-Wno-UNDRIVEN \
	-Wno-WIDTH \
	--top-module $(TOP_MODULE)

# --- Icarus Verilog flags ---
IVERILOG_FLAGS := \
	-g2012 \
	-Wall \
	-o $(BUILD_DIR)/$(TB_MODULE) \
	-s $(TB_MODULE)

# --- Vivado synthesis ---
VIVADO_PART  := xcu280-fsvh2892-2L-e
VIVADO_FLAGS := -mode batch -source scripts/build_vivado.tcl

# =============================================================================
# Targets
# =============================================================================

.PHONY: all lint sim synth wave clean help

all: lint sim

# --- Directory creation ---
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# --- Lint ---
lint: $(BUILD_DIR)
	@echo "=== Running Verilator lint ==="
	verilator $(VERILATOR_LINT_FLAGS) $(ALL_RTL_SRC)
	@echo "=== Lint PASSED ==="

# --- Simulation ---
sim: $(BUILD_DIR)
ifeq ($(SIM),verilator)
	@echo "=== Building with Verilator ==="
	verilator $(VERILATOR_FLAGS) $(ALL_SRC)
	@echo "=== Running simulation ==="
	$(BUILD_DIR)/verilator/$(TB_MODULE) +DUMP_VCD
else
	@echo "=== Building with Icarus Verilog ==="
	iverilog $(IVERILOG_FLAGS) $(ALL_SRC)
	@echo "=== Running simulation ==="
	cd $(BUILD_DIR) && vvp $(TB_MODULE) +DUMP_VCD
endif

# --- Synthesis (Vivado) ---
synth: $(BUILD_DIR)
	@echo "=== Running Vivado synthesis ==="
	cd $(BUILD_DIR) && vivado $(VIVADO_FLAGS) \
		-tclargs $(TOP_MODULE) $(VIVADO_PART) "$(addprefix ../,$(ALL_RTL_SRC))"

# --- Waveform viewer ---
wave: $(WAVE_FILE)
	@echo "=== Opening waveform ==="
	gtkwave $(WAVE_FILE) &

# --- Source file listing ---
list:
	@echo "=== RTL Source Files ==="
	@for f in $(ALL_RTL_SRC); do echo "  $$f"; done
	@echo ""
	@echo "=== Testbench Files ==="
	@for f in $(TB_SRC); do echo "  $$f"; done
	@echo ""
	@echo "=== Total: $$(echo $(ALL_SRC) | wc -w) files ==="

# --- Line count ---
loc:
	@echo "=== Lines of Code ==="
	@wc -l $(ALL_SRC) | tail -1

# --- Clean ---
clean:
	rm -rf $(BUILD_DIR)
	rm -f *.vcd *.log *.jou

# --- Help ---
help:
	@echo "USE-6G RTL Build System"
	@echo ""
	@echo "Targets:"
	@echo "  lint     - Run Verilator lint checks"
	@echo "  sim      - Run behavioral simulation (SIM=verilator|iverilog)"
	@echo "  synth    - Run Vivado synthesis"
	@echo "  wave     - Open waveform viewer (requires gtkwave)"
	@echo "  list     - List all source files"
	@echo "  loc      - Count lines of code"
	@echo "  clean    - Remove build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  SIM      - Simulator: verilator (default) or iverilog"
