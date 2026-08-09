# AVL Benchmarks

A framework for comparing AVL randomization against SystemVerilog randomization, and recording
how long each one takes.

The two are compared like with like. Every flavour of a benchmark compiles the **same RTL** and
runs the **same cocotb testbench**, which generates clock and reset and randomizes once per
rising edge. The only difference is where the randomization happens:

| Flavour | Randomized by | Solved by |
|---------|---------------|-----------|
| `sv`    | SystemVerilog classes and constraints, inside the RTL | the simulator |
| `avl`   | the identical object in the cocotb testbench          | AVL |

That difference is the only thing under an `` `ifdef `` in the RTL, and the only branch in the
testbench. The simulator, the elaboration, the clock, the reset and the loop are common, so what
is left in the measurement is the constraint solver.

---

## The benchmarks

Each one isolates a single category of randomization.

| Benchmark | Category | Cross variable constraints |
|-----------|----------|----------------------------|
| [randomization/urandom](randomization/urandom) | `$urandom` / `$urandom_range` against `avl.urandom_range` - no solver on either side | none |
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
| `SEED`       | `1`         | Random seed, applied to both flavours                            |
| `BURST`      | `1`         | Randomizations per clock edge                                    |
| `SIM`        | `verilator` | Any simulator cocotb supports - `verilator`, `questa`, `vcs`, `xcelium`, ... |

A benchmark may override `ITERATIONS` and `BURST` in its own `bench.conf`, because the
categories differ enormously in cost - a `$urandom` is several thousand times cheaper than
solving a set of arithmetic constraints. Anything given on the command line still wins.

`BURST` exists for the categories where a single randomization is cheaper than advancing the
clock, which costs about 8 us an edge. It stays at one - one randomization per positive edge -
everywhere except `urandom`.

Both flavours are built and run through cocotb's makefiles, exactly as the examples are, so
changing `SIM` changes it for both and the comparison stays honest.

Verilator solves SystemVerilog constraints with an external SMT solver (`z3 --in` by default,
overridable with `VERILATOR_SOLVER`) and must be able to find it on `PATH` - the AVL virtual
environment provides one, so `source avl.sh` before running.

---

## Reports

`make bench` prints the results and writes them to `results/`:

| File           | Contents                                                        |
|----------------|-----------------------------------------------------------------|
| `report.html`  | Self contained page - tables plus charts comparing the flavours |
| `summary.csv`  | The cost of randomization, one row per benchmark and flavour     |
| `summary.md`   | The same tables in markdown                                      |

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
│   ├── bench_report.py   # report generator
│   └── bench_html.py     # HTML report
└── randomization/
    └── mixed/
        ├── Makefile      -> ../../bench.mk
        ├── bench.conf        # optional per benchmark ITERATIONS / BURST
        ├── rtl/mixed.sv      # shared by both flavours
        ├── cocotb/mixed.py   # shared by both flavours
        ├── sv/Makefile   -> ../../../flavour.mk
        └── avl/Makefile  -> ../../../flavour.mk
```

A flavour directory holds nothing but the symlink - the sources live in the benchmark, because
both flavours use the same ones. The flavour is taken from the directory name.

### Adding a benchmark

```sh
mkdir -p mygroup/mybench/rtl mygroup/mybench/cocotb mygroup/mybench/sv mygroup/mybench/avl
ln -s ../../bench.mk      mygroup/mybench/Makefile
ln -s ../../../flavour.mk mygroup/mybench/sv/Makefile
ln -s ../../../flavour.mk mygroup/mybench/avl/Makefile
```

Sources are found by convention:

| What                | Where                        | Requirement                                      |
|---------------------|------------------------------|--------------------------------------------------|
| RTL                 | `<benchmark>/rtl/*.sv`       | toplevel module `<benchmark>_bench (clk, rst_n)` |
| cocotb testbench    | `<benchmark>/cocotb/<benchmark>.py` | a `@cocotb.test`                          |

The testbench must honour these controls, so that the same sources serve both flavours and both
measurement phases:

| Control              | Read by        | Meaning                                            |
|----------------------|----------------|----------------------------------------------------|
| `BENCH_SV_RANDOMIZE` | RTL, `` `ifdef `` | Randomize in SystemVerilog - defined for `sv` only |
| `BENCH_FLAVOUR`      | Python, environment | `sv` or `avl`                                 |
| `BENCH_ITERATIONS`   | Python, environment | Randomizations to perform                     |
| `BENCH_BURST`        | Python, environment, and `+burst=` plusarg in RTL | Randomizations per clock edge |
| `BENCH_RANDOMIZE`    | Python, environment, and `+randomize=` plusarg in RTL | Randomize, or run the harness alone for the baseline |

Any other subdirectory containing a `Makefile` is picked up as a further flavour, so a third
implementation can be dropped in beside `sv` and `avl` without changing the framework.

---

## How the measurement works

Each testbench is compiled first, outside the measurement, then run once untimed to warm the file
cache. It is then measured twice, driving the **same number of clock cycles** each time:

- **baseline** - randomization disabled. Captures everything that is not randomization: process
  startup, elaboration, the Python interpreter, cocotb bringup, and the cost of the loop itself.
- **run** - randomization enabled.

The report subtracts the two. Because the harness is identical, the two flavours' baselines come
out within a few percent of each other, and what is left is the solver. The `relative` column is
the cost per randomization against the fastest flavour of that benchmark.

### CPU accounting

Timing is process *tree* aware. A SystemVerilog simulator solves constraints in a separate SMT
solver process which it never reaps, so `/usr/bin/time` and `getrusage()` attribute none of that
solver's CPU time to the simulator - the SystemVerilog flavour appears to use no CPU at all.
`bench_time.py` therefore samples `/proc/<pid>/stat` for every process in the run's process group
as well as calling `getrusage()`, and reports the larger of the two. CPU usage above 100% is real:
both solvers use more than one core.

Benchmarks, flavours and repeats are always run serially, never in parallel, so that runs do not
compete for cores.
