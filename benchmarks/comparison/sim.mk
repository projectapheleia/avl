#Copyright 2026 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) comparison benchmark - flavour driver.
#
# Compiles and runs one flavour of the benchmark, through cocotb, from the RTL
# and the testbench in this directory. Not used directly: comparison_benchmark.py
# invokes it once per flavour in that flavour's own run directory, with that
# flavour's Python environment,
#
#   make -C <run directory> -f <this file> sim FLAVOUR=<flavour>
#
# so that every flavour is built and run exactly the same way and the comparison
# stays honest. Because the flow is cocotb's, any simulator cocotb supports can
# be used - make SIM=questa.

# Directory of the benchmark, resolved through the -f path rather than assumed
# to be the working directory, which is the flavour's run directory.
BENCH_DIR            := $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))

# sv, avl, released or pyuvm.
FLAVOUR              ?= avl

SEED                 ?= 1

# HDL source files. The classes are `include`d by the RTL rather than compiled on
# their own, so they are named as a dependency too - otherwise editing them would
# not rebuild the model.
VERILOG_SOURCES      += $(BENCH_DIR)/rtl/comparison_bench.sv
VERILOG_INCLUDE_DIRS += $(BENCH_DIR)/rtl
CUSTOM_COMPILE_DEPS  += $(BENCH_DIR)/rtl/classes.svh

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL             := comparison_bench
TOPLEVEL_LANG        ?= verilog

# MODULE is the basename of the Python test file(s). Every flavour but pyuvm
# shares one testbench - the loop is common, and only the work under test is
# behind an if.
ifeq ($(FLAVOUR),pyuvm)
MODULE               ?= benchmark_pyuvm
else
MODULE               ?= benchmark
endif

# cocotb >= 2.0 no longer exports PYTHONPATH from its own makefiles
PYTHONPATH           := $(BENCH_DIR)/cocotb$(if $(PYTHONPATH),:$(PYTHONPATH))
export PYTHONPATH
export BENCH_FLAVOUR := $(FLAVOUR)

# The classes are compiled into the model for the sv flavour, and randomized by
# the simulator's own solver.
ifeq ($(FLAVOUR),sv)
COMPILE_ARGS         += +define+BENCH_SV
endif

# Jobs the model is compiled with. Compilation happens once, before anything is
# measured, so this changes how long a run takes to get started and nothing about
# what it measures.
BUILD_JOBS           ?= $(shell getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)

# Seed the simulator's constraint solver. The Python flavours are seeded through
# cocotb, which seeds the random module from COCOTB_RANDOM_SEED.
ifeq ($(SIM),verilator)
BENCH_PLUSARGS       += +verilator+seed+$(SEED)

# The classes become one large C++ function, and compiling it is the slowest part
# of getting started. Splitting the output into units and building them in
# parallel takes that back. Neither changes what the model does.
COMPILE_ARGS         += --output-split 5000 --output-split-cfuncs 500
BUILD_ARGS           += -j $(BUILD_JOBS)
else ifeq ($(SIM),questa)
SIM_ARGS             += -sv_seed $(SEED)
else ifeq ($(SIM),vcs)
SIM_ARGS             += +ntb_random_seed=$(SEED)
else ifeq ($(SIM),xcelium)
EXTRA_ARGS           += -svseed $(SEED)
endif

# Plusargs the driver sets per run - whether the work under test is enabled, how
# many items are done per clock edge, and how many classes take part. Kept apart
# from BENCH_PLUSARGS so that setting one of them on the command line does not
# drop the other.
RUN_PLUSARGS         ?=

COCOTB_PLUSARGS      += $(BENCH_PLUSARGS) $(RUN_PLUSARGS)

# Questa / ModelSim workaround
VSIM_ARGS            += -lib work

# Benchmarks measure the work under test - never enable waveform tracing here.

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

clean::
	rm -rf $(BENCH_DIR)/cocotb/__pycache__/
	rm -rf *.txt *.xml *.json *.csv *.log sim_build
