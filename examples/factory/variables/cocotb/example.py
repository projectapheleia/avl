# Copyright 2024 Apheleia
#
# Description:
# Apheleia factory example


import avl
import cocotb


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Get variable env.a in factory (set in the test method)
        self.a = avl.Factory.get_variable(f"{self.get_full_name()}.a") 

        if self.a != 100:
            self.error(f"Expected a to be 100, got {self.a}")

        # Get variable env.b from the factory. Because it was never set, use the default
        # value 200 instead.
        self.b = avl.Factory.get_variable(f"{self.get_full_name()}.b", default=200)

        if self.b != 200:
            self.error(f"Expected b to be 200, got {self.b}")



@cocotb.test
async def test(dut):
    avl.Factory.set_variable("env.a", 100)

    e = example_env("env", None)
    await e.start()
