# Copyright 2026 Apheleia
#
# Description:
# Apheleia mutation testing example - ALU
#
# This is an ordinary AVL testbench and knows nothing about mutation testing.
# avl-mutation-testing generates mutated copies of the RTL from the golden
# source, and the Makefile chooses which copy to build:
#
#   make sim                   golden design
#   make sim AVL_MUTANT=2      build and run mutant 2
#   make mutation_regression   every mutant in turn, scored

import copy

import avl
import cocotb
from cocotb.triggers import RisingEdge

OP_ADD = 0
OP_SUB = 1
OP_AND = 2

RESULT_MASK = 0x1FF


class alu_item(avl.SequenceItem):
    def __init__(self, name, parent_sequence):
        super().__init__(name, parent_sequence)

        self.a = avl.Uint8(0, fmt=str)
        self.b = avl.Uint8(0, fmt=str)
        self.op = avl.Logic(0, fmt=str, width=2)
        self.result = avl.Logic(0, fmt=str, auto_random=False, width=9)
        self.zero = avl.Logic(0, fmt=str, auto_random=False, width=1)

class alu_sequence(avl.Sequence):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.n_items = avl.Factory.get_variable(f"{self.get_full_name()}.n_items", 200)

    async def body(self):
        self._parent_sequencer_.raise_objection()
        for _ in range(self.n_items):
            item = alu_item("item", self)
            await self.start_item(item)
            item.randomize()
            await self.finish_item(item)
        self._parent_sequencer_.drop_objection()

class alu_sequencer(avl.Sequencer):
    def __init__(self, name, parent):
        super().__init__(name, parent)

class alu_driver(avl.Driver):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def reset(self):
        self.hdl.valid_in.value = 0
        self.hdl.a.value = 0
        self.hdl.b.value = 0
        self.hdl.op.value = 0

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
            self.hdl.op.value = item.op.value
            item.set_event("done")
            cocotb.start_soon(self.clear())

class alu_monitor(avl.Monitor):
    def __init__(self, name, parent):
        super().__init__(name, parent)

        # Mutation 3 only shows up on the zero flag, so the operation mix has
        # to be covered for the campaign to mean anything.
        self.cg = avl.Covergroup("cg", self)
        self.cp_op = self.cg.add_coverpoint("cp_op", lambda: self.hdl.op.value)
        self.cp_op.add_bin("add", OP_ADD)
        self.cp_op.add_bin("sub", OP_SUB)
        self.cp_op.add_bin("and", OP_AND)

        self.cp_zero = self.cg.add_coverpoint("cp_zero", lambda: self.hdl.zero.value)
        self.cp_zero.add_bin("result_zero", 1)
        self.cp_zero.add_bin("result_nonzero", 0)

    async def connect_phase(self):
        self.hdl = avl.Factory.get_variable(f"{self.get_full_name()}.hdl", None)

    async def collect_result(self, item):
        await RisingEdge(self.hdl.clk)
        if self.hdl.valid_out.value != 1:
            self.error(f"Expected valid_out to be 1, got {self.hdl.valid_out.value}")

        item.result.value = int(self.hdl.result.value)
        item.zero.value = int(self.hdl.zero.value)
        self.item_export.write(item)

    async def run_phase(self):
        while True:
            await RisingEdge(self.hdl.clk)

            if self.hdl.rst_n.value == 0:
                continue

            if self.hdl.valid_in.value == 1:
                item = alu_item("item", None)
                item.a.value = int(self.hdl.a.value)
                item.b.value = int(self.hdl.b.value)
                item.op.value = int(self.hdl.op.value)
                cocotb.start_soon(self.collect_result(item))

            self.cg.sample()

    async def report_phase(self):
        print(self.cg.report(full=True))

class alu_model(avl.Model):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def run_phase(self):
        while True:
            monitor_item = await self.item_port.blocking_get()
            model_item = copy.deepcopy(monitor_item)

            a = int(monitor_item.a.value)
            b = int(monitor_item.b.value)
            op = int(monitor_item.op.value)

            if op == OP_ADD:
                out = a + b
            elif op == OP_SUB:
                out = a - b
            elif op == OP_AND:
                out = a & b
            else:
                out = a ^ b
            out &= RESULT_MASK

            model_item.result.value = out
            model_item.zero.value = int(out == 0)
            self.item_export.write(model_item)

class alu_scoreboard(avl.Scoreboard):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        self.set_min_compare_count(100)

class alu_agent(avl.Agent):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.sqr = alu_sequencer("sqr", self)
        self.seq = alu_sequence("seq", self.sqr)
        self.drv = alu_driver("drv", self)
        self.mon = alu_monitor("mon", self)
        self.model = alu_model("model", self)
        self.sb = alu_scoreboard("sb", self)

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

class alu_env(avl.Env):
    def __init__(self, name, parent):
        super().__init__(name, parent)

    async def build_phase(self):
        self.agent = alu_agent("agent", self)

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

    e = alu_env('alu_env', None)
    await e.start()
