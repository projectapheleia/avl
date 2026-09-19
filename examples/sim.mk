#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Example

# Makefile

# HDL source files
# AVL_RTL lets an example build a generated copy of its RTL (see
# mutation_testing) without otherwise departing from the standard flow.
AVL_RTL              ?= $(CURDIR)/rtl/example_hdl.sv
VERILOG_SOURCES      += $(AVL_RTL)
VERILOG_INCLUDE_DIRS +=
COMPILE_ARGS         +=

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL             := example_hdl
PYTHONPATH           := $(CURDIR)/cocotb$(if $(PYTHONPATH),:$(PYTHONPATH))
# cocotb >= 2.0 no longer exports PYTHONPATH from its own makefiles
export PYTHONPATH

# MODULE is the basename of the Python test file(s)
MODULE               ?= example

# One seed for every example, so that a run is the same run every time. Without
# this cocotb draws a fresh seed from the clock per simulation, and an example
# whose stimulus only occasionally reaches a corner passes or fails depending on
# which random numbers that run happened to draw - which makes a failure hard to
# reproduce and a pass worth little. Override it to sweep:
#
#     make sim COCOTB_RANDOM_SEED=42
#
COCOTB_RANDOM_SEED   ?= 1
export COCOTB_RANDOM_SEED

# Questa / ModelSim workaround
VSIM_ARGS            += -lib work

# Enable VCD trace from Verilator
ifeq ($(SIM), verilator)
EXTRA_ARGS           += --trace --trace-structs
endif

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf cocotb/__pycache__/
	rm -rf *.txt *.xml *.json *.csv *.yaml *.vcd *.png *.vhex *.vbin *.vmem *.ihex *.ti-txt *.srec sim.log html transcript modelsim.ini ucli.key
