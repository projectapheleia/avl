# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb

class Item(avl.Object):
    def __init__(self):
        super().__init__("item", None)
        self.a = avl.Logic(0, width=8)
        self.b = avl.Logic(0, width=8)
        self.add_constraint("c_a_nonzero", lambda x: x != 0, self.a)

@cocotb.test
async def test(dut):
    item = Item()
    item.a._auto_random_ = False     # freeze a at value 0
    item.randomize()                 # before: raises; after: passes, b gets a random value
