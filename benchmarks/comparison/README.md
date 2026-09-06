# comparison benchmark

Measures what it costs to create, constrain and randomize an item, and compares
four implementations of the same workload:

| flavour | what it is |
| --- | --- |
| `sv` | SystemVerilog classes, randomized by the simulator's own constraint solver |
| `pyuvm` | pyvsc `randobj`s, randomized from the `run_phase` of a `pyuvm` test |
| `avl-<version>` | the latest released `avl-core` from PyPI, reported under the version it is - `avl-1.0.1`, say |
| `avl` | the AVL in this repository - the editable install `avl.sh` puts in `./venv` |

Two figures are reported for each of them: the **total run time** of the
simulation, which is what a user waits for, and the **randomization** on its own,
which is that with a run of the same testbench with the randomization disabled
subtracted from it.

```bash
source ./avl.sh                       # from the repository root
cd benchmarks/comparison
./comparison_benchmark.py --dry-run   # show the plan, run nothing
./comparison_benchmark.py             # 16 classes, 256 items, 3 repeats each
```

The first run installs what the other environments need - it downloads and
installs `avl-core`, `pyuvm` and `pyvsc` - and compiles a model per flavour, so
it takes a few minutes longer than the ones after it. Both are reused
afterwards.

## The workload

Sixteen classes, written out in each of the three languages the benchmark
compares:

| flavour | the classes |
| --- | --- |
| `sv` | [`rtl/classes.svh`](rtl/classes.svh) |
| `avl`, `avl-<version>` | [`cocotb/classes_avl.py`](cocotb/classes_avl.py) |
| `pyuvm` | [`cocotb/classes_pyuvm.py`](cocotb/classes_pyuvm.py) |

Every class declares the same representative set of variables:

| variable | type | width |
| --- | --- | ---: |
| `addr` | unsigned logic | 32 |
| `len` | unsigned logic | 16 |
| `mask` | unsigned logic | 8 |
| `kind` | unsigned logic | 8 |
| `delta` | signed integer | 16 |
| `level` | signed integer | 16 |

under eleven constraints, chosen to cover what constrained random code actually
uses rather than any one construct:

| constraint | category | what it says |
| --- | --- | --- |
| `c_addr` | arithmetic | `addr` lies in this class's 16 MB window |
| `c_align` | arithmetic, modulo | `addr` is aligned to 4, 8 or 16 |
| `c_page` | bitwise, shift | `addr >> 24` is this class's page |
| `c_len` | arithmetic range | `1 <= len <= lmax` |
| `c_kind` | list | `kind` is one of four values |
| `c_mask` | bitwise, and | bits of `mask` held at zero |
| `c_mask_kind` | bitwise, xor, cross field | the low nibble of `mask` is tied to `kind` |
| `c_delta` | signed arithmetic | `-dmax <= delta <= dmax`, and not zero |
| `c_level` | signed arithmetic | `-vmax <= level <= vmax` |
| `c_sum` | signed arithmetic, cross field | `delta + level >= 0` |
| `c_kind0` | implication | one `kind` implies a single beat |

In all three languages the constraints are written once, in an `item_base`, and
each class is the constants it is written with - its page, its alignment, its
set of kinds, its bounds. That is how a testbench parameterizes one item type,
and it is why sixteen classes are sixteen short blocks rather than sixteen
copies of the same eleven constraints:

```systemverilog
class item_3 extends item_base;
    function new();
        low   = 32'h10000000; high  = 32'h10ffffff; page = 32'h10;
        align = 16; lmax = 16'd64;
        kind0 = 8'd14; kind1 = 8'd28; kind2 = 8'd44; kind3 = 8'd63;
        clear = 8'hc0; xr = 8'h0f;
        dmax  = 16'sd256; vmax = 16'sd128;
    endfunction
endclass : item_3
```

```python
class item_3(item_base):
    """page 0x10, aligned to 16, len <= 64, kinds {14, 28, 44, 63}, ..."""

    LOW, HIGH = 0x10000000, 0x10ffffff
    PAGE = 0x10
    ALIGN = 16
    LMAX = 64
    KINDS = (14, 28, 44, 63)
    CLEAR = 0xc0
    XOR = 0x0f
    DMAX = 256
    VMAX = 128
```

The sixteen are deliberately all different. An implementation may analyse a
class once and cache the answer, and a testbench declaring one sequence item per
bus never gets the benefit of that cache; distinct classes, each built fresh, is
the position real code is in. `-N` says how many of the sixteen take part, so
`-N 1,4,16` sweeps that.

Each item is checked against all eleven constraints after it is randomized, in
every flavour, so a flavour that draws an illegal value fails rather than being
reported as fast.

z3's bit vector comparisons, `%` and `>>` are signed by default, so the unsigned
forms the logic variables imply are spelled `UGE` / `ULE`, `URem` and `LShR` in
the AVL classes. pyvsc's `rand_bit_t` is unsigned and its `rand_int16_t` signed
already, and SystemVerilog takes its signedness from the declaration.

## How the measurement works

Every flavour compiles the same [RTL](rtl/comparison_bench.sv), is built and run
through cocotb's makefiles, and drives the same clock, the same reset and the
same number of edges, doing one item per rising edge. The only difference is who
does the work - the RTL under `` `ifdef BENCH_SV ``, or the testbench in
[`cocotb/`](cocotb).

Each flavour's model is compiled once, outside the measurement, and run once
untimed. It is then measured twice per repeat, over the same number of clock
cycles:

- **run** - the work under test enabled. This is the **total run time**:
  process startup, elaboration, cocotb bringup, the class definitions, the loop
  and the randomization, all of it.
- **baseline** - the same testbench over the same number of clock cycles with the
  randomization disabled.

The difference is the **randomization**, and `us/item` is that divided by the
items. The two phases are interleaved, so drift in machine load moves both
together. Baselines are not expected to agree between flavours - `pyuvm` pays for
pyuvm's bringup, the AVL flavours for importing z3 - only to be the same for a
flavour's own two phases, which is all the subtraction needs.

Both figures are worth having, and they do not always agree: a flavour can
randomize quickly and still lose on the run because of what it costs to start.

`cpu us/item` is the same subtraction over user + system time across the whole
process group. A SystemVerilog simulator solves constraints in a separate SMT
solver process which it never reaps, so that time is invisible to `getrusage()`
and to `/usr/bin/time`; it is sampled from `/proc` instead, and shows up only in
this column. CPU above 100 % is real - solvers use more than one core. On a
platform with no `/proc` the runs are still timed, but on `getrusage()` alone,
and the `sv` flavour then understates its CPU.

## Environments

Only the `avl` and `sv` flavours use the environment `avl.sh` sets up. The other
two are built by the benchmark, inside this directory, and reused until what they
were built from changes:

| directory | holds |
| --- | --- |
| `.venv-released-<version>/` | `avl-core` from PyPI, with `cocotb` and `z3-solver` pinned to the versions the local environment uses |
| `.venv-pyuvm/` | `pyuvm` and `pyvsc`, with `cocotb` pinned the same way |

pyuvm is installed here rather than alongside AVL on purpose: nothing in the
repository depends on it, and it belongs to this benchmark alone.

Pinning `cocotb` keeps the simulator interface identical everywhere, so what is
left between the flavours is the thing being compared. Repository paths are
stripped from `PYTHONPATH` for every flavour but the local one, and the run
fails rather than reporting a comparison if the released environment turns out
to resolve `avl` to the working copy.

`.venv-*/`, `work/` and `results/` are not tracked by git.

## Useful options

```bash
./comparison_benchmark.py -N 1,4,16                 # sweep how many classes take part
./comparison_benchmark.py -n 500                    # 500 items, classes taken in turn
./comparison_benchmark.py -r 5                      # five timed repeats
./comparison_benchmark.py --flavours avl,released   # just the two AVLs
./comparison_benchmark.py --released-version 1.0.0  # against another release
./comparison_benchmark.py --sim questa              # another simulator
./comparison_benchmark.py --rebuild-env             # rebuild both environments
./comparison_benchmark.py -o results/run-2 --label "after the solver change"
```

`--flavours` names them as the benchmark knows them, so the released AVL is
`released` there however it is reported.

`-N` is how many of the sixteen classes take part; `-n` is how many items are
built from them, taken in turn. `-n` defaults to one of each class and never
fewer than 256, because the randomization has to be comfortably larger than the
run-to-run spread of the phases it is subtracted from. Times are per item either
way, so the two can be set independently - and a fresh object is built for every
item, so a class built more than once amortizes nothing a real testbench would
not also amortize.

## The report

`results/` holds four files, rewritten by every run:

| file | contents |
| --- | --- |
| `report.html` | self contained page - what it was measured on, both tables and both charts per class count, and AVL against each of the others |
| `RESULTS.md` | the same tables in markdown |
| `summary.csv` | every timed run, one row each |
| `results.json` | everything, including each individual sample |

Every report carries the machine, the operating system, the simulator version
and the version of each of the four things being compared. A time means little
without them, and less still against a time from another machine.

`results/` is not tracked by git, so a `make distclean` in `benchmarks/` is the
end of any recorded run - take a copy first if you want to keep one.

### Reading the numbers

`us/item` is the figure to compare for randomization, and the seconds in the
first table for the run as a whole; `relative` in each is against the fastest
flavour there. A constrained solve costs milliseconds, so the randomization is
far larger than the run-to-run spread of the phases it is subtracted from; the
residual noise is a few percent, which resolves differences of about 10 % and
up. Raise `-r` to settle anything smaller.

How many classes take part matters to the comparison, not just to the total: an
implementation that pays a setup cost per constraint shape and then runs cheaply
looks worse at `-N 16 -n 16`, where every item is a class it has not seen, than
at `-N 1 -n 256`, where it sees the same class 256 times. Sweeping `-N` at a
fixed `-n` is how that shows up.
