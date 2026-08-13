# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Bitwise constraints - and, or, xor, shift and bit select, and nothing else.
# No arithmetic, no sets, no implications.
#
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/bitwise.py, with the item written as
# a pyvsc randobj and the loop hosted in the run_phase of a pyuvm test. Only the
# randomization differs.
#
# pyvsc's rand_bit_t is an unsigned bit vector, so ">>" is already a logical
# shift and the constraints read as they do in SystemVerilog. The bit select of
# the top nibble is written as a shift, which is what it amounts to.


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
FIELDS = [("a", 32), ("b", 32), ("c", 32), ("d", 32)]


@vsc.randobj
class bitwise_item:
    def __init__(self):
        self.a = vsc.rand_bit_t(32)
        self.b = vsc.rand_bit_t(32)
        self.c = vsc.rand_bit_t(32)
        self.d = vsc.rand_bit_t(32)

    # Masked equality - fixes the bottom byte, leaves the rest free.
    @vsc.constraint
    def c_a(self):
        (self.a & 0x000000FF) == 0x0000005A

    # Or - forces the top half to all ones, leaves the bottom half free.
    @vsc.constraint
    def c_b(self):
        (self.b | 0x0000FFFF) == 0xFFFFFFFF

    # Xor against a pattern, masked to the top half.
    @vsc.constraint
    def c_c(self):
        ((self.c ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000

    # Logical shift right, then masked equality, and a bit select.
    @vsc.constraint
    def c_d(self):
        ((self.d >> 8) & 0x000000FF) == 0x0000003C
        (self.d >> 28) == 0b1010


class bitwise_bench_test(uvm_test):
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
                    item = bitwise_item()
                    item.randomize()

                    a, b, c, d = item.a, item.b, item.c, item.d

                    assert (a & 0x000000FF) == 0x0000005A, f"c_a violated : a={a:08x}"
                    assert (b | 0x0000FFFF) == 0xFFFFFFFF, f"c_b violated : b={b:08x}"
                    assert ((c ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000, (
                        f"c_c violated : c={c:08x}"
                    )
                    assert ((d >> 8) & 0x000000FF) == 0x0000003C and (d >> 28) == 0b1010, (
                        f"c_d violated : d={d:08x}"
                    )

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
    await uvm_root().run_test("bitwise_bench_test")
