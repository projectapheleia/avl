# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import copy

import avl
import cocotb
from cocotb.triggers import Timer
from z3 import ULT


class packed_struct_t(avl.Struct):
    single_bit : avl.Bool = avl.Bool(False)
    multi_bit : avl.Uint32 = avl.Uint32(0)
    state_enum : avl.Enum = avl.Enum("S0", {"S0" : 0, "S1" : 1, "S2" : 2})

class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.s0 = packed_struct_t()
        self.s1 = packed_struct_t()

    async def run_phase(self):

        self.raise_objection()

        for i in range(10):
            await Timer(10, unit="ns")

            self.dut.value = self.s0.to_bits()

            await Timer(1, "ns")
            self.s1.from_bits(self.dut)

            assert i%2 == self.s0.single_bit == self.s1.single_bit
            assert i   == self.s0.multi_bit == self.s1.multi_bit
            assert self.s0.state_enum == self.s1.state_enum


            self.s0.single_bit += 1
            self.s0.multi_bit += 1

            if bool(self.s0.single_bit):
                self.s0.state_enum.value = "S2"
            else:
                self.s0.state_enum.value = "S0"


        # Test randomization
        self.s0_copy = copy.deepcopy(self.s0)
        self.s0.multi_bit.add_constraint("c_multi_bit", lambda x: ULT(x,100))
        self.s0_copy.multi_bit.add_constraint("c_multi_bit", lambda x: x == 200)
        self.s0.single_bit.value = 0
        self.s0.multi_bit.value = 0
        self.s0.state_enum.value = "S0"

        for _ in range(10):

            await Timer(10, unit="ns")
            self.randomize()

            self.s0.to_hdl(self.dut)

            await Timer(1, "ns")
            self.s1.from_hdl(self.dut)

            assert self.s0.single_bit == self.s1.single_bit
            assert self.s0.multi_bit == self.s1.multi_bit
            assert self.s0.multi_bit < 100
            assert self.s0.state_enum == self.s1.state_enum

            assert self.s0_copy.multi_bit.value == 200
        await Timer(10, unit="ns")

        # Test the .value shortcut
        self.s0.value = 0
        assert self.s0.single_bit.value == 0 and self.s0.multi_bit.value == 0 and self.s0.state_enum.value == 0
        assert self.s0.value == 0

        self.s0.value = 1
        assert self.s0.single_bit.value == 0 and self.s0.multi_bit.value == 0 and self.s0.state_enum.value == 1
        assert self.s0.value == 1
        self.drop_objection()

@cocotb.test
async def test(dut):
    e = example_env("env", None)
    e.dut = dut.data

    await e.start()
