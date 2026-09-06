# AVL Benchmarks

Performance benchmarks for the Apheleia Verification Library.

Set the environment up from the repository root first — every benchmark assumes
it:

```bash
source ./avl.sh
```

All benchmarks run on Verilator.

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
