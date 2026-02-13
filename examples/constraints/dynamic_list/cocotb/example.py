# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example



import time

import avl
import cocotb
from z3 import And, If


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Size array to maximum size required
        self.a = [avl.Int32(0) for i in range(8)]

        # Declare a var to randomize the size of the array
        self.size = avl.Int32(0)

        # Constrain the size of the array
        self.add_constraint(
            "size_c",
            lambda x: And(x > 0, x <= 8),
            self.size
        )

        # Constrain the first element of the array to a random number between 0 and 100
        self.add_constraint(
            "a0_c",
            lambda x: And(x >= 0, x <= 100),
            self.a[0]
        )

        # Constrain the rest of the elements of the array to be one greater than the previous element
        for i in range(1, len(self.a)):
            self.add_constraint(
                f"a{i}_c",
                lambda x, y, z, idx=i: If(idx < z, x == y + 1, x == 0),
                self.a[i],
                self.a[i - 1],
                self.size
            )

@cocotb.test
async def test(dut):
    e = example_env("env", None)

    start = time.time()
    for _ in range(10):
        e.randomize()
        assert(e.size > 0 and e.size <= 8)

        for i in range(0, int(e.size)):
            if i == 0:
                assert e.a[i] >= 0 and e.a[i] <= 100
            else:
                assert e.a[i] == e.a[i - 1] + 1
    end = time.time()
    print(f"Time taken : {end - start:.2f} seconds")
