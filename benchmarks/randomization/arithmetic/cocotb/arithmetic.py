# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Arithmetic constraints - relational operators and addition / subtraction, and
# nothing else. No sets, no bitwise operators, no implications.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/arithmetic.sv is likewise shared.
#
# avl.Logic maps onto a z3 bit vector, and z3 bit vector comparison operators are
# signed by default, so the unsigned comparisons of SystemVerilog are spelled
# UGT / ULT / UGE / ULE here. Bit vector addition and subtraction wrap at the
# width of the variable, exactly as they do in SystemVerilog.


import os

import avl
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import UGE, UGT, ULE, ULT, And

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5


class arithmetic_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.a = avl.Logic(0, width=16, fmt=hex)
        self.b = avl.Logic(0, width=16, fmt=hex)
        self.c = avl.Logic(0, width=16, fmt=hex)
        self.d = avl.Logic(0, width=16, fmt=hex)

        # Every constraint here controls a single variable - there are no
        # dependencies between the fields. See the implication benchmark for
        # those.

        # Bounded above and below.
        self.add_constraint("c_a", lambda a: And(UGE(a, 100), ULE(a, 10000)), self.a)

        # Bounded above and below, both strict.
        self.add_constraint("c_b", lambda b: And(UGT(b, 250), ULT(b, 20000)), self.b)

        # An inequality, and an upper bound.
        self.add_constraint("c_c", lambda c: And(c != 0, ULE(c, 1000)), self.c)

        # Addition inside the comparison. The upper bound keeps the sum clear of
        # the wrap at 16 bits.
        self.add_constraint("c_d", lambda d: And(ULE(d, 30000), UGT(d + 1000, 5000)), self.d)


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

    item = arithmetic_item("item")
    checksum = 0
    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                item.randomize()

                a, b, c, d = int(item.a), int(item.b), int(item.c), int(item.d)

                assert 100 <= a <= 10000, f"c_a violated : a={a} on iteration {count}"
                assert 250 < b < 20000, f"c_b violated : b={b} on iteration {count}"
                assert c != 0 and c <= 1000, f"c_c violated : c={c} on iteration {count}"
                assert d <= 30000 and ((d + 1000) & 0xFFFF) > 5000, f"c_d violated : d={d}"

                checksum += a + b + c + d
                count += 1

    # Both flavours must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl iterations={count} checksum={checksum}")
