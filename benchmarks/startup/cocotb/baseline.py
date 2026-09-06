# Copyright 2026 Apheleia
#
# Description:
# Minimal plain-cocotb testbench used as the startup benchmark reference.
#
# Identical in structure to example.py but with no reference to AVL, so the
# difference between the two runs is the AVL startup overhead.

import cocotb


@cocotb.test
async def test(dut):
    pass
