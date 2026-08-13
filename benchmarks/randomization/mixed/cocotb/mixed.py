# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library (AVL) Benchmark
#
# Mixed constraints - the widest spread of constructs in the suite, on an item
# shaped like a real bus transaction. Ranges, sets, exclusion, alignment,
# bitwise masking, a shift, an implication, an if / else dependency and an
# inequality, over fields of four different widths.
#
# Where the other benchmarks isolate one category, this one is deliberately
# representative: it is the closest thing here to everyday constrained random
# code.
#
# This testbench is run unchanged by both flavours of the benchmark. It drives
# clock and reset, then randomizes once per rising edge for the requested number
# of iterations. The RTL in ../rtl/mixed.sv is likewise shared.
#
# avl.Logic maps onto a z3 bit vector. Its comparison operators and its "%" and
# ">>" are signed by default, so the unsigned forms of SystemVerilog are spelled
# UGE / UGT / ULE / ULT, URem and LShR here.


import os

import avl
import cocotb
from bench_dump import dump_path, write_dump
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from z3 import UGE, ULE, And, If, Implies, LShR, Not, Or, URem

CLOCK_PERIOD_NS = 1
RESET_CYCLES = 5

# Fields recorded by the quality run.
FIELDS = [("addr", 32), ("len", 16), ("kind", 8), ("attr", 8), ("secure", 1)]

KINDS = (0, 1, 2, 4, 8)
WINDOW = (0x10000000, 0x1FFFFFFF)
HOLE = (0x18000000, 0x18FFFFFF)
PAGES = (0x10, 0x11, 0x1F)
SECURE_BASE = 0x1F000000


class mixed_item(avl.Object):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Logic(0, width=32, fmt=hex)
        self.len = avl.Logic(0, width=16, fmt=hex)
        self.kind = avl.Logic(0, width=8, fmt=hex)
        self.attr = avl.Logic(0, width=8, fmt=hex)
        self.secure = avl.Logic(0, width=1, fmt=bin)

        # List - a set of discrete values.
        self.add_constraint("c_kind", lambda kind: Or([kind == v for v in KINDS]), self.kind)

        # Arithmetic - a bounded range.
        self.add_constraint(
            "c_len", lambda length: And(UGE(length, 1), ULE(length, 4096)), self.len
        )

        # Arithmetic - alignment, by modulo.
        self.add_constraint("c_align", lambda addr: URem(addr, 4) == 0, self.addr)

        # List - a window, with a reserved hole excluded from it.
        self.add_constraint(
            "c_addr",
            lambda addr: And(
                UGE(addr, WINDOW[0]),
                ULE(addr, WINDOW[1]),
                Not(And(UGE(addr, HOLE[0]), ULE(addr, HOLE[1]))),
            ),
            self.addr,
        )

        # Bitwise - attr shares its low nibble with kind.
        self.add_constraint(
            "c_attr", lambda kind, attr: (attr & 0x0F) == (kind & 0x0F), self.kind, self.attr
        )

        # Bitwise - the page the address falls in, by shift.
        self.add_constraint(
            "c_page", lambda addr: Or([LShR(addr, 24) == p for p in PAGES]), self.addr
        )

        # Implication - one kind implies a single beat.
        self.add_constraint(
            "c_kind0",
            lambda kind, length: Implies(kind == 0, length == 1),
            self.kind,
            self.len,
        )

        # Dependency - if / else, so both branches are constrained.
        self.add_constraint(
            "c_secure",
            lambda addr, secure: If(UGE(addr, SECURE_BASE), secure == 1, secure == 0),
            self.addr,
            self.secure,
        )

        # Arithmetic - an inequality.
        self.add_constraint("c_attr_ne", lambda attr: attr != 0xFF, self.attr)


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
                item = mixed_item("item")
                item.randomize()

                addr = int(item.addr)
                length = int(item.len)
                kind = int(item.kind)
                attr = int(item.attr)
                secure = int(item.secure)

                assert kind in KINDS, f"c_kind violated : kind={kind} on iteration {count}"
                assert 1 <= length <= 4096, f"c_len violated : len={length}"
                assert addr % 4 == 0, f"c_align violated : addr={addr:08x}"
                assert WINDOW[0] <= addr <= WINDOW[1] and not (HOLE[0] <= addr <= HOLE[1]), (
                    f"c_addr violated : addr={addr:08x}"
                )
                assert (attr & 0x0F) == (kind & 0x0F), (
                    f"c_attr violated : kind={kind:02x} attr={attr:02x}"
                )
                assert (addr >> 24) in PAGES, f"c_page violated : addr={addr:08x}"
                assert kind != 0 or length == 1, f"c_kind0 violated : len={length}"
                assert secure == (1 if addr >= SECURE_BASE else 0), (
                    f"c_secure violated : addr={addr:08x} secure={secure}"
                )
                assert attr != 0xFF, f"c_attr_ne violated : attr={attr:02x}"

                if samples is not None:
                    samples.append((addr, length, kind, attr, secure))

                checksum += addr + length + kind + attr + secure
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
