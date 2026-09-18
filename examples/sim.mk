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
