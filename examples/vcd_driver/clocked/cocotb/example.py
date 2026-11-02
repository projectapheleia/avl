# Copyright 2026 Apheleia
#
# Description:
# Apheleia VCD driver example - clocked replay

import copy
import os

import avl
import cocotb
from cocotb.triggers import RisingEdge

STIMULUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "stimulus", "adder.vcd")
N_ITEMS = 100


class adder_item(avl.SequenceItem):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.a = avl.Uint8(0, fmt=str)
        self.b = avl.Uint8(0, fmt=str)
        self.c = avl.Logic(0, fmt=str, auto_random=False, width=9)


class adder_monitor(avl.Monitor):
    def __init__(self, name, parent):
        super().__init__(name, parent)

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
        # The capture holds exactly this many additions; fewer means something was not replayed
        self.set_min_compare_count(N_ITEMS)


class adder_agent(avl.Agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.drv = avl.VcdDriver("drv", self)
        self.mon = adder_monitor("mon", self)
        self.model = adder_model("model", self)
        self.sb = adder_scoreboard("sb", self)

    async def connect_phase(self):
        hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

        # Replay inputs on the testbench clock, excluding captured outputs
        grp = self.drv.add_clock("adder.clk", hdl.clk)
        grp.add_scope("adder", hdl, exclude=("valid_out", "c"))

        self.mon.item_export.connect(self.model.item_port)
        self.mon.item_export.connect(self.sb.after_port)
        self.model.item_export.connect(self.sb.before_port)


class adder_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.agent = adder_agent("agent", self)

    async def connect_phase(self):
        self.clk = avl.Factory.get_variable(f"{self.get_full_name()}.clk", None)
        self.clk_freq_mhz = avl.Factory.get_variable(f"{self.get_full_name()}.clk_freq_mhz", 100)
        self.timeout_ns = avl.Factory.get_variable(f"{self.get_full_name()}.timeout_ns", 100000)

    async def run_phase(self):
        # The clock is the testbench's; the driver's clock group follows it. Reset comes
        # from the capture. The driver holds the run phase open until every cycle is replayed.
        cocotb.start_soon(self.clock(self.clk, self.clk_freq_mhz))
        cocotb.start_soon(self.timeout(self.timeout_ns))


@cocotb.test
async def test(dut):
    avl.PhaseManager.add_phase("BUILD", after=None, top_down=True)
    avl.PhaseManager.add_phase("CONNECT", after=avl.PhaseManager.get_phase("BUILD"), top_down=True)

    avl.Factory.set_variable("*.hdl", dut)
    avl.Factory.set_variable("*.clk", dut.clk)
    avl.Factory.set_variable("*.drv.vcd_file", STIMULUS)
    avl.Factory.set_variable("env.clk_freq_mhz", 100)
    avl.Factory.set_variable("env.timeout_ns", 100000)

    e = adder_env("env", None)
    await e.start()
