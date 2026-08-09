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
FLAVOURS       ?= sv avl $(filter-out sv avl,$(ALL_FLAVOURS))
FLAVOUR_DIRS   := $(foreach f,$(FLAVOURS),$(wildcard $(CURDIR)/$(f)/Makefile))

# Optional per benchmark defaults - a category whose randomizations are much
# cheaper or much dearer than the rest can set its own ITERATIONS and BURST.
-include $(CURDIR)/bench.conf

RESULTS        := $(CURDIR)/results.csv
PYTHON         ?= python3

# Set to 0 by the top level makefile, which reports on every benchmark at once.
BENCH_REPORT   ?= 1

# Passed down to the flavours - see common.mk for the defaults.
BENCH_VARS      = $(if $(ITERATIONS),ITERATIONS=$(ITERATIONS)) \
                  $(if $(REPEATS),REPEATS=$(REPEATS)) \
                  $(if $(SEED),SEED=$(SEED)) \
                  $(if $(SIM),SIM=$(SIM)) \
                  $(if $(BURST),BURST=$(BURST))

.DEFAULT_GOAL  := bench

# One benchmark at a time, otherwise the flavours compete for the same cores.
.NOTPARALLEL:

.PHONY: bench sim report clean list

bench:
	@echo "$(BENCH_NAME)"
	@rm -f $(RESULTS)
	@$(foreach m,$(FLAVOUR_DIRS), \
	  $(MAKE) --no-print-directory -C $(dir $(m)) bench $(BENCH_VARS) || exit 1;)
	@$(if $(filter-out 0,$(BENCH_REPORT)),$(MAKE) --no-print-directory report)

# Alias, for consistency with the examples tree.
sim: bench

report:
	@$(PYTHON) $(BENCH_ROOT)/scripts/bench_report.py $(RESULTS) \
	  --title "$(BENCH_NAME)" --output $(CURDIR)/results

clean:
	@$(foreach m,$(FLAVOUR_DIRS), \
	  $(MAKE) --no-print-directory -C $(dir $(m)) clean > /dev/null 2>&1;)
	rm -rf $(RESULTS) $(CURDIR)/results

list:
	@$(foreach m,$(FLAVOUR_DIRS),echo "$(BENCH_NAME)/$(notdir $(patsubst %/,%,$(dir $(m))))";)
