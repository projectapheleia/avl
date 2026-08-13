# randomization / mixed

The widest spread of constructs in the suite, on an item shaped like a real bus transaction.
Where the other benchmarks isolate one category, this one is deliberately representative - it is
the closest thing here to everyday constrained random code.

Five fields of four different widths: a 32 bit `addr`, a 16 bit `len`, two 8 bit fields `kind`
and `attr`, and a single bit `secure`.

| Constraint | Category | SystemVerilog | AVL | pyvsc |
|---|---|---|---|---|
| `c_kind` | list | `kind inside {0, 1, 2, 4, 8};` | `Or([kind == v for v in KINDS])` | `self.kind.inside(vsc.rangelist(*KINDS))` |
| `c_len` | arithmetic range | `len >= 1; len <= 4096;` | `And(UGE(length, 1), ULE(length, 4096))` | `self.len >= 1` / `self.len <= 4096` |
| `c_align` | arithmetic, modulo | `addr % 4 == 0;` | `URem(addr, 4) == 0` | `self.addr % 4 == 0` |
| `c_addr` | list, window with a hole | `addr inside {[32'h1000_0000:32'h1fff_ffff]}; !(addr inside {[32'h1800_0000:32'h18ff_ffff]});` | `And(UGE(...), ULE(...), Not(And(...)))` | `self.addr.inside(vsc.rangelist(vsc.rng(*WINDOW)))` / `self.addr.not_inside(vsc.rangelist(vsc.rng(*HOLE)))` |
| `c_attr` | bitwise, cross field | `(attr & 8'h0f) == (kind & 8'h0f);` | `(attr & 0x0F) == (kind & 0x0F)` | `(self.attr & 0x0F) == (self.kind & 0x0F)` |
| `c_page` | bitwise, shift | `(addr >> 24) inside {32'h10, 32'h11, 32'h1f};` | `Or([LShR(addr, 24) == p for p in PAGES])` | `(self.addr >> 24).inside(vsc.rangelist(*PAGES))` |
| `c_kind0` | implication | `(kind == 0) -> (len == 1);` | `Implies(kind == 0, length == 1)` | `with vsc.implies(self.kind == 0): self.len == 1` |
| `c_secure` | dependency, if / else | `if (addr >= 32'h1f00_0000) secure == 1; else secure == 0;` | `If(UGE(addr, SECURE_BASE), secure == 1, secure == 0)` | `with vsc.if_then(self.addr >= SECURE_BASE): ...` / `with vsc.else_then: ...` |
| `c_attr_ne` | inequality | `attr != 8'hff;` | `attr != 0xFF` | `self.attr != 0xFF` |

Between them these cover set membership, ranges, exclusion, alignment by modulo, bitwise masking
across two fields, a shift, an implication, a two sided dependency and an inequality - nine
constraints over five fields.

z3's bit vector comparisons, `%` and `>>` are all signed by default, so the unsigned forms a
SystemVerilog vector implies are spelled `UGE` / `ULE`, `URem` and `LShR`. pyvsc's `rand_bit_t` is
unsigned already, and takes `inside` on an expression as well as on a field, so `c_page` stays a
shift there rather than becoming a set of ranges.

`addr` is 32 bits partly because Verilator 5.040 mis-emits a right shift of a narrower vector -
see [cross](../cross) for the detail.

- SystemVerilog : [rtl/mixed.sv](rtl/mixed.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/mixed.py](cocotb/mixed.py)
- pyuvm / pyvsc : [cocotb/mixed_pyuvm.py](cocotb/mixed_pyuvm.py)

```sh
make            # or: make ITERATIONS=2000
```
