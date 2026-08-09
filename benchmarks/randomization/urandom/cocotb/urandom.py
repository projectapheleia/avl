# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Unconstrained randomization - $urandom and $urandom_range.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/urandom.sv is likewise shared.
#
# Only the randomization itself differs. When the flavour is "avl" the values are
# drawn here with avl.urandom_range - which is exactly what AVL itself uses to
# pick an unconstrained value. When it is "sv" the identical values are drawn
# inside the RTL on the same clock edge with $urandom and $urandom_range, and this
# loop only advances the clock.
#
# No constraint solver is involved on either side - this is the raw cost of
# producing a random number. A single one of those is far cheaper than advancing
# the clock, so this benchmark draws a burst of them per edge; see bench.conf.


import os

import avl
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5


class urandom_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.a = avl.Logic(0, width=32, fmt=hex)
        self.b = avl.Logic(0, width=32, fmt=hex)
        self.c = avl.Logic(0, width=32, fmt=hex)


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

    item = urandom_item("item")
    checksum = 0
    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                # The full 32 bit range.
                item.a.value = avl.urandom_range(0, 0xFFFFFFFF)

                # A bounded range, inclusive of both ends.
                item.b.value = avl.urandom_range(10, 100)

                # A range from zero, inclusive.
                item.c.value = avl.urandom_range(0, 255)

                a, b, c = int(item.a), int(item.b), int(item.c)

                assert 10 <= b <= 100, f"b out of range : b={b} on iteration {count}"
                assert c <= 255, f"c out of range : c={c} on iteration {count}"

                checksum += a + b + c
                count += 1

    # Both flavours must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl iterations={count} checksum={checksum}")
