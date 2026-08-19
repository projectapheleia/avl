# turnaround / bitwise_128

**How long you wait to see a change.** Every other benchmark in this tree measures how fast a
testbench runs. This one measures how long it takes to run at all - build it from nothing, then
change one line of it and build and run it again.

It is the only benchmark here where what is being compared is the language the testbench is written
in rather than the library. The testbench, the RTL, the item and the simulator are
[randomize_and_send/bitwise_128](../../randomize_and_send/bitwise_128)'s, used unchanged, so the
figure sits directly alongside that benchmark's per transaction cost: one says what a transaction
costs once you are running, the other says what it costs to get there.

---

## The three measurements

| Phase | State it starts from | What it is |
|-------|----------------------|------------|
| `cold` | nothing built - no model, no byte compiled testbench | the first run of a testbench you have just been handed |
| `baseline` | built, and nothing changed | the run on its own, with nothing to build |
| `run` | built, and one line of the testbench just edited | every run after you change something |

`cold` gives every flavour the same build to do - the simulator elaborates and compiles the same 128
signal design - and then each runs its own test.

`run` minus `baseline` is **the rebuild the edit forced**, and that is the headline figure, because
it is the only part of the wait that the choice of testbench language decides:

- **sv** - the testbench is compiled with the design. The line that changed is a line the simulator
  has to elaborate and compile again before anything can run.
- **avl**, **pyuvm** - the testbench is Python, which the simulator never sees. The model it built
  still stands, and the `.pyc` is the only thing rebuilt. **Both are zero**, and they are measured
  rather than assumed: the logs of both flavours' edit phase contain no invocation of Verilator and
  no invocation of the compiler.

The run each flavour then does is reported next to it, in the `run (s)` column, and all three
totals are in the *As measured* table. A turnaround is a wall clock wait, and both halves of it are
there to be read.

---

## The edit

One line, in each flavour's own testbench, reached by a define:

| Flavour | File | The line |
|---------|------|----------|
| `sv` | [rtl/bitwise_128.sv](../../randomize_and_send/bitwise_128/rtl/bitwise_128.sv) | `` `ifdef BENCH_EDIT `` sets `localparam REVISION` from the define |
| `avl` | [cocotb/bitwise_128.py](../../randomize_and_send/bitwise_128/cocotb/bitwise_128.py) | `REVISION` from `BENCH_EDIT` in the environment |
| `pyuvm` | [cocotb/bitwise_128_pyuvm.py](../../randomize_and_send/bitwise_128/cocotb/bitwise_128_pyuvm.py) | the same |

`REVISION` is only ever printed, on the `BENCH_RESULT` line at the end of the run. That is
deliberate: an edit that changed what the test did would change how long the run took, and the
build and the run would no longer be separable. The entire cost of changing this line is whatever
has to be built again before the change can be seen - which is the thing being measured.

The define is how the variants are expressed, and the timestamp is how the tools are told there was
an edit at all: [scripts/bench_edit.py](../../scripts/bench_edit.py) moves the file's mtime on,
exactly as saving it in an editor does, and then runs the command. Make compares mtimes and Python
compares the mtime recorded in the `.pyc` header, so both react as they would to a real save. No
file in the tree is rewritten, and the benchmark leaves no diff behind.

**Every repeat is a different edit.** The define carries a number that changes with each one,
rather than a flag. It has to: Verilator hashes what it is given and skips regenerating an
identical model, quite rightly, so repeating one edit would be measured once and skipped twice, and
the median of three would be a build that did nothing. That is not a hypothetical - it is what the
first version of this benchmark measured, and it reported the sv flavour at 3.0 s instead of 15.2 s.

Both the removal and the edit are done inside the measured command rather than once beforehand, so
each of the `REPEATS` runs starts from the state it is supposed to be measuring.

---

## Running

```sh
make -C turnaround/bitwise_128        # this benchmark, with its own report
make bench BENCHES=turnaround         # the same, through the top level
```

| Setting | Value | Why |
|---------|-------|-----|
| `ITERATIONS` | 5 | the run has to be real, but it is not what is being measured |
| `BENCH_PHASES` | `turnaround` | cold, baseline and edit, instead of the usual two |
| `BENCH_QUALITY` | 0 | the spread of the drawn values is measured where the values matter |

Five transactions is enough to elaborate the model, start cocotb, solve, drive, and have the RTL
checker confirm what it received. Raising `ITERATIONS` adds the same run time to every phase, so it
leaves the rebuild figure alone and grows the `run (s)` beside it - which is a way of asking how
long a test has to be before the build stops being what you are waiting for.

---

## Reading it

The headline figure is seconds per edit. The `cold` figures are in the *As measured* table
alongside it, and the two are meant to be read together - what a flavour has to do again for one
line is the distance between them.

On the machine in the report, with `ITERATIONS=5`:

| Flavour | cold | after an edit | What the edit cost |
|---------|------|---------------|--------------------|
| `sv` | 13.7 s | 15.2 s | the whole build, again |
| `avl` | 18.7 s | 8.6 s | nothing to rebuild |
| `pyuvm` | 12.5 s | 2.3 s | nothing to rebuild |

Two separate things are in those numbers, and they point in opposite directions.

**The build.** For `sv` an edit costs what a first build costs - the line that changed is a line
Verilator has to elaborate and compile again, and the model it produced is thrown away. `avl` and
`pyuvm` rebuild nothing at all: their edit figure contains no compilation, only the wait to run.
This is the difference the benchmark was written to measure, and it is a language difference rather
than a library one - it would hold for any Python testbench against any compiled one.

**The run.** AVL costs about 6 s more than pyuvm for the same five transactions, in the cold figure
and in the edit figure alike, so it is a fixed cost rather than a per transaction one - the setup
for an item of 128 constrained variables, paid once per process. At five transactions that fixed
cost is nearly the whole figure, which is why AVL is 3.7x pyuvm here while
[randomize_and_send](../../randomize_and_send/bitwise_128), at 200 transactions, measures the two as
level and AVL slightly ahead. The two results are the same curve read at its two ends: AVL trades a
setup cost for a lower steady state, and five transactions is well below where that trade pays.

So the honest summary of this benchmark is that a Python testbench does not rebuild and a compiled
one does, and that on a test this short AVL spends a good part of what that saves on starting up.
Raising `ITERATIONS` moves the balance: the fixed costs stay where they are and every flavour pays
for the extra transactions, AVL least of the three. Where it ends up level with pyuvm is around the
two hundred transactions [randomize_and_send](../../randomize_and_send/bitwise_128) runs.
