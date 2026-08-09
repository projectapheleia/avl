# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# List constraints - set membership with "inside", and nothing else. Value sets,
# range sets, exclusion, and a set built from other random fields.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/list.sv is likewise shared.
#
# SystemVerilog's "inside" becomes an Or over the members. A range inside a set
# becomes an unsigned bound, because avl.Logic maps onto a z3 bit vector whose
# comparison operators are signed by default.


import os

import avl
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import UGE, ULE, And, Not, Or

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

VALUES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
RANGES = [(100, 200), (500, 600), (5000, 5100)]
EXCLUDED = (0, 1000)
MIXED = (7, (20, 25), 9999)


class list_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        # Every constraint here controls a single variable - there are no
        # dependencies between the fields. See the implication benchmark for
        # those.

        self.a = avl.Logic(0, width=16, fmt=hex)
        self.b = avl.Logic(0, width=16, fmt=hex)
        self.c = avl.Logic(0, width=16, fmt=hex)
        self.d = avl.Logic(0, width=16, fmt=hex)

        # A set of sixteen discrete values.
        self.add_constraint("c_a", lambda a: Or([a == v for v in VALUES]), self.a)

        # A set of ranges.
        self.add_constraint(
            "c_b",
            lambda b: Or([And(UGE(b, lo), ULE(b, hi)) for lo, hi in RANGES]),
            self.b,
        )

        # Exclusion - anything outside the range.
        self.add_constraint(
            "c_c",
            lambda c: Not(And(UGE(c, EXCLUDED[0]), ULE(c, EXCLUDED[1]))),
            self.c,
        )

        # A set mixing discrete values with a range.
        self.add_constraint(
            "c_d",
            lambda d: Or(d == MIXED[0], And(UGE(d, MIXED[1][0]), ULE(d, MIXED[1][1])),
                         d == MIXED[2]),
            self.d,
        )


@cocotb.test
async def test(dut):
    iterations = int(os.environ.get("BENCH_ITERATIONS", 1000))
    burst = int(os.environ.get("BENCH_BURST", 1))
    flavour = os.environ.get("BENCH_FLAVOUR", "avl")

    # Cleared for the baseline run, which measures the harness on its own.
    enable = os.environ.get("BENCH_RANDOMIZE", "1") == "1"

    edges = max(iterations // burst, 1)

    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, unit="ns").start())

    dut.rst_n.value = 0
    for _ in range(RESET_CYCLES):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    item = list_item("item")
    checksum = 0
    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                item.randomize()

                a, b, c, d = int(item.a), int(item.b), int(item.c), int(item.d)

                assert a in VALUES, f"c_a violated : a={a} on iteration {count}"
                assert any(lo <= b <= hi for lo, hi in RANGES), f"c_b violated : b={b}"
                assert not (EXCLUDED[0] <= c <= EXCLUDED[1]), f"c_c violated : c={c}"
                assert d == MIXED[0] or MIXED[1][0] <= d <= MIXED[1][1] or d == MIXED[2], (
                    f"c_d violated : d={d}"
                )

                checksum += a + b + c + d
                count += 1

    # Both flavours must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl iterations={count} checksum={checksum}")
