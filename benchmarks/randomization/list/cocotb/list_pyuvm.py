# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# List constraints - set membership with "inside", and nothing else. Value sets,
# range sets, exclusion, and a set built from other random fields.
#
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/list.py, with the item written as a
# pyvsc randobj and the loop hosted in the run_phase of a pyuvm test. Only the
# randomization differs.
#
# pyvsc spells SystemVerilog's "inside" as a rangelist, and its negation as
# not_inside, so these constraints are close to a transcription of the ones in
# ../rtl/list.sv.


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

VALUES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
RANGES = [(100, 200), (500, 600), (5000, 5100)]
EXCLUDED = (0, 1000)
MIXED = (7, (20, 25), 9999)


@vsc.randobj
class list_item:
    def __init__(self):
        self.a = vsc.rand_bit_t(16)
        self.b = vsc.rand_bit_t(16)
        self.c = vsc.rand_bit_t(16)
        self.d = vsc.rand_bit_t(16)

    # Every constraint here controls a single variable - there are no
    # dependencies between the fields. See the implication benchmark for those.

    # A set of sixteen discrete values.
    @vsc.constraint
    def c_a(self):
        self.a.inside(vsc.rangelist(*VALUES))

    # A set of ranges.
    @vsc.constraint
    def c_b(self):
        self.b.inside(vsc.rangelist(*[vsc.rng(lo, hi) for lo, hi in RANGES]))

    # Exclusion - anything outside the range.
    @vsc.constraint
    def c_c(self):
        self.c.not_inside(vsc.rangelist(vsc.rng(EXCLUDED[0], EXCLUDED[1])))

    # A set mixing discrete values with a range.
    @vsc.constraint
    def c_d(self):
        self.d.inside(vsc.rangelist(MIXED[0], vsc.rng(MIXED[1][0], MIXED[1][1]), MIXED[2]))


class list_bench_test(uvm_test):
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
                    item = list_item()
                    item.randomize()

                    a, b, c, d = item.a, item.b, item.c, item.d

                    assert a in VALUES, f"c_a violated : a={a} on iteration {count}"
                    assert any(lo <= b <= hi for lo, hi in RANGES), f"c_b violated : b={b}"
                    assert not (EXCLUDED[0] <= c <= EXCLUDED[1]), f"c_c violated : c={c}"
                    assert d == MIXED[0] or MIXED[1][0] <= d <= MIXED[1][1] or d == MIXED[2], (
                        f"c_d violated : d={d}"
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
    await uvm_root().run_test("list_bench_test")
