#Copyright 2024 Apheleia
#
#Description:
# Apheleia Verification Library (AVL) Benchmarks
#
# Runs every benchmark in the tree and reports the results side by side.
#
#   make bench                  run everything with the default settings
#   make bench ITERATIONS=5000  randomize 5000 times per run
#   make bench REPEATS=5        run each testbench 5 times, report the median
#   make -C randomization/basic run one benchmark on its own
#   make report                 re-print the report without re-running
#   make clean

.SILENT:

# A benchmark is any directory whose Makefile is a symlink to bench.mk.
# Note this must not be called MAKEFILES - that is a special variable which make
# would then try to read as makefiles, in this and in every sub-make.
BENCH_MAKEFILES := $(shell find */* -type l -name Makefile -lname '*bench.mk')
BENCHES         := $(patsubst %/Makefile,%,$(BENCH_MAKEFILES))
RESULTS         := $(patsubst %/Makefile,%/results.csv,$(BENCH_MAKEFILES))
# Left as a glob for the shell to expand when the report runs - make's own
# wildcard caches the directory from before the runs wrote anything.
QUALITY         := $(patsubst %/Makefile,%/*/quality.csv,$(BENCH_MAKEFILES))

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
	$(PYTHON) scripts/bench_report.py $(wildcard $(RESULTS)) --output results \
	  --quality $(QUALITY)

.PHONY: clean
clean: $(patsubst %/Makefile,%/clean,$(BENCH_MAKEFILES))
	rm -rf results scripts/__pycache__
	echo "Clean complete"
