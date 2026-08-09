# randomization / bitwise

Bitwise constraints only - and, or, xor, shift and bit select. No arithmetic, no sets, no
implications.

| Constraint | Property | SystemVerilog | AVL |
|---|---|---|---|
| `c_a` | masked equality | `(a & 32'h0000_00ff) == 32'h0000_005a;` | `(a & 0x000000FF) == 0x0000005A` |
| `c_b` | or against a mask | `(b \| 32'h0000_ffff) == 32'hffff_ffff;` | `(b \| 0x0000FFFF) == 0xFFFFFFFF` |
| `c_c` | xor against a pattern | `((c ^ 32'ha5a5_a5a5) & 32'hffff_0000) == 32'h5a5a_0000;` | `((c ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000` |
| `c_d` | shift and bit select | `(d >> 8) & 32'hff == 32'h3c; d[31:28] == 4'b1010;` | `LShR(d, 8) & 0xFF == 0x3C`, `Extract(31, 28, d) == 0b1010` |

All four fields are 32 bits. Python's `>>` on a z3 bit vector is an *arithmetic* shift, so the
logical shift of an unsigned SystemVerilog vector is spelled `LShR`, and a bit select is spelled
`Extract`.

- SystemVerilog : [rtl/bitwise.sv](rtl/bitwise.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/bitwise.py](cocotb/bitwise.py)

```sh
make            # or: make ITERATIONS=2000
```
