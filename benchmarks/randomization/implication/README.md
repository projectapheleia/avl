# randomization / implication

Implication and dependency constraints - one random field steering the legal values of the
others.

| Constraint | Property | SystemVerilog | AVL |
|---|---|---|---|
| `c_mode` | the field the rest depend on | `mode <= 3;` | `ULE(mode, 3)` |
| `c_0` | implies an exact value | `(mode == 0) -> (len == 0);` | `Implies(mode == 0, length == 0)` |
| `c_1` | implies an upper bound | `(mode == 1) -> (len <= 16);` | `Implies(mode == 1, ULE(length, 16))` |
| `c_2` | implies a range on another field | `(mode == 2) -> (addr >= 16'h1000 && addr < 16'h2000);` | `Implies(mode == 2, And(UGE(addr, 0x1000), ULT(addr, 0x2000)))` |
| `c_3` | implies a lower bound | `(mode == 3) -> (len > 200);` | `Implies(mode == 3, UGT(length, 200))` |
| `c_valid` | two sided dependency | `if (len > 100) valid == 1; else valid == 0;` | `If(UGT(length, 100), valid == 1, valid == 0)` |

A constraint written as `if / else` constrains both branches, so it becomes `If` rather than a
single `Implies`. Every mode is satisfiable, and the checks confirm the dependency held for the
mode that was drawn.

- SystemVerilog : [rtl/implication.sv](rtl/implication.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/implication.py](cocotb/implication.py)

```sh
make            # or: make ITERATIONS=2000
```
