# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import copy

import avl
import cocotb
from z3 import And


class gnr_enum(avl.Enum):
    def __init__(self, value, auto_random=False, fmt=str):
        super().__init__(value, {"AXL": 0, "SLASH": 1, "DUFF": 2, "IZZY" : 4, "STEVEN" : 5}, auto_random=auto_random, fmt=fmt)

class container(avl.Object):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # avl.Int
        self.v = avl.Int(0, fmt=str)
        self.add_constraint("c_default", lambda x : And(x >= 0, x <= 1000), self.v)

        # avl.Enum
        self.e = avl.Enum("A", {"A" : 0, "B": 1, "C": 2})

        # Custom Enum
        self.g = gnr_enum("AXL")

        # int
        self.i = 0

        # object
        self.s = avl.Object("s", self)

class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Example to show shallow copy create new avl_var objects
        x = container("x", self)
        y = copy.copy(x)

        assert(x.v is not y.v and x.e is not y.e and x.g is not y.g)
        assert(x.v.value == y.v.value and x.e.value == y.e.value and x.g.value == y.g.value)

        # Show s is a reference
        assert(x.s is y.s)

        # Show avl_vars aren't related after copy
        y.i = 1
        assert(x.i == 0 and y.i == 1)

        # Show the variables in constraints aren't related after copy
        for k,v in x._constraints_[True].items():
            assert(k in y._constraints_[True].keys())    # Key exists
            assert(v[0] is y._constraints_[True][k][0])  # Lambda function is the same

            for i in range(len(v[1])):
                assert(v[1][i] is not y._constraints_[True][k][1][i]) # Variable is not the same

        # Example to show deep copy create new avl_var objects
        z = copy.deepcopy(x)
        assert(x.v is not y.v)

        # Show s is a reference
        assert(x.s is z.s)

        # Show avl_vars aren't related after copy
        z.i = 2
        assert(x.i == 0 and z.i == 2)

        # Show the variables in constraints aren't related after copy
        for k,v in x._constraints_[True].items():
            assert(k in z._constraints_[True].keys())    # Key exists
            assert(v[0] is z._constraints_[True][k][0])  # Lambda function is the same

            for i in range(len(v[1])):
                assert(v[1][i] is not z._constraints_[True][k][1][i]) # Variable is not the same

        # Show randomization doesn't bleed after copy
        for i in range(10):
            x.randomize(hard=[(lambda value, i=i: value == 100 + i, x.v)])
            y.randomize(hard=[(lambda value, i=i: value == 200 + i, y.v)])
            z.randomize(hard=[(lambda value, i=i: value == 300 + i, z.v)])
            assert(x.v.value == 100 + i and y.v.value == 200 + i and z.v.value == 300 + i)

        # Show constraints are copied correctly
        x.v.value = 0
        x.add_constraint("c", lambda value: value == 10, x.v)
        y = copy.copy(x)
        z = copy.deepcopy(x)
        x.randomize()
        assert(x.v.value == 10 and y.v.value == 0 and z.v.value == 0)
        y.randomize()
        assert(x.v.value == 10 and y.v.value == 10 and z.v.value == 0)
        x.randomize()
        assert(x.v.value == 10 and y.v.value == 10 and z.v.value == 0)

        # Show constraints are independent after copy
        y.add_constraint("c", lambda value: value == 20, y.v)
        z.add_constraint("c", lambda value: value == 30, z.v)
        x.randomize()
        y.randomize()
        z.randomize()
        assert(x.v.value == 10 and y.v.value == 20 and z.v.value == 30)

        # Show randomizing one object doesn't affect the others
        # First way using variable in lambda
        x = container("x", self)
        y = container("y", self)
        y.v.value = 10
        x.add_constraint("c", lambda value_a: value_a == y.v + 1, x.v)

        for _ in range(5):
            x.randomize()
            assert(x.v.value == y.v.value + 1)
            y.v += 1

        # Second way using variable in args but not in randomization
        x = container("x", self)
        y = container("y", self)
        y.v.value = 10
        x.add_constraint("c", lambda value_a, value_b: value_a == value_b + 1, x.v, y.v)
        for _ in range(5):
            x.randomize()
            assert(x.v.value == y.v.value + 1)
            y.v += 1

@cocotb.test
async def test(dut):
    example_env("env", None)
