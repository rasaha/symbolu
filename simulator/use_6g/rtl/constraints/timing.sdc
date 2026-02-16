# =============================================================================
# USE-6G Timing Constraints (SDC)
# =============================================================================
# Reference: USE_6G_CHIP_SPEC.md Section 7.1 Clock Domains
# =============================================================================

# --- Clock definitions ---

# Core clock: 1 GHz (1 ns period)
create_clock -name clk_core -period 1.0 [get_ports clk_core]

# CSAC reference clock: 10 MHz (100 ns period)
create_clock -name clk_csac -period 100.0 [get_ports clk_csac]

# --- Clock domain crossing ---
set_clock_groups -asynchronous \
  -group [get_clocks clk_core] \
  -group [get_clocks clk_csac]

# --- Input/Output delays ---
# Register bus interface (assumes 0.5 ns setup/hold)
set_input_delay  -clock clk_core -max 0.5 [get_ports {reg_req*}]
set_input_delay  -clock clk_core -min 0.1 [get_ports {reg_req*}]
set_output_delay -clock clk_core -max 0.5 [get_ports {reg_rsp*}]

# RF phase inputs (tight timing for phase accuracy)
set_input_delay  -clock clk_core -max 0.3 [get_ports {rf_phase_in*}]
set_input_delay  -clock clk_core -min 0.05 [get_ports {rf_phase_in*}]

# Interrupt output
set_output_delay -clock clk_core -max 0.5 [get_ports irq_out]

# Status outputs
set_output_delay -clock clk_core -max 0.5 [get_ports {sync_state*}]
set_output_delay -clock clk_core -max 0.5 [get_ports phase_locked]

# --- Critical path constraints ---
# Sync pipeline must complete in 4 cycles (4 ns)
# MFU adder tree is the critical combinational path
set_max_delay 0.8 -from [get_pins u_mfu/g_sincos[*].u_sincos/*] \
                   -to   [get_pins u_mfu/u_sin_tree/*]

# CORDIC pipeline: 16 stages, each must fit in 1 ns
set_max_delay 0.9 -from [get_pins u_mfu/u_atan2/g_cordic_stage[*].*] \
                   -to   [get_pins u_mfu/u_atan2/g_cordic_stage[*].*]

# --- False paths ---
# Calibration data is static during operation
set_false_path -from [get_pins u_eprf/elem_state[*].phase_offset_cal*]
set_false_path -from [get_pins u_eprf/elem_state[*].amplitude_cal*]
set_false_path -from [get_pins u_eprf/elem_state[*].pos_x*]
set_false_path -from [get_pins u_eprf/elem_state[*].pos_y*]

# Reset is asynchronous
set_false_path -from [get_ports rst_n]

# --- Area constraints ---
# Target: ≤25 mm² at 4nm
# (Area constraints are process-specific, placeholder)

# --- Power constraints ---
# Target: ≤20W total, ≤5W sync-only
# (Power constraints handled by synthesis tool)
