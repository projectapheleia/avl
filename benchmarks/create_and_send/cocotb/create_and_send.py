# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Create and send - the cost of building one transaction object and driving it
# onto the RTL. Nothing here is randomized; the values are a counter.
#
# This testbench is run unchanged by the sv and the avl flavours, and by every
# benchmark in the group - BENCH_SIGNALS says how many of the signals the model
# carries this one drives. It drives clock and reset, then on each rising edge
# builds one item and writes its fields onto the signals. The RTL in
# ../rtl/create_and_send.sv is likewise shared, and checks what arrives.
#
# For the sv flavour the loop below drives nothing: the RTL builds and sends the
# item itself, from inside the module. The harness - the clock, the reset and the
# same number of edges - is identical either way.


import os

import avl
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Width of every signal, matching WIDTH in the RTL.
WIDTH = 32


class create_and_send_item(avl.SequenceItem):
    """One transaction - a field per signal the benchmark drives.

    An AVL sequence item, built the way a testbench builds one: a field object
    per field, each carrying its own width. Nothing about it is randomized here,
    so what this costs is the item itself.
    """

    def __init__(self, name, parent=None, signals=1, width=WIDTH):
        super().__init__(name, parent)

        self.d = [avl.Logic(0, width=width, fmt=hex) for _ in range(signals)]


@cocotb.test
async def test(dut):
    iterations = int(os.environ.get("BENCH_ITERATIONS", 1000))
    burst = int(os.environ.get("BENCH_BURST", 1))
    signals = int(os.environ.get("BENCH_SIGNALS", 1))
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
    # measured is the writes, not the lookup.
    handles = [dut.d[i] for i in range(signals)]

    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                # A fresh item per edge, the way a testbench builds a fresh
                # sequence item per transaction rather than refilling one.
                item = create_and_send_item("item", signals=signals)

                base = count + 1
                for i, field in enumerate(item.d):
                    field.value = base + i

                # Send it. Each write crosses into the simulator, which is the
                # other half of what this benchmark measures.
                for handle, field in zip(handles, item.d, strict=True):
                    handle.value = field.value

                count += 1

    # Every flavour must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    # And the items must actually have reached the RTL, which checked them as
    # they arrived. A write lands after the edge it was made on and the counter
    # is non-blocking, so the RTL is two edges behind by the time it is read.
    if enable:
        checked = int(dut.checked.value)
        assert checked >= edges - 2, (
            f"the RTL saw {checked} items, expected at least {edges - 2}"
        )

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl signals={signals} iterations={count}")
