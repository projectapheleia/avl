# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
import os


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.b = avl.Logic(0, width=8, fmt=hex)
        self.a = avl.Logic(0, width=8, fmt=hex)
        self.add_constraint("c_0", lambda x: x == 100, self.a)
        self.add_constraint("c_1", lambda x: x == 200, self.a)
        self.add_constraint("c_2", lambda x: x == 200, self.b)

@cocotb.test(expect_error=Exception)
async def test0(dut):
    os.environ["AVL_CONSTRAINT_DEBUG"] = "1"
    e = example_env("env", None)
    e.randomize()

@cocotb.test(expect_error=Exception)
async def test1(dut):
    os.environ["AVL_CONSTRAINT_DEBUG"] = "1"
    e = example_env("env", None)
    e.b.add_constraint("c_0", lambda x: x == 0x00)
    e.b.add_constraint("c_1", lambda x: x == 0x11)
    e.b.randomize()
