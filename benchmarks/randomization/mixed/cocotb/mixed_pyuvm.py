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
# This is the pyuvm flavour of the benchmark: the same RTL, the same clock, the
# same reset and the same loop as ../cocotb/mixed.py, with the item written as a
# pyvsc randobj and the loop hosted in the run_phase of a pyuvm test. Only the
# randomization differs.
#
# pyvsc's rand_bit_t is an unsigned bit vector, so its comparisons, its "%" and
# its ">>" are already unsigned, and set membership is spelled as a rangelist -
# including on an expression, which is how c_page is written.


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
FIELDS = [("addr", 32), ("len", 16), ("kind", 8), ("attr", 8), ("secure", 1)]

KINDS = (0, 1, 2, 4, 8)
WINDOW = (0x10000000, 0x1FFFFFFF)
HOLE = (0x18000000, 0x18FFFFFF)
PAGES = (0x10, 0x11, 0x1F)
SECURE_BASE = 0x1F000000


@vsc.randobj
class mixed_item:
    def __init__(self):
        self.addr = vsc.rand_bit_t(32)
        self.len = vsc.rand_bit_t(16)
        self.kind = vsc.rand_bit_t(8)
        self.attr = vsc.rand_bit_t(8)
        self.secure = vsc.rand_bit_t(1)

    # List - a set of discrete values.
    @vsc.constraint
    def c_kind(self):
        self.kind.inside(vsc.rangelist(*KINDS))

    # Arithmetic - a bounded range.
    @vsc.constraint
    def c_len(self):
        self.len >= 1
        self.len <= 4096

    # Arithmetic - alignment, by modulo.
    @vsc.constraint
    def c_align(self):
        self.addr % 4 == 0

    # List - a window, with a reserved hole excluded from it.
    @vsc.constraint
    def c_addr(self):
        self.addr.inside(vsc.rangelist(vsc.rng(WINDOW[0], WINDOW[1])))
        self.addr.not_inside(vsc.rangelist(vsc.rng(HOLE[0], HOLE[1])))

    # Bitwise - attr shares its low nibble with kind.
    @vsc.constraint
    def c_attr(self):
        (self.attr & 0x0F) == (self.kind & 0x0F)

    # Bitwise - the page the address falls in, by shift.
    @vsc.constraint
    def c_page(self):
        (self.addr >> 24).inside(vsc.rangelist(*PAGES))

    # Implication - one kind implies a single beat.
    @vsc.constraint
    def c_kind0(self):
        with vsc.implies(self.kind == 0):
            self.len == 1

    # Dependency - if / else, so both branches are constrained.
    @vsc.constraint
    def c_secure(self):
        with vsc.if_then(self.addr >= SECURE_BASE):
            self.secure == 1
        with vsc.else_then:
            self.secure == 0

    # Arithmetic - an inequality.
    @vsc.constraint
    def c_attr_ne(self):
        self.attr != 0xFF


class mixed_bench_test(uvm_test):
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
                    item = mixed_item()
                    item.randomize()

                    addr = item.addr
                    length = item.len
                    kind = item.kind
                    attr = item.attr
                    secure = item.secure

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
    await uvm_root().run_test("mixed_bench_test")
