# randomization / urandom

Unconstrained randomization - the cost of simply producing a random number, with no
constraint solver involved on either side.

| | SystemVerilog | AVL |
|---|---|---|
| full 32 bit range | `$urandom()` | `avl.urandom_range(0, 0xFFFFFFFF)` |
| bounded range, inclusive | `$urandom_range(100, 10)` | `avl.urandom_range(10, 100)` |
| range from zero, inclusive | `$urandom_range(255)` | `avl.urandom_range(0, 255)` |

`avl.urandom_range` is what AVL itself calls to pick an unconstrained value, so this is a like
for like comparison of the two random number generators rather than of the two solvers.

A single draw is far cheaper than advancing the clock - roughly 8 us per edge - so this
benchmark draws a burst of them per edge rather than one, and runs a million in total. See
[bench.conf](bench.conf).

- SystemVerilog : [rtl/urandom.sv](rtl/urandom.sv) (behind `` `ifdef BENCH_SV_RANDOMIZE ``)
- AVL : [cocotb/urandom.py](cocotb/urandom.py)

```sh
make            # or: make ITERATIONS=2000000 BURST=1000
```
