# Copyright 2024 Apheleia
#
# Description:
# Apheleia factory example


import avl
import cocotb


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.a = avl.Factory.get_variable(f"{self.get_full_name()}.a")

        if self.a != 100:
            self.error(f"Expected a to be 100, got {self.a}")


        self.b = avl.Factory.get_variable(f"{self.get_full_name()}.b", 200)

        if self.b != 200:
            self.error(f"Expected b to be 200, got {self.b}")
        

        try:
            avl.Factory.get_variable(f"{self.get_full_name()}.c")
            missing_variable_errors = False
        except KeyError:
            missing_variable_errors = True

        if missing_variable_errors is False:
            self.error(f"Excepted missing varaible to error. It did not.")


@cocotb.test
async def test(dut):
    avl.Factory.set_variable("env.a", 100)

    e = example_env("env", None)
    await e.start()
