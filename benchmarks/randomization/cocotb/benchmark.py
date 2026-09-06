# Copyright 2026 Apheleia
#
# Description:
# Testbench for the AVL randomization benchmark.
#
# Models what a real testbench does: build one constrained transaction and
# randomize it over and over. Timing is taken in-process with perf_counter and
# printed as JSON, so the simulator, make and import costs are not measured.

import json
import os
import sys
import time

import avl
import cocotb
from z3 import UGE, ULE, And, Implies, LShR, Or, ZeroExt

OPCODE = {"NOP": 0, "READ": 1, "WRITE": 2, "FENCE": 3}
BURST = {"FIXED": 0, "INCR": 1, "WRAP": 2}


class Packet(avl.Transaction):
    """A bus packet with arithmetic, bitwise and select constraints.

    Covers every variable family AVL supports - logic, unsigned, signed,
    enumerated and floating point - and the three kinds of constraint a
    testbench typically writes over them.
    """

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Uint32(0, fmt=hex)
        self.data = avl.Logic(0, width=64, fmt=hex)
        self.length = avl.Uint8(0)
        self.offset = avl.Int16(0)
        self.opcode = avl.Enum("NOP", OPCODE)
        self.burst = avl.Enum("INCR", BURST)
        self.gain = avl.Fp32(1.0)

        # Arithmetic - ranges, sums and products over the integer fields.
        # Z3's comparison operators are signed, so unsigned fields use ULE/UGE
        # and only the signed offset uses the plain operators.
        self.add_constraint("c_addr_range",
                            lambda a: And(UGE(a, 0x1000), ULE(a, 0xFFFF_0000)),
                            self.addr)
        self.add_constraint("c_length_range",
                            lambda n: And(UGE(n, 1), ULE(n, 64)),
                            self.length)
        self.add_constraint("c_offset_range",
                            lambda o: And(o >= -1024, o <= 1024),
                            self.offset)
        # length is 8 bit and addr is 32 bit, so widen before the arithmetic.
        self.add_constraint("c_no_wrap",
                            lambda a, n: ULE(a + ZeroExt(24, n) * 4, 0xFFFF_FF00),
                            self.addr, self.length)

        # Bitwise - alignment and field masking.
        self.add_constraint("c_addr_aligned",
                            lambda a: a & 0x3 == 0,
                            self.addr)
        self.add_constraint("c_data_tag",
                            lambda d: LShR(d, 56) == 0xA5,
                            self.data)
        self.add_constraint("c_length_pow2",
                            lambda n: (n & (n - 1)) == 0,
                            self.length)

        # Select - enumerated choices and the implications between them.
        self.add_constraint("c_opcode",
                            lambda o: Or(o == self.opcode.READ, o == self.opcode.WRITE),
                            self.opcode)
        self.add_constraint("c_fixed_is_single",
                            lambda b, n: Implies(b == self.burst.FIXED, n == 1),
                            self.burst, self.length)
        self.add_constraint("c_wrap_is_aligned",
                            lambda b, a: Implies(b == self.burst.WRAP, a & 0xF == 0),
                            self.burst, self.addr)

        # Floating point.
        self.add_constraint("c_gain_range",
                            lambda g: And(g >= 0.5, g <= 2.0),
                            self.gain)

        # Soft - a preference the solver relaxes rather than fails on.
        self.add_constraint("c_prefer_read",
                            lambda o: o == self.opcode.READ,
                            self.opcode, hard=False)


class IntegerPacket(avl.Transaction):
    """Integer fields only - randomization without the floating point solver."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Uint32(0, fmt=hex)
        self.length = avl.Uint8(0)
        self.offset = avl.Int16(0)

        self.add_constraint("c_addr_range",
                            lambda a: And(UGE(a, 0x1000), ULE(a, 0xFFFF_0000)),
                            self.addr)
        self.add_constraint("c_addr_aligned",
                            lambda a: a & 0x3 == 0,
                            self.addr)
        self.add_constraint("c_length_range",
                            lambda n: And(UGE(n, 1), ULE(n, 64)),
                            self.length)
        self.add_constraint("c_offset_range",
                            lambda o: And(o >= -1024, o <= 1024),
                            self.offset)


class TightPacket(avl.Transaction):
    """Fields held to narrow ranges, as a real testbench usually holds them.

    Where Packet leaves its fields most of their range, this pins the majority of
    their bits - an address within one page, a short burst, a handful of ids. The
    two shapes bound what constraint solving costs in practice.
    """

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Uint32(0, fmt=hex)
        self.data = avl.Logic(0, width=64, fmt=hex)
        self.length = avl.Uint16(0)
        self.id = avl.Uint8(0)
        self.opcode = avl.Enum("NOP", OPCODE)

        self.add_constraint("c_addr_page",
                            lambda a: And(UGE(a, 0x4000), ULE(a, 0x4FFF)),
                            self.addr)
        self.add_constraint("c_addr_aligned",
                            lambda a: a & 0x7 == 0,
                            self.addr)
        self.add_constraint("c_data_payload",
                            lambda d: And(UGE(d, 0x100), ULE(d, 0x1FF)),
                            self.data)
        self.add_constraint("c_length",
                            lambda n: And(UGE(n, 1), ULE(n, 16)),
                            self.length)
        self.add_constraint("c_id",
                            lambda i: ULE(i, 3),
                            self.id)
        self.add_constraint("c_opcode",
                            lambda o: Or(o == self.opcode.READ, o == self.opcode.WRITE),
                            self.opcode)


class PlainPacket(avl.Transaction):
    """The same fields with no constraints at all - the floor for comparison."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)

        self.addr = avl.Uint32(0, fmt=hex)
        self.data = avl.Logic(0, width=64, fmt=hex)
        self.length = avl.Uint8(0)
        self.offset = avl.Int16(0)
        self.opcode = avl.Enum("NOP", OPCODE)
        self.burst = avl.Enum("INCR", BURST)
        self.gain = avl.Fp32(1.0)


def measure(n, fn):
    """Run fn n times and return the mean time per call in seconds."""
    fn()  # warm up - the first call builds the Z3 variables
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) / n


def measurements(n):
    """Time each randomization pattern a testbench commonly uses."""
    packet = Packet("packet")
    yield "constrained", measure(n, packet.randomize)

    tight = TightPacket("tight")
    yield "tightly_constrained", measure(n, tight.randomize)

    integer = IntegerPacket("integer")
    yield "integer_only", measure(n, integer.randomize)

    plain = PlainPacket("plain")
    yield "unconstrained", measure(n, plain.randomize)

    # A fresh object each time, as a sequence generating new items would.
    counter = iter(range(n + 1))

    def fresh():
        Packet(f"p{next(counter)}").randomize()

    yield "fresh_object", measure(n, fresh)

    # A single variable randomized on its own.
    var = avl.Uint32(0)
    yield "single_var", measure(n, var.randomize)


@cocotb.test
async def test(dut):
    n = int(os.environ.get("AVL_BENCH_N", "1000"))
    results = dict(measurements(n))
    sys.stdout.write("AVL_BENCH_JSON " + json.dumps(results) + "\n")
