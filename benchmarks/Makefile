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

.PHONY: report
report:
	$(PYTHON) scripts/bench_report.py $(wildcard $(RESULTS)) \
	  --title "$(TITLE)" --output $(OUTPUT) \
	  --quality $(QUALITY)

.PHONY: clean
clean: $(patsubst %/Makefile,%/clean,$(BENCH_MAKEFILES))
	rm -rf $(OUTPUT) scripts/__pycache__
	echo "Clean complete"
