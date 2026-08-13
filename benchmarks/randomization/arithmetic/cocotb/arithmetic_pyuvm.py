# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Arithmetic constraints - relational operators and addition / subtraction, and
# nothing else. No sets, no bitwise operators, no implications.
#
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/arithmetic.py, with the item written
# as a pyvsc randobj and the loop hosted in the run_phase of a pyuvm test. Only
# the randomization differs.
#
# pyvsc's rand_bit_t is an unsigned bit vector, so its comparison operators are
# already unsigned and the constraints read as they do in SystemVerilog.
# Arithmetic wraps at the width of the field, exactly as it does there.


import os

import cocotb
import vsc
from bench_dump import dump_path, write_dump
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from pyuvm import uvm_root, uvm_test

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Fields recorded by the quality run.
FIELDS = [("a", 16), ("b", 16), ("c", 16), ("d", 16)]


@vsc.randobj
class arithmetic_item:
    def __init__(self):
        self.a = vsc.rand_bit_t(16)
        self.b = vsc.rand_bit_t(16)
        self.c = vsc.rand_bit_t(16)
        self.d = vsc.rand_bit_t(16)

    # Every constraint here controls a single variable - there are no
    # dependencies between the fields. See the implication benchmark for those.

    # Bounded above and below.
    @vsc.constraint
    def c_a(self):
        self.a >= 100
        self.a <= 10000

    # Bounded above and below, both strict.
    @vsc.constraint
    def c_b(self):
        self.b > 250
        self.b < 20000

    # An inequality, and an upper bound.
    @vsc.constraint
    def c_c(self):
        self.c != 0
        self.c <= 1000

    # Addition inside the comparison. The upper bound keeps the sum clear of the
    # wrap at 16 bits.
    @vsc.constraint
    def c_d(self):
        self.d <= 30000
        self.d + 1000 > 5000


class arithmetic_bench_test(uvm_test):
    """The benchmark loop, driven from a pyuvm run_phase."""

    async def run_phase(self):
        self.raise_objection()

        dut = cocotb.top

        iterations = int(os.environ.get("BENCH_ITERATIONS", 1000))
        burst = int(os.environ.get("BENCH_BURST", 1))

        # Cleared for the baseline run, which measures the harness on its own.
        enable = os.environ.get("BENCH_RANDOMIZE", "1") == "1"

        edges = max(iterations // burst, 1)

        cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, unit="ns").start())

        dut.rst_n.value = 0
        for _ in range(RESET_CYCLES):
            await RisingEdge(dut.clk)
        dut.rst_n.value = 1

        # Only the quality run dumps.
        dump = dump_path()
        samples = [] if dump else None

        checksum = 0
        count = 0

        for _ in range(edges):
            await RisingEdge(dut.clk)

            if enable:
                for _ in range(burst):
                    # A fresh item per randomization, the way a testbench builds a
                    # fresh sequence item per transaction, rather than one item
                    # reused - which would let a solver amortize work across draws.
                    item = arithmetic_item()
                    item.randomize()

                    a, b, c, d = item.a, item.b, item.c, item.d

                    assert 100 <= a <= 10000, f"c_a violated : a={a} on iteration {count}"
                    assert 250 < b < 20000, f"c_b violated : b={b} on iteration {count}"
                    assert c != 0 and c <= 1000, f"c_c violated : c={c} on iteration {count}"
                    assert d <= 30000 and ((d + 1000) & 0xFFFF) > 5000, f"c_d violated : d={d}"

                    if samples is not None:
                        samples.append((a, b, c, d))

                    checksum += a + b + c + d
                    count += 1

        # Every flavour must have advanced the same number of clock cycles. The
        # counter is assigned non-blocking, so it lags the final edge by one.
        assert int(dut.cycles.value) >= edges - 1, (
            f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
        )

        if samples is not None:
            write_dump(dump, FIELDS, samples)

        print(f"BENCH_RESULT flavour=pyuvm iterations={count} checksum={checksum}")

        self.drop_objection()


@cocotb.test
async def test(dut):
    await uvm_root().run_test("arithmetic_bench_test")
