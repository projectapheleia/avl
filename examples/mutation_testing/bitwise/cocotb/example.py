# Copyright 2026 Apheleia
#
# Description:
# AVL mutation testing example - bitwise
#
# An ordinary AVL testbench. It knows nothing about mutation testing; the
# Makefile decides which copy of the RTL to build.
#
#   make sim                   golden design
#   make sim AVL_MUTANT=1      build and run mutant 1, which should fail
#   make mutation_regression   every mutant in turn, scored

import copy

import avl
import cocotb
from cocotb.triggers import RisingEdge

Y_MASK = 0x1FF


def model(a, b):
    """
    The reference for what the DUT should produce.

    (a & b) ^ (a | b) is a ^ b, but written so that each bitwise operator appears.

    :param a: The a input.
    :type a: int
    :param b: The b input.
    :type b: int
    :return: The expected y output.
    :rtype: int
    """
    return (a ^ b) & 0xFF


class mutation_item(avl.SequenceItem):
    def __init__(self, name, parent_sequence):
        super().__init__(name, parent_sequence)

        self.a = avl.Uint8(0, fmt=str)
        self.b = avl.Uint8(0, fmt=str)
        self.y = avl.Logic(0, fmt=str, auto_random=False, width=9)

class mutation_sequence(avl.Sequence):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.n_items = avl.Factory.get_variable(f"{self.get_full_name()}.n_items", 200)

    async def body(self):
        self._parent_sequencer_.raise_objection()
        for _ in range(self.n_items):
            item = mutation_item("item", self)
            await self.start_item(item)
            item.randomize()
            # Uniform random stimulus is enough to expose this class.
            await self.finish_item(item)
        self._parent_sequencer_.drop_objection()

class mutation_sequencer(avl.Sequencer):
    def __init__(self, name, parent):
        super().__init__(name, parent)

class mutation_driver(avl.Driver):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def reset(self):
        self.hdl.valid_in.value = 0
        self.hdl.a.value = 0
        self.hdl.b.value = 0

    async def clear(self):
        await RisingEdge(self.hdl.clk)
        await self.reset()

    async def run_phase(self):
        await self.reset()

        await RisingEdge(self.hdl.clk)
        while True:
            item = await self.seq_item_port.blocking_get()

            while True:
                await RisingEdge(self.hdl.clk)
                if self.hdl.rst_n.value == 0:
                    await self.reset()
                else:
                    break

            self.hdl.valid_in.value = 1
            self.hdl.a.value = item.a.value
            self.hdl.b.value = item.b.value
            item.set_event("done")
            cocotb.start_soon(self.clear())

class mutation_monitor(avl.Monitor):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def collect_result(self, item):
        # One cycle after valid_in the answer is on the output. A pipeline
        # defect breaks exactly this expectation.
        await RisingEdge(self.hdl.clk)
        if self.hdl.valid_out.value != 1:
            self.error(f"Expected valid_out to be 1, got {self.hdl.valid_out.value}")

        item.y.value = int(self.hdl.y.value) & Y_MASK
        self.item_export.write(item)

    async def run_phase(self):
        while True:
            await RisingEdge(self.hdl.clk)

            if self.hdl.rst_n.value == 0:
                continue

            if self.hdl.valid_in.value == 1:
                item = mutation_item("item", None)
                item.a.value = int(self.hdl.a.value)
                item.b.value = int(self.hdl.b.value)
                cocotb.start_soon(self.collect_result(item))

class mutation_model(avl.Model):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def run_phase(self):
        while True:
            monitor_item = await self.item_port.blocking_get()
            model_item = copy.deepcopy(monitor_item)
            model_item.y.value = model(int(monitor_item.a.value), int(monitor_item.b.value))
            self.item_export.write(model_item)

class mutation_scoreboard(avl.Scoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.set_min_compare_count(100)

class mutation_agent(avl.Agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.sqr = mutation_sequencer("sqr", self)
        self.seq = mutation_sequence("seq", self.sqr)
        self.drv = mutation_driver("drv", self)
        self.mon = mutation_monitor("mon", self)
        self.model = mutation_model("model", self)
        self.sb = mutation_scoreboard("sb", self)

        self.seq.set_sequencer(self.sqr)

    async def connect_phase(self):
        self.sqr.seq_item_export.connect(self.drv.seq_item_port)

        self.mon.item_export.connect(self.model.item_port)
        self.mon.item_export.connect(self.sb.after_port)
        self.model.item_export.connect(self.sb.before_port)

    async def run_phase(self):
        self.raise_objection()
        await self.seq.start()
        self.drop_objection()

class mutation_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.agent = mutation_agent("agent", self)

    async def connect_phase(self):
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.rst = avl.Factory.get_variable(f"{self.get_full_name()}.rst", None)
        self.clk_freq_mhz = avl.Factory.get_variable(f"{self.get_full_name()}.clk_freq_mhz", 100)
        self.reset_ns = avl.Factory.get_variable(f"{self.get_full_name()}.reset_ns", 100)
        self.timeout_ns = avl.Factory.get_variable(f"{self.get_full_name()}.timeout_ns", 100000)

    async def run_phase(self):
        cocotb.start_soon(self.clock(self.clk, self.clk_freq_mhz))
        cocotb.start_soon(self.async_reset(self.rst, self.reset_ns, active_high=False))
        cocotb.start_soon(self.timeout(self.timeout_ns))

@cocotb.test
async def test(dut):
    avl.PhaseManager.add_phase("BUILD", after=None, top_down=True)
    avl.PhaseManager.add_phase("CONNECT", after=avl.PhaseManager.get_phase("BUILD"), top_down=True)

    avl.Factory.set_variable('*.hdl', dut)
    avl.Factory.set_variable('*.clk', dut.clk)
    avl.Factory.set_variable('*.rst', dut.rst_n)
    avl.Factory.set_variable('env.timeout_ns', 100000)
    avl.Factory.set_variable('env.clk_freq_mhz', 100)
    avl.Factory.set_variable('*.n_items', 200)

    e = mutation_env('mutation_env', None)
    await e.start()
