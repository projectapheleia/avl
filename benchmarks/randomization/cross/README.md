# randomization / cross

Cross constraints - four fields whose legal values depend on each other, mixing arithmetic,
bitwise and list constructs in a single solve. Nothing here can be solved a variable at a time,
which is what separates it from the [arithmetic](../arithmetic), [bitwise](../bitwise) and
[list](../list) benchmarks, where every constraint controls one variable.

The dependency runs `a` -> `b` -> `c` -> `d`.

| Constraint | Category | SystemVerilog | AVL | pyvsc |
|---|---|---|---|---|
| `c_a` | list | `a inside {[100:200], [1000:1100], 5000};` | `Or([And(UGE(a, lo), ULE(a, hi)) ...] + [a == 5000])` | `self.a.inside(vsc.rangelist(vsc.rng(100, 200), ..., 5000))` |
| `c_b` | arithmetic, on `a` | `b > a; b < a + 1000;` | `And(UGT(b, a), ULT(b, a + 1000))` | `self.b > self.a` / `self.b < self.a + 1000` |
| `c_c` | arithmetic, on `b` | `c > b;` | `UGT(c, b)` | `self.c > self.b` |
| `c_mask` | bitwise, on `a` and `b` | `(c & 32'h0000_00ff) == ((a ^ b) & 32'h0000_00ff);` | `(c & 0x00FF) == ((a ^ b) & 0x00FF)` | `(self.c & 0x00FF) == ((self.a ^ self.b) & 0x00FF)` |
| `c_shift` | bitwise and arithmetic, on `a` | `(c >> 8) == ((a >> 8) + 1);` | `LShR(c, 8) == LShR(a, 8) + 1` | `(self.c >> 8) == (self.a >> 8) + 1` |
| `c_d` | list, on `a`, `b` and `c` | `d inside {a, b, c};` | `Or(d == a, d == b, d == c)` | `self.d.inside(vsc.rangelist(self.a, self.b, self.c))` |

`c_mask` and `c_shift` together determine `c` from `a` and `b`, while `c_c` requires `c > b`, so
the solver has to choose `b` such that the resulting `c` outranks it. The system is satisfiable
across the whole domain of `a`.

## Why 32 bit fields

Verilator 5.040 emits a malformed SMT-LIB expression for a right shift of a vector narrower than
32 bits - it passes a 32 bit shift constant to a 16 bit `bvlshr`:

```
Solver error: Argument #x00000008 at position 1 has sort (_ BitVec 32)
  it does not match declaration (declare-fun bvlshr ((_ BitVec 16) (_ BitVec 16)) (_ BitVec 16))
```

The solver rejects it, `randomize()` returns 0, and the failure then poisons the solver
connection for the rest of the simulation, so every later randomization fails too. Widening the
fields to 32 bits avoids it. AVL solves the 16 bit form without complaint.

- SystemVerilog : [rtl/cross.sv](rtl/cross.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/cross.py](cocotb/cross.py)
- pyuvm / pyvsc : [cocotb/cross_pyuvm.py](cocotb/cross_pyuvm.py)

```sh
make            # or: make ITERATIONS=1000
```
