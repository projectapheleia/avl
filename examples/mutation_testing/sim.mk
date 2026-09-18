#Copyright 2026 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Mutation Testing Example
#
# Shared by every example under mutation_testing/. Each example supplies its
# own mutation.mk naming the mutations it wants.
#
#   make sim                golden design, exactly like any other AVL example
#   make sim AVL_MUTANT=2   build and run mutant 2, which should fail
#   make mutate             run the golden design and every mutant, scored
#   make clean

# Per example settings, overridden by <example>/mutation.mk. MUTATION_REQUIRES
# names any tool the example cannot do without - the regression above skips an
# example rather than failing it when one is missing.
MUTATION_COUNT    ?= 3
MUTATION_TYPES    ?= arith
MUTATION_REQUIRES ?=
-include $(CURDIR)/mutation.mk

# Every file of the design, sorted so that the mutations are numbered the same
# way on every machine. A design split across several files needs no more than
# this: each mutant is a complete copy of all of them with one file changed.
GOLDEN_RTL  ?= $(sort $(wildcard $(CURDIR)/rtl/*.sv))

MUTANT_DIR  := $(CURDIR)/mutants
MUTANT_JSON := $(MUTANT_DIR)/faults.json

# One seed for the whole campaign. Without this cocotb draws a fresh seed from
# the clock for every simulation, so the golden design and each mutant would see
# different stimulus - and whether a mutation was caught would depend on which
# random numbers its own run happened to draw rather than on whether the
# testbench can catch it. Boundary mutations are the ones that suffer: they need
# a particular input, so they are exactly the mutations a drifting seed decides
# by luck. Override it to sweep, but sweep the whole campaign together.
COCOTB_RANDOM_SEED ?= 1
export COCOTB_RANDOM_SEED

# Which design to build. 0 is the golden source, so the default build is the
# unmodified RTL and a plain "make sim" behaves like every other example.
AVL_MUTANT ?= 0

ifeq ($(AVL_MUTANT),0)
AVL_RTL    := $(GOLDEN_RTL)
else
AVL_RTL    := $(addprefix $(MUTANT_DIR)/$(AVL_MUTANT)/,$(notdir $(GOLDEN_RTL)))
endif

# Keep one build tree per mutant so switching between them does not force a
# rebuild of the ones already compiled.
SIM_BUILD  := $(CURDIR)/sim_build/$(AVL_MUTANT)

# Declared before the include so the mutants exist before cocotb builds
# anything - make works through a target's prerequisites in the order they were
# added, and the include appends its own.
sim: $(MUTANT_JSON)

include ../../sim.mk

# The mutants are generated from the golden source, never edited by hand.
#
# --top names the module the equivalence check compares. It matters once the
# design has sub-modules: without it yosys would be pointed at whichever module
# the mutation happened to land in, rather than at the top of the design.
$(MUTANT_JSON): $(GOLDEN_RTL)
	avl-mutation-testing --source $(GOLDEN_RTL) --output $(MUTANT_DIR) \
	                     --types $(MUTATION_TYPES) --count $(MUTATION_COUNT) \
	                     --top $(TOPLEVEL) --json $(MUTANT_JSON)

.PHONY: mutants
mutants: $(MUTANT_JSON)

# How many mutations this example asks for. The regression in the directory
# above uses it to check that every one of them was actually located.
.PHONY: mutation_count
mutation_count:
	@echo $(MUTATION_COUNT)

.PHONY: mutation_requires
mutation_requires:
	@echo $(MUTATION_REQUIRES)

# Run the testbench against the golden design and every mutant, and report what
# was caught. Each run's log and results are kept under mutants/<id>/ so a
# surprising verdict can be looked into without re-running the campaign.
#
# Serial by design. Every run shares this directory, and AVL writes coverage.json
# to the working directory with a fixed name, so running mutants concurrently
# here would have them overwrite each other's coverage.
.PHONY: mutation_regression
mutation_regression: $(MUTANT_JSON)
	avl-mutation-testing --grade --json $(MUTANT_JSON) --directory $(CURDIR) \
	                     --archive $(MUTANT_DIR) --make "$(MAKE) sim"

# Shorthands. "regression" is already taken by cocotb's makefiles, where it
# means run this one test if it is out of date.
.PHONY: mutate
mutate: mutation_regression

clean::
	rm -rf $(MUTANT_DIR) $(CURDIR)/sim_build
