# randomization / arithmetic

Arithmetic constraints only - relational operators and addition / subtraction. No sets, no
bitwise operators, no implications.

Every constraint controls a single variable - there are no dependencies between the fields.
See the [implication](../implication) benchmark for those.

| Constraint | Property | SystemVerilog | AVL | pyvsc |
|---|---|---|---|---|
| `c_a` | bounded above and below | `a >= 100; a <= 10000;` | `And(UGE(a, 100), ULE(a, 10000))` | `self.a >= 100` / `self.a <= 10000` |
| `c_b` | bounded, both strict | `b > 250; b < 20000;` | `And(UGT(b, 250), ULT(b, 20000))` | `self.b > 250` / `self.b < 20000` |
| `c_c` | inequality, and an upper bound | `c != 0; c <= 1000;` | `And(c != 0, ULE(c, 1000))` | `self.c != 0` / `self.c <= 1000` |
| `c_d` | addition inside the comparison | `d <= 30000; d + 1000 > 5000;` | `And(ULE(d, 30000), UGT(d + 1000, 5000))` | `self.d <= 30000` / `self.d + 1000 > 5000` |

All four fields are 16 bits. Bit vector addition wraps at the width of the variable in z3
exactly as it does in SystemVerilog; the upper bound in `c_d` keeps the sum clear of the wrap.

z3's bit vector comparisons are signed by default, so the unsigned comparison of a SystemVerilog
`bit [15:0]` is spelled `UGT` / `ULT` / `UGE` / `ULE`. pyvsc's `rand_bit_t` is unsigned already,
so its constraints read as the SystemVerilog ones do.

- SystemVerilog : [rtl/arithmetic.sv](rtl/arithmetic.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/arithmetic.py](cocotb/arithmetic.py)
- pyuvm / pyvsc : [cocotb/arithmetic_pyuvm.py](cocotb/arithmetic_pyuvm.py)

```sh
make            # or: make ITERATIONS=1000
```
