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
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/cross.sv is likewise shared.
#
# avl.Logic maps onto a z3 bit vector. Its comparison operators are signed by
# default, so unsigned comparisons are spelled UGT / ULT / UGE / ULE, and its
# ">>" is an arithmetic shift, so a logical shift is spelled LShR.


import os

import avl
import cocotb
from bench_dump import dump_path, write_dump
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import UGE, UGT, ULE, ULT, And, LShR, Or

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Fields recorded by the quality run.
FIELDS = [("a", 32), ("b", 32), ("c", 32), ("d", 32)]

RANGES = [(100, 200), (1000, 1100)]
DISCRETE = 5000


class cross_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.a = avl.Logic(0, width=32, fmt=hex)
        self.b = avl.Logic(0, width=32, fmt=hex)
        self.c = avl.Logic(0, width=32, fmt=hex)
        self.d = avl.Logic(0, width=32, fmt=hex)

        # List - anchors a to a set of ranges and a discrete value.
        self.add_constraint(
            "c_a",
            lambda a: Or([And(UGE(a, lo), ULE(a, hi)) for lo, hi in RANGES] + [a == DISCRETE]),
            self.a,
        )

        # Arithmetic - b is bounded relative to a.
        self.add_constraint(
            "c_b", lambda a, b: And(UGT(b, a), ULT(b, a + 1000)), self.a, self.b
        )

        # Arithmetic - c is ordered against b.
        self.add_constraint("c_c", lambda b, c: UGT(c, b), self.b, self.c)

        # Bitwise - the bottom byte of c is the xor of a and b.
        self.add_constraint(
            "c_mask", lambda a, b, c: (c & 0x00FF) == ((a ^ b) & 0x00FF), self.a, self.b, self.c
        )

        # Bitwise and arithmetic - the top byte of c follows the top byte of a.
        self.add_constraint(
            "c_shift", lambda a, c: LShR(c, 8) == LShR(a, 8) + 1, self.a, self.c
        )

        # List - d is drawn from the other three fields.
        self.add_constraint(
            "c_d", lambda a, b, c, d: Or(d == a, d == b, d == c), self.a, self.b, self.c, self.d
        )


@cocotb.test
async def test(dut):
    iterations = int(os.environ.get("BENCH_ITERATIONS", 1000))
    burst = int(os.environ.get("BENCH_BURST", 1))
    flavour = os.environ.get("BENCH_FLAVOUR", "avl")

    # Cleared for the baseline run, which measures the harness on its own.
    enable = os.environ.get("BENCH_RANDOMIZE", "1") == "1"

    edges = max(iterations // burst, 1)

    cocotb.start_soon(Clock(dut.clk, CLOCK_PERIOD_NS, unit="ns").start())

    dut.rst_n.value = 0
    for _ in range(RESET_CYCLES):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1

    # Only the quality run dumps, and only for the flavour randomizing here -
    # the sv flavour records its own draws from the RTL.
    dump = dump_path() if flavour == "avl" else None
    samples = [] if dump else None

    checksum = 0
    count = 0

    for _ in range(edges):
        await RisingEdge(dut.clk)

        if flavour == "avl" and enable:
            for _ in range(burst):
                # A fresh item per randomization, the way a testbench builds a
                # fresh sequence item per transaction, rather than one item
                # reused - which would let a solver amortize work across draws.
                item = cross_item("item")
                item.randomize()

                a, b, c, d = int(item.a), int(item.b), int(item.c), int(item.d)

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

    # Both flavours must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if samples is not None:
        write_dump(dump, FIELDS, samples)

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl iterations={count} checksum={checksum}")
