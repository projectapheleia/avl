# Copyright 2026 Apheleia
#
# Description:
# Testbench for the AVL object / variable creation benchmark.
#
# Times the construction of AVL objects and variables inside a real simulation.
# The timing is taken in-process with perf_counter and printed as JSON, so the
# simulator, make and import costs are not part of any sample.
#
# Several distinct transaction classes are used, cycled round-robin, so that any
# per-class caching in AVL has to work for varied classes rather than for one
# class constructed over and over.

import json
import os
import sys
import time

import avl
import cocotb

COLOUR = {"RED": 0, "GREEN": 1, "BLUE": 2, "AMBER": 3}
OPCODE = {"NOP": 0, "READ": 1, "WRITE": 2, "FENCE": 3}


class Packet(avl.Transaction):
    """Logic / Uint / Bool mix."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.addr = avl.Uint32(0)
        self.data = avl.Logic(0, width=64)
        self.length = avl.Uint8(0)
        self.last = avl.Bool(False)


class Descriptor(avl.Transaction):
    """Signed and enumerated fields."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.offset = avl.Int16(0)
        self.stride = avl.Int32(0)
        self.opcode = avl.Enum("NOP", OPCODE)
        self.colour = avl.Enum("RED", COLOUR)


class Sample(avl.Transaction):
    """Floating point fields."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.gain = avl.Fp32(1.0)
        self.offset = avl.Fp16(0.0)
        self.scale = avl.Fp64(1.0)
        self.valid = avl.Bool(True)


class Frame(avl.Transaction):
    """Everything at once - the class the headline figure is measured on."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.addr = avl.Uint32(0)
        self.data = avl.Logic(0, width=48)
        self.count = avl.Int16(0)
        self.opcode = avl.Enum("READ", OPCODE)
        self.gain = avl.Fp32(1.0)
        self.last = avl.Bool(False)


CLASSES = (Packet, Descriptor, Sample, Frame)


def measure(name, n, fn):
    """Run fn(i) n times and return the mean time per call in seconds."""
    fn(0)  # warm up - first call may import a deferred dependency
    start = time.perf_counter()
    for i in range(n):
        fn(i)
    return name, (time.perf_counter() - start) / n


def measurements(n):
    yield measure("object", n, lambda i: avl.Object(f"o{i}", None))
    yield measure("transaction", n, lambda i: avl.Transaction(f"t{i}", None))

    yield measure("var_logic", n, lambda i: avl.Logic(0, width=64))
    yield measure("var_uint", n, lambda i: avl.Uint32(0))
    yield measure("var_int", n, lambda i: avl.Int16(0))
    yield measure("var_bool", n, lambda i: avl.Bool(False))
    yield measure("var_enum", n, lambda i: avl.Enum("RED", COLOUR))
    yield measure("var_float", n, lambda i: avl.Fp32(1.0))

    yield measure("frame", n, lambda i: Frame(f"f{i}"))
    yield measure("mixed", n, lambda i: CLASSES[i & 3](f"m{i}"))


@cocotb.test
async def test(dut):
    n = int(os.environ.get("AVL_BENCH_N", "1000"))
    results = dict(measurements(n))
    sys.stdout.write("AVL_BENCH_JSON " + json.dumps(results) + "\n")
