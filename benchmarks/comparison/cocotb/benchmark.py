# Copyright 2026 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) comparison benchmark.
#
# Run unchanged by three of the four flavours - the local AVL, the released
# avl-core and SystemVerilog - because the harness is identical for all of them
# and only the work under test differs. It drives the clock and the reset, then
# creates, constrains and randomizes one item per rising edge.
#
#   sv                 the work happens in the RTL, so the loop here does
#                      nothing but advance the clock
#   the AVL flavours   the work happens here, on the classes in classes_avl.py
#
# pyuvm has a testbench of its own, benchmark_pyuvm.py, because its loop has to
# live inside a uvm_test. It drives the same clock, the same reset and the same
# number of edges.

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

FLAVOUR = os.environ.get("BENCH_FLAVOUR", "avl")

# Imported at module scope, so that defining the classes costs the same in the
# baseline run as in the measured one and cancels out of the difference between
# them. The SystemVerilog flavour has its classes compiled into the model and
# never imports these.
if FLAVOUR == "sv":
    CLASSES = ()
else:
    from classes_avl import CLASSES


@cocotb.test
async def test(dut):
    iterations = int(os.environ.get("BENCH_ITERATIONS", 256))
    burst = int(os.environ.get("BENCH_BURST", 1))

    # How many of the classes take part, the rest left unused - see classes_avl.py.
    classes = CLASSES[:int(os.environ.get("BENCH_CLASSES", len(CLASSES)))] if CLASSES else ()

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

        if classes and enable:
            for _ in range(burst):
                # A fresh item per iteration, the way a testbench builds a fresh
                # sequence item per transaction, rather than one item reused -
                # which would let an implementation amortize the work of
                # analysing a class across draws. The classes are taken in turn,
                # so a run of N iterations over N classes builds one of each.
                item = classes[count % len(classes)]("item")
                item.randomize()
                checksum += item.check()
                count += 1

    # Every flavour must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if FLAVOUR != "sv":
        print(f"BENCH_RESULT flavour={FLAVOUR} iterations={count} checksum={checksum}")
