#Copyright 2026 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmark

# Makefile

# HDL source files
VERILOG_SOURCES      += $(CURDIR)/rtl/example_hdl.sv
VERILOG_INCLUDE_DIRS +=
COMPILE_ARGS         +=

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL             := example_hdl

# MODULE is the basename of the Python test file(s)
MODULE               ?= benchmark

# cocotb >= 2.0 no longer exports PYTHONPATH from its own makefiles
PYTHONPATH           := $(CURDIR)/cocotb$(if $(PYTHONPATH),:$(PYTHONPATH))
export PYTHONPATH

# Questa / ModelSim workaround
VSIM_ARGS            += -lib work

# Benchmarks measure start-up cost only - never enable waveform tracing here.

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf cocotb/__pycache__/
	rm -rf *.txt *.xml *.json *.csv *.yaml *.vcd *.png *.vhex *.vbin *.vmem *.ihex *.ti-txt *.srec sim.log html transcript modelsim.ini ucli.key
