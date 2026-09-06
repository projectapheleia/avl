# Copyright 2026 Apheleia
#
# Description:
# Minimal AVL testbench used by the startup benchmark.
#
# Deliberately contains no verification content - it exists only to measure the
# cost of importing AVL and bringing up a standard environment.

import avl
import cocotb


class benchmark_env(avl.Env):
    pass


@cocotb.test
async def test(dut):
    _ = benchmark_env("env", None)
