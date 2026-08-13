# AVL Benchmarks

A framework for comparing AVL randomization against SystemVerilog randomization and against
pyuvm with pyvsc, and recording how long each one takes.

They are compared like with like. Every flavour of a benchmark compiles the **same RTL** and runs
the **same harness**, which generates clock and reset and, on each rising edge, builds a fresh item
and randomizes it once. The only difference is where the randomization happens:

| Flavour | Randomized by | Solved by |
|---------|---------------|-----------|
| `sv`    | SystemVerilog classes and constraints, inside the RTL | the simulator |
| `avl`   | the identical object in the cocotb testbench          | AVL |
| `pyuvm` | the identical object as a pyvsc `randobj`, from the `run_phase` of a pyuvm test | pyvsc |

That difference is the only thing under an `` `ifdef `` in the RTL, and the only branch in the
testbench. The simulator, the elaboration, the clock, the reset and the loop are common, so what
is left in the measurement is the constraint solver.

`sv` and `avl` share one testbench, because the loop is identical and only the randomization sits
behind an `if`. `pyuvm` needs its own, `cocotb/<benchmark>_pyuvm.py`, because the loop has to live
inside a `uvm_test` - but it drives the same clock, the same reset, the same number of edges and
the same checks.

---

## The benchmarks

Each one isolates a single category of randomization.

| Benchmark | Category | Cross variable constraints |
|-----------|----------|----------------------------|
| [randomization/arithmetic](randomization/arithmetic) | relational operators and addition | none |
| [randomization/bitwise](randomization/bitwise) | and, or, xor, shift, bit select | none |
| [randomization/list](randomization/list) | set membership - `inside` | none |
| [randomization/implication](randomization/implication) | `->` and if / else dependencies | yes, that is the category |
| [randomization/cross](randomization/cross) | arithmetic, bitwise and list constraints that depend on each other | yes, that is the category |
| [randomization/mixed](randomization/mixed) | the widest spread of constructs, on a bus-transaction shaped item | yes |

Apart from `implication`, `cross` and `mixed`, every constraint controls a single variable, so
each category measures its own construct and nothing else.

---

## Running

```sh
# Everything
make bench

# One benchmark
make -C randomization/mixed

# More randomizations per run, more runs per testbench
make bench ITERATIONS=5000 REPEATS=5

# Another simulator
make bench SIM=questa

# Re-print the report without re-running anything
make report

make clean
```

### Options

| Variable     | Default     | Description                                                     |
|--------------|-------------|-----------------------------------------------------------------|
| `ITERATIONS` | `1000`      | Randomizations - and clock cycles - per run of a testbench       |
| `REPEATS`    | `3`         | Runs of each testbench - the report uses the median              |
| `SEED`       | `1`         | Random seed, applied to every flavour                            |
| `BURST`      | `1`         | Randomizations per clock edge                                    |
| `QUALITY_ITERATIONS` | `1000` | Draws recorded by the quality run - see below            |
| `QUALITY_CHECK` | `avl`    | Flavours whose randomization quality must meet the thresholds, or `none` |
| `SIM`        | `verilator` | Any simulator cocotb supports - `verilator`, `questa`, `vcs`, `xcelium`, ... |

A benchmark may override `ITERATIONS` and `BURST` in its own `bench.conf`, because the categories
differ in cost - a set of independent range constraints solves far faster than four variables that
have to be solved together. Either may also be set for a single flavour, as `ITERATIONS_<flavour>`
and `BURST_<flavour>`, for a flavour whose cost is out of proportion to the rest and which would
otherwise dominate the run. Everything the report compares is a time *per* randomization, so the
counts do not have to match. Anything given on the command line still wins, for every flavour.

`BURST` exists for the case where a single randomization is cheaper than advancing the clock, which
costs about 8 us an edge. Every category here is far dearer than that, so it stays at one - one
randomization per positive edge - throughout.

Every flavour is built and run through cocotb's makefiles, exactly as the examples are, so
changing `SIM` changes it for all of them and the comparison stays honest.

Verilator solves SystemVerilog constraints with an external SMT solver (`z3 --in` by default,
overridable with `VERILATOR_SOLVER`) and must be able to find it on `PATH` - the AVL virtual
environment provides one, so `source avl.sh` before running.

The `pyuvm` flavour needs `pyuvm` and `pyvsc`, both of which are development dependencies of AVL
and so are installed by `avl.sh` alongside everything else.

---

## Reports

`make bench` prints the results and writes them to `results/`:

| File           | Contents                                                        |
|----------------|-----------------------------------------------------------------|
| `report.html`  | Self contained page - AVL against SystemVerilog and against pyuvm / pyvsc side by side at the top, then randomization quality, then tables and per benchmark charts |
| `summary.csv`  | The cost of randomization, one row per benchmark and flavour     |
| `summary.md`   | The same tables in markdown                                      |
| `quality.csv`  | Spread of the values drawn, one row per benchmark, flavour and field |

Raw per-run rows are kept in each benchmark's `results.csv`. A single benchmark run writes its
own `results/` in the same way.

---

## Layout

```
benchmarks/
├── Makefile              # runs every benchmark, aggregates the report
├── bench.mk              # per benchmark driver, symlinked in as <benchmark>/Makefile
├── flavour.mk            # per flavour driver, symlinked in as <benchmark>/<flavour>/Makefile
├── common.mk             # settings shared by the flavours
├── scripts/
│   ├── bench_time.py     # timing harness
│   ├── bench_dump.py     # records drawn values, shared by the testbenches
│   ├── bench_quality.py  # measures the spread of those values
│   ├── bench_report.py   # report generator
│   └── bench_html.py     # HTML report
└── randomization/
    └── mixed/
        ├── Makefile             -> ../../bench.mk
        ├── bench.conf               # optional per benchmark ITERATIONS / BURST
        ├── rtl/mixed.sv             # shared by every flavour
        ├── cocotb/mixed.py          # shared by sv and avl
        ├── cocotb/mixed_pyuvm.py    # the pyuvm / pyvsc testbench
        ├── sv/Makefile          -> ../../../flavour.mk
        ├── avl/Makefile         -> ../../../flavour.mk
        └── pyuvm/Makefile       -> ../../../flavour.mk
```

A flavour directory holds nothing but the symlink - the sources live in the benchmark, because the
flavours share them. The flavour is taken from the directory name.

### Adding a benchmark

```sh
mkdir -p mygroup/mybench/{rtl,cocotb,sv,avl,pyuvm}
ln -s ../../bench.mk      mygroup/mybench/Makefile
ln -s ../../../flavour.mk mygroup/mybench/sv/Makefile
ln -s ../../../flavour.mk mygroup/mybench/avl/Makefile
ln -s ../../../flavour.mk mygroup/mybench/pyuvm/Makefile
```

Sources are found by convention:

| What                | Where                        | Requirement                                      |
|---------------------|------------------------------|--------------------------------------------------|
| RTL                 | `<benchmark>/rtl/*.sv`       | toplevel module `<benchmark>_bench (clk, rst_n)` |
| cocotb testbench    | `<benchmark>/cocotb/<benchmark>.py` | a `@cocotb.test`                          |
| pyuvm testbench     | `<benchmark>/cocotb/<benchmark>_pyuvm.py` | a `@cocotb.test` running a `uvm_test` |

A testbench must honour these controls, so that the same sources serve every flavour and both
measurement phases:

| Control              | Read by        | Meaning                                            |
|----------------------|----------------|----------------------------------------------------|
| `BENCH_SV_RANDOMIZE` | RTL, `` `ifdef `` | Randomize in SystemVerilog - defined for `sv` only |
| `BENCH_FLAVOUR`      | Python, environment | `sv`, `avl` or `pyuvm`                        |
| `BENCH_ITERATIONS`   | Python, environment | Randomizations to perform                     |
| `BENCH_BURST`        | Python, environment, and `+burst=` plusarg in RTL | Randomizations per clock edge |
| `BENCH_RANDOMIZE`    | Python, environment, and `+randomize=` plusarg in RTL | Randomize, or run the harness alone for the baseline |
| `BENCH_DUMP`         | Python, environment, and `+dump=` plusarg in RTL | File to record every drawn value in, for the quality measurement. Set only for the quality run |

`BENCH_FLAVOUR` is what the shared testbench branches on; the pyuvm one has a module to itself and
does not need it. Any other subdirectory containing a `Makefile` is picked up as a further flavour,
so a fourth implementation can be dropped in beside `sv`, `avl` and `pyuvm` without changing the
framework - it runs `cocotb/<benchmark>.py` unless `flavour.mk` says otherwise.

---

## How the measurement works

### A fresh item per randomization

Every flavour builds a **new object for each randomization** rather than randomizing one object
over and over. That is what a testbench actually does - a sequence item per transaction - and it is
what keeps the measurement honest. An object randomized repeatedly lets an implementation amortize
setup across draws: hold a solver open, keep its constraint expressions, analyse the constraints
once and reuse the answer. None of that is available to a testbench that discards the item every
time, so a benchmark that reused one item would reward work that real code never gets the benefit
of.

### Quality of randomization

Speed on its own is a misleading number, because randomization can be made a great deal faster by
giving up distribution - exploring a narrower set of values, or leaving the bits a constraint does
not pin at whatever the solver reaches for first. Nothing in a timing measurement notices. So each
flavour also gets an **untimed quality run** which records every value it draws, and
[scripts/bench_quality.py](scripts/bench_quality.py) measures the spread:

| Metric | Meaning |
|---|---|
| `distinct`  | Distinct values drawn, over the number of draws. Cheap to read, but blind to how evenly they were spread |
| `entropy`   | Spread of the values drawn, normalised so `1.00` is flat across every value any flavour managed for that field. Scale free, so a field with sixteen legal values compares with one with sixteen million |
| `bit skew`  | How far the flavour strays from what the others agree on for any one bit, ignoring bits the constraints pinned |

The check is based on **entropy**, because its normalisation already accounts for how many values
the constraints allow: a uniform draw scores `1.00` whatever shape its constraints are. Checking
each bit against a half-and-half split would be wrong here - `a inside {1, 2, 4 ... 32768}`
legitimately leaves every bit set only one time in sixteen.

`bit skew` is reported but not failed on by default. With only three flavours a median is not a
robust centre, so when one of them is badly spread the skew can land on whichever well behaved
flavour sits further from the outlier. Treat it as a pointer to a field worth looking at, and raise
`--bit-skew-ceiling` if you want it enforced too.

Neither metric can see a bias that every flavour shares.

The quality run is deliberately separate from the timed ones - the values have to be written
somewhere, and that must not be measured as randomization cost. It runs last, so it cannot perturb
them either.

```sh
make quality                        # just the quality runs and the check
make quality QUALITY_CHECK=all      # hold every flavour to the thresholds
make quality QUALITY_CHECK=none     # measure without failing
```

### Baseline and run

Each testbench is compiled first, outside the measurement, then run once untimed to warm the file
cache. It is then measured twice, driving the **same number of clock cycles** each time:

- **baseline** - randomization disabled. Captures everything that is not randomization: process
  startup, elaboration, the Python interpreter, cocotb bringup, and the cost of the loop itself.
- **run** - randomization enabled.

The report subtracts the two. Because the harness is identical, the flavours' baselines come out
within a few percent of each other - the `pyuvm` one a little higher, since it pays for pyuvm's
bringup and phasing, which the subtraction then removes - and what is left is the solver. The
`relative` column is the cost per randomization against the fastest flavour of that benchmark.

### CPU accounting

Timing is process *tree* aware. A SystemVerilog simulator solves constraints in a separate SMT
solver process which it never reaps, so `/usr/bin/time` and `getrusage()` attribute none of that
solver's CPU time to the simulator - the SystemVerilog flavour appears to use no CPU at all.
`bench_time.py` therefore samples every process in the run's process group as well as calling
`getrusage()`, and reports the larger of the two. CPU usage above 100% is real: the solvers use
more than one core.

Sampling a process group has no portable interface, so there is one sampler per platform - Linux
reads `/proc/<pid>/stat`, macOS asks `libproc`, and both are checked against a known workload the
same way. On any other platform the benchmarks still run and are still timed, but on `getrusage()`
alone, which means an unreaped solver process goes uncounted and the `sv` flavour will understate
its CPU.

Benchmarks, flavours and repeats are always run serially, never in parallel, so that runs do not
compete for cores.
