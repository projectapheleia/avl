# Mutation Testing

Mutation testing measures the **testbench**, not the design.

`avl-mutation-testing` injects artificial bugs into the RTL and re-runs the
existing tests against each one. A mutant the tests still pass is a hole in the
verification environment: a class of bug that could ship unnoticed.

## Running everything

From this directory, one campaign per example and a single summary:

```sh
make            # every example, then a summary
make list       # the examples that would be run
make clean
```

```
Mutation testing regression
---------------------------------------------------------------
  alu              PASS  5 mutation(s), score 100.0%
  arith            PASS  2 mutation(s), score 100.0%
  ...
---------------------------------------------------------------
  12/12 passed
```

An example passes when the campaign ran, every mutation it asked for was located
and the campaign came back clean — so every mutation was either detected or
proved equivalent. Anything else fails, one failure makes the exit status non
zero, and each run's full log is kept under `.results/<example>.log`.

## Running one example

```sh
cd alu          # or any of the others

make sim                   # golden design, exactly like any other AVL example
make sim AVL_MUTANT=2      # build and run mutant 2, which should fail
make mutants               # generate the mutants, check them, write the report
make mutation_regression   # run the testbench against every mutant and score it
make clean
```

Generating the mutants also writes `mutants/mutations.html`, a report explaining
every mutation in its source context, and checks each one against the golden
design with yosys:

```
    1  alu_arith.sv:17   arith    a - b                   ->  a + b
    2  alu_arith.sv:20   arith    a + b                   ->  a - b
    3  alu_logic.sv:17   bitwise  a ^ b                   ->  a & b
    4  example_hdl.sv:69 pipeline valid_out <= valid_in;  ->  valid_out delayed 1 cycle
    5  example_hdl.sv:71 compare  alu_out == '0           ->  alu_out != '0

5 mutation(s)

Equivalence (yosys)
    1  different   differs from the golden design
    2  different   differs from the golden design
    3  different   differs from the golden design
    4  different   differs from the golden design
    5  different   differs from the golden design
```

`make mutation_regression` then runs the testbench against the golden design and
every mutant in turn, and reports what was caught:

```
Mutation regression: 5 mutation(s)

Golden design
  passed

   ID  WHERE             MUTATION                                             STATUS
  ----------------------------------------------------------------------------------
    1  alu_arith.sv:17   a - b -> a + b                                       DETECTED
    2  alu_arith.sv:20   a + b -> a - b                                       DETECTED
    3  alu_logic.sv:17   a ^ b -> a & b                                       DETECTED
    4  example_hdl.sv:69 valid_out <= valid_in; -> valid_out delayed 1 cycle  DETECTED
    5  example_hdl.sv:71 alu_out == '0 -> alu_out != '0                       DETECTED
  ----------------------------------------------------------------------------------
  5 detected, 0 survived
  Score 100.0% (5/5)
```

It exits non-zero if any mutation survives, so it drops into CI like any other
regression. Every run's log and results are kept, so a surprising verdict can be
looked into without re-running the campaign:

```
mutants/golden/sim.log     mutants/golden/results.xml
mutants/1/sim.log          mutants/1/results.xml       mutants/1/*.sv
```

`make mutate` is a shorthand for the same thing. The name `regression` on its own
is already taken by cocotb's makefiles, where it means *run this one test if it
is out of date*.

The campaign is deliberately serial. Every run shares the example directory and
AVL writes `coverage.json` to the working directory under a fixed name, so
running mutants concurrently here would have them overwrite each other's
coverage.

## How it works

Each mutation is written out as a **complete, standalone copy of the RTL**
carrying exactly one defect:

```
rtl/alu_arith.sv          y = a + b;     the golden source
mutants/2/alu_arith.sv    y = a - b;     mutant 2
```

Most defects are a single swapped operator. Two are not.

`pipeline` gives a registered signal an extra stage, so the signal arrives a
cycle late.

```
                 y <= result;
        becomes  begin avl_pipe_1 <= result; y <= avl_pipe_1; end
```

with `logic [$bits(y)-1:0] avl_pipe_1 = '0;` declared inside the module. `$bits`
keeps the width from having to be inferred, the initialiser stops the extra
stage pushing an X through the design out of reset, and the `begin`/`end` means
it works whether or not the original statement was already in a block.

Only a whole signal can gain a stage. `mem[wptr] <= wdata` is skipped, because
delaying that would need the index delayed too — a different defect. So is any
assignment from a constant, which is the reset arm of a register and models
nothing anybody would call a pipeline bug.

`sign` negates the value assigned to a **signed** variable:

```
                 diff = a - 1;
        becomes  diff = -(a - 1);
```

Signedness is read from the declarations: an explicit `signed`, or a type that
is signed by default (`int`, `integer`, `byte`, `shortint`, `longint`). An
explicit `unsigned` overrides the default, so `int unsigned` is not a site.
Unsigned variables are never offered — negating one is not a sign error, it is a
wrap, and nobody would have written it that way. Neither is a part select, which
is unsigned in SystemVerilog whatever it was carved out of.

This is read from the file rather than from an elaborated design, so a variable
whose signedness arrives through a typedef or a parameterised type is not
recognised and is simply not offered as a site.

`array_packed` and `array_unpacked` turn a declared dimension around:

```
        logic [W-1:0] a;      becomes  logic [0:W-1] a;      packed
        logic a [0:N-1];      becomes  logic a [N-1:0];      unpacked
```

They are separate classes because they break different things. Reversing a
**packed** dimension renumbers the bits, so it only shows up where the signal is
bit selected — a signal used only as a whole value is unaffected, and the
mutation is equivalent. Reversing an **unpacked** dimension reorders the
elements, so it shows up through assignment patterns and iteration order, not
through plain indexing: `mem[2]` is `mem[2]` either way.

A dimension with nothing to reverse is not offered: `[4]` carries a size rather
than a range, `[0:0]` reversed is itself, and parameter dimensions are left
alone.

`width` takes a bit off a packed declaration, modelling a bus declared one bit
too narrow so its top bit is quietly lost:

```systemverilog
logic [8:0] total;          becomes   logic [7:0] total;
total = a + b;                        total = 8'(a + b);
y     <= total;                       y     <= 9'(total);
```

The casts are not decoration. Narrowing a declaration on its own leaves every
expression the signal takes part in a bit short, and Verilator turns those width
warnings into errors — the mutant would fail to *build*, and a mutant that fails
to build is scored as detected without any testbench having noticed a thing. So
each reference is cast back to the original width and each assignment cast down
to the new one. The widths are then unchanged everywhere except inside the
signal itself, which is exactly the defect.

That rewriting has to reach every reference, so a signal is only offered when it
can all be done safely: internal declarations only (narrowing a port moves the
mismatch to the instantiation, out of reach), literal bounds only (the cast needs
a width), at least two bits wide, one declarator, no bit or part selects, and no
reading of the signal inside an assignment to itself — a counter like
`n <= n + 1` would need the two casts nested, so it is skipped.

Three classes are about control flow rather than what a signal holds.

`condition` works on branch decisions. It holds the branch permanently open and
permanently shut, and it nudges the comparisons the decision is built from:

```systemverilog
if (a > b)   becomes   if (1'b1)   and   if (1'b0)   and   if (a >= b)
```

The first two ask whether the tests go both ways and whether anything checks the
result when they do — line coverage tells you the branch ran, this tells you
whether its consequence is verified. The third asks the sharper question:
whether the stimulus sits on the boundary the branch turns on, since `>` and
`>=` differ only when the operands are equal.

A comparison that forms a branch decision therefore belongs to `condition`
rather than to `compare`, which would otherwise produce the very same mutant.
They are only partitioned when `condition` is actually requested, so `--types
compare` on its own still reaches every comparison in the design.

For a boundary mutation to be worth anything the two arms have to disagree at
the boundary. `if (a > b) pick = a; else pick = b;` is a max(), and a max is the
same whichever way the boundary falls — the equivalence check says so and
rightly excludes it. The example is written so that the arms do disagree.

It also drives `b = a` on every fourth item, and that is not decoration. Taking
one boundary mutation — `a >= b` becoming `a > b`, which differs only when the
operands are equal — and running it across eight seeds:

| | seeds detecting it |
| --- | --- |
| uniform random stimulus | 3 of 8 |
| with `b = a` driven on purpose | 8 of 8 |

Which is what the arithmetic says: `a == b` is expected 200/256 ≈ 0.78 times in
200 uniform byte pairs, so about half of seeds never reach the boundary at all.
Without directed stimulus, whether a boundary mutation is caught is decided by
the seed. That is the whole lesson of the class: the mutations worth having are
the ones your stimulus has to aim at. The reset arm of a clocked block is left alone:
holding that open or shut leaves the reset edge-sensitive but unused, which is a
malformed design rather than a defect, and one the equivalence check cannot read.

`statement` drops a registered assignment, so the register holds instead of
updating — an enable nobody wired up, a write path that never fires. Where
`pipeline` says *late*, this says *never*. The statement becomes a null
statement rather than vanishing, so an `if` without `begin`/`end` around it
still has a statement after it. Clocked blocks only, and not the reset arm.

`operand` turns a non-commutative operator around, keeping the operator and
reversing the meaning:

```systemverilog
a - b   becomes   b - a
a < b   becomes   b < a
```

Commutative operators are excluded — swapping the operands of an add or an and
produces a mutant that cannot differ from the original.

`blocking` and `nonblocking` swap the two kinds of assignment:

```systemverilog
x <= a;   becomes   x = a;      blocking
x = a;    becomes   x <= a;     nonblocking
```

This is the classic race. A blocking assignment in sequential logic hands the
new value to whatever reads it next; a nonblocking one hands over the old one.

Both are only offered where the target is **read again later in the same
begin/end**, because nowhere else can tell the two apart — a nonblocking
assignment nobody reads again behaves exactly like a blocking one, and the
mutation would be dead on arrival. The scope is the enclosing block rather than
the whole always block: a reset arm and the arm beside it are different paths,
and a read over in the other one is never reached from here.

Both are also restricted to edge-triggered blocks. A nonblocking assignment in
combinational logic is a `COMBDLY` error rather than a defect, so the mutant
would fail to build and be scored as detected without a testbench noticing
anything.

One caveat worth knowing: unlike every other class, the effect of these two
depends on simulation scheduling rather than on logic alone, so a mutant could
in principle behave differently under another simulator. Everything here is
checked against Verilator.

One declaration can carry more than one defect. `logic [7:0] lut [0:3]` has a
packed dimension and an unpacked one, and they are separate mutants.

One statement can too. A nonblocking assignment to a signed register is a
candidate for both `sign` and `pipeline`, and since those are different bugs
both are generated, as separate mutants.

Nothing in the testbench knows that mutation testing is happening. A mutant is
ordinary RTL that happens to be wrong, so it builds and runs like any other
design on any simulator.

Every line a mutation changed carries a marker saying what was done to it:

```systemverilog
alu_out = a - b;  /* AVL MUTATION - arith: a + b -> a - b */
```

A mutant is otherwise indistinguishable from the golden source, and one will
sooner or later turn up in an editor, a debugger or a waveform with no
indication of which it is. The marker is that indication. Where a mutation
changes more than one line - `pipeline` rewrites a statement and declares a
register above it - every line it touched is marked.

Mutation sites are found with [pyslang](https://pypi.org/project/pyslang/),
whose concrete syntax tree round trips back to the original source byte for
byte. The parser only locates the exact source span of each operator; the
rewrite is a splice over that span, so formatting and comments survive.

Elaboration time constants are skipped. Mutating the `WIDTH-1` of a port or the
`AW-1:0` of a part select is a structural change or a compile error, not a
design bug, so those are not offered as sites.

## Designs of more than one file

The ALU is split across three files, and the mutations land in whichever one
holds the site:

```
rtl/alu_arith.sv    the add and the subtract        arith
rtl/alu_logic.sv    the and and the xor             bitwise
rtl/example_hdl.sv  the zero flag comparison        compare
                    a cycle of delay on an output   pipeline
```

Nothing special is needed. `GOLDEN_RTL` defaults to every `.sv` under `rtl/`,
sorted so the mutations are numbered identically on every machine, and each
mutant is a **complete copy of all three files with one of them changed**:

```
mutants/2/alu_arith.sv     <- the mutated file
mutants/2/alu_logic.sv     <- byte for byte the golden source
mutants/2/example_hdl.sv   <- byte for byte the golden source
```

That is why the build never has to know which file a mutation landed in. It
compiles `mutants/<id>/*.sv` and gets one defect wherever it happens to be.

The one thing a hierarchical design does need is `--top`. Without it the
equivalence check is pointed at whichever module the mutation landed in, so a
mutation in `alu_arith` would be compared against `alu_arith` in isolation
rather than against the whole design — and a sub-module difference the top masks
would be reported as `different` when nothing could ever detect it. The
`sim.mk` passes `--top $(TOPLEVEL)`.

To run the generator over several files by hand, just list them:

```sh
avl-mutation-testing --source rtl/*.sv --top example_hdl \
                     --types arith,bitwise --count 4 --list
```

## One seed for the campaign

`sim.mk` pins `COCOTB_RANDOM_SEED` for every run:

```make
COCOTB_RANDOM_SEED ?= 1
export COCOTB_RANDOM_SEED
```

Without it cocotb draws a fresh seed from the clock for each simulation, so the
golden design and every mutant see different stimulus. A campaign run that way
can report a mutation as detected and the next run report the same mutation as a
survivor, with nothing changed in the design or the testbench — and a survivor is
exactly the result you would act on, by going to look for a verification hole
that the previous run said was not there.

Pinning the seed does not make boundary mutations reliably caught; it makes the
answer stable, so that a survivor means something. Catching them reliably is
what directed stimulus is for. Override the seed to sweep, but sweep the whole
campaign together.

## Equivalence checking

A mutation that does not change what the design does can never be caught by any
testbench. Report it as a survivor and you have invented a verification hole
that is not there. This is the standard nuisance of mutation testing, and it is
why the score is meaningless without some way of spotting them.

If [yosys](https://yosyshq.net/yosys/) is on `PATH`, generation builds a miter
of the golden design against each mutant and asks a SAT solver to break it:

| Verdict | Meaning |
| --- | --- |
| `different` | An input sequence exists that tells the mutant apart. A testbench that exercises this logic can catch it. |
| `equivalent` | No such sequence within the unrolling bound. Reported separately by the regression and excluded from the score. |
| `unknown` | yosys could not read the design or could not decide. |
| `timeout` | The solver ran out of time. |
| `skipped` | yosys is not installed, or `--no-equiv` was passed. |

Only `different` is a sound proof. `equivalent` means *no difference within
`--equiv-cycles` cycles* (8 by default), not a proof of equivalence — a mutation
that takes longer than that to show will be labelled `equivalent`. Raise the
bound if you suspect that; `--equiv-timeout` caps the solver per mutation.

None of this is required. Without yosys the flow works exactly as before, and
every mutation is marked `skipped`.

The `equivalent` example is a negative test for all of this. Its RTL adds zero:

```systemverilog
pass_through = a + 8'd0;
```

The `arith` mutation turns that into a subtract — a change to the source that is
no change at all to the design. Beside it sits an ordinary xor mutation that
should be caught, so one campaign shows both outcomes:

```
    1  example_hdl.sv:29 a + 8'd0 -> a - 8'd0                  EQUIVALENT
    2  example_hdl.sv:39 pass_through ^ b -> pass_through & b  DETECTED
  1 detected, 0 survived, 1 equivalent (not scored)
  Score 100.0% (1/1)
```

Run the same campaign with `--no-equiv` and the first mutation is reported as a
survivor instead, the score drops to 50%, and the run fails — telling you that
you have a hole in the testbench when you have nothing of the kind. That is the
whole argument for the equivalence check, and the example exists so the claim is
tested rather than asserted.

It is the one example that needs yosys, so it declares that in its
`mutation.mk`:

```make
MUTATION_REQUIRES := yosys
```

The regression skips an example whose required tools are missing rather than
failing it, and reports the skip in the summary.

## Choosing the mutations

Each example sets its own mutations in `mutation.mk`:

```make
MUTATION_TYPES := arith,compare
MUTATION_COUNT := 3
```

`avl-mutation-testing --list-types` lists the available classes: `arith`,
`bitwise`, `compare`, `logical`, `shift`, `unary`, `pipeline`, `sign`,
`array_packed`, `array_unpacked`, `width`, `condition`, `statement`, `operand`,
`blocking` and `nonblocking`. To see the sites without generating anything:

```sh
avl-mutation-testing --source rtl/example_hdl.sv --types arith --list
```

When there are more sites than `--count`, variety comes before repetition. Every
class is represented before any class appears twice, and within a class every
operator is used before any operator is used twice — so asking for four
mutations of a file full of adds gets you an add, a comparison and a shift
before it gets you a second add. Classes are offered in the order you list them
in `--types`, which decides what to drop when `--count` is smaller than the
number of classes, and sites are taken in source order within an operator, so
the result is fully determined.

Defects of one sort tend to cluster — a file will have a run of adds long before
its first comparison — so taking sites in source order would spend the whole
budget on one class and never reach the rest.

Add `--seed` to sample randomly instead, reproducibly.

## The examples

Eight of them are synthetic, one per mutation class. Each is a tiny DUT holding
sites of that class and nothing else, with a testbench small enough to read in
one sitting, so a class can be seen on its own:

| Example | RTL | Mutations |
| --- | --- | --- |
| `arith` | `y <= (a + b) - 9'd1` | the add, the subtract |
| `bitwise` | `y <= (a & b) ^ (a \| b)` | the and, the or, the xor |
| `compare` | `y <= {(a < b), (a == b)}` | the less-than, the equality |
| `logical` | `y <= {a>0 && b>0, a>0 \|\| b>0}` | the and, the or |
| `shift` | `y <= (a << 1) \| (b >> 1)` | the left shift, the right shift |
| `unary` | `y <= ~a` | the `~`, and the `!` of the reset |
| `pipeline` | `y <= a ^ b` | a cycle of delay on `y`, and on `valid_out` |
| `sign` | signed `sum = a + b; y <= sum` | both signed assignments |

All eight share one interface — `clk`, `rst_n`, `valid_in`, `a`, `b` in and
`valid_out`, `y` out — so the testbenches are identical apart from the reference
`model()`, and any one of them reads against the others.

Two need directed stimulus, which is the point of those two classes:

* `compare` — `<` and `<=` differ **only** when `a == b`. Uniform random bytes
  hit that less than once in 200 items on average, so the mutant would survive
  more often than not. The sequence forces `b = a` on every fourth item.
* `logical` — `&&` and `||` agree unless the two conditions disagree, which
  needs an operand to be zero. The sequence forces `a = 0` or `b = 0` on half
  the items.

The other six are exposed by uniform random stimulus. All eight score 100%, and
yosys proves every one of their mutations differs from its golden design.

The remaining two examples are less synthetic:

| Example | Design | `--types` | Mutations |
| --- | --- | --- | --- |
| `alu` | Registered 8 bit ALU, three files | `arith,compare,bitwise,pipeline` | the add and subtract in `alu_arith`, the xor in `alu_logic`, the zero flag comparison and a cycle of delay on `valid_out` in the top |
| `fifo` | Synchronous FIFO | `arith,pipeline` | the occupancy subtract, the two pointer increments, a cycle of delay on both pointers |

Both score 100%, and yosys proves every mutation differs from its golden design,
so those are real detections rather than mutants that could not have failed.

That is the uninteresting answer, and it is worth breaking one to see the
interesting one. Delete this line from the ALU model in `alu/cocotb/example.py`:

```python
model_item.zero.value = int(out == 0)
```

The score drops to 4/5 and mutation 5 survives, because nothing in the testbench
looks at the zero flag any more. Yosys still calls that mutation `different`,
which is what tells you it is a genuine hole rather than an equivalent mutant.

## Detection

AVL logs an error and keeps going rather than aborting the test, so a
scoreboard mismatch is an `ERROR` record and not a cocotb failure. A mutant
counts as detected if the run logged an error, if cocotb recorded a failure, or
if the simulation did not complete.

This is why the golden run is checked first. If the testbench cannot pass the
unmutated design, every mutant would score as detected and the result would be
meaningless, so the regression stops there.
