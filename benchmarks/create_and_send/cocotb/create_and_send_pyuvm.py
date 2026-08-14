# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Create and send - the cost of building one transaction object and driving it
# onto the RTL. Nothing here is randomized; the values are a counter.
#
# This is the pyuvm flavour: the same RTL, the same clock, the same reset and the
# same loop as ../cocotb/create_and_send.py, with the item written as a
# uvm_sequence_item and the loop hosted in the run_phase of a pyuvm test. Only
# the item and the writes differ.
#
# pyvsc is deliberately absent. It is what the randomization benchmarks compare
# against, because it is what a pyuvm testbench randomizes with, but nothing here
# is randomized and a pyuvm item that is not randomized carries plain Python
# attributes. Its fields therefore have no width of their own, which the loop
# below masks for by hand.


import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from pyuvm import uvm_root, uvm_sequence_item, uvm_test

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Width of every signal, matching WIDTH in the RTL.
WIDTH = 32
MASK = (1 << WIDTH) - 1


class create_and_send_item(uvm_sequence_item):
    """One transaction - a field per signal the benchmark drives."""

    def __init__(self, name, signals=1):
        super().__init__(name)

        self.d = [0] * signals


class create_and_send_bench_test(uvm_test):
    """The benchmark loop, driven from a pyuvm run_phase."""

    async def run_phase(self):
        self.raise_objection()

        dut = cocotb.top

        iterations = int(os.environ.get("BENCH_ITERATIONS", 1000))
        burst = int(os.environ.get("BENCH_BURST", 1))
        signals = int(os.environ.get("BENCH_SIGNALS", 1))

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

            if enable:
                for _ in range(burst):
                    # A fresh item per edge, the way a testbench builds a fresh
                    # sequence item per transaction rather than refilling one.
                    item = create_and_send_item("item", signals=signals)

                    base = count + 1
                    for i in range(signals):
                        item.d[i] = (base + i) & MASK

                    # Send it. Each write crosses into the simulator, which is
                    # the other half of what this benchmark measures.
                    for handle, value in zip(handles, item.d, strict=True):
                        handle.value = value

                    count += 1

        # Every flavour must have advanced the same number of clock cycles. The
        # counter is assigned non-blocking, so it lags the final edge by one.
        assert int(dut.cycles.value) >= edges - 1, (
            f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
        )

        # And the items must actually have reached the RTL, which checked them as
        # they arrived. A write lands after the edge it was made on and the
        # counter is non-blocking, so the RTL is two edges behind when it is read.
        if enable:
            checked = int(dut.checked.value)
            assert checked >= edges - 2, (
                f"the RTL saw {checked} items, expected at least {edges - 2}"
            )

        print(f"BENCH_RESULT flavour=pyuvm signals={signals} iterations={count}")

        self.drop_objection()


@cocotb.test
async def test(dut):
    await uvm_root().run_test("create_and_send_bench_test")
