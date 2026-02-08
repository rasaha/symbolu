#-----------------------------------------------------------------------------
# PCAM FPGA RTL Makefile
#-----------------------------------------------------------------------------
# Targets:
#   make sim       - Run simulation (Verilator or iverilog)
#   make synth     - Run synthesis only
#   make impl      - Run implementation (place & route)
#   make bit       - Generate bitstream
#   make clean     - Clean build artifacts
#   make lint      - Run linting (verilator --lint-only)
#-----------------------------------------------------------------------------

#=============================================================================
# Configuration
#=============================================================================

TOP_MODULE := pcam_top
PART := xcu280-fsvh2892-2L-e

# Directories
RTL_DIR := $(shell pwd)
BUILD_DIR := $(RTL_DIR)/build
SIM_DIR := $(BUILD_DIR)/sim
REPORTS_DIR := $(BUILD_DIR)/reports

# Tool selection
SIMULATOR ?= verilator
VIVADO ?= vivado

#=============================================================================
# Source Files
#=============================================================================

PKG_FILES := \
    pcam_pkg.sv

COMMON_FILES := \
    common/cmp_swap.sv \
    common/score_update.sv \
    common/async_fifo.sv

CORE_FILES := \
    core/bank_mem.sv \
    core/topk_network.sv \
    core/update_coalescer.sv \
    core/decay_engine.sv

HOST_FILES := \
    host_if/pcie_endpoint.sv \
    host_if/dma_engine.sv

TOP_FILES := \
    pcam_top.sv

TB_FILES := \
    tb/tb_pcam_top.sv

ALL_RTL := $(PKG_FILES) $(COMMON_FILES) $(CORE_FILES) $(HOST_FILES) $(TOP_FILES)
ALL_TB := $(TB_FILES)

#=============================================================================
# Default Target
#=============================================================================

.PHONY: all
all: lint sim

#=============================================================================
# Lint
#=============================================================================

.PHONY: lint
lint:
	@echo "Running Verilator lint..."
	@mkdir -p $(BUILD_DIR)
	verilator --lint-only -Wall \
		--top-module $(TOP_MODULE) \
		-I$(RTL_DIR) \
		$(addprefix $(RTL_DIR)/,$(ALL_RTL)) \
		2>&1 | tee $(BUILD_DIR)/lint.log
	@echo "Lint complete. See $(BUILD_DIR)/lint.log"

#=============================================================================
# Simulation
#=============================================================================

.PHONY: sim
sim: sim_$(SIMULATOR)

.PHONY: sim_verilator
sim_verilator:
	@echo "Building simulation with Verilator..."
	@mkdir -p $(SIM_DIR)
	verilator --binary --timing \
		-j 0 \
		--top-module tb_pcam_top \
		--Mdir $(SIM_DIR)/verilator \
		-DSIMULATION \
		-I$(RTL_DIR) \
		$(addprefix $(RTL_DIR)/,$(ALL_RTL)) \
		$(addprefix $(RTL_DIR)/,$(ALL_TB)) \
		-o pcam_sim
	@echo "Running simulation..."
	$(SIM_DIR)/verilator/pcam_sim
	@echo "Simulation complete."

.PHONY: sim_iverilog
sim_iverilog:
	@echo "Building simulation with Icarus Verilog..."
	@mkdir -p $(SIM_DIR)
	iverilog -g2012 -Wall \
		-DSIMULATION \
		-I$(RTL_DIR) \
		-s tb_pcam_top \
		-o $(SIM_DIR)/pcam_sim.vvp \
		$(addprefix $(RTL_DIR)/,$(ALL_RTL)) \
		$(addprefix $(RTL_DIR)/,$(ALL_TB))
	@echo "Running simulation..."
	vvp $(SIM_DIR)/pcam_sim.vvp
	@echo "Simulation complete."

#=============================================================================
# Synthesis (Vivado)
#=============================================================================

.PHONY: synth
synth:
	@echo "Running synthesis..."
	@mkdir -p $(BUILD_DIR)
	$(VIVADO) -mode batch -source scripts/build_vivado.tcl -tclargs synth_only
	@echo "Synthesis complete. See $(REPORTS_DIR)/synth_*.rpt"

#=============================================================================
# Implementation (Vivado)
#=============================================================================

.PHONY: impl
impl:
	@echo "Running implementation..."
	@mkdir -p $(BUILD_DIR)
	$(VIVADO) -mode batch -source scripts/build_vivado.tcl -tclargs impl
	@echo "Implementation complete. See $(REPORTS_DIR)/impl_*.rpt"

#=============================================================================
# Bitstream Generation (Vivado)
#=============================================================================

.PHONY: bit
bit:
	@echo "Generating bitstream..."
	@mkdir -p $(BUILD_DIR)
	$(VIVADO) -mode batch -source scripts/build_vivado.tcl
	@echo "Bitstream generated: $(BUILD_DIR)/pcam_fpga.bit"

#=============================================================================
# Clean
#=============================================================================

.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR)
	rm -rf .Xil
	rm -f *.jou *.log *.pb
	rm -f *.vcd
	@echo "Clean complete."

#=============================================================================
# Formal Verification (optional)
#=============================================================================

.PHONY: formal
formal:
	@echo "Running formal verification with SymbiYosys..."
	@mkdir -p $(BUILD_DIR)/formal
	sby -f scripts/pcam_formal.sby
	@echo "Formal verification complete."

#=============================================================================
# Coverage
#=============================================================================

.PHONY: coverage
coverage:
	@echo "Running coverage simulation..."
	verilator --binary --timing --coverage \
		-j 0 \
		--top-module tb_pcam_top \
		--Mdir $(SIM_DIR)/verilator_cov \
		-DSIMULATION \
		-I$(RTL_DIR) \
		$(addprefix $(RTL_DIR)/,$(ALL_RTL)) \
		$(addprefix $(RTL_DIR)/,$(ALL_TB)) \
		-o pcam_sim_cov
	$(SIM_DIR)/verilator_cov/pcam_sim_cov
	verilator_coverage --annotate $(BUILD_DIR)/coverage $(SIM_DIR)/verilator_cov/coverage.dat
	@echo "Coverage report: $(BUILD_DIR)/coverage"

#=============================================================================
# Help
#=============================================================================

.PHONY: help
help:
	@echo "PCAM FPGA RTL Build System"
	@echo ""
	@echo "Targets:"
	@echo "  make all       - Run lint and simulation (default)"
	@echo "  make lint      - Run Verilator linting"
	@echo "  make sim       - Run simulation (SIMULATOR=verilator|iverilog)"
	@echo "  make synth     - Run Vivado synthesis"
	@echo "  make impl      - Run Vivado implementation"
	@echo "  make bit       - Generate bitstream"
	@echo "  make coverage  - Run simulation with coverage"
	@echo "  make clean     - Clean build artifacts"
	@echo ""
	@echo "Variables:"
	@echo "  SIMULATOR     - Simulator to use (default: verilator)"
	@echo "  VIVADO        - Vivado executable (default: vivado)"
	@echo "  PART          - Target FPGA part (default: $(PART))"
