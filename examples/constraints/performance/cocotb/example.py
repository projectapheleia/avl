# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import time
from pprint import pp
import json

import avl
import cocotb
import matplotlib.pyplot as plt


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

@cocotb.test
async def test(dut):
    e = example_env("env", None)

    times: dict[int, float] = {}

    samples_per_decade = 5

    for i in range(15*samples_per_decade):
        var_count: int = int(2**(i/samples_per_decade))

        #e.a = [avl.Logic(0, width=32, fmt=hex) for i in range(var_count)]
        for i in range(var_count):
            setattr(e, f"var_{i}", avl.Logic(0, width=32, fmt=hex))
        start = time.time()
        e.randomize()
        end = time.time()

        elapsed_time: float = end - start
        print(f"Time taken (logic32) {var_count}: {elapsed_time:.2f} seconds")
        times[var_count] = elapsed_time
        with open("times.json", "w") as f:
            json.dump(times, f)


    plt.figure(1)
    plt.plot(list(times.keys()), list(times.values()))

    plt.xscale("log")
    plt.yscale("log")

    plt.xlabel("Vars Randomized")
    plt.ylabel("Time")

    plt.title("Time for AVL to Randomize Objects per Number of Vars")

    plt.savefig("time.png")

    pp(times)
