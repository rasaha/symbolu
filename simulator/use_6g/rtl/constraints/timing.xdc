## =============================================================================
## USE-6G Timing Constraints (Xilinx XDC)
## =============================================================================
## For FPGA prototyping on Xilinx Virtex UltraScale+
## Note: FPGA clock will be slower than 1 GHz target
## =============================================================================

## --- Clock definitions ---
## Core clock (FPGA: 250 MHz for prototyping)
create_clock -name clk_core -period 4.0 [get_ports clk_core]

## CSAC reference clock: 10 MHz
create_clock -name clk_csac -period 100.0 [get_ports clk_csac]

## --- Clock domain crossing ---
set_clock_groups -asynchronous \
  -group [get_clocks clk_core] \
  -group [get_clocks clk_csac]

## --- I/O constraints ---
set_input_delay  -clock clk_core -max 1.5 [get_ports {reg_req*}]
set_input_delay  -clock clk_core -min 0.3 [get_ports {reg_req*}]
set_output_delay -clock clk_core -max 1.5 [get_ports {reg_rsp*}]

set_input_delay  -clock clk_core -max 1.0 [get_ports {rf_phase_in*}]
set_output_delay -clock clk_core -max 1.5 [get_ports {irq_out}]
set_output_delay -clock clk_core -max 1.5 [get_ports {sync_state*}]
set_output_delay -clock clk_core -max 1.5 [get_ports {phase_locked}]

## --- False paths ---
set_false_path -from [get_ports rst_n]

## --- Physical constraints (FPGA pin assignments - placeholder) ---
## set_property PACKAGE_PIN AY38 [get_ports clk_core]
## set_property IOSTANDARD LVDS [get_ports clk_core]
