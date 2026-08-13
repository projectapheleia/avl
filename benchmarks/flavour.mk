#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmark - flavour driver
#
# Compiles and runs one flavour of a benchmark. Symlink this file in as
# <benchmark>/<flavour>/Makefile - the directory name is the flavour.
#
# Every flavour is built and run exactly the same way, through cocotb, from the
# same RTL. The flavour changes where the randomization happens and nothing
# else:
#
#   sv     +define+BENCH_SV_RANDOMIZE, so the RTL randomizes with SystemVerilog
#          classes and constraints, solved by the simulator
#   avl    no define, so the cocotb testbench randomizes the identical object
#          with AVL instead
#   pyuvm  no define either, and the same RTL, but the testbench is the pyuvm
#          one - the identical object as a pyvsc randobj, randomized from the
#          run_phase of a pyuvm test
#
# Because the flow is cocotb's, any simulator cocotb supports can be used:
#
#   make SIM=questa

include $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))/common.mk

SIM                  ?= verilator
BENCH_TOOL           := $(SIM)

# Sources are shared by every flavour of the benchmark.
VERILOG_SOURCES      += $(sort $(wildcard $(BENCH_DIR)/rtl/*.sv))
VERILOG_INCLUDE_DIRS += $(BENCH_DIR)/rtl

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL             := $(notdir $(BENCH_DIR))_bench
TOPLEVEL_LANG        ?= verilog
# The testbenches import bench_dump from scripts/ for the quality run.
PYTHONPATH           := $(BENCH_DIR)/cocotb:$(BENCH_ROOT)/scripts

# MODULE is the basename of the Python test file(s). The sv and avl flavours
# share one testbench - the loop is common and only the randomization is under
# an if. pyuvm brings its own, because the loop has to live inside a uvm test.
ifeq ($(FLAVOUR),pyuvm)
MODULE               ?= $(notdir $(BENCH_DIR))_pyuvm
else
MODULE               ?= $(notdir $(BENCH_DIR))
endif

export PYTHONPATH
export BENCH_FLAVOUR := $(FLAVOUR)

ifeq ($(FLAVOUR),sv)
COMPILE_ARGS         += +define+BENCH_SV_RANDOMIZE
endif

# Seed the simulator's constraint solver. AVL is seeded through cocotb, which
# seeds the Python random module from COCOTB_RANDOM_SEED.
ifeq ($(SIM),verilator)
BENCH_PLUSARGS       += +verilator+seed+$(SEED)
else ifeq ($(SIM),questa)
SIM_ARGS             += -sv_seed $(SEED)
else ifeq ($(SIM),vcs)
SIM_ARGS             += +ntb_random_seed=$(SEED)
else ifeq ($(SIM),xcelium)
EXTRA_ARGS           += -svseed $(SEED)
endif

# Questa / ModelSim workaround
VSIM_ARGS            += -lib work

# No waveform tracing - it would be measured as randomization cost.

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

# cocotb's makefiles make "sim" the default goal.
.DEFAULT_GOAL        := bench

# Randomization is enabled for the measured run and disabled for the baseline.
# SystemVerilog reads a plusarg, Python reads the environment - the two flavours
# are otherwise driven identically.
COCOTB_RUN            = env MAKEFLAGS= \
                          COCOTB_RANDOM_SEED=$(SEED) \
                          BENCH_ITERATIONS=$(ITERATIONS) \
                          BENCH_BURST=$(BURST) \
                          BENCH_RANDOMIZE=$(1) \
                          $(MAKE) --no-print-directory -C $(CURDIR) sim \
                            COCOTB_PLUSARGS="+randomize=$(1) +burst=$(BURST) $(BENCH_PLUSARGS)"

.PHONY: bench build warm baseline run quality

bench: build warm baseline run quality

# Elaborate and compile the model, outside the measurement.
build:
	@echo "  $(FLAVOUR)  building with cocotb / $(SIM)"
	@$(call COCOTB_RUN,0) > $(CURDIR)/build.log 2>&1 || \
	  { echo "  $(FLAVOUR)  build FAILED - see $(CURDIR)/build.log"; exit 1; }

# An untimed run first, so that the measured runs are not the ones paying for
# cold file caches and .pyc compilation.
warm: build
	@$(call COCOTB_RUN,1) > $(CURDIR)/warm.log 2>&1 || \
	  { echo "  $(FLAVOUR)  run FAILED - see $(CURDIR)/warm.log"; exit 1; }

# The same testbench, driving the same number of clock cycles, with the
# randomization switched off. Everything except randomization is measured here:
# interpreter and simulator startup, elaboration, cocotb bringup and the cost of
# running the loop itself.
baseline: build
	@$(BENCH_TIME) --phase baseline --iterations $(ITERATIONS) --log $(CURDIR)/baseline.log \
	  -- $(call COCOTB_RUN,0)

run: build
	@$(BENCH_TIME) --phase run --iterations $(ITERATIONS) --log $(CURDIR)/run.log \
	  -- $(call COCOTB_RUN,1)

# Records every value drawn, for bench_quality.py to measure the spread of.
# Untimed and separate from the measured runs, because the values have to be
# written somewhere and that must not show up in a measurement. Runs last so it
# cannot perturb them either.
quality: build
	@rm -f $(QUALITY_DUMP)
	@env MAKEFLAGS= \
	   COCOTB_RANDOM_SEED=$(SEED) \
	   BENCH_ITERATIONS=$(QUALITY_ITERATIONS) \
	   BENCH_BURST=1 \
	   BENCH_RANDOMIZE=1 \
	   BENCH_DUMP=$(QUALITY_DUMP) \
	   $(MAKE) --no-print-directory -C $(CURDIR) sim \
	     COCOTB_PLUSARGS="+randomize=1 +burst=1 +dump=$(QUALITY_DUMP) $(BENCH_PLUSARGS)" \
	   > $(CURDIR)/quality.log 2>&1 || \
	  { echo "  $(FLAVOUR)  quality FAILED - see $(CURDIR)/quality.log"; exit 1; }
	@test -s $(QUALITY_DUMP) || \
	  { echo "  $(FLAVOUR)  quality recorded nothing - see $(CURDIR)/quality.log"; exit 1; }
	@echo "  $(FLAVOUR)  quality   $(QUALITY_ITERATIONS) draws recorded"

clean::
	rm -rf $(BENCH_DIR)/cocotb/__pycache__/
	rm -f *.log *.xml quality.csv
