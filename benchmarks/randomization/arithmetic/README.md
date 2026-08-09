# randomization / arithmetic

Arithmetic constraints only - relational operators and addition / subtraction. No sets, no
bitwise operators, no implications.

Every constraint controls a single variable - there are no dependencies between the fields.
See the [implication](../implication) benchmark for those.

| Constraint | Property | SystemVerilog | AVL |
|---|---|---|---|
| `c_a` | bounded above and below | `a >= 100; a <= 10000;` | `And(UGE(a, 100), ULE(a, 10000))` |
| `c_b` | bounded, both strict | `b > 250; b < 20000;` | `And(UGT(b, 250), ULT(b, 20000))` |
| `c_c` | inequality, and an upper bound | `c != 0; c <= 1000;` | `And(c != 0, ULE(c, 1000))` |
| `c_d` | addition inside the comparison | `d <= 30000; d + 1000 > 5000;` | `And(ULE(d, 30000), UGT(d + 1000, 5000))` |

All four fields are 16 bits. Bit vector addition wraps at the width of the variable in z3
exactly as it does in SystemVerilog; the upper bound in `c_d` keeps the sum clear of the wrap.

z3's bit vector comparisons are signed by default, so the unsigned comparison of a SystemVerilog
`bit [15:0]` is spelled `UGT` / `ULT` / `UGE` / `ULE`.

- SystemVerilog : [rtl/arithmetic.sv](rtl/arithmetic.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/arithmetic.py](cocotb/arithmetic.py)

```sh
make            # or: make ITERATIONS=1000
```
