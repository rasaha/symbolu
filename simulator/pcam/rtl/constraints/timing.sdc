#-----------------------------------------------------------------------------
# PCAM FPGA Timing Constraints (Intel/Altera SDC Format)
#-----------------------------------------------------------------------------
# Target: Intel Agilex / Stratix 10
# Tool: Quartus Prime Pro 23.1+
#-----------------------------------------------------------------------------

#=============================================================================
# Clock Definitions
#=============================================================================

# PCIe reference clock (100 MHz)
create_clock -name pcie_refclk -period 10.000 [get_ports pcie_refclk]

# PCIe generated clock (250 MHz from P-Tile)
create_clock -name pcie_clk -period 4.000 [get_pins pcie_hip|coreclkout_hip]

# User clock (250 MHz from fPLL)
create_clock -name user_clk -period 4.000 [get_pins u_pll|outclk_0]

#=============================================================================
# Clock Domain Crossing
#=============================================================================

# Asynchronous clock groups
set_clock_groups -asynchronous \
    -group [get_clocks pcie_clk] \
    -group [get_clocks user_clk]

# Synchronizer constraints
set_false_path -from [get_registers *async_fifo*wr_ptr_gray*] \
               -to   [get_registers *async_fifo*wr_ptr_gray_meta*]

set_false_path -from [get_registers *async_fifo*rd_ptr_gray*] \
               -to   [get_registers *async_fifo*rd_ptr_gray_meta*]

# Max delay for synchronizer chain
set_max_delay 8.000 -from [get_registers *_meta*] -to [get_registers *_sync*]

#=============================================================================
# Input/Output Delays
#=============================================================================

# Debug outputs (relaxed)
set_output_delay -clock user_clk -max 2.000 [get_ports debug_status[*]]
set_output_delay -clock user_clk -min 0.000 [get_ports debug_status[*]]

#=============================================================================
# Critical Paths
#=============================================================================

# Top-K network stages
set_max_delay 3.500 \
    -from [get_registers *topk_network*stage_data*] \
    -to   [get_registers *topk_network*stage_data*]

# Bank memory paths
set_max_delay 3.500 \
    -from [get_registers *bank_array*] \
    -to   [get_registers *bank_mem*]

#=============================================================================
# Multi-Cycle Paths
#=============================================================================

# Decay engine (background operation)
set_multicycle_path 2 -setup -end \
    -from [get_registers *decay_engine*current_*] \
    -to   [get_registers *decay_engine*bank_*]

set_multicycle_path 1 -hold -end \
    -from [get_registers *decay_engine*current_*] \
    -to   [get_registers *decay_engine*bank_*]

#=============================================================================
# False Paths
#=============================================================================

# Asynchronous reset
set_false_path -from [get_ports rst_n]

# Static configuration
set_false_path -from [get_registers *csr_bank*config*]

#=============================================================================
# Physical Constraints
#=============================================================================

# Logic Lock regions (Intel equivalent of Pblocks)
# set_instance_assignment -name PLACE_REGION "X0 Y0 X100 Y200" -to "u_bank_array"
# set_instance_assignment -name PLACE_REGION "X100 Y0 X200 Y200" -to "u_topk_network"

#=============================================================================
# Optimization Directives
#=============================================================================

# Enable retiming for critical paths
set_global_assignment -name ALLOW_REGISTER_RETIMING ON

# Enable physical synthesis
set_global_assignment -name PHYSICAL_SYNTHESIS_COMBO_LOGIC ON
set_global_assignment -name PHYSICAL_SYNTHESIS_REGISTER_DUPLICATION ON
set_global_assignment -name PHYSICAL_SYNTHESIS_REGISTER_RETIMING ON

# Memory optimization
set_global_assignment -name AUTO_RAM_RECOGNITION ON
set_global_assignment -name AUTO_ROM_RECOGNITION ON
