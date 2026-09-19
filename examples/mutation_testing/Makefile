#Copyright 2026 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Mutation Testing Regression
#
# Runs the mutation campaign in every example under this directory and reports
# one summary. "make help" lists the targets.

.SILENT:

EXAMPLES := $(sort $(patsubst %/mutation.mk,%,$(wildcard */mutation.mk)))
RESULTS  := $(CURDIR)/.results
VERDICTS := $(addprefix $(RESULTS)/,$(addsuffix .result,$(EXAMPLES)))

# How an example is invoked. Clearing MAKEFLAGS keeps -j, and the jobserver it
# comes with, out of the sub-make: the examples run in parallel, the campaign
# inside any one of them does not. Its mutants share a directory and AVL writes
# coverage.json to the working directory under a fixed name, so concurrent
# mutants would overwrite each other's coverage. Nothing is shared between one
# example and the next - each has its own rtl/, mutants/ and sim_build/, and
# each runs with its own directory as the working directory - so running whole
# examples side by side is safe.
SUBMAKE := $(MAKE) MAKEFLAGS= --no-print-directory

.DEFAULT_GOAL := help

.PHONY: help
help:
	echo "AVL mutation testing"
	echo ""
	echo "Every example below holds a golden design and a testbench. The"
	echo "campaign generates mutated copies of the RTL, runs the testbench"
	echo "against each one, and reports which were caught. A mutation the"
	echo "testbench still passes is a hole in the verification."
	echo ""
	echo "Targets in this directory:"
	echo "  make help          this message"
	echo "  make regression    run every example's campaign, then a summary"
	echo "  make list          list the examples that would be run"
	echo "  make clean         clean every example"
	echo ""
	echo "The regression takes -j, which runs that many examples at once:"
	echo "  make -j 6 regression"
	echo "Each example's own campaign stays serial however many jobs are"
	echo "asked for, so -j costs one simulation's worth of memory per job."
	echo "Results are reported as each example finishes, so the order they"
	echo "appear in varies; the summary at the end does not."
	echo ""
	echo "An example PASSES when its campaign ran, every mutation it asked"
	echo "for was located, and every one of them was either detected or"
	echo "proved equivalent. Anything else FAILS, and a single failure makes"
	echo "the exit status non zero. A failing example does not stop the"
	echo "others. Each run's log is kept under"
	echo "  .results/<example>.log"
	echo ""
	echo "Targets inside any one example:"
	echo "  make sim                  the golden design, as any AVL example"
	echo "  make sim AVL_MUTANT=2     build and run mutant 2, which should fail"
	echo "  make mutants              generate them, check them, write the report"
	echo "  make mutation_regression  every mutant in turn, scored"
	echo "  make clean"
	echo ""
	echo "Examples ($(words $(EXAMPLES))):"
	$(foreach e,$(EXAMPLES),printf '  %-16s %s\n' "$(e)" "$$(sed -n 's/^MUTATION_TYPES *:= *//p' $(e)/mutation.mk)";)

.PHONY: list
list:
	$(foreach e,$(EXAMPLES),echo $(e);)

# Two passes, so that the summary is not written until every example has
# reported. Both are recursive calls rather than prerequisites of one target
# because a prerequisite of the summary would be free to run alongside it.
# The jobserver passes through a recursive call, so -j reaches the first of
# them and the examples run as widely as it allows.
.PHONY: regression
regression:
	rm -rf $(RESULTS)
	mkdir -p $(RESULTS)
	echo ""
	echo "Mutation testing regression"
	echo "---------------------------------------------------------------"
	$(MAKE) --no-print-directory $(VERDICTS)
	$(MAKE) --no-print-directory summary

# One example. The verdict is written to a file as well as printed, so that
# the summary can count the results whatever order they finished in.
#
# The recipe itself succeeds even when the campaign fails: a failure is a
# recorded FAIL, not a reason for make to abandon the examples that have not
# run yet. The summary is what turns a FAIL into a non zero exit status.
$(RESULTS)/%.result: FORCE | $(RESULTS)
	log=$(RESULTS)/$*.log; \
	wanted=$$($(SUBMAKE) -C $* mutation_count 2>/dev/null); \
	wanted=$${wanted:-0}; \
	missing=""; \
	for tool in $$(sed -n 's/^MUTATION_REQUIRES *:= *//p' $*/mutation.mk); do \
	    command -v $$tool >/dev/null 2>&1 || missing="$$missing $$tool"; \
	done; \
	if [ -n "$$missing" ]; then \
	    printf 'SKIP\tneeds%s\n' "$$missing" > $@; \
	else \
	    $(SUBMAKE) -C $* clean > $$log 2>&1; \
	    if $(SUBMAKE) -C $* mutation_regression >> $$log 2>&1; then status=0; else status=1; fi; \
	    found=$$(grep -c '"id":' $*/mutants/faults.json 2>/dev/null || echo 0); \
	    score=$$(sed -n 's/.*"score": *\([0-9.]*\).*/\1/p' $*/mutants/summary.json 2>/dev/null); \
	    if [ "$$status" -ne 0 ]; then \
	        printf 'FAIL\tcampaign failed\n' > $@; \
	    elif [ "$$found" != "$$wanted" ]; then \
	        printf 'FAIL\tlocated %s of %s mutation(s)\n' "$$found" "$$wanted" > $@; \
	    else \
	        printf 'PASS\t%s mutation(s), score %s%%\n' "$$found" "$${score:-n/a}" > $@; \
	    fi; \
	fi; \
	printf '  %-16s %-4s  %s\n' "$*" "$$(cut -f1 $@)" "$$(cut -f2 $@)"

$(RESULTS):
	mkdir -p $@

# An example is re-run every time the regression asks for it, never treated as
# up to date because its verdict from a previous run is still lying around.
.PHONY: FORCE
FORCE:

# Counts the verdicts and sets the exit status. /dev/null is in the list so
# that cut has something to read even if there are no examples at all.
.PHONY: summary
summary:
	verdicts=$$(cut -f1 /dev/null $(VERDICTS) 2>/dev/null); \
	pass=$$(echo "$$verdicts" | grep -c '^PASS' || true); \
	fail=$$(echo "$$verdicts" | grep -c '^FAIL' || true); \
	skip=$$(echo "$$verdicts" | grep -c '^SKIP' || true); \
	echo "---------------------------------------------------------------"; \
	echo "  $$pass/$$((pass + fail)) passed$$([ $$skip -gt 0 ] && echo ", $$skip skipped")"; \
	if [ "$$fail" -ne 0 ]; then \
	    echo ""; \
	    grep -l '^FAIL' $(VERDICTS) 2>/dev/null | sed 's|.*/\(.*\)\.result|  FAILED: \1, see $(RESULTS)/\1.log|'; \
	    exit 1; \
	fi

.PHONY: clean
clean:
	for e in $(EXAMPLES); do \
	    $(SUBMAKE) -C $$e clean; \
	done
	rm -rf $(RESULTS)
