# randomization / list

List constraints only - set membership with `inside`. No arithmetic beyond the bounds a range
implies, no bitwise operators, no implications.

Every constraint controls a single variable - there are no dependencies between the fields. See
the [implication](../implication) benchmark for those.

| Constraint | Property | SystemVerilog | AVL | pyvsc |
|---|---|---|---|---|
| `c_a` | a set of sixteen values | `a inside {1, 2, 4, ... 32768};` | `Or([a == v for v in VALUES])` | `self.a.inside(vsc.rangelist(*VALUES))` |
| `c_b` | a set of ranges | `b inside {[100:200], [500:600], [5000:5100]};` | `Or([And(UGE(b, lo), ULE(b, hi)) for lo, hi in RANGES])` | `self.b.inside(vsc.rangelist(vsc.rng(100, 200), ...))` |
| `c_c` | exclusion | `!(c inside {[0:1000]});` | `Not(And(UGE(c, 0), ULE(c, 1000)))` | `self.c.not_inside(vsc.rangelist(vsc.rng(0, 1000)))` |
| `c_d` | values mixed with a range | `d inside {7, [20:25], 9999};` | `Or(d == 7, And(UGE(d, 20), ULE(d, 25)), d == 9999)` | `self.d.inside(vsc.rangelist(7, vsc.rng(20, 25), 9999))` |

All four fields are 16 bits. z3's bit vector comparisons are signed by default, so the bounds of
a range use `UGE` / `ULE`. pyvsc has `inside` and `not_inside` directly, so of the three this is
the one where its constraints sit closest to the SystemVerilog.

- SystemVerilog : [rtl/list.sv](rtl/list.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/list.py](cocotb/list.py)
- pyuvm / pyvsc : [cocotb/list_pyuvm.py](cocotb/list_pyuvm.py)

```sh
make            # or: make ITERATIONS=2000
```
