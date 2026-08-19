#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmark - flavour driver
#
# Compiles and runs one flavour of a benchmark. Symlink this file in as
# <benchmark>/<flavour>/Makefile - the directory name is the flavour.
#
# Every flavour is built and run exactly the same way, through cocotb, from the
# same RTL. The flavour changes where the work under test happens and nothing
# else:
#
#   sv     +define+BENCH_SV, so the RTL does the work in SystemVerilog - a class
#          randomized by the simulator's solver, or an object built and driven
#          onto the signals from inside the module
#   avl    no define, so the cocotb testbench does it on the identical object
#          with AVL instead
#   pyuvm  no define either, and the same RTL, but the testbench is the pyuvm
#          one - working on the same object from the run_phase of a pyuvm test,
#          with pyvsc where it has to be randomized
#
# Because the flow is cocotb's, any simulator cocotb supports can be used:
#
#   make SIM=questa

include $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))/common.mk

SIM                  ?= verilator
BENCH_TOOL           := $(SIM)

# Sources are shared by every flavour of the benchmark, and - where a group of
# benchmarks differs only in configuration - by every benchmark in the group.
# See BENCH_SOURCE_DIR in common.mk.
VERILOG_SOURCES      += $(sort $(wildcard $(BENCH_SOURCE_DIR)/rtl/*.sv))
VERILOG_INCLUDE_DIRS += $(BENCH_SOURCE_DIR)/rtl

# TOPLEVEL is the name of the toplevel module in your Verilog or VHDL file
TOPLEVEL             ?= $(notdir $(BENCH_SOURCE_DIR))_bench
TOPLEVEL_LANG        ?= verilog
# The testbenches import bench_dump from scripts/ for the quality run.
PYTHONPATH           := $(BENCH_SOURCE_DIR)/cocotb:$(BENCH_ROOT)/scripts

# MODULE is the basename of the Python test file(s). The sv and avl flavours
# share one testbench - the loop is common and only the randomization is under
# an if. pyuvm brings its own, because the loop has to live inside a uvm test.
ifeq ($(FLAVOUR),pyuvm)
MODULE               ?= $(notdir $(BENCH_SOURCE_DIR))_pyuvm
else
MODULE               ?= $(notdir $(BENCH_SOURCE_DIR))
endif

export PYTHONPATH
export BENCH_FLAVOUR := $(FLAVOUR)

# BENCH_SV_RANDOMIZE is the older name, kept because the randomization
# benchmarks are written against it. BENCH_SV says the same thing without
# claiming that what the RTL does under it is randomization.
ifeq ($(FLAVOUR),sv)
COMPILE_ARGS         += +define+BENCH_SV_RANDOMIZE +define+BENCH_SV
endif

# Which edit of the testbench to build - see BENCH_PHASES in common.mk. Set by
# bench_edit.py in the environment this make inherits, to a number that differs
# with every edit, and unset everywhere else.
#
# The sv flavour's testbench is compiled with the design, so its edit is a
# define the model has to be elaborated and compiled again for. The Python
# flavours read the same value from the environment at run time and rebuild
# nothing. That difference is the entire subject of the turnaround benchmark, so
# it is expressed here rather than hidden inside a testbench.
ifneq ($(BENCH_EDIT),)
ifeq ($(FLAVOUR),sv)
COMPILE_ARGS         += +define+BENCH_EDIT=$(BENCH_EDIT)
endif
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
#
# BENCH_EDIT is deliberately not set here: on the turnaround benchmarks it is
# put into the environment by bench_edit.py, which has to choose it afresh for
# every repeat, and an assignment on this line would overwrite it.
COCOTB_RUN            = env MAKEFLAGS= \
                          COCOTB_RANDOM_SEED=$(SEED) \
                          BENCH_ITERATIONS=$(ITERATIONS) \
                          BENCH_BURST=$(BURST) \
                          BENCH_RANDOMIZE=$(1) \
                          $(BENCH_ENV) \
                          $(MAKE) --no-print-directory -C $(CURDIR) sim \
                            COCOTB_PLUSARGS="+randomize=$(1) +burst=$(BURST) $(BENCH_PLUSARGS)"

# ---------------------------------------------------------------------------
# Turnaround - see BENCH_PHASES in common.mk. Unused by a benchmark measuring
# work rather than the wait to see it.
# ---------------------------------------------------------------------------

# Everything a build produces, and so everything a cold build has to produce
# again. SIM_BUILD is cocotb's, and is this flavour's alone; the byte compiled
# testbench is shared with any other benchmark built from the same sources,
# which only means they compile it again too.
BENCH_COLD_PATHS     ?= $(abspath $(SIM_BUILD)) $(BENCH_SOURCE_DIR)/cocotb/__pycache__

# Where a minor edit to the testbench lands. For sv that is the RTL - the sv
# flavour's testbench lives inside it, behind `ifdef BENCH_SV - and for the
# others it is the cocotb module. Each flavour's own testbench, and nothing
# else: the design is not what is being edited.
ifeq ($(FLAVOUR),sv)
BENCH_EDIT_FILES     ?= $(VERILOG_SOURCES)
else
BENCH_EDIT_FILES     ?= $(BENCH_SOURCE_DIR)/cocotb/$(MODULE).py
endif

# Named apart from BENCH_EDIT, which is the flag above and arrives from the
# environment - a makefile variable of that name would shadow it, and the sv
# flavour would quietly never be given its define.
BENCH_EDIT_CMD        = $(PYTHON) $(BENCH_ROOT)/scripts/bench_edit.py

.PHONY: bench build warm baseline run quality cold rerun edit

ifeq ($(BENCH_PHASES),turnaround)
# Nothing is built beforehand and nothing is warmed - here the build is the
# measurement, and a warm run would have done half of it already.
#
# In this order, and not in parallel: rerun needs what cold built, and edit
# needs the model rerun proved was up to date.
bench: cold rerun edit
else
# A benchmark that does not randomize has no quality to measure - see
# BENCH_QUALITY in common.mk.
bench: build warm baseline run $(if $(filter-out 0,$(BENCH_QUALITY)),quality)
endif

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

# A checkout that has never been simulated: the model elaborated and compiled
# from nothing, the testbench byte compiled from nothing, and the test run. What
# it costs to see this testbench work for the first time.
#
# One iteration is one build and run, not one transaction - the report divides
# by it, and what is being compared here is the wait, whole. How much the run
# then does is ITERATIONS, and is deliberately small: it has to be a real run,
# but it is not the thing being measured.
cold:
	@echo "  $(FLAVOUR)  cold      building and running from scratch"
	@$(BENCH_TIME) --phase cold --iterations 1 --log $(CURDIR)/cold.log \
	  -- $(BENCH_EDIT_CMD) --remove $(BENCH_COLD_PATHS) -- $(call COCOTB_RUN,1)

# The same thing again with nothing changed at all: no file touched, no define
# moved, so there is nothing for any flavour to build and this is the run on its
# own. Recorded as the "baseline" phase, and subtracted from the one below -
# what is left is the rebuild an edit forced, and nothing else. For a testbench
# the simulator never compiled, that is zero, and the report says so.
rerun:
	@echo "  $(FLAVOUR)  rerun     running again with nothing changed"
	@$(BENCH_TIME) --phase baseline --iterations 1 --log $(CURDIR)/rerun.log \
	  -- $(call COCOTB_RUN,1)

# One line of the testbench changed, and nothing else touched. For sv that line
# is in a source the model was compiled from, so the model is elaborated and
# compiled again before anything can run; for the Python flavours there is
# nothing to compile but the module itself, and the model the simulator already
# built still stands. Recorded as the "run" phase, because it is the figure this
# benchmark exists to compare.
edit:
	@echo "  $(FLAVOUR)  edit      rebuilding and running after a testbench edit"
	@$(BENCH_TIME) --phase run --iterations 1 --log $(CURDIR)/edit.log \
	  -- $(BENCH_EDIT_CMD) --touch $(BENCH_EDIT_FILES) --revision BENCH_EDIT \
	     -- $(call COCOTB_RUN,1)

# Records every value drawn, for bench_quality.py to measure the spread of.
# Untimed and separate from the measured runs, because the values have to be
# written somewhere and that must not show up in a measurement. Runs last so it
# cannot perturb them either.
quality: build
ifeq ($(BENCH_QUALITY),0)
	@echo "  $(FLAVOUR)  quality   nothing is randomized here - not measured"
else
	@rm -f $(QUALITY_DUMP)
	@env MAKEFLAGS= \
	   COCOTB_RANDOM_SEED=$(SEED) \
	   BENCH_ITERATIONS=$(QUALITY_ITERATIONS) \
	   BENCH_BURST=1 \
	   BENCH_RANDOMIZE=1 \
	   BENCH_DUMP=$(QUALITY_DUMP) \
	   $(BENCH_ENV) \
	   $(MAKE) --no-print-directory -C $(CURDIR) sim \
	     COCOTB_PLUSARGS="+randomize=1 +burst=1 +dump=$(QUALITY_DUMP) $(BENCH_PLUSARGS)" \
	   > $(CURDIR)/quality.log 2>&1 || \
	  { echo "  $(FLAVOUR)  quality FAILED - see $(CURDIR)/quality.log"; exit 1; }
	@test -s $(QUALITY_DUMP) || \
	  { echo "  $(FLAVOUR)  quality recorded nothing - see $(CURDIR)/quality.log"; exit 1; }
	@echo "  $(FLAVOUR)  quality   $(QUALITY_ITERATIONS) draws recorded"
endif

clean::
	rm -rf $(BENCH_SOURCE_DIR)/cocotb/__pycache__/
	rm -f *.log *.xml quality.csv
