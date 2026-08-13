#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmark - per benchmark driver
#
# Runs every flavour of one benchmark and reports the result. Symlink this file
# in as <benchmark>/Makefile. A flavour is any subdirectory holding a Makefile.

BENCH_ROOT     := $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))
BENCH_NAME     := $(patsubst $(BENCH_ROOT)/%,%,$(CURDIR))

# Any subdirectory holding a Makefile is a flavour. The reference implementation
# is run first, anything else in the order it is found.
ALL_FLAVOURS   := $(patsubst $(CURDIR)/%/Makefile,%,$(wildcard $(CURDIR)/*/Makefile))
FLAVOURS       ?= sv avl pyuvm $(filter-out sv avl pyuvm,$(ALL_FLAVOURS))
FLAVOUR_DIRS   := $(foreach f,$(FLAVOURS),$(wildcard $(CURDIR)/$(f)/Makefile))

# Optional per benchmark defaults - a category whose randomizations are much
# cheaper or much dearer than the rest can set its own ITERATIONS and BURST.
# Either may also be set for one flavour alone, as ITERATIONS_<flavour> and
# BURST_<flavour>, for a flavour whose cost is out of proportion to the rest and
# which would otherwise dominate the run. The report compares time per
# randomization, so the counts do not have to match.
-include $(CURDIR)/bench.conf

RESULTS        := $(CURDIR)/results.csv

# One per flavour, written by its quality run. Passed to the scripts as is,
# not through wildcard - that caches the directory as it was when this file was
# read, which is before the runs have written anything.
QUALITY_DUMPS  := $(foreach m,$(FLAVOUR_DIRS),$(dir $(m))quality.csv)

# Flavours held to the randomization quality thresholds. AVL is what this
# tree is responsible for; the others are measured but not failed on.
QUALITY_CHECK  ?= avl

PYTHON         ?= python3

# Set to 0 by the top level makefile, which reports on every benchmark at once.
BENCH_REPORT   ?= 1

# The flavour a Makefile belongs to is its directory name.
flavour_of      = $(notdir $(patsubst %/,%,$(dir $(1))))

# A per flavour override from bench.conf applies only when the variable was not
# given on the command line, so an explicit "make ITERATIONS=5000" still governs
# every flavour and the comparison stays under the user's control.
# Wrapped in strip, because the continuation below would otherwise leave a space
# in the middle of the assignment and make would read the value as a goal.
iterations_for  = $(strip $(if $(filter command line,$(origin ITERATIONS)),$(ITERATIONS),\
                    $(or $(ITERATIONS_$(1)),$(ITERATIONS))))
burst_for       = $(strip $(if $(filter command line,$(origin BURST)),$(BURST),\
                    $(or $(BURST_$(1)),$(BURST))))

# Passed down to the flavours - see common.mk for the defaults. Takes the
# flavour as its argument, so the per flavour overrides can be resolved.
BENCH_VARS      = $(if $(call iterations_for,$(1)),ITERATIONS=$(call iterations_for,$(1))) \
                  $(if $(REPEATS),REPEATS=$(REPEATS)) \
                  $(if $(SEED),SEED=$(SEED)) \
                  $(if $(SIM),SIM=$(SIM)) \
                  $(if $(call burst_for,$(1)),BURST=$(call burst_for,$(1)))

.DEFAULT_GOAL  := bench

# One benchmark at a time, otherwise the flavours compete for the same cores.
.NOTPARALLEL:

.PHONY: bench sim report quality clean list

bench:
	@echo "$(BENCH_NAME)"
	@rm -f $(RESULTS)
	@$(foreach m,$(FLAVOUR_DIRS), \
	  $(MAKE) --no-print-directory -C $(dir $(m)) bench \
	    $(call BENCH_VARS,$(call flavour_of,$(m))) || exit 1;)
	@$(if $(filter-out 0,$(BENCH_REPORT)),$(MAKE) --no-print-directory report)

# Alias, for consistency with the examples tree.
sim: bench

report:
	@$(PYTHON) $(BENCH_ROOT)/scripts/bench_report.py $(RESULTS) \
	  --title "$(BENCH_NAME)" --output $(CURDIR)/results \
	  --quality $(QUALITY_DUMPS) \
	  $(if $(QUALITY_CHECK),--quality-check $(QUALITY_CHECK))

# Just the randomization quality, without re-timing anything.
quality:
	@echo "$(BENCH_NAME)"
	@$(foreach m,$(FLAVOUR_DIRS), \
	  $(MAKE) --no-print-directory -C $(dir $(m)) quality \
	    $(call BENCH_VARS,$(call flavour_of,$(m))) || exit 1;)
	@$(PYTHON) $(BENCH_ROOT)/scripts/bench_quality.py $(QUALITY_DUMPS) \
	  --check $(QUALITY_CHECK)

clean:
	@$(foreach m,$(FLAVOUR_DIRS), \
	  $(MAKE) --no-print-directory -C $(dir $(m)) clean > /dev/null 2>&1;)
	rm -rf $(RESULTS) $(CURDIR)/results

list:
	@$(foreach m,$(FLAVOUR_DIRS),echo "$(BENCH_NAME)/$(notdir $(patsubst %/,%,$(dir $(m))))";)
