# Copyright 2024 Apheleia
#
# Description:
# Apheleia phase example
# https://verificationguide.com/uvm/uvm-testbench/

import copy

import avl
import avl.templates
import cocotb
from cocotb.triggers import RisingEdge


class adder_item(avl.SequenceItem):
    def __init__(self, name, parent_sequence):
        super().__init__(name, parent_sequence)

        self.a = avl.Uint8(0, fmt=str)
        self.b = avl.Uint8(0, fmt=str)
        self.c = avl.Logic(0, fmt=str, auto_random=False, width=9)

class adder_sequence(avl.Sequence):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.n_items = avl.Factory.get_variable(f"{self.get_full_name()}.n_items", 200)

    async def body(self):
        self._parent_sequencer_.raise_objection()
        for _ in range(self.n_items):
            item = adder_item("item", self)
            await self.start_item(item)
            item.randomize()
            await self.finish_item(item)
        self._parent_sequencer_.drop_objection()

class adder_sequencer(avl.Sequencer):
    def __init__(self, name, parent):
        super().__init__(name, parent)

class adder_driver(avl.Driver):
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

class adder_monitor(avl.Monitor):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        self.cg = avl.Covergroup('cg',self)
        self.cp_a = self.cg.add_coverpoint('cp_a', lambda: self.hdl.a.value)
        self.cp_a.add_bin('a_zero_bin',0)
        self.cp_a_cross = self.cg.add_coverpoint('cp_a_cross', lambda: self.hdl.a.value)
        self.cp_a_cross.add_bin('a_overflow',range(128,255))

        self.cp_b = self.cg.add_coverpoint('cp_b', lambda: self.hdl.b.value)
        self.cp_b.add_bin('b_zero_bin',0)
        self.cp_b_cross = self.cg.add_coverpoint('cp_b_cross', lambda: self.hdl.b.value)
        self.cp_b_cross.add_bin('b_overflow',range(128,255))

        self.cg.add_covercross("overflow_cover",self.cp_a_cross, self.cp_b_cross)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def collect_result(self, item):
        await RisingEdge(self.hdl.clk)
        if self.hdl.valid_out.value != 1:
            self.error(f"Expected valid_out to be 1, got {self.hdl.valid_out.value}")

        item.c.value = int(self.hdl.c.value)
        self.item_export.write(item)

    async def run_phase(self):
        while True:
            await RisingEdge(self.hdl.clk)

            if self.hdl.rst_n.value == 0:
                continue

            if self.hdl.valid_in.value == 1:
                item = adder_item("item", None)
                item.a.value = int(self.hdl.a.value)
                item.b.value = int(self.hdl.b.value)
                cocotb.start_soon(self.collect_result(item))

            # collect coverage
            self.cg.sample()

    async def report_phase(self):
        print(self.cg.report(full=True))

class adder_model(avl.Model):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def run_phase(self):
        while True:

            monitor_item = await self.item_port.blocking_get()
            model_item = copy.deepcopy(monitor_item)
            model_item.c.value = monitor_item.a.value + monitor_item.b.value
            self.item_export.write(model_item)

class adder_scoreboard(avl.Scoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.set_min_compare_count(100)

class adder_agent(avl.Agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.info("Creating adder agent")

    async def build_phase(self):
        self.sqr = adder_sequencer("sqr", self)
        self.seq = adder_sequence("seq", self.sqr)
        self.drv = adder_driver("drv", self)
        self.mon = adder_monitor("mon", self)
        self.model = adder_model("model", self)
        self.sb = adder_scoreboard("sb", self)

        # Set the sequencer for the sequence
        self.seq.set_sequencer(self.sqr)

    async def connect_phase(self):
        # Connect the sequencer to the driver
        self.sqr.seq_item_export.connect(self.drv.seq_item_port)

        # Connect the monitor to the model and scoreboard
        self.mon.item_export.connect(self.model.item_port)
        self.mon.item_export.connect(self.sb.after_port)
        self.model.item_export.connect(self.sb.before_port)

    async def run_phase(self):
        self.raise_objection()

        # Start the sequence
        self.info(f"Starting sequence {self.seq.get_full_name()}")
        await self.seq.start()
        self.info(f"Sequence {self.seq.get_full_name()} completed")
        self.drop_objection()

class adder_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.agent = adder_agent("agent", self)

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

    # Create the environment
    avl.Factory.set_variable('*.hdl', dut)
    avl.Factory.set_variable('*.clk', dut.clk)
    avl.Factory.set_variable('*.rst', dut.rst_n)
    avl.Factory.set_variable('env.timeout_ns', 100000)
    avl.Factory.set_variable('env.clk_freq_mhz', 100)
    avl.Factory.set_variable('*.n_items', 200)

    e = adder_env('adder_env', None)
    await e.start()
