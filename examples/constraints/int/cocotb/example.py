# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
from z3 import And, Extract


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.a = avl.Uint8(0, fmt=hex)
        self.add_constraint("c_0", lambda x: x != 0, self.a)

        self.b = avl.Int32(0, fmt=str)
        self.add_constraint("c_1", lambda x: And(x > -2, x < 10), self.b)

        self.c = avl.Uint8(0, fmt=hex)
        self.add_constraint("c_2", lambda x: x & 0x0f == 0x03, self.c)

        self.d = avl.Uint32(0, fmt=hex)
        self.d.add_constraint("c_3", lambda x: Extract(7, 0, x) == 0b0000_0110)

@cocotb.test
async def test(dut):
    e = example_env("env", None)
    for _ in range(100):
        e.randomize()
        assert e.a != 0
        assert e.b > -2 and e.b < 10
        assert e.c & 0x0f == 0x3
        assert e.d & 0x0000000f == 0x6
