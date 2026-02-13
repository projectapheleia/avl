# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
from z3 import And


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.fp16 = avl.Fp16(0.0)
        self.fp32 = avl.Fp32(0.0)
        self.fp64 = avl.Fp64(0.0)

        self.fp16.add_constraint("c_0", lambda x: And(x >= 0.0,   x <= 10.0))
        self.fp32.add_constraint("c_1", lambda x: And(x >= -1.1,  x <= 1.1))
        self.fp64.add_constraint("c_2", lambda x: And(x >= 100.0, x <= 200.0))

@cocotb.test
async def test(dut):
    e = example_env("env", None)
    for _ in range(500):
        e.randomize()
        assert e.fp16.value >= 0.0 and e.fp16.value <= 10.0
        assert e.fp32.value >= -1.1 and e.fp32.value <= 1.1
        assert e.fp64.value >= 100.0 and e.fp64.value <= 200.0

    for _ in range(500):
        e.fp16.randomize()
        e.fp32.randomize()
        e.fp64.randomize()
        assert e.fp16.value >= 0.0 and e.fp16.value <= 10.0
        assert e.fp32.value >= -1.1 and e.fp32.value <= 1.1
        assert e.fp64.value >= 100.0 and e.fp64.value <= 200.0
