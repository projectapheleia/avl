# examples benchmark

Measures the runtime of every example in [`examples/`](../../examples) against
the released `avl-core` of the same version number, and reports the relative
performance difference per example.

```bash
source ./avl.sh                    # from the repository root
cd benchmarks/examples
./examples_benchmark.py --dry-run  # show the plan, run nothing
./examples_benchmark.py            # 3 timed runs per example, per variant
```

Two variants are timed:

| variant | what it is |
| --- | --- |
| `released` | `avl-core==<version from pyproject.toml>` installed from PyPI into `.venv-released-<version>/` |
| `local` | the AVL in this repository - the editable install `avl.sh` puts in `./venv` |

`cocotb`, `z3-solver`, `pandas`, `numpy` and `matplotlib` are installed in the
released environment at the versions the local environment uses, so AVL is the
only difference between the variants. That list covers more than avl-core's own
dependencies on purpose: `matplotlib` ships only in this repository's `[dev]`
extra, so an environment built from the released wheel alone cannot even import
the testbenches of `constraints/distribution` and `constraints/performance`, and
those examples would be reported as failures that have nothing to do with AVL.
`--pin PKG` changes what is installed and pinned; `--no-pin` installs nothing
extra and lets pip resolve avl-core's dependencies freely, which will skip any
example importing a package the released wheel does not require.

Add to `--pin` if an example ever grows a new third-party import.

Each example is copied into a private work tree per variant under `work/`, so
neither variant writes into `examples/` and neither can invalidate the other's
`sim_build`. Every example is run `--warmup` times untimed first, which compiles
the DUT, so no timed sample includes Verilator compilation. Timed runs then
alternate `released`/`local` per iteration, so drift in machine load does not
systematically favour either.

Every run in both variants is given the same `COCOTB_RANDOM_SEED` (`--seed`,
default 1). cocotb otherwise seeds Python's RNG from the wall clock, which has
two consequences worth avoiding: the two variants randomize differently and so
do not solve the same problems, and examples whose outcome depends on the draw -
`sequences/sequence_of_sequences`, whose sub-sequence delays and sequencer
arbitration are both random - fail intermittently. `--no-seed` restores cocotb's
own behaviour, which is what a normal example run does.

A run counts as passing exactly as `examples/Makefile` counts it: `make sim`
exits cleanly and `results.xml` contains no `failure message=`. An example that
fails in either variant - a new example the released version cannot run, for
instance - is reported under *not compared* rather than aborting the benchmark.

### Useful options

```bash
./examples_benchmark.py -n 7                      # 7 timed runs per variant
./examples_benchmark.py --only 'constraints/*'    # a subset (repeatable)
./examples_benchmark.py --skip 'visualization/*'  # exclude a subset
./examples_benchmark.py --released-version 1.0.0  # compare against another release
./examples_benchmark.py --no-trace                # drop VCD writing from every sample
./examples_benchmark.py --rebuild-env             # rebuild the released venv
./examples_benchmark.py --json results/run.json --markdown results/RESULTS.md
```

An example reported as *incomplete* rather than *skipped* built and passed its
warm-up but then failed a timed run - almost always the flakiness above.

`--no-trace` overrides the `EXTRA_ARGS` that [`examples/sim.mk`](../../examples/sim.mk)
uses to turn on Verilator waveform tracing. It applies to both variants, so the
comparison stays fair, but the absolute times are then no longer what running
the examples normally costs.

### Reading the report

Times are the mean wall time of a full `make sim`, in seconds. A negative change
and a speedup above `1.00x` mean the local AVL is faster. An example marked `~`
(`*` in the markdown report) has a difference smaller than twice its own
run-to-run standard deviation - raise `-n` to resolve it. The totals row divides
summed released time by summed local time, so it is weighted by how long each
example takes; the geometric mean speedup weights every example equally.

`work/`, `.venv-released-*/` and `results/` are not tracked by git.
