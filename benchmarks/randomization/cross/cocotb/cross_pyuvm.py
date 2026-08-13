# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Cross constraints - four variables whose legal values depend on each other,
# mixing arithmetic, bitwise and list constructs in a single solve.
#
# The dependency runs a -> b -> c -> d. "a" is anchored by a set, "b" is bounded
# relative to "a", "c" is built bitwise out of "a" and "b" and ordered against
# "b", and "d" is drawn from the set of the other three. Nothing here can be
# solved a variable at a time.
#
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/cross.py, with the item written as a
# pyvsc randobj and the loop hosted in the run_phase of a pyuvm test. Only the
# randomization differs.
#
# pyvsc's rand_bit_t is an unsigned bit vector, so its comparisons and its ">>"
# are already unsigned, and a rangelist may hold references to other fields -
# which is how c_d is written.


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

RANGES = [(100, 200), (1000, 1100)]
DISCRETE = 5000


@vsc.randobj
class cross_item:
    def __init__(self):
        self.a = vsc.rand_bit_t(32)
        self.b = vsc.rand_bit_t(32)
        self.c = vsc.rand_bit_t(32)
        self.d = vsc.rand_bit_t(32)

    # List - anchors a to a set of ranges and a discrete value.
    @vsc.constraint
    def c_a(self):
        self.a.inside(vsc.rangelist(*[vsc.rng(lo, hi) for lo, hi in RANGES], DISCRETE))

    # Arithmetic - b is bounded relative to a.
    @vsc.constraint
    def c_b(self):
        self.b > self.a
        self.b < self.a + 1000

    # Arithmetic - c is ordered against b.
    @vsc.constraint
    def c_c(self):
        self.c > self.b

    # Bitwise - the bottom byte of c is the xor of a and b.
    @vsc.constraint
    def c_mask(self):
        (self.c & 0x00FF) == ((self.a ^ self.b) & 0x00FF)

    # Bitwise and arithmetic - the top byte of c follows the top byte of a.
    @vsc.constraint
    def c_shift(self):
        (self.c >> 8) == (self.a >> 8) + 1

    # List - d is drawn from the other three fields.
    @vsc.constraint
    def c_d(self):
        self.d.inside(vsc.rangelist(self.a, self.b, self.c))


class cross_bench_test(uvm_test):
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
                    item = cross_item()
                    item.randomize()

                    a, b, c, d = item.a, item.b, item.c, item.d

                    assert any(lo <= a <= hi for lo, hi in RANGES) or a == DISCRETE, (
                        f"c_a violated : a={a} on iteration {count}"
                    )
                    assert a < b < ((a + 1000) & 0xFFFFFFFF), f"c_b violated : a={a} b={b}"
                    assert c > b, f"c_c violated : b={b} c={c}"
                    assert (c & 0x00FF) == ((a ^ b) & 0x00FF), (
                        f"c_mask violated : a={a:04x} b={b:04x} c={c:04x}"
                    )
                    assert (c >> 8) == (((a >> 8) + 1) & 0xFFFFFFFF), (
                        f"c_shift violated : a={a:04x} c={c:04x}"
                    )
                    assert d in (a, b, c), f"c_d violated : a={a} b={b} c={c} d={d}"

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
    await uvm_root().run_test("cross_bench_test")
