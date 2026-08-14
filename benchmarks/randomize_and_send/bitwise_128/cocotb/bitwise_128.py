# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Randomize and send - a whole transaction, end to end: build an object of 128
# constrained variables, randomize it, and drive the result onto the RTL, once per
# clock edge.
#
# This testbench is run unchanged by the sv and the avl flavours. It drives clock
# and reset, then on each rising edge builds one item, randomizes it and writes
# its fields onto the signals. The RTL in ../rtl/bitwise_128.sv is likewise
# shared, and checks that every value it receives satisfies the constraint its
# position carries.
#
# For the sv flavour the loop below drives nothing: the RTL builds, randomizes and
# sends the item itself, from inside the module. The harness - the clock, the
# reset and the same number of edges - is identical either way.
#
# The constraints are the bitwise ones of randomization/bitwise, rotated over the
# variables, so that what is being solved here is a known quantity that can be
# read against that benchmark's per randomization figure.


import os

import avl
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import And, Extract, LShR

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Width of every variable, matching WIDTH in the RTL.
WIDTH = 32

# The four bitwise constraints, in the order they rotate over the variables.
# Variable i carries KINDS[i % 4] - see the checker in the RTL.
KINDS = [
    # Masked equality - fixes the bottom byte, leaves the rest free.
    lambda x: (x & 0x000000FF) == 0x0000005A,
    # Or - forces the top half to all ones, leaves the bottom half free.
    lambda x: (x | 0x0000FFFF) == 0xFFFFFFFF,
    # Xor against a pattern, masked to the top half.
    lambda x: ((x ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000,
    # Logical shift right, then masked equality, and a bit select.
    lambda x: And((LShR(x, 8) & 0x000000FF) == 0x0000003C, Extract(31, 28, x) == 0b1010),
]


class bitwise_128_item(avl.SequenceItem):
    """One transaction - a constrained variable per signal the benchmark drives."""

    def __init__(self, name, parent=None, signals=1, width=WIDTH):
        super().__init__(name, parent)

        self.d = [avl.Logic(0, width=width, fmt=hex) for _ in range(signals)]

        for i, field in enumerate(self.d):
            self.add_constraint(f"c_{i % 4}_{i}", KINDS[i % 4], field)


def holds(index: int, value: int) -> bool:
    """Whether a drawn value satisfies the constraint its position carries.

    The same four constraints as KINDS, in plain Python - the point of checking
    them here as well as in the RTL is that these are written independently of
    the expressions the solver was given.
    """
    kind = index % 4
    if kind == 0:
        return (value & 0x000000FF) == 0x0000005A
    if kind == 1:
        return (value | 0x0000FFFF) == 0xFFFFFFFF
    if kind == 2:
        return ((value ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000
    return ((value >> 8) & 0x000000FF) == 0x0000003C and (value >> 28) == 0b1010


@cocotb.test
async def test(dut):
    iterations = int(os.environ.get("BENCH_ITERATIONS", 200))
    burst = int(os.environ.get("BENCH_BURST", 1))
    signals = int(os.environ.get("BENCH_SIGNALS", 128))
    flavour = os.environ.get("BENCH_FLAVOUR", "avl")

    # Cleared for the baseline run, which measures the harness on its own.
    enable = os.environ.get("BENCH_RANDOMIZE", "1") == "1"

    edges = max(iterations // burst, 1)

    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, unit="ns").start())

    dut.rst_n.value = 0
    for _ in range(RESET_CYCLES):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    # Resolved once, before the measurement: a driver holds the interface it
    # drives rather than looking it up per transaction, and what is being
    # measured is the solve and the writes, not the lookup.
    handles = [dut.d[i] for i in range(signals)]

    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                # A fresh item per edge, the way a testbench builds a fresh
                # sequence item per transaction rather than refilling one - which
                # would let a solver amortize its analysis across draws in a way
                # real code never gets the benefit of.
                item = bitwise_128_item("item", signals=signals)
                item.randomize()

                # Send it. Each write crosses into the simulator; the RTL checks
                # what arrives, and the constraints are checked here too, against
                # expressions written independently of the ones solved.
                for i, (handle, field) in enumerate(zip(handles, item.d, strict=True)):
                    value = field.value
                    assert holds(i, value), \
                        f"c_{i % 4} violated : d[{i}] = {value:#010x} on iteration {count}"
                    handle.value = value

                count += 1

    # Every flavour must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    # And the items must actually have reached the RTL, which checked every
    # constraint as they arrived. A write lands after the edge it was made on and
    # the counter is non-blocking, so the RTL is two edges behind when it is read.
    if enable:
        checked = int(dut.checked.value)
        assert checked >= edges - 2, (
            f"the RTL saw {checked} items, expected at least {edges - 2}"
        )

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl signals={signals} iterations={count}")
