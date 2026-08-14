# randomize_and_send / bitwise_128

A **whole transaction, end to end**: build an object of 128 constrained variables, randomize it, and
drive the result onto 128 signals, once per clock edge. One test, covering both halves of the tree in
a single figure.

The other two groups each measure half of this deliberately:

| Group | What it isolates |
|-------|------------------|
| [randomization](../../randomization) | solving constraints, on four variable items |
| [create_and_send](../../create_and_send) | building a transaction and driving it, with no solving |
| **this** | both at once, at a size where neither is negligible |

Nothing here is separable, and that is the point - it is the number a testbench actually pays per
transaction. Read against the other two, it also says how the halves compose: the solve dominates by
roughly two orders of magnitude, so a per-transaction figure is mostly a solver figure.

---

## The item

128 variables of 32 bits, each carrying one of the four bitwise constraints of
[randomization/bitwise](../../randomization/bitwise), rotating over the variables - variable `i`
carries kind `i % 4`. The constraints are unchanged from that benchmark, so its per randomization
figure for a four variable item is directly comparable.

| Kind | Constraint | Leaves free |
|------|-----------|-------------|
| `c_0` | `(d & 32'h0000_00ff) == 32'h0000_005a` | the top 24 bits |
| `c_1` | `(d \| 32'h0000_ffff) == 32'hffff_ffff` | the bottom 16 bits |
| `c_2` | `((d ^ 32'ha5a5_a5a5) & 32'hffff_0000) == 32'h5a5a_0000` | the bottom 16 bits |
| `c_3` | `((d >> 8) & 32'h0000_00ff) == 32'h0000_003c` and `d[31:28] == 4'b1010` | 20 bits, in two pieces |

- SystemVerilog : [rtl/bitwise_128.sv](rtl/bitwise_128.sv) (behind `` `ifdef BENCH_SV ``) - a `rand`
  array with one `foreach` constraint per kind
- AVL : [cocotb/bitwise_128.py](cocotb/bitwise_128.py) - an `avl.SequenceItem` with a list of 128
  `avl.Logic`, and a constraint added per variable
- pyuvm / pyvsc : [cocotb/bitwise_128_pyuvm.py](cocotb/bitwise_128_pyuvm.py) - a `vsc.randobj`

The pyvsc item holds its variables as **four lists of 32**, one per kind, rather than one list of 128.
A pyvsc constraint cannot pick a kind out of a single list by index arithmetic - `foreach` with
`if_then` on `i % 4` is rejected by its constraint builder - and four `foreach` blocks over four
lists express the same problem: 128 variables, 32 of each kind, and variable `i` still carries kind
`i % 4` because the drive loop reads them back in that order.

Every value that arrives is checked twice: by the RTL, against the constraint its position carries,
and by the testbench, against the same four constraints written independently of the expressions the
solver was given. A flavour that solved wrongly, or drove nothing, fails rather than looks fast.

---

## Running

```sh
make                       # this benchmark, with its own report
make ITERATIONS=1000       # steady state figure - see below
make -C ../.. bench BENCHES=randomize_and_send
```

The quality runs are switched off here (`BENCH_QUALITY := 0`). The spread of the values drawn is
measured by [randomization/bitwise](../../randomization/bitwise), which constrains the same four
shapes at the same width; 128 variables of them would add 384 rows to the report and say the same
thing.

### On the iteration count

The default is **200 transactions**, three orders of magnitude below the randomization benchmarks,
because an item of 128 constrained variables costs tens of milliseconds to solve rather than tens of
microseconds.

At that count the figure includes a visible share of AVL's **per shape analysis**, which is amortized
rather than paid per randomization: the first few randomizations of a constraint shape work out which
bits the constraints pin and which are worth a randomization clause, and on an item this wide that is
a one-off cost of a few seconds before the steady state takes over. Measured at 20, 200 and 600
transactions, the total is linear with a fixed offset - so on this machine roughly **43 ms** a
transaction plus **2.5 to 2.8 s** once, which is about a quarter of the reported figure at 200
transactions, under a tenth at 600, and nothing over thousands.

The other two flavours show no such offset: pyvsc rebuilds its model per object and Verilator solves
each randomization afresh, so neither has anything to amortize. That is a real difference in shape,
not a measurement artefact, and it means the honest answer to "which is faster" depends on how long
the test is - AVL is behind pyvsc for the first hundred or so transactions of a constraint shape and
ahead of it thereafter. Both readings are legitimate, so if what you want is the steady state, raise
`ITERATIONS`; if what you want is what a two hundred transaction test costs, leave it.
