#Copyright 2026 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmarks

.SILENT:

BENCHMARKS    := $(patsubst %/,%,$(wildcard */))

# A benchmark with a Makefile is driven by a simulator through sim.mk, and
# leaves a simulator build directory behind. Not called MAKEFILES: that name is
# reserved, and make would read every one of them into each sub-make.
SIM_MAKEFILES := $(wildcard */Makefile)
CLEANS        := $(patsubst %/Makefile,%/clean,$(SIM_MAKEFILES))

# A benchmark without one is driven by a script of its own, and keeps a working
# copy of what it measures and a virtual environment to measure it against.
SCRIPTED      := $(filter-out $(patsubst %/Makefile,%,$(SIM_MAKEFILES)),$(BENCHMARKS))

# Every benchmark is driven by the single *_benchmark.py in its directory.
DRIVERS       := $(wildcard */*_benchmark.py)
RUNS          := $(patsubst %/,%/run,$(dir $(DRIVERS)))

%clean: %Makefile
	$(MAKE) -C $(dir $<) clean > /dev/null 2>&1

# Arguments differ from one benchmark to the next, so ARGS is only meaningful
# when running a single one. Not declared phony: make does not look for an
# implicit rule to build a phony target, so this pattern would never fire.
%/run:
	echo "== $* =="
	cd $* && ./$(notdir $(wildcard $*/*_benchmark.py)) $(ARGS)

.PHONY: list
list:
	$(foreach m, $(SIM_MAKEFILES), echo "$(patsubst %/,%,$(dir $(m))) (simulator)";)
	$(foreach d, $(SCRIPTED), echo "$(d) (script)";)

# Every benchmark, at its defaults. A sanity sweep rather than a measurement -
# nothing is recorded, so run one benchmark with --json to keep a result.
.PHONY: run
run:
	$(if $(ARGS),$(error ARGS applies to one benchmark - try make <name>/run ARGS="..."))
	$(MAKE) $(RUNS)

# Everything a run leaves behind except its results.
.PHONY: clean
clean: $(CLEANS)
	rm -rf $(foreach d, $(SCRIPTED), $(d)/work $(d)/__pycache__)
	echo "Clean complete"

# Also the results, and the virtual environments the scripted benchmarks build.
# Recorded runs and write-ups are not tracked by git, so this is the only copy
# of them there is.
.PHONY: distclean
distclean: clean
	rm -rf $(foreach d, $(SCRIPTED), $(d)/.venv-*)
	rm -rf $(foreach d, $(BENCHMARKS), $(d)/results)
	echo "Distclean complete"
