# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) comparison benchmark - pyuvm flavour.
#
# The same RTL, the same clock, the same reset and the same loop as
# benchmark.py, with the classes written as pyvsc randobjs and the loop hosted
# in the run_phase of a pyuvm test. Only the work under test differs.

import os

import cocotb

# The classes are imported at module scope, so that defining them costs the same
# in the baseline run as in the measured one and cancels out of the difference
# between the two.
from classes_pyuvm import CLASSES
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from pyuvm import uvm_root, uvm_test

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5


class comparison_bench_test(uvm_test):
    """The benchmark loop, driven from a pyuvm run_phase."""

    async def run_phase(self):
        self.raise_objection()

        dut = cocotb.top

        iterations = int(os.environ.get("BENCH_ITERATIONS", 256))
        burst = int(os.environ.get("BENCH_BURST", 1))

        # How many of the classes take part, the rest left unused.
        classes = CLASSES[:int(os.environ.get("BENCH_CLASSES", len(CLASSES)))]

        # Cleared for the baseline run, which measures the harness on its own.
        enable = os.environ.get("BENCH_WORK", "1") == "1"

        edges = max(iterations // burst, 1)

        cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, unit="ns").start())

        dut.rst_n.value = 0
        for _ in range(RESET_CYCLES):
            await RisingEdge(dut.clk)
        dut.rst_n.value = 1

        checksum = 0
        count = 0

        for _ in range(edges):
            await RisingEdge(dut.clk)

            if enable:
                for _ in range(burst):
                    # A fresh item per iteration, the classes taken in turn -
                    # see benchmark.py.
                    item = classes[count % len(classes)]()
                    item.randomize()
                    checksum += item.check()
                    count += 1

        # Every flavour must have advanced the same number of clock cycles. The
        # counter is assigned non-blocking, so it lags the final edge by one.
        assert int(dut.cycles.value) >= edges - 1, (
            f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
        )

        print(f"BENCH_RESULT flavour=pyuvm iterations={count} checksum={checksum}")

        self.drop_objection()


@cocotb.test
async def test(dut):
    await uvm_root().run_test("comparison_bench_test")
