# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Implication and dependency constraints - one random field steering the legal
# values of the others, through "->" and through if / else.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/implication.sv is likewise shared.
#
# SystemVerilog's "->" becomes Implies. A constraint written as if / else
# constrains both branches, so it becomes If. avl.Logic maps onto a z3 bit
# vector, whose comparison operators are signed by default, hence UGT / ULE.


import os

import avl
import cocotb
from bench_dump import dump_path, write_dump
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import UGE, UGT, ULE, ULT, And, If, Implies

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Fields recorded by the quality run.
FIELDS = [("mode", 8), ("addr", 16), ("len", 8), ("valid", 1)]


class implication_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.mode = avl.Logic(0, width=8, fmt=hex)
        self.addr = avl.Logic(0, width=16, fmt=hex)
        self.len = avl.Logic(0, width=8, fmt=hex)
        self.valid = avl.Logic(0, width=1, fmt=bin)

        # The field everything else depends on.
        self.add_constraint("c_mode", lambda mode: ULE(mode, 3), self.mode)

        # Each mode implies a different shape of transaction.
        self.add_constraint(
            "c_0", lambda mode, length: Implies(mode == 0, length == 0), self.mode, self.len
        )
        self.add_constraint(
            "c_1", lambda mode, length: Implies(mode == 1, ULE(length, 16)), self.mode, self.len
        )
        self.add_constraint(
            "c_2",
            lambda mode, addr: Implies(mode == 2, And(UGE(addr, 0x1000), ULT(addr, 0x2000))),
            self.mode,
            self.addr,
        )
        self.add_constraint(
            "c_3", lambda mode, length: Implies(mode == 3, UGT(length, 200)), self.mode, self.len
        )

        # A two sided dependency - if / else, rather than implication.
        self.add_constraint(
            "c_valid",
            lambda length, valid: If(UGT(length, 100), valid == 1, valid == 0),
            self.len,
            self.valid,
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
                item = implication_item("item")
                item.randomize()

                mode = int(item.mode)
                addr = int(item.addr)
                length = int(item.len)
                valid = int(item.valid)

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

    # Both flavours must have advanced the same number of clock cycles. The
    # counter is assigned non-blocking, so it lags the final edge by one.
    assert int(dut.cycles.value) >= edges - 1, (
        f"harness ran {int(dut.cycles.value)} cycles, expected at least {edges - 1}"
    )

    if samples is not None:
        write_dump(dump, FIELDS, samples)

    if flavour == "avl":
        print(f"BENCH_RESULT flavour=avl iterations={count} checksum={checksum}")
