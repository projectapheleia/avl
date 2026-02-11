# Copyright 2024 Apheleia
#
# Description:
# Apheleia scoreboard example


import random

import avl
import cocotb
from cocotb.triggers import Timer


class example_item(avl.SequenceItem):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.value = 0

    def randomize(self):
        self.value = random.randint(0x0, 0xFF)


class example_sequence(avl.Sequence):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)

    def response_cb(self, item, ok=False):
        if ok:
            self.info(f"Item {item.name} ok")
        else:
            self.error(f"Item {item.name} not ok")

    async def body(self):
        for i in range(5):
            item = example_item(f"item_{i}", self)
            item.add_event("response", self.response_cb)

            await self.start_item(item)
            item.randomize()
            await self.finish_item(item)

            await item.wait_on_event("response")


class example_driver(avl.Driver):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.count = 0

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.blocking_get()
            self.debug(f"Driving item :\n{item}")
            item.set_event("done")
            self.count += 1

            item.set_event("response", item, ok=True)

    async def report_phase(self):
        if self.count != 5:
            self.error(f"Expected 5 items, got {self.count}")
        else:
            self.info("All items driven")


class example_sequencer(avl.Sequencer):
    def __init__(self, name, parent):
        super().__init__(name, parent)


class example_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.driver = example_driver("driver", self)
        self.sequencer = example_sequencer("sequencer", self)

        self.sequencer.seq_item_export.connect(self.driver.seq_item_port)

    async def run_phase(self):
        self.raise_objection()

        seq = example_sequence("sequence", self.sequencer)
        await seq.start()

        await Timer(1000, "ns")

        self.drop_objection()


@cocotb.test
async def test(dut):
    e = example_env("env", None)
    await e.start()
