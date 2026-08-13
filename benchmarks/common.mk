#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmark - settings shared by every flavour
#
# Included by sv.mk and avl.mk. Not used directly.

# Root of the benchmark tree. The flavour makefiles are symlinked into each
# benchmark, so resolve the symlink to find where this file actually lives.
BENCH_ROOT     := $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))

# Directory of the benchmark this flavour belongs to, and its name relative to
# the benchmark root - e.g. "randomization/basic".
FLAVOUR_DIR    := $(CURDIR)
FLAVOUR        ?= $(notdir $(CURDIR))
BENCH_DIR      := $(patsubst %/,%,$(dir $(CURDIR)))
BENCH_NAME     := $(patsubst $(BENCH_ROOT)/%,%,$(BENCH_DIR))

# Number of randomizations performed by a single run of the testbench.
ITERATIONS     ?= 1000

# Randomizations performed per clock edge. One per edge is the default. Raise it
# only where a single randomization is too cheap to measure against the cost of
# advancing the clock, around 8 us. ITERATIONS should be a multiple.
BURST          ?= 1

# A burst bigger than the run itself would randomize more times than were asked
# for, and the report would divide by the wrong number. This matters when
# ITERATIONS is overridden on the command line, below a benchmark's own BURST.
# "override" is needed because BURST reaches here as a command line variable.
override BURST := $(shell if [ $(BURST) -gt $(ITERATIONS) ]; then \
                            echo $(ITERATIONS); else echo $(BURST); fi)

# Number of times each testbench is run. The report uses the median, so an odd
# number is preferable.
REPEATS        ?= 3

# Randomizations performed by the quality run, which measures how well spread
# the values were rather than how fast they came. Enough for the per bit
# statistics to mean something; it is untimed, so it can afford them.
QUALITY_ITERATIONS ?= 1000

# Random seed, applied to both flavours so a run is repeatable.
SEED           ?= 1

# Sampling interval, in seconds, of the CPU accounting in bench_time.py.
SAMPLE_INTERVAL ?= 0.02

# Every flavour of a benchmark appends to the same file.
RESULTS        := $(BENCH_DIR)/results.csv

# The values drawn by this flavour's quality run.
QUALITY_DUMP   := $(CURDIR)/quality.csv

PYTHON         ?= python3

# Timing harness. Append "-- <command>" to measure a command.
BENCH_TIME      = $(PYTHON) $(BENCH_ROOT)/scripts/bench_time.py \
                    --csv $(RESULTS) \
                    --benchmark $(BENCH_NAME) \
                    --flavour $(FLAVOUR) \
                    --tool $(BENCH_TOOL) \
                    --repeats $(REPEATS) \
                    --interval $(SAMPLE_INTERVAL)

# Timing is meaningless if two testbenches are competing for the same cores.
.NOTPARALLEL:
