# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Implication and dependency constraints - one random field steering the legal
# values of the others, through "->" and through if / else.
#
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/implication.py, with the item
# written as a pyvsc randobj and the loop hosted in the run_phase of a pyuvm
# test. Only the randomization differs.
#
# pyvsc spells SystemVerilog's "->" as a with vsc.implies(...) block, and a
# constraint written as if / else - which constrains both branches - as
# vsc.if_then / vsc.else_then.


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
FIELDS = [("mode", 8), ("addr", 16), ("len", 8), ("valid", 1)]


@vsc.randobj
class implication_item:
    def __init__(self):
        self.mode = vsc.rand_bit_t(8)
        self.addr = vsc.rand_bit_t(16)
        self.len = vsc.rand_bit_t(8)
        self.valid = vsc.rand_bit_t(1)

    # The field everything else depends on.
    @vsc.constraint
    def c_mode(self):
        self.mode <= 3

    # Each mode implies a different shape of transaction.
    @vsc.constraint
    def c_0(self):
        with vsc.implies(self.mode == 0):
            self.len == 0

    @vsc.constraint
    def c_1(self):
        with vsc.implies(self.mode == 1):
            self.len <= 16

    @vsc.constraint
    def c_2(self):
        with vsc.implies(self.mode == 2):
            self.addr >= 0x1000
            self.addr < 0x2000

    @vsc.constraint
    def c_3(self):
        with vsc.implies(self.mode == 3):
            self.len > 200

    # A two sided dependency - if / else, rather than implication.
    @vsc.constraint
    def c_valid(self):
        with vsc.if_then(self.len > 100):
            self.valid == 1
        with vsc.else_then:
            self.valid == 0


class implication_bench_test(uvm_test):
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
                    item = implication_item()
                    item.randomize()

                    mode = item.mode
                    addr = item.addr
                    length = item.len
                    valid = item.valid

                    assert mode <= 3, f"c_mode violated : mode={mode} on iteration {count}"
                    assert mode != 0 or length == 0, f"c_0 violated : len={length}"
                    assert mode != 1 or length <= 16, f"c_1 violated : len={length}"
                    assert mode != 2 or 0x1000 <= addr < 0x2000, f"c_2 violated : addr={addr:04x}"
                    assert mode != 3 or length > 200, f"c_3 violated : len={length}"
                    assert valid == (1 if length > 100 else 0), (
                        f"c_valid violated : len={length} valid={valid}"
                    )

                    if samples is not None:
                        samples.append((mode, addr, length, valid))

                    checksum += mode + addr + length + valid
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
    await uvm_root().run_test("implication_bench_test")
