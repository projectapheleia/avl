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

class struct_a_b_t(avl.Struct):
    var_a   : avl.Logic = avl.Logic(0, width = 4)
    var_b   : avl.Logic = avl.Logic(0, width = 4)

class struct_c_d_t(avl.Struct):
    var_c   : avl.Logic = avl.Logic(0, width = 4)
    var_d   : avl.Logic = avl.Logic(0, width = 4)

class struct_a_b_c_d_t(avl.Struct):
    struct_a_b : struct_a_b_t = struct_a_b_t()
    struct_c_d : struct_c_d_t = struct_c_d_t()

class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.s0 = packed_struct_t()
        self.s1 = packed_struct_t()

        assert self.s0.width == self.s1.width == 35

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

        # Test nested structs
        self.test_nested_structs()
        await Timer(10, unit="ns")

        # Test the .value shortcut
        self.s0.value = 0
        assert self.s0.single_bit.value == 0 and self.s0.multi_bit.value == 0 and self.s0.state_enum.value == 0
        assert self.s0.value == 0

        self.s0.value = 1
        assert self.s0.single_bit.value == 0 and self.s0.multi_bit.value == 0 and self.s0.state_enum.value == 1
        assert self.s0.value == 1

        # Test the slice shortcuts
        self.s0.value = 0
        self.s0[34] = 1
        assert self.s0.single_bit.value == 1 and self.s0.multi_bit.value == 0 and self.s0.state_enum.value == 0
        assert self.s0[34] == 1

        self.s0.value = 0
        self.s0[2:34] = 0xdeadbeef
        assert self.s0.single_bit.value == 0 and self.s0.multi_bit.value == 0xdeadbeef and self.s0.state_enum.value == 0
        assert self.s0[2:34] == 0xdeadbeef

        self.drop_objection()

    def check_struct(self, struct, expected):
        self.info(f"Struct:{struct}")
        for field_name, _field_type in struct._fields_:
            field_val = getattr(struct, field_name)
            if hasattr(field_val, '_fields_'):  # it's a nested struct
                self.check_struct(field_val, expected)
            else:  # it's a leaf value
                self.info(f"  {field_name}: {field_val}")
                assert field_val == expected[field_name], \
                    f"variable {field_name} is not correctly assigned. Expected: {hex(expected[field_name])}, Actual: {hex(field_val)}"

    def test_nested_structs(self):
        _var_a = 0xA
        _var_b = 0xB
        _var_c = 0xC
        _var_d = 0xD
        init_val = (_var_a << 12) | (_var_b << 8) | (_var_c << 4) | _var_d

        # Create a dict to map field names to expected values
        expected = {
            "var_a": _var_a,
            "var_b": _var_b,
            "var_c": _var_c,
            "var_d": _var_d,
        }

        self.info(f"Testing nested struct with init_val = {hex(init_val)}")
        full_struct = struct_a_b_c_d_t()
        #using the from_bits function
        full_struct.from_bits(init_val)
        self.info("Calling check_struct for inital value")
        self.check_struct(full_struct, expected)
        #using the to_bits function
        self.info("Setting a varible using to_bits function")
        to_bits_var = full_struct.to_bits()
        self.info(f"Value set is equal to {hex(to_bits_var)}")
        assert to_bits_var == init_val, f"to_bits is not working. Expected {hex(init_val)}, Actual: {hex(to_bits_var)}"

@cocotb.test
async def test(dut):
    e = example_env("env", None)
    e.dut = dut.data

    await e.start()
