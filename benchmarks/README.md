# AVL Benchmarks

Performance benchmarks for the Apheleia Verification Library.

Set the environment up from the repository root first — every benchmark assumes
it:

```bash
source ./avl.sh
```

All benchmarks run on Verilator.

## Cleaning up

```bash
cd benchmarks
make list        # what is here, and how each one is driven
make clean       # simulator build directories, working copies, stray output
make distclean   # everything, including the results
```

`clean` leaves each benchmark's `results/` directory alone, so recorded runs and
write-ups survive it.

`distclean` removes them, along with the virtual environments the scripted
benchmarks build — the released `avl-core` that `examples` and `comparison`
compare against, and the pyuvm and pyvsc installation `comparison` measures.
`results/` is not tracked by git, so a `distclean` is the end of any recorded run
and any write-up in there — take a copy first if you want to keep one. The
environments cost a download and an install to recreate.

## startup

Measures how long it takes to start an AVL testbench, and how much of that is
AVL rather than cocotb and the simulator.

```bash
cd benchmarks/startup
./startup_benchmark.py             # 3 iterations (default)
./startup_benchmark.py -n 15       # 15 iterations
```

Four quantities are measured, each in a fresh process, `N` times:

| measurement | what it is |
| --- | --- |
| `import avl (clean interpreter)` | `import avl` from a cold interpreter, including cocotb |
| `import avl (cocotb preloaded)` | `import avl` with cocotb already loaded, timed inside the child process. This is the shape a real simulation has, and it isolates AVL's own cost. It is by far the least noisy of the four. |
| `bare cocotb testbench` | a full Verilator run of [`cocotb/baseline.py`](startup/cocotb/baseline.py) — a testbench with an empty `cocotb.test` |
| `AVL testbench (standard env)` | a full Verilator run of [`cocotb/benchmark.py`](startup/cocotb/benchmark.py) — the same thing built as a standard `avl.Env` with no content |

The headline figure, **AVL start-up overhead**, is the difference between the last
two: everything AVL costs to start, with `make`, the simulator and cocotb
cancelled out. The DUT is compiled once before timing starts, so no sample
includes Verilator compilation.

### Recording and comparing runs

```bash
./startup_benchmark.py -n 15 --json results/base.json --label base
# ... change something in avl/ ...
./startup_benchmark.py -n 15 --json results/new.json --label new --compare results/base.json
```

`--compare` prints a before/after table for every measurement plus the overhead.

### Interpreting the numbers

The two full-simulation measurements carry roughly ±100 ms of run-to-run noise
on a typical machine, so the overhead figure is only meaningful when it is large
compared to that. Use `import avl (cocotb preloaded)` for fine-grained work: its
standard deviation is a few milliseconds. Raise `-n` if the reported standard
deviation is close to the difference you are trying to measure.

`results/` is not tracked by git. It holds the recorded runs, and
`startup/results/RESULTS.md` — the write-up of the start-up optimisation work this
benchmark was written for.

## objects

Measures how long it takes to construct AVL objects and variables — the cost paid
once per transaction, and so paid over and over by any real testbench.

```bash
cd benchmarks/objects
./object_benchmark.py                    # 1000 objects, 3 repeats (default)
./object_benchmark.py -n 5000 -r 7
```

The testbench ([`cocotb/benchmark.py`](objects/cocotb/benchmark.py)) builds `N` of
each measurement inside a real simulation and times each loop in-process, so
`make`, the simulator and the import cost are not part of any sample. It cycles
through four different transaction classes, so per-class caching in AVL has to
work for varied classes rather than for one class built over and over.

| measurement | what it is |
| --- | --- |
| `avl.Object` / `avl.Transaction` | the bare base objects, with no variables |
| `avl.Logic` … `avl.Fp32` | a single variable of each type |
| `transaction, 6 variables` | one transaction carrying one of each type — the headline figure |
| `4 classes, round-robin` | four different transaction classes in turn |

All figures are microseconds per object. `--json`, `--label` and `--compare` work
the same way as the start-up benchmark.

See `objects/results/RESULTS.md` for the results of the object creation
optimisation work.

## randomization

Measures how long it takes to randomize a constrained transaction — the most
expensive thing a testbench asks AVL to do, and something a sequence does once per
item.

```bash
cd benchmarks/randomization
./randomization_benchmark.py                     # 1000 randomizations, 3 repeats
./randomization_benchmark.py -n 200 -r 5
```

The testbench ([`cocotb/benchmark.py`](randomization/cocotb/benchmark.py)) builds
each packet once and randomizes it `N` times, timing the loop in-process.

| measurement | what it is |
| --- | --- |
| `constrained packet` | logic, uint, int, enum and float fields under arithmetic, bitwise and select constraints, their ranges left wide — the headline figure |
| `tightly constrained packet` | the same variable types held to narrow ranges, as a real testbench holds them |
| `integer fields only` | the same shape without the floating point variable |
| `no constraints` | the same variables with no constraints, the floor |
| `new object each time` | a new packet built and randomized each time, as a sequence generating items would |
| `single variable` | one variable randomized on its own |

All figures are microseconds per randomization.

A constrained randomization costs tens of milliseconds, so the default `-n 1000`
takes a while — use `-n 200` while iterating.

**On reading the numbers.** The scenarios run once each, in order, in a separate
process, so comparing two saved runs carries both measurement noise and machine
drift; the spread on the constrained packet is around 5 %. It resolves changes of
20 % and up cleanly. To settle anything smaller, A/B the two code paths inside one
process with the rounds interleaved.

See `randomization/results/RESULTS.md` for the results of the randomization
optimisation work.

## logging

Measures what it costs to write a log message — the one thing a testbench does on
every interesting line, so its cost is spread across everything else.

```bash
cd benchmarks/logging
./logging_benchmark.py                     # 2000 messages, 3 repeats
./logging_benchmark.py -n 5000 -r 5
```

| measurement | what it is |
| --- | --- |
| `info from a component` | one INFO message, no log file — the headline figure |
| `info, six deep hierarchy` | the same from six levels down, where the group name costs more to build and the record reaches more handlers |
| `below the level` | a DEBUG message, filtered out, which should cost almost nothing |
| `formatted message` | an INFO message built from an f-string, as most real ones are |
| `avl.Log directly` | through `avl.Log`, without a component to name the group |
| `to a .csv/.json/.txt log file` | with a log file set, in each of three formats |

All figures are microseconds per message.

Each measurement starts from a clean log state, and the file measurements flush
once before timing — the log accumulates globally, and the first flush of a format
imports pandas, so without both the numbers describe the order the measurements
ran in rather than the thing being measured.

See `logging/results/RESULTS.md` for the results of the logging optimisation work.

## comparison

Measures the same thing as `randomization` — the cost of creating, constraining
and randomizing an item — but against the alternatives rather than against a
previous version of AVL. Four implementations of one workload are compared:
the AVL in this repository, the latest released `avl-core` from PyPI, pyuvm with
pyvsc, and SystemVerilog classes solved by the simulator.

```bash
cd benchmarks/comparison
./comparison_benchmark.py --dry-run   # show the plan, run nothing
./comparison_benchmark.py             # 16 classes, 256 items, 3 repeats each
./comparison_benchmark.py -N 1,4,16 -r 5
```

This is the long one: it builds two virtual environments the first time it runs,
and compiles a model per flavour. Both are reused afterwards, and neither is part
of any measurement, but a first run takes a few minutes before it starts timing
anything.

| flavour | what it is |
| --- | --- |
| `sv` | SystemVerilog classes, randomized by the simulator's own constraint solver |
| `pyuvm` | pyvsc `randobj`s, randomized from the `run_phase` of a `pyuvm` test |
| `avl-<version>` | the latest released `avl-core` from PyPI, under the version it is |
| `avl` | the AVL in this repository |

The workload is sixteen classes, each declaring four unsigned logic vectors and
two signed integers under eleven arithmetic, bitwise and related constraints, and
each written with different constants — so no implementation can analyse one
class and reuse the answer for the rest, which is the position a testbench
declaring one sequence item per bus is in. They are ordinary source, one file per
flavour: [`rtl/classes.svh`](comparison/rtl/classes.svh),
[`cocotb/classes_avl.py`](comparison/cocotb/classes_avl.py) and
[`cocotb/classes_pyuvm.py`](comparison/cocotb/classes_pyuvm.py).

Every flavour compiles the same RTL, runs through the same cocotb flow and does
one item per clock edge. Two figures are reported for each: the total run time of
the simulation, which is what a user waits for, and the randomization on its own,
which is that with a run of the same testbench with the randomization disabled
subtracted from it. The second is in microseconds per item.

The benchmark installs what it needs itself: the released `avl-core` and pyuvm
with pyvsc each go into a virtual environment of their own inside
`benchmarks/comparison/`, with `cocotb` pinned to the version the local
environment uses. Nothing in the repository depends on pyuvm.

Reports are written to `comparison/results/` on every run — `report.html`,
`RESULTS.md`, `summary.csv` and `results.json` — each carrying the machine, the
simulator and the version of all four things compared.

See [`comparison/README.md`](comparison/README.md) for the workload, the
measurement and the options in full.
