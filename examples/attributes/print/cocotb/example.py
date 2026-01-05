# Copyright 2024 Apheleia
#
# Description:
# Apheleia attributes example


import avl
import cocotb
from collections import OrderedDict, defaultdict


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Python variables
        self.dec_var = 100
        self.hex_var = 100
        self.custom_var = 100
        self.hex_list = [100, 200, 300]
        self.dec_set = {100, 200, 300}
        self.hex_dict = {"A": 100, "B": 200, "C": 300}
        self.list_list = [[0,1], [2,3], [4,5]]
        self.simple_dict = {"A": 1, "B": 2, "C": 3}
        self.list_dict = {"X" : ["a", "b"], "Y" : [0]}
        self.mixed = [{"dict" : ["value1", "value2"]}, ["list0", "list1", avl.Uint32(100, fmt=bin)]]
        self.obj = avl.Object("obj", self)
        self.tuple_var = (1, 2, 3)
        self.dict_tuple = {"T1" : (10, 20), "T2" : (30, 40)}
        self.dict_set = {"S1" : {1,2,3}, "S2" : {4,5,6}}
        self.odict = OrderedDict({"one": 1, "two": 2, "three": 3})
        self.ddict = defaultdict(list, {"first": [1,2], "second": [3,4]})

        self.set_field_attributes("hex_var", fmt=hex)
        self.set_field_attributes("hex_list", fmt=hex)
        self.set_field_attributes("hex_dict", fmt=hex)
        self.set_field_attributes("custom_var", fmt=self.custom_fmt)

    def custom_fmt(self, value):
        return f"custom_var={value}"


@cocotb.test
async def test(dut):
    e = example_env("env", None)

    for f in [e._table_fmt_, "fancy_grid", "presto", "simple_grid", "psql", "orgtbl", "rst", "jira"]:
      print(f"\n\n{f}:\n\n")
      e.set_table_fmt(fmt=f)
      print(e)

    # Stick to grid - show transpose
    e.set_table_fmt(fmt="grid", transpose=True)
    print(e)

    # Show recurse
    e.set_table_fmt(recurse=False)
    print(e)
