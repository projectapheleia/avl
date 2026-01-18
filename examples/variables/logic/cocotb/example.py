# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
from z3 import And


class example_env(avl.Env):

    def test_unsigned(self):

        self.info("Testing unsigned logic and arithmetic operations...")

        a = avl.Logic(5, width=4)     # 0b0101
        b = avl.Logic(13, width=4)    # 0b1101

        c = 1 + a
        assert c == 6              # (1 + 5) % 16 = 6
        assert type(c) is avl.Logic  # Ensure c is still a Logic object

        # Constants
        mod = 1 << 4  # 16
        assert mod == 16

        # Arithmetic
        assert a + b == 2          # (5 + 13) % 16 = 18 % 16 = 2
        assert a - b == 8          # (5 - 13) % 16 = -8 % 16 = 8
        assert b - a == 8          # (13 - 5) % 16 = 8
        assert -a == 11            # (-5) % 16 = 11
        assert abs(b) == 13


        # Overflow / wraparound
        max_val = avl.Logic(15, width=4)
        assert max_val + 1 == 0    # 15 + 1 = 16 % 16 = 0

        min_val = avl.Logic(0, width=4)
        assert min_val - 1 == 15   # 0 - 1 = -1 % 16 = 15

        # Multiplication / division
        assert a * 3 == 15         # (5 * 3) % 16 = 15
        assert b // 2 == 6         # 13 // 2 = 6
        assert b % 4 == 1          # 13 % 4 = 1

        # Comparisons
        assert (a < b) is True     # 5 < 13
        assert (a > b) is False
        assert (a == 5) is True
        assert (b != 5) is True
        assert (a <= 5) is True
        assert (b >= 13) is True

        # Bitwise operations
        assert a & b == 5          # 0b0101 & 0b1101 = 0b0101 = 5
        assert a | b == 13         # 0b0101 | 0b1101 = 0b1101 = 13
        assert a ^ b == 8          # 0b0101 ^ 0b1101 = 0b1000 = 8
        assert ~a == 10            # ~5 = -6 % 16 = 10

        # Shifts
        assert a << 1 == 10        # (5 << 1) % 16 = 10
        assert b >> 1 == 6         # 13 >> 1 = 6

        # Oversized int operands
        assert a + 1000 == 13      # (5 + 1000) % 16 = 1005 % 16 = 13
        assert a - 300 == 9        # (5 - 300) % 16 = -295 % 16 = 9
        assert a * 123 == 7        # (5 * 123) % 16 = 615 % 16 = 7
        assert b // 999 == 0       # 13 // 999 = 0
        assert b % 99 == 13        # 13 % 99 = 13

        # Comparisons with large ints
        assert (a < 1000) is True
        assert (b < 1000) is True
        assert (a > -1000) is True
        assert (b != 999) is True

        # Bitwise operations with oversized ints
        assert a & 0b10011010010 == 0   # 5 & (1234 % 16 = 2) = 0b0101 & 0b0010 = 0b0000 = 0
        assert a | 0b10011010010 == 7   # 5 | 2 = 0b0101 | 0b0010 = 0b0111 = 7
        assert a ^ 0b10011010010 == 7   # 5 ^ 2 = 0b0101 ^ 0b0010 = 0b0111 = 7

        # Immutability check
        a_id = id(a)
        c = a + 1
        assert c == 6
        assert id(a) == a_id
        assert id(c) != a_id

        a += 1
        assert a == 6
        assert id(a) == a_id  # a should still point to the same object
        assert id(c) != a_id  # c should still point to a different object

        # slices
        c = avl.Logic(0xdeadbeef, width=32)
        assert c[0:8] == 0xef
        assert c[24:32] == 0xde
        assert c[8:24] == 0xadbe
        assert c[19] == 1
        assert c[14] == 0

        c[8:16] = 0xab
        assert c == 0xdeadabef
        c[3] = 0
        assert c == 0xdeadabe7

        self.info("Unsigned logic and arithmetic operations passed successfully.")

    def test_randomization(self):

        self.info("Testing randomization...")

        # Create a random Logic variable
        rand_var = avl.Logic(0, auto_random=True, width=4)

        # Check if the value is within the expected range
        assert 0 <= rand_var < (1 << 4)

        # Simple randomization
        for _ in range(10):
            rand_var.randomize(hard=[lambda x: And(x >=1, x <= 2)])
            assert  rand_var >= 1 and rand_var <= 2

        # Bitwise
        for _ in range(10):
            rand_var.randomize(hard=[lambda x: And(x & 0b0001 == 0, x & 0b0010 == 0)])
            assert rand_var.value % 4 == 0

            rand_var.randomize(hard=[lambda x: (x ^ 0b0011) & 0b0011 == 0])
            assert rand_var.value % 4 == 3

        self.info("Randomization test passed successfully.")

    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Test unsigned arithmetic operations
        self.test_unsigned()

        # Test randomization
        self.test_randomization()


@cocotb.test
async def test(dut):
    _ = example_env("env", None)
