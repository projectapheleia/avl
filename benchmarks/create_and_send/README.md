# create_and_send

What it costs a testbench to **build one transaction object and drive it onto the RTL**, once per
clock edge, for a growing number of signals. Nothing here is randomized - the values are a counter -
so what is measured is the framework overhead of a transaction and of the writes that send it.

| Benchmark | Signals built and driven per clock edge |
|-----------|-----------------------------------------|
| [signals_001](signals_001) | 1 |
| [signals_008](signals_008) | 8 |
| [signals_032](signals_032) | 32 |
| [signals_064](signals_064) | 64 |

Read across the sweep and the two halves separate: the part that does not change with the signal
count is what one transaction object costs, and the slope is what one field and one signal write
cost.

---

## What each flavour does

Every flavour drives the same 32 bit signals with the same values - signal `i` carries `i` more than
signal 0, and each item advances by one - and each builds a fresh object per item, the way a
testbench builds a sequence item per transaction rather than refilling one. The RTL checks both of
those as the values arrive, so a flavour that skipped the work would fail rather than look fast.

| Flavour | Item | Fields | Sending |
|---------|------|--------|---------|
| `sv`    | a plain SystemVerilog class, allocated with `new` | a dynamic array of `bit [31:0]`, sized to the benchmark | assignment to signals in the same process |
| `avl`   | `avl.SequenceItem` | one `avl.Logic(width=32)` per field | `handle.value = ...` per signal, through the simulator's programming interface |
| `pyuvm` | `uvm_sequence_item` | plain Python integers | the same, from the `run_phase` of a `uvm_test` |

The fields are not equivalent in what they offer, and the numbers should be read with that in mind.
An `avl.Logic` is an object per field which carries its own width, format and constraints, and masks
on assignment. A pyuvm item that is not randomized carries plain attributes, which offer none of
that - the testbench masks by hand instead - so pyuvm is doing less work per field, not the same work
faster. pyvsc, which is what the [randomization](../randomization) benchmarks measure pyuvm with, is
deliberately absent here: it exists to randomize, and nothing here is randomized.

- SystemVerilog : [rtl/create_and_send.sv](rtl/create_and_send.sv) (behind `` `ifdef BENCH_SV ``)
- AVL : [cocotb/create_and_send.py](cocotb/create_and_send.py)
- pyuvm : [cocotb/create_and_send_pyuvm.py](cocotb/create_and_send_pyuvm.py)

The `sv` flavour is the floor rather than a like-for-like framework comparison. It has no
transaction base class - there is no UVM in these benchmarks - and it assigns to the signals from
inside the module, so it pays nothing to cross into the simulator. That is the point of having it:
it says how much of the cost is inherent and how much is the framework and the interface.

---

## How it is built

All four benchmarks share one model and one testbench, and differ only in their `bench.conf`:

```
create_and_send/
├── create_and_send.conf              # settings shared by the group
├── rtl/create_and_send.sv            # one model, 64 signals, every benchmark
├── cocotb/create_and_send.py         # the sv and avl testbench
├── cocotb/create_and_send_pyuvm.py   # the pyuvm testbench
└── signals_032/
    ├── Makefile     -> ../../bench.mk
    ├── bench.conf                    # BENCH_SIGNALS := 32, and the shared conf
    ├── sv/Makefile      -> ../../../flavour.mk
    ├── avl/Makefile     -> ../../../flavour.mk
    └── pyuvm/Makefile   -> ../../../flavour.mk
```

The model always carries 64 signals - the largest count the sweep asks for - and each benchmark drives
the first `+signals=<n>` of them. Elaboration, the clock and the baseline are therefore identical
across the sweep, and the only thing that changes from one benchmark to the next is how much the
testbench does per edge. A benchmark asking for more than the model carries fails on elaboration
rather than quietly driving fewer, so raise `SIGNALS` in the RTL if the sweep grows.

They are one unpacked array port rather than 64 named ones, so `dut.d[i]` is what the testbench
writes. That asks the simulator's VPI to expose the elements of an array, which Verilator - the
default - does; a simulator that did not would need the ports written out separately.

There is no valid signal. The values driven start at one, so signal 0 being zero is enough to tell
the checker that nothing has been driven yet - and a valid signal would be another write on top of
the ones being measured, which at one signal would be half of the measurement.

---

## Running

```sh
# The whole sweep, and a report on just it, in ../results/create_and_send/
make -C .. bench BENCHES=create_and_send

# Re-print that report without re-running anything
make -C .. report BENCHES=create_and_send

# One point of the sweep, with its own report in signals_032/results/
make -C signals_032

# Quicker, at the cost of a noisier measurement
make -C signals_032 ITERATIONS=2000
```

The whole sweep is 12 builds and around 85 simulator runs, so it takes a couple of minutes. `make -C ..
bench` with no `BENCHES` runs everything else in the tree as well.

Nothing here randomizes, so `bench.conf` clears `BENCH_QUALITY` and the quality runs and the quality
section of the report are skipped - see the [framework README](../README.md).

### Iteration counts

The counts are set by the group's `create_and_send.conf`, and differ by flavour:

| Flavour        | Items per run                     | Items per clock edge |
|----------------|-----------------------------------|----------------------|
| `avl`, `pyuvm` | `max(10000, 160000 / signals)`    | 1                    |
| `sv`           | a hundred times that              | 100                  |

Both measurement phases scale with the count, so it does not change the ratio between them. What it
buys is a difference far enough clear of the run to run variation of the baseline, which is a few
percent. The count falls with the signal count - which is roughly what an item costs - to hold that
difference at half a second or more throughout, and the floor is where a wide item reaches it on its
own. One signal is the hardest case: an item there costs less than the 8 us the clock edge it is
built on costs, so most of the run is the baseline and it takes the most items to measure.

Native SystemVerilog comes out two to three orders of magnitude cheaper per item than a Python
testbench writing signals through the simulator, so at the same count its cost would disappear into
that noise. It therefore runs a hundred times as many items, and bursts them, because one item is
far cheaper than the 8 us an edge costs and the clock would otherwise be most of what its own run
measured. Everything the report compares is a time **per item**, so the counts do not have to match.

Anything given on the command line still wins, for every flavour.
