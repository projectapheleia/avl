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

# Optional per benchmark settings - the same file bench.mk reads, so a benchmark
# can set anything below as well as its ITERATIONS and BURST. Read before the
# defaults, so that a "?=" here wins over the default and a command line
# variable still wins over both.
-include $(BENCH_DIR)/bench.conf

# Where a benchmark's sources live. Benchmarks that differ only in configuration
# share one set, and point at it from their bench.conf.
BENCH_SOURCE_DIR ?= $(BENCH_DIR)

# What a single iteration of this benchmark is, in the singular. Recorded with
# every timing row, and the word the report is then written in.
BENCH_UNIT     ?= randomization

# What this benchmark measures, and so which phases its flavours are run
# through:
#
#   work        the default. An already built model is run twice - once with the
#               work under test switched on and once with it off - and the two
#               are subtracted, leaving the cost of the work alone.
#   turnaround  a build and run from nothing, then a build and run again after a
#               minor edit to the testbench. Nothing is subtracted: the figure is
#               the whole wait, which is what a turnaround is.
#
# The two cannot be mixed within a benchmark - a phase is either measuring work
# or measuring the wait to see it - so this is set per benchmark in bench.conf.
BENCH_PHASES   ?= work

# Whether this benchmark has a randomization quality to measure. Cleared by a
# benchmark that does not randomize at all.
BENCH_QUALITY  ?= 1

# Extra environment for the testbench, as "NAME=value ..." - anything a
# benchmark's own controls need on top of the ones every flavour is given.
BENCH_ENV      ?=

# Number of iterations - randomizations, items sent - performed by a single run
# of the testbench.
ITERATIONS     ?= 1000

# Iterations performed per clock edge. One per edge is the default. Raise it only
# where a single iteration is too cheap to measure against the cost of advancing
# the clock, around 8 us. ITERATIONS should be a multiple.
BURST          ?= 1

# A burst bigger than the run itself would iterate more times than were asked
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
                    --unit $(BENCH_UNIT) \
                    --repeats $(REPEATS) \
                    --interval $(SAMPLE_INTERVAL)

# Timing is meaningless if two testbenches are competing for the same cores.
.NOTPARALLEL:
