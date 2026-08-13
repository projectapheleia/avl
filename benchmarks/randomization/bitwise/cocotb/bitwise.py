# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Bitwise constraints - and, or, xor, shift and bit select, and nothing else.
# No arithmetic, no sets, no implications.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/bitwise.sv is likewise shared.
#
# avl.Logic maps onto a z3 bit vector. Python's ">>" on a z3 bit vector is an
# arithmetic shift, so the logical shift of an unsigned SystemVerilog vector is
# spelled LShR here, and a bit select is spelled Extract.


import os

import avl
import cocotb
from bench_dump import dump_path, write_dump
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import And, Extract, LShR

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Fields recorded by the quality run.
FIELDS = [("a", 32), ("b", 32), ("c", 32), ("d", 32)]


class bitwise_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.a = avl.Logic(0, width=32, fmt=hex)
        self.b = avl.Logic(0, width=32, fmt=hex)
        self.c = avl.Logic(0, width=32, fmt=hex)
        self.d = avl.Logic(0, width=32, fmt=hex)

        # Masked equality - fixes the bottom byte, leaves the rest free.
        self.add_constraint("c_a", lambda a: (a & 0x000000FF) == 0x0000005A, self.a)

        # Or - forces the top half to all ones, leaves the bottom half free.
        self.add_constraint("c_b", lambda b: (b | 0x0000FFFF) == 0xFFFFFFFF, self.b)

        # Xor against a pattern, masked to the top half.
        self.add_constraint(
            "c_c", lambda c: ((c ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000, self.c
        )

        # Logical shift right, then masked equality, and a bit select.
        self.add_constraint(
            "c_d",
            lambda d: And((LShR(d, 8) & 0x000000FF) == 0x0000003C, Extract(31, 28, d) == 0b1010),
            self.d,
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
                item = bitwise_item("item")
                item.randomize()

                a, b, c, d = int(item.a), int(item.b), int(item.c), int(item.d)

                assert (a & 0x000000FF) == 0x0000005A, f"c_a violated : a={a:08x}"
                assert (b | 0x0000FFFF) == 0xFFFFFFFF, f"c_b violated : b={b:08x}"
                assert ((c ^ 0xA5A5A5A5) & 0xFFFF0000) == 0x5A5A0000, f"c_c violated : c={c:08x}"
                assert ((d >> 8) & 0x000000FF) == 0x0000003C and (d >> 28) == 0b1010, (
                    f"c_d violated : d={d:08x}"
                )

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
