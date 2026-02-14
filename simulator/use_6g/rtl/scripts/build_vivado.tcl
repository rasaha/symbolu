# =============================================================================
# USE-6G Vivado Synthesis Script
# =============================================================================
# Usage: vivado -mode batch -source build_vivado.tcl -tclargs <top> <part> <sources>
# =============================================================================

# Parse arguments
set top_module [lindex $argv 0]
set part       [lindex $argv 1]
set src_files  [lindex $argv 2]

puts "=== USE-6G Vivado Synthesis ==="
puts "  Top module: $top_module"
puts "  Part:       $part"
puts "  Sources:    $src_files"

# Create project
create_project -force use_6g_synth ./use_6g_synth -part $part

# Add source files
foreach f $src_files {
    add_files $f
}

# Add constraints
add_files -fileset constrs_1 ../constraints/timing.xdc

# Set top module
set_property top $top_module [current_fileset]

# Synthesis settings
set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-mode out_of_context} -objects [get_runs synth_1]
set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY rebuilt [get_runs synth_1]
set_property STEPS.SYNTH_DESIGN.ARGS.RETIMING true [get_runs synth_1]

# Run synthesis
launch_runs synth_1 -jobs 4
wait_on_run synth_1

# Report utilization
open_run synth_1
report_utilization -file use_6g_utilization.rpt
report_timing_summary -file use_6g_timing.rpt
report_power -file use_6g_power.rpt

puts "=== Synthesis Complete ==="
puts "  See use_6g_utilization.rpt for resource usage"
puts "  See use_6g_timing.rpt for timing analysis"
puts "  See use_6g_power.rpt for power estimates"
