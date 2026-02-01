#-----------------------------------------------------------------------------
# PCAM Vivado Build Script
#-----------------------------------------------------------------------------
# Target: Xilinx Alveo U280
# Tool: Vivado 2023.2+
#
# Usage:
#   vivado -mode batch -source build_vivado.tcl
#   vivado -mode batch -source build_vivado.tcl -tclargs synth_only
#   vivado -mode batch -source build_vivado.tcl -tclargs impl
#-----------------------------------------------------------------------------

#=============================================================================
# Configuration
#=============================================================================

set project_name "pcam_fpga"
set part_name "xcu280-fsvh2892-2L-e"  # Alveo U280
set top_module "pcam_top"

# Directories
set script_dir [file dirname [info script]]
set rtl_dir [file normalize "$script_dir/.."]
set output_dir "$rtl_dir/build"
set reports_dir "$output_dir/reports"

# Build mode from command line
set build_mode "full"
if {$argc > 0} {
    set build_mode [lindex $argv 0]
}

#=============================================================================
# Create Project
#=============================================================================

puts "============================================"
puts "PCAM FPGA Build"
puts "============================================"
puts "Part: $part_name"
puts "Mode: $build_mode"
puts "============================================"

# Clean previous build
file delete -force $output_dir
file mkdir $output_dir
file mkdir $reports_dir

# Create in-memory project
create_project -in_memory -part $part_name

#=============================================================================
# Add Source Files
#=============================================================================

# Package first (for type definitions)
read_verilog -sv "$rtl_dir/pcam_pkg.sv"

# Common modules
read_verilog -sv "$rtl_dir/common/cmp_swap.sv"
read_verilog -sv "$rtl_dir/common/score_update.sv"
read_verilog -sv "$rtl_dir/common/async_fifo.sv"

# Core modules
read_verilog -sv "$rtl_dir/core/bank_mem.sv"
read_verilog -sv "$rtl_dir/core/topk_network.sv"
read_verilog -sv "$rtl_dir/core/update_coalescer.sv"
read_verilog -sv "$rtl_dir/core/decay_engine.sv"

# Host interface
read_verilog -sv "$rtl_dir/host_if/pcie_endpoint.sv"
read_verilog -sv "$rtl_dir/host_if/dma_engine.sv"

# Top level
read_verilog -sv "$rtl_dir/pcam_top.sv"

# Constraints
read_xdc "$rtl_dir/constraints/timing.xdc"

#=============================================================================
# Synthesis
#=============================================================================

puts "Running synthesis..."

synth_design \
    -top $top_module \
    -part $part_name \
    -flatten_hierarchy rebuilt \
    -directive PerformanceOptimized \
    -fsm_extraction one_hot \
    -resource_sharing auto \
    -retiming

# Generate synthesis reports
report_timing_summary -file "$reports_dir/synth_timing.rpt"
report_utilization -file "$reports_dir/synth_utilization.rpt"
report_design_analysis -file "$reports_dir/synth_analysis.rpt"
report_methodology -file "$reports_dir/synth_methodology.rpt"

# Write checkpoint
write_checkpoint -force "$output_dir/post_synth.dcp"

if {$build_mode == "synth_only"} {
    puts "Synthesis complete. Exiting."
    exit 0
}

#=============================================================================
# Implementation
#=============================================================================

puts "Running implementation..."

# Optimize design
opt_design -directive Explore

# Place design
place_design -directive ExtraNetDelay_high

# Physical optimization
phys_opt_design -directive AggressiveExplore

# Route design
route_design -directive AggressiveExplore

# Post-route physical optimization
phys_opt_design -directive AggressiveExplore

#=============================================================================
# Generate Reports
#=============================================================================

puts "Generating reports..."

# Timing
report_timing_summary -file "$reports_dir/impl_timing.rpt" -max_paths 100
report_timing -file "$reports_dir/impl_timing_detail.rpt" \
    -max_paths 50 \
    -sort_by slack \
    -nworst 5

# Utilization
report_utilization -file "$reports_dir/impl_utilization.rpt"
report_utilization -hierarchical -file "$reports_dir/impl_utilization_hier.rpt"

# Power
report_power -file "$reports_dir/impl_power.rpt"

# DRC
report_drc -file "$reports_dir/impl_drc.rpt"

# Clock networks
report_clock_networks -file "$reports_dir/impl_clocks.rpt"
report_clock_utilization -file "$reports_dir/impl_clock_util.rpt"

# Write checkpoint
write_checkpoint -force "$output_dir/post_impl.dcp"

#=============================================================================
# Generate Bitstream
#=============================================================================

if {$build_mode == "impl"} {
    puts "Implementation complete. Exiting before bitstream."
    exit 0
}

puts "Generating bitstream..."

write_bitstream -force "$output_dir/${project_name}.bit"

# Generate memory configuration file for flash programming
write_cfgmem -format mcs -size 128 -interface SPIx4 \
    -loadbit "up 0x0 $output_dir/${project_name}.bit" \
    -force -file "$output_dir/${project_name}.mcs"

#=============================================================================
# Final Summary
#=============================================================================

puts ""
puts "============================================"
puts "Build Complete!"
puts "============================================"
puts "Bitstream: $output_dir/${project_name}.bit"
puts "MCS File:  $output_dir/${project_name}.mcs"
puts ""

# Check timing
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -hold]]

puts "Timing Summary:"
puts "  WNS (setup): $wns ns"
puts "  WHS (hold):  $whs ns"

if {$wns < 0} {
    puts "WARNING: Design has setup timing violations!"
    exit 1
}

if {$whs < 0} {
    puts "WARNING: Design has hold timing violations!"
    exit 1
}

puts ""
puts "Timing met. Build successful!"
exit 0
