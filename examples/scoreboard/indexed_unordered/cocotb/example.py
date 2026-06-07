# Copyright 2024 Apheleia
#
# Description:
# Apheleia scoreboard example


import random

import avl
import cocotb
from cocotb.triggers import Timer


class example_item(avl.Object):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.value = None


class example_sb(avl.IndexedScoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    def get_index(self, item):
        return item.value


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.sb = example_sb("sb", self)
        self.sb.set_verbose(True)
        self.sb.set_indices(range(10))

    async def run_phase(self):
        # send a random amount of items to both before and after ports every time, and let indexed scoreboard handle this
        self.raise_objection()

        before = []
        after = []
        for i in range(10):
            item = example_item("item" + str(i), None)
            item.value = i
            before.append(item)
            after.append(item)

        random.shuffle(before)
        random.shuffle(after)

        while len(before) > 0 or len(after) > 0:
            await Timer(random.randint(1, 5), "ns")

            # send a random number of before items this cycle
            n_before = random.randint(1, 3)
            for _ in range(n_before):
                if len(before) > 0:
                    self.sb.before_port.append(before.pop(0))

            await Timer(random.randint(1, 5), "ns")

            # send a different random number of after items this cycle
            n_after = random.randint(1, 3)
            for _ in range(n_after):
                if len(after) > 0:
                    self.sb.after_port.append(after.pop(0))

        self.drop_objection()


@cocotb.test
async def test(dut):
    e = example_env("env", None)
    await e.start()
