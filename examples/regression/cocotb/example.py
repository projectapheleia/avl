# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example

import avl
import cocotb


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.s = sub_comp_A("super_long_name", self)


class sub_comp_A(avl.Component):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.error("sub_comp_A should have been overriden by sub_comp_B")

class sub_comp_C(avl.Component):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.info("Hello from sub_comp_C")


class sub_comp_B(avl.Component):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.info("sub_comp_B successfully overriden sub_comp_A")


@cocotb.test
async def test0(dut):
    avl.Factory.set_override_by_instance("env.super_long_name", sub_comp_B)

    e = example_env("env", None)
    assert isinstance(e.s, sub_comp_B)
    await e.start()

@cocotb.test
async def test1(dut):
    avl.Factory.set_override_by_instance("env.super_long*", sub_comp_C)

    e = example_env("env", None)
    assert isinstance(e.s, sub_comp_C) # expecting sub_comp_C, but it will be sub_comp_B
    await e.start()
