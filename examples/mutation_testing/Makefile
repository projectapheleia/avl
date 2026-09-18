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
	echo "An example PASSES when its campaign ran, every mutation it asked"
	echo "for was located, and every one of them was either detected or"
	echo "proved equivalent. Anything else FAILS, and a single failure makes"
	echo "the exit status non zero. Each run's log is kept under"
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

.PHONY: regression
regression:
	rm -rf $(RESULTS)
	mkdir -p $(RESULTS)
	fail=0; \
	skip=0; \
	total=0; \
	echo ""; \
	echo "Mutation testing regression"; \
	echo "---------------------------------------------------------------"; \
	for e in $(EXAMPLES); do \
	    total=$$((total + 1)); \
	    mkdir -p $(RESULTS); \
	    log=$(RESULTS)/$$e.log; \
	    wanted=$$($(MAKE) --no-print-directory -C $$e mutation_count 2>/dev/null); \
	    wanted=$${wanted:-0}; \
	    missing=""; \
	    for tool in $$(sed -n 's/^MUTATION_REQUIRES *:= *//p' $$e/mutation.mk); do \
	        command -v $$tool >/dev/null 2>&1 || missing="$$missing $$tool"; \
	    done; \
	    if [ -n "$$missing" ]; then \
	        skip=$$((skip + 1)); \
	        printf '  %-16s %-4s  needs%s\n' "$$e" "SKIP" "$$missing"; \
	        continue; \
	    fi; \
	    $(MAKE) -C $$e clean > $$log 2>&1; \
	    if $(MAKE) -C $$e mutation_regression >> $$log 2>&1; then status=0; else status=1; fi; \
	    found=$$(grep -c '"id":' $$e/mutants/faults.json 2>/dev/null || echo 0); \
	    score=$$(sed -n 's/.*"score": *\([0-9.]*\).*/\1/p' $$e/mutants/summary.json 2>/dev/null); \
	    if [ "$$status" -ne 0 ]; then \
	        verdict=FAIL; why="campaign failed"; \
	    elif [ "$$found" != "$$wanted" ]; then \
	        verdict=FAIL; why="located $$found of $$wanted mutation(s)"; \
	    else \
	        verdict=PASS; why="$$found mutation(s), score $${score:-n/a}%"; \
	    fi; \
	    if [ "$$verdict" = FAIL ]; then fail=$$((fail + 1)); fi; \
	    printf '  %-16s %-4s  %s\n' "$$e" "$$verdict" "$$why"; \
	done; \
	echo "---------------------------------------------------------------"; \
	echo "  $$((total - fail - skip))/$$((total - skip)) passed$$([ $$skip -gt 0 ] && echo ", $$skip skipped")"; \
	if [ "$$fail" -ne 0 ]; then \
	    echo ""; \
	    echo "  Logs: $(RESULTS)/<example>.log"; \
	    exit 1; \
	fi

.PHONY: clean
clean:
	for e in $(EXAMPLES); do \
	    $(MAKE) --no-print-directory -C $$e clean; \
	done
	rm -rf $(RESULTS)
