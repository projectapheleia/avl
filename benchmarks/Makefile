#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmarks
#
# Runs every benchmark in the tree and reports the results side by side.
#
#   make bench                  run everything with the default settings
#   make bench BENCHES=create_and_send   run one group, and report on just it
#   make bench ITERATIONS=5000  5000 iterations per run
#   make bench REPEATS=5        run each testbench 5 times, report the median
#   make -C randomization/mixed run one benchmark on its own
#   make list                   list the benchmarks
#   make report                 re-print the report without re-running
#   make clean
#
# BENCHES restricts every one of those - bench, quality, report, list and clean.
#
# The report covers everything that was run, and each group of benchmarks -
# randomization, create_and_send - is also reported on in its own right, under
# the same output directory. Every one of them carries the machine and the tool
# versions it was measured with, and links to the others.

.SILENT:

# A benchmark is any directory whose Makefile is a symlink to bench.mk.
# Note this must not be called MAKEFILES - that is a special variable which make
# would then try to read as makefiles, in this and in every sub-make.
ALL_MAKEFILES   := $(shell find */* -type l -name Makefile -lname '*bench.mk')
ALL_BENCHES     := $(patsubst %/Makefile,%,$(ALL_MAKEFILES))

# What to run, report on or clean. Everything by default; name a group or
# particular benchmarks to restrict it, and the report then covers just those:
#
#   make bench BENCHES=create_and_send
#   make bench BENCHES="randomization/mixed randomization/cross"
BENCHES         ?= $(ALL_BENCHES)

BENCH_MAKEFILES := $(foreach b,$(BENCHES),$(filter $(patsubst %/,%,$(b))/%,$(ALL_MAKEFILES)))
RESULTS         := $(patsubst %/Makefile,%/results.csv,$(BENCH_MAKEFILES))
# Left as a glob for the shell to expand when the report runs - make's own
# wildcard caches the directory from before the runs wrote anything.
QUALITY         := $(patsubst %/Makefile,%/*/quality.csv,$(BENCH_MAKEFILES))

# A group is the top level directory a benchmark sits in, and so the kind of
# thing the benchmarks in it measure. Each is reported on separately as well as
# in the combined report: a group is written in the words of what it measures -
# randomizations, items - where a report spanning several kinds can only be
# neutral about them, and comparing one group against another is meaningless
# anyway.
GROUPS          := $(sort $(foreach m,$(BENCH_MAKEFILES),$(firstword $(subst /, ,$(m)))))

# The results, and the quality dumps, of one group. The quality dumps are left
# as a glob for the shell for the same reason as QUALITY above.
results_in       = $(patsubst %/Makefile,%/results.csv,$(filter $(1)/%,$(BENCH_MAKEFILES)))
quality_in       = $(patsubst %/Makefile,%/*/quality.csv,$(filter $(1)/%,$(BENCH_MAKEFILES)))

# The groups something has actually been run in. Deliberately recursive, so that
# it is resolved when the report runs rather than when this file is read - a
# report following a run in the same invocation would otherwise be deciding on
# the tree as it was before the run wrote anything.
#
# A group with nothing to report on is one whose benchmarks have not been run,
# or were interrupted, and there is no report to write for it.
GROUPS_RUN       = $(sort $(foreach g,$(GROUPS),$(if $(wildcard $(call results_in,$(g))),$(g))))

# Only worth writing when more than one group has results - a single group's
# report would be the combined report again under another name.
GROUP_REPORTS    = $(if $(word 2,$(GROUPS_RUN)),$(GROUPS_RUN))

# Benchmarks that were asked for but have no results. Everything below still
# reports on what there is, so this is said rather than fallen over - but it is
# said, because a partial report looks exactly like a complete one otherwise.
# This is how a report taken while a run is still going announces itself.
MISSING          = $(foreach m,$(BENCH_MAKEFILES),\
                     $(if $(wildcard $(patsubst %/Makefile,%/results.csv,$(m))),,\
                       $(patsubst %/Makefile,%,$(m))))

ifeq ($(strip $(BENCH_MAKEFILES)),)
ifneq ($(filter command line,$(origin BENCHES)),)
$(error No benchmarks match BENCHES="$(BENCHES)" - "make list" shows what there is)
endif
endif

# Named after the subset when one was asked for, so that a report says what it
# covers rather than claiming to be the lot. Also where it is written, so a
# subset does not overwrite the report for everything.
empty           :=
space           := $(empty) $(empty)

ifeq ($(filter command line,$(origin BENCHES)),)
TITLE           ?= AVL Benchmark Results
OUTPUT          ?= results
else
TITLE           ?= AVL Benchmarks - $(BENCHES)
OUTPUT          ?= results/$(subst /,-,$(subst $(space),-,$(strip $(BENCHES))))
endif

PYTHON    ?= python3

# Each benchmark is reported on collectively here, so they do not report singly.
BENCH_VARS = BENCH_REPORT=0 \
             $(if $(SIM),SIM=$(SIM)) \
             $(if $(ITERATIONS),ITERATIONS=$(ITERATIONS)) \
             $(if $(REPEATS),REPEATS=$(REPEATS)) \
             $(if $(SEED),SEED=$(SEED)) \
             $(if $(BURST),BURST=$(BURST))

.DEFAULT_GOAL := bench

# Benchmarks must not run against each other.
.NOTPARALLEL:

%bench: %Makefile
	$(MAKE) --no-print-directory -C $(dir $<) bench $(BENCH_VARS)

%clean: %Makefile
	$(MAKE) --no-print-directory -C $(dir $<) clean > /dev/null 2>&1

%quality: %Makefile
	$(MAKE) --no-print-directory -C $(dir $<) quality $(BENCH_VARS)

.PHONY: list
list: $(BENCH_MAKEFILES)
	$(foreach dep, $^, echo $(dir $(dep));)

.PHONY: bench
bench: $(patsubst %/Makefile,%/bench,$(BENCH_MAKEFILES))
	$(MAKE) --no-print-directory report

.PHONY: quality
quality: $(patsubst %/Makefile,%/quality,$(BENCH_MAKEFILES))

# Each report lists every report of the run, so that any one of them is a way in
# to the rest. The one being written is given an empty link - listed, but not
# linked to itself - and the paths are relative, so the whole output directory
# can be copied or published as it stands.
COMBINED         = All benchmarks
links_from       = $(foreach g,$(GROUP_REPORTS),\
                     "$(g)=$(if $(filter $(g),$(1)),,$(if $(1),../)$(g)/report.html)")

.PHONY: report
report:
	$(if $(MISSING),echo "No results for $(words $(MISSING)) of $(words $(BENCH_MAKEFILES)) benchmarks - reporting on the rest. Missing:"; $(foreach b,$(MISSING),echo "  $(b)";))
	$(PYTHON) scripts/bench_report.py $(wildcard $(RESULTS)) \
	  --title "$(TITLE)" --output $(OUTPUT) \
	  --quality $(QUALITY) \
	  $(if $(GROUP_REPORTS),--related "$(COMBINED)=" $(call links_from,))
	$(foreach g,$(GROUP_REPORTS), \
	  $(PYTHON) scripts/bench_report.py $(wildcard $(call results_in,$(g))) \
	    --title "AVL Benchmarks - $(g)" --output $(OUTPUT)/$(g) --quiet \
	    --quality $(call quality_in,$(g)) \
	    --related "$(COMBINED)=../report.html" $(call links_from,$(g)) || exit 1;)

.PHONY: clean
clean: $(patsubst %/Makefile,%/clean,$(BENCH_MAKEFILES))
	rm -rf $(OUTPUT) scripts/__pycache__
	echo "Clean complete"
