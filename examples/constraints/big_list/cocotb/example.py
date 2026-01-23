# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import time

import avl
import cocotb


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

@cocotb.test
async def test(dut):
    e = example_env("env", None)

    e.a = [avl.Logic(0, width=32, fmt=hex) for i in range(2048)]
    start = time.time()
    e.randomize()
    end = time.time()
    print(f"Time taken (logic32): {end - start:.2f} seconds")

    e.a = [avl.Uint32(0, fmt=hex) for i in range(2048)]
    start = time.time()
    e.randomize()
    end = time.time()
    print(f"Time taken (Uint32): {end - start:.2f} seconds")

    e.a = [avl.Int8(0, fmt=str) for i in range(2048)]
    start = time.time()
    e.randomize()
    end = time.time()
    print(f"Time taken (Int8): {end - start:.2f} seconds")

    e.a = [avl.Int64(0, fmt=str) for i in range(2048)]
    start = time.time()
    e.randomize()
    end = time.time()
    print(f"Time taken (Int64): {end - start:.2f} seconds")

    # Add a constraint - will be slower (but should work)
    e.a = [avl.Int32(0, fmt=str) for i in range(2048)]
    for i in range(len(e.a)):
        e.a[i].add_constraint("c", lambda x,i=i: x == i)

    start = time.time()
    e.randomize()
    end = time.time()
    for i in range(2048):
        assert e.a[i] == i
    print(f"Time taken (Int32 + constraint): {end - start:.2f} seconds")
