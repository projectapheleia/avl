# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
from z3 import ULT


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.a = avl.Logic(0, width=8, fmt=hex)

        # Simple base constarint
        self.add_constraint("c_0", lambda x: x >= 10, self.a)


@cocotb.test
async def test(dut):
    e = example_env("env", None)

    # Simple first test
    e.randomize()
    assert e.a >= 10

    # Add hard constraint
    for _ in range(100):
        e.randomize(hard=[(lambda x: x > 100, e.a)])
        assert e.a > 100

    # Add conflicting hard constraint - ok as last one was removed
    for _ in range(100):
        e.randomize(hard=[(lambda x: ULT(x,100), e.a)])
        assert e.a < 100

    # Add soft constraint - ok as no conflict
    for _ in range(100):
        e.randomize(soft=[(lambda x: x == 11, e.a)])
        assert e.a == 11

    # Add a soft constraint that conflicts with the hard constraint
    for _ in range(100):
        e.randomize(hard=[(lambda x: x == 12, e.a)], soft=[(lambda x: x == 11, e.a)])
        assert e.a == 12

    # Add a constraint directly to the variable
    for _ in range(100):
        e.a.randomize(hard=[lambda x: x == 13])
        assert e.a == 13
