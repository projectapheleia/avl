# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Randomize and send - a whole transaction, end to end: build an object of 128
# constrained variables, randomize it, and drive the result onto the RTL, once per
# clock edge.
#
# This is the pyuvm flavour: the same RTL, the same clock, the same reset and the
# same loop as ../cocotb/bitwise_128.py, with the item written as a pyvsc randobj
# and the loop hosted in the run_phase of a pyuvm test. Only the item and the
# solving differ.
#
# The variables are held as four lists of 32 rather than one list of 128, one list
# per constraint kind, because a pyvsc constraint cannot select a kind by index
# arithmetic over a single list - "foreach with if_then on i % 4" is rejected by
# the constraint builder. The problem posed to the solver is the same one: 128
# variables, 32 of each of the four kinds, and variable i still carries the kind
# that i % 4 gives it in the other flavours, since the drive loop below reads them
# back in that order.


import os

import cocotb
import vsc
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from pyuvm import uvm_root, uvm_test

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Width of every variable, matching WIDTH in the RTL.
WIDTH = 32

# Variables per constraint kind. Four kinds, so four times this is the item.
PER_KIND = 32

# The minor edit turnaround/bitwise_128 measures - one line of the testbench,
# changed. Only ever printed, so an edit cannot alter what the run does or how
# long it takes; the whole cost of changing it is whatever has to be built again
# before it can run, which for a Python testbench is this module and nothing
# else. The sv flavour carries the same line as a compile time define, in the
# RTL, where its testbench lives. The value differs with every edit so that no
# two of them are the same edit - see scripts/bench_edit.py.
REVISION = int(os.environ.get("BENCH_EDIT") or 1)


@vsc.randobj
class bitwise_128_item:
    def __init__(self):
        self.d0 = vsc.rand_list_t(vsc.uint32_t(), PER_KIND)
        self.d1 = vsc.rand_list_t(vsc.uint32_t(), PER_KIND)
        self.d2 = vsc.rand_list_t(vsc.uint32_t(), PER_KIND)
        self.d3 = vsc.rand_list_t(vsc.uint32_t(), PER_KIND)

    # Masked equality - fixes the bottom byte, leaves the rest free.
    @vsc.constraint
    def c_0(self):
        with vsc.foreach(self.d0) as v:
            (v & 0x000000FF) == 0x0000005A

    # Or - forces the top half to all ones, leaves the bottom half free.
    @vsc.constraint
    def c_1(self):
        with vsc.foreach(self.d1) as v:
            (v | 0x0000FFFF) == 0xFFFFFFFF

    # Xor against a pattern, masked to the top half.
    @vsc.constraint
    def c_2(self):
        with vsc.foreach(self.d2) as v:
            ((v ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000

    # Logical shift right, then masked equality, and a bit select.
    @vsc.constraint
    def c_3(self):
        with vsc.foreach(self.d3) as v:
            ((v >> 8) & 0x000000FF) == 0x0000003C
            (v >> 28) == 0b1010


def holds(index: int, value: int) -> bool:
    """Whether a drawn value satisfies the constraint its position carries."""
    kind = index % 4
    if kind == 0:
        return (value & 0x000000FF) == 0x0000005A
    if kind == 1:
        return (value | 0x0000FFFF) == 0xFFFFFFFF
    if kind == 2:
        return ((value ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000
    return ((value >> 8) & 0x000000FF) == 0x0000003C and (value >> 28) == 0b1010


class bitwise_128_bench_test(uvm_test):
    """The benchmark loop, driven from a pyuvm run_phase."""

    async def run_phase(self):
        self.raise_objection()

        dut = cocotb.top

        iterations = int(os.environ.get("BENCH_ITERATIONS", 200))
        burst = int(os.environ.get("BENCH_BURST", 1))
        signals = int(os.environ.get("BENCH_SIGNALS", 128))

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

            if enable:
                for _ in range(burst):
                    # A fresh item per edge, the way a testbench builds a fresh
                    # sequence item per transaction rather than refilling one.
                    item = bitwise_128_item()
                    item.randomize()

                    # Variable i is the i//4'th of the list for kind i % 4 - see
                    # the note at the top on why they are held that way.
                    kinds = (item.d0, item.d1, item.d2, item.d3)

                    for i, handle in enumerate(handles):
                        value = kinds[i & 3][i >> 2]
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
        # constraint as they arrived. A write lands after the edge it was made on
        # and the counter is non-blocking, so the RTL is two edges behind by then.
        if enable:
            checked = int(dut.checked.value)
            assert checked >= edges - 2, (
                f"the RTL saw {checked} items, expected at least {edges - 2}"
            )

        print(f"BENCH_RESULT flavour=pyuvm signals={signals} iterations={count} "
              f"revision={REVISION}")

        self.drop_objection()


@cocotb.test
async def test(dut):
    await uvm_root().run_test("bitwise_128_bench_test")
